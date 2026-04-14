"""WebSocket 事件定義和發送器.

定義所有 WebSocket 事件類型和統一的事件發送介面。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.utils.datetime_utils import utcnow

from .manager import ConnectionManager, get_connection_manager


class EventType(str, Enum):
    """WebSocket 事件類型.

    事件分類：
    1. CRUD 事件 - 資料建立/更新/刪除的通知
    2. Task 生命週期事件 - 任務狀態變化
    3. Streaming 事件 - 串流回應
    4. Thinking 事件 - Claude 思考過程
    5. Tool 事件 - 工具執行
    6. Permission 事件 - 權限請求和決策
    """

    # CRUD 事件 - Sessions
    SESSIONS_CREATED = "sessions created"
    SESSIONS_PATCHED = "sessions patched"
    SESSIONS_UPDATED = "sessions updated"
    SESSIONS_REMOVED = "sessions removed"

    # CRUD 事件 - Tasks
    TASKS_CREATED = "tasks created"
    TASKS_PATCHED = "tasks patched"
    TASKS_UPDATED = "tasks updated"
    TASKS_REMOVED = "tasks removed"

    # Task 生命週期事件
    TASK_STARTED = "task:started"           # 任務開始執行
    TASK_COMPLETED = "task:completed"       # 任務成功完成
    TASK_FAILED = "task:failed"             # 任務執行失敗
    TASK_STOP = "task:stop"                 # 請求停止任務 (前端 -> 後端)
    TASK_STOP_ACK = "task:stop_ack"         # 確認收到停止信號 (後端 -> 前端)
    TASK_STOPPING = "task:stopping"         # 任務正在停止中
    TASK_STOPPED = "task:stopped"           # 任務已停止完成

    # CRUD 事件 - Messages
    MESSAGES_CREATED = "messages created"
    MESSAGES_PATCHED = "messages patched"
    MESSAGES_UPDATED = "messages updated"
    MESSAGES_REMOVED = "messages removed"
    MESSAGES_QUEUED = "messages queued"

    # Streaming 事件
    STREAMING_START = "streaming:start"
    STREAMING_CHUNK = "streaming:chunk"
    STREAMING_END = "streaming:end"
    STREAMING_ERROR = "streaming:error"

    # Thinking 事件 (Claude 專屬)
    THINKING_START = "thinking:start"
    THINKING_CHUNK = "thinking:chunk"
    THINKING_END = "thinking:end"

    # Tool 事件
    TOOL_START = "tool:start"               # 工具開始執行
    TOOL_COMPLETE = "tool:complete"         # 工具執行完成
    TOOL_ERROR = "tool:error"               # 工具執行錯誤

    # Tool Decision 事件
    TOOL_DECISION_REQUEST = "tool-decision:request"
    TOOL_DECISION_APPROVED = "tool-decision:approved"
    TOOL_DECISION_DENIED = "tool-decision:denied"
    TOOL_DECISION_TIMEOUT = "tool-decision:timeout"

    # Queue 事件
    MESSAGE_DEQUEUED = "message:dequeued"   # 訊息從佇列移除（處理中或被刪除）
    QUEUE_PROCESSING_FAILED = "queue:processing_failed"  # 佇列訊息處理失敗


@dataclass
class WebSocketEvent:
    """WebSocket 事件.

    統一的事件結構，包含類型、資料和元資訊。
    """

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    seq: Optional[int] = None
    timestamp: str = field(default_factory=lambda: utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典.

        Returns:
            事件字典
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

    # === 工廠方法 ===

    # CRUD 事件
    @classmethod
    def session_created(cls, session_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """建立 session created 事件."""
        return cls(
            type=EventType.SESSIONS_CREATED,
            data=data,
            session_id=session_id,
        )

    @classmethod
    def session_patched(cls, session_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """建立 session patched 事件."""
        return cls(
            type=EventType.SESSIONS_PATCHED,
            data=data,
            session_id=session_id,
        )

    @classmethod
    def session_removed(cls, session_id: str) -> "WebSocketEvent":
        """建立 session removed 事件."""
        return cls(
            type=EventType.SESSIONS_REMOVED,
            data={"session_id": session_id},
            session_id=session_id,
        )

    @classmethod
    def task_created(cls, session_id: str, task_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """建立 task created 事件."""
        return cls(
            type=EventType.TASKS_CREATED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_patched(cls, session_id: str, task_id: str, data: Dict[str, Any]) -> "WebSocketEvent":
        """建立 task patched 事件."""
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
        """建立 task:started 事件 - 任務開始執行."""
        return cls(
            type=EventType.TASK_STARTED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "running",  # 加入 status 讓前端可以更新 task 狀態
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
    ) -> "WebSocketEvent":
        """建立 task:completed 事件 - 任務成功完成."""
        return cls(
            type=EventType.TASK_COMPLETED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "completed",  # 加入 status 讓前端可以更新 task 狀態
                "message_count": message_count,
                "duration_ms": duration_ms,
                "token_usage": token_usage,
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
        """建立 task:failed 事件 - 任務執行失敗."""
        return cls(
            type=EventType.TASK_FAILED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "failed",  # 加入 status 讓前端可以更新 task 狀態
                "error_message": error_message,
                "error_code": error_code,
                "stack_trace": stack_trace,
            },
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stop_request(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """建立 task:stop 事件 - 請求停止任務."""
        return cls(
            type=EventType.TASK_STOP,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stop_ack(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """建立 task:stop_ack 事件 - 確認收到停止信號."""
        return cls(
            type=EventType.TASK_STOP_ACK,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stopping(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """建立 task:stopping 事件 - 任務正在停止中."""
        return cls(
            type=EventType.TASK_STOPPING,
            data={"session_id": session_id, "task_id": task_id},
            session_id=session_id,
            task_id=task_id,
        )

    @classmethod
    def task_stopped(cls, session_id: str, task_id: str) -> "WebSocketEvent":
        """建立 task:stopped 事件 - 任務已停止完成."""
        return cls(
            type=EventType.TASK_STOPPED,
            data={
                "session_id": session_id,
                "task_id": task_id,
                "status": "stopped",  # 加入 status 讓前端可以更新 task 狀態
            },
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
        """建立 message created 事件."""
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
        """建立 message patched 事件."""
        return cls(
            type=EventType.MESSAGES_PATCHED,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    # Streaming 事件
    @classmethod
    def streaming_start(
        cls,
        session_id: str,
        task_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """建立 streaming:start 事件."""
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
        """建立 streaming:chunk 事件."""
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
        """建立 streaming:end 事件."""
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
        """建立 streaming:error 事件."""
        return cls(
            type=EventType.STREAMING_ERROR,
            data={"error": error, "code": code},
            session_id=session_id,
            task_id=task_id,
        )

    # Thinking 事件
    @classmethod
    def thinking_start(
        cls,
        session_id: str,
        task_id: str,
        message_id: Optional[str] = None,
    ) -> "WebSocketEvent":
        """建立 thinking:start 事件."""
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
        """建立 thinking:chunk 事件."""
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
        """建立 thinking:end 事件."""
        data = {}
        if message_id:
            data["message_id"] = message_id
        return cls(
            type=EventType.THINKING_END,
            data=data,
            session_id=session_id,
            task_id=task_id,
        )

    # Tool Decision 事件
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
        """建立 tool-decision:request 事件."""
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
        """建立 tool-decision:approved 事件."""
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
        """建立 tool-decision:denied 事件."""
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
        """建立 tool-decision:timeout 事件."""
        return cls(
            type=EventType.TOOL_DECISION_TIMEOUT,
            data={"request_id": request_id},
            session_id=session_id,
            task_id=task_id,
        )

    # Tool 事件
    @classmethod
    def tool_start(
        cls,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> "WebSocketEvent":
        """建立 tool:start 事件 - 工具開始執行."""
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
        """建立 tool:complete 事件 - 工具執行完成."""
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
        """建立 tool:error 事件 - 工具執行錯誤."""
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

    # Queue 事件
    @classmethod
    def message_dequeued(
        cls,
        session_id: str,
        message_id: str,
        queue_position: int,
        reason: str = "processing",
    ) -> "WebSocketEvent":
        """建立 message:dequeued 事件 - 訊息從佇列移除.

        Args:
            session_id: 會話 ID
            message_id: 訊息 ID
            queue_position: 原佇列位置
            reason: 移除原因 ("processing" 處理中 / "deleted" 被刪除)
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


