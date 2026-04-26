"""Automation task data models"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["active", "paused", "failed", "draft"]
JobTrigger = Literal["cron", "manual", "webhook"]
JobExecutionStatus = Literal[
    "queued",
    "waiting",
    "running",
    "success",
    "failed",
    "cancelled",
    "timeout"
]


class JobNotificationSettings(BaseModel):
    """Task notification settings"""

    email: bool = Field(default=False, description="Enable email notifications")
    slack: bool = Field(default=False, description="Enable Slack notifications")
    webhook: bool = Field(default=False, description="Enable webhook notifications")

    model_config = ConfigDict(populate_by_name=True)


class JobBase(BaseModel):
    """Automation task common fields"""

    name: str = Field(description="Task name")
    description: str = Field(description="Task description")
    owner: str = Field(description="Owner")
    user_id: str = Field(alias="userId", description="User ID who created the task")
    workspace_id: str = Field(alias="workspaceId", description="Target workspace ID")
    prompt: str = Field(description="Task prompt or content")
    status: JobStatus = Field(description="Task status")
    trigger: JobTrigger = Field(description="Trigger condition")
    schedule: str = Field(description="Schedule expression")
    tags: list[str] = Field(default_factory=list, description="Tags")
    notifications: JobNotificationSettings = Field(
        default_factory=JobNotificationSettings, description="Notification settings"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional task settings")
    webhook_api_key: Optional[str] = Field(
        default=None, alias="webhookApiKey", description="Webhook API Key"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobCreateRequest(JobBase):
    """Create automation task request"""

    pass


class JobUpdateRequest(BaseModel):
    """Update automation task request"""

    name: Optional[str] = Field(default=None, description="Task name")
    description: Optional[str] = Field(default=None, description="Task description")
    owner: Optional[str] = Field(default=None, description="Owner")
    user_id: Optional[str] = Field(
        default=None, alias="userId", description="User ID who created the task"
    )
    workspace_id: Optional[str] = Field(
        default=None, alias="workspaceId", description="Target workspace ID"
    )
    prompt: Optional[str] = Field(default=None, description="Task prompt or content")
    status: Optional[JobStatus] = Field(default=None, description="Task status")
    trigger: Optional[JobTrigger] = Field(default=None, description="Trigger condition")
    schedule: Optional[str] = Field(default=None, description="Schedule expression")
    tags: Optional[list[str]] = Field(default=None, description="Tags")
    notifications: Optional[JobNotificationSettings] = Field(
        default=None, description="Notification settings"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Additional task settings"
    )
    webhook_api_key: Optional[str] = Field(
        default=None, alias="webhookApiKey", description="Webhook API Key"
    )

    model_config = ConfigDict(populate_by_name=True)


class AutomationJob(JobBase):
    """Automation task response"""

    id: str = Field(description="Task ID")
    workspace_name: Optional[str] = Field(
        default=None, alias="workspaceName", description="Workspace name"
    )
    created_at: datetime = Field(alias="createdAt", description="Creation time")
    updated_at: datetime = Field(alias="updatedAt", description="Update time")
    last_run_at: Optional[datetime] = Field(
        default=None, alias="lastRunAt", description="Last execution time"
    )
    next_run_at: Optional[datetime] = Field(
        default=None, alias="nextRunAt", description="Next execution time"
    )
    success_rate: float = Field(
        default=0.0, alias="successRate", description="Success rate (0~1)"
    )
    failure_rate: float = Field(
        default=0.0, alias="failureRate", description="Failure rate (0~1)"
    )
    total_executions: int = Field(
        default=0, alias="totalExecutions", description="Total execution count"
    )
    average_duration: int = Field(
        default=0, alias="averageDuration", description="Average execution time (seconds)"
    )
    last_duration: Optional[int] = Field(
        default=None, alias="lastDuration", description="Last execution time (seconds)"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobListResponse(BaseModel):
    """Automation task list response"""

    items: list[AutomationJob] = Field(description="Task list")
    total: int = Field(description="Total count")

    model_config = ConfigDict(populate_by_name=True)


class AutomationMetrics(BaseModel):
    """Automation statistics"""

    active_count: int = Field(alias="activeCount", description="Active task count")
    paused_count: int = Field(alias="pausedCount", description="Paused task count")
    failed_count: int = Field(alias="failedCount", description="Total failed executions")
    draft_count: int = Field(alias="draftCount", description="Draft task count")
    success_rate: float = Field(alias="successRate", description="Overall success rate")
    running_executions: int = Field(
        alias="runningExecutions", description="Running task count"
    )
    queued_executions: int = Field(
        alias="queuedExecutions", description="Queued task count"
    )
    average_duration: float = Field(
        alias="averageDuration", description="Average execution time (seconds)"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobExecution(BaseModel):
    """Task execution record"""

    id: str = Field(description="Execution ID")
    job_id: str = Field(alias="jobId", description="Corresponding task ID")
    status: JobExecutionStatus = Field(description="Execution status")
    trigger: JobTrigger = Field(description="Trigger source")
    started_at: Optional[datetime] = Field(
        default=None, alias="startedAt", description="Start time"
    )
    finished_at: Optional[datetime] = Field(
        default=None, alias="finishedAt", description="Completion time"
    )
    duration: Optional[int] = Field(
        default=None, description="Execution duration (seconds)", ge=0
    )
    session_id: Optional[str] = Field(
        default=None, alias="sessionId", description="Corresponding workspace Session ID"
    )
    error_message: Optional[str] = Field(
        default=None, alias="errorMessage", description="Error message"
    )
    execution_metadata: Optional[dict] = Field(
        default=None, alias="executionMetadata", description="Execution metadata (includes error details, etc.)"
    )
    summary: str = Field(description="Execution summary")
    queue_position: Optional[int] = Field(
        default=None, alias="queuePosition", description="Queue position (1-based)"
    )
    queued_at: Optional[datetime] = Field(
        default=None, alias="queuedAt", description="Queued time"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobExecutionListResponse(BaseModel):
    """Task execution record list response"""

    items: list[JobExecution] = Field(description="Execution record list")
    total: int = Field(description="Total count")

    model_config = ConfigDict(populate_by_name=True)


class JobExecutionCreateRequest(BaseModel):
    """Create execution record request"""

    status: JobExecutionStatus = Field(description="Execution status")
    trigger: JobTrigger = Field(description="Trigger source")
    summary: str = Field(description="Execution summary")
    duration: Optional[int] = Field(default=None, description="Execution duration (seconds)", ge=0)
    session_id: Optional[str] = Field(
        default=None, alias="sessionId", description="Corresponding workspace Session ID"
    )
    error_message: Optional[str] = Field(
        default=None, alias="errorMessage", description="Error message"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobStatusUpdate(BaseModel):
    """Update task status request"""

    status: JobStatus = Field(description="New task status")

    model_config = ConfigDict(populate_by_name=True)


class JobCalendarEvent(BaseModel):
    """Task calendar event"""

    id: str = Field(description="Event ID")
    job_id: str = Field(alias="jobId", description="Task ID")
    title: str = Field(description="Display name")
    start: datetime = Field(description="Start time")
    end: datetime = Field(description="End time")
    status: JobExecutionStatus = Field(description="Expected status")

    model_config = ConfigDict(populate_by_name=True)


class JobCalendarResponse(BaseModel):
    """Task calendar event response"""

    items: list[JobCalendarEvent] = Field(description="Calendar event list")
    total: int = Field(description="Total count")

    model_config = ConfigDict(populate_by_name=True)


class QueuePosition(BaseModel):
    """Queue position information"""

    execution_id: str = Field(alias="executionId", description="Execution record ID")
    position: int = Field(description="Queue position (1-based)")
    total: int = Field(description="Queue total length")
    estimated_wait_seconds: Optional[int] = Field(
        default=None, alias="estimatedWaitSeconds", description="Estimated wait time (seconds)"
    )

    model_config = ConfigDict(populate_by_name=True)


class WorkspaceQueueResponse(BaseModel):
    """Workspace queue response"""

    workspace_id: str = Field(alias="workspaceId", description="Workspace ID")
    queue_length: int = Field(alias="queueLength", description="Queue length")
    executions: list[JobExecution] = Field(description="Queued execution records")

    model_config = ConfigDict(populate_by_name=True)


class ExecutionCancelResponse(BaseModel):
    """Cancel execution response"""

    execution_id: str = Field(alias="executionId", description="Execution record ID")
    status: str = Field(description="Current status")
    message: str = Field(description="Response message")
    cancelled: bool = Field(description="Successfully cancelled")

    model_config = ConfigDict(populate_by_name=True)


__all__ = [
    "JobNotificationSettings",
    "AutomationJob",
    "JobBase",
    "JobCalendarEvent",
    "JobCalendarResponse",
    "JobCreateRequest",
    "JobListResponse",
    "JobStatus",
    "JobStatusUpdate",
    "JobTrigger",
    "JobUpdateRequest",
    "AutomationMetrics",
    "JobExecution",
    "JobExecutionCreateRequest",
    "JobExecutionListResponse",
    "JobExecutionStatus",
    "QueuePosition",
    "WorkspaceQueueResponse",
    "ExecutionCancelResponse",
]

