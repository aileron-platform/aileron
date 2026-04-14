from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.modules.file_system.workspace_service import WorkspaceDataService


@pytest.fixture
def settings():
    return SimpleNamespace(
        MANAGER_URL="http://manager.test",
        WORKSPACE_ID="ws-current",
        manager_headers={"Authorization": "Bearer token"},
    )


@pytest.fixture
def client():
    mock = AsyncMock()
    mock.get = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def service(monkeypatch, settings, client):
    monkeypatch.setattr("app.modules.file_system.workspace_service.get_settings", lambda: settings)
    monkeypatch.setattr("app.modules.file_system.workspace_service.httpx.AsyncClient", lambda timeout: client)
    return WorkspaceDataService()


@pytest.mark.asyncio
async def test_get_workspace_maps_manager_response(service, client):
    response = MagicMock()
    response.json.return_value = {
        "id": "ws-123",
        "name": "Workspace",
        "workspacePath": "/tmp/workspace",
        "runtimeStatus": {"status": "running"},
        "envVars": [{"key": "A", "value": "1"}, "skip-me", {"key": "B", "value": "2"}],
        "acpCliArgs": ["--debug"],
    }
    response.raise_for_status.return_value = None
    client.get.return_value = response

    workspace = await service.get_workspace("ws-123")

    assert workspace is not None
    assert workspace.id == "ws-123"
    assert workspace.workspace_path == "/tmp/workspace"
    assert workspace.runtime_status == "running"
    assert workspace.env_vars[0].key == "A"
    assert workspace.env_vars[1].value == "2"
    assert workspace.acp_cli_args == ["--debug"]
    client.get.assert_awaited_once_with(
        "http://manager.test/api/v1/workspaces/ws-123",
        headers={"Authorization": "Bearer token"},
    )


@pytest.mark.asyncio
async def test_get_workspace_uses_defaults_for_optional_fields(service, client):
    response = MagicMock()
    response.json.return_value = {
        "id": "ws-456",
        "name": "Workspace 456",
    }
    response.raise_for_status.return_value = None
    client.get.return_value = response

    workspace = await service.get_workspace("ws-456")

    assert workspace is not None
    assert workspace.workspace_path == "/workspace"
    assert workspace.runtime_status == "stopped"
    assert workspace.env_vars == []
    assert workspace.acp_cli_args == []


@pytest.mark.asyncio
async def test_get_workspace_returns_none_on_http_error(service, client):
    client.get.side_effect = httpx.HTTPError("boom")

    workspace = await service.get_workspace("ws-http-error")

    assert workspace is None


@pytest.mark.asyncio
async def test_get_workspace_returns_none_on_unexpected_error(service, client):
    response = MagicMock()
    response.raise_for_status.side_effect = RuntimeError("unexpected")
    client.get.return_value = response

    workspace = await service.get_workspace("ws-runtime-error")

    assert workspace is None


def test_get_current_workspace_id_reads_settings(service):
    assert service.get_current_workspace_id() == "ws-current"


@pytest.mark.asyncio
async def test_close_closes_http_client(service, client):
    await service.close()

    client.aclose.assert_awaited_once()
