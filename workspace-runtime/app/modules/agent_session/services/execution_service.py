"""
Execution Service.

Architected after agor-main using the ITool interface.
Coordinates tool execution, message persistence, and WebSocket streaming.
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
from app.modules.agent_session.services.task_service import TaskService, TaskServiceError
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
    """Execution Service error."""
    pass


class WebSocketStreamingCallbacks:
    """
    WebSocket streaming callbacks implementation.

    Implements StreamingCallbacks protocol to send events to WebSocket.
    """
    
    def __init__(
        self,
        emitter: EventEmitter,
        session_id: str,
        task_id: str,
    ):
        self.emitter = emitter
        self.session_id = session_id
        self.task_id = task_id

    async def on_stream_start(self, message_id: str) -> None:
        await self.emitter.emit(
            WebSocketEvent.streaming_start(
                self.session_id,
                self.task_id,
                {"message_id": message_id},
            )
        )
    
    async def on_stream_chunk(self, message_id: str, chunk: str) -> None:
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
        await self.emitter.emit(
            WebSocketEvent.thinking_start(
                self.session_id,
                self.task_id,
                message_id=message_id,
            )
        )
    
    async def on_thinking_chunk(self, message_id: str, chunk: str) -> None:
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
        await self.emitter.emit(
            WebSocketEvent.thinking_end(
                self.session_id,
                self.task_id,
                message_id=message_id,
            )
        )

    async def on_message_created(self, message: Dict[str, Any]) -> None:
        await self.emitter.emit(
            WebSocketEvent.message_created(
                session_id=self.session_id,
                message_id=message["message_id"],
                data=message,
                task_id=self.task_id,
            )
        )

    def emit_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Emit WebSocket event.

        Args:
            event_name: Event name
            data: Event data
        """
        import asyncio

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
            # Generic event - try converting string to EventType
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

        # Emit event using asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.emitter.emit(event))
            else:
                loop.run_until_complete(self.emitter.emit(event))
        except RuntimeError:
            # No event loop available, create a new one
            asyncio.run(self.emitter.emit(event))


