"""Agent Session Repository.

提供 Agent 會話資料的存取操作。
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

    提供 Agent 會話的 CRUD 操作和特定查詢方法。
    """

    def __init__(self, db: AsyncSession):
        """初始化 Repository."""
        super().__init__(db, AgentSessionModel, "session_id")

    def _get_id_column(self) -> Any:
        """取得主鍵欄位."""
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
        """依工作區查詢會話.

        Args:
            workspace_id: 工作區 ID
            status: 會話狀態過濾
            agentic_tool: 工具類型過濾
            archived: 是否包含已封存
            limit: 最大筆數
            offset: 偏移量

        Returns:
            會話列表
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
        """依狀態查詢會話.

        Args:
            status: 會話狀態
            limit: 最大筆數
            offset: 偏移量

        Returns:
            會話列表
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
        """查詢工作區中正在執行的會話.

        Args:
            workspace_id: 工作區 ID

        Returns:
            正在執行的會話或 None
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
        """更新會話狀態.

        Args:
            session_id: 會話 ID
            status: 新狀態
            updated_at: 更新時間

        Returns:
            更新後的會話或 None
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
        """新增 Task 到會話.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID

        Returns:
            更新後的會話或 None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        tasks = data.get("tasks", [])

        # 新增 task_id
        if task_id not in tasks:
            tasks.append(task_id)
            data["tasks"] = tasks

            # 序列化後更新 (dict -> JSON 字符串)
            return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

        return session

    async def increment_message_count(
        self,
        session_id: str,
        count: int = 1,
    ) -> Optional[AgentSessionModel]:
        """增加訊息計數.

        Args:
            session_id: 會話 ID
            count: 增加數量

        Returns:
            更新後的會話或 None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        message_count = data.get("message_count", 0) + count
        data["message_count"] = message_count

        # 序列化後更新 (dict -> JSON 字符串)
        return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def update_context_usage(
        self,
        session_id: str,
        usage: int,
        limit: Optional[int] = None,
    ) -> Optional[AgentSessionModel]:
        """更新 Context Window 使用量.

        Args:
            session_id: 會話 ID
            usage: 當前使用量
            limit: Context 上限

        Returns:
            更新後的會話或 None
        """
        session = await self.find_by_id(session_id)
        if not session:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(session.data, session_id, "session")
        data["current_context_usage"] = usage
        data["last_context_update_at"] = utcnow().isoformat()

        if limit is not None:
            data["context_window_limit"] = limit

        # 序列化後更新 (dict -> JSON 字符串)
        return await self.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def archive(
        self,
        session_id: str,
        reason: str = "manual",
    ) -> Optional[AgentSessionModel]:
        """封存會話.

        Args:
            session_id: 會話 ID
            reason: 封存原因

        Returns:
            更新後的會話或 None
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
        """將 ORM 模型轉換為領域實體.

        Args:
            model: ORM 模型

        Returns:
            領域實體
        """
        # 反序列化 data (JSON 字符串 -> dict)
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
