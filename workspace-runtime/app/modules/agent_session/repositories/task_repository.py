"""Task Repository.

提供任務資料的存取操作。
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

    提供任務的 CRUD 操作和狀態管理方法。
    """

    def __init__(self, db: AsyncSession):
        """初始化 Repository."""
        super().__init__(db, AgentTaskModel, "task_id")

    def _get_id_column(self) -> Any:
        """取得主鍵欄位."""
        return AgentTaskModel.task_id

    async def find_by_session(
        self,
        session_id: str,
        status: Optional[Union[TaskStatus, List[TaskStatus]]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AgentTaskModel]:
        """依會話 ID 查詢任務.

        Args:
            session_id: 會話 ID
            status: 任務狀態過濾（單個或多個）
            limit: 最大筆數
            offset: 偏移量

        Returns:
            任務列表
        """
        conditions = [AgentTaskModel.session_id == session_id]

        if status:
            if isinstance(status, list):
                # 多個狀態
                status_values = [s.value for s in status]
                conditions.append(AgentTaskModel.status.in_(status_values))
            else:
                # 單個狀態
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
        """依狀態查詢任務.

        Args:
            status: 任務狀態
            limit: 最大筆數
            offset: 偏移量

        Returns:
            任務列表
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
        """查詢會話中活躍的任務.

        Args:
            session_id: 會話 ID

        Returns:
            活躍的任務或 None
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
        """開始執行任務.

        Args:
            task_id: 任務 ID
            started_at: 開始時間

        Returns:
            更新後的任務或 None
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
        """完成任務.

        Args:
            task_id: 任務 ID
            raw_sdk_response: SDK 原始回應
            computed_context_window: 計算的 Context Window
            completed_at: 完成時間

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = ensure_utc(completed_at) or datetime.now(timezone.utc)
        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # 計算執行時間
        if task.started_at:
            started_at = ensure_utc(task.started_at)
            if started_at:
                duration_ms = int((now - started_at).total_seconds() * 1000)
                data["duration_ms"] = duration_ms

        # 儲存 SDK 回應
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
        """標記任務失敗.

        Args:
            task_id: 任務 ID
            error_message: 錯誤訊息
            completed_at: 完成時間

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = ensure_utc(completed_at) or datetime.now(timezone.utc)
        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # 計算執行時間
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
        """停止任務.

        Args:
            task_id: 任務 ID
            completed_at: 完成時間

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        now = completed_at or datetime.now(timezone.utc)
        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(task.data, task_id, "task")

        # 計算執行時間
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
        """設定任務等待權限.

        Args:
            task_id: 任務 ID
            permission_request: 權限請求資訊

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
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
        """更新訊息範圍.

        Args:
            task_id: 任務 ID
            message_range: 訊息範圍

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(task.data, task_id, "task")
        data["message_range"] = message_range.to_dict()

        return await self.update(task_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def increment_tool_use_count(
        self,
        task_id: str,
        count: int = 1,
    ) -> Optional[AgentTaskModel]:
        """增加工具使用計數.

        Args:
            task_id: 任務 ID
            count: 增加數量

        Returns:
            更新後的任務或 None
        """
        task = await self.find_by_id(task_id)
        if not task:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = safe_json_loads(task.data, task_id, "task")
        tool_use_count = data.get("tool_use_count", 0) + count
        data["tool_use_count"] = tool_use_count

        return await self.update(task_id, {"data": json.dumps(data, ensure_ascii=False)})

    def to_entity(self, model: AgentTaskModel) -> Task:
        """將 ORM 模型轉換為領域實體.

        Args:
            model: ORM 模型

        Returns:
            領域實體
        """
        # 反序列化 data (JSON 字符串 -> dict)
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
