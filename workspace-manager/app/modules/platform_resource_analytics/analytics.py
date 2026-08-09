"""Activity ledger and capacity transition ownership for platform resources."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.platform_resource_capacity.models import CapacityRisk
from app.modules.platform_resource_capacity.policy import CapacityGovernancePolicy


class PlatformResourceCapacityMetrics:
    """Process-local low-cardinality counters for threshold transitions."""

    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()

    def increment(self, event_type: str, storage_kind: str, provisioner: str) -> None:
        self._counts[f"{event_type}:{storage_kind}:{provisioner}"] += 1

    def snapshot(self) -> dict[str, int]:
        return dict(self._counts)


capacity_threshold_metrics = PlatformResourceCapacityMetrics()


class PlatformResourceActivityLedger:
    """Own activity ledger writes and capacity transition semantics."""

    def __init__(
        self,
        db: Session,
        *,
        capacity_metrics: PlatformResourceCapacityMetrics | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.capacity_metrics = capacity_metrics or capacity_threshold_metrics

    def record_runtime_activity(
        self,
        *,
        event_id: str,
        resource_id: str,
        event_type: str,
        occurred_at: datetime,
    ) -> bool:
        return self._record_activity(
            event_id=event_id,
            resource_type="workspace",
            resource_id=resource_id,
            event_type=event_type,
            source="runtime",
            occurred_at=occurred_at,
        )

    def record_manager_activity(
        self,
        *,
        event_id: str,
        resource_type: str,
        resource_id: str,
        event_type: str,
        occurred_at: datetime | None = None,
    ) -> bool:
        return self._record_activity(
            event_id=event_id,
            resource_type=resource_type,
            resource_id=resource_id,
            event_type=event_type,
            source="manager",
            occurred_at=occurred_at or _utcnow(),
        )

    def record_capacity_transition(
        self,
        *,
        resource_type: str,
        resource_id: str,
        storage_kind: str,
        previous_used_bytes: int,
        current_used_bytes: int,
        allocated_bytes: int | None,
        source: str,
        occurred_at: datetime,
    ) -> str | None:
        previous_risk = CapacityGovernancePolicy.assess(
            used_bytes=previous_used_bytes,
            allocated_bytes=allocated_bytes,
            measured_at=occurred_at,
        ).risk
        current_risk = CapacityGovernancePolicy.assess(
            used_bytes=current_used_bytes,
            allocated_bytes=allocated_bytes,
            measured_at=occurred_at,
        ).risk
        event_type = _capacity_transition_event(previous_risk, current_risk)
        if event_type is None:
            return None
        identity = (
            f"{resource_type}:{resource_id}:{storage_kind}:"
            f"{occurred_at.isoformat()}:{event_type}"
        )
        self.db.add(
            db_models.PlatformResourceActivityEvent(
                event_id=f"capacity:{uuid5(NAMESPACE_URL, identity)}",
                resource_type=resource_type,
                resource_id=resource_id,
                event_type=event_type,
                source=source,
                occurred_at=occurred_at,
                received_at=_utcnow(),
            )
        )
        return event_type

    def count_capacity_transition(
        self, event_type: str, storage_kind: str, capacity_kind: str
    ) -> None:
        self.capacity_metrics.increment(event_type, storage_kind, capacity_kind)

    def _record_activity(
        self,
        *,
        event_id: str,
        resource_type: str,
        resource_id: str,
        event_type: str,
        source: str,
        occurred_at: datetime,
    ) -> bool:
        self.db.add(
            db_models.PlatformResourceActivityEvent(
                event_id=event_id,
                resource_type=resource_type,
                resource_id=resource_id,
                event_type=event_type,
                source=source,
                occurred_at=occurred_at,
                received_at=_utcnow(),
            )
        )
        self._mark_active(
            resource_type=resource_type,
            resource_id=resource_id,
            occurred_at=occurred_at,
        )
        return True

    def _mark_active(
        self, *, resource_type: str, resource_id: str, occurred_at: datetime
    ) -> None:
        local_date = (
            _as_aware(occurred_at)
            .astimezone(ZoneInfo(self.settings.TZ))
            .date()
            .isoformat()
        )
        for pending in self.db.new:
            if (
                isinstance(pending, db_models.PlatformResourceDailyActiveResource)
                and pending.local_date == local_date
                and pending.time_zone == self.settings.TZ
                and pending.resource_type == resource_type
                and pending.resource_id == resource_id
            ):
                return
        existing = self.db.scalar(
            select(db_models.PlatformResourceDailyActiveResource).where(
                db_models.PlatformResourceDailyActiveResource.local_date == local_date,
                db_models.PlatformResourceDailyActiveResource.time_zone
                == self.settings.TZ,
                db_models.PlatformResourceDailyActiveResource.resource_type
                == resource_type,
                db_models.PlatformResourceDailyActiveResource.resource_id
                == resource_id,
            )
        )
        if existing is None:
            self.db.add(
                db_models.PlatformResourceDailyActiveResource(
                    local_date=local_date,
                    time_zone=self.settings.TZ,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    first_occurred_at=occurred_at,
                )
            )


def _capacity_transition_event(
    previous: CapacityRisk, current: CapacityRisk
) -> str | None:
    severity = {"normal": 0, "unknown": 0, "stale": 0, "warning": 1, "critical": 2}
    previous_level = severity[previous]
    current_level = severity[current]
    if current_level > previous_level:
        return (
            "capacity_threshold_critical"
            if current == "critical"
            else "capacity_threshold_warning"
        )
    if current_level < previous_level and previous_level > 0:
        return "capacity_threshold_recovered"
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


__all__ = [
    "PlatformResourceActivityLedger",
    "PlatformResourceCapacityMetrics",
    "capacity_threshold_metrics",
]
