"""Codex SDK approval callback bridge."""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from typing import Any, Callable

from app.database import async_session_scope
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tools.claude.permission_hooks import PermissionHooks
from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

APPROVAL_METHODS = {
    "item/commandExecution/requestApproval": "shell",
    "item/fileChange/requestApproval": "write_file",
}
DECLINED_APPROVAL_METHODS = {"item/permissions/requestApproval"}
DEFAULT_OPTIONS = PermissionHooks.DEFAULT_PERMISSION_OPTIONS


def default_decline_response(method: str) -> dict[str, Any]:
    """Return a schema-valid negative response for an unhandled request."""
    if method in APPROVAL_METHODS:
        return {"decision": "decline"}
    if method in DECLINED_APPROVAL_METHODS:
        return {"permissions": {}, "scope": "turn"}
    return {}


class CodexApprovalHandler:
    """Bridge the SDK sync approval callback to the async WebSocket UI."""

    def __init__(
        self,
        session_id: str,
        task_id: str,
        emit_event: Callable[[str, dict[str, Any]], None],
        loop: asyncio.AbstractEventLoop,
        timeout_seconds: int = 60,
    ) -> None:
        self.session_id = session_id
        self.task_id = task_id
        self.emit_event = emit_event
        self.loop = loop
        self.timeout_seconds = timeout_seconds
        self._pending: dict[str, threading.Event] = {}
        self._results: dict[str, str] = {}
        self._request_options: dict[str, list[dict[str, Any]]] = {}

    def sync_approval_callback(self, method: str, params: dict | None) -> dict[str, Any]:
        """Handle Codex SDK approval callback from a worker thread."""
        if method in DECLINED_APPROVAL_METHODS:
            logger.info(
                "Declining unsupported Codex approval method=%s session=%s",
                method,
                self.session_id[:8],
            )
            return {"permissions": {}, "scope": "turn"}

        if method not in APPROVAL_METHODS:
            logger.warning(
                "Unknown Codex approval method=%s session=%s",
                method,
                self.session_id[:8],
            )
            return {}

        approval_id = str(uuid.uuid4())
        ready = threading.Event()
        self._pending[approval_id] = ready
        self._request_options[approval_id] = [dict(option) for option in DEFAULT_OPTIONS]

        future = asyncio.run_coroutine_threadsafe(
            self._request_via_websocket(approval_id, method, params or {}),
            self.loop,
        )
        try:
            future.result(timeout=10)
        except Exception:
            logger.exception("Failed to emit Codex approval request")
            self._pending.pop(approval_id, None)
            self._request_options.pop(approval_id, None)
            return {"decision": "cancel"}

        if not ready.wait(self.timeout_seconds):
            self._pending.pop(approval_id, None)
            self._request_options.pop(approval_id, None)
            self.emit_event(
                "tool-decision:timeout",
                {
                    "request_id": approval_id,
                    "session_id": self.session_id,
                    "task_id": self.task_id,
                },
            )
            return {"decision": "cancel"}

        sdk_decision = self._results.pop(approval_id, "cancel")
        self._request_options.pop(approval_id, None)
        return {"decision": sdk_decision}

    async def _request_via_websocket(
        self,
        approval_id: str,
        method: str,
        params: dict[str, Any],
    ) -> None:
        tool_name = APPROVAL_METHODS[method]
        tool_input = self._extract_tool_input(method, params)
        tool_call = {
            "toolCallId": approval_id,
            "title": tool_name,
            "kind": "execute",
            "rawInput": tool_input,
        }
        options = self._request_options[approval_id]

        async with async_session_scope() as db:
            message_service = MessageService(db)
            await message_service.create_permission_request(
                session_id=self.session_id,
                task_id=self.task_id,
                request_id=approval_id,
                tool_name=tool_name,
                tool_input=tool_input,
                decision_type="permission",
                options=options,
                raw_tool_call=tool_call,
                tool_call_id=approval_id,
            )

        self.emit_event(
            "tool-decision:request",
            {
                "request_id": approval_id,
                "session_id": self.session_id,
                "task_id": self.task_id,
                "decision_type": "permission",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "options": options,
                "tool_call": tool_call,
                "timeout": self.timeout_seconds,
                "timestamp": utcnow().isoformat(),
            },
        )

    def _extract_tool_input(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "item/commandExecution/requestApproval":
            command = params.get("command") or params.get("cmd") or params.get("commandLine")
            cwd = params.get("cwd") or params.get("workingDirectory")
            return {"command": command, "cwd": cwd}

        if method == "item/fileChange/requestApproval":
            return {
                "path": params.get("grantRoot") or params.get("path"),
                "reason": params.get("reason"),
            }

        return dict(params)

    def resolve_decision(self, decision: dict[str, Any]) -> bool:
        approval_id = decision.get("request_id")
        if not approval_id:
            return False

        thread_event = self._pending.pop(approval_id, None)
        if thread_event is None:
            return False

        outcome = decision.get("outcome", "")
        option_id = decision.get("option_id") or decision.get("optionId") or ""
        options = self._request_options.get(approval_id, DEFAULT_OPTIONS)
        matched = next(
            (
                option
                for option in options
                if (option.get("option_id") or option.get("optionId")) == option_id
            ),
            None,
        )

        sdk_decision = "cancel" if outcome == "cancelled" else "decline"
        if outcome != "cancelled" and matched:
            kind = matched.get("kind", "")
            scope = decision.get("scope") or matched.get("scope")
            if kind.startswith("reject"):
                sdk_decision = "decline"
            elif kind.startswith("allow"):
                sdk_decision = "acceptForSession" if scope == "session" else "accept"

        self._results[approval_id] = sdk_decision
        thread_event.set()
        return True
