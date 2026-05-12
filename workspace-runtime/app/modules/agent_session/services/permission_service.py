"""Permission Service.

Provides business logic for permission approval.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Callable, Dict, Optional

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.enums import PermissionStatus, AgentSessionStatus, TaskStatus
from ..repositories.message_repository import MessageRepository
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.agent_session import PermissionDecisionRequest


class PermissionServiceError(Exception):
    """Permission Service error."""

    pass


class PermissionTimeoutError(PermissionServiceError):
    """Permission request timeout."""

    pass


class PermissionDeniedError(PermissionServiceError):
    """Permission denied."""

    pass


class PermissionService:
    """Permission Service.

    Handles permission approval flow for tool execution.
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
        self._pending_decisions: Dict[str, asyncio.Event] = {}
        self._decision_results: Dict[str, PermissionDecisionRequest] = {}

        # Track permission requests per session (session_id -> set of request_ids)
        # Used to batch-cancel other pending requests in the same session when permission is denied
        self._session_requests: Dict[str, set] = {}

    async def create_permission_request(
        self,
        session_id: str,
        task_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> str:
        """Create permission request.

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

        # Create permission request data
        permission_request = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "requested_at": now.isoformat(),
        }
        if tool_use_id:
            permission_request["tool_use_id"] = tool_use_id

        # Update task status
        await self.task_repo.set_awaiting_permission(task_id, permission_request)

        # Update session status
        await self.session_repo.update_status(session_id, AgentSessionStatus.AWAITING_PERMISSION)

        # Create permission request message
        await self._create_permission_message(
            session_id=session_id,
            task_id=task_id,
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
        )

        # Send WebSocket event
        if self.event_emitter:
            self.event_emitter("permission:request", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
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
    ) -> PermissionDecisionRequest:
        """Wait for permission decision.

        Args:
            request_id: Request ID
            timeout_seconds: Timeout in seconds

        Returns:
            Permission decision

        Raises:
            PermissionTimeoutError: Timeout
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
                raise PermissionServiceError(f"Decision not found for request: {request_id}")

            return decision

        except asyncio.TimeoutError:
            raise PermissionTimeoutError(f"Permission request timed out: {request_id}")

        finally:
            # Clean up
            self._pending_decisions.pop(request_id, None)
            self._decision_results.pop(request_id, None)

    async def resolve_decision(
        self,
        decision: PermissionDecisionRequest,
    ) -> bool:
        """Handle permission decision.

        Args:
            decision: Decision request

        Returns:
            Whether processing was successful
        """
        request_id = decision.request_id

        # Get task
        task_model = await self.task_repo.find_by_id(decision.task_id)
        if not task_model:
            raise PermissionServiceError(f"Task not found: {decision.task_id}")

        session_id = task_model.session_id

        # Update permission request message
        status = PermissionStatus.APPROVED.value if decision.allow else PermissionStatus.DENIED.value
        await self._update_permission_message(
            session_id=session_id,
            request_id=request_id,
            status=status,
            scope=decision.scope.value if decision.remember else None,
            approved_by=decision.decided_by,
        )

        # Update task status
        if decision.allow:
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
            event_name = "permission:approved" if decision.allow else "permission:denied"
            self.event_emitter(event_name, {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": decision.task_id,
                "allow": decision.allow,
                "scope": decision.scope.value if decision.remember else None,
                "decided_by": decision.decided_by,
                "reason": decision.reason,
            })

        return True

    async def handle_timeout(
        self,
        request_id: str,
        task_id: str,
    ) -> None:
        """Handle permission request timeout.

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
        await self.task_repo.fail_task(task_id, error_message="Permission request timed out")

        # Update session status
        await self.session_repo.update_status(session_id, AgentSessionStatus.IDLE)

        # Send WebSocket event
        if self.event_emitter:
            self.event_emitter("permission:timeout", {
                "request_id": request_id,
                "session_id": session_id,
                "task_id": task_id,
            })

    async def cancel_request(
        self,
        request_id: str,
    ) -> None:
        """Cancel permission request.

        Args:
            request_id: Request ID
        """
        # Notify waiters
        event = self._pending_decisions.get(request_id)
        if event:
            # Create a denied decision
            self._decision_results[request_id] = PermissionDecisionRequest(
                request_id=request_id,
                task_id="",
                allow=False,
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
        Cancels all other pending requests in the session.

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
                self._decision_results[request_id] = PermissionDecisionRequest(
                    request_id=request_id,
                    task_id="",
                    allow=False,
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

    async def _create_permission_message(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
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
        )

    async def _update_permission_message(
        self,
        session_id: str,
        request_id: str,
        status: str,
        scope: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> None:
        """Update permission request message.

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
        )


__all__ = [
    "PermissionDeniedError",
    "PermissionService",
    "PermissionServiceError",
    "PermissionTimeoutError",
]
