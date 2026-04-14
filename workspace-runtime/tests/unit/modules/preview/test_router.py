from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.preview.models import PreviewSyncResponse
from app.modules.preview.router import router


class FakePreviewService:
    def scan_nextjs_routes(self, workspace_id: str):
        return {
            "workspaceId": workspace_id,
            "routes": [{"path": "/"}, {"path": "/about"}],
            "total": 2,
            "scannedAt": "2026-03-28T00:00:00Z",
        }

    def start_sync(self, workspace_id: str, payload):
        return PreviewSyncResponse(
            workspaceId=workspace_id,
            operationId="sync-1",
            status="pending",
            message="queued",
            startedAt=datetime(2026, 3, 28),
        )

    def execute_sync(self, operation_id: str) -> None:
        self.executed = operation_id

    def get_sync_status(self, operation_id: str):
        return {
            "workspaceId": "ws-1",
            "operationId": operation_id,
            "status": "completed",
            "progress": 1.0,
            "message": "done",
            "startedAt": "2026-03-28T00:00:00Z",
            "completedAt": "2026-03-28T00:01:00Z",
            "error": None,
        }

    def check_health(self, workspace_id: str):
        return {"status": "healthy", "nextjs_running": True, "port_available": True, "message": "ok"}


def test_preview_router_happy_paths() -> None:
    service = FakePreviewService()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides = {}
    from app.modules.preview.dependencies import get_preview_service

    app.dependency_overrides[get_preview_service] = lambda: service
    client = TestClient(app)

    assert client.get("/workspaces/ws-1/preview/nextjs/routes").status_code == 200

    response = client.post("/workspaces/ws-1/preview/sync", json={"force": True})
    assert response.status_code == 202
    assert response.json()["operationId"] == "sync-1"

    response = client.get("/workspaces/ws-1/preview/sync/sync-1")
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    response = client.get("/workspaces/ws-1/preview/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
