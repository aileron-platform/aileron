"""Read and maintenance projection for platform resource analytics."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.platform_resource_capacity.errors import PlatformResourceError
from app.modules.platform_resource_capacity.inventory import (
    PlatformResourceCapacityInventory,
)
from app.modules.platform_resource_capacity.policy import CapacityGovernancePolicy

from .cache import PlatformResourceCache
from .models import (
    CapacityTrendPoint,
    CapacityTrendResponse,
    DistributionItem,
    PlatformResourceSummaryResponse,
    RangeValue,
    ResourceTrendPoint,
    ResourceTrendResponse,
    ResourceType,
    StatisticValue,
    SummaryMetrics,
)


class PlatformResourceAnalytics:
    """Own SQL, cache freshness, and maintenance of analytics read models."""

    def __init__(
        self,
        db: Session,
        *,
        cache: PlatformResourceCache | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.authorization = AuthorizationOperationPolicy(db)
        self.cache = cache or PlatformResourceCache(self.settings.REDIS_URL)

    def get_summary(
        self,
        *,
        actor: AuthorizationActor,
        resource_type: str,
        range_value: str,
        refresh: bool = False,
    ) -> PlatformResourceSummaryResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_READ
        )
        days = _range_days(range_value)
        cache_key = self.cache.key(
            view="summary",
            resource_type=resource_type,
            range_value=range_value,
            time_zone=self.settings.TZ,
        )
        if not refresh:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                return PlatformResourceSummaryResponse.model_validate(cached)
        model = _resource_model(resource_type)
        total = self.db.scalar(select(func.count()).select_from(model)) or 0
        today = _utcnow().astimezone(ZoneInfo(self.settings.TZ)).date()
        current_start = (today - timedelta(days=days - 1)).isoformat()
        previous_start = (today - timedelta(days=(2 * days) - 1)).isoformat()
        previous_end = (today - timedelta(days=days)).isoformat()
        active = self._active_count(resource_type, current_start, today.isoformat())
        previous_active = self._active_count(
            resource_type, previous_start, previous_end
        )
        total_used, near_limit = self._capacity_totals(resource_type)
        distribution = self._distribution(resource_type)
        created_at = self.db.scalar(select(func.min(model.created_at)))
        response = PlatformResourceSummaryResponse(
            resourceType=cast(ResourceType, resource_type),
            range=cast(RangeValue, range_value),
            timeZone=self.settings.TZ,
            calculatedAt=_utcnow(),
            collectionStartedAt=created_at,
            isStale=False,
            refreshInProgress=False,
            metrics=SummaryMetrics(
                total=_statistic(total, total),
                active=_statistic(active, previous_active),
                usedBytes=_statistic(total_used, total_used),
                nearLimit=_statistic(near_limit, near_limit),
            ),
            distributions=[
                DistributionItem(key=key, count=count)
                for key, count in distribution.items()
            ],
        )
        self.cache.set_json(
            cache_key,
            response.model_dump(mode="json", by_alias=True),
            self.settings.PLATFORM_RESOURCE_SUMMARY_CACHE_TTL_SECONDS,
        )
        return response

    def get_resource_trend(
        self,
        *,
        actor: AuthorizationActor,
        resource_type: str,
        range_value: str,
        refresh: bool = False,
    ) -> ResourceTrendResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_READ
        )
        days = _range_days(range_value)
        cache_key = self.cache.key(
            view="resource-trend",
            resource_type=resource_type,
            range_value=range_value,
            time_zone=self.settings.TZ,
        )
        if not refresh:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                return ResourceTrendResponse.model_validate(cached)
        start = (_utcnow().date() - timedelta(days=days - 1)).isoformat()
        rows = self.db.scalars(
            select(db_models.PlatformResourceDailyMetric)
            .where(
                db_models.PlatformResourceDailyMetric.resource_type == resource_type,
                db_models.PlatformResourceDailyMetric.time_zone == self.settings.TZ,
                db_models.PlatformResourceDailyMetric.local_date >= start,
            )
            .order_by(db_models.PlatformResourceDailyMetric.local_date)
        ).all()
        response = ResourceTrendResponse(
            resourceType=cast(ResourceType, resource_type),
            range=cast(RangeValue, range_value),
            timeZone=self.settings.TZ,
            calculatedAt=_utcnow(),
            collectionStartedAt=min(
                (row.collection_started_at for row in rows), default=None
            ),
            isStale=False,
            refreshInProgress=False,
            points=[
                ResourceTrendPoint(
                    date=row.local_date,
                    total=row.end_of_day_total,
                    created=row.created_count,
                    active=row.active_count,
                    deleted=row.deleted_count,
                )
                for row in rows
            ],
        )
        self.cache.set_json(
            cache_key,
            response.model_dump(mode="json", by_alias=True),
            self.settings.PLATFORM_RESOURCE_TREND_CACHE_TTL_SECONDS,
        )
        return response

    def get_capacity_trend(
        self,
        *,
        actor: AuthorizationActor,
        resource_type: str,
        range_value: str,
        refresh: bool = False,
    ) -> CapacityTrendResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_READ
        )
        days = _range_days(range_value)
        cache_key = self.cache.key(
            view="capacity-trend",
            resource_type=resource_type,
            range_value=range_value,
            time_zone=self.settings.TZ,
        )
        if not refresh:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                return CapacityTrendResponse.model_validate(cached)
        start = (_utcnow().date() - timedelta(days=days - 1)).isoformat()
        rows = self.db.scalars(
            select(db_models.PlatformResourceCapacityDailyMetric)
            .where(
                db_models.PlatformResourceCapacityDailyMetric.resource_type
                == resource_type,
                db_models.PlatformResourceCapacityDailyMetric.time_zone
                == self.settings.TZ,
                db_models.PlatformResourceCapacityDailyMetric.local_date >= start,
            )
            .order_by(db_models.PlatformResourceCapacityDailyMetric.local_date)
        ).all()
        by_date: dict[str, list[db_models.PlatformResourceCapacityDailyMetric]] = {}
        for row in rows:
            by_date.setdefault(row.local_date, []).append(row)
        response = CapacityTrendResponse(
            resourceType=cast(ResourceType, resource_type),
            range=cast(RangeValue, range_value),
            timeZone=self.settings.TZ,
            calculatedAt=_utcnow(),
            collectionStartedAt=min(
                (row.calculated_at for row in rows), default=None
            ),
            isStale=False,
            refreshInProgress=False,
            points=[
                CapacityTrendPoint(
                    date=point_date,
                    usedBytes=sum(row.used_bytes for row in date_rows),
                    allocatedBytes=(
                        sum(
                            row.allocated_bytes
                            for row in date_rows
                            if row.allocated_bytes is not None
                        )
                        or None
                    ),
                    unknownCount=sum(row.unknown_count for row in date_rows),
                    staleCount=sum(row.stale_count for row in date_rows),
                )
                for point_date, date_rows in by_date.items()
            ],
        )
        self.cache.set_json(
            cache_key,
            response.model_dump(mode="json", by_alias=True),
            self.settings.PLATFORM_RESOURCE_TREND_CACHE_TTL_SECONDS,
        )
        return response

    def aggregate_day(self, local_date: date | None = None) -> None:
        zone = ZoneInfo(self.settings.TZ)
        target = local_date or _utcnow().astimezone(zone).date()
        start_local = datetime.combine(target, time.min, tzinfo=zone)
        end_local = start_local + timedelta(days=1)
        start_utc = start_local.astimezone(timezone.utc)
        end_utc = end_local.astimezone(timezone.utc)
        for resource_type, model in (
            ("workspace", db_models.Workspace),
            ("knowledge_base", db_models.KnowledgeBase),
        ):
            total = (
                self.db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.created_at < end_utc)
                )
                or 0
            )
            created = (
                self.db.scalar(
                    select(func.count())
                    .select_from(model)
                    .where(model.created_at >= start_utc, model.created_at < end_utc)
                )
                or 0
            )
            active = self._active_count(
                resource_type, target.isoformat(), target.isoformat()
            )
            row = self.db.scalar(
                select(db_models.PlatformResourceDailyMetric).where(
                    db_models.PlatformResourceDailyMetric.local_date
                    == target.isoformat(),
                    db_models.PlatformResourceDailyMetric.time_zone
                    == self.settings.TZ,
                    db_models.PlatformResourceDailyMetric.resource_type
                    == resource_type,
                )
            )
            values = dict(
                end_of_day_total=total,
                created_count=created,
                deleted_count=0,
                active_count=active,
                collection_started_at=start_utc,
                calculated_at=_utcnow(),
            )
            if row is None:
                self.db.add(
                    db_models.PlatformResourceDailyMetric(
                        local_date=target.isoformat(),
                        time_zone=self.settings.TZ,
                        resource_type=resource_type,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(row, key, value)
        self.db.commit()
        self.cache.invalidate("workspace")
        self.cache.invalidate("knowledge_base")

    def snapshot_capacity(self, target: date) -> None:
        observations = self.db.scalars(
            select(db_models.ResourceCapacityObservation)
        ).all()
        grouped: dict[tuple[str, str], list[db_models.ResourceCapacityObservation]] = {}
        for observation in observations:
            existing = self.db.scalar(
                select(db_models.ResourceCapacityDailySnapshot).where(
                    db_models.ResourceCapacityDailySnapshot.local_date
                    == target.isoformat(),
                    db_models.ResourceCapacityDailySnapshot.time_zone
                    == self.settings.TZ,
                    db_models.ResourceCapacityDailySnapshot.resource_type
                    == observation.resource_type,
                    db_models.ResourceCapacityDailySnapshot.resource_id
                    == observation.resource_id,
                    db_models.ResourceCapacityDailySnapshot.storage_kind
                    == observation.storage_kind,
                )
            )
            if existing is None:
                self.db.add(
                    db_models.ResourceCapacityDailySnapshot(
                        local_date=target.isoformat(),
                        time_zone=self.settings.TZ,
                        resource_type=observation.resource_type,
                        resource_id=observation.resource_id,
                        storage_kind=observation.storage_kind,
                        used_bytes=observation.used_bytes,
                        allocated_bytes=observation.allocated_bytes,
                        host_available_bytes=observation.host_available_bytes,
                        measured_at=observation.measured_at,
                        captured_at=_utcnow(),
                    )
                )
            grouped.setdefault(
                (observation.resource_type, observation.storage_kind), []
            ).append(observation)
        for (resource_type, storage_kind), rows in grouped.items():
            metric = self.db.scalar(
                select(db_models.PlatformResourceCapacityDailyMetric).where(
                    db_models.PlatformResourceCapacityDailyMetric.local_date
                    == target.isoformat(),
                    db_models.PlatformResourceCapacityDailyMetric.time_zone
                    == self.settings.TZ,
                    db_models.PlatformResourceCapacityDailyMetric.resource_type
                    == resource_type,
                    db_models.PlatformResourceCapacityDailyMetric.storage_kind
                    == storage_kind,
                )
            )
            values = dict(
                used_bytes=sum(row.used_bytes for row in rows),
                allocated_bytes=sum(
                    row.allocated_bytes
                    for row in rows
                    if row.allocated_bytes is not None
                )
                or None,
                unknown_count=0,
                stale_count=sum(
                    CapacityGovernancePolicy.assess(
                        used_bytes=row.used_bytes,
                        allocated_bytes=row.allocated_bytes,
                        measured_at=row.measured_at,
                    ).stale
                    for row in rows
                ),
                calculated_at=_utcnow(),
            )
            if metric is None:
                self.db.add(
                    db_models.PlatformResourceCapacityDailyMetric(
                        local_date=target.isoformat(),
                        time_zone=self.settings.TZ,
                        resource_type=resource_type,
                        storage_kind=storage_kind,
                        **values,
                    )
                )
            else:
                for key, value in values.items():
                    setattr(metric, key, value)

    def snapshot_capacity_day(self, target: date) -> None:
        self.snapshot_capacity(target)
        self.db.commit()
        self.cache.invalidate("workspace")
        self.cache.invalidate("knowledge_base")

    def prune_raw_activity(self, now: datetime | None = None) -> int:
        cutoff = (now or _utcnow()) - timedelta(
            days=self.settings.PLATFORM_RESOURCE_ACTIVITY_RETENTION_DAYS
        )
        events = self.db.scalars(
            select(db_models.PlatformResourceActivityEvent).where(
                db_models.PlatformResourceActivityEvent.occurred_at < cutoff
            )
        ).all()
        memberships = self.db.scalars(
            select(db_models.PlatformResourceDailyActiveResource).where(
                db_models.PlatformResourceDailyActiveResource.first_occurred_at < cutoff
            )
        ).all()
        for row in [*events, *memberships]:
            self.db.delete(row)
        self.db.commit()
        return len(events) + len(memberships)

    def _active_count(self, resource_type: str, start: str, end: str) -> int:
        return (
            self.db.scalar(
                select(
                    func.count(
                        func.distinct(
                            db_models.PlatformResourceDailyActiveResource.resource_id
                        )
                    )
                ).where(
                    db_models.PlatformResourceDailyActiveResource.resource_type
                    == resource_type,
                    db_models.PlatformResourceDailyActiveResource.time_zone
                    == self.settings.TZ,
                    db_models.PlatformResourceDailyActiveResource.local_date >= start,
                    db_models.PlatformResourceDailyActiveResource.local_date <= end,
                )
            )
            or 0
        )

    def _capacity_totals(self, resource_type: str) -> tuple[int, int]:
        if resource_type == "knowledge_base":
            rows = self.db.scalars(select(db_models.KnowledgeBase)).all()
            used = sum(row.current_size_bytes or 0 for row in rows)
            near = sum(
                PlatformResourceCapacityInventory.knowledge_base_projection(
                    row,
                    default_quota_bytes=self.settings.DEFAULT_KB_QUOTA_BYTES,
                ).risk
                in {"warning", "critical"}
                for row in rows
            )
            return used, near
        rows = self.db.scalars(
            select(db_models.ResourceCapacityObservation).where(
                db_models.ResourceCapacityObservation.resource_type == "workspace"
            )
        ).all()
        used = sum(row.used_bytes for row in rows)
        near = 0
        for row in rows:
            risk = CapacityGovernancePolicy.assess(
                used_bytes=row.used_bytes,
                allocated_bytes=row.allocated_bytes,
                measured_at=row.measured_at,
            ).risk
            near += risk in {"warning", "critical"}
        return used, near

    def _distribution(self, resource_type: str) -> dict[str, int]:
        if resource_type == "workspace":
            result = {"running": 0, "transitioning": 0, "stopped": 0, "error": 0}
            for status in self.db.scalars(
                select(db_models.Workspace.runtime_status)
            ).all():
                if status in {"starting", "stopping", "restarting"}:
                    result["transitioning"] += 1
                elif status in result:
                    result[status] += 1
            return result
        result = {
            "public": 0,
            "private": 0,
            "success": 0,
            "processing": 0,
            "failure": 0,
            "never_indexed": 0,
        }
        for visibility, index_status in self.db.execute(
            select(
                db_models.KnowledgeBase.visibility,
                db_models.KnowledgeBase.last_index_status,
            )
        ).all():
            result[visibility] += 1
            if index_status in {"success", "completed"}:
                result["success"] += 1
            elif index_status in {"processing", "pending"}:
                result["processing"] += 1
            elif index_status in {"failure", "failed", "error"}:
                result["failure"] += 1
            else:
                result["never_indexed"] += 1
        return result


def _resource_model(resource_type: str):
    if resource_type == "workspace":
        return db_models.Workspace
    if resource_type == "knowledge_base":
        return db_models.KnowledgeBase
    raise PlatformResourceError("PLATFORM_RESOURCE_INVALID_RANGE", 422)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _range_days(value: str) -> int:
    try:
        return {"7d": 7, "30d": 30, "90d": 90}[value]
    except KeyError as exc:
        raise PlatformResourceError("PLATFORM_RESOURCE_INVALID_RANGE", 422) from exc


def _statistic(value: int, previous: int) -> StatisticValue:
    change = None if previous == 0 else ((value - previous) / previous) * 100
    return StatisticValue(
        value=value,
        previousValue=previous,
        changePercent=change,
    )


__all__ = ["PlatformResourceAnalytics"]
