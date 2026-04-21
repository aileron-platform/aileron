"""Celery app 設定單元測試。"""

from __future__ import annotations

import pytest

from app.celery.app import celery_app


@pytest.mark.unit
def test_celery_beat_schedule_includes_knowledge_base_maintenance_jobs():
    beat_schedule = celery_app.conf.beat_schedule

    assert beat_schedule["knowledge-bases-reconcile-kb-quota"]["task"] == "knowledge_bases.reconcile_kb_quota"
    assert beat_schedule["knowledge-bases-cleanup-tombstoned-kb"]["task"] == "knowledge_bases.cleanup_tombstoned_kb"
    assert beat_schedule["knowledge-bases-reconcile-kb-quota"]["schedule"].hour == {2}
    assert beat_schedule["knowledge-bases-reconcile-kb-quota"]["schedule"].minute == {0}
    assert beat_schedule["knowledge-bases-cleanup-tombstoned-kb"]["schedule"].hour == {3}
    assert beat_schedule["knowledge-bases-cleanup-tombstoned-kb"]["schedule"].minute == {0}
