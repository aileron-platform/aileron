"""Domain 值對象定義.

值對象 (Value Objects) 是不可變的資料結構，用於封裝領域概念。
包括：
- PermissionConfig: 權限配置
- ModelConfig: 模型配置
- MessageRange: 訊息範圍
- ToolUse: 工具使用記錄
- PermissionRequestContent: 權限請求內容
- TokenUsage: Token 使用量
- ContextWindowStatus: Context Window 狀態
- ToolCapabilities: 工具能力描述
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .enums import (
    CodexApprovalPolicy,
    CodexSandboxMode,
    PermissionMode,
    PermissionScope,
    PermissionStatus,
)


@dataclass(frozen=True, slots=True)
class CodexPermissionConfig:
    """Codex 專用權限配置."""

    sandbox_mode: CodexSandboxMode = CodexSandboxMode.STRICT
    approval_policy: CodexApprovalPolicy = CodexApprovalPolicy.MANUAL
    network_access: bool = False


@dataclass(frozen=True, slots=True)
class PermissionConfig:
    """權限配置.

    定義會話的權限行為，不同工具有不同的配置選項。
    """

    mode: PermissionMode = PermissionMode.DEFAULT
    codex: Optional[CodexPermissionConfig] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PermissionConfig":
        """從字典建立配置."""
        if not data:
            return cls()

        codex_data = data.get("codex")
        codex_config = None
        if codex_data:
            codex_config = CodexPermissionConfig(
                sandbox_mode=CodexSandboxMode(codex_data.get("sandboxMode", "strict")),
                approval_policy=CodexApprovalPolicy(codex_data.get("approvalPolicy", "manual")),
                network_access=codex_data.get("networkAccess", False),
            )

        return cls(
            mode=PermissionMode(data.get("mode", "default")),
            codex=codex_config,
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {"mode": self.mode.value}
        if self.codex:
            result["codex"] = {
                "sandboxMode": self.codex.sandbox_mode.value,
                "approvalPolicy": self.codex.approval_policy.value,
                "networkAccess": self.codex.network_access,
            }
        return result


@dataclass(frozen=True, slots=True)
class ModelConfig:
    """模型配置.

    定義會話使用的 AI 模型設定。
    """

    mode: str = "alias"  # 'alias' | 'exact'
    model: str = ""
    updated_at: Optional[str] = None
    notes: Optional[str] = None
    thinking_mode: Optional[str] = None  # 'auto' | 'manual' | 'off'
    manual_thinking_tokens: Optional[int] = None
    provider: Optional[str] = None  # OpenCode provider ID

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ModelConfig":
        """從字典建立配置."""
        if not data:
            return cls()

        return cls(
            mode=data.get("mode", "alias"),
            model=data.get("model", ""),
            updated_at=data.get("updated_at"),
            notes=data.get("notes"),
            thinking_mode=data.get("thinkingMode"),
            manual_thinking_tokens=data.get("manualThinkingTokens"),
            provider=data.get("provider"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {
            "mode": self.mode,
            "model": self.model,
        }
        if self.updated_at:
            result["updated_at"] = self.updated_at
        if self.notes:
            result["notes"] = self.notes
        if self.thinking_mode:
            result["thinkingMode"] = self.thinking_mode
        if self.manual_thinking_tokens:
            result["manualThinkingTokens"] = self.manual_thinking_tokens
        if self.provider:
            result["provider"] = self.provider
        return result


@dataclass(frozen=True, slots=True)
class MessageRange:
    """訊息範圍.

    追蹤 Task 對應的訊息索引範圍。
    """

    start_index: int
    end_index: int
    start_timestamp: str
    end_timestamp: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> Optional["MessageRange"]:
        """從字典建立."""
        if not data:
            return None

        return cls(
            start_index=data.get("start_index", 0),
            end_index=data.get("end_index", 0),
            start_timestamp=data.get("start_timestamp", ""),
            end_timestamp=data.get("end_timestamp"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {
            "start_index": self.start_index,
            "end_index": self.end_index,
            "start_timestamp": self.start_timestamp,
        }
        if self.end_timestamp:
            result["end_timestamp"] = self.end_timestamp
        return result


@dataclass(frozen=True, slots=True)
class ToolUse:
    """工具使用記錄.

    記錄 AI 助手調用的工具資訊。
    """

    id: str
    name: str
    input: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolUse":
        """從字典建立."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            input=data.get("input", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        return {
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }


