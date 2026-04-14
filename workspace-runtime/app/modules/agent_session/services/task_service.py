"""Task Service.

提供任務的業務邏輯，包含建立、狀態轉換、完成等功能。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.entities import Task
from ..domain.enums import AgentSessionStatus, TaskStatus
from ..domain.value_objects import MessageRange, TokenUsage
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.task import TaskCreate, TaskQuery
from ..websocket.events import EventEmitter, get_event_emitter


class TaskServiceError(Exception):
    """Task Service 錯誤."""

    pass


class InvalidStateTransitionError(TaskServiceError):
    """無效的狀態轉換."""

    pass


class TaskService:
    """Task Service.

    處理任務相關的業務邏輯。
    """

    def __init__(
        self,
        db: AsyncSession,
        task_repo: Optional[TaskRepository] = None,
        session_repo: Optional[AgentSessionRepository] = None,
        emitter: Optional[EventEmitter] = None,
    ):
        """初始化 Service.

        Args:
            db: 資料庫 session
            task_repo: Task Repository (可注入)
            session_repo: Session Repository (可注入)
            emitter: Event Emitter (可注入)
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
        """建立任務.

        Args:
            session_id: 會話 ID
            full_prompt: 完整 prompt
            created_by: 建立者

        Returns:
            建立的任務實體
        """
        task_id = str(uuid.uuid4())
        now = utcnow()

        # 建立 data blob
        data_blob: Dict[str, Any] = {
            "full_prompt": full_prompt,
            "tool_use_count": 0,
        }

        # 建立記錄 (data 序列化為 JSON 字串存入 TEXT 欄位)
        model = await self.task_repo.create({
            "task_id": task_id,
            "session_id": session_id,
            "created_at": now,
            "created_by": created_by,
            "status": TaskStatus.CREATED.value,
            "data": json.dumps(data_blob, ensure_ascii=False),
        })

        # 將 task 加入 session
        await self.session_repo.add_task(session_id, task_id)

        task_entity = self.task_repo.to_entity(model)

        # 發送 tasks:created 事件
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
        """取得任務.

        Args:
            task_id: 任務 ID

        Returns:
            任務實體或 None
        """
        model = await self.task_repo.find_by_id(task_id)
        if not model:
            return None

        return self.task_repo.to_entity(model)

    async def find_tasks(
        self,
        query: TaskQuery,
    ) -> Tuple[List[Task], int]:
        """查詢任務列表.

        Args:
            query: 查詢參數

        Returns:
            (任務列表, 總數)
        """
        # 建立過濾條件
        filters: Dict[str, Any] = {}

        if query.session_id:
            filters["session_id"] = query.session_id
        if query.status:
            filters["status"] = query.status.value

        # 查詢
        models = await self.task_repo.find_all(
            filters=filters,
            limit=query.limit,
            offset=query.offset,
            order_by="created_at",
            order_desc=True,
        )

        # 計算總數
        total = await self.task_repo.count(filters)

        # 轉換為實體
        tasks = [self.task_repo.to_entity(m) for m in models]

        return tasks, total

    async def start_task(
        self,
        task_id: str,
    ) -> Task:
        """開始執行任務.

        將任務狀態從 CREATED 轉換為 RUNNING。

        Args:
            task_id: 任務 ID

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在
            InvalidStateTransitionError: 無效的狀態轉換
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

        # 更新 session 狀態
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.RUNNING)

        # 發送 task patched 事件通知前端 task 已開始
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "running"}
        )

        # 發送 session patched 事件通知前端
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
    ) -> Task:
        """完成任務.

        Args:
            task_id: 任務 ID
            raw_sdk_response: SDK 原始回應
            computed_context_window: 計算的 Context Window

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在或操作失敗
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

        # 更新 session 狀態
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # 發送 task patched 事件通知前端 task 已完成
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "completed"}
        )

        # 發送 session patched 事件通知前端
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        # 更新 context usage
        if computed_context_window is not None:
            await self.session_repo.update_context_usage(
                task.session_id,
                computed_context_window,
            )

        return self.task_repo.to_entity(model)

    async def fail_task(
        self,
        task_id: str,
        error_message: Optional[str] = None,
    ) -> Task:
        """標記任務失敗.

        Args:
            task_id: 任務 ID
            error_message: 錯誤訊息

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在或操作失敗
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        model = await self.task_repo.fail_task(task_id, error_message)
        if not model:
            raise TaskServiceError(f"Failed to fail task: {task_id}")

        # 更新 session 狀態
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # 發送 task patched 事件通知前端 task 已失敗
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "failed", "error_message": error_message}
        )

        # 發送 session patched 事件通知前端
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        return self.task_repo.to_entity(model)

    async def stop_task(
        self,
        task_id: str,
    ) -> Task:
        """停止任務.

        Args:
            task_id: 任務 ID

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在
            InvalidStateTransitionError: 無效的狀態轉換
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # 根據當前狀態決定目標狀態
        model = None
        if task.status in [TaskStatus.RUNNING, TaskStatus.AWAITING_PERMISSION, TaskStatus.STOPPING]:
            # 直接設為 stopped
            # 這樣可以處理多個 stop_task 調用的競態條件
            model = await self.task_repo.stop_task(task_id)

        # 更新 session 狀態
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.IDLE)

        # 發送 task patched 事件通知前端 task 已停止
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "stopped"}
        )

        # 發送 session patched 事件通知前端
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.IDLE.value}
        )

        # 發送 task stop 事件
        await self.emitter.emit_task_stopped(
            session_id=task.session_id,
            task_id=task.id,
        )

        # 如果 model 是 None，重新獲取
        if not model:
            model = await self.task_repo.find_by_id(task_id)

        return self.task_repo.to_entity(model)

    async def set_awaiting_permission(
        self,
        task_id: str,
        permission_request: Dict[str, Any],
    ) -> Task:
        """設定任務等待權限.

        此方法設計為冪等操作，以處理競態條件：
        - 如果狀態是 running，正常轉換到 awaiting_permission
        - 如果狀態已經是 awaiting_permission，只更新 permission_request（可能是連續的權限請求）
        - 其他狀態才拋出錯誤

        Args:
            task_id: 任務 ID
            permission_request: 權限請求資訊

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在
            InvalidStateTransitionError: 無效的狀態轉換
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # 冪等性處理：如果已經是 awaiting_permission 狀態，只更新 permission_request
        # 這可能發生在：
        # 1. 權限批准後 DB 還沒更新完成，Claude SDK 就請求下一個權限
        # 2. 連續多個工具需要權限的情況
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

        # 更新 session 狀態
        await self.session_repo.update_status(
            task.session_id,
            AgentSessionStatus.AWAITING_PERMISSION,
        )

        # 發送 task patched 事件通知前端 task 等待權限
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "awaiting_permission"}
        )

        # 發送 session patched 事件通知前端
        await self.emitter.emit_session_patched(
            task.session_id,
            {"session_id": task.session_id, "status": AgentSessionStatus.AWAITING_PERMISSION.value}
        )

        return self.task_repo.to_entity(model)

    async def resume_from_permission(
        self,
        task_id: str,
    ) -> Task:
        """權限批准後恢復執行.

        此方法設計為冪等操作，以處理競態條件和重複請求：
        - 如果狀態是 awaiting_permission，正常 resume
        - 如果狀態已經是 running，視為成功（可能是重複請求或競態條件）
        - 其他狀態才拋出錯誤

        Args:
            task_id: 任務 ID

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在
            InvalidStateTransitionError: 無效的狀態轉換
        """
        task = await self.get_task(task_id)
        if not task:
            raise TaskServiceError(f"Task not found: {task_id}")

        # 冪等性處理：如果已經是 running 狀態，直接返回（可能是重複請求或競態條件）
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

        # 更新 session 狀態
        await self.session_repo.update_status(task.session_id, AgentSessionStatus.RUNNING)

        # 發送 task patched 事件通知前端 task 恢復執行
        await self.emitter.emit_task_patched(
            task.session_id,
            task_id,
            {"task_id": task_id, "status": "running"}
        )

        # 發送 session patched 事件通知前端
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
        """更新訊息範圍.

        Args:
            task_id: 任務 ID
            start_index: 起始索引
            end_index: 結束索引
            start_timestamp: 起始時間
            end_timestamp: 結束時間

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在或操作失敗
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
        """增加工具使用計數.

        Args:
            task_id: 任務 ID
            count: 增加數量

        Returns:
            更新後的任務

        Raises:
            TaskServiceError: 任務不存在或操作失敗
        """
        model = await self.task_repo.increment_tool_use_count(task_id, count)
        if not model:
            raise TaskServiceError(f"Failed to increment tool use count: {task_id}")

        return self.task_repo.to_entity(model)

    async def get_active_task(
        self,
        session_id: str,
    ) -> Optional[Task]:
        """取得會話中活躍的任務.

        Args:
            session_id: 會話 ID

        Returns:
            活躍的任務或 None
        """
        model = await self.task_repo.find_active_by_session(session_id)
        if not model:
            return None

        return self.task_repo.to_entity(model)

    @staticmethod
    def extract_token_usage(raw_sdk_response: Dict[str, Any]) -> Optional[TokenUsage]:
        """從 SDK 回應提取 token 使用量.

        Args:
            raw_sdk_response: SDK 原始回應

        Returns:
            Token 使用量或 None
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
            turn = response.get("turn", {})
            usage = turn.get("usage", {})
            return TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
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
        """取得會話的所有 active tasks.

        Active tasks 包含 CREATED, RUNNING 和 AWAITING_PERMISSION 狀態的任務。
        CREATED 狀態表示 task 已建立但尚未開始執行，也應視為 active。

        Args:
            session_id: 會話 ID

        Returns:
            Active tasks 列表
        """
        models = await self.task_repo.find_by_session(
            session_id=session_id,
            status=[TaskStatus.CREATED, TaskStatus.RUNNING, TaskStatus.AWAITING_PERMISSION],
        )
        return [self.task_repo.to_entity(m) for m in models]

    @staticmethod
    def _task_to_event_data(task: Task) -> Dict[str, Any]:
        """將 Task 實體轉換為事件數據.

        包含完整的任務資訊，用於 WebSocket 事件廣播。

        Args:
            task: Task 實體

        Returns:
            事件數據字典
        """
        data = {
            "task_id": task.id,
            "session_id": task.session_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "created_by": task.created_by,
            "status": task.status,
        }

        # 添加 Task 實體中的信息
        if task.full_prompt:
            data["description"] = task.full_prompt[:100]  # 前 100 個字符作為摘要
        if task.tool_use_count > 0:
            data["tool_use_count"] = task.tool_use_count

        return data


__all__ = [
    "InvalidStateTransitionError",
    "TaskService",
    "TaskServiceError",
]
