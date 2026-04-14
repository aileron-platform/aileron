"""Agent Session Schema 定義.

定義會話相關的 API 請求/回應模型。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..domain.enums import (
    AgenticTool,
    PermissionMode,
    PermissionScope,
    AgentSessionStatus,
    ToolDecisionType,
    ToolDecisionOutcome,
)


# === 請求模型 ===


class PermissionConfigCreate(BaseModel):
    """權限配置建立請求."""

    mode: PermissionMode = PermissionMode.DEFAULT
    codex: Optional[Dict[str, Any]] = None


class ModelConfigCreate(BaseModel):
    """模型配置建立請求."""

    mode: str = "alias"
    model: str = ""
    thinking_mode: Optional[str] = Field(None, alias="thinkingMode")
    manual_thinking_tokens: Optional[int] = Field(None, alias="manualThinkingTokens")
    provider: Optional[str] = None

    model_config = {"populate_by_name": True}


class AgentSessionCreate(BaseModel):
    """建立會話請求."""

    workspace_id: str
    agentic_tool: AgenticTool = AgenticTool.CLAUDE_CODE
    source: str = "user"
    instruction: Optional[str] = None
    user_id: Optional[str] = None
    permission_config: Optional[PermissionConfigCreate] = None
    model_settings: Optional[ModelConfigCreate] = Field(None, alias="model_config")
    title: Optional[str] = None
    context_files: List[str] = Field(default_factory=list)


class AgentSessionUpdate(BaseModel):
    """更新會話請求."""

    status: Optional[AgentSessionStatus] = None
    title: Optional[str] = None
    archived: Optional[bool] = None
    archived_reason: Optional[str] = None
    permission_config: Optional[PermissionConfigCreate] = None
    model_settings: Optional[ModelConfigCreate] = Field(None, alias="model_config")


class AgentSessionQuery(BaseModel):
    """會話查詢參數."""

    workspace_id: Optional[str] = None
    status: Optional[AgentSessionStatus] = None
    agentic_tool: Optional[AgenticTool] = None
    source: Optional[str] = None
    archived: bool = False
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


class PromptRequest(BaseModel):
    """執行 Prompt 請求."""

    prompt: str
    permission_mode: Optional[PermissionMode] = None
    images: Optional[List[Dict[str, Any]]] = None
    stream: bool = True
    thinking_mode: Optional[str] = None  # "enabled", "disabled", "auto"
    thinking_budget: Optional[int] = None  # Token budget for thinking
    automation_execution_id: Optional[str] = None  # 自動化執行 ID（用於完成通知）


class PermissionDecisionRequest(BaseModel):
    """權限決策請求（相容舊版 API）.

    Deprecated: 新流程使用 ToolDecisionRequest。
    """

    request_id: str
    task_id: str
    allow: bool
    remember: bool = False
    scope: PermissionScope = PermissionScope.ONCE
    decided_by: str
    reason: Optional[str] = None


class ToolDecisionRequest(BaseModel):
    """Tool Decision 請求."""

    request_id: str
    task_id: str
    decision_type: ToolDecisionType
    outcome: ToolDecisionOutcome
    option_id: Optional[str] = None
    decided_by: str
    scope: Optional[PermissionScope] = None
    reason: Optional[str] = None
    content: Optional[str] = None


class ToolDecisionResponse(BaseModel):
    """Tool Decision 回應."""

    success: bool
    request_id: str
    outcome: ToolDecisionOutcome
    option_id: Optional[str] = None
    hooks_resolved: bool
    db_updated: bool


class ToolResultRequest(BaseModel):
    """工具結果請求 - 用於使用者互動工具如 AskUserQuestion."""

    tool_use_id: str
    task_id: str
    content: str
    is_error: bool = False


# === 回應模型 ===


class PermissionConfigResponse(BaseModel):
    """權限配置回應."""

    mode: str
    codex: Optional[Dict[str, Any]] = None


class ModelConfigResponse(BaseModel):
    """模型配置回應."""

    mode: str
    model: str
    updated_at: Optional[str] = None
    thinking_mode: Optional[str] = Field(None, alias="thinkingMode")
    manual_thinking_tokens: Optional[int] = Field(None, alias="manualThinkingTokens")
    provider: Optional[str] = None

    model_config = {"populate_by_name": True}


class ContextWindowResponse(BaseModel):
    """Context Window 狀態回應."""

    current_usage: int = 0
    limit: int = 200000
    usage_percentage: float = 0.0
    needs_compaction: bool = False
    last_update_at: Optional[str] = None


class AgentSessionResponse(BaseModel):
    """會話回應."""

    session_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: str = "anonymous"

    status: AgentSessionStatus
    agentic_tool: AgenticTool
    workspace_id: str
    source: str = "user"
    ready_for_prompt: bool = False
    archived: bool = False
    archived_reason: Optional[str] = None

    # Data blob 欄位
    agentic_tool_version: Optional[str] = None
    sdk_session_id: Optional[str] = None
    title: Optional[str] = None
    tasks: List[str] = Field(default_factory=list)
    message_count: int = 0
    context_files: List[str] = Field(default_factory=list)

    permission_config: Optional[PermissionConfigResponse] = None
    model_settings: Optional[ModelConfigResponse] = None
    context_window: Optional[ContextWindowResponse] = None

    model_config = {"from_attributes": True, "populate_by_name": True}

    @classmethod
    def from_entity(cls, entity) -> "AgentSessionResponse":
        """從領域實體建立回應."""
        # 建立 context_window
        context_window = None
        if entity.current_context_usage is not None:
            limit = entity.context_window_limit or 200000
            usage = entity.current_context_usage
            percentage = (usage / limit * 100) if limit > 0 else 0.0
            context_window = ContextWindowResponse(
                current_usage=usage,
                limit=limit,
                usage_percentage=percentage,
                needs_compaction=percentage >= 80.0,
                last_update_at=entity.last_context_update_at,
            )

        # 建立 permission_config
        permission_config = None
        if entity.permission_config:
            permission_config = PermissionConfigResponse(
                mode=entity.permission_config.mode.value,
                codex=entity.permission_config.codex.__dict__ if entity.permission_config.codex else None,
            )

        # 建立 model_settings
        model_settings = None
        if entity.model_settings:
            model_settings = ModelConfigResponse(
                mode=entity.model_settings.mode,
                model=entity.model_settings.model,
                updated_at=entity.model_settings.updated_at,
                thinkingMode=entity.model_settings.thinking_mode,
                manualThinkingTokens=entity.model_settings.manual_thinking_tokens,
                provider=entity.model_settings.provider,
            )

        return cls(
            session_id=entity.id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            created_by=entity.created_by,
            status=entity.status,
            agentic_tool=entity.agentic_tool,
            workspace_id=entity.workspace_id,
            source=entity.source,
            ready_for_prompt=entity.ready_for_prompt,
            archived=entity.archived,
            archived_reason=entity.archived_reason.value if entity.archived_reason else None,
            agentic_tool_version=entity.agentic_tool_version,
            sdk_session_id=entity.sdk_session_id,
            title=entity.title,
            tasks=entity.tasks,
            message_count=entity.message_count,
            context_files=entity.context_files,
            permission_config=permission_config,
            model_settings=model_settings,
            context_window=context_window,
        )


class AgentSessionListResponse(BaseModel):
    """會話列表回應."""

    items: List[AgentSessionResponse]
    total: int
    limit: int
    offset: int


class TokenUsageResponse(BaseModel):
    """Token 使用量回應."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    context_window: ContextWindowResponse
    estimated_cost: Optional[float] = None


