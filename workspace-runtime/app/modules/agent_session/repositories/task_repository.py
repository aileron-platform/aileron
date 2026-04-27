"""Task Repository.

Provides data access operations for tasks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import ensure_utc, utcnow

from ..domain.entities import Task
from ..domain.enums import TaskStatus
from ..domain.value_objects import MessageRange
from .base import BaseRepository
from .json_utils import safe_json_loads
from .sqlalchemy_models import AgentTaskModel

logger = logging.getLogger(__name__)


class TaskRepository(BaseRepository[AgentTaskModel]):
    """Task Repository.

    Provides CRUD operations and state management methods for tasks.
    """

    def __init__(self, db: AsyncSession):
        """Initialize Repository."""
        super().__init__(db, AgentTaskModel, "task_id")

    def _get_id_column(self) -> Any:
        """Get primary key column."""
        return AgentTaskModel.task_id

    async def find_by_session(
        self,
        session_id: str,
        status: Optional[Union[TaskStatus, List[TaskStatus]]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTaskModel]:
        """Query tasks by session ID.

        Args:
            session_id: Session ID
            status: Task status filter (single or multiple)
            limit: Max results
            offset: Offset

        Returns:
            Task list
        """
        conditions = [AgentTaskModel.session_id == session_id]

        if status:
            if isinstance(status, list):
                # Multiple statuses
                status_values = [s.value for s in status]
                conditions.append(AgentTaskModel.status.in_(status_values))
            else:
                # Single status
                conditions.append(AgentTaskModel.status == status.value)

        stmt = (
            select(AgentTaskModel)
            .where(and_(*conditions))
            .order_by(AgentTaskModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(
        self,
        status: TaskStatus,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTaskModel]:
        """Query tasks by status.

        Args:
            status: Task status
            limit: Max results
            offset: Offset

        Returns:
            Task list
        """
        stmt = (
            select(AgentTaskModel)
            .where(AgentTaskModel.status == status.value)
            .order_by(AgentTaskModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_active_by_session(
        self,
        session_id: str,
    ) -> Optional[AgentTaskModel]:
        """Query active task in session.

        Args:
            session_id: Session ID

        Returns:
            Active task or None
        """
        active_statuses = [
            TaskStatus.CREATED.value,
            TaskStatus.RUNNING.value,
            TaskStatus.STOPPING.value,
            TaskStatus.AWAITING_PERMISSION.value,
        ]

        stmt = select(AgentTaskModel).where(
            and_(
                AgentTaskModel.session_id == session_id,
                AgentTaskModel.status.in_(active_statuses),
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def start_task(
        self,
        task_id: str,
        started_at: Optional[datetime] = None,
    ) -> Optional[AgentTaskModel]:
        """Start executing task.

        Args:
            task_id: Task ID
            started_at: Start time

        Returns:
            Updated task or None
        """
        return await self.update(
            task_id,
            {
                "status": TaskStatus.RUNNING.value,
                "started_at": started_at or utcnow(),
            },
        )

    async def complete_task(
        self,
        task_id: str,
        raw_sdk_response: Optional[Dict[str, Any]] = None,
        computed_context_window: Optional[int] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[AgentTaskModel]:
        """Complete task.

        Args:
            task_id: Task ID
            raw_sdk_response: Raw SDK response
            computed_context_window: Computed Context Window
            completed_at: Completion time

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = ensure_utc(completed_at) or datetime.now(timezone.utc)
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # Calculate execution time
        if task.started_at:
            started_at = ensure_utc(task.started_at)
            if started_at:
                duration_ms = int((now - started_at).total_seconds() * 1000)
                data["duration_ms"] = duration_ms

        # Store SDK response
        if raw_sdk_response:
            data["raw_sdk_response"] = raw_sdk_response

        if computed_context_window is not None:
            data["computed_context_window"] = computed_context_window

        return await self.update(
            task_id,
            {
                "status": TaskStatus.COMPLETED.value,
                "completed_at": now,
                "data": json.dumps(data, ensure_ascii=False),
            },
        )

    async def fail_task(
        self,
        task_id: str,
        error_message: Optional[str] = None,
        completed_at: Optional[datetime] = None,
    ) -> Optional[AgentTaskModel]:
        """Mark task as failed.

        Args:
            task_id: Task ID
            error_message: Error message
            completed_at: Completion time

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = ensure_utc(completed_at) or datetime.now(timezone.utc)
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # Calculate execution time
        if task.started_at:
            started_at = ensure_utc(task.started_at)
            if started_at:
                duration_ms = int((now - started_at).total_seconds() * 1000)
                data["duration_ms"] = duration_ms

        if error_message:
            data["error_message"] = error_message

        return await self.update(
            task_id,
            {
                "status": TaskStatus.FAILED.value,
                "completed_at": now,
                "data": json.dumps(data, ensure_ascii=False),
            },
        )

    async def stop_task(
        self,
        task_id: str,
        completed_at: Optional[datetime] = None,
    ) -> Optional[AgentTaskModel]:
        """Stop task.

        Args:
            task_id: Task ID
            completed_at: Completion time

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = completed_at or datetime.now(timezone.utc)
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # Calculate execution time
        if task.started_at:
            duration_ms = int((now - task.started_at).total_seconds() * 1000)
            data["duration_ms"] = duration_ms

        return await self.update(
            task_id,
            {
                "status": TaskStatus.STOPPED.value,
                "completed_at": now,
                "data": json.dumps(data, ensure_ascii=False),
            },
        )

    async def set_awaiting_permission(
        self,
        task_id: str,
        permission_request: Dict[str, Any],
    ) -> Optional[AgentTaskModel]:
        """Set task awaiting permission.

        Args:
            task_id: Task ID
            permission_request: Permission request info

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")
        data["permission_request"] = permission_request

        return await self.update(
            task_id,
            {
                "status": TaskStatus.AWAITING_PERMISSION.value,
                "data": json.dumps(data, ensure_ascii=False),
            },
        )

    async def update_message_range(
        self,
        task_id: str,
        message_range: MessageRange,
    ) -> Optional[AgentTaskModel]:
        """Update message range.

        Args:
            task_id: Task ID
            message_range: Message range

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")
        data["message_range"] = message_range.to_dict()

        return await self.update(task_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def increment_tool_use_count(
        self,
        task_id: str,
        count: int = 1,
    ) -> Optional[AgentTaskModel]:
        """Increment tool use count.

        Args:
            task_id: Task ID
            count: Increment amount

        Returns:
            Updated task or None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(task.data, task_id, "task")
        tool_use_count = data.get("tool_use_count", 0) + count
        data["tool_use_count"] = tool_use_count

        return await self.update(task_id, {"data": json.dumps(data, ensure_ascii=False)})

    def to_entity(self, model: AgentTaskModel) -> Task:
        """Convert ORM model to domain entity.

        Args:
            model: ORM model

        Returns:
            Domain entity
        """
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(model.data, model.task_id, "task") if model.data else None

        return Task.from_db_row({
            "task_id": model.task_id,
            "session_id": model.session_id,
            "created_at": model.created_at,
            "created_by": model.created_by,
            "started_at": model.started_at,
            "completed_at": model.completed_at,
            "status": model.status,
            "data": data,
        })


__all__ = ["TaskRepository"]
