"""Health router unit tests."""

from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

health_router_module = importlib.import_module("app.modules.health.router")


def test_health_router_success(monkeypatch) -> None:
    class FakeService:
        def check_runtime_status(self):
            return {
                "status": "healthy",
                "service": "workspace-runtime",
                "workspace_id": "ws-1",
            }

    monkeypatch.setattr(health_router_module, "HealthCheckService", FakeService)
    app = FastAPI()
    app.include_router(health_router_module.router)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_router_returns_503_on_local_failure(monkeypatch) -> None:
    class FakeService:
        def __init__(self):
            raise RuntimeError("local health unavailable")

    monkeypatch.setattr(health_router_module, "HealthCheckService", FakeService)
    app = FastAPI()
    app.include_router(health_router_module.router)

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unhealthy",
        "service": "workspace-runtime",
    }


def test_health_router_returns_503_when_automation_runner_is_fatal(monkeypatch) -> None:
    class FakeService:
        def check_runtime_status(self):
            return {"status": "healthy", "service": "workspace-runtime"}

    monkeypatch.setattr(health_router_module, "HealthCheckService", FakeService)
    app = FastAPI()
    app.state.automation_runner = type(
        "Runner", (), {"is_healthy": False, "fatal_reason": "agent_stop_failed"}
    )()
    app.include_router(health_router_module.router)

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    assert response.json()["automation_runner"]["fatal_reason"] == "agent_stop_failed"
