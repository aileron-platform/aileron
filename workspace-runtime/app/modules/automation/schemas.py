"""Typed Runtime-side Automation protocol contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CompletionStatus = Literal["success", "failed", "cancelled"]


class AutomationAgentConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: str | None = None
    permission_mode: Literal["bypassPermissions"] = Field(
        "bypassPermissions", alias="permissionMode"
    )


class ClaimResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    execution_id: str = Field(alias="executionId")
    job_id: str = Field(alias="jobId")
    workspace_id: str = Field(alias="workspaceId")
    trigger: str
    scheduled_for: datetime = Field(alias="scheduledFor")
    principal_user_id: str = Field(alias="principalUserId")
    prompt: str
    agentic_tool: str = Field(alias="agenticTool")
    model: str
    agent_config: AutomationAgentConfigSnapshot = Field(alias="agentConfig")
    worktree_key: str = Field(alias="worktreeKey")
    runner_instance_id: UUID = Field(alias="runnerInstanceId")
    claim_request_id: UUID = Field(alias="claimRequestId")
    cancel_requested_at: datetime | None = Field(
        default=None, alias="cancelRequestedAt"
    )


class CompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    runner_instance_id: UUID = Field(alias="runnerInstanceId")
    claim_request_id: UUID = Field(alias="claimRequestId")
    status: CompletionStatus
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")


class CompletionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["success", "failed", "cancelled", "running"]


class CancelExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    runner_instance_id: UUID = Field(alias="runnerInstanceId")
    claim_request_id: UUID = Field(alias="claimRequestId")


__all__ = [
    "AutomationAgentConfigSnapshot",
    "CancelExecutionRequest",
    "ClaimResponse",
    "CompletionRequest",
    "CompletionResponse",
    "CompletionStatus",
]
