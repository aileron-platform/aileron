"""Workspace control-plane availability contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.core.pydantic import CamelModel

WorkspaceAvailabilityState = Literal[
    "ready",
    "transitioning",
    "stopped",
    "blocked",
    "deleting",
    "not_found",
]
WorkspaceAvailabilityAction = Literal["start", "retry", "rebuild", "return"]
WorkspaceDeletionAction = Literal["delete", "retry"]
WorkspaceDeletionPhase = Literal[
    "queued",
    "cancelling_automations",
    "stopping_runtime",
    "deleting_resources",
    "finalizing",
]
WorkspaceDeletionStatus = Literal["queued", "running", "failed"]
KnowledgeMountAvailabilityState = Literal["ready", "syncing", "degraded"]


class KnowledgeMountAvailability(CamelModel):
    """Knowledge mount health that never controls global availability."""

    status: KnowledgeMountAvailabilityState
    desired_revision: int = Field(..., alias="desiredRevision")
    observed_revision: int = Field(..., alias="observedRevision")
    last_known_good_revision: int = Field(..., alias="lastKnownGoodRevision")
    error_code: str | None = Field(None, alias="errorCode")
    compensating: bool = False


class WorkspaceDeletionProjection(CamelModel):
    """Owner-scoped deletion intent projection inside availability."""

    availability: WorkspaceAvailabilityState
    allowed_actions: list[WorkspaceDeletionAction] = Field(
        default_factory=list,
        alias="allowedActions",
    )
    phase: WorkspaceDeletionPhase | None = None
    status: WorkspaceDeletionStatus | None = None
    error_code: str | None = Field(None, alias="errorCode")


class WorkspaceAvailabilityResponse(CamelModel):
    """Manager-owned control-plane availability snapshot."""

    workspace_id: str = Field(..., alias="workspaceId")
    availability: WorkspaceAvailabilityState
    reason_code: str = Field(..., alias="reasonCode")
    runtime_status: str | None = Field(None, alias="runtimeStatus")
    runtime_instance_id: str | None = Field(None, alias="runtimeInstanceId")
    runtime_access_desired_revision: int = Field(
        0,
        alias="runtimeAccessDesiredRevision",
    )
    runtime_access_observed_revision: int = Field(
        0,
        alias="runtimeAccessObservedRevision",
    )
    retryable: bool = False
    allowed_actions: list[WorkspaceAvailabilityAction] = Field(
        default_factory=list,
        alias="allowedActions",
    )
    retry_after_ms: int | None = Field(None, alias="retryAfterMs")
    knowledge_mount_status: KnowledgeMountAvailability = Field(
        ...,
        alias="knowledgeMountStatus",
    )
    deletion: WorkspaceDeletionProjection


class WorkspaceAvailabilityActionResponse(CamelModel):
    """Accepted durable action returned before execution-plane convergence."""

    workspace_id: str = Field(..., alias="workspaceId")
    action: Literal["start", "retry", "rebuild"]
    job_id: str = Field(..., alias="jobId")
    status: str
    reason_code: str = Field(..., alias="reasonCode")


__all__ = [
    "KnowledgeMountAvailability",
    "KnowledgeMountAvailabilityState",
    "WorkspaceAvailabilityAction",
    "WorkspaceAvailabilityActionResponse",
    "WorkspaceAvailabilityResponse",
    "WorkspaceAvailabilityState",
    "WorkspaceDeletionAction",
    "WorkspaceDeletionPhase",
    "WorkspaceDeletionProjection",
    "WorkspaceDeletionStatus",
]
