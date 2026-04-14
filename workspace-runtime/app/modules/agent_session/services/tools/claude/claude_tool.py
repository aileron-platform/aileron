"""
Claude Code Tool Implementation.

比照 agor-main 的 claude-tool.ts

目前能力：
- ✅ 即時執行（透過 Anthropic SDK）
- ✅ 權限請求 UI（透過 can_use_tool 回調）
- ❌ 匯入 sessions（等待 SDK）
- ❌ 建立新 sessions（等待 SDK）
"""

import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from claude_agent_sdk.types import (
    CanUseTool,
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

from app.database import async_session_scope
from app.modules.agent_session.domain.enums import MessageRole, PermissionMode
from app.modules.agent_session.repositories.message_repository import MessageRepository
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.tools.base.streaming_callbacks import (
    StreamingCallbacks,
)
from app.modules.agent_session.services.tools.base.tool_interface import ITool
from app.modules.agent_session.services.tools.base.types import (
    CompleteEvent,
    PartialEvent,
    ResultEvent,
    TaskResult,
    ThinkingCompleteEvent,
    ThinkingPartialEvent,
    ToolCapabilities,
    ToolType,
    TokenUsage,
)
from .message_builder import create_assistant_message, create_user_message, create_tool_result_message, create_system_message
from .prompt_service import ClaudePromptService
from .permission_hooks import PermissionHooks
from app.modules.agent_session.services.tool_decision_manager import (
    global_tool_decision_manager,
)


def _build_message_dict(msg_entity) -> Dict[str, Any]:
    """將訊息實體轉為前端期望的 dict 格式."""
    content_blocks: list = []
    if isinstance(msg_entity.content, str):
        content_blocks = [{"type": "text", "text": msg_entity.content}]
    elif isinstance(msg_entity.content, list):
        content_blocks = msg_entity.content

    return {
        "message_id": msg_entity.id,
        "session_id": msg_entity.session_id,
        "task_id": msg_entity.task_id,
        "type": msg_entity.type.value if hasattr(msg_entity.type, "value") else msg_entity.type,
        "role": msg_entity.role.value if hasattr(msg_entity.role, "value") else msg_entity.role,
        "index": msg_entity.index,
        "content_blocks": content_blocks,
        "metadata": msg_entity.metadata,
        "created_at": msg_entity.created_at.isoformat() if msg_entity.created_at else None,
    }


class ClaudeTool(ITool):
    """
    Claude Code Tool.

    比照 agor-main 的 ClaudeTool 實作。

    無狀態：不持有 DB session，每個 DB 操作使用短期 session
    （透過 async_session_scope），避免長時間執行任務時佔用連線池。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        初始化 Claude Tool.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key

        # 建立 prompt service（無狀態）
        self.prompt_service = ClaudePromptService(api_key=api_key)

        # 追蹤每個 session 的 abort event（用於中止任務）
        self.abort_events: dict[str, asyncio.Event] = {}
    
    @property
    def tool_type(self) -> ToolType:
        """Tool 類型."""
        return ToolType.CLAUDE_CODE
    
    @property
    def name(self) -> str:
        """Tool 名稱."""
        return "Claude Code"
    
    def get_capabilities(self) -> ToolCapabilities:
        """取得 Tool 能力."""
        return ToolCapabilities(
            # 基本能力
            streaming=True,
            thinking=True,
            multimodal=False,
            max_context_window=200000,
            prompt_caching=True,
            local_execution=True,
            built_in_tools=["file_operations", "git", "shell"],
            # 進階能力
            supports_session_import=False,  # 等待 SDK
            supports_session_create=False,  # 等待 SDK
            supports_live_execution=True,  # ✅ 支援
            supports_session_fork=False,
            supports_child_spawn=False,
            supports_git_state=False,
        )
    
    async def check_installed(self) -> bool:
        """檢查是否已安裝."""
        # Claude Agent SDK 是 Python package，只要能 import 就算已安裝
        try:
            import claude_agent_sdk
            return True
        except ImportError:
            return False
    
    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        """
        執行任務（發送 prompt）WITH 實時串流.

        建立使用者訊息，從 Claude 串流回應片段，然後建立完整的助手訊息。
        在訊息生成期間呼叫 streamingCallbacks 以實現實時 UI 更新。
        Agent SDK 可能返回多個助手訊息（例如，工具調用，然後回應）。

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            task_id: 任務 ID（可選）
            permission_mode: 權限模式（Claude Code 原生模式）
            streaming_callbacks: 串流回調（可選）

        Returns:
            TaskResult: 任務結果
        """
        # 取得下一個訊息索引並建立使用者訊息（短期 session）
        async with async_session_scope() as db:
            message_repo = MessageRepository(db)
            message_service = MessageService(db)
            existing_messages = await message_repo.find_by_session(session_id)
            next_index = len(existing_messages)

            user_message = await create_user_message(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                index=next_index,
                message_service=message_service,
            )
            # session 在 context 結束時自動 commit

        # 通知回調（發送 WebSocket 事件）
        if streaming_callbacks:
            await streaming_callbacks.on_message_created(user_message)

        next_index += 1
        
        # 執行 prompt（透過 Agent SDK，帶串流）
        assistant_message_ids: list[str] = []
        captured_agent_session_id: Optional[str] = None
        resolved_model: Optional[str] = None
        
        # Stream Separation Pattern（選項 C）
        current_text_message_id: Optional[str] = None
        current_thinking_message_id: Optional[str] = None
        
        stream_start_time = time.time()
        token_usage: Optional[TokenUsage] = None
        duration_ms: Optional[int] = None
        raw_sdk_response: Optional[dict] = None
        was_stopped = False

        # 設置權限回調（根據 Claude SDK 原生權限模式）
        can_use_tool_callback: Optional[CanUseTool] = None
        permission_hooks: Optional[PermissionHooks] = None

        # 決定使用的權限模式：優先使用參數傳入的，否則從 session 取得
        effective_permission_mode: Optional[PermissionMode] = permission_mode
        if not effective_permission_mode:
            async with async_session_scope() as db:
                session_repo = AgentSessionRepository(db)
                session_model = await session_repo.find_by_id(session_id)
                if session_model:
                    session = session_repo.to_entity(session_model)
                    if session.permission_config:
                        effective_permission_mode = session.permission_config.mode

        # 根據權限模式決定是否需要權限回調
        # - DEFAULT: 每個工具都提示（最嚴格）
        # - ACCEPT_EDITS: 自動接受編輯，其他工具提示
        # - BYPASS_PERMISSIONS: 允許所有操作（不提示），但仍需攔截 AskUserQuestion 等用戶輸入工具
        # - PLAN: 計劃模式
        # 所有模式都需要權限回調，以支援 AskUserQuestion 等用戶輸入工具
        # PermissionHooks 內部會根據 permission_mode 決定是否自動允許非用戶輸入工具
        needs_permission_callback = effective_permission_mode is not None
        logger.info(
            "[PERMISSION] execute_task: session=%s, permission_mode=%s, effective=%s, needs_callback=%s, has_streaming=%s",
            session_id[:8], permission_mode, effective_permission_mode, needs_permission_callback,
            bool(streaming_callbacks),
        )

        if streaming_callbacks and hasattr(streaming_callbacks, 'emit_event') and needs_permission_callback:
            # 創建 PermissionHooks 實例
            permission_hooks = PermissionHooks(
                session_id=session_id,
                task_id=task_id or "",
                emit_event=streaming_callbacks.emit_event,
                permission_mode=effective_permission_mode.value if effective_permission_mode else None,
            )

            # 註冊到全域 PermissionManager（供 API endpoint 使用）
            global_tool_decision_manager.register_hooks(session_id, permission_hooks)

            # 使用 PermissionHooks 的 can_use_tool 作為回調
            can_use_tool_callback = permission_hooks.can_use_tool

        # 創建 abort event（用於中止任務）
        abort_event = asyncio.Event()
        self.abort_events[session_id] = abort_event

        # 迭代事件
        async for event in self.prompt_service.prompt_session_streaming(
            session_id=session_id,
            prompt=prompt,
            task_id=task_id,
            can_use_tool=can_use_tool_callback,
            abort_event=abort_event,
            permission_mode=effective_permission_mode,
        ):
            # 檢測是否提前停止
            if hasattr(event, 'type') and event.type == 'stopped':
                was_stopped = True
                continue

            # 捕獲 resolved model
            if isinstance(event, (CompleteEvent, PartialEvent)) and hasattr(event, 'resolved_model'):
                if event.resolved_model and not resolved_model:
                    resolved_model = event.resolved_model

            # 捕獲 raw SDK response（用於 token accounting）
            if isinstance(event, ResultEvent):
                raw_sdk_response = event.raw_sdk_message

                # 捕獲 SDK session_id 並保存到 session（用於對話接續）
                sdk_session_id = raw_sdk_response.get("session_id") if raw_sdk_response else None
                if sdk_session_id and not captured_agent_session_id:
                    captured_agent_session_id = sdk_session_id
                    # 保存到 session 實體（用於下次對話的 resume 參數）
                    async with async_session_scope() as db:
                        session_repo = AgentSessionRepository(db)
                        session_model = await session_repo.find_by_id(session_id)
                        if session_model:
                            # 反序列化 data (JSON 字符串 -> dict)
                            try:
                                data = json.loads(session_model.data) if session_model.data else {}
                            except (json.JSONDecodeError, TypeError) as e:
                                logger.error(
                                    "Failed to deserialize session data when saving sdk_session_id",
                                    extra={
                                        "error": str(e),
                                        "session_id": session_id,
                                    }
                                )
                                data = {}
                            data["sdk_session_id"] = sdk_session_id
                            # 序列化後更新 (dict -> JSON 字符串)
                            await session_repo.update(session_id, {"data": json.dumps(data, ensure_ascii=False)})

                if event.token_usage:
                    token_usage = event.token_usage

                    # 更新最後一個 assistant message 的 metadata（如果存在）
                    if assistant_message_ids:
                        last_message_id = assistant_message_ids[-1]
                        async with async_session_scope() as db:
                            message_repo = MessageRepository(db)
                            existing_model = await message_repo.find_by_id(last_message_id)
                            if existing_model:
                                # 反序列化 data (JSON 字符串 -> dict)
                                try:
                                    data = json.loads(existing_model.data) if existing_model.data else {}
                                except (json.JSONDecodeError, TypeError) as e:
                                    logger.error(
                                        "Failed to deserialize message data when updating token metadata",
                                        extra={
                                            "error": str(e),
                                            "message_id": last_message_id,
                                        }
                                    )
                                    data = {}
                                metadata = data.get("metadata", {}) or {}
                                metadata["tokens"] = {
                                    "input": token_usage.input,
                                    "output": token_usage.output,
                                }
                                if token_usage.cache_read is not None:
                                    metadata["tokens"]["cache_read"] = token_usage.cache_read
                                if token_usage.cache_creation is not None:
                                    metadata["tokens"]["cache_creation"] = token_usage.cache_creation

                                data["metadata"] = metadata

                                # 序列化後更新訊息 (dict -> JSON 字符串)
                                await message_repo.update(
                                    last_message_id,
                                    {"data": json.dumps(data, ensure_ascii=False)},
                                )

                if event.duration_ms:
                    duration_ms = event.duration_ms

            # 處理 thinking partial（串流）
            if isinstance(event, ThinkingPartialEvent):
                if streaming_callbacks and streaming_callbacks.on_thinking_chunk:
                    # 開始 thinking stream（如果需要）
                    if not current_thinking_message_id:
                        current_thinking_message_id = str(uuid4())
                        if streaming_callbacks.on_thinking_start:
                            await streaming_callbacks.on_thinking_start(
                                current_thinking_message_id,
                                metadata=None,
                            )

                    # 串流 thinking chunk
                    await streaming_callbacks.on_thinking_chunk(
                        current_thinking_message_id,
                        event.thinking_chunk,
                    )

            # 處理 thinking complete
            if isinstance(event, ThinkingCompleteEvent):
                if streaming_callbacks and streaming_callbacks.on_thinking_end:
                    if current_thinking_message_id:
                        await streaming_callbacks.on_thinking_end(current_thinking_message_id)

            # 處理 partial（串流文字）
            if isinstance(event, PartialEvent):
                if streaming_callbacks and streaming_callbacks.on_stream_chunk:
                    # 開始 text stream（如果需要）
                    if not current_text_message_id:
                        current_text_message_id = str(uuid4())
                        if streaming_callbacks.on_stream_start:
                            await streaming_callbacks.on_stream_start(current_text_message_id)

                    # 串流 text chunk
                    await streaming_callbacks.on_stream_chunk(
                        current_text_message_id,
                        event.text,
                    )

            # 處理 complete（完整訊息）
            if isinstance(event, CompleteEvent):
                # 結束串流
                if current_text_message_id and streaming_callbacks:
                    if streaming_callbacks.on_stream_end:
                        await streaming_callbacks.on_stream_end(current_text_message_id)
                    current_text_message_id = None

                if current_thinking_message_id and streaming_callbacks:
                    if streaming_callbacks.on_thinking_end:
                        await streaming_callbacks.on_thinking_end(current_thinking_message_id)
                    current_thinking_message_id = None

                # 建立訊息
                if event.role == MessageRole.ASSISTANT:
                    # 在短期 session 中建立訊息並準備通知 dict
                    msg_dict: Optional[Dict[str, Any]] = None
                    async with async_session_scope() as db:
                        message_repo = MessageRepository(db)
                        message_service = MessageService(db)
                        actual_message_id = await create_assistant_message(
                            session_id=session_id,
                            message_id=str(uuid4()),  # 未使用，由 MessageService 生成
                            content=event.content,
                            tool_uses=event.tool_uses,
                            task_id=task_id,
                            index=next_index,
                            resolved_model=resolved_model,
                            message_service=message_service,
                            parent_tool_use_id=event.parent_tool_use_id,
                            token_usage=token_usage,
                        )
                        if streaming_callbacks:
                            msg_model = await message_repo.find_by_id(actual_message_id)
                            if msg_model:
                                msg_entity = message_repo.to_entity(msg_model)
                                msg_dict = _build_message_dict(msg_entity)

                    # 通知前端（在 session 結束後）
                    if msg_dict and streaming_callbacks:
                        await streaming_callbacks.on_message_created(msg_dict)

                    next_index += 1
                    assistant_message_ids.append(actual_message_id)

                elif event.role == MessageRole.USER:
                    # 處理包含 tool_result 的 USER 訊息
                    # 檢查是否包含 tool_result（不是一般用戶輸入）
                    has_tool_result = any(
                        block.get("type") == "tool_result"
                        for block in event.content
                    )
                    if has_tool_result:
                        msg_dict = None
                        async with async_session_scope() as db:
                            message_repo = MessageRepository(db)
                            message_service = MessageService(db)
                            # 創建 tool_result 訊息
                            actual_message_id = await create_tool_result_message(
                                session_id=session_id,
                                content=event.content,
                                task_id=task_id,
                                index=next_index,
                                message_service=message_service,
                            )
                            if streaming_callbacks:
                                msg_model = await message_repo.find_by_id(actual_message_id)
                                if msg_model:
                                    msg_entity = message_repo.to_entity(msg_model)
                                    msg_dict = _build_message_dict(msg_entity)

                        # 通知前端
                        if msg_dict and streaming_callbacks:
                            await streaming_callbacks.on_message_created(msg_dict)

                        next_index += 1

                elif event.role == MessageRole.SYSTEM:
                    # 處理系統訊息（如 init）
                    msg_dict = None
                    actual_system_message_id: Optional[str] = None
                    try:
                        async with async_session_scope() as db:
                            message_repo = MessageRepository(db)
                            message_service = MessageService(db)
                            # 保存系統訊息到資料庫
                            actual_system_message_id = await create_system_message(
                                session_id=session_id,
                                content=event.content,
                                task_id=task_id,
                                index=next_index,
                                resolved_model=resolved_model,
                                message_service=message_service,
                            )
                            if streaming_callbacks:
                                msg_model = await message_repo.find_by_id(actual_system_message_id)
                                if msg_model:
                                    msg_entity = message_repo.to_entity(msg_model)
                                    msg_dict = _build_message_dict(msg_entity)
                    except Exception as e:
                        logger.error(
                            "Failed to create/commit system message: session_id=%s, task_id=%s, error=%s",
                            session_id[:8], task_id, str(e), exc_info=True
                        )
                        raise  # Re-raise to ensure the error propagates

                    # 通知前端
                    if streaming_callbacks:
                        try:
                            if msg_dict:
                                await streaming_callbacks.on_message_created(msg_dict)
                            else:
                                logger.warning(
                                    "System message created but not found for notification: message_id=%s, session_id=%s",
                                    actual_system_message_id, session_id[:8]
                                )
                        except Exception as e:
                            logger.error(
                                "Failed to notify frontend of system message: message_id=%s, session_id=%s, error=%s",
                                actual_system_message_id, session_id[:8], str(e), exc_info=True
                            )
                            # Continue execution - notification failure shouldn't stop task

                    next_index += 1

        # 清理 abort event
        self.abort_events.pop(session_id, None)

        # 清理 permission hooks
        if permission_hooks:
            global_tool_decision_manager.unregister_hooks(session_id)

        # 清理 SDK client 和進程（解決進程洩漏問題）
        # 必須在 generator 外部調用，避免 anyio context 問題
        await self.prompt_service.cleanup_client(session_id)

        # DEBUG: 追蹤 execute_task 返回
        logger.info(
            "[DEBUG] execute_task RETURN: session_id=%s, task_id=%s, was_stopped=%s, assistant_message_ids=%d, raw_sdk_response=%s",
            session_id[:8], task_id, was_stopped, len(assistant_message_ids),
            "has_data" if raw_sdk_response else "None"
        )

        return TaskResult(
            user_message_id=user_message["message_id"],
            assistant_message_ids=assistant_message_ids,
            token_usage=token_usage,
            duration_ms=duration_ms,
            agent_session_id=captured_agent_session_id,
            model=resolved_model,
            raw_sdk_response=raw_sdk_response,
            was_stopped=was_stopped,
        )

    async def stop_task(
        self,
        session_id: str,
        task_id: Optional[str] = None,
    ) -> dict:
        """
        停止目前執行的任務.

        使用 Claude Agent SDK 的原生 interrupt() 方法優雅地停止執行。

        Args:
            session_id: 會話 ID
            task_id: 任務 ID（可選）

        Returns:
            成功狀態和原因（如果失敗）
        """
        # 設定 abort_event（用於通知 prompt_service 的 asyncio.wait 循環）
        abort_event = self.abort_events.get(session_id)
        if abort_event:
            abort_event.set()

        # 嘗試中斷活動的 client
        client = self.prompt_service.active_clients.get(session_id)
        if client:
            try:
                # 調用 Claude SDK 的 interrupt() 方法
                await client.interrupt()
                return {"success": True}
            except Exception as e:
                # 即使 interrupt() 失敗，abort_event 已設定
                return {"success": True, "warning": str(e)}

        return {"success": True, "warning": "No active client found, but abort_event set"}

    async def set_permission_mode(self, session_id: str, mode: str) -> bool:
        """
        Dynamically change permission mode for an active session.

        Delegates to prompt_service which holds the active SDK client.
        Per SDK spec, mode can be: 'default', 'acceptEdits', 'bypassPermissions', 'plan'.

        Args:
            session_id: Session ID
            mode: New permission mode

        Returns:
            True if mode was changed successfully
        """
        return await self.prompt_service.set_permission_mode(session_id, mode)

    @classmethod
    def resolve_permission_decision(cls, session_id: str, decision: Dict[str, Any]) -> bool:
        """
        解決權限決策.

        這是一個類方法，供 API endpoint 調用來解決等待中的權限請求。
        使用全域 PermissionManager 來路由決策到正確的 PermissionHooks。

        Args:
            session_id: 會話 ID
            decision: 決策資料，包含 request_id, allow, scope 等

        Returns:
            是否成功解決
        """
        return global_tool_decision_manager.resolve_decision(session_id, decision)
