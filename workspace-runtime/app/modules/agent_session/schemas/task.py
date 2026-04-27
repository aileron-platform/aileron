"""Task Schema definitions.

Defines API request/response models for tasks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..domain.enums import TaskStatus


# === Request Models ===


class TaskCreate(BaseModel):
    """Create task request."""

    session_id: str
    full_prompt: Optional[str] = None
    created_by: str = "anonymous"


class TaskUpdate(BaseModel):
    """Update task request."""

    status: Optional[TaskStatus] = None
    description: Optional[str] = None
    model: Optional[str] = None


class TaskQuery(BaseModel):
    """Task query parameters."""

    session_id: Optional[str] = None
    status: Optional[TaskStatus] = None
    limit: int = Field(50, ge=1, le=200)
    offset: int = Field(0, ge=0)


# === Response Models ===


class MessageRangeResponse(BaseModel):
    """Message range response."""

    start_index: int
    end_index: int
    start_timestamp: str
    end_timestamp: Optional[str] = None


class PermissionRequestResponse(BaseModel):
    """Permission request response."""

    request_id: str
    tool_name: str
    tool_input: Dict[str, Any]
    tool_use_id: Optional[str] = None
    requested_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None


class TokenUsageSummary(BaseModel):
    """Token usage summary."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    service_tier: Optional[str] = None


class TaskResponse(BaseModel):
    """Task response."""

    task_id: str = Field(alias="id")
    session_id: str
    created_at: datetime
    created_by: str = "anonymous"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus

    # Data blob fields
    description: Optional[str] = None
    full_prompt: Optional[str] = None
    message_range: Optional[MessageRangeResponse] = None
    model: Optional[str] = None
    tool_use_count: int = 0
    duration_ms: Optional[int] = None
    agent_session_id: Optional[str] = None
    computed_context_window: Optional[int] = None
    permission_request: Optional[PermissionRequestResponse] = None
    token_usage: Optional[TokenUsageSummary] = None

    model_config = {"from_attributes": True, "populate_by_name": True, "by_alias": True}

    @classmethod
    def from_entity(cls, entity) -> "TaskResponse":
        """Create response from domain entity."""
        # Create message_range
        message_range = None
        if entity.message_range:
            message_range = MessageRangeResponse(
                start_index=entity.message_range.start_index,
                end_index=entity.message_range.end_index,
                start_timestamp=entity.message_range.start_timestamp,
                end_timestamp=entity.message_range.end_timestamp,
            )

        # Create permission_request
        permission_request = None
        if entity.permission_request:
            pr = entity.permission_request
            permission_request = PermissionRequestResponse(
                request_id=pr.get("request_id", ""),
                tool_name=pr.get("tool_name", ""),
                tool_input=pr.get("tool_input", {}),
                tool_use_id=pr.get("tool_use_id"),
                requested_at=pr.get("requested_at", ""),
                approved_by=pr.get("approved_by"),
                approved_at=pr.get("approved_at"),
            )

        # Extract token usage from raw_sdk_response
        token_usage = None
        if entity.raw_sdk_response:
            token_usage = cls._extract_token_usage(entity.raw_sdk_response)

        return cls(
            id=entity.id,
            session_id=entity.session_id,
            created_at=entity.created_at,
            created_by=entity.created_by,
            started_at=entity.started_at,
            completed_at=entity.completed_at,
            status=entity.status,
            description=entity.description,
            full_prompt=entity.full_prompt,
            message_range=message_range,
            model=entity.model,
            tool_use_count=entity.tool_use_count,
            duration_ms=entity.duration_ms,
            agent_session_id=entity.agent_session_id,
            computed_context_window=entity.computed_context_window,
            permission_request=permission_request,
            token_usage=token_usage,
        )

    @staticmethod
    def _extract_token_usage(raw_response: Dict[str, Any]) -> Optional[TokenUsageSummary]:
        """Extract token usage from raw_sdk_response."""
        sdk_type = raw_response.get("type")
        response = raw_response.get("response", {})

        if sdk_type == "claude":
            usage = response.get("usage", {}) or raw_response.get("usage", {})
            usage_data = raw_response.get("usageData", {}) or {}
            return TokenUsageSummary(
                input_tokens=usage_data.get("inputTokens", usage.get("input_tokens", 0)),
                output_tokens=usage_data.get("outputTokens", usage.get("output_tokens", 0)),
                total_tokens=usage_data.get(
                    "totalTokens",
                    usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                ),
                cache_creation_tokens=usage_data.get(
                    "cacheCreationTokens",
                    usage.get("cache_creation_input_tokens"),
                ),
                cache_read_tokens=usage_data.get(
                    "cacheReadTokens",
                    usage.get("cache_read_input_tokens"),
                ),
                cost_usd=usage_data.get("costUsd", raw_response.get("total_cost_usd")),
                service_tier=usage_data.get("serviceTier"),
            )
        elif sdk_type == "codex":
            turn = response.get("turn", {})
            usage = turn.get("usage", {})
            costs = turn.get("costs", {})
            return TokenUsageSummary(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_usd=costs.get("total_cost", costs.get("total_cost_usd")),
            )
        elif sdk_type == "gemini":
            usage = response.get("usageMetadata", {})
            return TokenUsageSummary(
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
            )
        elif sdk_type == "opencode":
            usage = response.get("usage", {})
            return TokenUsageSummary(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )

        return None


class TaskListResponse(BaseModel):
    """Task list response."""

    items: List[TaskResponse]
    total: int
    limit: int
    offset: int


class StopTaskResponse(BaseModel):
    """Stop task response."""

    success: bool = True
    task_id: str
    status: TaskStatus


__all__ = [
    "MessageRangeResponse",
    "PermissionRequestResponse",
    "StopTaskResponse",
    "TaskCreate",
    "TaskListResponse",
    "TaskQuery",
    "TaskResponse",
    "TaskUpdate",
    "TokenUsageSummary",
]
