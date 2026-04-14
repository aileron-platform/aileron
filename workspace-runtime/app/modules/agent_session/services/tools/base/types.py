"""
共用類型定義.

比照 agor-main 的 types.ts
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from app.modules.agent_session.domain.enums import MessageRole


class ToolType(str, Enum):
    """Tool 類型."""
    
    CLAUDE_CODE = "claude-code"
    GEMINI = "gemini"
    CODEX = "codex"
    OPENCODE = "opencode"


@dataclass
class ToolCapabilities:
    """Tool 能力標記."""

    # 基本能力（對應 ToolCapabilityResponse schema）
    streaming: bool = True
    thinking: bool = False
    multimodal: bool = False
    max_context_window: int = 200000
    prompt_caching: bool = False
    local_execution: bool = False
    built_in_tools: list[str] = None

    # 進階能力（內部使用）
    supports_session_import: bool = False
    supports_session_create: bool = False
    supports_live_execution: bool = False
    supports_session_fork: bool = False
    supports_child_spawn: bool = False
    supports_git_state: bool = False

    def __post_init__(self):
        """初始化後處理."""
        if self.built_in_tools is None:
            self.built_in_tools = []


@dataclass
class TokenUsage:
    """Token 使用量."""
    
    input: int = 0
    output: int = 0
    cache_read: Optional[int] = None
    cache_creation: Optional[int] = None


@dataclass
class TaskResult:
    """任務執行結果."""
    
    user_message_id: str
    assistant_message_ids: List[str]
    token_usage: Optional[TokenUsage] = None
    duration_ms: Optional[int] = None
    agent_session_id: Optional[str] = None
    context_window: Optional[int] = None
    context_window_limit: Optional[int] = None
    model: Optional[str] = None
    model_usage: Optional[Dict[str, Any]] = None
    raw_sdk_response: Optional[Dict[str, Any]] = None
    was_stopped: bool = False


# ProcessedEvent 類型定義（比照 agor-main 的 ProcessedEvent）
@dataclass
class BaseProcessedEvent:
    """基礎處理事件."""

    type: str = ""


@dataclass
class PartialEvent(BaseProcessedEvent):
    """部分文字事件（串流）."""

    text: str = ""
    resolved_model: Optional[str] = None
    type: Literal["partial"] = "partial"


@dataclass
class ThinkingPartialEvent(BaseProcessedEvent):
    """思考部分事件（串流）."""

    thinking_chunk: str = ""
    type: Literal["thinking_partial"] = "thinking_partial"


@dataclass
class ThinkingCompleteEvent(BaseProcessedEvent):
    """思考完成事件."""

    type: Literal["thinking_complete"] = "thinking_complete"


@dataclass
class CompleteEvent(BaseProcessedEvent):
    """訊息完成事件."""

    role: MessageRole = MessageRole.ASSISTANT
    content: List[Dict[str, Any]] = None
    type: Literal["complete"] = "complete"
    tool_uses: Optional[List[Dict[str, Any]]] = None
    parent_tool_use_id: Optional[str] = None
    resolved_model: Optional[str] = None

    def __post_init__(self):
        """初始化後處理."""
        if self.content is None:
            self.content = []


@dataclass
class ResultEvent(BaseProcessedEvent):
    """結果事件（包含 token usage）."""

    raw_sdk_message: Dict[str, Any] = None
    type: Literal["result"] = "result"
    token_usage: Optional[TokenUsage] = None
    duration_ms: Optional[int] = None
    model_usage: Optional[Dict[str, Any]] = None
    structured_output: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """初始化後處理."""
        if self.raw_sdk_message is None:
            self.raw_sdk_message = {}


@dataclass
class EndEvent(BaseProcessedEvent):
    """結束事件."""
    
    type: Literal["end"] = "end"
    reason: str = "conversation_ended"


@dataclass
class StoppedEvent(BaseProcessedEvent):
    """停止事件."""
    
    type: Literal["stopped"] = "stopped"


@dataclass
class ToolStartEvent(BaseProcessedEvent):
    """工具開始事件."""

    tool_use_id: str = ""
    tool_name: str = ""
    type: Literal["tool_start"] = "tool_start"


@dataclass
class ToolCompleteEvent(BaseProcessedEvent):
    """工具完成事件."""

    tool_use_id: str = ""
    type: Literal["tool_complete"] = "tool_complete"


# Union type for all events
ProcessedEvent = Union[
    PartialEvent,
    ThinkingPartialEvent,
    ThinkingCompleteEvent,
    CompleteEvent,
    ResultEvent,
    EndEvent,
    StoppedEvent,
    ToolStartEvent,
    ToolCompleteEvent,
]

