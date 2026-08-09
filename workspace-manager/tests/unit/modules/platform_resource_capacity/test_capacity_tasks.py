"""Capacity background workflow registration contract."""

from __future__ import annotations

from app.celery.app import celery_app


def test_capacity_expansion_delivery_is_registered_for_worker_and_beat() -> None:
    assert "app.modules.platform_resource_capacity.tasks" in celery_app.conf.include
    assert (
        celery_app.conf.beat_schedule["platform-resource-capacity-deliver-expansions"][
            "task"
        ]
        == "platform_resource_capacity.deliver_expansions"
    )
