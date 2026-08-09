"""Public API models for platform resource analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from app.core.pydantic import CamelModel

ResourceType = Literal["workspace", "knowledge_base"]
RangeValue = Literal["7d", "30d", "90d"]


class RuntimeActivityEventInput(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    event_id: str = Field(..., alias="eventId", min_length=1, max_length=128)
    event_type: str = Field(..., alias="eventType", min_length=1, max_length=64)
    occurred_at: datetime = Field(..., alias="occurredAt")


class CapacityMeasurementInput(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    storage_kind: Literal["workspace_data", "runtime_home"] = Field(
        ..., alias="storageKind"
    )
    used_bytes: int = Field(..., alias="usedBytes", ge=0)
    capacity_bytes: int = Field(..., alias="capacityBytes", ge=0)
    available_bytes: int = Field(..., alias="availableBytes", ge=0)
    observed_at: datetime = Field(..., alias="observedAt")


class RuntimeTelemetryBatch(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(..., alias="schemaVersion")
    batch_id: str = Field(..., alias="batchId", min_length=1, max_length=128)
    workspace_id: str = Field(..., alias="workspaceId", min_length=1, max_length=128)
    runtime_instance_id: str = Field(
        ..., alias="runtimeInstanceId", min_length=1, max_length=128
    )
    observed_at: datetime = Field(..., alias="observedAt")
    events: list[RuntimeActivityEventInput] = Field(
        default_factory=list, max_length=500
    )
    capacity_measurements: list[CapacityMeasurementInput] = Field(
        default_factory=list, alias="capacityMeasurements", max_length=2
    )


class TelemetryIngestResponse(CamelModel):
    accepted_events: int = Field(..., alias="acceptedEvents")
    deduplicated_events: int = Field(..., alias="deduplicatedEvents")
    accepted_measurements: int = Field(..., alias="acceptedMeasurements")


class StatisticValue(CamelModel):
    value: int
    previous_value: int = Field(..., alias="previousValue")
    change_percent: float | None = Field(None, alias="changePercent")


class SummaryMetrics(CamelModel):
    total: StatisticValue
    active: StatisticValue
    used_bytes: StatisticValue = Field(..., alias="usedBytes")
    near_limit: StatisticValue = Field(..., alias="nearLimit")


class DistributionItem(CamelModel):
    key: str
    count: int


class PlatformResourceSummaryResponse(CamelModel):
    resource_type: ResourceType = Field(..., alias="resourceType")
    range: RangeValue
    time_zone: str = Field(..., alias="timeZone")
    calculated_at: datetime = Field(..., alias="calculatedAt")
    collection_started_at: datetime | None = Field(None, alias="collectionStartedAt")
    is_stale: bool = Field(False, alias="isStale")
    refresh_in_progress: bool = Field(False, alias="refreshInProgress")
    metrics: SummaryMetrics
    distributions: list[DistributionItem]


class ResourceTrendPoint(CamelModel):
    date: str
    total: int
    created: int
    active: int
    deleted: int


class ResourceTrendResponse(CamelModel):
    resource_type: ResourceType = Field(..., alias="resourceType")
    range: RangeValue
    time_zone: str = Field(..., alias="timeZone")
    calculated_at: datetime = Field(..., alias="calculatedAt")
    collection_started_at: datetime | None = Field(None, alias="collectionStartedAt")
    is_stale: bool = Field(False, alias="isStale")
    refresh_in_progress: bool = Field(False, alias="refreshInProgress")
    points: list[ResourceTrendPoint]


class CapacityTrendPoint(CamelModel):
    date: str
    used_bytes: int = Field(..., alias="usedBytes")
    allocated_bytes: int | None = Field(None, alias="allocatedBytes")
    unknown_count: int = Field(..., alias="unknownCount")
    stale_count: int = Field(..., alias="staleCount")


class CapacityTrendResponse(CamelModel):
    resource_type: ResourceType = Field(..., alias="resourceType")
    range: RangeValue
    time_zone: str = Field(..., alias="timeZone")
    calculated_at: datetime = Field(..., alias="calculatedAt")
    collection_started_at: datetime | None = Field(None, alias="collectionStartedAt")
    is_stale: bool = Field(False, alias="isStale")
    refresh_in_progress: bool = Field(False, alias="refreshInProgress")
    points: list[CapacityTrendPoint]
