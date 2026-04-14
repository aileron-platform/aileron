"""Message Service.

提供訊息的業務邏輯，包含建立、查詢、佇列管理等功能。
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import utcnow

from ..domain.entities import Message
from ..domain.enums import MessageRole, MessageStatus, MessageType
from ..domain.value_objects import PermissionRequestContent, ToolUse
from ..repositories.message_repository import MessageRepository
from ..repositories.agent_session_repository import AgentSessionRepository
from ..schemas.message import MessageCreate, MessageQuery
from ..websocket.events import EventEmitter, get_event_emitter


class MessageServiceError(Exception):
    """Message Service 錯誤."""

    pass


class MessageService:
    """Message Service.

    處理訊息相關的業務邏輯。
    """

    def __init__(
        self,
        db: AsyncSession,
        message_repo: Optional[MessageRepository] = None,
        session_repo: Optional[AgentSessionRepository] = None,
        emitter: Optional[EventEmitter] = None,
    ):
        """初始化 Service.

        Args:
            db: 資料庫 session
            message_repo: Message Repository (可注入)
            session_repo: Session Repository (可注入)
            emitter: WebSocket 事件發送器 (可注入)
        """
        self.db = db
        self.message_repo = message_repo or MessageRepository(db)
        self.session_repo = session_repo or AgentSessionRepository(db)
        self.emitter = emitter or get_event_emitter()

    async def create_message(
        self,
        data: MessageCreate,
    ) -> Message:
        """建立訊息.

        Args:
            data: 建立請求資料

        Returns:
            建立的訊息實體
        """
        message_id = str(uuid.uuid4())
        now = utcnow()

        # 取得下一個索引
        next_index = await self.message_repo.get_next_index(data.session_id)

        # 建立 data blob
        data_blob: Dict[str, Any] = {
            "content": data.content,
        }

        if data.tool_uses:
            data_blob["tool_uses"] = [
                {"id": tu.id, "name": tu.name, "input": tu.input}
                for tu in data.tool_uses
            ]

        if data.metadata:
            data_blob["metadata"] = data.metadata

        # 計算內容預覽
        content_preview = self._get_content_preview(data.content)

        # 建立記錄 (data 序列化為 JSON 字串存入 TEXT 欄位)
        model = await self.message_repo.create({
            "message_id": message_id,
            "created_at": now,
            "session_id": data.session_id,
            "task_id": data.task_id,
            "type": data.type.value,
            "role": data.role.value,
            "index": next_index,
            "timestamp": now,
            "content_preview": content_preview,
            "parent_tool_use_id": data.parent_tool_use_id,
            "data": self._json_dumps(data_blob),
        })

        # 更新 session 的 message_count
        await self.session_repo.increment_message_count(data.session_id)

        # 如果是第一個用戶訊息，自動設定 session title
        if data.role == MessageRole.USER and next_index == 0:
            await self._update_session_title_from_first_message(
                data.session_id, content_preview
            )

        return self.message_repo.to_entity(model)

    async def get_message(
        self,
        message_id: str,
    ) -> Optional[Message]:
        """取得訊息.

        Args:
            message_id: 訊息 ID

        Returns:
            訊息實體或 None
        """
        model = await self.message_repo.find_by_id(message_id)
        if not model:
            return None

        return self.message_repo.to_entity(model)

    async def find_messages(
        self,
        query: MessageQuery,
    ) -> Tuple[List[Message], int]:
        """查詢訊息列表.

        Args:
            query: 查詢參數

        Returns:
            (訊息列表, 總數)
        """
        if not query.session_id:
            raise MessageServiceError("session_id is required")

        # 查詢
        models = await self.message_repo.find_by_session(
            session_id=query.session_id,
            task_id=query.task_id,
            message_type=query.type,
            limit=query.limit,
            offset=query.offset,
        )

        # 計算總數
        filters = {"session_id": query.session_id, "status": None}
        if query.task_id:
            filters["task_id"] = query.task_id
        if query.type:
            filters["type"] = query.type.value

        total = await self.message_repo.count(filters)

        # 轉換為實體
        messages = [self.message_repo.to_entity(m) for m in models]

        return messages, total

    async def find_by_task(
        self,
        task_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Message]:
        """依任務 ID 查詢訊息.

        Args:
            task_id: 任務 ID
            limit: 最大筆數
            offset: 偏移量

        Returns:
            訊息列表
        """
        models = await self.message_repo.find_by_task(task_id, limit, offset)
        return [self.message_repo.to_entity(m) for m in models]

    async def find_by_range(
        self,
        session_id: str,
        start_index: int,
        end_index: int,
    ) -> List[Message]:
        """依索引範圍查詢訊息.

        Args:
            session_id: 會話 ID
            start_index: 起始索引
            end_index: 結束索引

        Returns:
            訊息列表
        """
        models = await self.message_repo.find_by_range(
            session_id,
            start_index,
            end_index,
        )
        return [self.message_repo.to_entity(m) for m in models]

    async def create_bulk(
        self,
        messages: List[MessageCreate],
    ) -> List[Message]:
        """批次建立訊息.

        Args:
            messages: 訊息建立請求列表

        Returns:
            建立的訊息列表
        """
        if not messages:
            return []

        session_id = messages[0].session_id
        now = utcnow()

        # 取得起始索引
        start_index = await self.message_repo.get_next_index(session_id)

        # 準備批次資料
        bulk_data = []
        for i, data in enumerate(messages):
            message_id = str(uuid.uuid4())

            data_blob: Dict[str, Any] = {
                "content": data.content,
            }

            if data.tool_uses:
                data_blob["tool_uses"] = [
                    {"id": tu.id, "name": tu.name, "input": tu.input}
                    for tu in data.tool_uses
                ]

            if data.metadata:
                data_blob["metadata"] = data.metadata

            content_preview = self._get_content_preview(data.content)

            bulk_data.append({
                "message_id": message_id,
                "created_at": now,
                "session_id": data.session_id,
                "task_id": data.task_id,
                "type": data.type.value,
                "role": data.role.value,
                "index": start_index + i,
                "timestamp": now,
                "content_preview": content_preview,
                "parent_tool_use_id": data.parent_tool_use_id,
                "data": self._json_dumps(data_blob),
            })

        # 批次建立
        models = await self.message_repo.create_bulk(bulk_data)

        # 更新 session 的 message_count
        await self.session_repo.increment_message_count(session_id, len(messages))

        return [self.message_repo.to_entity(m) for m in models]

    async def delete_message(
        self,
        message_id: str,
    ) -> bool:
        """刪除訊息.

        Args:
            message_id: 訊息 ID

        Returns:
            是否成功刪除
        """
        return await self.message_repo.delete(message_id)

    # === 佇列管理方法（已移至 Queue Management Methods 區塊）===
    # 舊的實作已移除，使用新的 create_queued_message, get_queued_messages 等方法

    # === 權限請求相關 ===

    async def create_permission_request(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        tool_use_id: Optional[str] = None,
        decision_type: str = "permission",
        options: Optional[List[Dict[str, Any]]] = None,
        raw_tool_call: Optional[Dict[str, Any]] = None,
        tool_call_id: Optional[str] = None,
    ) -> Message:
        """建立權限請求訊息.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID
            request_id: 請求 ID
            tool_name: 工具名稱
            tool_input: 工具輸入
            tool_use_id: Tool Use ID

        Returns:
            建立的權限請求訊息
        """
        message_id = str(uuid.uuid4())
        now = utcnow()

        # 取得下一個索引
        next_index = await self.message_repo.get_next_index(session_id)

        # 建立權限請求內容
        permission_content = {
            "request_id": request_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "decision_type": decision_type,
            "status": "pending",
        }
        if tool_use_id:
            permission_content["tool_use_id"] = tool_use_id
        if tool_call_id:
            permission_content["tool_call_id"] = tool_call_id
        if options is not None:
            permission_content["options"] = options
        if raw_tool_call is not None:
            permission_content["raw_tool_call"] = raw_tool_call

        data_blob: Dict[str, Any] = {
            "content": permission_content,
        }

        content_preview = f"Permission request: {tool_name}"

        model = await self.message_repo.create({
            "message_id": message_id,
            "created_at": now,
            "session_id": session_id,
            "task_id": task_id,
            "type": MessageType.PERMISSION_REQUEST.value,
            "role": MessageRole.SYSTEM.value,
            "index": next_index,
            "timestamp": now,
            "content_preview": content_preview,
            "data": self._json_dumps(data_blob),
        })

        # 更新 session 的 message_count
        await self.session_repo.increment_message_count(session_id)

        return self.message_repo.to_entity(model)

    async def update_permission_request(
        self,
        session_id: str,
        request_id: str,
        status: str,
        scope: Optional[str] = None,
        approved_by: Optional[str] = None,
        decision_type: Optional[str] = None,
        outcome: Optional[str] = None,
        option_id: Optional[str] = None,
        reason: Optional[str] = None,
        decision_content: Optional[str] = None,
    ) -> Optional[Message]:
        """更新權限請求狀態.

        Args:
            session_id: 會話 ID
            request_id: 請求 ID
            status: 新狀態
            scope: 權限範圍
            approved_by: 批准者

        Returns:
            更新後的訊息或 None
        """
        model = await self.message_repo.find_permission_request(session_id, request_id)
        if not model:
            return None

        # 反序列化 data (JSON 字符串 -> dict)
        data = self._json_loads(model.data)
        content = data.get("content", {})

        content["status"] = status
        if decision_type:
            content["decision_type"] = decision_type
        if outcome:
            content["outcome"] = outcome
        if option_id:
            content["option_id"] = option_id
        if scope:
            content["scope"] = scope
        if approved_by:
            content["approved_by"] = approved_by
            content["approved_at"] = utcnow().isoformat()
        if reason:
            content["reason"] = reason
        if decision_content is not None:
            content["content"] = decision_content

        data["content"] = content

        # 序列化後更新 (dict -> JSON 字符串)
        updated_model = await self.message_repo.update(model.message_id, {"data": self._json_dumps(data)})
        if not updated_model:
            return None

        return self.message_repo.to_entity(updated_model)

    # =====================================================
    # Queue Management Methods
    # =====================================================

    async def create_queued_message(
        self,
        session_id: str,
        prompt: str,
        metadata: Optional[Dict[str, Any]] = None,
        queued_by_user_id: Optional[str] = None,
    ) -> Message:
        """建立佇列訊息.

        Args:
            session_id: 會話 ID
            prompt: Prompt 內容
            metadata: 額外的 metadata
            queued_by_user_id: 建立此訊息的使用者 ID（用於認證保留）

        Returns:
            建立的 queued message entity
        """
        # 合併 metadata，加入認證資訊
        combined_metadata = metadata or {}
        if queued_by_user_id:
            combined_metadata["queued_by_user_id"] = queued_by_user_id
        combined_metadata["queued_at"] = utcnow().isoformat()

        model = await self.message_repo.create_queued(
            session_id=session_id,
            prompt=prompt,
            metadata=combined_metadata if combined_metadata else None,
        )
        return self.message_repo.to_entity(model)

    async def count_queued_messages(self, session_id: str) -> int:
        """計算 session 中的 queued messages 數量.

        Args:
            session_id: 會話 ID

        Returns:
            Queued messages 數量
        """
        return await self.message_repo.count_queued(session_id)

    async def get_queued_messages(self, session_id: str) -> List[Message]:
        """取得所有 queued messages.

        Args:
            session_id: 會話 ID

        Returns:
            Queued messages 列表
        """
        models = await self.message_repo.find_queued(session_id)
        return [self.message_repo.to_entity(m) for m in models]

    async def delete_queued_message(self, message_id: str) -> bool:
        """刪除 queued message.

        Args:
            message_id: 訊息 ID

        Returns:
            是否成功刪除
        """
        return await self.message_repo.delete_queued(message_id)

    # NOTE: 舊的別名方法 add_to_queue, get_queue 已移除
    # 直接使用 create_queued_message, get_queued_messages

    def _json_dumps(self, data: Dict[str, Any]) -> str:
        """將字典序列化為 JSON 字串（用於存入 TEXT 欄位）.

        會自動清理 NULL 字元 (\\x00)，因為 PostgreSQL TEXT 欄位不支援。

        Args:
            data: 要序列化的字典

        Returns:
            JSON 字串（已清理 NULL 字元）
        """
        json_str = json.dumps(data, ensure_ascii=False)
        # 清理 NULL 字元，避免 PostgreSQL 錯誤
        return json_str.replace('\x00', '')

    def _json_loads(self, data: Optional[str]) -> Dict[str, Any]:
        """將 JSON 字串反序列化為字典（從 TEXT 欄位讀取）.

        Args:
            data: JSON 字串或 None

        Returns:
            字典，如果 data 為 None 或解析失敗則返回空字典
        """
        if not data:
            return {}
        try:
            return json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON from database TEXT field",
                extra={
                    "error": str(e),
                    "data_length": len(data) if data else 0,
                    "data_preview": data[:100] if data else None,
                }
            )
            return {}

    def _get_content_preview(
        self,
        content: Union[str, List[Dict[str, Any]], Dict[str, Any]],
        max_length: int = 200,
    ) -> str:
        """取得內容預覽.

        Args:
            content: 訊息內容
            max_length: 最大長度

        Returns:
            內容預覽字串
        """
        if isinstance(content, str):
            return content[:max_length]

        if isinstance(content, list):
            # 找第一個 text block
            for block in content:
                if block.get("type") == "text":
                    text = block.get("text", "")
                    return text[:max_length]

        if isinstance(content, dict):
            # 可能是 PermissionRequestContent
            if "request_id" in content:
                return f"Permission request: {content.get('tool_name', '')}"
            if "text" in content:
                return content["text"][:max_length]

        return ""

    async def _update_session_title_from_first_message(
        self,
        session_id: str,
        content_preview: str,
        max_length: int = 50,
    ) -> None:
        """從第一個訊息更新 session title.

        Args:
            session_id: 會話 ID
            content_preview: 訊息內容預覽
            max_length: title 最大長度
        """
        # 檢查 session 是否已有 title
        session_model = await self.session_repo.find_by_id(session_id)
        if not session_model:
            return

        session = self.session_repo.to_entity(session_model)
        if session.title:
            # 已有 title，不覆蓋
            return

        # 截斷並清理 title
        title = content_preview.strip()
        if len(title) > max_length:
            title = title[:max_length - 3] + "..."

        # 移除換行符
        title = title.replace("\n", " ").replace("\r", "")

        # 更新 session title
        if title:
            # 反序列化 data (JSON 字符串 -> dict)
            try:
                data = json.loads(session_model.data) if session_model.data else {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    "Failed to deserialize session data when updating title",
                    extra={
                        "error": str(e),
                        "session_id": session_id,
                    }
                )
                data = {}
            data["title"] = title
            # 序列化後更新 (dict -> JSON 字符串，清理 NULL 字元)
            json_str = json.dumps(data, ensure_ascii=False).replace('\x00', '')
            await self.session_repo.update(session_id, {"data": json_str})

            # 發送 WebSocket 事件通知前端更新 session 列表
            await self.emitter.emit_session_patched(
                session_id,
                {
                    "session_id": session_id,
                    "title": title,
                    "workspace_id": session.workspace_id,
                }
            )


__all__ = [
    "MessageService",
    "MessageServiceError",
]