# 事件監聽器類型
EventListener = Callable[[WebSocketEvent], None]


class EventEmitter:
    """事件發送器.

    統一的事件發送介面，整合 ConnectionManager 和事件監聽。
    """

    def __init__(
        self,
        manager: Optional[ConnectionManager] = None,
    ):
        """初始化發送器.

        Args:
            manager: Connection Manager (可選)
        """
        self._manager = manager
        self._listeners: Dict[EventType, List[EventListener]] = {}

    @property
    def manager(self) -> ConnectionManager:
        """取得 Connection Manager."""
        if self._manager is None:
            self._manager = get_connection_manager()
        return self._manager

    def on(self, event_type: EventType, listener: EventListener) -> None:
        """註冊事件監聽器.

        Args:
            event_type: 事件類型
            listener: 監聽器函式
        """
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(listener)

    def off(self, event_type: EventType, listener: EventListener) -> None:
        """移除事件監聽器.

        Args:
            event_type: 事件類型
            listener: 監聽器函式
        """
        if event_type in self._listeners:
            self._listeners[event_type] = [
                l for l in self._listeners[event_type] if l != listener
            ]

    async def emit(self, event: WebSocketEvent) -> int:
        """發送事件.

        Args:
            event: 事件

        Returns:
            發送的連線數
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"📡 [EventEmitter] 發送事件: {event.type.value}")
        logger.info(f"   Session ID: {event.session_id}")
        logger.info(f"   Task ID: {event.task_id}")

        # 呼叫本地監聽器
        listeners = self._listeners.get(event.type, [])
        logger.info(f"   本地監聽器數: {len(listeners)}")
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                pass  # 忽略監聽器錯誤

        payload = event.to_dict()

        # 發送到 WebSocket（seq 由 ConnectionManager._with_replay_seq 統一分配）
        if event.session_id:
            logger.info(f"   準備發送到 session: {event.session_id}")
            sent_count = await self.manager.send_to_session(
                event.session_id,
                payload,
            )
            logger.info(f"   ✅ 已發送給 {sent_count} 個連線")
            return sent_count
        else:
            logger.info(f"   準備廣播給所有連線")
            sent_count = await self.manager.broadcast(payload)
            logger.info(f"   ✅ 已廣播給 {sent_count} 個連線")
            return sent_count

    async def emit_to_user(
        self,
        user_id: str,
        event: WebSocketEvent,
    ) -> int:
        """發送事件給指定使用者.

        Args:
            user_id: 使用者 ID
            event: 事件

        Returns:
            發送的連線數
        """
        return await self.manager.send_to_user(user_id, event.to_dict())

    # === 便捷方法 ===

    async def emit_session_created(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> int:
        """發送 session created 事件."""
        return await self.emit(WebSocketEvent.session_created(session_id, data))

    async def emit_session_patched(
        self,
        session_id: str,
        data: Dict[str, Any],
    ) -> int:
        """發送 session patched 事件."""
        return await self.emit(WebSocketEvent.session_patched(session_id, data))

    async def emit_task_created(
        self,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> int:
        """發送 task created 事件."""
        return await self.emit(WebSocketEvent.task_created(session_id, task_id, data))

    async def emit_task_patched(
        self,
        session_id: str,
        task_id: str,
        data: Dict[str, Any],
    ) -> int:
        """發送 task patched 事件."""
        return await self.emit(WebSocketEvent.task_patched(session_id, task_id, data))

    async def emit_task_started(
        self,
        session_id: str,
        task_id: str,
        prompt: Optional[str] = None,
    ) -> int:
        """發送 task:started 事件."""
        return await self.emit(WebSocketEvent.task_started(session_id, task_id, prompt))

    async def emit_task_completed(
        self,
        session_id: str,
        task_id: str,
        message_count: Optional[int] = None,
        duration_ms: Optional[int] = None,
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> int:
        """發送 task:completed 事件."""
        return await self.emit(
            WebSocketEvent.task_completed(
                session_id, task_id, message_count, duration_ms, token_usage
            )
        )

    async def emit_task_failed(
        self,
        session_id: str,
        task_id: str,
        error_message: str,
        error_code: Optional[str] = None,
    ) -> int:
        """發送 task:failed 事件."""
        return await self.emit(
            WebSocketEvent.task_failed(session_id, task_id, error_message, error_code)
        )

    async def emit_task_stopped(
        self,
        session_id: str,
        task_id: str,
    ) -> int:
        """發送 task:stopped 事件."""
        return await self.emit(WebSocketEvent.task_stopped(session_id, task_id))

    async def emit_task_stop_ack(
        self,
        session_id: str,
        task_id: str,
    ) -> int:
        """發送 task:stop_ack 事件 - 確認收到停止信號."""
        return await self.emit(WebSocketEvent.task_stop_ack(session_id, task_id))

    async def emit_tool_start(
        self,
        session_id: str,
        task_id: str,
        tool_use_id: str,
        tool_name: str,
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> int:
        """發送 tool:start 事件."""
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
        """發送 streaming:error 事件."""
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
        """發送 message created 事件."""
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
        """發送 streaming:chunk 事件."""
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
        """發送 tool-decision:request 事件."""
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
        """發送 message:dequeued 事件."""
        return await self.emit(
            WebSocketEvent.message_dequeued(session_id, message_id, queue_position, reason)
        )


# 全域 Event Emitter 實例
_global_emitter: Optional[EventEmitter] = None


def get_event_emitter() -> EventEmitter:
    """取得全域 Event Emitter.

    Returns:
        Event Emitter 實例
    """
    global _global_emitter
    if _global_emitter is None:
        _global_emitter = EventEmitter()
    return _global_emitter


def reset_event_emitter() -> None:
    """重置全域 Event Emitter.

    主要用於測試。
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
