"""Automation wire contracts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr


class AutomationJobStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class AutomationExecutionStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AutomationTrigger(StrEnum):
    CRON = "cron"
    MANUAL = "manual"
    WEBHOOK = "webhook"
    AT = "at"
    EVERY = "every"


class AutomationNotificationStatus(StrEnum):
    DELIVERED = "delivered"
    FAILED = "failed"


class AutomationAgentConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str | None = None


class AutomationAgentConfigSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    mode: str | None = None
    permission_mode: Literal["bypassPermissions"] = Field(
        "bypassPermissions", alias="permissionMode"
    )


class AutomationNotificationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_api_key: SecretStr | None = None
    delivery_webhook_url: HttpUrl | None = None
    failure_destination: HttpUrl | None = None


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    description: str | None = None
    workspace_id: str = Field(alias="workspaceId")
    prompt: str
    trigger: AutomationTrigger
    schedule: str
    exact: bool = False
    agentic_tool: str | None = Field(default=None, alias="agenticTool")
    model: str | None = None
    agent_config: AutomationAgentConfigInput | None = Field(
        default=None, alias="agentConfig"
    )
    webhook_api_key: SecretStr | None = Field(default=None, alias="webhookApiKey")
    delivery_webhook_url: HttpUrl | None = Field(
        default=None, alias="deliveryWebhookUrl"
    )
    failure_destination: HttpUrl | None = Field(
        default=None, alias="failureDestination"
    )


class JobUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    status: Literal["active", "paused"] | None = None
    trigger: AutomationTrigger | None = None
    schedule: str | None = None
    exact: bool | None = None
    agentic_tool: str | None = Field(default=None, alias="agenticTool")
    model: str | None = None
    agent_config: AutomationAgentConfigInput | None = Field(
        default=None, alias="agentConfig"
    )
    webhook_api_key: SecretStr | None = Field(default=None, alias="webhookApiKey")
    delivery_webhook_url: HttpUrl | None = Field(
        default=None, alias="deliveryWebhookUrl"
    )
    failure_destination: HttpUrl | None = Field(
        default=None, alias="failureDestination"
    )


class AutomationJob(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, from_attributes=True
    )

    id: str
    workspace_id: str = Field(alias="workspaceId")
    creator_user_id: str = Field(alias="creatorUserId")
    creator_display_name: str = Field(alias="creatorDisplayName")
    name: str
    description: str | None = None
    prompt: str
    status: AutomationJobStatus
    trigger: AutomationTrigger
    schedule: str
    exact: bool
    agentic_tool: str = Field(alias="agenticTool")
    model: str
    agent_config: AutomationAgentConfigSnapshot = Field(alias="agentConfig")
    worktree_key: str = Field(alias="worktreeKey")
    worktree_branch: str = Field(alias="worktreeBranch")
    webhook_configured: bool = Field(alias="webhookConfigured")
    delivery_webhook_url: HttpUrl | None = Field(
        default=None, alias="deliveryWebhookUrl"
    )
    failure_destination: HttpUrl | None = Field(
        default=None, alias="failureDestination"
    )
    next_run_at: datetime | None = Field(default=None, alias="nextRunAt")
    last_run_at: datetime | None = Field(default=None, alias="lastRunAt")
    total_executions: int = Field(default=0, alias="totalExecutions")
    success_rate: float = Field(default=0.0, alias="successRate")
    average_duration: float = Field(default=0.0, alias="averageDuration")
    last_duration: int | None = Field(default=None, alias="lastDuration")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")


class AutomationJobListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[AutomationJob]
    total: int


class AutomationExecution(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, from_attributes=True
    )

    id: str
    job_id: str = Field(alias="jobId")
    workspace_id: str = Field(alias="workspaceId")
    status: AutomationExecutionStatus
    trigger: AutomationTrigger
    scheduled_for: datetime = Field(alias="scheduledFor")
    queued_at: datetime | None = Field(default=None, alias="queuedAt")
    runner_instance_id: str | None = Field(default=None, alias="runnerInstanceId")
    claim_request_id: str | None = Field(default=None, alias="claimRequestId")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    cancel_requested_at: datetime | None = Field(
        default=None, alias="cancelRequestedAt"
    )
    principal_user_id_snapshot: str = Field(alias="principalUserIdSnapshot")
    prompt_snapshot: str = Field(alias="promptSnapshot")
    agentic_tool_snapshot: str = Field(alias="agenticToolSnapshot")
    model_snapshot: str = Field(alias="modelSnapshot")
    agent_config_snapshot: AutomationAgentConfigSnapshot = Field(
        alias="agentConfigSnapshot"
    )
    worktree_key_snapshot: str = Field(alias="worktreeKeySnapshot")
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")
    notification_status: AutomationNotificationStatus | None = Field(
        default=None, alias="notificationStatus"
    )
    queue_position: int | None = Field(default=None, alias="queuePosition")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AutomationExecutionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[AutomationExecution]
    total: int


class AutomationExecutionPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[AutomationExecution]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class ClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    workspace_id: str = Field(alias="workspaceId")
    runner_instance_id: UUID = Field(alias="runnerInstanceId")
    claim_request_id: UUID = Field(alias="claimRequestId")


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
    status: Literal["success", "failed", "cancelled"]
    error_code: str | None = Field(default=None, alias="errorCode")
    error_message: str | None = Field(default=None, alias="errorMessage")


class ReconcileRestartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    workspace_id: str = Field(alias="workspaceId")
    new_runner_instance_id: UUID = Field(alias="newRunnerInstanceId")


__all__ = [
    "AutomationAgentConfigInput",
    "AutomationAgentConfigSnapshot",
    "AutomationExecution",
    "AutomationExecutionListResponse",
    "AutomationExecutionStatus",
    "AutomationJob",
    "AutomationJobListResponse",
    "AutomationJobStatus",
    "AutomationNotificationConfig",
    "AutomationNotificationStatus",
    "AutomationTrigger",
    "ClaimRequest",
    "ClaimResponse",
    "CompletionRequest",
    "JobCreateRequest",
    "JobUpdateRequest",
    "ReconcileRestartRequest",
]
