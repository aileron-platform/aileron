"""Celery application configuration"""

from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings

settings = get_settings()

CELERY_TIMEZONE = os.getenv("TZ", "Asia/Taipei")

celery_app = Celery(
    "workspace-manager",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=CELERY_TIMEZONE,
    enable_utc=False,
    task_track_started=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    worker_send_task_events=False,
    worker_disable_rate_limits=True,
)

celery_app.conf.beat_schedule = {
    "automation-dispatch-due-jobs": {
        "task": "automation.dispatch_due_jobs",
        "schedule": 60.0,
    },
    "automation-cleanup-stuck-executions": {
        "task": "automation.cleanup_stuck_executions",
        "schedule": 300.0,
        "kwargs": {"timeout_minutes": 60},
    },
    "automation-cleanup-expired-queue": {
        "task": "automation.cleanup_expired_queue",
        "schedule": 300.0,
    },
    "knowledge-bases-reconcile-kb-quota": {
        "task": "knowledge_bases.reconcile_kb_quota",
        "schedule": crontab(hour=2, minute=0),
    },
    "knowledge-bases-cleanup-tombstoned-kb": {
        "task": "knowledge_bases.cleanup_tombstoned_kb",
        "schedule": crontab(hour=3, minute=0),
    },
}

app = celery_app
