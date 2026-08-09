"""Celery application configuration"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings

settings = get_settings()

CELERY_TIMEZONE = settings.TZ

celery_app = Celery(
    "workspace-manager",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.modules.auth.tasks",
        "app.modules.knowledge_base.tasks",
        "app.modules.platform_resource_analytics.tasks",
        "app.modules.platform_resource_capacity.tasks",
        "app.modules.workspace.tasks",
    ],
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
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=None,
    broker_heartbeat=10,
    broker_heartbeat_checkrate=2,
    broker_transport_options={
        "health_check_interval": 10,
        "socket_connect_timeout": 5,
        "socket_timeout": 5,
        "retry_on_timeout": True,
    },
)

celery_app.conf.beat_schedule = {
    "manager-sessions-cleanup-expired": {
        "task": "manager_sessions.cleanup_expired",
        "schedule": 300,
    },
    "workspace-runtime-recover-and-dispatch-jobs": {
        "task": "workspace_runtime.recover_and_dispatch_jobs",
        "schedule": settings.RUNTIME_JOB_RECOVERY_INTERVAL_SECONDS,
    },
    "workspace-kubernetes-reconcile-status": {
        "task": "workspace_kubernetes.reconcile_status",
        "schedule": settings.KUBERNETES_STATUS_RECONCILIATION_INTERVAL_SECONDS,
    },
    "workspace-docker-browser-connectivity-reconcile": {
        "task": "workspace_browser_connectivity.reconcile",
        "schedule": settings.TURN_BROWSER_CONNECTIVITY_RECONCILIATION_INTERVAL_SECONDS,
    },
    "workspace-firewall-reconcile-commands": {
        "task": "workspace_firewall.reconcile_commands",
        "schedule": settings.FIREWALL_SYNC_INTERVAL_SECONDS,
    },
    "knowledge-bases-reconcile-kb-quota": {
        "task": "knowledge_bases.reconcile_kb_quota",
        "schedule": crontab(hour=2, minute=0),
    },
    "platform-resources-hourly-aggregate": {
        "task": "platform_resources.aggregate_current_day",
        "schedule": crontab(minute=5),
    },
    "platform-resources-prune-raw-activity": {
        "task": "platform_resources.prune_raw_activity",
        "schedule": crontab(hour=3, minute=15),
    },
    "platform-resources-daily-capacity-snapshot": {
        "task": "platform_resources.snapshot_capacity_daily",
        "schedule": crontab(hour=0, minute=10),
    },
    "platform-resource-capacity-deliver-expansions": {
        "task": "platform_resource_capacity.deliver_expansions",
        "schedule": 5,
    },
}

app = celery_app
