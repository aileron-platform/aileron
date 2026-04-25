"""Canvas API integration tests."""

from __future__ import annotations

from datetime import datetime

from .helpers import override_dependency
from app.modules.canvas.dependencies import get_canvas_service
from app.modules.canvas.models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasRoute,
    CanvasRoutesResponse,
)


class StubCanvasService:
    def detect(self, workspace_id: str) -> CanvasDetectResponse:
        return CanvasDetectResponse(
            workspaceId=workspace_id,
            type="html",
            manifestStatus="valid",
            defaultPath="/",
            routes=[CanvasRoute(path="/", file="index.html")],
            detectedAt=datetime(2026, 4, 25),
        )

    def routes(self, workspace_id: str) -> CanvasRoutesResponse:
        routes = [
            CanvasRoute(path="/", file="index.html"),
            CanvasRoute(path="/docs", file="docs.html"),
        ]
        return CanvasRoutesResponse(
            workspaceId=workspace_id,
            type="html",
            manifestStatus="valid",
            defaultPath="/",
            routes=routes,
            total=len(routes),
            scannedAt=datetime(2026, 4, 25),
        )

    def sync(self, workspace_id: str) -> CanvasActionResponse:
        return CanvasActionResponse(
            workspaceId=workspace_id,
            status="ok",
            type="html",
            manifestStatus="valid",
            message="synced",
        )

    def reset(self, workspace_id: str) -> CanvasActionResponse:
        return CanvasActionResponse(
            workspaceId=workspace_id,
            status="ok",
            type="html",
            manifestStatus="valid",
            message="reset",
        )

    def health(self, workspace_id: str) -> CanvasHealthResponse:
        return CanvasHealthResponse(
            workspaceId=workspace_id,
            status="healthy",
            type="html",
            manifestStatus="valid",
            rendererRunning=True,
            portAvailable=True,
            message="Canvas service is healthy",
        )

    def logs(self, workspace_id: str) -> CanvasLogsResponse:
        return CanvasLogsResponse(
            workspaceId=workspace_id,
            logs=["management"],
            rendererLogs=["renderer"],
            total=2,
        )


def test_canvas_detect_and_routes(client) -> None:
    service = StubCanvasService()
    workspace_id = "ws_test_001"

    with override_dependency(get_canvas_service, lambda: service):
        detect_response = client.get(f"/api/v1/workspaces/{workspace_id}/canvas/detect")
        routes_response = client.get(f"/api/v1/workspaces/{workspace_id}/canvas/routes")

    assert detect_response.status_code == 200
    assert detect_response.json()["type"] == "html"
    assert detect_response.json()["manifestStatus"] == "valid"

    assert routes_response.status_code == 200
    payload = routes_response.json()
    assert payload["workspaceId"] == workspace_id
    assert payload["defaultPath"] == "/"
    assert [route["path"] for route in payload["routes"]] == ["/", "/docs"]


def test_canvas_sync_reset_health_and_logs(client) -> None:
    service = StubCanvasService()
    workspace_id = "ws_test_002"

    with override_dependency(get_canvas_service, lambda: service):
        sync_response = client.post(f"/api/v1/workspaces/{workspace_id}/canvas/sync")
        reset_response = client.post(f"/api/v1/workspaces/{workspace_id}/canvas/reset")
        health_response = client.get(f"/api/v1/workspaces/{workspace_id}/canvas/health")
        logs_response = client.get(f"/api/v1/workspaces/{workspace_id}/canvas/logs")

    assert sync_response.status_code == 202
    assert sync_response.json()["message"] == "synced"
    assert reset_response.status_code == 202
    assert reset_response.json()["message"] == "reset"
    assert health_response.status_code == 200
    assert health_response.json()["rendererRunning"] is True
    assert logs_response.status_code == 200
    assert logs_response.json()["rendererLogs"] == ["renderer"]


def test_removed_preview_routes_return_404(client) -> None:
    workspace_id = "ws_test_003"

    removed_prefix = "/" + "preview"
    assert client.get(
        f"/api/v1/workspaces/{workspace_id}{removed_prefix}/nextjs/routes"
    ).status_code in {404, 405}
    assert client.post(f"/api/v1/workspaces/{workspace_id}{removed_prefix}/sync").status_code in {
        404,
        405,
    }
    assert client.get(f"/api/v1/workspaces/{workspace_id}{removed_prefix}/health").status_code in {
        404,
        405,
    }
