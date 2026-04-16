"""Agent Session Service.

提供會話的業務邏輯，包含建立、查詢、執行 prompt 等功能。
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.modules.version_control.utils import GitUtils
from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)

from ..domain.entities import AgentSession
from ..domain.enums import AgenticTool, AgentSessionStatus
from ..domain.value_objects import (
    ModelConfig,
    PermissionConfig,
    TOOL_CAPABILITIES,
    ToolCapabilities,
    get_tool_capabilities,
)
from ..repositories.agent_session_repository import AgentSessionRepository
from ..repositories.task_repository import TaskRepository
from ..schemas.agent_session import (
    AgentSessionCreate,
    AgentSessionQuery,
    AgentSessionResponse,
    AgentSessionUpdate,
)
from ..websocket.events import EventEmitter, get_event_emitter


class AgentSessionService:
    """Agent Session Service.

    處理會話相關的業務邏輯。
    """

    def __init__(
        self,
        db: AsyncSession,
        session_repo: Optional[AgentSessionRepository] = None,
        task_repo: Optional[TaskRepository] = None,
        emitter: Optional[EventEmitter] = None,
        git_utils: Optional[GitUtils] = None,
    ):
        """初始化 Service.

        Args:
            db: 資料庫 session
            session_repo: Session Repository (可注入)
            task_repo: Task Repository (可注入)
            emitter: Event Emitter (可注入)
        """
        self.db = db
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.task_repo = task_repo or TaskRepository(db)
        self.emitter = emitter or get_event_emitter()
        workspace_root = Path(get_settings().WORKSPACE_PATH).resolve()
        self.git_utils = git_utils or GitUtils(workspace_root)

    async def create_session(
        self,
        data: AgentSessionCreate,
    ) -> AgentSession:
        """建立會話.

        Args:
            data: 建立請求資料

        Returns:
            建立的會話實體
        """
        session_id = str(uuid.uuid4())
        now = utcnow()
        custom_context: Dict[str, Any] = {}

        if data.git_context_id:
            workspace_path = str(
                self.git_utils.resolve_context_path(
                    data.workspace_id,
                    data.git_context_id,
                )
            )
            custom_context["git_context_id"] = data.git_context_id
            custom_context["workspace_path"] = workspace_path

        # 建立 data blob
        data_blob: Dict[str, Any] = {
            "tasks": [],
            "message_count": 0,
            "contextFiles": data.context_files,
        }
        if custom_context:
            data_blob["custom_context"] = custom_context

        if data.title:
            data_blob["title"] = data.title

        if data.permission_config:
            data_blob["permission_config"] = {
                "mode": data.permission_config.mode.value,
            }
            if data.permission_config.codex:
                data_blob["permission_config"]["codex"] = data.permission_config.codex

        if data.model_settings:
            data_blob["model_config"] = {
                "mode": data.model_settings.mode,
                "model": data.model_settings.model,
                "updated_at": now.isoformat(),
            }
            if data.model_settings.thinking_mode:
                data_blob["model_config"]["thinkingMode"] = data.model_settings.thinking_mode
            if data.model_settings.manual_thinking_tokens:
                data_blob["model_config"]["manualThinkingTokens"] = data.model_settings.manual_thinking_tokens
            if data.model_settings.provider:
                data_blob["model_config"]["provider"] = data.model_settings.provider

        # 設定 context window limit
        tool_caps = get_tool_capabilities(data.agentic_tool.value)
        if tool_caps:
            data_blob["context_window_limit"] = tool_caps.max_context_window

        # 建立記錄 (data 序列化為 JSON 字串存入 TEXT 欄位)
        model = await self.session_repo.create({
            "session_id": session_id,
            "created_at": now,
            "created_by": data.user_id or "anonymous",
            "status": AgentSessionStatus.IDLE.value,
            "agentic_tool": data.agentic_tool.value,
            "workspace_id": data.workspace_id,
            "source": data.source,
            "ready_for_prompt": True,
            "archived": False,
            "data": json.dumps(data_blob, ensure_ascii=False),
        })

        session_entity = self.session_repo.to_entity(model)

        # 發送 sessions:created 事件
        logger.debug("Sending sessions:created event - session_id=%s", session_id)
        try:
            sent_count = await self.emitter.emit_session_created(
                session_id=session_id,
                data=self._session_to_event_data(session_entity),
            )
            logger.debug("sessions:created event sent to %d connections", sent_count)
        except Exception as e:
            logger.error("Failed to send sessions:created event: %s", e)

        return session_entity

    async def get_session(
        self,
        session_id: str,
    ) -> Optional[AgentSession]:
        """取得會話.

        Args:
            session_id: 會話 ID

        Returns:
            會話實體或 None
        """
        model = await self.session_repo.find_by_id(session_id)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def find_sessions(
        self,
        query: AgentSessionQuery,
    ) -> Tuple[List[AgentSession], int]:
        """查詢會話列表.

        Args:
            query: 查詢參數

        Returns:
            (會話列表, 總數)
        """
        # 建立過濾條件
        filters: Dict[str, Any] = {"archived": query.archived}

        if query.workspace_id:
            filters["workspace_id"] = query.workspace_id
        if query.status:
            filters["status"] = query.status.value
        if query.agentic_tool:
            filters["agentic_tool"] = query.agentic_tool.value
        if query.source:
            filters["source"] = query.source

        # 查詢
        models = await self.session_repo.find_all(
            filters=filters,
            limit=query.limit,
            offset=query.offset,
            order_by="created_at",
            order_desc=True,
        )

        # 計算總數
        total = await self.session_repo.count(filters)

        # 轉換為實體
        sessions = [self.session_repo.to_entity(m) for m in models]

        return sessions, total

    async def update_session(
        self,
        session_id: str,
        data: AgentSessionUpdate,
    ) -> Optional[AgentSession]:
        """更新會話.

        Args:
            session_id: 會話 ID
            data: 更新資料

        Returns:
            更新後的會話或 None
        """
        existing = await self.session_repo.find_by_id(session_id)
        if not existing:
            return None

        update_data: Dict[str, Any] = {}

        if data.status is not None:
            update_data["status"] = data.status.value

        if data.archived is not None:
            update_data["archived"] = data.archived

        if data.archived_reason is not None:
            update_data["archived_reason"] = data.archived_reason

        # 更新 data blob
        if data.title is not None or data.permission_config is not None or data.model_settings is not None:
            # 反序列化 existing data (JSON 字符串 -> dict)
            existing_data = json.loads(existing.data) if existing.data else {}

            if data.title is not None:
                existing_data["title"] = data.title

            if data.permission_config is not None:
                existing_data["permission_config"] = {
                    "mode": data.permission_config.mode.value,
                }
                if data.permission_config.codex:
                    existing_data["permission_config"]["codex"] = data.permission_config.codex

            if data.model_settings is not None:
                existing_data["model_config"] = {
                    "mode": data.model_settings.mode,
                    "model": data.model_settings.model,
                    "updated_at": utcnow().isoformat(),
                }
                if data.model_settings.thinking_mode:
                    existing_data["model_config"]["thinkingMode"] = data.model_settings.thinking_mode
                if data.model_settings.manual_thinking_tokens:
                    existing_data["model_config"]["manualThinkingTokens"] = data.model_settings.manual_thinking_tokens
                if data.model_settings.provider:
                    existing_data["model_config"]["provider"] = data.model_settings.provider

            # 序列化後更新 (dict -> JSON 字符串)
            update_data["data"] = json.dumps(existing_data, ensure_ascii=False)

        if not update_data:
            return self.session_repo.to_entity(existing)

        model = await self.session_repo.update(session_id, update_data)
        if not model:
            return None

        session_entity = self.session_repo.to_entity(model)

        # 發送 sessions:patched 事件
        await self.emitter.emit_session_patched(
            session_id=session_id,
            data=self._session_to_event_data(session_entity),
        )

        return session_entity

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        """刪除會話.

        Args:
            session_id: 會話 ID

        Returns:
            是否成功刪除
        """
        # 清理相關資源
        from .execution_service import ExecutionService
        ExecutionService.cleanup_session_lock(session_id)

        return await self.session_repo.delete(session_id)

    async def archive_session(
        self,
        session_id: str,
        reason: str = "manual",
    ) -> Optional[AgentSession]:
        """封存會話.

        Args:
            session_id: 會話 ID
            reason: 封存原因

        Returns:
            更新後的會話或 None
        """
        model = await self.session_repo.archive(session_id, reason)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def get_current_execution(
        self,
        workspace_id: str,
    ) -> Optional[Dict[str, Any]]:
        """取得工作區當前執行中的會話.

        Args:
            workspace_id: 工作區 ID

        Returns:
            執行狀態資訊或 None
        """
        model = await self.session_repo.find_running_by_workspace(workspace_id)
        if not model:
            return {
                "has_active_execution": False,
            }

        # 查詢活躍的 task
        active_task = await self.task_repo.find_active_by_session(model.session_id)

        return {
            "has_active_execution": True,
            "session_id": model.session_id,
            "task_id": active_task.id if active_task else None,
            "agentic_tool": model.agentic_tool,
            "started_at": active_task.started_at if active_task else None,
        }

    async def update_status(
        self,
        session_id: str,
        status: AgentSessionStatus,
    ) -> Optional[AgentSession]:
        """更新會話狀態.

        Args:
            session_id: 會話 ID
            status: 新狀態

        Returns:
            更新後的會話或 None
        """
        model = await self.session_repo.update_status(session_id, status)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def add_task(
        self,
        session_id: str,
        task_id: str,
    ) -> Optional[AgentSession]:
        """新增 Task 到會話.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID

        Returns:
            更新後的會話或 None
        """
        model = await self.session_repo.add_task(session_id, task_id)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def increment_message_count(
        self,
        session_id: str,
        count: int = 1,
    ) -> Optional[AgentSession]:
        """增加訊息計數.

        Args:
            session_id: 會話 ID
            count: 增加數量

        Returns:
            更新後的會話或 None
        """
        model = await self.session_repo.increment_message_count(session_id, count)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    async def update_context_usage(
        self,
        session_id: str,
        usage: int,
        limit: Optional[int] = None,
    ) -> Optional[AgentSession]:
        """更新 Context Window 使用量.

        Args:
            session_id: 會話 ID
            usage: 當前使用量
            limit: Context 上限

        Returns:
            更新後的會話或 None
        """
        model = await self.session_repo.update_context_usage(session_id, usage, limit)
        if not model:
            return None

        return self.session_repo.to_entity(model)

    @staticmethod
    def get_tool_capabilities(tool: str) -> Optional[ToolCapabilities]:
        """取得工具能力.

        Args:
            tool: 工具名稱

        Returns:
            工具能力描述
        """
        return get_tool_capabilities(tool)

    @staticmethod
    def get_all_tool_capabilities() -> Dict[str, ToolCapabilities]:
        """取得所有工具能力.

        Returns:
            所有工具的能力描述
        """
        return TOOL_CAPABILITIES

    @staticmethod
    def _session_to_event_data(session: AgentSession) -> Dict[str, Any]:
        """將 AgentSession 實體轉換為事件數據.

        包含完整的會話資訊，用於 WebSocket 事件廣播。

        Args:
            session: AgentSession 實體

        Returns:
            事件數據字典
        """
        data = {
            "session_id": session.id,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "created_by": session.created_by,
            "status": session.status.value if hasattr(session.status, "value") else session.status,
            "agentic_tool": session.agentic_tool.value if hasattr(session.agentic_tool, "value") else session.agentic_tool,
            "workspace_id": session.workspace_id,
            "source": session.source,
            "ready_for_prompt": session.ready_for_prompt,
            "archived": session.archived,
        }

        # 添加 Session 實體中的信息
        if session.title:
            data["title"] = session.title
        if session.message_count > 0:
            data["message_count"] = session.message_count
        if session.tasks:
            data["tasks"] = session.tasks
        if session.permission_config:
            data["permission_config"] = session.permission_config.to_dict()
        if session.model_settings:
            data["model_config"] = session.model_settings.to_dict()

        return data


__all__ = ["AgentSessionService"]
