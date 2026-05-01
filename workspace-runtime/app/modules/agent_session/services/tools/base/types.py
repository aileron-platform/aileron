"""
Common type definitions.

Modeled after agor-main's types.ts
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from app.modules.agent_session.domain.enums import MessageRole


class ToolType(str, Enum):
    """Tool type."""

    CLAUDE_CODE = "claude-code"
    GEMINI = "gemini"
    CODEX = "codex"
    OPENCODE = "opencode"


class ToolExecutionError(Exception):
    """Tool execution error with a stable client-facing code."""

    error_code = "TOOL_EXECUTION_FAILED"
    message_key = "workspace.chat.errors.executionFailed"

    def __init__(self, message_key: str | None = None, *, error_code: str | None = None) -> None:
        self.message_key = message_key or self.message_key
        self.error_code = error_code or self.error_code
        super().__init__(self.message_key)


class ToolAuthenticationError(ToolExecutionError):
    """Tool authentication failure."""

    error_code = "AUTHENTICATION_FAILED"
    message_key = "workspace.chat.errors.authenticationFailed"


@dataclass
class ToolCapabilities:
    """Tool capability flags."""

    # Basic capabilities (corresponds to ToolCapabilityResponse schema)
    streaming: bool = True
    thinking: bool = False
    multimodal: bool = False
    max_context_window: int = 200000
    prompt_caching: bool = False
    local_execution: bool = False
    built_in_tools: list[str] = None

    # Advanced capabilities (internal use)
    supports_session_import: bool = False
    supports_session_create: bool = False
    supports_live_execution: bool = False
    supports_session_fork: bool = False
    supports_child_spawn: bool = False
    supports_git_state: bool = False

    def __post_init__(self):
        """Post-initialization processing."""
        if self.built_in_tools is None:
            self.built_in_tools = []


@dataclass
class TokenUsage:
    """Token usage."""

    input: int = 0
    output: int = 0
    cache_read: Optional[int] = None
    cache_creation: Optional[int] = None


@dataclass
class TaskResult:
    """Task execution result."""

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


# ProcessedEvent type definitions (modeled after agor-main's ProcessedEvent)
@dataclass
class BaseProcessedEvent:
    """Base processing event."""

    type: str = ""


@dataclass
class PartialEvent(BaseProcessedEvent):
    """Partial text event (streaming)."""

    text: str = ""
    resolved_model: Optional[str] = None
    type: Literal["partial"] = "partial"


@dataclass
class ThinkingPartialEvent(BaseProcessedEvent):
    """Thinking partial event (streaming)."""

    thinking_chunk: str = ""
    type: Literal["thinking_partial"] = "thinking_partial"


@dataclass
class ThinkingCompleteEvent(BaseProcessedEvent):
    """Thinking complete event."""

    type: Literal["thinking_complete"] = "thinking_complete"


@dataclass
class CompleteEvent(BaseProcessedEvent):
    """Message complete event."""

    role: MessageRole = MessageRole.ASSISTANT
    content: List[Dict[str, Any]] = None
    type: Literal["complete"] = "complete"
    tool_uses: Optional[List[Dict[str, Any]]] = None
    parent_tool_use_id: Optional[str] = None
    resolved_model: Optional[str] = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.content is None:
            self.content = []


@dataclass
class ResultEvent(BaseProcessedEvent):
    """Result event (includes token usage)."""

    raw_sdk_message: Dict[str, Any] = None
    type: Literal["result"] = "result"
    token_usage: Optional[TokenUsage] = None
    duration_ms: Optional[int] = None
    model_usage: Optional[Dict[str, Any]] = None
    structured_output: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Post-initialization processing."""
        if self.raw_sdk_message is None:
            self.raw_sdk_message = {}


@dataclass
class EndEvent(BaseProcessedEvent):
    """End event."""

    type: Literal["end"] = "end"
    reason: str = "conversation_ended"


@dataclass
class StoppedEvent(BaseProcessedEvent):
    """Stopped event."""

    type: Literal["stopped"] = "stopped"


@dataclass
class ToolStartEvent(BaseProcessedEvent):
    """Tool start event."""

    tool_use_id: str = ""
    tool_name: str = ""
    type: Literal["tool_start"] = "tool_start"


@dataclass
class ToolCompleteEvent(BaseProcessedEvent):
    """Tool complete event."""

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
