"""Agent Session Repository.

Provides data access operations for Agent sessions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import utcnow

from ..domain.entities import AgentSession
from ..domain.enums import AgenticTool, AgentSessionStatus
from .json_utils import safe_json_loads

logger = logging.getLogger(__name__)
from .base import BaseRepository
from .sqlalchemy_models import AgentSessionModel


class AgentSessionRepository(BaseRepository[AgentSessionModel]):
    """Agent Session Repository.

    Provides CRUD operations and specific query methods for Agent sessions.
    """

    def __init__(self, db: AsyncSession):
        """Initialize Repository."""
        super().__init__(db, AgentSessionModel, "session_id")

    def _get_id_column(self) -> Any:
        """Get primary key column."""
        return AgentSessionModel.session_id

    async def find_by_workspace(
        self,
        workspace_id: str,
        status: Optional[AgentSessionStatus] = None,
        agentic_tool: Optional[AgenticTool] = None,
        archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentSessionModel]:
        """Query sessions by workspace.

        Args:
            workspace_id: Workspace ID
            status: Session status filter
            agentic_tool: Tool type filter
            archived: Include archived
            limit: Max results
            offset: Offset

        Returns:
            Session list
        """
        conditions = [
            AgentSessionModel.workspace_id == workspace_id,
            AgentSessionModel.archived == archived,
        ]

        if status:
            conditions.append(AgentSessionModel.status == status.value)

        if agentic_tool:
            conditions.append(AgentSessionModel.agentic_tool == agentic_tool.value)

        stmt = (
            select(AgentSessionModel)
            .where(and_(*conditions))
            .order_by(AgentSessionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_status(
        self,
        status: AgentSessionStatus,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentSessionModel]:
        """Query sessions by status.

        Args:
            status: Session status
            limit: Max results
            offset: Offset

        Returns:
            Session list
        """
        stmt = (
            select(AgentSessionModel)
            .where(AgentSessionModel.status == status.value)
            .order_by(AgentSessionModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_running_by_workspace(
        self,
        workspace_id: str,
    ) -> Optional[AgentSessionModel]:
        """Query currently executing session in workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            Currently executing session or None
        """
        stmt = select(AgentSessionModel).where(
            and_(
                AgentSessionModel.workspace_id == workspace_id,
                AgentSessionModel.status.in_([
                    AgentSessionStatus.RUNNING.value,
                    AgentSessionStatus.AWAITING_PERMISSION.value,
                ]),
            )
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        session_id: str,
        status: AgentSessionStatus,
        updated_at: Optional[datetime] = None,
    ) -> Optional[AgentSessionModel]:
        """Update session status.

        Args:
            session_id: Session ID
            status: New status
            updated_at: Update time

        Returns:
            Updated session or None
        """
        data = {"status": status.value}
        if updated_at:
            data["updated_at"] = updated_at

        return await self.update(session_id, data)

    async def add_task(
        self,
        session_id: str,
        task_id: str,
    ) -> Optional[AgentSessionModel]:
        """Add task to session.

        Args:
            session_id: Session ID
            task_id: Task ID

        Returns:
            Updated session or None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        tasks = data.get("tasks", [])

        # Add task_id
        if task_id not in tasks:
            tasks.append(task_id)
            data["tasks"] = tasks

            # Serialize and update (dict -> JSON string)
            return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

        return session

    async def increment_message_count(
        self,
        session_id: str,
        count: int = 1,
    ) -> Optional[AgentSessionModel]:
        """Increment message count.

        Args:
            session_id: Session ID
            count: Increment amount

        Returns:
            Updated session or None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        message_count = data.get("message_count", 0) + count
        data["message_count"] = message_count

        # Serialize and update (dict -> JSON string)
        return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def set_sdk_session_id(self, session_id: str, sdk_session_id: str) -> None:
        """Persist the SDK session id inside the session data JSON."""
        session = await self.find_by_id(session_id)
        if not session:
            logger.warning("Session not found when saving sdk_session_id: %s", session_id[:8])
            return

        data = {}
        if session.data:
            try:
                data = json.loads(session.data)
            except (TypeError, json.JSONDecodeError):
                data = {}
        data["sdk_session_id"] = sdk_session_id

        await self.update(
            session_id,
            {
                "data": json.dumps(data, ensure_ascii=False),
                "updated_at": utcnow(),
            },
        )

    async def update_context_usage(
        self,
        session_id: str,
        usage: int,
        limit: Optional[int] = None,
    ) -> Optional[AgentSessionModel]:
        """Update Context Window usage.

        Args:
            session_id: Session ID
            usage: Current usage
            limit: Context limit

        Returns:
            Updated session or None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        data["current_context_usage"] = usage
        data["last_context_update_at"] = utcnow().isoformat()

        if limit is not None:
            data["context_window_limit"] = limit

        # Serialize and update (dict -> JSON string)
        return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def archive(
        self,
        session_id: str,
        reason: str = "manual",
    ) -> Optional[AgentSessionModel]:
        """Archive session.

        Args:
            session_id: Session ID
            reason: Archive reason

        Returns:
            Updated session or None
        """
        return await self.update(
            session_id,
            {
                "archived": True,
                "archived_reason": reason,
                "status": AgentSessionStatus.COMPLETED.value,
            },
        )

    def to_entity(self, model: AgentSessionModel) -> AgentSession:
        """Convert ORM model to domain entity.

        Args:
            model: ORM model

        Returns:
            Domain entity
        """
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(model.data, model.session_id, "session") if model.data else None

        return AgentSession.from_db_row({
            "session_id": model.session_id,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "created_by": model.created_by,
            "status": model.status,
            "agentic_tool": model.agentic_tool,
            "workspace_id": model.workspace_id,
            "source": getattr(model, "source", "user"),
            "ready_for_prompt": model.ready_for_prompt,
            "archived": model.archived,
            "archived_reason": model.archived_reason,
            "data": data,
        })


__all__ = ["AgentSessionRepository"]
