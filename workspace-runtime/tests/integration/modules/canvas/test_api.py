"""Canvas API integration tests."""

from __future__ import annotations

from datetime import datetime

from .dependency_overrides import override_dependency
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
            type="active",
            kind="static",
            title="Demo",
            owner=None,
            manifestStatus="valid",
            runtimeStatus="healthy",
            defaultPath="/",
            routes=[CanvasRoute(path="/", label="Home")],
            detectedAt=datetime(2026, 4, 25),
        )

    def routes(self, workspace_id: str) -> CanvasRoutesResponse:
        routes = [
            CanvasRoute(path="/", label="Home"),
            CanvasRoute(path="/docs", label="Docs"),
        ]
        return CanvasRoutesResponse(
            workspaceId=workspace_id,
            type="active",
            kind="static",
            title="Demo",
            owner=None,
            manifestStatus="valid",
            runtimeStatus="healthy",
            defaultPath="/",
            routes=routes,
            total=len(routes),
            scannedAt=datetime(2026, 4, 25),
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
            rendererActionReason="manifest-unchanged",
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
    assert detect_response.json()["type"] == "active"
    assert detect_response.json()["kind"] == "static"
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
    assert sync_response.json()["rendererAction"] == "reused"
    assert reset_response.status_code == 202
    assert reset_response.json()["message"] == "reset"
    assert health_response.status_code == 200
    assert health_response.json()["rendererRunning"] is True
    assert logs_response.status_code == 200
    assert logs_response.json()["rendererLogs"] == ["renderer"]


def test_removed_preview_routes_fail_closed(client) -> None:
    workspace_id = "ws_test_003"

    removed_prefix = "/" + "preview"
    requests = [
        client.get(
            f"/api/v1/workspaces/{workspace_id}{removed_prefix}/nextjs/routes"
        ),
        client.post(f"/api/v1/workspaces/{workspace_id}{removed_prefix}/sync"),
        client.get(f"/api/v1/workspaces/{workspace_id}{removed_prefix}/health"),
    ]

    for response in requests:
        assert response.status_code == 403
        assert response.json()["detail"]["errorCode"] == (
            "WORKSPACE_RUNTIME_ACTION_FORBIDDEN"
        )
