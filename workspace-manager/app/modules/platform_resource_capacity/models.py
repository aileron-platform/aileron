"""Public interface models for platform resource capacity governance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from app.core.pydantic import CamelModel

CapacityRisk = Literal["normal", "warning", "critical", "unknown", "stale"]
WorkspaceStorageKind = Literal["workspace_data", "runtime_home"]
StorageErrorCode = Literal[
    "STORAGE_CAPACITY_INVALID",
    "STORAGE_CAPACITY_SHRINK_UNSUPPORTED",
    "STORAGE_CLASS_EXPANSION_UNSUPPORTED",
    "STORAGE_CLASS_NOT_FOUND",
]
STORAGE_ERROR_CODES: frozenset[str] = frozenset(
    {
        "STORAGE_CAPACITY_INVALID",
        "STORAGE_CAPACITY_SHRINK_UNSUPPORTED",
        "STORAGE_CLASS_EXPANSION_UNSUPPORTED",
        "STORAGE_CLASS_NOT_FOUND",
    }
)


@dataclass(frozen=True)
class StorageDesired:
    """One storage kind's Manager-owned desired state."""

    storage_kind: WorkspaceStorageKind
    capacity_bytes: int
    revision: int


@dataclass(frozen=True)
class WorkspaceStorageDesiredState:
    """Typed desired state delivered through the Kubernetes adapter."""

    workspace_data: StorageDesired
    runtime_home: StorageDesired


@dataclass(frozen=True)
class StorageObservation:
    """One Operator observation after transport validation."""

    storage_kind: WorkspaceStorageKind
    allocated_bytes: int
    observed_revision: int
    expansion_supported: bool
    error_code: StorageErrorCode | None
    observed_at: datetime | None


@dataclass(frozen=True)
class WorkspaceStorageObservation:
    """Typed observations accepted by the capacity lifecycle."""

    items: tuple[StorageObservation, ...]


class CapacityDailyPoint(CamelModel):
    date: str
    used_bytes: int = Field(..., alias="usedBytes")


class WorkspaceCapacityItem(CamelModel):
    storage_kind: WorkspaceStorageKind = Field(..., alias="storageKind")
    used_bytes: int | None = Field(None, alias="usedBytes")
    allocated_bytes: int | None = Field(None, alias="allocatedBytes")
    host_available_bytes: int | None = Field(None, alias="hostAvailableBytes")
    utilization_percent: float | None = Field(None, alias="utilizationPercent")
    risk: CapacityRisk
    measured_at: datetime | None = Field(None, alias="measuredAt")
    stale: bool
    history: list[CapacityDailyPoint] = Field(default_factory=list)


class PlatformCapacityProjection(CamelModel):
    """Current capacity projection for one platform resource storage kind."""

    used_bytes: int = Field(..., alias="usedBytes")
    allocated_bytes: int | None = Field(None, alias="allocatedBytes")
    host_available_bytes: int | None = Field(None, alias="hostAvailableBytes")
    utilization_percent: float | None = Field(None, alias="utilizationPercent")
    risk: CapacityRisk
    measured_at: datetime = Field(..., alias="measuredAt")
    expansion_supported: bool = Field(..., alias="expansionSupported")


class WorkspaceCapacityResponse(CamelModel):
    workspace_id: str = Field(..., alias="workspaceId")
    provisioner: str
    time_zone: str = Field(..., alias="timeZone")
    range: Literal["7d", "30d", "90d"]
    calculated_at: datetime = Field(..., alias="calculatedAt")
    collection_started_at: datetime | None = Field(None, alias="collectionStartedAt")
    items: list[WorkspaceCapacityItem]


class KnowledgeBaseQuotaRequest(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    quota_bytes: int | None = Field(None, alias="quotaBytes", ge=0)


class KnowledgeBaseQuotaResponse(CamelModel):
    knowledge_base_id: str = Field(..., alias="knowledgeBaseId")
    current_size_bytes: int = Field(..., alias="currentSizeBytes")
    quota_bytes: int | None = Field(None, alias="quotaBytes")
    effective_quota_bytes: int = Field(..., alias="effectiveQuotaBytes")
    quota_source: Literal["custom", "platform_default"] = Field(
        ..., alias="quotaSource"
    )


class WorkspaceCapacityExpansionRequest(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    storage_kind: WorkspaceStorageKind = Field(..., alias="storageKind")
    requested_bytes: int = Field(..., alias="requestedBytes", gt=0)

    @field_validator("requested_bytes")
    @classmethod
    def require_gib_boundary(cls, value: int) -> int:
        if value % (1024**3) != 0:
            raise ValueError("requestedBytes must be aligned to a GiB boundary")
        return value


class WorkspaceCapacityExpansionResponse(CamelModel):
    request_id: str = Field(..., alias="requestId")
    workspace_id: str = Field(..., alias="workspaceId")
    storage_kind: WorkspaceStorageKind = Field(..., alias="storageKind")
    previous_bytes: int = Field(..., alias="previousBytes")
    requested_bytes: int = Field(..., alias="requestedBytes")
    phase: Literal["pending", "applying", "completed", "failed"]
    error_code: str | None = Field(None, alias="errorCode")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
