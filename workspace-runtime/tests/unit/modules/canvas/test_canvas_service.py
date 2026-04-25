"""Canvas service tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.canvas.service import CanvasService


@pytest.fixture
def canvas_service() -> CanvasService:
    return CanvasService()


def _mock_response(payload: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestCanvasServiceInitialization:
    def test_init(self, canvas_service: CanvasService) -> None:
        assert canvas_service._workspace_base == Path("/workspace")
        assert canvas_service._canvas_api_url == "http://localhost:3013"
        assert canvas_service._canvas_url == "http://localhost:3003"


class TestDetectionAndRoutes:
    def test_detect_remote_manifest(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value = _mock_response(
                {
                    "type": "html",
                    "manifestStatus": "valid",
                    "defaultPath": "/",
                    "routes": [{"path": "/", "file": "index.html"}],
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.detect("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.type == "html"
        assert response.manifest_status == "valid"
        assert [route.path for route in response.routes] == ["/"]

    def test_routes_remote_success(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value = _mock_response(
                {
                    "type": "nextjs",
                    "manifestStatus": "valid",
                    "defaultPath": "/",
                    "routes": [{"path": "/"}, {"path": "/about"}],
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.routes("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.type == "nextjs"
        assert [route.path for route in response.routes] == ["/", "/about"]
        assert response.total == 2

    def test_routes_falls_back_to_local_default(self, canvas_service: CanvasService) -> None:
        with patch(
            "app.modules.canvas.service.httpx.Client",
            side_effect=httpx.ConnectError("boom"),
        ):
            with patch.object(Path, "exists", return_value=False):
                with patch.object(Path, "glob", return_value=[]):
                    response = canvas_service.routes("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.type == "default"
        assert response.manifest_status == "missing"
        assert [route.path for route in response.routes] == ["/"]

    def test_detect_local_invalid_manifest(self, canvas_service: CanvasService) -> None:
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", side_effect=ValueError("bad json")):
                result = canvas_service._detect_local()

        assert result["type"] == "default"
        assert result["manifestStatus"] == "invalid"
        assert result["routes"] == []
        assert "bad json" in result["error"]


class TestActionsAndHealth:
    def test_sync_posts_to_canvas_management(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = _mock_response(
                {
                    "status": "ok",
                    "type": "html",
                    "manifestStatus": "valid",
                    "message": "synced",
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.sync("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.status == "ok"
        assert response.type == "html"
        mock_client.post.assert_called_once_with("http://localhost:3013/sync")

    def test_reset_reports_management_unavailable(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client", side_effect=RuntimeError("down")):
            response = canvas_service.reset("ws-1")

        assert response.status == "error"
        assert response.message == "CANVAS_MANAGEMENT_UNAVAILABLE"

    def test_health_success(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value = _mock_response(
                {
                    "status": "healthy",
                    "type": "html",
                    "manifestStatus": "valid",
                    "rendererRunning": True,
                    "portAvailable": True,
                    "message": "OK",
                    "source": "remote",
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = canvas_service.health("ws-1")

        assert result.status == "healthy"
        assert result.renderer_running is True
        assert result.port_available is True
        assert result.source == "remote"

    def test_health_connect_error(self, canvas_service: CanvasService) -> None:
        with patch(
            "app.modules.canvas.service.httpx.Client",
            side_effect=httpx.ConnectError("unavailable"),
        ):
            result = canvas_service.health("ws-1")

        assert result.status == "unhealthy"
        assert result.renderer_running is False
        assert result.message == "CANVAS_MANAGEMENT_UNAVAILABLE"

    def test_logs_normalizes_renderer_logs(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value = _mock_response(
                {"logs": ["management"], "rendererLogs": ["renderer"]}
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = canvas_service.logs("ws-1")

        assert result.logs == ["management"]
        assert result.renderer_logs == ["renderer"]
        assert result.total == 2