class PromptResponse(BaseModel):
    """執行 Prompt 回應."""

    success: bool = True
    task_id: Optional[str] = None  # Queued message 沒有 task_id
    status: str = "running"  # 可能是 "running" 或 "queued"
    streaming: bool = True
    queued: Optional[bool] = None  # 是否進入 queue
    message_id: Optional[str] = None  # Queued message ID
    queue_position: Optional[int] = None  # Queue 位置


class CurrentExecutionResponse(BaseModel):
    """當前執行狀態回應."""

    has_active_execution: bool
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    agentic_tool: Optional[AgenticTool] = None
    started_at: Optional[datetime] = None


class ActiveRequestsResponse(BaseModel):
    """活躍請求回應."""

    has_active_requests: bool
    active_count: int = 0
    current_task_id: Optional[str] = None


__all__ = [
    "ActiveRequestsResponse",
    "AgentSessionCreate",
    "AgentSessionListResponse",
    "AgentSessionQuery",
    "AgentSessionResponse",
    "AgentSessionUpdate",
    "ContextWindowResponse",
    "CurrentExecutionResponse",
    "ModelConfigCreate",
    "ModelConfigResponse",
    "PermissionConfigCreate",
    "PermissionConfigResponse",
    "PermissionDecisionRequest",
    "PromptRequest",
    "PromptResponse",
    "TokenUsageResponse",
    "ToolDecisionRequest",
    "ToolDecisionResponse",
    "ToolResultRequest",
]
