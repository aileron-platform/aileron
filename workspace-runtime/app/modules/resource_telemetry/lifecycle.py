"""Application composition for Runtime resource telemetry."""

from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.database.session import get_async_session_local

from .capacity import CapacityProbe, FilesystemCapacityProbe
from .outbox import SqlAlchemyTelemetryOutbox, TelemetryOutbox
from .reporter import ResourceTelemetryReporter
from .sink import ManagerResourceTelemetryClient, ResourceTelemetrySink

RUNTIME_HOME_PATH = Path("/home/developer")


def build_resource_telemetry_reporter(
    settings: Settings,
    *,
    probe: CapacityProbe | None = None,
    outbox: TelemetryOutbox | None = None,
    sink: ResourceTelemetrySink | None = None,
) -> ResourceTelemetryReporter:
    return ResourceTelemetryReporter(
        probe=probe
        if probe is not None
        else FilesystemCapacityProbe(
            workspace_path=Path(settings.AILERON_WORKSPACE_PATH),
            runtime_home_path=RUNTIME_HOME_PATH,
            timeout_seconds=settings.RESOURCE_TELEMETRY_PROBE_TIMEOUT_SECONDS,
        ),
        outbox=outbox
        if outbox is not None
        else SqlAlchemyTelemetryOutbox(get_async_session_local()),
        sink=sink
        if sink is not None
        else ManagerResourceTelemetryClient(
            manager_url=settings.AILERON_MANAGER_INTERNAL_URL,
            runtime_control_token=(
                settings.AILERON_RUNTIME_CONTROL_TOKEN_FILE.get_secret_value()
            ),
            workspace_id=settings.AILERON_WORKSPACE_ID,
            runtime_instance_id=settings.AILERON_RUNTIME_INSTANCE_ID,
        ),
        workspace_id=settings.AILERON_WORKSPACE_ID,
        runtime_instance_id=settings.AILERON_RUNTIME_INSTANCE_ID,
        interval_seconds=settings.RESOURCE_TELEMETRY_INTERVAL_SECONDS,
        retry_interval_seconds=settings.RESOURCE_TELEMETRY_RETRY_INTERVAL_SECONDS,
        delayed_probe_seconds=settings.RESOURCE_TELEMETRY_DELAYED_PROBE_SECONDS,
        shutdown_timeout_seconds=settings.RESOURCE_TELEMETRY_SHUTDOWN_TIMEOUT_SECONDS,
    )


__all__ = ["RUNTIME_HOME_PATH", "build_resource_telemetry_reporter"]
