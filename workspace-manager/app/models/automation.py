"""自動化任務資料模型"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["active", "paused", "failed", "draft"]
JobTrigger = Literal["cron", "manual", "webhook"]
JobExecutionStatus = Literal[
    "queued",      # 已加入 Celery 佇列，等待 Worker 處理
    "waiting",     # 等待工作區鎖釋放（排隊中）
    "running",     # 正在執行
    "success",     # 執行成功
    "failed",      # 執行失敗
    "cancelled",   # 已取消（使用者主動取消）
    "timeout"      # 執行超時
]


class JobNotificationSettings(BaseModel):
    """任務通知設定"""

    email: bool = Field(default=False, description="是否啟用 Email 通知")
    slack: bool = Field(default=False, description="是否啟用 Slack 通知")
    webhook: bool = Field(default=False, description="是否啟用 Webhook 通知")

    model_config = ConfigDict(populate_by_name=True)


class JobBase(BaseModel):
    """自動化任務共用欄位"""

    name: str = Field(description="任務名稱")
    description: str = Field(description="任務描述")
    owner: str = Field(description="負責人")
    user_id: str = Field(alias="userId", description="建立任務的使用者 ID")
    workspace_id: str = Field(alias="workspaceId", description="目標工作區 ID")
    prompt: str = Field(description="任務提示或內容")
    status: JobStatus = Field(description="任務狀態")
    trigger: JobTrigger = Field(description="觸發條件")
    schedule: str = Field(description="排程表達式")
    tags: list[str] = Field(default_factory=list, description="標籤")
    notifications: JobNotificationSettings = Field(
        default_factory=JobNotificationSettings, description="通知設定"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="任務額外設定")
    webhook_api_key: Optional[str] = Field(
        default=None, alias="webhookApiKey", description="Webhook API Key"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobCreateRequest(JobBase):
    """建立自動化任務請求"""

    pass


class JobUpdateRequest(BaseModel):
    """更新自動化任務請求"""

    name: Optional[str] = Field(default=None, description="任務名稱")
    description: Optional[str] = Field(default=None, description="任務描述")
    owner: Optional[str] = Field(default=None, description="負責人")
    user_id: Optional[str] = Field(
        default=None, alias="userId", description="建立任務的使用者 ID"
    )
    workspace_id: Optional[str] = Field(
        default=None, alias="workspaceId", description="目標工作區 ID"
    )
    prompt: Optional[str] = Field(default=None, description="任務提示或內容")
    status: Optional[JobStatus] = Field(default=None, description="任務狀態")
    trigger: Optional[JobTrigger] = Field(default=None, description="觸發條件")
    schedule: Optional[str] = Field(default=None, description="排程表達式")
    tags: Optional[list[str]] = Field(default=None, description="標籤")
    notifications: Optional[JobNotificationSettings] = Field(
        default=None, description="通知設定"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="任務額外設定"
    )
    webhook_api_key: Optional[str] = Field(
        default=None, alias="webhookApiKey", description="Webhook API Key"
    )

    model_config = ConfigDict(populate_by_name=True)


class AutomationJob(JobBase):
    """自動化任務回應"""

    id: str = Field(description="任務 ID")
    workspace_name: Optional[str] = Field(
        default=None, alias="workspaceName", description="工作區名稱"
    )
    created_at: datetime = Field(alias="createdAt", description="建立時間")
    updated_at: datetime = Field(alias="updatedAt", description="更新時間")
    last_run_at: Optional[datetime] = Field(
        default=None, alias="lastRunAt", description="最後執行時間"
    )
    next_run_at: Optional[datetime] = Field(
        default=None, alias="nextRunAt", description="下一次執行時間"
    )
    success_rate: float = Field(
        default=0.0, alias="successRate", description="成功率 (0~1)"
    )
    failure_rate: float = Field(
        default=0.0, alias="failureRate", description="失敗率 (0~1)"
    )
    total_executions: int = Field(
        default=0, alias="totalExecutions", description="總執行次數"
    )
    average_duration: int = Field(
        default=0, alias="averageDuration", description="平均執行時間 (秒)"
    )
    last_duration: Optional[int] = Field(
        default=None, alias="lastDuration", description="最近一次執行時間 (秒)"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobListResponse(BaseModel):
    """自動化任務列表回應"""

    items: list[AutomationJob] = Field(description="任務清單")
    total: int = Field(description="總筆數")

    model_config = ConfigDict(populate_by_name=True)


class AutomationMetrics(BaseModel):
    """自動化統計資訊"""

    active_count: int = Field(alias="activeCount", description="啟用中的任務數")
    paused_count: int = Field(alias="pausedCount", description="暫停的任務數")
    failed_count: int = Field(alias="failedCount", description="失敗執行次數總和")
    draft_count: int = Field(alias="draftCount", description="草稿任務數")
    success_rate: float = Field(alias="successRate", description="整體成功率")
    running_executions: int = Field(
        alias="runningExecutions", description="執行中的任務數"
    )
    queued_executions: int = Field(
        alias="queuedExecutions", description="佇列中的任務數"
    )
    average_duration: float = Field(
        alias="averageDuration", description="平均執行時間 (秒)"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobExecution(BaseModel):
    """任務執行紀錄"""

    id: str = Field(description="執行 ID")
    job_id: str = Field(alias="jobId", description="對應任務 ID")
    status: JobExecutionStatus = Field(description="執行狀態")
    trigger: JobTrigger = Field(description="觸發來源")
    started_at: Optional[datetime] = Field(
        default=None, alias="startedAt", description="開始時間"
    )
    finished_at: Optional[datetime] = Field(
        default=None, alias="finishedAt", description="完成時間"
    )
    duration: Optional[int] = Field(
        default=None, description="執行耗時 (秒)", ge=0
    )
    session_id: Optional[str] = Field(
        default=None, alias="sessionId", description="對應的工作區 Session ID"
    )
    error_message: Optional[str] = Field(
        default=None, alias="errorMessage", description="錯誤訊息"
    )
    execution_metadata: Optional[dict] = Field(
        default=None, alias="executionMetadata", description="執行元數據（包含錯誤詳情等）"
    )
    summary: str = Field(description="執行摘要")
    queue_position: Optional[int] = Field(
        default=None, alias="queuePosition", description="排隊位置（1-based）"
    )
    queued_at: Optional[datetime] = Field(
        default=None, alias="queuedAt", description="加入佇列時間"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobExecutionListResponse(BaseModel):
    """任務執行紀錄列表回應"""

    items: list[JobExecution] = Field(description="執行紀錄清單")
    total: int = Field(description="總筆數")

    model_config = ConfigDict(populate_by_name=True)


class JobExecutionCreateRequest(BaseModel):
    """新增執行紀錄請求"""

    status: JobExecutionStatus = Field(description="執行狀態")
    trigger: JobTrigger = Field(description="觸發來源")
    summary: str = Field(description="執行摘要")
    duration: Optional[int] = Field(default=None, description="執行耗時 (秒)", ge=0)
    session_id: Optional[str] = Field(
        default=None, alias="sessionId", description="對應的工作區 Session ID"
    )
    error_message: Optional[str] = Field(
        default=None, alias="errorMessage", description="錯誤訊息"
    )

    model_config = ConfigDict(populate_by_name=True)


class JobStatusUpdate(BaseModel):
    """更新任務狀態請求"""

    status: JobStatus = Field(description="新的任務狀態")

    model_config = ConfigDict(populate_by_name=True)


class JobCalendarEvent(BaseModel):
    """任務行事曆事件"""

    id: str = Field(description="事件 ID")
    job_id: str = Field(alias="jobId", description="任務 ID")
    title: str = Field(description="顯示名稱")
    start: datetime = Field(description="開始時間")
    end: datetime = Field(description="結束時間")
    status: JobExecutionStatus = Field(description="預期狀態")

    model_config = ConfigDict(populate_by_name=True)


class JobCalendarResponse(BaseModel):
    """任務行事曆事件回應"""

    items: list[JobCalendarEvent] = Field(description="行事曆事件清單")
    total: int = Field(description="總筆數")

    model_config = ConfigDict(populate_by_name=True)


class QueuePosition(BaseModel):
    """佇列位置資訊"""

    execution_id: str = Field(alias="executionId", description="執行記錄 ID")
    position: int = Field(description="排隊位置（1-based）")
    total: int = Field(description="佇列總長度")
    estimated_wait_seconds: Optional[int] = Field(
        default=None, alias="estimatedWaitSeconds", description="預估等待時間（秒）"
    )

    model_config = ConfigDict(populate_by_name=True)


class WorkspaceQueueResponse(BaseModel):
    """工作區佇列回應"""

    workspace_id: str = Field(alias="workspaceId", description="工作區 ID")
    queue_length: int = Field(alias="queueLength", description="佇列長度")
    executions: list[JobExecution] = Field(description="排隊中的執行記錄")

    model_config = ConfigDict(populate_by_name=True)


class ExecutionCancelResponse(BaseModel):
    """取消執行回應"""

    execution_id: str = Field(alias="executionId", description="執行記錄 ID")
    status: str = Field(description="當前狀態")
    message: str = Field(description="回應訊息")
    cancelled: bool = Field(description="是否成功取消")

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

