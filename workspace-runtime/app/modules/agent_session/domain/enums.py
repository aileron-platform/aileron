"""Domain enum type definitions.

Defines all enum types used in the Agent Session system, including:
- SessionStatus: Session status
- TaskStatus: Task status
- AgenticTool: Supported Agentic CLI tools
- MessageType: Message type
- MessageRole: Message role
- PermissionMode/Scope/Status: Permission related
- ContentBlockType: Content block type
"""

from __future__ import annotations

from enum import Enum


class AgentSessionStatus(str, Enum):
    """Agent session status.

    State transitions:
    - idle -> running (executing prompt)
    - running -> idle (execution complete)
    - running -> awaiting_permission (permission required)
    - awaiting_permission -> running (permission approved)
    - awaiting_permission -> idle (permission denied)
    - * -> completed (manually completed)
    - * -> failed (execution failed)
    """

    IDLE = "idle"
    RUNNING = "running"
    AWAITING_PERMISSION = "awaiting_permission"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """Task status.

    State transition diagram:
    created -> running (SDK starts execution)
    running -> awaiting_permission (tool requires permission approval)
    running -> stopping (user requested stop)
    running -> completed (task completed successfully)
    running -> failed (SDK execution error)
    awaiting_permission -> running (permission approved)
    awaiting_permission -> stopping (user requested stop)
    awaiting_permission -> failed (permission denied or timeout)
    stopping -> stopped (SDK stopped successfully)
    stopping -> failed (SDK stop failed)

    Terminal States (Terminal States):
    - completed: Normal completion
    - failed: Execution failed
    - stopped: User actively stopped
    """

    CREATED = "created"
    RUNNING = "running"
    STOPPING = "stopping"
    AWAITING_PERMISSION = "awaiting_permission"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"

    @classmethod
    def terminal_states(cls) -> set["TaskStatus"]:
        """Get all terminal states."""
        return {cls.COMPLETED, cls.FAILED, cls.STOPPED}

    @property
    def is_terminal(self) -> bool:
        """Check if is terminal state."""
        return self in self.terminal_states()

    @property
    def is_active(self) -> bool:
        """Check if is active state (can transition to other states)."""
        return not self.is_terminal


class AgenticTool(str, Enum):
    """Supported Agentic CLI tools.

    Each tool has different characteristics:
    - claude-code: Anthropic Claude Code CLI, supports Thinking Mode and Prompt Caching
    - codex: OpenAI Codex CLI
    - gemini: Google Gemini Code Assist, supports 1M Context Window
    - opencode: Open-source terminal AI assistant, supports local execution
    """

    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class ArchivedReason(str, Enum):
    """Session archive reason."""

    MANUAL = "manual"


class MessageType(str, Enum):
    """Message type.

    - user: User message
    - assistant: AI assistant message
    - system: System message
    - file_history_snapshot: File history snapshot
    - permission_request: Permission request
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FILE_HISTORY_SNAPSHOT = "file-history-snapshot"
    PERMISSION_REQUEST = "permission_request"


class MessageRole(str, Enum):
    """Message role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """Message status.

    - queued: Waiting in queue for execution
    - dispatching: Claimed by queue processor, preparing for execution
    - None/null: Normal message
    """

    QUEUED = "queued"
    DISPATCHING = "dispatching"


class PermissionMode(str, Enum):
    """Claude Code permission mode.

    References agor design, uses Claude SDK native permission modes:
    - default: Prompt for every tool (strictest)
    - acceptEdits: Auto-accept file edits, prompt for other tools
    - bypassPermissions: Allow all operations (no prompt)
    - plan: Plan mode (generate plan but do not execute)
    - dontAsk: Allow all operations (no prompt, no ask)
    - auto: Automatically determine permission mode
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    PLAN = "plan"
    DONT_ASK = "dontAsk"
    AUTO = "auto"


class PermissionScope(str, Enum):
    """Permission scope.

    Defines the effective scope of permission decisions:
    - once: This time only
    - session: Valid during current session (not persisted)
    - project: Entire project
    - user: All projects for this user
    - local: Local (same as project)
    """

    ONCE = "once"
    SESSION = "session"
    PROJECT = "project"
    USER = "user"
    LOCAL = "local"


class PermissionStatus(str, Enum):
    """Permission request status."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ToolDecisionType(str, Enum):
    """Tool Decision type."""

    PERMISSION = "permission"
    USER_INPUT = "user_input"


class ToolDecisionOutcome(str, Enum):
    """Tool Decision outcome."""

    SELECTED = "selected"
    CANCELLED = "cancelled"


class ContentBlockType(str, Enum):
    """Content block type.

    Supported ContentBlock types:
    - text: Text content
    - image: Image content (Claude supported)
    - tool_use: Tool invocation
    - tool_result: Tool result
    - thinking: Thinking process (Claude exclusive)
    - system_status: System status
    - system_complete: Completion notification
    """

    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    SYSTEM_STATUS = "system_status"
    SYSTEM_COMPLETE = "system_complete"


# Codex specific configuration
class CodexSandboxMode(str, Enum):
    """Codex sandbox mode."""

    STRICT = "strict"
    RELAXED = "relaxed"
    OFF = "off"


class CodexApprovalPolicy(str, Enum):
    """Codex approval policy."""

    AUTO = "auto"
    MANUAL = "manual"
    SUGGEST = "suggest"


__all__ = [
    "AgenticTool",
    "AgentSessionStatus",
    "ArchivedReason",
    "CodexApprovalPolicy",
    "CodexSandboxMode",
    "ContentBlockType",
    "MessageRole",
    "MessageStatus",
    "MessageType",
    "PermissionMode",
    "PermissionScope",
    "PermissionStatus",
    "TaskStatus",
]
