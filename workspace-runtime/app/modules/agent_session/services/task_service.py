"""Task Service.

Provides business logic for tasks, including creation, state transitions, completion, etc.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from ..codex_usage import codex_usage_totals
from ..domain.entities import Task
from ..domain.enums import AgentSessionStatus, TaskStatus
from ..domain.value_objects import MessageRange, TokenUsage
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.task import TaskCreate, TaskQuery
from ..websocket.events import EventEmitter, get_event_emitter


class TaskServiceError(Exception):
    """Task Service error."""

    pass


class InvalidStateTransitionError(TaskServiceError):
    """Invalid state transition."""

    pass


class TaskService:
    """Task Service.

    Handles task-related business logic.
    """

    def __init__(
        self,
        db: AsyncSession,
        task_repo: Optional[TaskRepository] = None,
        session_repo: Optional[AgentSessionRepository] = None,
        emitter: Optional[EventEmitter] = None,
    ):
        """Initialize Service.

        Args:
            db: Database session
            task_repo: Task Repository (injectable)
            session_repo: Session Repository (injectable)
            emitter: Event Emitter (injectable)
        """
        self.db = db
        self.task_repo = task_repo or TaskRepository(db)
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.emitter = emitter or get_event_emitter()

    async def create_task(
        self,
        session_id: str,
        full_prompt: str,
        created_by: str = "anonymous",
    ) -> Task:
        """Create task.

        Args:
            session_id: Session ID
            full_prompt: Full prompt
            created_by: Creator

        Returns:
            Created task entity
        """
        task_id = str(uuid.uuid4())
        now = utcnow()

        # Create data blob
        data_blob: Dict[str, Any] = {
            "full_prompt": full_prompt,
            "tool_use_count": 0,
        }

        # Create record (data serialized to JSON string stored in TEXT field)
        model = await self.task_repo.create({
            "task_id": task_id,
            "session_id": session_id,
            "created_at": now,
            "created_by": created_by,
            "status": TaskStatus.CREATED.value,
            "data": json.dumps(data_blob, ensure_ascii=False),
        })

        # Add task to session
        await self.session_repo.add_task(session_id, task_id)

        task_entity = self.task_repo.to_entity(model)

        # Emit tasks:created event
        await self.emitter.emit_task_created(
            session_id=session_id,
            task_id=task_id,
            data=self._task_to_event_data(task_entity),
        )

        return task_entity

    async def get_task(
        self,
        task_id: str,
    ) -> Optional[Task]:
        """Get task.

        Args:
            task_id: Task ID

        Returns:
            Task entity or None
        """
        model = await self.task_repo.find_by_id(task_id)
        if not model:
            return None

        return self.task_repo.to_entity(model)

    async def find_tasks(
        self,
        query: TaskQuery,
    ) -> Tuple[List[Task], int]:
        """Query task list.

        Args:
            query: Query parameters

        Returns:
            (Task list, total)
        """
        # Build filter conditions
        filters: Dict[str, Any] = {}

        if query.session_id:
            filters["session_id"] = query.session_id
        if query.status:
            filters["status"] = query.status.value

        # Query
        models = await self.task_repo.find_all(
            filters=filters,
            limit=query.limit,
            offset=query.offset,
            order_by="created_at",
            order_desc=True,
        )

        # Count total
        total = await self.task_repo.count(filters)

        # Convert to entities
        tasks = [self.task_repo.to_entity(m) for m in models]

        return tasks, total

    async def start_task(
        self,
        task_id: str,
    ) -> Task:
        """Start executing task.

        Convert task status from CREATED to RUNNING.

        Args:
            task_id: Task ID

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found
            InvalidStateTransitionError: Invalid state transition
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        if not task.can_transition_to(TaskStatus.RUNNING):
            raise InvalidStateTransitionError(
                f"Cannot transition from {task.status.value} to running"
            )

        model = await self.task_repo.start_task(task_id)
        if not model:
            raise TaskServiceError(f"Failed to start task: {task_id}")

        # Update session status
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.RUNNING)

        # Emit task patched event to notify frontend task started
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "running"}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.RUNNING.value}
        )

        return self.task_repo.to_entity(model)

    async def complete_task(
        self,
        task_id: str,
        raw_sdk_response: Optional[Dict[str, Any]] = None,
        computed_context_window: Optional[int] = None,
        context_window_limit: Optional[int] = None,
    ) -> Task:
        """Complete task.

        Args:
            task_id: Task ID
            raw_sdk_response: Raw SDK response
            computed_context_window: Computed Context Window

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found or operation failed
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        model = await self.task_repo.complete_task(
            task_id,
            raw_sdk_response=raw_sdk_response,
            computed_context_window=computed_context_window,
        )
        if not model:
            raise TaskServiceError(f"Failed to complete task: {task_id}")

        # Update session status
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # Emit task patched event to notify frontend task completed
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "completed"}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        # Update context usage
        if computed_context_window is not None:
            await self.session_repo.update_context_usage(
                task.session_id,
                computed_context_window,
                context_window_limit,
            )

        return self.task_repo.to_entity(model)

    async def fail_task(
        self,
        task_id: str,
        error_message: Optional[str] = None,
    ) -> Task:
        """Mark task as failed.

        Args:
            task_id: Task ID
            error_message: Error message

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found or operation failed
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        model = await self.task_repo.fail_task(task_id, error_message)
        if not model:
            raise TaskServiceError(f"Failed to fail task: {task_id}")

        # Update session status
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # Emit task patched event to notify frontend task failed
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "failed", "error_message": error_message}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        return self.task_repo.to_entity(model)

    async def stop_task(
        self,
        task_id: str,
    ) -> Task:
        """Stop task.

        Args:
            task_id: Task ID

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found
            InvalidStateTransitionError: Invalid state transition
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # Determine target state based on current state
        model = None
        if task.status in [TaskStatus.RUNNING, TaskStatus.AWAITING_PERMISSION, TaskStatus.STOPPING]:
            # Set to stopped directly
            # This handles race conditions from multiple stop_task calls
            model = await self.task_repo.stop_task(task_id)

        # Update session status
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # Emit task patched event to notify frontend task stopped
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "stopped"}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        # Emit task stop event
        await self.emitter.emit_task_stopped(
            session_id=task.session_id,
            task_id=task.id,
        )

        # If model is None, re-fetch
        if not model:
            model = await self.task_repo.find_by_id(task_id)

        return self.task_repo.to_entity(model)

    async def set_awaiting_permission(
        self,
        task_id: str,
        permission_request: Dict[str, Any],
    ) -> Task:
        """Set task awaiting permission.

        This method is designed as idempotent to handle race conditions:
        - If status is running, transition to awaiting_permission normally
        - If status is already awaiting_permission, only update permission_request (possibly continuous permission requests)
        - Other statuses throw errors

        Args:
            task_id: Task ID
            permission_request: Permission request info

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found
            InvalidStateTransitionError: Invalid state transition
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # Idempotency handling: if already awaiting_permission status, only update permission_request
        # This can happen when:
        # 1. After permission approved, DB not yet updated, Claude SDK requests next permission
        # 2. Multiple tools need permissions in succession
        if task.status == TaskStatus.AWAITING_PERMISSION:
            logger.info(f"Task {task_id} is already awaiting_permission, updating permission_request only")
            model = await self.task_repo.set_awaiting_permission(task_id, permission_request)
            if not model:
                raise TaskServiceError(f"Failed to update permission request: {task_id}")
            return self.task_repo.to_entity(model)

        if not task.can_transition_to(TaskStatus.AWAITING_PERMISSION):
            raise InvalidStateTransitionError(
                f"Cannot transition from {task.status.value} to awaiting_permission"
            )

        model = await self.task_repo.set_awaiting_permission(task_id, permission_request)
        if not model:
            raise TaskServiceError(f"Failed to set awaiting permission: {task_id}")

        # Update session status
        await self.session_repo.update_status(
            task.session_id,
            AgentSessionStatus.AWAITING_PERMISSION,
        )

        # Emit task patched event to notify frontend task awaiting permission
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "awaiting_permission"}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.AWAITING_PERMISSION.value}
        )

        return self.task_repo.to_entity(model)

    async def resume_from_permission(
        self,
        task_id: str,
    ) -> Task:
        """Resume execution after permission approved.

        This method is designed as idempotent to handle race conditions and duplicate requests:
        - If status is awaiting_permission, resume normally
        - If status is already running, treat as success (possibly duplicate request or race condition)
        - Other statuses throw errors

        Args:
            task_id: Task ID

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found
            InvalidStateTransitionError: Invalid state transition
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # Idempotency handling: if already running status, return directly (possibly duplicate request or race condition)
        if task.status == TaskStatus.RUNNING:
            logger.info(f"Task {task_id} is already running, treating as idempotent success")
            return task

        if task.status != TaskStatus.AWAITING_PERMISSION:
            raise InvalidStateTransitionError(
                f"Cannot resume from {task.status.value}, expected awaiting_permission"
            )

        model = await self.task_repo.update(task_id, {"status": TaskStatus.RUNNING.value})
        if not model:
            raise TaskServiceError(f"Failed to resume task: {task_id}")

        # Update session status
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.RUNNING)

        # Emit task patched event to notify frontend task resumed
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "running"}
        )

        # Emit session patched event to notify frontend
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.RUNNING.value}
        )

        return self.task_repo.to_entity(model)

    async def update_message_range(
        self,
        task_id: str,
        start_index: int,
        end_index: int,
        start_timestamp: str,
        end_timestamp: Optional[str] = None,
    ) -> Task:
        """Update message range.

        Args:
            task_id: Task ID
            start_index: Start index
            end_index: End index
            start_timestamp: Start timestamp
            end_timestamp: End timestamp

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found or operation failed
        """
        message_range = MessageRange(
            start_index=start_index,
            end_index=end_index,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )

        model = await self.task_repo.update_message_range(task_id, message_range)
        if not model:
            raise TaskServiceError(f"Failed to update message range: {task_id}")

        return self.task_repo.to_entity(model)

    async def increment_tool_use_count(
        self,
        task_id: str,
        count: int = 1,
    ) -> Task:
        """Increment tool use count.

        Args:
            task_id: Task ID
            count: Increment amount

        Returns:
            Updated task

        Raises:
            TaskServiceError: Task not found or operation failed
        """
        model = await self.task_repo.increment_tool_use_count(task_id, count)
        if not model:
            raise TaskServiceError(f"Failed to increment tool use count: {task_id}")

        return self.task_repo.to_entity(model)

    async def get_active_task(
        self,
        session_id: str,
    ) -> Optional[Task]:
        """Get active task in session.

        Args:
            session_id: Session ID

        Returns:
            Active task or None
        """
        model = await self.task_repo.find_active_by_session(session_id)
        if not model:
            return None

        return self.task_repo.to_entity(model)

    @staticmethod
    def extract_token_usage(raw_sdk_response: Dict[str, Any]) -> Optional[TokenUsage]:
        """Extract token usage from SDK response.

        Args:
            raw_sdk_response: Raw SDK response

        Returns:
            Token usage or None
        """
        sdk_type = raw_sdk_response.get("type")
        response = raw_sdk_response.get("response", {})

        if sdk_type == "claude":
            usage = response.get("usage", {}) or raw_sdk_response.get("usage", {})
            usage_data = raw_sdk_response.get("usageData", {}) or {}
            return TokenUsage(
                input_tokens=usage_data.get("inputTokens", usage.get("input_tokens", 0)),
                output_tokens=usage_data.get("outputTokens", usage.get("output_tokens", 0)),
                total_tokens=usage_data.get(
                    "totalTokens",
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                ),
                cache_creation_input_tokens=usage_data.get(
                    "cacheCreationTokens",
                    usage.get("cache_creation_input_tokens"),
                ),
                cache_read_input_tokens=usage_data.get(
                    "cacheReadTokens",
                    usage.get("cache_read_input_tokens"),
                ),
            )
        elif sdk_type == "codex":
            usage = codex_usage_totals(raw_sdk_response)
            return TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cache_read_input_tokens=usage.get("cached_input_tokens"),
            )
        elif sdk_type == "gemini":
            usage = response.get("usageMetadata", {})
            return TokenUsage(
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
            )
        elif sdk_type == "opencode":
            usage = response.get("usage", {})
            return TokenUsage(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )

        return None

    async def get_active_tasks(self, session_id: str) -> List[Task]:
        """Get all active tasks in session.

        Active tasks include tasks with CREATED, RUNNING, and AWAITING_PERMISSION statuses.
        CREATED status means task created but not yet started, should also be considered active.

        Args:
            session_id: Session ID

        Returns:
            Active tasks list
        """
        models = await self.task_repo.find_by_session(
            session_id=session_id,
            status=[TaskStatus.CREATED, TaskStatus.RUNNING, TaskStatus.AWAITING_PERMISSION],
        )
        return [self.task_repo.to_entity(m) for m in models]

    @staticmethod
    def _task_to_event_data(task: Task) -> Dict[str, Any]:
        """Convert Task entity to event data.

        Contains complete task info for WebSocket event broadcast.

        Args:
            task: Task entity

        Returns:
            Event data dictionary
        """
        data = {
            "task_id": task.id,
            "session_id": task.session_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "created_by": task.created_by,
            "status": task.status,
        }

        # Add info from Task entity
        if task.full_prompt:
            data["description"] = task.full_prompt[:100]  # First 100 chars as summary
        if task.tool_use_count > 0:
            data["tool_use_count"] = task.tool_use_count

        return data


__all__ = [
    "InvalidStateTransitionError",
    "TaskService",
    "TaskServiceError",
]
