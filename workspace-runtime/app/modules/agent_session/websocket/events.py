"""WebSocket event definitions and emitter.

Defines all WebSocket event types and unified event emission interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.utils.datetime_utils import utcnow

from .manager import ConnectionManager, get_connection_manager


class EventType(str, Enum):
    """WebSocket event types.

    Event categories:
    1. CRUD events - Data create/update/delete notifications
    2. Task lifecycle events - Task state changes
    3. Streaming events - Streaming responses
    4. Thinking events - Claude thinking process
    5. Tool events - Tool execution
    6. Permission events - Permission requests and decisions
    """

    # CRUD events - Sessions
    SESSIONS_CREATED = "sessions created"
    SESSIONS_PATCHED = "sessions patched"
    SESSIONS_UPDATED = "sessions updated"
    SESSIONS_REMOVED = "sessions removed"

    # CRUD events - Tasks
    TASKS_CREATED = "tasks created"
    TASKS_PATCHED = "tasks patched"
    TASKS_UPDATED = "tasks updated"
    TASKS_REMOVED = "tasks removed"

    # Task lifecycle events
    TASK_STARTED = "task:started"           # Task started execution
    TASK_COMPLETED = "task:completed"       # Task completed successfully
    TASK_FAILED = "task:failed"             # Task execution failed
    TASK_STOP = "task:stop"                 # Request to stop task (frontend -> backend)
    TASK_STOP_ACK = "task:stop_ack"         # Acknowledge stop signal received (backend -> frontend)
    TASK_STOPPING = "task:stopping"         # Task stopping
    TASK_STOPPED = "task:stopped"           # Task stopped completed
    TASK_STATUS_NOTICE = "task:status_notice"  # Non-terminal task status notice

    # CRUD events - Messages
    MESSAGES_CREATED = "messages created"
    MESSAGES_PATCHED = "messages patched"
    MESSAGES_UPDATED = "messages updated"
    MESSAGES_REMOVED = "messages removed"
    MESSAGES_QUEUED = "messages queued"

    # Streaming events
    STREAMING_START = "streaming:start"
    STREAMING_CHUNK = "streaming:chunk"
    STREAMING_END = "streaming:end"
    STREAMING_ERROR = "streaming:error"

    # Thinking events (Claude specific)
    THINKING_START = "thinking:start"
    THINKING_CHUNK = "thinking:chunk"
    THINKING_END = "thinking:end"

    # Tool events
    TOOL_START = "tool:start"               # Tool started execution
    TOOL_COMPLETE = "tool:complete"         # Tool execution completed
    TOOL_ERROR = "tool:error"               # Tool execution error

    # Tool Decision events
    TOOL_DECISION_REQUEST = "tool-decision:request"
    TOOL_DECISION_APPROVED = "tool-decision:approved"
    TOOL_DECISION_DENIED = "tool-decision:denied"
    TOOL_DECISION_TIMEOUT = "tool-decision:timeout"

    # Queue events
    MESSAGE_DEQUEUED = "message:dequeued"   # Message removed from queue (processing or deleted)
    QUEUE_PROCESSING_FAILED = "queue:processing_failed"  # Queue message processing failed


@dataclass
class WebSocketEvent:
    """WebSocket event.

    Unified event structure containing type, data, and metadata.
    """

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    seq: Optional[int] = None
    timestamp: str = field(default_factory=lambda: utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Event dictionary
        """
        result = {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }
        if self.session_id:
            result["session_id"] = self.session_id
        if self.task_id:
            result["task_id"] = self.task_id
        if self.seq is not None:
            result["seq"] = self.seq
        return result

    # === Factory methods ===

    # CRUD events
    @classmethod
    def session_created(cls, session_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """Create session created event."""
        return cls(
            type=EventType.SESSIONS_CREATED,
            data=data,
            session_id=session_id,
        )

    @classmethod
    def session_patched(cls, session_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """Create session patched event."""
        return cls(
            type=EventType.SESSIONS_PATCHED,
            data=data,
            session_id=session_id,
        )

    @classmethod
    def session_removed(cls, session_id: str) -> "WebSocketEvent":
        """Create session removed event."""
        return cls(
            type=EventType.SESSIONS_REMOVED,
            data={"session_id": session_id},
            session_id=session_id,
        )

    @classmethod
    def task_created(cls, session_id: str, task_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """Create task created event."""
        return cls(
            type=EventType.TASKS_CREATED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_patched(cls, session_id: str, task_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """Create task patched event."""
        return cls(
            type=EventType.TASKS_PATCHED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_started(
        cls,
        session_id: str,
        task_id: str,
        prompt: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create task:started event - Task started execution."""
        return cls(
            type=EventType.TASK_STARTED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "running",  # Add status so frontend can update task state
                "prompt": prompt[:100] if prompt else None,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_completed(
        cls,
        session_id: str,
        task_id: str,
        message_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        context_compacted: bool = False,
    ) -> "WebSocketEvent":
        """Create task:completed event - Task completed successfully."""
        return cls(
            type=EventType.TASK_COMPLETED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "completed",  # Add status so frontend can update task state
                "message_count": message_count,
                "duration_ms": duration_ms,
                "token_usage": token_usage,
                "context_compacted": context_compacted,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_failed(
        cls,
        session_id: str,
        task_id: str,
        error_message: str,
        error_code: Optional[str] = None,
        stack_trace: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create task:failed event - Task execution failed."""
        return cls(
            type=EventType.TASK_FAILED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "failed",  # Add status so frontend can update task state
                "error_message": error_message,
                "error_code": error_code,
                "stack_trace": stack_trace,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stop_request(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """Create task:stop event - Request to stop task."""
        return cls(
            type=EventType.TASK_STOP,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stop_ack(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """Create task:stop_ack event - Acknowledge stop signal received."""
        return cls(
            type=EventType.TASK_STOP_ACK,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stopping(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """Create task:stopping event - Task stopping."""
        return cls(
            type=EventType.TASK_STOPPING,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stopped(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """Create task:stopped event - Task stopped completed."""
        return cls(
            type=EventType.TASK_STOPPED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "stopped",  # Add status so frontend can update task state
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_status_notice(
        cls,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> "WebSocketEvent":
        """Create task:status_notice event."""
        return cls(
            type=EventType.TASK_STATUS_NOTICE,
            data={"session_id": session_id, "task_id": task_id, **data},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def message_created(
        cls,
        session_id: str,
        message_id: str,
        data: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create message created event."""
        return cls(
            type=EventType.MESSAGES_CREATED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def message_patched(
        cls,
        session_id: str,
        message_id: str,
        data: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create message patched event."""
        return cls(
            type=EventType.MESSAGES_PATCHED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    # Streaming events
    @classmethod
    def streaming_start(
        cls,
        session_id: str,
        task_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """Create streaming:start event."""
        return cls(
            type=EventType.STREAMING_START,
            data=data or {},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def streaming_chunk(
        cls,
        session_id: str,
        task_id: str,
        content: str,
        is_partial: bool = True,
        message_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create streaming:chunk event."""
        data = {"content": content, "is_partial": is_partial}
        if message_id:
            data["message_id"] = message_id
        return cls(
            type=EventType.STREAMING_CHUNK,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def streaming_end(
        cls,
        session_id: str,
        task_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """Create streaming:end event."""
        return cls(
            type=EventType.STREAMING_END,
            data=data or {},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def streaming_error(
        cls,
        session_id: str,
        task_id: str,
        error: str,
        code: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create streaming:error event."""
        return cls(
            type=EventType.STREAMING_ERROR,
            data={"error": error, "code": code},
            session_id=session_id,
            task_id=task_id,
        )

    # Thinking events
    @classmethod
    def thinking_start(
        cls,
        session_id: str,
        task_id: str,
        message_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create thinking:start event."""
        data = {}
        if message_id:
            data["message_id"] = message_id
        return cls(
            type=EventType.THINKING_START,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def thinking_chunk(
        cls,
        session_id: str,
        task_id: str,
        content: str,
        is_partial: bool = True,
        message_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create thinking:chunk event."""
        data = {"content": content, "is_partial": is_partial}
        if message_id:
            data["message_id"] = message_id
        return cls(
            type=EventType.THINKING_CHUNK,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def thinking_end(
        cls,
        session_id: str,
        task_id: str,
        message_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create thinking:end event."""
        data = {}
        if message_id:
            data["message_id"] = message_id
        return cls(
            type=EventType.THINKING_END,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    # Tool Decision events
    @classmethod
    def tool_decision_request(
        cls,
        session_id: str,
        task_id: str,
        request_id: str,
        decision_type: str,
        options: List[Dict[str, Any]],
        tool_call: Dict[str, Any],
        timeout: int = 60,
    ) -> "WebSocketEvent":
        """Create tool-decision:request event."""
        return cls(
            type=EventType.TOOL_DECISION_REQUEST,
            data={
                "request_id": request_id,
                "decision_type": decision_type,
                "options": options,
                "tool_call": tool_call,
                "timeout": timeout,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def tool_decision_approved(
        cls,
        session_id: str,
        task_id: str,
        request_id: str,
        scope: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create tool-decision:approved event."""
        return cls(
            type=EventType.TOOL_DECISION_APPROVED,
            data={"request_id": request_id, "scope": scope},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def tool_decision_denied(
        cls,
        session_id: str,
        task_id: str,
        request_id: str,
        reason: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create tool-decision:denied event."""
        return cls(
            type=EventType.TOOL_DECISION_DENIED,
            data={"request_id": request_id, "reason": reason},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def tool_decision_timeout(
        cls,
        session_id: str,
        task_id: str,
        request_id: str,
    ) -> "WebSocketEvent":
        """Create tool-decision:timeout event."""
        return cls(
            type=EventType.TOOL_DECISION_TIMEOUT,
            data={"request_id": request_id},
            session_id=session_id,
            task_id=task_id,
        )

    # Tool events
    @classmethod
    def tool_start(
        cls,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """Create tool:start event - Tool started execution."""
        return cls(
            type=EventType.TOOL_START,
            data={
                "tool_use_id": tool_use_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def tool_complete(
        cls,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        result: Any,
        is_error: bool = False,
    ) -> "WebSocketEvent":
        """Create tool:complete event - Tool execution completed."""
        return cls(
            type=EventType.TOOL_COMPLETE,
            data={
                "tool_use_id": tool_use_id,
                "tool_name": tool_name,
                "result": result,
                "is_error": is_error,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def tool_error(
        cls,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> "WebSocketEvent":
        """Create tool:error event - Tool execution error."""
        return cls(
            type=EventType.TOOL_ERROR,
            data={
                "tool_use_id": tool_use_id,
                "tool_name": tool_name,
                "error_message": error_message,
                "error_code": error_code,
            },
            session_id=session_id,
            task_id=task_id,
        )

    # Queue events
    @classmethod
    def message_dequeued(
        cls,
        session_id: str,
        message_id: str,
        queue_position: int,
        reason: str = "processing",
    ) -> "WebSocketEvent":
        """Create message:dequeued event - Message removed from queue.

        Args:
            session_id: Session ID
            message_id: Message ID
            queue_position: Original queue position
            reason: Removal reason ("processing" being processed / "deleted" deleted)
        """
        return cls(
            type=EventType.MESSAGE_DEQUEUED,
            data={
                "session_id": session_id,
                "message_id": message_id,
                "queue_position": queue_position,
                "reason": reason,
            },
            session_id=session_id,
        )


# Event listener type
EventListener = Callable[[WebSocketEvent], None]


class EventEmitter:
    """Event emitter.

    Unified event emission interface, integrating ConnectionManager and event listeners.
    """

    def __init__(
        self,
        manager: Optional[ConnectionManager] = None,
    ):
        """Initialize emitter.

        Args:
            manager: Connection Manager (optional)
        """
        self._manager = manager
        self._listeners: Dict[EventType, List[EventListener]] = {}

    @property
    def manager(self) -> ConnectionManager:
        """Get Connection Manager."""
        if self._manager is None:
            self._manager = get_connection_manager()
        return self._manager

    def on(self, event_type: EventType, listener: EventListener) -> None:
        """Register event listener.

        Args:
            event_type: Event type
            listener: Listener function
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def off(self, event_type: EventType, listener: EventListener) -> None:
        """Remove event listener.

        Args:
            event_type: Event type
            listener: Listener function
        """
        if event_type in self._listeners:
            self._listeners[event_type] = [
                l for l in self._listeners[event_type] if l != listener
            ]

    async def emit(self, event: WebSocketEvent) -> int:
        """Emit event.

        Args:
            event: Event

        Returns:
            Number of connections sent
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"📡 [EventEmitter] Emitting event: {event.type.value}")
        logger.info(f"   Session ID: {event.session_id}")
        logger.info(f"   Task ID: {event.task_id}")

        # Call local listeners
        listeners = self._listeners.get(event.type, [])
        logger.info(f"   Local listeners count: {len(listeners)}")
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass  # Ignore listener errors

        payload = event.to_dict()

        # Send to WebSocket (seq allocated by ConnectionManager._with_replay_seq)
        if event.session_id:
            logger.info(f"   Prepare to send to session: {event.session_id}")
            sent_count = await self.manager.send_to_session(
                event.session_id,
                payload,
            )
            logger.info(f"   ✅ Sent to {sent_count} connections")
            return sent_count
        else:
            logger.info(f"   Prepare to broadcast to all connections")
            sent_count = await self.manager.broadcast(payload)
            logger.info(f"   ✅ Broadcasted to {sent_count} connections")
            return sent_count

    async def emit_to_user(
        self,
        user_id: str,
        event: WebSocketEvent,
    ) -> int:
        """Emit event to specific user.

        Args:
            user_id: User ID
            event: Event

        Returns:
            Number of connections sent
        """
        return await self.manager.send_to_user(user_id, event.to_dict())

    # === Convenience methods ===

    async def emit_session_created(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit session created event."""
        return await self.emit(WebSocketEvent.session_created(session_id, data))

    async def emit_session_patched(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit session patched event."""
        return await self.emit(WebSocketEvent.session_patched(session_id, data))

    async def emit_task_created(
        self,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit task created event."""
        return await self.emit(WebSocketEvent.task_created(session_id, task_id, data))

    async def emit_task_patched(
        self,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit task patched event."""
        return await self.emit(WebSocketEvent.task_patched(session_id, task_id, data))

    async def emit_task_started(
        self,
        session_id: str,
        task_id: str,
        prompt: Optional[str] = None,
    ) -> int:
        """Emit task:started event."""
        return await self.emit(WebSocketEvent.task_started(session_id, task_id, prompt))

    async def emit_task_completed(
        self,
        session_id: str,
        task_id: str,
        message_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        token_usage: Optional[Dict[str, Any]] = None,
        context_compacted: bool = False,
    ) -> int:
        """Emit task:completed event."""
        return await self.emit(
            WebSocketEvent.task_completed(
                session_id,
                task_id,
                message_count,
                duration_ms,
                token_usage,
                context_compacted,
            )
        )

    async def emit_task_failed(
        self,
        session_id: str,
        task_id: str,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> int:
        """Emit task:failed event."""
        return await self.emit(
            WebSocketEvent.task_failed(session_id, task_id, error_message, error_code)
        )

    async def emit_task_stopped(
        self,
        session_id: str,
        task_id: str,
    ) -> int:
        """Emit task:stopped event."""
        return await self.emit(WebSocketEvent.task_stopped(session_id, task_id))

    async def emit_task_stop_ack(
        self,
        session_id: str,
        task_id: str,
    ) -> int:
        """Emit task:stop_ack event - Acknowledge stop signal received."""
        return await self.emit(WebSocketEvent.task_stop_ack(session_id, task_id))

    async def emit_task_status_notice(
        self,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> int:
        """Emit task:status_notice event."""
        return await self.emit(
            WebSocketEvent.task_status_notice(session_id, task_id, data)
        )

    async def emit_tool_start(
        self,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Emit tool:start event."""
        return await self.emit(
            WebSocketEvent.tool_start(session_id, task_id, tool_use_id, tool_name, tool_input)
        )

    async def emit_streaming_error(
        self,
        session_id: str,
        task_id: str,
        error: str,
        code: Optional[str] = None,
    ) -> int:
        """Emit streaming:error event."""
        return await self.emit(
            WebSocketEvent.streaming_error(session_id, task_id, error, code)
        )

    async def emit_message_created(
        self,
        session_id: str,
        message_id: str,
        data: Dict[str, Any],
        task_id: Optional[str] = None,
    ) -> int:
        """Emit message created event."""
        return await self.emit(
            WebSocketEvent.message_created(session_id, message_id, data, task_id)
        )

    async def emit_streaming_chunk(
        self,
        session_id: str,
        task_id: str,
        content: str,
        is_partial: bool = True,
        message_id: Optional[str] = None,
    ) -> int:
        """Emit streaming:chunk event."""
        return await self.emit(
            WebSocketEvent.streaming_chunk(session_id, task_id, content, is_partial, message_id)
        )

    async def emit_tool_decision_request(
        self,
        session_id: str,
        task_id: str,
        request_id: str,
        decision_type: str,
        options: List[Dict[str, Any]],
        tool_call: Dict[str, Any],
        timeout: int = 60,
    ) -> int:
        """Emit tool-decision:request event."""
        return await self.emit(
            WebSocketEvent.tool_decision_request(
                session_id, task_id, request_id, decision_type, options, tool_call, timeout
            )
        )

    async def emit_message_dequeued(
        self,
        session_id: str,
        message_id: str,
        queue_position: int,
        reason: str = "processing",
    ) -> int:
        """Emit message:dequeued event."""
        return await self.emit(
            WebSocketEvent.message_dequeued(session_id, message_id, queue_position, reason)
        )


# Global Event Emitter instance
_global_emitter: Optional[EventEmitter] = None


def get_event_emitter() -> EventEmitter:
    """Get global Event Emitter.

    Returns:
        Event Emitter instance
    """
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = EventEmitter()
    return _global_emitter


def reset_event_emitter() -> None:
    """Reset global Event Emitter.

    Mainly used for testing.
    """
    global _global_emitter
    _global_emitter = None


__all__ = [
    "EventEmitter",
    "EventListener",
    "EventType",
    "WebSocketEvent",
    "get_event_emitter",
    "reset_event_emitter",
]
