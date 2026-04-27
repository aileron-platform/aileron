"""WebSocket layer - Real-time communication and event broadcasting."""

from .manager import ConnectionManager, get_connection_manager
from .events import (
    EventEmitter,
    EventType,
    WebSocketEvent,
    get_event_emitter,
)
from .router import router as websocket_router

__all__ = [
    "ConnectionManager",
    "EventEmitter",
    "EventType",
    "WebSocketEvent",
    "get_connection_manager",
    "get_event_emitter",
    "websocket_router",
]
