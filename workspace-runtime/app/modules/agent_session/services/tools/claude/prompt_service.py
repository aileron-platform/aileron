"""
Claude Prompt Service.

Handles real-time execution of Claude sessions.
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

    Handles real-time execution of Claude sessions.

    Stateless: does not hold DB sessions; all DB operations use short-lived sessions.
    """

    # Configuration constants
    ENABLE_TOKEN_STREAMING = True
    IDLE_TIMEOUT_MS = 300000  # 5 minutes - Tool execution can keep the SDK silent for a while.

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Prompt Service.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key

        # Query builder
        self.query_builder = QueryBuilder(api_key=api_key)

        # Track active clients (for interruption)
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

        Generate complete assistant messages and text fragments.
        Enable real-time typewriter effect.

        Args:
            session_id: Session ID
            prompt: User prompt
            task_id: Task ID (optional)

        Yields:
            ProcessedEvent: Processed event
        """
        # Get session (check if sdk_session_id exists) - short-lived session
        async with async_session_scope() as db:
            session_repo = AgentSessionRepository(db)
            session_model = await session_repo.find_by_id(session_id)
            if not session_model:
                raise ValueError(f"Session not found: {session_id}")
            session = session_repo.to_entity(session_model)

        existing_sdk_session_id = session.sdk_session_id
        
        # Create SDK options
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
        
        # Create message processor
        processor = SDKMessageProcessor(
            ProcessorOptions(
                session_id=session_id,
                existing_sdk_session_id=existing_sdk_session_id,
                enable_token_streaming=self.ENABLE_TOKEN_STREAMING,
                idle_timeout_ms=self.IDLE_TIMEOUT_MS,
            )
        )
        
        # Create Claude SDK Client
        client = ClaudeSDKClient(options=options)

        # Store client reference (for interruption and permission mode switching)
        self.active_clients[session_id] = client

        try:
            # Create streaming client first, then send prompt.
            # When can_use_tool exists, still need to use AsyncIterable prompt;
            # Other cases follow official recommended connect() + query(str) path.
            await client.connect()
            await self._send_prompt(client, prompt, can_use_tool)
            
            # Receive messages (use asyncio.wait to wait for messages and abort event simultaneously)
            should_break = False
            try:
                # Get async iterator
                msg_iterator = client.receive_messages().__aiter__()

                while True:
                    # Check if stop requested (check before starting to wait)
                    if abort_event and abort_event.is_set():
                        yield await self._interrupt_and_stop(
                            client,
                            session_id,
                            "Abort detected before next message",
                        )
                        return

                    # Create task to wait for next message
                    msg_task = asyncio.create_task(msg_iterator.__anext__())

                    # Create task to wait for abort event (if abort_event provided)
                    abort_task = asyncio.create_task(abort_event.wait()) if abort_event else None

                    try:
                        # Use asyncio.wait for parallel waiting, return when either completes
                        tasks_to_wait = [msg_task]
                        if abort_task:
                            tasks_to_wait.append(abort_task)

                        done, pending = await asyncio.wait(
                            tasks_to_wait,
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        # Cancel unfinished task
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except (asyncio.CancelledError, StopAsyncIteration):
                                pass

                        # Check if abort event completed
                        if abort_task and abort_task in done:
                            yield await self._interrupt_and_stop(
                                client,
                                session_id,
                                "Abort event triggered",
                            )
                            return

                        # Message arrived
                        if msg_task in done:
                            try:
                                msg = msg_task.result()
                            except StopAsyncIteration:
                                # Iteration ended
                                break

                            # Check timeout
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

                            # Process message
                            events = await processor.process(msg)

                            # Process each event
                            for event in events:
                                yield event

                                # If EndEvent received, conversation ended
                                if isinstance(event, EndEvent):
                                    should_break = True
                                    break

                            # Break outer loop
                            if should_break:
                                break

                    except asyncio.CancelledError:
                        # Task cancelled, possibly due to abort
                        logger.debug("Task cancelled for session %s", session_id[:8])
                        yield StoppedEvent()
                        return

            except StopAsyncIteration:
                # Normal completion
                pass
            except Exception as e:
                # Catch AbortError and handle gracefully
                error_name = type(e).__name__
                error_msg = str(e).lower()
                if 'abort' in error_name.lower() or 'abort' in error_msg or 'cancel' in error_msg or 'interrupt' in error_msg:
                    logger.debug("Query aborted for session %s - this is expected", session_id[:8])
                    yield StoppedEvent()
                    return  # Clean exit, no error raised
                # Re-raise other errors
                raise

        finally:
            # Clean up client reference (but don't disconnect here, let external call to cleanup_client)
            # Note: Don't call client.disconnect() inside generator as it causes
            # "Attempted to exit cancel scope in a different task" error
            # Instead, claude_tool.py calls cleanup_client() outside generator
            pass

    async def cleanup_client(self, session_id: str) -> None:
        """
        Clean up session-related SDK client and processes.

        Must be called outside generator (avoid anyio context issues).
        This terminates Claude CLI process and all related MCP service processes.

        Args:
            session_id: Session ID
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
