"""Canvas service tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.modules.canvas.service import CanvasService
from app.modules.canvas.models import (
    CanvasReviewAreaTarget,
    CanvasReviewNoteCreate,
    CanvasReviewRect,
    CanvasReviewReplyCreate,
)


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
                    "type": "active",
                    "kind": "static",
                    "title": "Demo",
                    "owner": {"type": "skill", "skillName": "ppt-image-first"},
                    "manifestStatus": "valid",
                    "runtimeStatus": "healthy",
                    "defaultPath": "/",
                    "routes": [{"path": "/", "label": "Home"}],
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.detect("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.type == "active"
        assert response.kind == "static"
        assert response.title == "Demo"
        assert response.owner is not None
        assert response.owner.skill_name == "ppt-image-first"
        assert response.manifest_status == "valid"
        assert response.runtime_status == "healthy"
        assert [route.path for route in response.routes] == ["/"]
        assert response.routes[0].label == "Home"

    def test_routes_remote_success(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get.return_value = _mock_response(
                {
                    "type": "active",
                    "kind": "nextjs",
                    "title": "Next App",
                    "owner": {"type": "user"},
                    "manifestStatus": "valid",
                    "runtimeStatus": "healthy",
                    "defaultPath": "/",
                    "routes": [{"path": "/"}, {"path": "/about"}],
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.routes("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.type == "active"
        assert response.kind == "nextjs"
        assert response.title == "Next App"
        assert response.owner is not None
        assert response.owner.type == "user"
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
                    "type": "active",
                    "kind": "static",
                    "manifestStatus": "valid",
                    "runtimeStatus": "healthy",
                    "message": "synced",
                    "syncedAt": "2026-04-29T00:00:00Z",
                    "rendererAction": "reused",
                    "rendererActionReason": "manifest-unchanged",
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.sync("ws-1")

        assert response.workspace_id == "ws-1"
        assert response.status == "ok"
        assert response.type == "active"
        assert response.synced_at == "2026-04-29T00:00:00Z"
        assert response.kind == "static"
        assert response.runtime_status == "healthy"
        assert response.renderer_action == "reused"
        assert response.renderer_action_reason == "manifest-unchanged"
        assert response.details["rendererAction"] == "reused"
        mock_client.post.assert_called_once_with("http://localhost:3013/sync")

    def test_sync_allows_missing_optional_metadata(self, canvas_service: CanvasService) -> None:
        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = _mock_response(
                {
                    "status": "ok",
                    "type": "active",
                    "manifestStatus": "valid",
                    "message": "synced",
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.sync("ws-1")

        assert response.status == "ok"
        assert response.renderer_action is None
        assert response.renderer_action_reason is None

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
                    "type": "active",
                    "kind": "static",
                    "manifestStatus": "valid",
                    "runtimeStatus": "healthy",
                    "rendererRunning": True,
                    "portAvailable": True,
                    "message": "OK",
                    "source": "remote",
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = canvas_service.health("ws-1")

        assert result.status == "healthy"
        assert result.type == "active"
        assert result.kind == "static"
        assert result.runtime_status == "healthy"
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

    def test_delete_manifest_is_idempotent_and_syncs(self, canvas_service: CanvasService, tmp_path: Path) -> None:
        canvas_service._workspace_base = tmp_path
        manifest_path = tmp_path / ".aileron" / "canvas.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text("{}", encoding="utf-8")

        with patch("app.modules.canvas.service.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post.return_value = _mock_response(
                {
                    "status": "completed",
                    "detection": {
                        "manifestStatus": "missing",
                        "runtimeStatus": "healthy",
                    },
                }
            )
            mock_client_class.return_value.__enter__.return_value = mock_client

            response = canvas_service.delete_manifest("ws-1")
            second = canvas_service.delete_manifest("ws-1")

        assert response.deleted is True
        assert response.manifest_status == "missing"
        assert response.runtime_status == "healthy"
        assert second.deleted is False
        assert mock_client.post.call_count == 2


class TestCanvasReviewNotes:
    def test_review_note_lifecycle_is_workspace_scoped(
        self,
        canvas_service: CanvasService,
        tmp_path: Path,
    ) -> None:
        canvas_service._review_store_path = tmp_path / "notes.json"
        target = CanvasReviewAreaTarget(
            rect=CanvasReviewRect(x=1, y=2, width=100, height=80, coordinateSpace="viewport")
        )

        note = canvas_service.create_review_note(
            "ws-1",
            CanvasReviewNoteCreate(
                routePath="/",
                canvasUrl="http://canvas.local/",
                target=target,
                instruction="Move this area higher",
            ),
        )

        assert note.workspace_id == "ws-1"
        assert note.status == "open"
        assert canvas_service.list_review_notes("ws-2").total == 0
        assert canvas_service.list_review_notes("ws-1").total == 1

        seen = canvas_service.update_review_note_status("ws-1", note.id, "seen")
        assert seen.status == "seen"

        replied = canvas_service.append_review_note_reply(
            "ws-1",
            note.id,
            CanvasReviewReplyCreate(role="agent", content="Applied in source."),
        )
        assert replied.replies[0].role == "agent"

        applied = canvas_service.update_review_note_status("ws-1", note.id, "applied")
        assert applied.status == "applied"
        assert applied.resolved_at is not None

        canvas_service.delete_review_note("ws-1", note.id)
        assert canvas_service.list_review_notes("ws-1").total == 0
