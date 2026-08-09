"""Process-local bridge from managed mutations to the telemetry scheduler."""

from __future__ import annotations

from typing import Protocol

from .models import ActivityType


class ResourceTelemetryScheduler(Protocol):
    def schedule_delayed_probe(self) -> None: ...

    def schedule_activity(self, event_type: ActivityType) -> None: ...


_scheduler: ResourceTelemetryScheduler | None = None


def set_resource_telemetry_scheduler(
    scheduler: ResourceTelemetryScheduler | None,
) -> None:
    global _scheduler
    _scheduler = scheduler


def notify_capacity_changed() -> None:
    scheduler = _scheduler
    if scheduler is not None:
        scheduler.schedule_delayed_probe()


def notify_agent_execution_started() -> None:
    scheduler = _scheduler
    if scheduler is not None:
        scheduler.schedule_activity("agent_execution_started")


__all__ = [
    "notify_agent_execution_started",
    "notify_capacity_changed",
    "set_resource_telemetry_scheduler",
]
