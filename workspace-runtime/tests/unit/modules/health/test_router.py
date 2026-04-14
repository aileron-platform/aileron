from __future__ import annotations

import importlib
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

health_router_module = importlib.import_module("app.modules.health.router")


def test_health_router_success(monkeypatch) -> None:
    class FakeService:
        def __init__(self, db):
            self.db = db

        def check_and_update_workspace_status(self):
            return {"status": "healthy", "service": "workspace-runtime", "workspace_id": "ws-1"}

    monkeypatch.setattr(health_router_module, "HealthCheckService", FakeService)

    app = FastAPI()
    app.include_router(health_router_module.router)
    from app.database.session import get_db
    app.dependency_overrides[get_db] = lambda: "db"
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_router_degraded_on_exception(monkeypatch) -> None:
    class FakeService:
        def __init__(self, db):
            raise RuntimeError("db down")

    monkeypatch.setattr(health_router_module, "HealthCheckService", FakeService)
    monkeypatch.setattr(
        health_router_module,
        "get_settings",
        lambda: type("S", (), {"WORKSPACE_ID": "ws-1"})(),
    )
    monkeypatch.setattr(
        health_router_module,
        "utcnow",
        lambda: datetime(2026, 3, 28),
    )

    app = FastAPI()
    app.include_router(health_router_module.router)
    from app.database.session import get_db
    app.dependency_overrides[get_db] = lambda: "db"
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "Database connection failed" in response.json()["error"]
