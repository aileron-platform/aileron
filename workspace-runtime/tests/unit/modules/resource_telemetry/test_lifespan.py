from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_starts_and_stops_resource_telemetry_reporter() -> None:
    reporter = AsyncMock()
    with (
        patch("app.main.build_resource_telemetry_reporter", return_value=reporter),
        patch("app.main.AutomationRunner.start", new_callable=AsyncMock),
        patch("app.main.AutomationRunner.shutdown", new_callable=AsyncMock),
        patch("app.main.AutomationControlPlaneClient.close", new_callable=AsyncMock),
        patch("app.main.reconcile_stale_running_threads", new_callable=AsyncMock),
        patch("app.main.set_resource_telemetry_scheduler") as set_scheduler,
    ):
        with TestClient(app):
            reporter.start.assert_awaited_once_with()
            assert app.state.resource_telemetry_reporter is reporter

    reporter.stop.assert_awaited_once_with()
    assert set_scheduler.call_args_list == [call(reporter), call(None)]
