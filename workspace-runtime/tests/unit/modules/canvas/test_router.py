from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.canvas.models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasManifestDeleteResponse,
    CanvasRoute,
    CanvasRoutesResponse,
)
from app.modules.canvas.router import router


class FakeCanvasService:
    def detect(self, workspace_id: str) -> CanvasDetectResponse:
        return CanvasDetectResponse(
            workspaceId=workspace_id,
            type="active",
            kind="static",
            title="Demo",
            owner=None,
            manifestStatus="valid",
            runtimeStatus="healthy",
            defaultPath="/",
            routes=[CanvasRoute(path="/")],
            detectedAt=datetime(2026, 3, 28),
        )

    def routes(self, workspace_id: str) -> CanvasRoutesResponse:
        return CanvasRoutesResponse(
            workspaceId=workspace_id,
            type="active",
            kind="static",
            title="Demo",
            owner=None,
            manifestStatus="valid",
            runtimeStatus="healthy",
            defaultPath="/",
            routes=[CanvasRoute(path="/"), CanvasRoute(path="/about")],
            total=2,
            scannedAt=datetime(2026, 3, 28),
        )

    def health(self, workspace_id: str) -> CanvasHealthResponse:
        return CanvasHealthResponse(
            workspaceId=workspace_id,
            status="healthy",
            type="active",
            kind="static",
            manifestStatus="valid",
            runtimeStatus="healthy",
            rendererRunning=True,
            portAvailable=True,
            message="ok",
        )

    def logs(self, workspace_id: str) -> CanvasLogsResponse:
        return CanvasLogsResponse(
            workspaceId=workspace_id,
            logs=["management"],
            rendererLogs=["renderer"],
            total=2,
        )

    def sync(self, workspace_id: str) -> CanvasActionResponse:
        return CanvasActionResponse(
            workspaceId=workspace_id,
            status="ok",
            type="active",
            kind="static",
            manifestStatus="valid",
            runtimeStatus="healthy",
            message="synced",
            syncedAt="2026-04-29T00:00:00Z",
            rendererAction="reused",
            rendererActionReason="nextjs-source-only",
        )

    def reset(self, workspace_id: str) -> CanvasActionResponse:
        return CanvasActionResponse(
            workspaceId=workspace_id,
            status="ok",
            type="active",
            kind="static",
            manifestStatus="valid",
            message="reset",
        )

    def delete_manifest(self, workspace_id: str) -> CanvasManifestDeleteResponse:
        return CanvasManifestDeleteResponse(
            workspaceId=workspace_id,
            deleted=True,
            manifestStatus="missing",
            runtimeStatus="healthy",
        )


def _client() -> TestClient:
    service = FakeCanvasService()
    app = FastAPI()
    app.include_router(router)

    from app.modules.canvas.dependencies import get_canvas_service

    app.dependency_overrides[get_canvas_service] = lambda: service
    return TestClient(app)


def test_canvas_router_happy_paths() -> None:
    client = _client()

    response = client.get("/workspaces/ws-1/canvas/detect")
    assert response.status_code == 200
    assert response.json()["type"] == "active"
    assert response.json()["kind"] == "static"

    response = client.get("/workspaces/ws-1/canvas/routes")
    assert response.status_code == 200
    assert response.json()["total"] == 2

    response = client.get("/workspaces/ws-1/canvas/health")
    assert response.status_code == 200
    assert response.json()["rendererRunning"] is True

    response = client.get("/workspaces/ws-1/canvas/logs")
    assert response.status_code == 200
    assert response.json()["rendererLogs"] == ["renderer"]

    response = client.post("/workspaces/ws-1/canvas/sync")
    assert response.status_code == 202
    assert response.json()["message"] == "synced"
    assert response.json()["rendererAction"] == "reused"

    response = client.post("/workspaces/ws-1/canvas/reset")
    assert response.status_code == 202
    assert response.json()["message"] == "reset"

    response = client.delete("/canvases/ws-1/manifest")
    assert response.status_code == 404

    response = client.delete("/workspaces/ws-1/canvas/manifest")
    assert response.status_code == 200
    assert response.json()["runtimeStatus"] == "healthy"


def test_old_preview_routes_are_removed() -> None:
    client = _client()

    removed_prefix = "/" + "preview"
    assert (
        client.get(f"/workspaces/ws-1{removed_prefix}/nextjs/routes").status_code == 404
    )
    assert client.post(f"/workspaces/ws-1{removed_prefix}/sync").status_code == 404
    assert client.get(f"/workspaces/ws-1{removed_prefix}/health").status_code == 404
