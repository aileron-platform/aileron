"""Preview Service 單元測試."""

from __future__ import annotations

from pathlib import Path
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.preview.models import PreviewSyncRequest
from app.modules.preview.service import PreviewService


@pytest.fixture
def preview_service():
    return PreviewService()


class TestPreviewServiceInitialization:
    def test_init(self, preview_service):
        assert preview_service._workspace_base == Path("/workspace")
        assert preview_service._sync_operations == {}


class TestScanNextJsRoutes:
    def test_scan_nextjs_routes_remote_success(self, preview_service):
        with patch("app.modules.preview.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "routes": [{"path": "/"}, {"path": "/about"}]
            }
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = preview_service.scan_nextjs_routes("ws-1")

        assert response.workspace_id == "ws-1"
        assert [route.path for route in response.routes] == ["/", "/about"]
        assert response.total == 2

    def test_scan_nextjs_routes_falls_back_to_local_scan(self, preview_service):
        with patch(
            "app.modules.preview.service.httpx.Client",
            side_effect=httpx.ConnectError("boom"),
        ):
            with patch.object(Path, "exists", return_value=False):
                response = preview_service.scan_nextjs_routes("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.routes == []
        assert response.total == 0

    def test_scan_routes_local_skips_empty_paths(self, preview_service):
        with patch.object(Path, "exists", return_value=True):
            with patch(
                "builtins.open",
                create=True,
            ) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    '{"routes": [{"path": "/"}, {"path": ""}, {"path": "/docs"}]}'
                )
                response = preview_service._scan_routes_local("ws-1")

        assert [route.path for route in response.routes] == ["/", "/docs"]
        assert response.total == 2

    def test_scan_routes_local_handles_invalid_json(self, preview_service):
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = "not json"
                response = preview_service._scan_routes_local("ws-1")

        assert response.routes == []
        assert response.total == 0


class TestSyncOperations:
    def test_start_sync_creates_operation(self, preview_service):
        response = preview_service.start_sync("ws-1", PreviewSyncRequest(force=False))

        assert response.workspace_id == "ws-1"
        assert response.status == "pending"
        assert response.operation_id in preview_service._sync_operations

    def test_execute_sync_marks_completed(self, preview_service):
        response = preview_service.start_sync("ws-1", PreviewSyncRequest(force=False))
        operation_id = response.operation_id

        with patch.object(preview_service, "_wait_for_nextjs_ready") as mock_wait:
            with patch("app.modules.preview.service.httpx.Client") as mock_client_class:
                mock_client = MagicMock()
                restart_response = MagicMock()
                restart_response.status_code = 200
                restart_response.json.return_value = {"message": "Restarting"}
                mock_client.post.return_value = restart_response
                mock_client_class.return_value.__enter__.return_value = mock_client

                preview_service.execute_sync(operation_id)

        status = preview_service._sync_operations[operation_id]
        assert status.status == "completed"
        assert status.progress == 1.0
        assert status.completed_at is not None
        mock_wait.assert_called_once_with(operation_id)

    def test_get_sync_status_not_found(self, preview_service):
        with pytest.raises(ValueError):
            preview_service.get_sync_status("missing")

    def test_execute_sync_missing_operation_is_noop(self, preview_service):
        preview_service.execute_sync("missing")

    def test_execute_sync_marks_failed_on_exception(self, preview_service):
        response = preview_service.start_sync("ws-1", PreviewSyncRequest(force=False))
        operation_id = response.operation_id

        with patch("app.modules.preview.service.httpx.Client", side_effect=RuntimeError("restart failed")):
            preview_service.execute_sync(operation_id)

        status = preview_service._sync_operations[operation_id]
        assert status.status == "failed"
        assert status.error == "restart failed"

    def test_wait_for_nextjs_ready_timeout_and_success(self, preview_service):
        with patch.object(time, "sleep") as mock_sleep:
            with patch.object(time, "time", side_effect=[0, 1, 2]):
                with patch("app.modules.preview.service.httpx.Client") as mock_client_class:
                    mock_client = MagicMock()
                    response = MagicMock()
                    response.status_code = 200
                    response.json.return_value = {"status": "healthy"}
                    mock_client.get.return_value = response
                    mock_client_class.return_value.__enter__.return_value = mock_client
                    preview_service._wait_for_nextjs_ready("op-1")
        mock_sleep.assert_not_called()

        with patch.object(time, "sleep") as mock_sleep:
            with patch.object(time, "time", side_effect=[0, 10, 20, 70, 80, 90]):
                with patch("app.modules.preview.service.httpx.Client") as mock_client_class:
                    mock_client = MagicMock()
                    mock_client.get.side_effect = RuntimeError("down")
                    mock_client_class.return_value.__enter__.return_value = mock_client
                    preview_service._wait_for_nextjs_ready("op-2")
        assert mock_sleep.call_count >= 1


class TestHealthCheck:
    def test_check_health_success(self, preview_service):
        with patch("app.modules.preview.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "healthy",
                "nextjs_running": True,
                "port_available": True,
                "message": "OK",
                "source": "remote",
            }
            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = preview_service.check_health("ws-1")

        assert result["status"] == "healthy"
        assert result["nextjs_running"] is True
        assert result["source"] == "remote"

    def test_check_health_connect_error(self, preview_service):
        with patch(
            "app.modules.preview.service.httpx.Client",
            side_effect=httpx.ConnectError("unavailable"),
        ):
            result = preview_service.check_health("ws-1")

        assert result["status"] == "unhealthy"
        assert result["nextjs_running"] is False

    def test_check_health_generic_error(self, preview_service):
        with patch(
            "app.modules.preview.service.httpx.Client",
            side_effect=RuntimeError("boom"),
        ):
            result = preview_service.check_health("ws-1")

        assert result["status"] == "unhealthy"
        assert "boom" in result["message"]
