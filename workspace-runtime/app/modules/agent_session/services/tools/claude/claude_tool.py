"""
Claude Code Tool Implementation.

Current capabilities:
- ✅ Live execution (via Anthropic SDK)
- ✅ Permission request UI (via can_use_tool callback)
- ❌ Import sessions (waiting for SDK)
- ❌ Create new sessions (waiting for SDK)
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
    ToolAuthenticationError,
    TokenUsage,
)
from app.modules.agent_session.services.tools.base.message_builder import (
    create_assistant_message,
    create_system_message,
    create_tool_result_message,
    create_user_message,
)
from .prompt_service import ClaudePromptService
from .permission_hooks import PermissionHooks
from app.modules.agent_session.services.tool_decision_manager import (
    global_tool_decision_manager,
)


def _is_authentication_retry_event(content: list[dict[str, Any]]) -> bool:
    """Detect provider authentication failures reported as SDK retry system events."""
    for block in content:
        if block.get("type") != "system" or block.get("subtype") != "api_retry":
            continue
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        if data.get("error_status") == 401:
            return True
        error = data.get("error")
        if isinstance(error, str) and error.lower() in {
            "authentication_failed",
            "invalid_api_key",
            "unauthorized",
        }:
            return True
    return False


class ClaudeTool(ITool):
    """
    Claude Code Tool.

    Stateless: doesn't hold DB sessions, each DB operation uses short-lived session
    (via async_session_scope) to avoid occupying connection pool during long-running tasks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Claude Tool.

        Args:
            api_key: Anthropic API key
        """
        self.api_key = api_key

        # Create prompt service (stateless)
        self.prompt_service = ClaudePromptService(api_key=api_key)

        # Track abort event for each session (for task cancellation)
        self.abort_events: dict[str, asyncio.Event] = {}

    async def _persist_and_notify_message(
        self,
        session_id: str,
        content: list[dict[str, Any]],
        role: MessageRole,
        task_id: Optional[str],
        index: int,
        streaming_callbacks: Optional[StreamingCallbacks],
        resolved_model: Optional[str] = None,
        tool_uses: Optional[list[dict[str, Any]]] = None,
        parent_tool_use_id: Optional[str] = None,
        token_usage: Optional[TokenUsage] = None,
    ) -> str:
        """Persist one Claude SDK message and notify the frontend."""
        async with async_session_scope() as db:
            message_service = MessageService(db)
            if role == MessageRole.ASSISTANT:
                message = await create_assistant_message(
                    session_id=session_id,
                    content=content,
                    tool_uses=tool_uses,
                    task_id=task_id,
                    index=index,
                    resolved_model=resolved_model,
                    message_service=message_service,
                    source="claude-sdk",
                    parent_tool_use_id=parent_tool_use_id,
                    token_usage=token_usage,
                )
            elif role == MessageRole.USER:
                message = await create_tool_result_message(
                    session_id=session_id,
                    content=content,
                    task_id=task_id,
                    index=index,
                    message_service=message_service,
                    source="claude-sdk",
                )
            elif role == MessageRole.SYSTEM:
                message = await create_system_message(
                    session_id=session_id,
                    content=content,
                    task_id=task_id,
                    index=index,
                    resolved_model=resolved_model,
                    message_service=message_service,
                    source="claude-sdk",
                )
            else:
                raise ValueError(f"Unsupported Claude SDK message role: {role}")

        if streaming_callbacks:
            await streaming_callbacks.on_message_created(message)

        return message["message_id"]

    async def _update_last_message_token_usage(
        self,
        message_id: str,
        token_usage: TokenUsage,
    ) -> None:
        """Update token metadata on the latest persisted assistant message."""
        async with async_session_scope() as db:
            message_repo = MessageRepository(db)
            existing_model = await message_repo.find_by_id(message_id)
            if not existing_model:
                return

            try:
                data = json.loads(existing_model.data) if existing_model.data else {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    "Failed to deserialize message data when updating token metadata",
                    extra={
                        "error": str(e),
                        "message_id": message_id,
                    },
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
            await message_repo.update(message_id, {"data": json.dumps(data, ensure_ascii=False)})

    async def execute_task(
        self,
        session_id: str,
        prompt: str,
        task_id: Optional[str] = None,
        permission_mode: Optional[PermissionMode] = None,
        streaming_callbacks: Optional[StreamingCallbacks] = None,
    ) -> TaskResult:
        """
        Execute task (send prompt) WITH real-time streaming.

        Creates user message, streams response fragments from Claude, then creates complete assistant messages.
        Calls streamingCallbacks during message generation for real-time UI updates.
        Agent SDK may return multiple assistant messages (e.g., tool calls, then responses).

        Args:
            session_id: Session ID
            prompt: User prompt
            task_id: Task ID (optional)
            permission_mode: Permission mode (Claude Code native mode)
            streaming_callbacks: Streaming callbacks (optional)

        Returns:
            TaskResult: Task result
        """
        # Get next message index and create user message (short-lived session)
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
                source="claude-sdk",
            )
            # Session commits automatically when context exits

        # Notify callback (emit WebSocket event)
        if streaming_callbacks:
            await streaming_callbacks.on_message_created(user_message)

        next_index += 1

        # Execute prompt (via Agent SDK, with streaming)
        assistant_message_ids: list[str] = []
        captured_agent_session_id: Optional[str] = None
        resolved_model: Optional[str] = None

        # Stream Separation Pattern (Option C)
        current_text_message_id: Optional[str] = None
        current_thinking_message_id: Optional[str] = None
        
        stream_start_time = time.time()
        token_usage: Optional[TokenUsage] = None
        duration_ms: Optional[int] = None
        raw_sdk_response: Optional[dict] = None
        was_stopped = False
        saw_authentication_failure = False

        # Set up permission callback (based on Claude SDK native permission mode)
        can_use_tool_callback: Optional[CanUseTool] = None
        permission_hooks: Optional[PermissionHooks] = None

        # Determine which permission mode to use: prioritize parameter, otherwise get from session
        effective_permission_mode: Optional[PermissionMode] = permission_mode
        if not effective_permission_mode:
            async with async_session_scope() as db:
                session_repo = AgentSessionRepository(db)
                session_model = await session_repo.find_by_id(session_id)
                if session_model:
                    session = session_repo.to_entity(session_model)
                    if session.permission_config:
                        effective_permission_mode = session.permission_config.mode

        # Determine if permission callback is needed based on permission mode
        # - DEFAULT: Prompt for every tool (strictest)
        # - ACCEPT_EDITS: Auto-accept edits, prompt for other tools
        # - BYPASS_PERMISSIONS: Allow all operations (no prompting), but still intercept AskUserQuestion etc.
        # - PLAN: Plan mode
        # All modes need permission callback to support AskUserQuestion etc.
        # PermissionHooks internally decides whether to auto-allow non-user-input tools based on permission_mode
        needs_permission_callback = effective_permission_mode is not None
        logger.info(
            "[PERMISSION] execute_task: session=%s, permission_mode=%s, effective=%s, needs_callback=%s, has_streaming=%s",
            session_id[:8], permission_mode, effective_permission_mode, needs_permission_callback,
            bool(streaming_callbacks),
        )

        if streaming_callbacks and hasattr(streaming_callbacks, 'emit_event') and needs_permission_callback:
            # Create PermissionHooks instance
            permission_hooks = PermissionHooks(
                session_id=session_id,
                task_id=task_id or "",
                emit_event=streaming_callbacks.emit_event,
                permission_mode=effective_permission_mode.value if effective_permission_mode else None,
            )

            # Register to global PermissionManager (for API endpoint use)
            global_tool_decision_manager.register_hooks(session_id, permission_hooks)

            # Use PermissionHooks' can_use_tool as callback
            can_use_tool_callback = permission_hooks.can_use_tool

        # Create abort event (for task cancellation)
        abort_event = asyncio.Event()
        self.abort_events[session_id] = abort_event

        # Iterate events
        async for event in self.prompt_service.prompt_session_streaming(
            session_id=session_id,
            prompt=prompt,
            task_id=task_id,
            can_use_tool=can_use_tool_callback,
            abort_event=abort_event,
            permission_mode=effective_permission_mode,
        ):
            # Check if stopped early
            if hasattr(event, 'type') and event.type == 'stopped':
                was_stopped = True
                continue

            # Capture resolved model
            if isinstance(event, (CompleteEvent, PartialEvent)) and hasattr(event, 'resolved_model'):
                if event.resolved_model and not resolved_model:
                    resolved_model = event.resolved_model

            # Capture raw SDK response (for token accounting)
            if isinstance(event, ResultEvent):
                raw_sdk_response = event.raw_sdk_message

                # Capture SDK session_id and save to session (for conversation continuation)
                sdk_session_id = raw_sdk_response.get("session_id") if raw_sdk_response else None
                if sdk_session_id and not captured_agent_session_id:
                    captured_agent_session_id = sdk_session_id
                    async with async_session_scope() as db:
                        session_repo = AgentSessionRepository(db)
                        await session_repo.set_sdk_session_id(session_id, sdk_session_id)

                if event.token_usage:
                    token_usage = event.token_usage

                    # Update last assistant message's metadata (if exists)
                    if assistant_message_ids:
                        await self._update_last_message_token_usage(
                            assistant_message_ids[-1],
                            token_usage,
                        )

                if event.duration_ms:
                    duration_ms = event.duration_ms

            # Handle thinking partial (streaming)
            if isinstance(event, ThinkingPartialEvent):
                if streaming_callbacks and streaming_callbacks.on_thinking_chunk:
                    # Start thinking stream (if needed)
                    if not current_thinking_message_id:
                        current_thinking_message_id = str(uuid4())
                        if streaming_callbacks.on_thinking_start:
                            await streaming_callbacks.on_thinking_start(
                                current_thinking_message_id,
                                metadata=None,
                            )

                    # Stream thinking chunk
                    await streaming_callbacks.on_thinking_chunk(
                        current_thinking_message_id,
                        event.thinking_chunk,
                    )

            # Handle thinking complete
            if isinstance(event, ThinkingCompleteEvent):
                if streaming_callbacks and streaming_callbacks.on_thinking_end:
                    if current_thinking_message_id:
                        await streaming_callbacks.on_thinking_end(current_thinking_message_id)

            # Handle partial (streaming text)
            if isinstance(event, PartialEvent):
                if streaming_callbacks and streaming_callbacks.on_stream_chunk:
                    # Start text stream (if needed)
                    if not current_text_message_id:
                        current_text_message_id = str(uuid4())
                        if streaming_callbacks.on_stream_start:
                            await streaming_callbacks.on_stream_start(current_text_message_id)

                    # Stream text chunk
                    await streaming_callbacks.on_stream_chunk(
                        current_text_message_id,
                        event.text,
                    )

            # Handle complete (complete message)
            if isinstance(event, CompleteEvent):
                if event.role == MessageRole.SYSTEM and _is_authentication_retry_event(event.content):
                    saw_authentication_failure = True

                # End streaming
                if current_text_message_id and streaming_callbacks:
                    if streaming_callbacks.on_stream_end:
                        await streaming_callbacks.on_stream_end(current_text_message_id)
                    current_text_message_id = None

                if current_thinking_message_id and streaming_callbacks:
                    if streaming_callbacks.on_thinking_end:
                        await streaming_callbacks.on_thinking_end(current_thinking_message_id)
                    current_thinking_message_id = None

                if saw_authentication_failure:
                    break

                # Create message
                if event.role == MessageRole.ASSISTANT:
                    actual_message_id = await self._persist_and_notify_message(
                        session_id=session_id,
                        content=event.content,
                        role=MessageRole.ASSISTANT,
                        task_id=task_id,
                        index=next_index,
                        streaming_callbacks=streaming_callbacks,
                        resolved_model=resolved_model,
                        tool_uses=event.tool_uses,
                        parent_tool_use_id=event.parent_tool_use_id,
                        token_usage=token_usage,
                    )
                    next_index += 1
                    assistant_message_ids.append(actual_message_id)

                elif event.role == MessageRole.USER:
                    # Handle USER messages containing tool_result
                    # Check if contains tool_result (not normal user input)
                    has_tool_result = any(
                        block.get("type") == "tool_result"
                        for block in event.content
                    )
                    if has_tool_result:
                        await self._persist_and_notify_message(
                            session_id=session_id,
                            content=event.content,
                            role=MessageRole.USER,
                            task_id=task_id,
                            index=next_index,
                            streaming_callbacks=streaming_callbacks,
                        )
                        next_index += 1

                elif event.role == MessageRole.SYSTEM:
                    # Handle system messages (e.g., init)
                    actual_system_message_id: Optional[str] = None
                    try:
                        actual_system_message_id = await self._persist_and_notify_message(
                            session_id=session_id,
                            content=event.content,
                            role=MessageRole.SYSTEM,
                            task_id=task_id,
                            index=next_index,
                            streaming_callbacks=streaming_callbacks,
                            resolved_model=resolved_model,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to create/commit system message: session_id=%s, task_id=%s, error=%s",
                            session_id[:8], task_id, str(e), exc_info=True
                        )
                        raise  # Re-raise to ensure the error propagates

                    next_index += 1

        # Cleanup abort event
        self.abort_events.pop(session_id, None)

        # Cleanup permission hooks
        if permission_hooks:
            global_tool_decision_manager.unregister_hooks(session_id)

        # Cleanup SDK client and process (fix process leak)
        # Must be called outside generator to avoid anyio context issues
        await self.prompt_service.cleanup_client(session_id)

        if saw_authentication_failure and not assistant_message_ids and raw_sdk_response is None:
            raise ToolAuthenticationError()

        # DEBUG: Track execute_task return
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
        Stop currently executing task.

        Uses Claude Agent SDK's native interrupt() method for graceful stop.

        Args:
            session_id: Session ID
            task_id: Task ID (optional)

        Returns:
            Success status and reason (if failed)
        """
        # Set abort_event (to notify prompt_service's asyncio.wait loop)
        abort_event = self.abort_events.get(session_id)
        if abort_event:
            abort_event.set()

        # Try interrupting active client
        client = self.prompt_service.active_clients.get(session_id)
        if client:
            try:
                # Call Claude SDK's interrupt() method
                await client.interrupt()
                return {"success": True}
            except Exception as e:
                # Even if interrupt() fails, abort_event is set
                return {"success": True, "warning": str(e)}

        return {"success": True, "warning": "No active client found, but abort_event set"}

    @classmethod
    def resolve_permission_decision(cls, session_id: str, decision: Dict[str, Any]) -> bool:
        """
        Resolve permission decision.

        This is a class method for API endpoint to call to resolve pending permission requests.
        Uses global PermissionManager to route decision to correct PermissionHooks.

        Args:
            session_id: Session ID
            decision: Decision data containing request_id, allow, scope, etc.

        Returns:
            Whether successfully resolved
        """
        return global_tool_decision_manager.resolve_decision(session_id, decision)
