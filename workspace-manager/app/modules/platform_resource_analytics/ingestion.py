"""Runtime telemetry ingestion boundary for platform resource observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from hashlib import sha256
from typing import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.platform_resource_capacity.errors import PlatformResourceError

from .analytics import PlatformResourceActivityLedger, PlatformResourceCapacityMetrics
from .cache import PlatformResourceCache
from .models import (
    CapacityMeasurementInput,
    RuntimeTelemetryBatch,
    TelemetryIngestResponse,
)


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryIdentity:
    """Identity facts collected by the transport boundary for one Runtime."""

    route_workspace_id: str
    header_workspace_id: str
    authenticated_runtime_instance_id: str | None
    expected_runtime_instance_id: str | None

    def validate(self, batch: RuntimeTelemetryBatch) -> None:
        if (
            self.route_workspace_id != self.header_workspace_id
            or batch.workspace_id != self.route_workspace_id
        ):
            raise PlatformResourceError("workspace_identity_mismatch", 403)
        if (
            self.authenticated_runtime_instance_id is None
            or self.expected_runtime_instance_id is None
            or self.authenticated_runtime_instance_id
            != self.expected_runtime_instance_id
            or batch.runtime_instance_id != self.authenticated_runtime_instance_id
        ):
            raise PlatformResourceError("runtime_instance_mismatch", 409)


class PlatformResourceTelemetryIngestion:
    """Validate and atomically project Runtime telemetry into Manager storage."""

    def __init__(
        self,
        db: Session,
        *,
        cache: PlatformResourceCache | None = None,
        capacity_metrics: PlatformResourceCapacityMetrics | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        settings = get_settings()
        self.cache = cache or PlatformResourceCache(settings.redis_url)
        self._clock = clock or _utcnow
        self._activity_ledger = PlatformResourceActivityLedger(
            db, capacity_metrics=capacity_metrics
        )

    def ingest(
        self,
        *,
        identity: RuntimeTelemetryIdentity,
        batch: RuntimeTelemetryBatch,
    ) -> TelemetryIngestResponse:
        identity.validate(batch)
        self._validate_batch(batch)
        payload_fingerprint = _batch_fingerprint(batch)

        for attempt in range(2):
            existing_batch = self.db.get(
                db_models.PlatformResourceTelemetryBatch,
                batch.batch_id,
            )
            if existing_batch is not None:
                if (
                    existing_batch.workspace_id != identity.route_workspace_id
                    or existing_batch.runtime_instance_id
                    != identity.authenticated_runtime_instance_id
                    or existing_batch.payload_fingerprint != payload_fingerprint
                ):
                    raise PlatformResourceError("batch_identity_conflict", 409)
                return TelemetryIngestResponse(
                    acceptedEvents=0,
                    deduplicatedEvents=len(batch.events),
                    acceptedMeasurements=0,
                )
            workspace = self.db.get(db_models.Workspace, identity.route_workspace_id)
            if workspace is None:
                raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
            try:
                self.db.add(
                    db_models.PlatformResourceTelemetryBatch(
                        batch_id=batch.batch_id,
                        workspace_id=identity.route_workspace_id,
                        runtime_instance_id=identity.authenticated_runtime_instance_id,
                        payload_fingerprint=payload_fingerprint,
                    )
                )
                response, changed, transitions = self._apply_batch(
                    workspace=workspace,
                    batch=batch,
                )
                self.db.commit()
            except PlatformResourceError:
                self.db.rollback()
                raise
            except IntegrityError:
                self.db.rollback()
                if attempt == 0:
                    continue
                raise

            for event_type, storage_kind, provisioner in transitions:
                self._activity_ledger.count_capacity_transition(
                    event_type, storage_kind, provisioner
                )
            if changed:
                self.cache.invalidate("workspace")
            return response

        raise AssertionError("Runtime telemetry ingestion retry was not exhausted")

    @staticmethod
    def _validate_batch(batch: RuntimeTelemetryBatch) -> None:
        storage_kinds = [
            measurement.storage_kind for measurement in batch.capacity_measurements
        ]
        if len(storage_kinds) != len(set(storage_kinds)):
            raise PlatformResourceError("duplicate_capacity_storage_kind", 422)

    def _apply_batch(
        self,
        *,
        workspace: db_models.Workspace,
        batch: RuntimeTelemetryBatch,
    ) -> tuple[TelemetryIngestResponse, bool, list[tuple[str, str, str]]]:
        now = self._clock()
        accepted_events = 0
        deduplicated_events = 0
        changed = False
        seen_event_ids: set[str] = set()

        for event in batch.events:
            if event.event_id in seen_event_ids:
                deduplicated_events += 1
                continue
            seen_event_ids.add(event.event_id)
            existing = self.db.get(
                db_models.PlatformResourceActivityEvent, event.event_id
            )
            if existing is not None:
                if not _is_runtime_workspace_event(existing, workspace.id):
                    raise PlatformResourceError("event_identity_conflict", 409)
                deduplicated_events += 1
                continue
            self._activity_ledger.record_runtime_activity(
                event_id=event.event_id,
                resource_id=workspace.id,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
            )
            accepted_events += 1
            changed = True

        transitions: list[tuple[str, str, str]] = []
        for measurement in batch.capacity_measurements:
            was_changed, transition = self._upsert_capacity(
                workspace=workspace,
                measurement=measurement,
                now=now,
            )
            changed = changed or was_changed
            if transition is not None:
                transitions.append(transition)

        return (
            TelemetryIngestResponse(
                acceptedEvents=accepted_events,
                deduplicatedEvents=deduplicated_events,
                acceptedMeasurements=len(batch.capacity_measurements),
            ),
            changed,
            transitions,
        )

    def _upsert_capacity(
        self,
        *,
        workspace: db_models.Workspace,
        measurement: CapacityMeasurementInput,
        now: datetime,
    ) -> tuple[bool, tuple[str, str, str] | None]:
        row = self.db.scalar(
            select(db_models.ResourceCapacityObservation).where(
                db_models.ResourceCapacityObservation.resource_type == "workspace",
                db_models.ResourceCapacityObservation.resource_id == workspace.id,
                db_models.ResourceCapacityObservation.storage_kind
                == measurement.storage_kind,
            )
        )
        previous_used_bytes = row.used_bytes if row is not None else 0
        allocated_bytes = (
            measurement.capacity_bytes
            if workspace.provisioner == "kubernetes"
            else None
        )
        values = {
            "used_bytes": measurement.used_bytes,
            "allocated_bytes": allocated_bytes,
            "host_available_bytes": (
                measurement.available_bytes
                if workspace.provisioner == "docker"
                else None
            ),
            "provisioner": workspace.provisioner,
            "measured_at": measurement.observed_at,
            "received_at": now,
            "measurement_source": "runtime",
        }
        if row is None:
            self.db.add(
                db_models.ResourceCapacityObservation(
                    resource_type="workspace",
                    resource_id=workspace.id,
                    storage_kind=measurement.storage_kind,
                    **values,
                )
            )
            changed = True
        elif _as_aware(measurement.observed_at) >= _as_aware(row.measured_at):
            changed = any(getattr(row, key) != value for key, value in values.items())
            for key, value in values.items():
                setattr(row, key, value)
        else:
            return False, None

        event_type = self._activity_ledger.record_capacity_transition(
            resource_type="workspace",
            resource_id=workspace.id,
            storage_kind=measurement.storage_kind,
            previous_used_bytes=previous_used_bytes,
            current_used_bytes=measurement.used_bytes,
            allocated_bytes=allocated_bytes,
            source="runtime",
            occurred_at=measurement.observed_at,
        )
        return changed, (
            (event_type, measurement.storage_kind, workspace.provisioner)
            if event_type is not None
            else None
        )


def _is_runtime_workspace_event(
    event: db_models.PlatformResourceActivityEvent,
    workspace_id: str,
) -> bool:
    return (
        event.resource_type == "workspace"
        and event.resource_id == workspace_id
        and event.source == "runtime"
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _batch_fingerprint(batch: RuntimeTelemetryBatch) -> str:
    payload = batch.model_dump(mode="json", by_alias=True)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "PlatformResourceTelemetryIngestion",
    "RuntimeTelemetryIdentity",
]
