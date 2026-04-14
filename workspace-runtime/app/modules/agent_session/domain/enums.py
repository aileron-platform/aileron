"""Domain 列舉類型定義.

定義 Agent Session 系統中使用的所有列舉類型，包括：
- SessionStatus: 會話狀態
- TaskStatus: 任務狀態
- AgenticTool: 支援的 Agentic CLI 工具
- MessageType: 訊息類型
- MessageRole: 訊息角色
- PermissionMode/Scope/Status: 權限相關
- ContentBlockType: 內容區塊類型
"""

from __future__ import annotations

from enum import Enum


class AgentSessionStatus(str, Enum):
    """Agent 會話狀態.

    狀態轉換：
    - idle -> running (執行 prompt)
    - running -> idle (執行完成)
    - running -> awaiting_permission (需要權限)
    - awaiting_permission -> running (權限批准)
    - awaiting_permission -> idle (權限拒絕)
    - * -> completed (手動完成)
    - * -> failed (執行失敗)
    """

    IDLE = "idle"
    RUNNING = "running"
    AWAITING_PERMISSION = "awaiting_permission"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatus(str, Enum):
    """任務狀態.

    狀態轉換圖:
    created -> running (SDK 開始執行)
    running -> awaiting_permission (工具需要權限批准)
    running -> stopping (使用者請求停止)
    running -> completed (任務成功完成)
    running -> failed (SDK 執行錯誤)
    awaiting_permission -> running (權限批准)
    awaiting_permission -> stopping (使用者請求停止)
    awaiting_permission -> failed (權限拒絕或超時)
    stopping -> stopped (SDK 成功停止)
    stopping -> failed (SDK 停止失敗)

    終止狀態 (Terminal States):
    - completed: 正常完成
    - failed: 執行失敗
    - stopped: 使用者主動停止
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
        """取得所有終止狀態."""
        return {cls.COMPLETED, cls.FAILED, cls.STOPPED}

    @property
    def is_terminal(self) -> bool:
        """檢查是否為終止狀態."""
        return self in self.terminal_states()

    @property
    def is_active(self) -> bool:
        """檢查是否為活躍狀態 (可轉換到其他狀態)."""
        return not self.is_terminal


class AgenticTool(str, Enum):
    """支援的 Agentic CLI 工具.

    每個工具有不同的特性：
    - claude-code: Anthropic Claude Code CLI, 支援 Thinking Mode 和 Prompt Caching
    - codex: OpenAI Codex CLI
    - gemini: Google Gemini Code Assist, 支援 1M Context Window
    - opencode: Open-source terminal AI assistant, 支援本地執行
    """

    CLAUDE_CODE = "claude-code"
    CODEX = "codex"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class ArchivedReason(str, Enum):
    """會話封存原因."""

    MANUAL = "manual"


class MessageType(str, Enum):
    """訊息類型.

    - user: 使用者訊息
    - assistant: AI 助手訊息
    - system: 系統訊息
    - file_history_snapshot: 檔案歷史快照
    - permission_request: 權限請求
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FILE_HISTORY_SNAPSHOT = "file-history-snapshot"
    PERMISSION_REQUEST = "permission_request"


class MessageRole(str, Enum):
    """訊息角色."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    """訊息狀態.

    - queued: 在佇列中等待執行
    - None/null: 正常訊息
    """

    QUEUED = "queued"


class PermissionMode(str, Enum):
    """Claude Code 權限模式.

    參考 agor 設計，使用 Claude SDK 原生權限模式：
    - default: 每個工具都提示（最嚴格）
    - acceptEdits: 自動接受檔案編輯，其他工具提示
    - bypassPermissions: 允許所有操作（不提示）
    - plan: 計劃模式（生成計劃但不執行）
    - dontAsk: 允許所有操作（不提示、不詢問）
    - auto: 自動決定權限模式
    """

    DEFAULT = "default"
    ACCEPT_EDITS = "acceptEdits"
    BYPASS_PERMISSIONS = "bypassPermissions"
    PLAN = "plan"
    DONT_ASK = "dontAsk"
    AUTO = "auto"


class PermissionScope(str, Enum):
    """權限範圍.

    定義權限決策的生效範圍：
    - once: 僅此次
    - session: 當前會話期間有效（不持久化）
    - project: 整個專案
    - user: 該使用者的所有專案
    - local: 本地 (同 project)
    """

    ONCE = "once"
    SESSION = "session"
    PROJECT = "project"
    USER = "user"
    LOCAL = "local"


class PermissionStatus(str, Enum):
    """權限請求狀態."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ToolDecisionType(str, Enum):
    """Tool Decision 類型."""

    PERMISSION = "permission"
    USER_INPUT = "user_input"


class ToolDecisionOutcome(str, Enum):
    """Tool Decision 結果."""

    SELECTED = "selected"
    CANCELLED = "cancelled"


class ContentBlockType(str, Enum):
    """內容區塊類型.

    支援的 ContentBlock 類型：
    - text: 文字內容
    - image: 影像內容 (Claude 支援)
    - tool_use: 工具調用
    - tool_result: 工具結果
    - thinking: 思考過程 (Claude 專屬)
    - system_status: 系統狀態
    - system_complete: 完成通知
    """

    TEXT = "text"
    IMAGE = "image"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    SYSTEM_STATUS = "system_status"
    SYSTEM_COMPLETE = "system_complete"


# Codex 專用配置
class CodexSandboxMode(str, Enum):
    """Codex sandbox 模式."""

    STRICT = "strict"
    RELAXED = "relaxed"
    OFF = "off"


class CodexApprovalPolicy(str, Enum):
    """Codex 批准策略."""

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
