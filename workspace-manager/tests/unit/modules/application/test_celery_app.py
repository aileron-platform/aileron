"""Celery app Configuration Unit Test."""

from __future__ import annotations

import pytest

from app.celery.app import celery_app
from app.config.settings import get_settings


@pytest.mark.unit
def test_beat_schedule_keeps_runtime_recovery_and_kb_maintenance_tasks():
    beat_schedule = celery_app.conf.beat_schedule
    tasks = {entry["task"] for entry in beat_schedule.values()}

    assert celery_app.conf.task_default_queue == "celery"
    manager_session_cleanup = beat_schedule["manager-sessions-cleanup-expired"]
    assert manager_session_cleanup["task"] == "manager_sessions.cleanup_expired"
    assert manager_session_cleanup["schedule"] == 300
    assert not any(task.startswith("identities.") for task in tasks)
    recovery = beat_schedule["workspace-runtime-recover-and-dispatch-jobs"]
    assert recovery["task"] == "workspace_runtime.recover_and_dispatch_jobs"
    assert recovery["schedule"] == get_settings().RUNTIME_JOB_RECOVERY_INTERVAL_SECONDS
    kubernetes_status = beat_schedule["workspace-kubernetes-reconcile-status"]
    assert kubernetes_status["task"] == "workspace_kubernetes.reconcile_status"
    assert (
        kubernetes_status["schedule"]
        == get_settings().KUBERNETES_STATUS_RECONCILIATION_INTERVAL_SECONDS
    )
    assert "knowledge_bases.reconcile_kb_quota" in tasks
    assert not any(task.startswith("marketplace.reconcile") for task in tasks)
    assert not any(task.startswith("automation.") for task in tasks)
    assert beat_schedule["knowledge-bases-reconcile-kb-quota"]["schedule"].hour == {2}
    assert beat_schedule["knowledge-bases-reconcile-kb-quota"]["schedule"].minute == {0}


@pytest.mark.unit
def test_broker_connection_recovers_without_retry_limit():
    assert celery_app.conf.broker_connection_retry is True
    assert celery_app.conf.broker_connection_retry_on_startup is True
    assert celery_app.conf.broker_connection_max_retries is None
    assert celery_app.conf.broker_heartbeat == 10
    assert celery_app.conf.broker_heartbeat_checkrate == 2
    assert celery_app.conf.broker_transport_options["health_check_interval"] == 10
    assert celery_app.conf.broker_transport_options["socket_connect_timeout"] == 5
    assert celery_app.conf.broker_transport_options["socket_timeout"] == 5
    assert celery_app.conf.broker_transport_options["retry_on_timeout"] is True
