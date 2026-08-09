"""Resource telemetry domain values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

StorageKind = Literal["workspace_data", "runtime_home"]
ActivityType = Literal["runtime_started", "agent_execution_started"]


@dataclass(frozen=True, slots=True)
class CapacityMeasurement:
    storage_kind: StorageKind
    used_bytes: int
    capacity_bytes: int
    available_bytes: int
    observed_at: datetime

    def to_wire(self) -> dict[str, Any]:
        return {
            "storageKind": self.storage_kind,
            "usedBytes": self.used_bytes,
            "capacityBytes": self.capacity_bytes,
            "availableBytes": self.available_bytes,
            "observedAt": _wire_time(self.observed_at),
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> "CapacityMeasurement":
        return cls(
            storage_kind=payload["storageKind"],
            used_bytes=int(payload["usedBytes"]),
            capacity_bytes=int(payload["capacityBytes"]),
            available_bytes=int(payload["availableBytes"]),
            observed_at=_parse_wire_time(payload["observedAt"]),
        )


@dataclass(frozen=True, slots=True)
class ResourceActivityEvent:
    event_id: str
    event_type: ActivityType
    occurred_at: datetime

    def to_wire(self) -> dict[str, Any]:
        return {
            "eventId": self.event_id,
            "eventType": self.event_type,
            "occurredAt": _wire_time(self.occurred_at),
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> "ResourceActivityEvent":
        return cls(
            event_id=payload["eventId"],
            event_type=payload["eventType"],
            occurred_at=_parse_wire_time(payload["occurredAt"]),
        )


@dataclass(frozen=True, slots=True)
class TelemetryBatch:
    batch_id: str
    workspace_id: str
    runtime_instance_id: str
    observed_at: datetime
    events: tuple[ResourceActivityEvent, ...]
    capacity_measurements: tuple[CapacityMeasurement, ...]
    schema_version: int = 1

    def to_wire(self) -> dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "batchId": self.batch_id,
            "workspaceId": self.workspace_id,
            "runtimeInstanceId": self.runtime_instance_id,
            "observedAt": _wire_time(self.observed_at),
            "events": [event.to_wire() for event in self.events],
            "capacityMeasurements": [
                measurement.to_wire() for measurement in self.capacity_measurements
            ],
        }

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> "TelemetryBatch":
        return cls(
            schema_version=int(payload["schemaVersion"]),
            batch_id=payload["batchId"],
            workspace_id=payload["workspaceId"],
            runtime_instance_id=payload["runtimeInstanceId"],
            observed_at=_parse_wire_time(payload["observedAt"]),
            events=tuple(
                ResourceActivityEvent.from_wire(item) for item in payload["events"]
            ),
            capacity_measurements=tuple(
                CapacityMeasurement.from_wire(item)
                for item in payload["capacityMeasurements"]
            ),
        )


def _wire_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_wire_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


__all__ = [
    "ActivityType",
    "CapacityMeasurement",
    "ResourceActivityEvent",
    "StorageKind",
    "TelemetryBatch",
]
