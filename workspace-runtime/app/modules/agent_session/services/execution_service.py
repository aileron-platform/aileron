"""
Execution Service (重構版).

比照 agor-main 的架構，使用 ITool 介面。
協調 Tool 執行、訊息持久化和 WebSocket 串流。
"""

import asyncio
import logging
from typing import Any, ClassVar, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_scope
from app.modules.agent_session.domain.enums import PermissionMode, TaskStatus
from app.modules.agent_session.repositories.message_repository import MessageRepository
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository
from app.modules.agent_session.repositories.task_repository import TaskRepository
from app.modules.agent_session.services.message_service import MessageService
from app.modules.agent_session.services.agent_session_service import AgentSessionService
from app.modules.agent_session.services.task_service import TaskService
from app.modules.agent_session.services.tools.base.streaming_callbacks import (
    StreamingCallbacks,
)
from app.modules.agent_session.services.tools.base.tool_interface import ITool
from app.modules.agent_session.services.tools.base.types import TaskResult
from app.modules.agent_session.services.tools.claude.claude_tool import ClaudeTool
from app.modules.agent_session.services.tools.claude.tool_manager import get_claude_tool_manager
from app.modules.agent_session.services.tools.acp.tool_manager import get_acp_tool_manager
from app.modules.agent_session.services.tools.base.types import ToolType
from app.modules.agent_session.websocket.events import EventEmitter, EventType, WebSocketEvent, get_event_emitter

logger = logging.getLogger(__name__)


class ExecutionServiceError(Exception):
    """Execution Service 錯誤."""
    pass


class WebSocketStreamingCallbacks:
    """
    WebSocket 串流回調實作.
    
    實作 StreamingCallbacks protocol，發送事件到 WebSocket。
    """
    
    def __init__(
        self,
        emitter: EventEmitter,
        session_id: str,
        task_id: str,
    ):
        """初始化回調."""
        self.emitter = emitter
        self.session_id = session_id
        self.task_id = task_id
    
    async def on_stream_start(self, message_id: str) -> None:
        """串流開始."""
        await self.emitter.emit(
            WebSocketEvent.streaming_start(
                self.session_id,
                self.task_id,
                {"message_id": message_id},
            )
        )
    
    async def on_stream_chunk(self, message_id: str, chunk: str) -> None:
        """串流文字區塊."""
        await self.emitter.emit(
            WebSocketEvent.streaming_chunk(
                self.session_id,
                self.task_id,
                chunk,
                is_partial=True,
                message_id=message_id,
            )
        )
    
    async def on_stream_end(self, message_id: str) -> None:
        """串流結束."""
        await self.emitter.emit(
            WebSocketEvent.streaming_end(
                self.session_id,
                self.task_id,
                {"message_id": message_id},
            )
        )
    
    async def on_thinking_start(
        self,
        message_id: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """思考開始."""
        await self.emitter.emit(
            WebSocketEvent.thinking_start(
                self.session_id,
                self.task_id,
                message_id=message_id,
            )
        )
    
    async def on_thinking_chunk(self, message_id: str, chunk: str) -> None:
        """思考區塊."""
        await self.emitter.emit(
            WebSocketEvent.thinking_chunk(
                self.session_id,
                self.task_id,
                chunk,
                is_partial=True,
                message_id=message_id,
            )
        )
    
    async def on_thinking_end(self, message_id: str) -> None:
        """思考結束."""
        await self.emitter.emit(
            WebSocketEvent.thinking_end(
                self.session_id,
                self.task_id,
                message_id=message_id,
            )
        )

    async def on_message_created(self, message: Dict[str, Any]) -> None:
        """訊息建立通知."""
        await self.emitter.emit(
            WebSocketEvent.message_created(
                session_id=self.session_id,
                message_id=message["message_id"],
                data=message,
                task_id=self.task_id,
            )
        )

    def emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """發送 WebSocket 事件.

        Args:
            event_name: 事件名稱
            data: 事件資料
        """
        import asyncio

        # 建立對應的 WebSocket 事件
        if event_name == "tool-decision:request":
            event = WebSocketEvent.tool_decision_request(
                session_id=data.get("session_id", self.session_id),
                task_id=data.get("task_id", self.task_id),
                request_id=data.get("request_id", ""),
                decision_type=data.get("decision_type", "permission"),
                options=data.get("options", []),
                tool_call=data.get("tool_call", {}),
                timeout=data.get("timeout", 60),
            )
        elif event_name == "tool-decision:approved":
            event = WebSocketEvent.tool_decision_approved(
                session_id=data.get("session_id", self.session_id),
                task_id=data.get("task_id", self.task_id),
                request_id=data.get("request_id", ""),
                scope=data.get("scope"),
            )
        elif event_name == "tool-decision:denied":
            event = WebSocketEvent.tool_decision_denied(
                session_id=data.get("session_id", self.session_id),
                task_id=data.get("task_id", self.task_id),
                request_id=data.get("request_id", ""),
                reason=data.get("reason"),
            )
        elif event_name == "tool-decision:timeout":
            event = WebSocketEvent.tool_decision_timeout(
                session_id=data.get("session_id", self.session_id),
                task_id=data.get("task_id", self.task_id),
                request_id=data.get("request_id", ""),
            )
        else:
            # 通用事件 - 嘗試將字符串轉換為 EventType
            try:
                event_type = EventType(event_name)
            except ValueError:
                logger.warning(f"Unknown event type: {event_name}, skipping")
                return
            event = WebSocketEvent(
                type=event_type,
                data=data,
                session_id=self.session_id,
                task_id=self.task_id,
            )

        # 使用 asyncio 來發送事件
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.emitter.emit(event))
            else:
                loop.run_until_complete(self.emitter.emit(event))
        except RuntimeError:
            # 沒有事件循環時，創建一個新的
            asyncio.run(self.emitter.emit(event))


