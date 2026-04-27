"""ACP client implementation (workspace-runtime side)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from acp import RequestError
from acp.schema import (
    AllowedOutcome,
    DeniedOutcome,
    EnvVariable,
    PermissionOption,
    ReadTextFileResponse,
    RequestPermissionResponse,
    TerminalExitStatus,
    TerminalOutputResponse,
    ToolCallUpdate,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from app.database import async_session_scope
from app.modules.agent_session.services.tool_decision_service import ToolDecisionService
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.task_service import TaskService
from app.modules.agent_session.services.tools.base.streaming_callbacks import StreamingCallbacks
from app.modules.agent_session.services.tool_decision_manager import global_tool_decision_manager
from app.modules.file_system.service import FileService
from app.modules.file_system.exceptions import FileNotFoundException

from .terminal_manager import TerminalProcessManager

logger = logging.getLogger(__name__)


class AcpClient:
    """ACP Client (implements ACP Client interface)."""

    def __init__(self, runtime_session_id: str, workspace_path: str) -> None:
        self.runtime_session_id = runtime_session_id
        self.workspace_path = Path(workspace_path).resolve()

        self.current_task_id: Optional[str] = None
        self.streaming_callbacks: Optional[StreamingCallbacks] = None
        self.emit_event = None

        self._stream_message_id: Optional[str] = None
        self._thinking_message_id: Optional[str] = None
        self._current_text: str = ""
        self._current_thinking: str = ""

        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, Dict[str, Any]] = {}

        self._tool_executions: list[dict[str, Any]] = []

        self._terminal_manager = TerminalProcessManager(str(self.workspace_path))

    def set_task_context(
        self,
        task_id: str,
        streaming_callbacks: Optional[StreamingCallbacks],
        emit_event: Optional[Any],
    ) -> None:
        self.current_task_id = task_id
        self.streaming_callbacks = streaming_callbacks
        self.emit_event = emit_event
        self._reset_buffers()

    def _reset_buffers(self) -> None:
        self._stream_message_id = None
        self._thinking_message_id = None
        self._current_text = ""
        self._current_thinking = ""
        self._tool_executions = []

    def on_connect(self, conn: Any) -> None:
        """ACP connection hook."""
        # Register for tool decision routing
        global_tool_decision_manager.register_hooks(self.runtime_session_id, self)

    def resolve_decision(self, decision: Dict[str, Any]) -> bool:
        request_id = decision.get("request_id")
        if not request_id:
            return False
        event = self._pending_decisions.get(request_id)
        if not event:
            return False
        self._decision_results[request_id] = decision
        event.set()
        return True

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:  # noqa: D401
        update_type = getattr(update, "session_update", None)
        if update_type == "agent_message_chunk":
            text = self._extract_text(update.content)
            if text:
                await self._append_text(text)
        elif update_type == "agent_thought_chunk":
            text = self._extract_text(update.content)
            if text:
                await self._append_thinking(text)
        elif update_type == "tool_call":
            await self._emit_tool_start(update)
        elif update_type == "tool_call_update":
            await self._emit_tool_update(update)
        else:
            return

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: ToolCallUpdate,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        request_id = str(uuid4())
        # Pre-register wait event to avoid race condition when emit_event responds immediately
        if request_id not in self._pending_decisions:
            self._pending_decisions[request_id] = asyncio.Event()
        options_payload = [opt.model_dump(by_alias=True, exclude_none=True) for opt in options]
        tool_call_payload = tool_call.model_dump(by_alias=True, exclude_none=True)
        tool_name = tool_call.title or (tool_call.kind.value if hasattr(tool_call.kind, "value") else tool_call.kind) or "tool"
        tool_input = tool_call.raw_input if tool_call.raw_input is not None else {}

        # Create DB messages and update status (using separate DB session)
        async with async_session_scope() as db:
            message_service = MessageService(db)
            task_service = TaskService(db)

            await message_service.create_permission_request(
                session_id=self.runtime_session_id,
                task_id=self.current_task_id or "",
                request_id=request_id,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_use_id=None,
                decision_type="permission",
                options=options_payload,
                raw_tool_call=tool_call_payload,
                tool_call_id=tool_call.tool_call_id,
            )

            if self.current_task_id:
                await task_service.set_awaiting_permission(
                    self.current_task_id,
                    {
                        "request_id": request_id,
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "tool_call_id": tool_call.tool_call_id,
                    },
                )

        if self.emit_event:
            self.emit_event(
                "tool-decision:request",
                {
                    "request_id": request_id,
                    "session_id": self.runtime_session_id,
                    "task_id": self.current_task_id,
                    "decision_type": "permission",
                    "options": options_payload,
                    "tool_call": tool_call_payload,
                    "timeout": 60,
                },
            )

        decision = await self._wait_for_decision(request_id, timeout=60)

        outcome = decision.get("outcome")
        option_id = decision.get("option_id")
        selected_option = self._find_option_by_id(options_payload, option_id) if option_id else None
        if selected_option and self._is_reject_option(selected_option):
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

        if outcome == "selected":
            if not option_id and options_payload:
                option_id = self._pick_default_allow_option(options_payload)
            return RequestPermissionResponse(
                outcome=AllowedOutcome(outcome="selected", option_id=option_id or "")
            )
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        abs_path = self._ensure_absolute_path(path)
        try:
            relative_path = self._resolve_relative_path(str(abs_path))
        except ValueError as exc:
            raise RequestError.invalid_params(
                {"path": str(abs_path), "reason": "path outside workspace"}
            ) from exc
        file_service = FileService(root_path=self.workspace_path)
        try:
            result = file_service.read_file(relative_path)
            content = result.get("content", "")
        except FileNotFoundException:
            # Gemini CLI may probe non-existent files before write; return empty content.
            content = ""

        lines = content.split("\n")
        start = max((line or 1) - 1, 0)
        if limit is not None:
            lines = lines[start : start + limit]
        else:
            lines = lines[start:]

        return ReadTextFileResponse(content="\n".join(lines))

    async def write_text_file(
        self,
        content: str,
        path: str,
        session_id: str,
        **kwargs: Any,
    ) -> WriteTextFileResponse | None:
        abs_path = self._ensure_absolute_path(path)
        try:
            relative_path = self._resolve_relative_path(str(abs_path))
        except ValueError as exc:
            raise RequestError.invalid_params(
                {"path": str(abs_path), "reason": "path outside workspace"}
            ) from exc
        file_service = FileService(root_path=self.workspace_path)
        file_service.write_file(relative_path, content)
        return WriteTextFileResponse()

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[EnvVariable] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> Any:
        env_map = {item.name: item.value for item in env or []}
        terminal_id = await self._terminal_manager.create_terminal(
            command=command,
            args=args,
            cwd=cwd,
            env=env_map or None,
            output_byte_limit=output_byte_limit,
        )
        from acp.schema import CreateTerminalResponse

        return CreateTerminalResponse(terminal_id=terminal_id)

    async def terminal_output(self, session_id: str, terminal_id: str, **kwargs: Any) -> TerminalOutputResponse:
        output, truncated, exit_code = await self._terminal_manager.get_output(terminal_id)
        exit_status = None
        if exit_code is not None:
            exit_status = TerminalExitStatus(exit_code=exit_code)
        return TerminalOutputResponse(output=output, truncated=truncated, exit_status=exit_status)

    async def wait_for_terminal_exit(
        self, session_id: str, terminal_id: str, **kwargs: Any
    ) -> WaitForTerminalExitResponse:
        exit_code = await self._terminal_manager.wait_for_exit(terminal_id)
        return WaitForTerminalExitResponse(exit_code=exit_code, signal=None)

    async def kill_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> Any:
        await self._terminal_manager.kill(terminal_id)
        from acp.schema import KillTerminalCommandResponse

        return KillTerminalCommandResponse()

    async def release_terminal(self, session_id: str, terminal_id: str, **kwargs: Any) -> Any:
        await self._terminal_manager.release(terminal_id)
        from acp.schema import ReleaseTerminalResponse

        return ReleaseTerminalResponse()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None

    async def _append_text(self, text: str) -> None:
        self._current_text += text
        if self.streaming_callbacks and self.streaming_callbacks.on_stream_chunk:
            if not self._stream_message_id:
                self._stream_message_id = str(uuid4())
                if self.streaming_callbacks.on_stream_start:
                    await self.streaming_callbacks.on_stream_start(self._stream_message_id)
            await self.streaming_callbacks.on_stream_chunk(self._stream_message_id, text)

    async def _append_thinking(self, text: str) -> None:
        self._current_thinking += text
        if self.streaming_callbacks and self.streaming_callbacks.on_thinking_chunk:
            if not self._thinking_message_id:
                self._thinking_message_id = str(uuid4())
                if self.streaming_callbacks.on_thinking_start:
                    await self.streaming_callbacks.on_thinking_start(self._thinking_message_id, metadata=None)
            await self.streaming_callbacks.on_thinking_chunk(self._thinking_message_id, text)

    async def finalize_streaming(self) -> None:
        if self.streaming_callbacks:
            if self._stream_message_id and self.streaming_callbacks.on_stream_end:
                await self.streaming_callbacks.on_stream_end(self._stream_message_id)
            if self._thinking_message_id and self.streaming_callbacks.on_thinking_end:
                await self.streaming_callbacks.on_thinking_end(self._thinking_message_id)
        self._stream_message_id = None
        self._thinking_message_id = None

    def get_current_content(self) -> tuple[str, str]:
        return self._current_text, self._current_thinking

    async def _wait_for_decision(self, request_id: str, timeout: int = 60) -> Dict[str, Any]:
        event = self._pending_decisions.get(request_id)
        if event is None:
            event = asyncio.Event()
            self._pending_decisions[request_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
            return self._decision_results.get(request_id, {"outcome": "cancelled"})
        except asyncio.TimeoutError:
            await self._handle_decision_timeout(request_id)
            return {"outcome": "cancelled"}
        finally:
            self._pending_decisions.pop(request_id, None)
            self._decision_results.pop(request_id, None)

    async def _handle_decision_timeout(self, request_id: str) -> None:
        """Persist timeout state and notify frontend when no decision is received."""
        task_id = self.current_task_id or ""

        try:
            if task_id:
                async with async_session_scope() as db:
                    service = ToolDecisionService(db)
                    await service.handle_timeout(request_id=request_id, task_id=task_id)
        except Exception:
            logger.exception(
                "Failed to persist ACP tool-decision timeout",
                extra={"session_id": self.runtime_session_id, "task_id": task_id, "request_id": request_id},
            )

        if self.emit_event:
            payload: Dict[str, Any] = {
                "request_id": request_id,
                "session_id": self.runtime_session_id,
            }
            if task_id:
                payload["task_id"] = task_id
            self.emit_event(
                "tool-decision:timeout",
                payload,
            )

    def _resolve_relative_path(self, path: str) -> str:
        abs_path = Path(path)
        if not abs_path.is_absolute():
            abs_path = self.workspace_path / abs_path
        abs_path = abs_path.resolve()
        if self.workspace_path not in abs_path.parents and abs_path != self.workspace_path:
            raise ValueError("Path outside workspace")
        return str(abs_path.relative_to(self.workspace_path))

    def _ensure_absolute_path(self, path: str) -> Path:
        abs_path = Path(path)
        if not abs_path.is_absolute():
            raise RequestError.invalid_params({"path": path, "reason": "path must be absolute"})
        return abs_path

    def _extract_text(self, content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, dict):
            if content.get("type") == "text":
                return content.get("text", "")
            return ""
        content_type = getattr(content, "type", None)
        if content_type == "text":
            return getattr(content, "text", "") or ""
        return ""

    def _extract_option_id(self, option: Dict[str, Any]) -> Optional[str]:
        return option.get("option_id") or option.get("optionId")

    def _find_option_by_id(self, options: list[Dict[str, Any]], option_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not option_id:
            return None

        for option in options:
            if self._extract_option_id(option) == option_id:
                return option
        return None

    def _is_reject_option(self, option: Dict[str, Any]) -> bool:
        kind = option.get("kind")
        return isinstance(kind, str) and kind.startswith("reject")

    def _pick_default_allow_option(self, options: list[Dict[str, Any]]) -> Optional[str]:
        for option in options:
            kind = option.get("kind")
            if isinstance(kind, str) and kind.startswith("allow"):
                return self._extract_option_id(option)

        if options:
            return self._extract_option_id(options[0])
        return None

    def _serialize_content_list(self, content_list: Any) -> list[dict[str, Any]] | None:
        """Serialize ACP ToolCallUpdate.content to JSON-compatible list."""
        if not content_list:
            return None
        result = []
        for item in content_list:
            if hasattr(item, "model_dump"):
                result.append(item.model_dump(by_alias=True, exclude_none=True))
            elif isinstance(item, dict):
                result.append(item)
        return result or None

    def _serialize_locations(self, locations: Any) -> list[dict[str, Any]] | None:
        """Serialize ACP ToolCallUpdate.locations to JSON-compatible list."""
        if not locations:
            return None
        result = []
        for loc in locations:
            if hasattr(loc, "model_dump"):
                result.append(loc.model_dump(by_alias=True, exclude_none=True))
            elif isinstance(loc, dict):
                result.append(loc)
        return result or None

    def _serialize_tool_call(self, tool_call: Any) -> dict[str, Any]:
        """Serialize raw ACP tool call/update payload with ACP field aliases."""
        if hasattr(tool_call, "model_dump"):
            return tool_call.model_dump(by_alias=True, exclude_none=True)
        if isinstance(tool_call, dict):
            return dict(tool_call)
        payload: dict[str, Any] = {}
        tool_call_id = getattr(tool_call, "tool_call_id", None)
        if tool_call_id:
            payload["toolCallId"] = tool_call_id
        title = getattr(tool_call, "title", None)
        if title:
            payload["title"] = title
        kind = self._extract_kind(tool_call)
        if kind:
            payload["kind"] = kind
        status = getattr(tool_call, "status", None)
        if status:
            payload["status"] = status
        content = self._serialize_content_list(getattr(tool_call, "content", None))
        if content:
            payload["content"] = content
        locations = self._serialize_locations(getattr(tool_call, "locations", None))
        if locations:
            payload["locations"] = locations
        session_update = getattr(tool_call, "session_update", None)
        if session_update:
            payload["sessionUpdate"] = session_update
        return payload

    def _extract_kind(self, tool_call: Any) -> str | None:
        """Extract kind string from a ToolCallUpdate."""
        kind = getattr(tool_call, "kind", None)
        if kind is None:
            return None
        if hasattr(kind, "value"):
            return kind.value
        return str(kind) if kind else None

    def _find_tool_execution(self, tool_call_id: str) -> dict[str, Any] | None:
        if not tool_call_id:
            return None
        for rec in reversed(self._tool_executions):
            if rec.get("tool_call_id") == tool_call_id:
                return rec
        return None

    def _new_tool_execution(self, tool_call_id: str, title: str) -> dict[str, Any]:
        return {
            "tool_call_id": tool_call_id,
            "title": title,
            "status": "running",
            "is_error": False,
            "kind": None,
            "raw_input": None,
            "raw_output": None,
            "content": None,
            "locations": None,
            "tool_call": None,
            "tool_updates": [],
            "tool_input": {},
            "tool_result": None,
        }

    def _build_tool_input_payload(
        self,
        *,
        tool_call_id: str,
        raw_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = dict(raw_payload or {})
        if tool_call_id and "toolCallId" not in payload:
            payload["toolCallId"] = tool_call_id
        return payload

    def _build_tool_result_payload(
        self,
        *,
        tool_call_id: str,
        status: str | None,
        content: list[dict[str, Any]] | None,
        raw_tool_update: dict[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = dict(raw_tool_update or {})
        payload.setdefault("toolCallId", tool_call_id)
        if status:
            payload.setdefault("status", status)
        if content:
            payload["content"] = content
        return payload

    def get_tool_executions(self) -> list[dict[str, Any]]:
        """Return accumulated tool execution records for persistence."""
        return list(self._tool_executions)

    async def _emit_tool_start(self, tool_call: Any) -> None:
        tool_call_id = getattr(tool_call, "tool_call_id", None)
        title = getattr(tool_call, "title", "tool")
        raw_input = getattr(tool_call, "raw_input", None)
        content = self._serialize_content_list(getattr(tool_call, "content", None))
        locations = self._serialize_locations(getattr(tool_call, "locations", None))
        kind = self._extract_kind(tool_call)
        raw_tool_call = self._serialize_tool_call(tool_call)
        tool_input_payload = self._build_tool_input_payload(
            tool_call_id=tool_call_id or "",
            raw_payload=raw_tool_call,
        )

        execution = self._find_tool_execution(tool_call_id or "")
        if execution is None:
            execution = self._new_tool_execution(tool_call_id or "", title)
            self._tool_executions.append(execution)

        execution["title"] = title
        execution["raw_input"] = raw_input
        execution["kind"] = kind
        execution["content"] = content
        execution["locations"] = locations
        execution["tool_call"] = raw_tool_call
        execution["tool_input"] = tool_input_payload
        execution["status"] = "running"
        execution["is_error"] = False

        if not self.emit_event:
            return
        event_payload: dict[str, Any] = {
            "tool_use_id": tool_call_id or "",
            "tool_name": title,
            "tool_input": tool_input_payload,
        }
        if kind:
            event_payload["kind"] = kind
        if content:
            event_payload["content"] = content
        if locations:
            event_payload["locations"] = locations
        self.emit_event("tool:start", event_payload)

    async def _emit_tool_update(self, tool_call: Any) -> None:
        status = getattr(tool_call, "status", None)
        tool_call_id = getattr(tool_call, "tool_call_id", None)
        title = getattr(tool_call, "title", "tool")
        raw_output = getattr(tool_call, "raw_output", None)
        raw_input = getattr(tool_call, "raw_input", None)
        content = self._serialize_content_list(getattr(tool_call, "content", None))
        locations = self._serialize_locations(getattr(tool_call, "locations", None))
        kind = self._extract_kind(tool_call)
        raw_tool_update = self._serialize_tool_call(tool_call)
        execution = self._find_tool_execution(tool_call_id or "")
        if execution is None:
            execution = self._new_tool_execution(tool_call_id or "", title)
            self._tool_executions.append(execution)

        tool_input_payload = self._build_tool_input_payload(
            tool_call_id=tool_call_id or "",
            raw_payload=(execution.get("tool_call") or raw_tool_update),
        )

        result_payload = self._build_tool_result_payload(
            tool_call_id=tool_call_id or "",
            status=status,
            content=content,
            raw_tool_update=raw_tool_update,
        )

        execution["title"] = title
        execution["raw_input"] = raw_input
        execution["raw_output"] = raw_output
        execution["tool_input"] = tool_input_payload
        execution["tool_result"] = result_payload
        execution["status"] = status or execution.get("status") or "completed"
        execution["is_error"] = status == "failed"
        if kind:
            execution["kind"] = kind
        if content:
            execution["content"] = content
        if locations:
            execution["locations"] = locations
        updates = execution.get("tool_updates")
        if isinstance(updates, list):
            updates.append(raw_tool_update)
        else:
            execution["tool_updates"] = [raw_tool_update]

        if not self.emit_event:
            return

        if status == "completed":
            event_payload: dict[str, Any] = {
                "tool_use_id": tool_call_id or "",
                "tool_name": title,
                "result": result_payload,
                "is_error": False,
            }
            if kind:
                event_payload["kind"] = kind
            if content:
                event_payload["content"] = content
            if locations:
                event_payload["locations"] = locations
            self.emit_event("tool:complete", event_payload)
        elif status == "failed":
            error_message: str | None = None
            error_code: str | None = None
            if isinstance(raw_output, dict):
                error_message = (
                    raw_output.get("error_message")
                    or raw_output.get("message")
                    or raw_output.get("error")
                )
                raw_code = raw_output.get("error_code") or raw_output.get("code")
                if raw_code is not None:
                    error_code = str(raw_code)
            if error_message is None:
                error_message = str(raw_output) if raw_output is not None else "Tool failed"
            payload: dict[str, Any] = {
                "tool_use_id": tool_call_id or "",
                "tool_name": title,
                "error_message": error_message,
            }
            if error_code:
                payload["error_code"] = error_code
            self.emit_event("tool:error", payload)
