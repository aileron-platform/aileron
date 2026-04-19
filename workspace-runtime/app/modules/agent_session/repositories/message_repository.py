"""Message Repository.

提供訊息資料的存取操作，包含佇列管理功能。
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

    提供訊息的 CRUD 操作、範圍查詢和佇列管理。
    """

    def __init__(self, db: AsyncSession):
        """初始化 Repository."""
        super().__init__(db, AgentMessageModel, "message_id")

    def _get_id_column(self) -> Any:
        """取得主鍵欄位."""
        return AgentMessageModel.message_id

    async def find_by_session(
        self,
        session_id: str,
        task_id: Optional[str] = None,
        message_type: Optional[MessageType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AgentMessageModel]:
        """依會話 ID 查詢訊息.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID 過濾
            message_type: 訊息類型過濾
            limit: 最大筆數
            offset: 偏移量

        Returns:
            訊息列表
        """
        conditions = [
            AgentMessageModel.session_id == session_id,
            # 排除佇列中的訊息
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
        """依任務 ID 查詢訊息.

        Args:
            task_id: 任務 ID
            limit: 最大筆數
            offset: 偏移量

        Returns:
            訊息列表
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
        """依索引範圍查詢訊息.

        Args:
            session_id: 會話 ID
            start_index: 起始索引
            end_index: 結束索引

        Returns:
            訊息列表
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
        """取得下一個訊息索引.

        Args:
            session_id: 會話 ID

        Returns:
            下一個索引值
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
        """批次建立訊息.

        Args:
            messages: 訊息資料列表

        Returns:
            建立的訊息列表
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
        """刪除會話的所有訊息.

        Args:
            session_id: 會話 ID

        Returns:
            刪除的記錄數
        """
        stmt = delete(AgentMessageModel).where(
            AgentMessageModel.session_id == session_id
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    # === 佇列管理方法 ===
    # NOTE: 舊的 get_queue_messages, add_to_queue, pop_queue, clear_queue 已移除
    # 使用新的 Queue Management Methods: find_queued, create_queued, delete_queued, count_queued

    async def count_queue(
        self,
        session_id: str,
    ) -> int:
        """計算佇列中的訊息數量.

        Args:
            session_id: 會話 ID

        Returns:
            佇列訊息數量
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
        """查詢權限請求訊息.

        使用 session_id + type 索引優化查詢，
        並按時間倒序搜尋（最新的權限請求最可能匹配）。

        Args:
            session_id: 會話 ID
            request_id: 請求 ID

        Returns:
            權限請求訊息或 None
        """
        # 使用索引 agent_messages_session_type_idx
        # 按時間倒序，最新的權限請求優先（通常最可能匹配）
        stmt = (
            select(AgentMessageModel)
            .where(
                and_(
                    AgentMessageModel.session_id == session_id,
                    AgentMessageModel.type == MessageType.PERMISSION_REQUEST.value,
                )
            )
            .order_by(AgentMessageModel.created_at.desc())
            .limit(50)  # 限制搜尋範圍，避免掃描過多記錄
        )

        result = await self.db.execute(stmt)
        messages = result.scalars().all()

        # 在 data blob 中查找 request_id
        for msg in messages:
            # 反序列化 data (JSON 字符串 -> dict)
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
        """建立佇列訊息.

        Args:
            session_id: 會話 ID
            prompt: Prompt 內容
            metadata: 額外的 metadata

        Returns:
            建立的 queued message
        """
        # 取得當前最大 queue_position
        stmt = select(func.max(AgentMessageModel.queue_position)).where(
            and_(
                AgentMessageModel.session_id == session_id,
                AgentMessageModel.status == MessageStatus.QUEUED.value,
            )
        )
        result = await self.db.execute(stmt)
        max_position = result.scalar()
        next_position = (max_position or 0) + 1

        # 建立 queued message
        from uuid import uuid4
        message = AgentMessageModel(
            message_id=str(uuid4()),
            session_id=session_id,
            task_id=None,  # Queued messages 沒有 task_id
            type=MessageType.USER.value,
            role=MessageRole.USER.value,
            index=0,  # 會在執行時重新分配
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
        """查詢所有 queued messages（按 queue_position 排序）.

        Args:
            session_id: 會話 ID

        Returns:
            Queued messages 列表
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
        """取得下一個 queued message.

        Args:
            session_id: 會話 ID

        Returns:
            下一個 queued message 或 None
        """
        queued = await self.find_queued(session_id)
        return queued[0] if queued else None

    async def claim_next_queued(self, session_id: str) -> Optional[AgentMessageModel]:
        """Claim 下一個 queued message 並標記為 dispatching."""
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
        """刪除 queued message.

        Args:
            message_id: 訊息 ID

        Returns:
            是否成功刪除
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
        """刪除 dispatching message."""
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
        """將 dispatching message 還原為 queued."""
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
        """計算 session 中的 queued messages 數量.

        Args:
            session_id: 會話 ID

        Returns:
            Queued messages 數量
        """
        return await self.count_queue(session_id)

    def to_entity(self, model: AgentMessageModel) -> Message:
        """將 ORM 模型轉換為領域實體.

        Args:
            model: ORM 模型

        Returns:
            領域實體
        """
        # 反序列化 data (JSON 字符串 -> dict)
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
