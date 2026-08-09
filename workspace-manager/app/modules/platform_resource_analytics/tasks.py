"""Celery maintenance tasks for platform resource aggregates and retention."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.celery.app import celery_app
from app.config.settings import get_settings
from app.core.task_lease import task_lease
from app.db.database import SessionLocal, engine

from .projection import PlatformResourceAnalytics

HOURLY_AGGREGATE_LEASE = "platform-resources-hourly-aggregate"
DAILY_CAPACITY_SNAPSHOT_LEASE = "platform-resources-daily-capacity-snapshot"
DAILY_RAW_PRUNE_LEASE = "platform-resources-daily-raw-prune"


@celery_app.task(name="platform_resources.aggregate_current_day")  # type: ignore[untyped-decorator]
def aggregate_current_day() -> bool:
    settings = get_settings()
    local_date = datetime.now(ZoneInfo(settings.TZ)).date()
    with task_lease(engine, HOURLY_AGGREGATE_LEASE) as acquired:
        if not acquired:
            return False
        with SessionLocal() as db:
            PlatformResourceAnalytics(db).aggregate_day(local_date)
    return True


@celery_app.task(name="platform_resources.snapshot_capacity_daily")  # type: ignore[untyped-decorator]
def snapshot_capacity_daily() -> bool:
    settings = get_settings()
    local_date = datetime.now(ZoneInfo(settings.TZ)).date() - timedelta(days=1)
    with task_lease(engine, DAILY_CAPACITY_SNAPSHOT_LEASE) as acquired:
        if not acquired:
            return False
        with SessionLocal() as db:
            PlatformResourceAnalytics(db).snapshot_capacity_day(local_date)
    return True


@celery_app.task(name="platform_resources.prune_raw_activity")  # type: ignore[untyped-decorator]
def prune_raw_activity() -> int:
    with task_lease(engine, DAILY_RAW_PRUNE_LEASE) as acquired:
        if not acquired:
            return 0
        with SessionLocal() as db:
            return PlatformResourceAnalytics(db).prune_raw_activity()


__all__ = [
    "aggregate_current_day",
    "prune_raw_activity",
    "snapshot_capacity_daily",
]