@dataclass(frozen=True, slots=True)
class PermissionRequestContent:
    """權限請求內容.

    用於 permission_request 類型訊息的內容結構。
    """

    request_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    status: PermissionStatus = PermissionStatus.PENDING
    tool_use_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    scope: Optional[PermissionScope] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    decision_type: Optional[str] = None
    outcome: Optional[str] = None
    option_id: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None
    raw_tool_call: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    content: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PermissionRequestContent":
        """從字典建立."""
        status = data.get("status", "pending")
        scope = data.get("scope")

        return cls(
            request_id=data.get("request_id", ""),
            tool_name=data.get("tool_name", ""),
            tool_input=data.get("tool_input", {}),
            status=PermissionStatus(status) if status else PermissionStatus.PENDING,
            tool_use_id=data.get("tool_use_id"),
            tool_call_id=data.get("tool_call_id"),
            scope=PermissionScope(scope) if scope else None,
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            decision_type=data.get("decision_type"),
            outcome=data.get("outcome"),
            option_id=data.get("option_id"),
            options=data.get("options"),
            raw_tool_call=data.get("raw_tool_call"),
            reason=data.get("reason"),
            content=data.get("content"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "status": self.status.value,
        }
        if self.tool_use_id:
            result["tool_use_id"] = self.tool_use_id
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.scope:
            result["scope"] = self.scope.value
        if self.approved_by:
            result["approved_by"] = self.approved_by
        if self.approved_at:
            result["approved_at"] = self.approved_at
        if self.decision_type:
            result["decision_type"] = self.decision_type
        if self.outcome:
            result["outcome"] = self.outcome
        if self.option_id:
            result["option_id"] = self.option_id
        if self.options is not None:
            result["options"] = self.options
        if self.raw_tool_call is not None:
            result["raw_tool_call"] = self.raw_tool_call
        if self.reason:
            result["reason"] = self.reason
        if self.content is not None:
            result["content"] = self.content
        return result


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token 使用量.

    統一的 token 使用量結構，支援不同 SDK 的 token 計算。
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_creation_input_tokens: Optional[int] = None  # Claude 專屬
    cache_read_input_tokens: Optional[int] = None  # Claude 專屬

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TokenUsage":
        """從字典建立."""
        if not data:
            return cls()

        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            cache_creation_input_tokens=data.get("cache_creation_input_tokens"),
            cache_read_input_tokens=data.get("cache_read_input_tokens"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.cache_creation_input_tokens is not None:
            result["cache_creation_input_tokens"] = self.cache_creation_input_tokens
        if self.cache_read_input_tokens is not None:
            result["cache_read_input_tokens"] = self.cache_read_input_tokens
        return result


@dataclass(frozen=True, slots=True)
class ContextWindowStatus:
    """Context Window 狀態.

    追蹤會話的 context window 使用情況。
    """

    current_usage: int = 0
    limit: int = 200000  # 預設 200K
    usage_percentage: float = 0.0
    needs_compaction: bool = False
    last_update_at: Optional[str] = None

    @classmethod
    def from_usage(
        cls,
        current_usage: int,
        limit: int = 200000,
        last_update_at: Optional[str] = None,
    ) -> "ContextWindowStatus":
        """從使用量建立狀態."""
        percentage = (current_usage / limit * 100) if limit > 0 else 0.0
        needs_compaction = percentage >= 80.0

        return cls(
            current_usage=current_usage,
            limit=limit,
            usage_percentage=percentage,
            needs_compaction=needs_compaction,
            last_update_at=last_update_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        result: Dict[str, Any] = {
            "current_usage": self.current_usage,
            "limit": self.limit,
            "usage_percentage": self.usage_percentage,
            "needs_compaction": self.needs_compaction,
        }
        if self.last_update_at:
            result["last_update_at"] = self.last_update_at
        return result


@dataclass(frozen=True, slots=True)
class ToolCapabilities:
    """工具能力描述.

    描述 Agentic Tool 的能力特性。
    """

    name: str
    streaming: bool = True
    thinking: bool = False
    multimodal: bool = False
    max_context_window: int = 200000
    prompt_caching: bool = False
    local_execution: bool = False
    built_in_tools: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典."""
        return {
            "name": self.name,
            "streaming": self.streaming,
            "thinking": self.thinking,
            "multimodal": self.multimodal,
            "max_context_window": self.max_context_window,
            "prompt_caching": self.prompt_caching,
            "local_execution": self.local_execution,
            "built_in_tools": self.built_in_tools,
        }


# 預定義的工具能力
TOOL_CAPABILITIES: Dict[str, ToolCapabilities] = {
    "claude-code": ToolCapabilities(
        name="Claude Code",
        streaming=True,
        thinking=True,
        multimodal=True,
        max_context_window=200000,
        prompt_caching=True,
        local_execution=False,
        built_in_tools=[
            "read_file",
            "write_file",
            "edit_file",
            "list_directory",
            "bash",
            "grep",
            "glob",
            "task",
        ],
    ),
    "codex": ToolCapabilities(
        name="Codex",
        streaming=True,
        thinking=False,
        multimodal=False,
        max_context_window=200000,
        prompt_caching=False,
        local_execution=False,
        built_in_tools=["shell", "file_read", "file_write", "apply_patch"],
    ),
    "gemini": ToolCapabilities(
        name="Gemini",
        streaming=True,
        thinking=False,
        multimodal=True,
        max_context_window=1000000,  # 1M context
        prompt_caching=False,
        local_execution=False,
        built_in_tools=["code_execution", "file_search", "web_search"],
    ),
    "opencode": ToolCapabilities(
        name="OpenCode",
        streaming=False,
        thinking=False,
        multimodal=False,
        max_context_window=128000,  # 依模型而定
        prompt_caching=False,
        local_execution=True,
        built_in_tools=["shell", "read_file", "write_file"],
    ),
}


def get_tool_capabilities(tool: str) -> Optional[ToolCapabilities]:
    """取得工具能力描述."""
    return TOOL_CAPABILITIES.get(tool)


__all__ = [
    "CodexPermissionConfig",
    "ContextWindowStatus",
    "MessageRange",
    "ModelConfig",
    "PermissionConfig",
    "PermissionRequestContent",
    "TokenUsage",
    "ToolCapabilities",
    "ToolUse",
    "TOOL_CAPABILITIES",
    "get_tool_capabilities",
]
