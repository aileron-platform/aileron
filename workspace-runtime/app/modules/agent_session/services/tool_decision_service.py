"""Tool Decision Service.

Provides business logic for tool decisions (permission/user_input).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import (
    PermissionStatus,
    AgentSessionStatus,
    TaskStatus,
    ToolDecisionOutcome,
    ToolDecisionType,
)
from ..repositories.message_repository import MessageRepository
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.agent_session import ToolDecisionRequest


class ToolDecisionServiceError(Exception):
    """Tool Decision Service error."""

    pass


class ToolDecisionTimeoutError(ToolDecisionServiceError):
    """Tool Decision request timeout."""

    pass


class ToolDecisionDeniedError(ToolDecisionServiceError):
    """Tool Decision denied."""

    pass


class ToolDecisionService:
    """Tool Decision Service.

    Handles tool execution decision flow.
    """

    def __init__(
        self,
        db: AsyncSession,
        session_repo: Optional[AgentSessionRepository] = None,
        task_repo: Optional[TaskRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        event_emitter: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        """Initialize Service.

        Args:
            db: Database session
            session_repo: Session Repository ((injectable))
            task_repo: Task Repository ((injectable))
            message_repo: Message Repository ((injectable))
            event_emitter: Event emitter (for WebSocket)
        """
        self.db = db
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.message_repo = message_repo or MessageRepository(db)
        self.event_emitter = event_emitter

        # Pending decisions (request_id -> asyncio.Event)
        # Note: These fields are currently instance-level, and ToolDecisionService creates a new instance per request.
        # Real in-memory waiting mechanism is managed by global_tool_decision_manager.
        # These fields are kept for backward compatibility, but will not take effect.
        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, ToolDecisionRequest] = {}

        # Track permission requests per session (session_id -> set of request_ids)
        # Used to batch-cancel other pending requests in the same session when permission is denied
        self._session_requests: Dict[str, set] = {}

    async def create_tool_decision_request(
        self,
        session_id: str,
        task_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[list[Dict[str, Any]]] = None,
        tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> str:
        """Create Tool Decision request.

        Args:
            session_id: Session ID
            task_id: Task ID
            tool_name: Tool name
            tool_input: Tool input parameters
            tool_use_id: Tool Use ID
            timeout_seconds: Timeout in seconds

        Returns:
            request_id
        """
        request_id = str(uuid.uuid4())
        now = utcnow()

        # Create decision request data
        permission_request = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "requested_at": now.isoformat(),
        }
        if tool_use_id:
            permission_request["tool_use_id"] = tool_use_id
        if tool_call_id:
            permission_request["tool_call_id"] = tool_call_id
        if options is not None:
            permission_request["options"] = options
        if tool_call is not None:
            permission_request["raw_tool_call"] = tool_call

        # Update task status
        await self.task_repo.set_awaiting_permission(task_id, permission_request)

        # Update session status
        await self.session_repo.update_status(session_id, AgentSessionStatus.AWAITING_PERMISSION)

        # Create decision request message
        await self._create_permission_message(
            session_id=session_id,
            task_id=task_id,
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
            decision_type=decision_type,
            options=options or [],
            raw_tool_call=tool_call,
            tool_call_id=tool_call_id,
        )

        # Send WebSocket event
        if self.event_emitter:
            tool_call_payload = tool_call or {
                "toolCallId": tool_use_id or request_id,
                "title": tool_name,
                "kind": "execute",
                "rawInput": tool_input,
            }
            self.event_emitter("tool-decision:request", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
                "decision_type": decision_type,
                "options": options or [],
                "tool_call": tool_call_payload,
                "timeout": timeout_seconds,
            })

        # Track this session's permission request
        if session_id not in self._session_requests:
            self._session_requests[session_id] = set()
        self._session_requests[session_id].add(request_id)

        return request_id

    async def wait_for_decision(
        self,
        request_id: str,
        timeout_seconds: int = 60,
    ) -> ToolDecisionRequest:
        """Wait for Tool Decision.

        Args:
            request_id: Request ID
            timeout_seconds: Timeout in seconds

        Returns:
            Permission decision

        Raises:
            ToolDecisionTimeoutError: Timeout
        """
        # Create wait event
        event = asyncio.Event()
        self._pending_decisions[request_id] = event

        try:
            # Wait for decision or timeout
            await asyncio.wait_for(event.wait(), timeout=timeout_seconds)

            # Get decision result
            decision = self._decision_results.get(request_id)
            if not decision:
                raise ToolDecisionServiceError(f"Decision not found for request: {request_id}")

            return decision

        except asyncio.TimeoutError:
            raise ToolDecisionTimeoutError(f"Tool decision request timed out: {request_id}")

        finally:
            # Clean up
            self._pending_decisions.pop(request_id, None)
            self._decision_results.pop(request_id, None)

    async def resolve_decision(
        self,
        decision: ToolDecisionRequest,
    ) -> bool:
        """Handle Tool Decision.

        Args:
            decision: Decision request

        Returns:
            Whether processing was successful
        """
        request_id = decision.request_id

        # Get task
        task_model = await self.task_repo.find_by_id(decision.task_id)
        if not task_model:
            raise ToolDecisionServiceError(f"Task not found: {decision.task_id}")

        session_id = task_model.session_id

        # Determine approval based on option kind/outcome
        approved, derived_scope = await self._resolve_decision_outcome(
            session_id=session_id,
            request_id=request_id,
            decision=decision,
        )

        # Update decision request message
        status = PermissionStatus.APPROVED.value if approved else PermissionStatus.DENIED.value
        await self._update_permission_message(
            session_id=session_id,
            request_id=request_id,
            status=status,
            scope=(decision.scope.value if decision.scope else derived_scope),
            approved_by=decision.decided_by,
            decision_type=decision.decision_type.value,
            outcome=decision.outcome.value,
            option_id=decision.option_id,
            reason=decision.reason,
            decision_content=decision.content,
        )

        # Update task status（user_input does not force status update, controlled by hooks）
        if decision.decision_type == ToolDecisionType.PERMISSION:
            if approved:
                # Approved - resume execution
                await self.task_repo.update(decision.task_id, {"status": TaskStatus.RUNNING.value})
                await self.session_repo.update_status(session_id, AgentSessionStatus.RUNNING)
            else:
                # Denied - mark as failed
                await self.task_repo.fail_task(
                    decision.task_id,
                    error_message=decision.reason or "Permission denied",
                )
                await self.session_repo.update_status(session_id, AgentSessionStatus.IDLE)
                # Cancel other pending permission requests in the same session
                await self.cancel_pending_requests(session_id)

        # Store decision result and notify waiters
        self._decision_results[request_id] = decision
        event = self._pending_decisions.get(request_id)
        if event:
            event.set()

        # Send WebSocket event
        if self.event_emitter:
            event_name = "tool-decision:approved" if approved else "tool-decision:denied"
            self.event_emitter(event_name, {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": decision.task_id,
                "decision_type": decision.decision_type.value,
                "outcome": decision.outcome.value,
                "option_id": decision.option_id,
                "scope": (decision.scope.value if decision.scope else derived_scope),
                "decided_by": decision.decided_by,
                "reason": decision.reason,
            })

        return True

    async def handle_timeout(
        self,
        request_id: str,
        task_id: str,
    ) -> None:
        """Handle Tool Decision request timeout.

        Args:
            request_id: Request ID
            task_id: Task ID
        """
        task_model = await self.task_repo.find_by_id(task_id)
        if not task_model:
            return

        session_id = task_model.session_id

        # Update permission request message
        await self._update_permission_message(
            session_id=session_id,
            request_id=request_id,
            status=PermissionStatus.DENIED.value,
            approved_by="system",
        )

        # Mark task as failed
        await self.task_repo.fail_task(task_id, error_message="Tool decision request timed out")

        # Update session status
        await self.session_repo.update_status(session_id, AgentSessionStatus.IDLE)

        # Send WebSocket event
        if self.event_emitter:
            self.event_emitter("tool-decision:timeout", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
            })

    async def cancel_request(
        self,
        request_id: str,
    ) -> None:
        """Cancel Tool Decision request.

        Args:
            request_id: Request ID
        """
        # Notify waiters
        event = self._pending_decisions.get(request_id)
        if event:
            # Create a cancelled decision
            self._decision_results[request_id] = ToolDecisionRequest(
                request_id=request_id,
                task_id="",
                decision_type=ToolDecisionType.PERMISSION,
                outcome=ToolDecisionOutcome.CANCELLED,
                decided_by="system",
                reason="Request cancelled",
            )
            event.set()

    async def cancel_pending_requests(
        self,
        session_id: str,
    ) -> int:
        """Cancel all pending permission requests for a given session.

        Called when permission is denied, automatically cancels all other pending requests in the session.
        References agor's cancelPendingRequests implementation.

        Args:
            session_id: Session ID

        Returns:
            Number of cancelled requests
        """
        request_ids = self._session_requests.get(session_id, set()).copy()
        cancelled_count = 0

        for request_id in request_ids:
            event = self._pending_decisions.get(request_id)
            if event:
                self._decision_results[request_id] = ToolDecisionRequest(
                    request_id=request_id,
                    task_id="",
                    decision_type=ToolDecisionType.PERMISSION,
                    outcome=ToolDecisionOutcome.CANCELLED,
                    decided_by="system",
                    reason="Cancelled due to previous permission denial",
                )
                event.set()
                cancelled_count += 1

        # Clean up session request tracking
        self._session_requests.pop(session_id, None)

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} pending request(s) for session {session_id[:8]}")

        return cancelled_count

    async def _resolve_decision_outcome(
        self,
        session_id: str,
        request_id: str,
        decision: ToolDecisionRequest,
    ) -> tuple[bool, Optional[str]]:
        """Resolve decision outcome and default scope."""
        approved = decision.outcome == ToolDecisionOutcome.SELECTED
        derived_scope: Optional[str] = None

        if decision.outcome == ToolDecisionOutcome.CANCELLED:
            return False, derived_scope

        if decision.option_id:
            content = await self._get_request_content(session_id, request_id)
            options = content.get("options") or []
            option = self._find_option(options, decision.option_id)
            if option:
                kind = option.get("kind")
                option_scope = option.get("scope")
                if isinstance(option_scope, str):
                    derived_scope = option_scope
                if isinstance(kind, str):
                    if kind.startswith("reject"):
                        approved = False
                    elif kind.startswith("allow"):
                        approved = True
                    if derived_scope is None:
                        derived_scope = self._scope_from_option_kind(kind)

        return approved, derived_scope

    async def _get_request_content(self, session_id: str, request_id: str) -> Dict[str, Any]:
        """Get decision request content（content blob）."""
        model = await self.message_repo.find_permission_request(session_id, request_id)
        if not model or not model.data:
            return {}
        try:
            data = json.loads(model.data)
        except (TypeError, json.JSONDecodeError):
            return {}
        if isinstance(data, dict):
            content = data.get("content")
            if isinstance(content, dict):
                return content
        return {}

    def _find_option(self, options: list[Any], option_id: str) -> Optional[Dict[str, Any]]:
        """Find corresponding option from options."""
        for option in options:
            if not isinstance(option, dict):
                continue
            candidate = option.get("option_id") or option.get("optionId")
            if candidate == option_id:
                return option
        return None

    def _scope_from_option_kind(self, kind: str) -> Optional[str]:
        """Derive scope from option kind."""
        if kind == "allow_once":
            return "once"
        if kind == "allow_always":
            return "session"
        if kind == "reject_always":
            return "session"
        return None

    async def _create_permission_message(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[list[Dict[str, Any]]] = None,
        raw_tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> None:
        """Create permission request message.

        Internal method to create the permission request message.
        """
        from .message_service import MessageService

        message_service = MessageService(
            self.db,
            message_repo=self.message_repo,
            session_repo=self.session_repo,
        )

        await message_service.create_permission_request(
            session_id=session_id,
            task_id=task_id,
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
            decision_type=decision_type,
            options=options,
            raw_tool_call=raw_tool_call,
            tool_call_id=tool_call_id,
        )

    async def _update_permission_message(
        self,
        session_id: str,
        request_id: str,
        status: str,
        scope: Optional[str] = None,
        approved_by: Optional[str] = None,
        decision_type: Optional[str] = None,
        outcome: Optional[str] = None,
        option_id: Optional[str] = None,
        reason: Optional[str] = None,
        decision_content: Optional[str] = None,
    ) -> None:
        """Update decision request message.

        Internal method to update the permission request message status.
        """
        from .message_service import MessageService

        message_service = MessageService(
            self.db,
            message_repo=self.message_repo,
            session_repo=self.session_repo,
        )

        await message_service.update_permission_request(
            session_id=session_id,
            request_id=request_id,
            status=status,
            scope=scope,
            approved_by=approved_by,
            decision_type=decision_type,
            outcome=outcome,
            option_id=option_id,
            reason=reason,
            decision_content=decision_content,
        )


__all__ = [
    "ToolDecisionDeniedError",
    "ToolDecisionService",
    "ToolDecisionServiceError",
    "ToolDecisionTimeoutError",
]
