"""
Claude Prompt Service.

比照 agor-main 的 prompt-service.ts
處理 Claude sessions 的即時執行。
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import CanUseTool

from app.database import async_session_scope
from app.modules.agent_session.domain.enums import PermissionMode
from app.modules.agent_session.repositories.agent_session_repository import AgentSessionRepository
from app.modules.agent_session.services.tools.base.types import ProcessedEvent, StoppedEvent, EndEvent
from .message_processor import ProcessorOptions, SDKMessageProcessor
from .query_builder import QueryBuilder, QueryOptions


class ClaudePromptService:
    """
    Claude Prompt Service.

    比照 agor-main 的 ClaudePromptService
    處理 Claude sessions 的即時執行。

    無狀態：不持有 DB session，所有 DB 操作使用短期 session。
    """

    # 配置常數
    ENABLE_TOKEN_STREAMING = True
    IDLE_TIMEOUT_MS = 300000  # 5 minutes — 工具執行期間（如 npx create-next-app）SDK 不會發送訊息，需要足夠的等待時間

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        初始化 Prompt Service.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key

        # Query builder
        self.query_builder = QueryBuilder(api_key=api_key)

        # 追蹤活動的 clients（用於中斷）
        self.active_clients: dict[str, ClaudeSDKClient] = {}

    def _prompt_as_stream(self, prompt: str) -> AsyncIterator[dict]:
        """Wrap a single prompt in the SDK streaming input format."""

        async def _stream() -> AsyncIterator[dict]:
            yield {
                "type": "user",
                "message": {"role": "user", "content": prompt},
                "parent_tool_use_id": None,
                "session_id": "default",
            }

        return _stream()

    async def _send_prompt(
        self,
        client: ClaudeSDKClient,
        prompt: str,
        can_use_tool: Optional[CanUseTool] = None,
    ) -> None:
        """Send prompt using the simplest SDK path compatible with current options."""
        if can_use_tool:
            await client.query(self._prompt_as_stream(prompt))
            return

        await client.query(prompt)

    async def _interrupt_and_stop(
        self,
        client: ClaudeSDKClient,
        session_id: str,
        reason: str,
    ) -> StoppedEvent:
        """Interrupt the active SDK client and convert errors to a stopped event."""
        logger.debug("%s for session %s", reason, session_id[:8])
        try:
            await client.interrupt()
        except Exception as interrupt_err:
            logger.warning("Interrupt call during stop: %s", interrupt_err)
        return StoppedEvent()
    
    async def prompt_session_streaming(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        can_use_tool: Optional[CanUseTool] = None,
        abort_event: Optional[asyncio.Event] = None,
        permission_mode: Optional[PermissionMode] = None,
    ) -> AsyncGenerator[ProcessedEvent, None]:
        """
        Prompt a session using Claude Agent SDK (streaming version).

        產生完整的助手訊息和文字片段。
        啟用實時打字機效果。

        Args:
            session_id: 會話 ID
            prompt: 使用者 prompt
            task_id: 任務 ID（可選）

        Yields:
            ProcessedEvent: 處理後的事件
        """
        # 取得 session（檢查是否存在 sdk_session_id）— 短期 session
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            session_model = await session_repo.find_by_id(session_id)
            if not session_model:
                raise ValueError(f"Session not found: {session_id}")
            session = session_repo.to_entity(session_model)

        existing_sdk_session_id = session.sdk_session_id
        
        # 建立 SDK options
        options = await self.query_builder.setup_query(
            session_id=session_id,
            prompt=prompt,
            options=QueryOptions(
                task_id=task_id,
                resume=True,
                can_use_tool=can_use_tool,
                permission_mode=permission_mode,
            ),
        )
        
        # 建立 message processor
        processor = SDKMessageProcessor(
            ProcessorOptions(
                session_id=session_id,
                existing_sdk_session_id=existing_sdk_session_id,
                enable_token_streaming=self.ENABLE_TOKEN_STREAMING,
                idle_timeout_ms=self.IDLE_TIMEOUT_MS,
            )
        )
        
        # 建立 Claude SDK Client
        client = ClaudeSDKClient(options=options)

        # 儲存 client reference（用於中斷和 permission mode 切換）
        self.active_clients[session_id] = client

        try:
            # 先建立 streaming client，再發送 prompt。
            # 有 can_use_tool 時仍需使用 AsyncIterable prompt；
            # 其餘情況走官方建議的 connect() + query(str) 路徑。
            await client.connect()
            await self._send_prompt(client, prompt, can_use_tool)
            
            # 接收訊息（使用 asyncio.wait 來同時等待訊息和中止事件）
            should_break = False
            try:
                # 取得 async iterator
                msg_iterator = client.receive_messages().__aiter__()

                while True:
                    # 檢查是否已請求停止（在開始等待前先檢查）
                    if abort_event and abort_event.is_set():
                        yield await self._interrupt_and_stop(
                            client,
                            session_id,
                            "Abort detected before next message",
                        )
                        return

                    # 創建等待下一個訊息的 task
                    msg_task = asyncio.create_task(msg_iterator.__anext__())

                    # 創建等待中止事件的 task（如果有提供 abort_event）
                    abort_task = asyncio.create_task(abort_event.wait()) if abort_event else None

                    try:
                        # 使用 asyncio.wait 來並行等待，任一完成就返回
                        tasks_to_wait = [msg_task]
                        if abort_task:
                            tasks_to_wait.append(abort_task)

                        done, pending = await asyncio.wait(
                            tasks_to_wait,
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        # 取消未完成的 task
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except (asyncio.CancelledError, StopAsyncIteration):
                                pass

                        # 檢查是否是中止事件完成
                        if abort_task and abort_task in done:
                            yield await self._interrupt_and_stop(
                                client,
                                session_id,
                                "Abort event triggered",
                            )
                            return

                        # 是訊息到達
                        if msg_task in done:
                            try:
                                msg = msg_task.result()
                            except StopAsyncIteration:
                                # 迭代結束
                                break

                            # 檢查超時
                            if processor.has_timed_out():
                                state = processor.get_state()
                                idle_seconds = int((time.time() - state.last_activity_time))
                                timeout_seconds = int(state.idle_timeout_ms / 1000)

                                raise TimeoutError(
                                    f"Claude SDK idle timeout: No activity for {idle_seconds}s "
                                    f"(timeout: {timeout_seconds}s). "
                                    f"SDK may have hung or crashed. "
                                    f"Last message type was #{state.message_count}."
                                )

                            # 處理訊息
                            events = await processor.process(msg)

                            # 處理每個事件
                            for event in events:
                                yield event

                                # 如果收到 EndEvent，表示對話結束
                                if isinstance(event, EndEvent):
                                    should_break = True
                                    break

                            # 跳出外層循環
                            if should_break:
                                break

                    except asyncio.CancelledError:
                        # Task 被取消，可能是因為中止
                        logger.debug("Task cancelled for session %s", session_id[:8])
                        yield StoppedEvent()
                        return

            except StopAsyncIteration:
                # 正常結束
                pass
            except Exception as e:
                # 參考 agor: 捕獲 AbortError 並優雅處理
                error_name = type(e).__name__
                error_msg = str(e).lower()
                if 'abort' in error_name.lower() or 'abort' in error_msg or 'cancel' in error_msg or 'interrupt' in error_msg:
                    logger.debug("Query aborted for session %s - this is expected", session_id[:8])
                    yield StoppedEvent()
                    return  # 乾淨退出，不拋出錯誤
                # 其他錯誤重新拋出
                raise

        finally:
            # 清理 client reference（但不在這裡 disconnect，由外部調用 cleanup_client）
            # 注意：不在 generator 內調用 client.disconnect()，因為會導致
            # "Attempted to exit cancel scope in a different task" 錯誤
            # 改由 claude_tool.py 在 generator 外部調用 cleanup_client()
            pass

    async def set_permission_mode(self, session_id: str, mode: str) -> bool:
        """
        Dynamically change permission mode for an active session.

        Per SDK spec, permission mode can be changed mid-streaming via
        set_permission_mode(). This method delegates to the active SDK client.

        Args:
            session_id: Session ID
            mode: New permission mode ('default', 'acceptEdits', 'bypassPermissions', 'plan')

        Returns:
            True if mode was changed, False if no active client found or not supported
        """
        client = self.active_clients.get(session_id)
        if not client:
            logger.warning(
                "Cannot set permission mode: no active client for session %s",
                session_id[:8],
            )
            return False

        set_mode_fn = getattr(client, 'set_permission_mode', None)
        if not callable(set_mode_fn):
            logger.warning(
                "SDK client does not support set_permission_mode for session %s",
                session_id[:8],
            )
            return False

        try:
            await set_mode_fn(mode)
            logger.info(
                "Permission mode changed to '%s' for session %s",
                mode, session_id[:8],
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to set permission mode for session %s: %s",
                session_id[:8], str(e),
            )
            return False

    async def cleanup_client(self, session_id: str) -> None:
        """
        清理 session 相關的 SDK client 和進程.

        必須在 generator 外部調用（避免 anyio context 問題）。
        這會終止 Claude CLI 進程和所有相關的 MCP 服務進程。

        Args:
            session_id: 會話 ID
        """
        client = self.active_clients.pop(session_id, None)
        if client:
            try:
                logger.info(
                    "[CLEANUP] Disconnecting SDK client for session: %s",
                    session_id[:8]
                )
                await client.disconnect()
                logger.info(
                    "[CLEANUP] SDK client disconnected successfully: %s",
                    session_id[:8]
                )
            except Exception as e:
                logger.error(
                    "[CLEANUP] Error disconnecting SDK client for session %s: %s",
                    session_id[:8], str(e),
                    exc_info=True
                )
