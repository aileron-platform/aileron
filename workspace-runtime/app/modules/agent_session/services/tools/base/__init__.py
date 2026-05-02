"""Base interfaces and types for tool implementations."""

from .streaming_callbacks import StreamingCallbacks
from .tool_interface import ITool
from .types import (
    ProcessedEvent,
    TaskResult,
    ToolType,
)

__all__ = [
    "ITool",
    "ProcessedEvent",
    "StreamingCallbacks",
    "TaskResult",
    "ToolType",
]