class ExecutionService:
    """
    Execution Service.

    協調 Tool 執行、訊息持久化和 WebSocket 串流。
    比照 agor-main 的架構，使用 ITool 介面。
    """

    # Queue 數量限制
    MAX_QUEUE_SIZE: ClassVar[int] = 5

    # Queue 處理鎖（每個 session 一個，防止並發處理）
    _queue_processing_locks: ClassVar[Dict[str, asyncio.Lock]] = {}

    # Session 執行鎖（每個 session 一個，防止並發執行）
    _session_execution_locks: ClassVar[Dict[str, asyncio.Lock]] = {}

    @classmethod
    def cleanup_session_lock(cls, session_id: str) -> bool:
        """清理指定 session 的 queue 處理鎖.

        應該在 session 被刪除時調用。

        Args:
            session_id: 會話 ID

        Returns:
            是否成功清理（True 表示鎖存在且已清理）
        """
        if session_id in cls._queue_processing_locks:
            del cls._queue_processing_locks[session_id]
            logger.debug(f"Cleaned up queue processing lock for session {session_id}")
            return True
        return False

    @classmethod
    def _get_execution_lock(cls, session_id: str) -> asyncio.Lock:
        """獲取或創建 session 的執行鎖.

        Args:
            session_id: 會話 ID

        Returns:
            asyncio.Lock: session 專屬的執行鎖
        """
        if session_id not in cls._session_execution_locks:
            cls._session_execution_locks[session_id] = asyncio.Lock()
        return cls._session_execution_locks[session_id]

    @classmethod
    def cleanup_execution_lock(cls, session_id: str) -> None:
        """清理 session 的執行鎖.

        應該在 session 被刪除時調用。

        Args:
            session_id: 會話 ID
        """
        cls._session_execution_locks.pop(session_id, None)

    @classmethod
    def cleanup_stale_locks(cls, active_session_ids: set) -> int:
        """清理不再活躍的 session 的鎖.

        可定期調用以防止記憶體洩漏。

        Args:
            active_session_ids: 活躍的 session ID 集合

        Returns:
            清理的鎖數量
        """
        stale_sessions = set(cls._queue_processing_locks.keys()) - active_session_ids
        for session_id in stale_sessions:
            del cls._queue_processing_locks[session_id]

        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale queue processing locks")

        return len(stale_sessions)

    @classmethod
    def get_lock_count(cls) -> int:
        """取得目前的鎖數量（用於監控）."""
        return len(cls._queue_processing_locks)

    def __init__(self, db: AsyncSession):
        """初始化 Execution Service."""
        self.db = db

        # 建立 repositories
        self.message_repo = MessageRepository(db)
        self.session_repo = AgentSessionRepository(db)
        self.task_repo = TaskRepository(db)

        # 建立 services
        self.message_service = MessageService(db)
        self.session_service = AgentSessionService(db)
        self.task_service = TaskService(db)

        # 取得 event emitter
        self.emitter = get_event_emitter()

        # API key（從環境變數取得）
        import os
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

        # 使用全域 ClaudeToolManager / AcpToolManager 取得無狀態 Tool
        # 這些 Tool 不持有 DB session，可安全共享於所有 ExecutionService 實例
        tool_manager = get_claude_tool_manager()
        self.claude_tool = tool_manager.get_tool()

        acp_tool_manager = get_acp_tool_manager()
        self.acp_codex_tool = acp_tool_manager.get_tool(tool_type=ToolType.CODEX)
        self.acp_gemini_tool = acp_tool_manager.get_tool(tool_type=ToolType.GEMINI)
        self.acp_opencode_tool = acp_tool_manager.get_tool(tool_type=ToolType.OPENCODE)

        # Tool registry（未來支援多 SDK）
        self.tools: dict[str, ITool] = {
            "claude-code": self.claude_tool,
            "codex": self.acp_codex_tool,
            "gemini": self.acp_gemini_tool,
            "opencode": self.acp_opencode_tool,
        }

        # 追蹤活躍執行
        self._active_executions: dict[str, asyncio.Task] = {}
    
    def get_tool(self, tool_type: str) -> ITool:
        """
        取得 Tool.

        Args:
            tool_type: Tool 類型

        Returns:
            ITool: Tool 實例
        """
        tool = self.tools.get(tool_type)
        if not tool:
            raise ValueError(f"Unknown tool type: {tool_type}")
        return tool

    async def execute_prompt(
        self,
        session_id: str,
        prompt: str,
        stream: bool = True,
        thinking_mode: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        permission_mode: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        context_files: Optional[List[str]] = None,
        tool_type: str = "claude-code",
        automation_execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        執行 prompt（帶串流）.

        如果 session 正在執行中，會將 prompt 加入 queue。

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            stream: 是否串流
            thinking_mode: 思考模式
            thinking_budget: 思考預算
            permission_mode: 權限模式
            images: 圖片列表
            context_files: 上下文文件列表
            tool_type: Tool 類型
            automation_execution_id: 自動化執行 ID（用於完成通知）

        Returns:
            執行結果包含 task_id 和狀態，或 queued 狀態
        """
        logger.info(f"execute_prompt called: session_id={session_id}, prompt={prompt[:50]}")

        # 1. 獲取 session 執行鎖
        lock = self._get_execution_lock(session_id)

        # 2. 檢查鎖狀態，如果已被佔用則直接加入 queue
        if lock.locked():
            logger.warning(
                "Session %s already has an active execution, queueing message",
                session_id[:8]
            )
            # 檢查 queue 數量限制
            queued_count = await self.message_service.count_queued_messages(session_id)
            if queued_count >= self.MAX_QUEUE_SIZE:
                logger.warning(f"Queue full for session {session_id}: {queued_count}/{self.MAX_QUEUE_SIZE}")
                raise ExecutionServiceError(
                    f"Queue is full. Maximum {self.MAX_QUEUE_SIZE} messages allowed. "
                    f"Please wait for current tasks to complete."
                )

            queued_msg = await self.message_service.create_queued_message(
                session_id=session_id,
                prompt=prompt,
            )

            # 發送 WebSocket 事件通知前端
            await self.emitter.emit(
                WebSocketEvent(
                    type=EventType.MESSAGES_QUEUED,
                    session_id=session_id,
                    task_id=None,
                    data={
                        "message_id": queued_msg.id,
                        "session_id": session_id,
                        "queue_position": queued_msg.queue_position,
                        "content_preview": prompt[:100],
                        "queued": True,
                    },
                )
            )

            return {
                "success": True,
                "task_id": None,
                "status": "queued",
                "streaming": False,
                "queued": True,
                "message_id": queued_msg.id,
                "queue_position": queued_msg.queue_position,
            }

        # 3. 獲取鎖並執行
        async with lock:
            return await self._execute_prompt_internal(
                session_id=session_id,
                prompt=prompt,
                stream=stream,
                thinking_mode=thinking_mode,
                thinking_budget=thinking_budget,
                permission_mode=permission_mode,
                images=images,
                context_files=context_files,
                tool_type=tool_type,
                automation_execution_id=automation_execution_id,
            )

    async def _execute_prompt_internal(
        self,
        session_id: str,
        prompt: str,
        stream: bool = True,
        thinking_mode: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        permission_mode: Optional[str] = None,
        images: Optional[List[Dict[str, Any]]] = None,
        context_files: Optional[List[str]] = None,
        tool_type: str = "claude-code",
        automation_execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """實際執行 prompt 的內部方法（在鎖保護下執行）."""
        # 1. 取得 session
        session = await self.session_service.get_session(session_id)
        if not session:
            raise ExecutionServiceError(f"Session not found: {session_id}")

        # 依 session 的 agentic_tool 決定實際 tool 類型
        tool_type = session.agentic_tool.value

        # 2. 檢查是否有 active tasks
        active_tasks = await self.task_service.get_active_tasks(session_id)
        logger.info(f"Session {session_id} active tasks count: {len(active_tasks)}")

        if active_tasks:
            # 有 active task，建立 queued message
            logger.info(f"Session {session_id} has active tasks, queueing prompt")

            # 檢查 queue 數量限制
            queued_count = await self.message_service.count_queued_messages(session_id)
            if queued_count >= self.MAX_QUEUE_SIZE:
                logger.warning(f"Queue full for session {session_id}: {queued_count}/{self.MAX_QUEUE_SIZE}")
                raise ExecutionServiceError(
                    f"Queue is full. Maximum {self.MAX_QUEUE_SIZE} messages allowed. "
                    f"Please wait for current tasks to complete."
                )

            queued_msg = await self.message_service.create_queued_message(
                session_id=session_id,
                prompt=prompt,
            )

            # 發送 WebSocket 事件通知前端
            await self.emitter.emit(
                WebSocketEvent(
                    type=EventType.MESSAGES_QUEUED,
                    session_id=session_id,
                    task_id=None,
                    data={
                        "message_id": queued_msg.id,
                        "session_id": session_id,  # 供前端過濾使用
                        "queue_position": queued_msg.queue_position,
                        "content_preview": prompt[:100],  # 前端期望 content_preview
                        "queued": True,
                    },
                )
            )

            return {
                "success": True,
                "task_id": None,  # Queued message 沒有 task_id
                "status": "queued",
                "streaming": False,
                "queued": True,
                "message_id": queued_msg.id,
                "queue_position": queued_msg.queue_position,
            }

        # 3. 沒有 active task，正常執行
        #
        # 重要：task 必須先在獨立交易中 commit，背景執行使用新的 DB session
        # 才能查到該 task。否則在 request transaction 尚未提交前，
        # 背景 coroutine 會先寫入綁定 task_id 的 message，觸發 FK violation。
        async with async_session_scope() as db:
            committed_task_service = TaskService(db, emitter=self.emitter)
            task = await committed_task_service.create_task(
                session_id=session_id,
                full_prompt=prompt,
                created_by="anonymous",
            )
            task_id = task.id

            # 將任務標記為執行中，並同步廣播狀態
            await committed_task_service.start_task(task_id)

        # 發送 task:started 事件
        await self.emitter.emit_task_started(
            session_id=session_id,
            task_id=task_id,
            prompt=prompt,
        )

        # 4. 在背景執行
        logger.info(f"Creating background task for task_id={task_id}")
        execution_task = asyncio.create_task(
            self._execute_in_background(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                stream=stream,
                tool_type=tool_type,
                permission_mode=permission_mode,
                automation_execution_id=automation_execution_id,
            )
        )
        logger.info(f"Background task created")

        # 追蹤執行
        self._active_executions[task_id] = execution_task
        logger.info(f"Active executions: {len(self._active_executions)}")

        return {
            "success": True,
            "task_id": task_id,
            "status": "running",
            "streaming": stream,
        }

    async def _execute_in_background(
        self,
        session_id: str,
        prompt: str,
        task_id: str,
        stream: bool,
        tool_type: str,
        permission_mode: Optional[str] = None,
        automation_execution_id: Optional[str] = None,
    ) -> None:
        """在背景執行 prompt.

        Tool 為無狀態設計，每個 DB 操作都使用短期 session（透過
        async_session_scope）。任務完成後，再用一個短期 session 更新 task 狀態。
        這避免了長時間佔用 DB 連線池造成的殭屍連線問題。

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            task_id: 任務 ID
            stream: 是否串流
            tool_type: Tool 類型
            automation_execution_id: 自動化執行 ID（用於完成通知）
        """
        logger.info(f"Background task started for task_id={task_id}")
        tool: Optional[ITool] = None
        try:
            # 取得 Tool（無狀態，不需綁定 db）
            tool = self.get_tool(tool_type)

            # 建立串流回調
            streaming_callbacks = WebSocketStreamingCallbacks(
                emitter=self.emitter,
                session_id=session_id,
                task_id=task_id,
            ) if stream else None

            # 解析 permission_mode
            effective_pm = None
            if permission_mode:
                try:
                    effective_pm = PermissionMode(permission_mode)
                except ValueError:
                    pass

            # 執行任務（Tool 內部會自行管理短期 DB session）
            result = await tool.execute_task(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                streaming_callbacks=streaming_callbacks,
                permission_mode=effective_pm,
            )

            # DEBUG: 追蹤 execute_prompt 結果
            logger.info(
                "[DEBUG] execute_prompt result: task_id=%s, was_stopped=%s, assistant_count=%d, raw_sdk_response=%s",
                task_id[:8], result.was_stopped, len(result.assistant_message_ids),
                "has_data" if result.raw_sdk_response else "None"
            )

            # 更新 task 狀態（短期 session）
            if result.was_stopped:
                logger.info("[DEBUG] Task was stopped, calling stop_task: task_id=%s", task_id[:8])
                async with async_session_scope() as db:
                    task_service = TaskService(db)
                    await task_service.stop_task(task_id)
                # 發送 task:stopped 事件
                await self.emitter.emit_task_stopped(
                    session_id=session_id,
                    task_id=task_id,
                )
                # 發布 Redis 完成事件（如果有 automation_execution_id）
                if automation_execution_id:
                    await self._publish_automation_completed(
                        execution_id=automation_execution_id,
                        session_id=session_id,
                        status="stopped",
                        has_error=False,
                    )
            else:
                logger.info("[DEBUG] Task completed normally, calling complete_task: task_id=%s", task_id[:8])
                # 從 SDK 回應計算 context window
                computed_context_window = self._compute_context_window(result.raw_sdk_response)
                async with async_session_scope() as db:
                    task_service = TaskService(db)
                    completed_task = await task_service.complete_task(
                        task_id,
                        raw_sdk_response=result.raw_sdk_response,
                        computed_context_window=computed_context_window,
                    )
                logger.info("[DEBUG] complete_task finished successfully: task_id=%s", task_id[:8])
                completed_token_usage = None
                if completed_task and completed_task.raw_sdk_response:
                    token_usage = TaskService.extract_token_usage(completed_task.raw_sdk_response)
                    completed_token_usage = token_usage.to_dict() if token_usage else None
                # 發送 task:completed 事件
                await self.emitter.emit_task_completed(
                    session_id=session_id,
                    task_id=task_id,
                    duration_ms=completed_task.duration_ms if completed_task else None,
                    token_usage=completed_token_usage,
                )
                # 發布 Redis 完成事件（如果有 automation_execution_id）
                if automation_execution_id:
                    await self._publish_automation_completed(
                        execution_id=automation_execution_id,
                        session_id=session_id,
                        status="completed",
                        has_error=False,
                    )

        except Exception as e:
            logger.error(f"Error executing prompt: {e}", exc_info=True)
            # 在異常情況下，使用新的 session 更新 task 狀態
            try:
                async with async_session_scope() as db:
                    task_service = TaskService(db)
                    await task_service.fail_task(
                        task_id,
                        error_message=str(e),
                    )
            except TaskServiceError:
                logger.warning(
                    "Failed to mark task as failed because task is missing: %s",
                    task_id,
                    exc_info=True,
                )

            # 發送 task:failed 事件通知前端
            await self.emitter.emit_task_failed(
                session_id=session_id,
                task_id=task_id,
                error_message=str(e),
                error_code=type(e).__name__,
            )

            # 發送 streaming:error 事件（如果有串流進行中）
            await self.emitter.emit_streaming_error(
                session_id=session_id,
                task_id=task_id,
                error=str(e),
                code=type(e).__name__,
            )

            # 發布 Redis 失敗事件（如果有 automation_execution_id）
            if automation_execution_id:
                await self._publish_automation_completed(
                    execution_id=automation_execution_id,
                    session_id=session_id,
                    status="failed",
                    has_error=True,
                    error_message=str(e),
                )
        finally:
            # 清理 SDK client 和進程（確保異常情況下也會清理）
            # 這是雙重保險：正常流程在 claude_tool.py 清理，異常流程在這裡清理
            try:
                if tool is not None and hasattr(tool, 'prompt_service') and tool.prompt_service:
                    await tool.prompt_service.cleanup_client(session_id)
            except Exception as cleanup_error:
                logger.error(
                    f"Error cleaning up SDK client for session {session_id}: {cleanup_error}",
                    exc_info=True
                )

            # 清理
            self._active_executions.pop(task_id, None)

            # 觸發 queue 處理
            logger.info(f"Triggering queue processing for session {session_id}")
            asyncio.create_task(self._process_queue(session_id))

    async def _process_queue(self, session_id: str) -> None:
        """處理 queue 中的下一個 message.

        參考 agor 的實作：
        1. 取得或創建 session 專屬的 lock
        2. 非阻塞方式檢查 lock，如果已被鎖定則跳過
        3. 取得下一個 queued message
        4. 驗證 session 狀態
        5. 刪除 queued message 並發送事件
        6. 調用 execute_prompt（會創建新的 task 和 messages）

        注意：必須使用新的 DB session，避免與其他請求衝突。

        Args:
            session_id: 會話 ID
        """
        # 取得或創建 session 專屬的 lock
        if session_id not in self._queue_processing_locks:
            self._queue_processing_locks[session_id] = asyncio.Lock()

        lock = self._queue_processing_locks[session_id]

        # 非阻塞方式檢查 lock
        if lock.locked():
            logger.info(f"Queue processing already in progress for session {session_id}, skipping")
            return

        async with lock:
            await self._process_queue_internal(session_id)

    async def _process_queue_internal(self, session_id: str) -> None:
        """實際處理 queue 的內部方法（在 lock 保護下執行）."""
        # 暫存變數，用於錯誤處理
        next_msg = None
        next_msg_id = None
        queue_position = None
        prompt_content = None

        try:
            # 使用新的 DB session
            async with async_session_scope() as db:
                message_repo = MessageRepository(db)
                session_service = AgentSessionService(db)
                task_service = TaskService(db)
                message_service = MessageService(db)

                # 取得下一個 queued message
                next_msg_model = await message_repo.get_next_queued(session_id)

                if not next_msg_model:
                    logger.info(f"No queued messages for session {session_id}")
                    return

                # 轉換為 entity
                next_msg = message_repo.to_entity(next_msg_model)
                next_msg_id = next_msg.id
                queue_position = next_msg.queue_position

                # 再次確認 session 狀態（避免競態條件）
                session = await session_service.get_session(session_id)
                if not session:
                    logger.warning(f"Session {session_id} not found during queue processing")
                    return

                # 檢查是否還有 active tasks
                active_tasks = await task_service.get_active_tasks(session_id)
                if active_tasks:
                    logger.info(f"Session {session_id} still has active tasks, skipping queue processing")
                    return

                logger.info(f"Processing queued message {next_msg.id} (position {next_msg.queue_position})")

                # 提取 prompt 內容
                prompt_content = next_msg.content
                if isinstance(prompt_content, list):
                    # 如果是 content blocks，提取文字
                    prompt_content = " ".join([
                        block.get("text", "") for block in prompt_content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ])
                elif not isinstance(prompt_content, str):
                    prompt_content = str(prompt_content)

            # 在 DB session 外執行 prompt（會創建新的 session）
            # 注意：我們先執行，成功後才刪除 queued message
            # 創建新的 ExecutionService 實例以使用新的 DB session
            async with async_session_scope() as db:
                execution_service = ExecutionService(db)
                result = await execution_service.execute_prompt(
                    session_id=session_id,
                    prompt=prompt_content,
                    stream=True,
                )

                # 執行成功，現在刪除 queued message
                # 不需手動 commit：async_session_scope 會在 context 結束時自動 commit
                message_service = MessageService(db)
                await message_service.delete_queued_message(next_msg_id)

                # 發送 MESSAGE_DEQUEUED 事件通知前端
                await self.emitter.emit(
                    WebSocketEvent(
                        type=EventType.MESSAGE_DEQUEUED,
                        session_id=session_id,
                        task_id=None,
                        data={
                            "message_id": next_msg_id,
                            "queue_position": queue_position,
                            "reason": "processed",
                        },
                    )
                )

                logger.info(f"Successfully processed queued message {next_msg_id} for session {session_id}")

        except Exception as e:
            logger.error(
                f"Error processing queue for session {session_id}: {e}",
                exc_info=True
            )

            # 通知用戶 queue message 處理失敗
            if next_msg_id:
                await self.emitter.emit(
                    WebSocketEvent(
                        type=EventType.QUEUE_PROCESSING_FAILED,
                        session_id=session_id,
                        task_id=None,
                        data={
                            "message_id": next_msg_id,
                            "queue_position": queue_position,
                            "error_message": str(e),
                            "error_type": type(e).__name__,
                            "content_preview": prompt_content[:100] if prompt_content else None,
                        },
                    )
                )

                logger.error(
                    f"Queue message {next_msg_id} processing failed for session {session_id}. "
                    f"Message remains in queue for retry."
                )

    async def stop_task(
        self,
        session_id: str,
        task_id: str,
        tool_type: Optional[str] = None,
    ) -> dict:
        """
        停止任務.

        Args:
            session_id: 會話 ID
            task_id: 任務 ID
            tool_type: Tool 類型（未提供時使用 session.agentic_tool）

        Returns:
            停止結果
        """
        # 發送 task:stop_ack 事件 - 確認收到停止信號
        await self.emitter.emit_task_stop_ack(
            session_id=session_id,
            task_id=task_id,
        )

        resolved_tool_type = tool_type
        if not resolved_tool_type:
            session = await self.session_service.get_session(session_id)
            if not session:
                raise ExecutionServiceError(f"Session not found: {session_id}")
            resolved_tool_type = session.agentic_tool.value

        # 取得 Tool
        tool = self.get_tool(resolved_tool_type)

        # 停止任務
        result = await tool.stop_task(
            session_id=session_id,
            task_id=task_id,
        )

        return result

    @staticmethod
    def _compute_context_window(raw_sdk_response: Optional[Dict[str, Any]]) -> Optional[int]:
        """從 SDK 回應計算 context window 使用量.

        Context window 使用量 = input_tokens + output_tokens
        這代表當前對話在 context window 中佔用的 token 數量。

        Args:
            raw_sdk_response: SDK 原始回應

        Returns:
            Context window 使用量（tokens）或 None
        """
        if not raw_sdk_response:
            return None

        sdk_type = raw_sdk_response.get("type")
        response = raw_sdk_response.get("response", {})

        try:
            if sdk_type == "claude":
                usage = response.get("usage", {})
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                return input_tokens + output_tokens

            elif sdk_type == "codex":
                turn = response.get("turn", {})
                usage = turn.get("usage", {})
                # Codex 可能直接提供 total_tokens
                if "total_tokens" in usage:
                    return usage["total_tokens"]
                return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            elif sdk_type == "gemini":
                usage = response.get("usageMetadata", {})
                # Gemini 使用 totalTokenCount
                if "totalTokenCount" in usage:
                    return usage["totalTokenCount"]
                return usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)

            elif sdk_type == "opencode":
                usage = response.get("usage", {})
                # OpenCode 可能直接提供 total_tokens
                if "total_tokens" in usage:
                    return usage["total_tokens"]
                return usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)

        except (TypeError, AttributeError) as e:
            logger.warning(f"Failed to compute context window: {e}")
            return None

        return None

    async def _publish_automation_completed(
        self,
        execution_id: str,
        session_id: str,
        status: str,
        has_error: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """發布自動化執行完成事件到 Redis.

        Args:
            execution_id: 自動化執行 ID
            session_id: 會話 ID
            status: 執行狀態 (completed, failed, stopped)
            has_error: 是否有錯誤
            error_message: 錯誤訊息
        """
        try:
            from app.core.redis_publisher import get_redis_publisher

            # 取得 session 以獲取 workspace_id
            session = await self.session_service.get_session(session_id)
            workspace_id = session.workspace_id if session else "unknown"

            # 計算訊息總數（簡化版，使用 message_count）
            total_messages = session.message_count if session else 0

            publisher = get_redis_publisher()
            await publisher.publish_execution_completed(
                execution_id=execution_id,
                session_id=session_id,
                workspace_id=workspace_id,
                status=status,
                total_messages=total_messages,
                has_error=has_error,
                error_message=error_message,
            )
            logger.info(
                f"Published automation completed event: execution_id={execution_id}, "
                f"status={status}, has_error={has_error}"
            )
        except Exception as e:
            # 不影響主流程，只記錄錯誤
            logger.error(f"Failed to publish automation completed event: {e}", exc_info=True)
