"""
Tools package for multi-SDK support.

Architecture design modeled after agor-main.
"""

from .base.streaming_callbacks import StreamingCallbacks
from .base.tool_interface import ITool
from .base.types import (
    TaskResult,
    ToolType,
)

__all__ = [
    "ITool",
    "StreamingCallbacks",
    "TaskResult",
    "ToolType",
]