class ExecutionService:
    """
    Execution Service.

    Coordinates tool execution, message persistence, and WebSocket streaming.
    Architected after agor-main using the ITool interface.
    """

    # Maximum queue size
    MAX_QUEUE_SIZE: ClassVar[int] = 5

    # Queue processing locks (one per session to prevent concurrent processing)
    _queue_processing_locks: ClassVar[Dict[str, asyncio.Lock]] = {}

    # Session execution locks (one per session to prevent concurrent execution)
    _session_execution_locks: ClassVar[Dict[str, asyncio.Lock]] = {}

    @classmethod
    def cleanup_session_lock(cls, session_id: str) -> bool:
        """Clean up queue processing lock for the specified session.

        Should be called when a session is deleted.

        Args:
            session_id: Session ID

        Returns:
            Whether cleanup succeeded (True means lock existed and was cleaned)
        """
        if session_id in cls._queue_processing_locks:
            del cls._queue_processing_locks[session_id]
            logger.debug(f"Cleaned up queue processing lock for session {session_id}")
            return True
        return False

    @classmethod
    def _get_execution_lock(cls, session_id: str) -> asyncio.Lock:
        """Get or create execution lock for the session.

        Args:
            session_id: Session ID

        Returns:
            asyncio.Lock: Session-specific execution lock
        """
        if session_id not in cls._session_execution_locks:
            cls._session_execution_locks[session_id] = asyncio.Lock()
        return cls._session_execution_locks[session_id]

    @classmethod
    def cleanup_execution_lock(cls, session_id: str) -> None:
        """Clean up execution lock for the session.

        Should be called when a session is deleted.

        Args:
            session_id: Session ID
        """
        cls._session_execution_locks.pop(session_id, None)

    @classmethod
    def cleanup_stale_locks(cls, active_session_ids: set) -> int:
        """Clean up locks for sessions that are no longer active.

        Can be called periodically to prevent memory leaks.

        Args:
            active_session_ids: Set of active session IDs

        Returns:
            Number of locks cleaned up
        """
        stale_sessions = set(cls._queue_processing_locks.keys()) - active_session_ids
        for session_id in stale_sessions:
            del cls._queue_processing_locks[session_id]

        if stale_sessions:
            logger.info(f"Cleaned up {len(stale_sessions)} stale queue processing locks")

        return len(stale_sessions)

    @classmethod
    def get_lock_count(cls) -> int:
        """Get current lock count (for monitoring)."""
        return len(cls._queue_processing_locks)

    def __init__(self, db: AsyncSession):
        """Initialize Execution Service."""
        self.db = db

        # Initialize repositories
        self.message_repo = MessageRepository(db)
        self.session_repo = AgentSessionRepository(db)
        self.task_repo = TaskRepository(db)

        # Initialize services
        self.message_service = MessageService(db)
        self.session_service = AgentSessionService(db)
        self.task_service = TaskService(db)

        # Get event emitter
        self.emitter = get_event_emitter()

        # API key (from environment variable)
        import os
        self.api_key = os.getenv("ANTHROPIC_API_KEY")

        # Use global ClaudeToolManager / AcpToolManager for stateless tools
        # These tools don't hold DB sessions, can be safely shared across all ExecutionService instances
        tool_manager = get_claude_tool_manager()
        self.claude_tool = tool_manager.get_tool()

        acp_tool_manager = get_acp_tool_manager()
        self.acp_codex_tool = acp_tool_manager.get_tool(tool_type=ToolType.CODEX)
        self.acp_gemini_tool = acp_tool_manager.get_tool(tool_type=ToolType.GEMINI)
        self.acp_opencode_tool = acp_tool_manager.get_tool(tool_type=ToolType.OPENCODE)

        # Tool registry (future multi-SDK support)
        self.tools: dict[str, ITool] = {
            "claude-code": self.claude_tool,
            "codex": self.acp_codex_tool,
            "gemini": self.acp_gemini_tool,
            "opencode": self.acp_opencode_tool,
        }

        # Track active executions
        self._active_executions: dict[str, asyncio.Task] = {}
    
    def get_tool(self, tool_type: str) -> ITool:
        """
        Get tool by type.

        Args:
            tool_type: Tool type

        Returns:
            ITool: Tool instance
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
        Execute prompt with streaming.

        If session is currently executing, prompt will be queued.

        Args:
            session_id: Session ID
            prompt: User prompt
            stream: Whether to stream
            thinking_mode: Thinking mode
            thinking_budget: Thinking budget
            permission_mode: Permission mode
            images: Image list
            context_files: Context file list
            tool_type: Tool type
            automation_execution_id: Automation execution ID (for completion notification)

        Returns:
            Execution result containing task_id and status, or queued status
        """
        logger.info(f"execute_prompt called: session_id={session_id}, prompt={prompt[:50]}")

        # 1. Get session execution lock
        lock = self._get_execution_lock(session_id)

        # 2. Check lock status, queue prompt if already locked
        if lock.locked():
            logger.warning(
                "Session %s already has an active execution, queueing message",
                session_id[:8]
            )
            # Check queue size limit
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

            # Emit WebSocket event to notify frontend
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
                        "status": "queued",
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

        # 3. Acquire lock and execute
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
                allow_queue=True,
            )

    async def execute_claimed_prompt(
        self,
        session_id: str,
        prompt: str,
        stream: bool = True,
        permission_mode: Optional[str] = None,
        automation_execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute claimed queued prompt, disallow re-queuing."""
        lock = self._get_execution_lock(session_id)
        if lock.locked():
            raise ExecutionServiceError(
                f"Session {session_id} is busy while dispatching queued message"
            )

        async with lock:
            return await self._execute_prompt_internal(
                session_id=session_id,
                prompt=prompt,
                stream=stream,
                permission_mode=permission_mode,
                automation_execution_id=automation_execution_id,
                allow_queue=False,
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
        allow_queue: bool = True,
    ) -> Dict[str, Any]:
        """Internal method that actually executes prompt (executes under lock protection)."""
        # 1. Get session
        session = await self.session_service.get_session(session_id)
        if not session:
            raise ExecutionServiceError(f"Session not found: {session_id}")

        # Determine actual tool type based on session's agentic_tool
        tool_type = session.agentic_tool.value

        # 2. Check for active tasks
        active_tasks = await self.task_service.get_active_tasks(session_id)
        logger.info(f"Session {session_id} active tasks count: {len(active_tasks)}")

        if active_tasks:
            if not allow_queue:
                raise ExecutionServiceError(
                    f"Session {session_id} has active task while dispatching queued message"
                )
            # Has active task, create queued message
            logger.info(f"Session {session_id} has active tasks, queueing prompt")

            # Check queue size limit
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

            # Emit WebSocket event to notify frontend
            await self.emitter.emit(
                WebSocketEvent(
                    type=EventType.MESSAGES_QUEUED,
                    session_id=session_id,
                    task_id=None,
                    data={
                        "message_id": queued_msg.id,
                        "session_id": session_id,  # For frontend filtering
                        "queue_position": queued_msg.queue_position,
                        "content_preview": prompt[:100],  # Frontend expects content_preview
                        "status": "queued",
                        "queued": True,
                    },
                )
            )

            return {
                "success": True,
                "task_id": None,  # Queued message has no task_id
                "status": "queued",
                "streaming": False,
                "queued": True,
                "message_id": queued_msg.id,
                "queue_position": queued_msg.queue_position,
            }

        # 3. No active task, execute normally
        #
        # Important: task must be committed in independent transaction first,
        # background execution uses new DB session to query that task.
        # Otherwise, before request transaction commits, background coroutine
        # will write message bound to task_id first, triggering FK violation.
        async with async_session_scope() as db:
            committed_task_service = TaskService(db, emitter=self.emitter)
            task = await committed_task_service.create_task(
                session_id=session_id,
                full_prompt=prompt,
                created_by="anonymous",
            )
            task_id = task.id

            # Mark task as executing and broadcast status
            await committed_task_service.start_task(task_id)

        # Emit task:started event
        await self.emitter.emit_task_started(
            session_id=session_id,
            task_id=task_id,
            prompt=prompt,
        )

        # 4. Execute in background
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

        # Track execution
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
        """Execute prompt in background.

        Tool is stateless, each DB operation uses short-lived session (via
        async_session_scope). After task completes, use another short-lived
        session to update task status. This avoids zombie connection issues
        caused by long-held DB connections.

        Args:
            session_id: Session ID
            prompt: User prompt
            task_id: Task ID
            stream: Whether to stream
            tool_type: Tool type
            automation_execution_id: Automation execution ID (for completion notification)
        """
        logger.info(f"Background task started for task_id={task_id}")
        tool: Optional[ITool] = None
        try:
            # Get tool (stateless, no need to bind db)
            tool = self.get_tool(tool_type)

            # Create streaming callbacks
            streaming_callbacks = WebSocketStreamingCallbacks(
                emitter=self.emitter,
                session_id=session_id,
                task_id=task_id,
            ) if stream else None

            # Parse permission_mode
            effective_pm = None
            if permission_mode:
                try:
                    effective_pm = PermissionMode(permission_mode)
                except ValueError:
                    pass

            # Execute task (Tool manages short-lived DB sessions internally)
            result = await tool.execute_task(
                session_id=session_id,
                prompt=prompt,
                task_id=task_id,
                streaming_callbacks=streaming_callbacks,
                permission_mode=effective_pm,
            )

            # DEBUG: Track execute_prompt result
            logger.info(
                "[DEBUG] execute_prompt result: task_id=%s, was_stopped=%s, assistant_count=%d, raw_sdk_response=%s",
                task_id[:8], result.was_stopped, len(result.assistant_message_ids),
                "has_data" if result.raw_sdk_response else "None"
            )

            # Update task status (short-lived session)
            if result.was_stopped:
                logger.info("[DEBUG] Task was stopped, calling stop_task: task_id=%s", task_id[:8])
                async with async_session_scope() as db:
                    task_service = TaskService(db)
                    await task_service.stop_task(task_id)
                # Emit task:stopped event
                await self.emitter.emit_task_stopped(
                    session_id=session_id,
                    task_id=task_id,
                )
                # Publish Redis completion event (if automation_execution_id exists)
                if automation_execution_id:
                    await self._publish_automation_completed(
                        execution_id=automation_execution_id,
                        session_id=session_id,
                        status="stopped",
                        has_error=False,
                    )
            else:
                logger.info("[DEBUG] Task completed normally, calling complete_task: task_id=%s", task_id[:8])
                # Compute context window from SDK response
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
                # Emit task:completed event
                await self.emitter.emit_task_completed(
                    session_id=session_id,
                    task_id=task_id,
                    duration_ms=completed_task.duration_ms if completed_task else None,
                    token_usage=completed_token_usage,
                )
                # Publish Redis completion event (if automation_execution_id exists)
                if automation_execution_id:
                    await self._publish_automation_completed(
                        execution_id=automation_execution_id,
                        session_id=session_id,
                        status="completed",
                        has_error=False,
                    )

        except Exception as e:
            logger.error(f"Error executing prompt: {e}", exc_info=True)
            # In exception case, use new session to update task status
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

            # Emit task:failed event to notify frontend
            await self.emitter.emit_task_failed(
                session_id=session_id,
                task_id=task_id,
                error_message=str(e),
                error_code=type(e).__name__,
            )

            # Emit streaming:error event (if streaming is in progress)
            await self.emitter.emit_streaming_error(
                session_id=session_id,
                task_id=task_id,
                error=str(e),
                code=type(e).__name__,
            )

            # Publish Redis failure event (if automation_execution_id exists)
            if automation_execution_id:
                await self._publish_automation_completed(
                    execution_id=automation_execution_id,
                    session_id=session_id,
                    status="failed",
                    has_error=True,
                    error_message=str(e),
                )
        finally:
            # Clean up SDK client and process (ensure cleanup even in exception cases)
            # This is double insurance: normal flow cleanup in claude_tool.py, exception flow here
            try:
                if tool is not None and hasattr(tool, 'prompt_service') and tool.prompt_service:
                    await tool.prompt_service.cleanup_client(session_id)
            except Exception as cleanup_error:
                logger.error(
                    f"Error cleaning up SDK client for session {session_id}: {cleanup_error}",
                    exc_info=True
                )

            # Cleanup
            self._active_executions.pop(task_id, None)

            # Trigger queue processing
            logger.info(f"Triggering queue processing for session {session_id}")
            asyncio.create_task(self._process_queue(session_id))

    async def _process_queue(self, session_id: str) -> None:
        """Process next message in queue.

        Reference agor implementation:
        1. Get or create session-specific lock
        2. Non-blocking check of lock, skip if already locked
        3. Get next queued message
        4. Validate session state
        5. Claim queued message, make it leave deletable state
        6. Call execute_claimed_prompt (creates new task and messages)

        Note: Must use new DB session to avoid conflicts with other requests.

        Args:
            session_id: Session ID
        """
        # Get or create session-specific lock
        if session_id not in self._queue_processing_locks:
            self._queue_processing_locks[session_id] = asyncio.Lock()

        lock = self._queue_processing_locks[session_id]

        # Non-blocking check of lock
        if lock.locked():
            logger.info(f"Queue processing already in progress for session {session_id}, skipping")
            return

        async with lock:
            await self._process_queue_internal(session_id)

    async def _process_queue_internal(self, session_id: str) -> None:
        """Internal method that actually processes queue (executes under lock protection)."""
        # Temporary variables for error handling
        next_msg = None
        next_msg_id = None
        queue_position = None
        prompt_content = None

        try:
            # Use new DB session
            async with async_session_scope() as db:
                message_repo = MessageRepository(db)
                session_service = AgentSessionService(db)
                task_service = TaskService(db)
                message_service = MessageService(db)

                # Claim next queued message
                next_msg_model = await message_repo.claim_next_queued(session_id)

                if not next_msg_model:
                    logger.info(f"No queued messages for session {session_id}")
                    return

                # Convert to entity
                next_msg = message_repo.to_entity(next_msg_model)
                next_msg_id = next_msg.id
                queue_position = next_msg.queue_position

                # Re-validate session state (avoid race condition)
                session = await session_service.get_session(session_id)
                if not session:
                    logger.warning(f"Session {session_id} not found during queue processing")
                    return

                # Check if still has active tasks
                active_tasks = await task_service.get_active_tasks(session_id)
                if active_tasks:
                    logger.info(f"Session {session_id} still has active tasks, skipping queue processing")
                    await message_service.restore_dispatching_message(next_msg_id)
                    return

                logger.info(f"Processing queued message {next_msg.id} (position {next_msg.queue_position})")

                # Extract prompt content
                prompt_content = next_msg.content
                if isinstance(prompt_content, list):
                    # If content blocks, extract text
                    prompt_content = " ".join([
                        block.get("text", "") for block in prompt_content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ])
                elif not isinstance(prompt_content, str):
                    prompt_content = str(prompt_content)

                await self.emitter.emit(
                    WebSocketEvent(
                        type=EventType.MESSAGE_DEQUEUED,
                        session_id=session_id,
                        task_id=None,
                        data={
                            "message_id": next_msg_id,
                            "queue_position": queue_position,
                            "reason": "claimed",
                        },
                    )
                )

            # Execute prompt outside DB session (creates new task and messages)
            async with async_session_scope() as db:
                execution_service = ExecutionService(db)
                await execution_service.execute_claimed_prompt(
                    session_id=session_id,
                    prompt=prompt_content,
                    stream=True,
                )

                message_service = MessageService(db)
                await message_service.finalize_dispatching_message(next_msg_id)

                logger.info(f"Successfully processed queued message {next_msg_id} for session {session_id}")

        except Exception as e:
            logger.error(
                f"Error processing queue for session {session_id}: {e}",
                exc_info=True
            )

            # Notify user queue message processing failed
            if next_msg_id:
                restored = False
                try:
                    async with async_session_scope() as db:
                        message_service = MessageService(db)
                        restored = await message_service.restore_dispatching_message(next_msg_id)
                except Exception:
                    logger.exception("Failed to restore dispatching message after queue processing failure")

                if restored:
                    await self.emitter.emit(
                        WebSocketEvent(
                            type=EventType.MESSAGES_QUEUED,
                            session_id=session_id,
                            task_id=None,
                            data={
                                "message_id": next_msg_id,
                                "session_id": session_id,
                                "queue_position": queue_position,
                                "content_preview": prompt_content[:100] if prompt_content else None,
                                "status": "queued",
                                "queued": True,
                            },
                        )
                    )
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
        Stop task.

        Args:
            session_id: Session ID
            task_id: Task ID
            tool_type: Tool type (uses session.agentic_tool if not provided)

        Returns:
            Stop result
        """
        # Emit task:stop_ack event - confirm stop signal received
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

        # Get tool
        tool = self.get_tool(resolved_tool_type)

        # Stop task
        result = await tool.stop_task(
            session_id=session_id,
            task_id=task_id,
        )

        return result

    @staticmethod
    def _compute_context_window(raw_sdk_response: Optional[Dict[str, Any]]) -> Optional[int]:
        """Calculate context window usage from SDK response.

        Context window usage = input_tokens + output_tokens
        This represents the number of tokens the current conversation occupies in the context window.

        Args:
            raw_sdk_response: Raw SDK response

        Returns:
            Context window usage (tokens) or None
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
                # Codex may provide total_tokens directly
                if "total_tokens" in usage:
                    return usage["total_tokens"]
                return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            elif sdk_type == "gemini":
                usage = response.get("usageMetadata", {})
                # Gemini uses totalTokenCount
                if "totalTokenCount" in usage:
                    return usage["totalTokenCount"]
                return usage.get("promptTokenCount", 0) + usage.get("candidatesTokenCount", 0)

            elif sdk_type == "opencode":
                usage = response.get("usage", {})
                # OpenCode may provide total_tokens directly
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
        """Publish automation execution completed event to Redis.

        Args:
            execution_id: Automation execution ID
            session_id: Session ID
            status: Execution status (completed, failed, stopped)
            has_error: Whether error occurred
            error_message: Error message
        """
        try:
            from app.core.redis_publisher import get_redis_publisher

            # Get session to retrieve workspace_id
            session = await self.session_service.get_session(session_id)
            workspace_id = session.workspace_id if session else "unknown"

            # Calculate total messages (simplified, using message_count)
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
            # Don't affect main flow, just log error
            logger.error(f"Failed to publish automation completed event: {e}", exc_info=True)
