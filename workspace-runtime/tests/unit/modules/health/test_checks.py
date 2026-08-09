"""Health service unit tests."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.modules.health.checks import HealthCheckService


def _service(monkeypatch) -> HealthCheckService:
    monkeypatch.setattr(
        "app.modules.health.checks.get_settings",
        lambda: SimpleNamespace(AILERON_WORKSPACE_ID="test-workspace"),
    )
    return HealthCheckService()


def test_get_container_id_returns_hostname(monkeypatch) -> None:
    service = _service(monkeypatch)
    monkeypatch.setattr("app.modules.health.checks.socket.gethostname", lambda: "pod-1")

    assert service.get_container_id() == "pod-1"


def test_get_container_id_tolerates_hostname_failure(monkeypatch) -> None:
    service = _service(monkeypatch)

    def _fail() -> str:
        raise OSError("hostname unavailable")

    monkeypatch.setattr("app.modules.health.checks.socket.gethostname", _fail)

    assert service.get_container_id() is None


def test_check_runtime_status_is_process_local(monkeypatch) -> None:
    service = _service(monkeypatch)
    now = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("app.modules.health.checks.utcnow", lambda: now)
    monkeypatch.setattr(service, "get_container_id", lambda: "pod-1")
    monkeypatch.setattr(
        service,
        "get_terminal_service_status",
        lambda: {"status": "ready", "port": 3004},
    )

    result = service.check_runtime_status()

    assert result == {
        "status": "healthy",
        "service": "workspace-runtime",
        "workspace_id": "test-workspace",
        "container_id": "pod-1",
        "runtime_status": "running",
        "last_seen": "2026-07-21T12:00:00+00:00Z",
        "timestamp": "2026-07-21T12:00:00+00:00Z",
        "updated": False,
        "terminal_service": {"status": "ready", "port": 3004},
    }
