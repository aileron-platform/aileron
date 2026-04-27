"""Message Repository.

Provides data access operations for messages, including queue management.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import Message
from ..domain.enums import MessageStatus, MessageType, MessageRole
from .base import BaseRepository
from .json_utils import safe_json_loads
from .sqlalchemy_models import AgentMessageModel

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository[AgentMessageModel]):
    """Message Repository.

    Provides CRUD operations, range queries, and queue management for messages.
    """

    def __init__(self, db: AsyncSession):
        """Initialize Repository."""
        super().__init__(db, AgentMessageModel, "message_id")

    def _get_id_column(self) -> Any:
        """Get primary key column."""
        return AgentMessageModel.message_id

    async def find_by_session(
        self,
        session_id: str,
        task_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AgentMessageModel]:
        """Query messages by session ID.

        Args:
            session_id: Session ID
            task_id: Task ID filter
            message_type: Message type filter
            limit: Max results
            offset: Offset

        Returns:
            Message list
        """
        conditions = [
            AgentMessageModel.session_id == session_id,
            # Exclude queued messages
            AgentMessageModel.status.is_(None),
        ]

        if task_id:
            conditions.append(AgentMessageModel.task_id == task_id)

        if message_type:
            conditions.append(AgentMessageModel.type == message_type.value)

        stmt = (
            select(AgentMessageModel)
            .where(and_(*conditions))
            .order_by(AgentMessageModel.created_at.asc(), AgentMessageModel.message_id.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_task(
        self,
        task_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AgentMessageModel]:
        """Query messages by task ID.

        Args:
            task_id: Task ID
            limit: Max results
            offset: Offset

        Returns:
            Message list
        """
        stmt = (
            select(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.task_id == task_id,
                    AgentMessageModel.status.is_(None),
                )
            )
            .order_by(AgentMessageModel.index.asc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_range(
        self,
        session_id: str,
        start_index: int,
        end_index: int,
    ) -> List[AgentMessageModel]:
        """Query messages by index range.

        Args:
            session_id: Session ID
            start_index: Start index
            end_index: End index

        Returns:
            Message list
        """
        stmt = (
            select(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.session_id == session_id,
                    AgentMessageModel.index >= start_index,
                    AgentMessageModel.index <= end_index,
                    AgentMessageModel.status.is_(None),
                )
            )
            .order_by(AgentMessageModel.index.asc())
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_next_index(self, session_id: str) -> int:
        """Get next message index.

        Args:
            session_id: Session ID

        Returns:
            Next index value
        """
        stmt = select(func.max(AgentMessageModel.index)).where(
            and_(
                AgentMessageModel.session_id == session_id,
                AgentMessageModel.status.is_(None),
            )
        )

        result = await self.db.execute(stmt)
        max_index = result.scalar()

        return (max_index or -1) + 1

    async def create_bulk(
        self,
        messages: List[Dict[str, Any]],
    ) -> List[AgentMessageModel]:
        """Batch create messages.

        Args:
            messages: Message data list

        Returns:
            Created message list
        """
        instances = []
        for msg_data in messages:
            instance = AgentMessageModel(**msg_data)
            self.db.add(instance)
            instances.append(instance)

        await self.db.flush()

        for instance in instances:
            await self.db.refresh(instance)

        return instances

    async def delete_by_session(self, session_id: str) -> int:
        """Delete all messages in session.

        Args:
            session_id: Session ID

        Returns:
            Number of deleted records
        """
        stmt = delete(AgentMessageModel).where(
            AgentMessageModel.session_id == session_id
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    # === Queue Management Methods ===
    # NOTE: Old get_queue_messages, add_to_queue, pop_queue, clear_queue removed
    # Use new Queue Management Methods: find_queued, create_queued, delete_queued, count_queued

    async def count_queue(
        self,
        session_id: str,
    ) -> int:
        """Count messages in queue.

        Args:
            session_id: Session ID

        Returns:
            Queue message count
        """
        stmt = select(func.count()).where(
            and_(
                AgentMessageModel.session_id == session_id,
                AgentMessageModel.status == MessageStatus.QUEUED.value,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def find_permission_request(
        self,
        session_id: str,
        request_id: str,
    ) -> Optional[AgentMessageModel]:
        """Query permission request message.

        Use session_id + type index to optimize query,
        and search by time descending (newest permission request most likely matches).

        Args:
            session_id: Session ID
            request_id: Request ID

        Returns:
            Permission request message or None
        """
        # Use index agent_messages_session_type_idx
        # Order by time descending, newest permission request first (usually most likely matches)
        stmt = (
            select(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.session_id == session_id,
                    AgentMessageModel.type == MessageType.PERMISSION_REQUEST.value,
                )
            )
            .order_by(AgentMessageModel.created_at.desc())
            .limit(50)  # Limit search range to avoid scanning too many records
        )

        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        # Find request_id in data blob
        for msg in messages:
            # Deserialize data (JSON string -> dict)
            data = safe_json_loads(msg.data, msg.message_id, "message")
            if not data:
                continue
            content = data.get("content", {})
            if isinstance(content, dict) and content.get("request_id") == request_id:
                return msg

        return None

    # =====================================================
    # Queue Management Methods
    # =====================================================

    async def create_queued(
        self,
        session_id: str,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessageModel:
        """Create queued message.

        Args:
            session_id: Session ID
            prompt: Prompt content
            metadata: Additional metadata

        Returns:
            Created queued message
        """
        # Get current max queue_position
        stmt = select(func.max(AgentMessageModel.queue_position)).where(
            and_(
                AgentMessageModel.session_id == session_id,
                AgentMessageModel.status == MessageStatus.QUEUED.value,
            )
        )
        result = await self.db.execute(stmt)
        max_position = result.scalar()
        next_position = (max_position or 0) + 1

        # Create queued message
        from uuid import uuid4
        message = AgentMessageModel(
            message_id=str(uuid4()),
            session_id=session_id,
            task_id=None,  # Queued messages do not have task_id
            type=MessageType.USER.value,
            role=MessageRole.USER.value,
            index=0,  # Will be reassigned during execution
            status=MessageStatus.QUEUED.value,
            queue_position=next_position,
            content_preview=prompt[:200] if prompt else None,
            data=json.dumps({
                "content": prompt,
                "metadata": metadata or {},
            }, ensure_ascii=False),
        )

        self.db.add(message)
        await self.db.flush()
        await self.db.refresh(message)

        return message

    async def find_queued(self, session_id: str) -> List[AgentMessageModel]:
        """Query all queued messages (sorted by queue_position).

        Args:
            session_id: Session ID

        Returns:
            Queued messages list
        """
        stmt = (
            select(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.session_id == session_id,
                    AgentMessageModel.status == MessageStatus.QUEUED.value,
                )
            )
            .order_by(AgentMessageModel.queue_position.asc())
        )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_next_queued(self, session_id: str) -> Optional[AgentMessageModel]:
        """Get next queued message.

        Args:
            session_id: Session ID

        Returns:
            Next queued message or None
        """
        queued = await self.find_queued(session_id)
        return queued[0] if queued else None

    async def claim_next_queued(self, session_id: str) -> Optional[AgentMessageModel]:
        """Claim next queued message and mark as dispatching."""
        next_queued = await self.get_next_queued(session_id)
        if not next_queued:
            return None

        stmt = (
            update(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.message_id == next_queued.message_id,
                    AgentMessageModel.status == MessageStatus.QUEUED.value,
                )
            )
            .values(status=MessageStatus.DISPATCHING.value)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        if result.rowcount != 1:
            return None

        next_queued.status = MessageStatus.DISPATCHING.value
        return next_queued

    async def delete_queued(self, message_id: str) -> bool:
        """Delete queued message.

        Args:
            message_id: Message ID

        Returns:
            Whether deletion succeeded
        """
        stmt = delete(AgentMessageModel).where(
            and_(
                AgentMessageModel.message_id == message_id,
                AgentMessageModel.status == MessageStatus.QUEUED.value,
            )
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        return result.rowcount > 0

    async def delete_dispatching(self, message_id: str) -> bool:
        """Delete dispatching message."""
        stmt = delete(AgentMessageModel).where(
            and_(
                AgentMessageModel.message_id == message_id,
                AgentMessageModel.status == MessageStatus.DISPATCHING.value,
            )
        )

        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def restore_dispatching(self, message_id: str) -> bool:
        """Restore dispatching message to queued."""
        stmt = (
            update(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.message_id == message_id,
                    AgentMessageModel.status == MessageStatus.DISPATCHING.value,
                )
            )
            .values(status=MessageStatus.QUEUED.value)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount > 0

    async def count_queued(self, session_id: str) -> int:
        """Count queued messages in session.

        Args:
            session_id: Session ID

        Returns:
            Queued messages count
        """
        return await self.count_queue(session_id)

    def to_entity(self, model: AgentMessageModel) -> Message:
        """Convert ORM model to domain entity.

        Args:
            model: ORM model

        Returns:
            Domain entity
        """
        # Deserialize data (JSON string -> dict)
        data = safe_json_loads(model.data, model.message_id, "message") if model.data else None

        return Message.from_db_row({
            "message_id": model.message_id,
            "created_at": model.created_at,
            "session_id": model.session_id,
            "task_id": model.task_id,
            "type": model.type,
            "role": model.role,
            "index": model.index,
            "timestamp": model.timestamp,
            "content_preview": model.content_preview,
            "parent_tool_use_id": model.parent_tool_use_id,
            "status": model.status,
            "queue_position": model.queue_position,
            "data": data,
        })


__all__ = ["MessageRepository"]
