from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.file_system import dependencies as deps


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    deps._workspace_service = None
    deps._file_service = None
    yield
    deps._workspace_service = None
    deps._file_service = None


def test_get_workspace_service_returns_singleton(monkeypatch) -> None:
    created = []

    class StubWorkspaceService:
        def __init__(self) -> None:
            created.append(self)

    monkeypatch.setattr(deps, "WorkspaceDataService", StubWorkspaceService)

    first = deps.get_workspace_service()
    second = deps.get_workspace_service()

    assert first is second
    assert len(created) == 1


@pytest.mark.asyncio
async def test_get_workspace_path_returns_workspace_path_from_service(monkeypatch) -> None:
    workspace_service = SimpleNamespace(
        get_current_workspace_id=lambda: "ws-1",
        get_workspace=lambda workspace_id: None,
    )

    async def get_workspace(_: str):
        return SimpleNamespace(workspace_path="/tmp/workspace-1")

    workspace_service.get_workspace = get_workspace
    monkeypatch.setattr(deps, "get_workspace_service", lambda: workspace_service)

    result = await deps.get_workspace_path()

    assert result == "/tmp/workspace-1"


@pytest.mark.asyncio
async def test_get_workspace_path_falls_back_when_service_returns_none(monkeypatch) -> None:
    workspace_service = SimpleNamespace(
        get_current_workspace_id=lambda: "ws-2",
    )

    async def get_workspace(_: str):
        return None

    workspace_service.get_workspace = get_workspace
    monkeypatch.setattr(deps, "get_workspace_service", lambda: workspace_service)

    assert await deps.get_workspace_path() == "/workspace"


@pytest.mark.asyncio
async def test_get_file_service_caches_file_service(monkeypatch) -> None:
    created = []

    class StubFileService:
        def __init__(self, root_path: str) -> None:
            self.root_path = root_path
            created.append(self)

    async def fake_workspace_path() -> str:
        return "/tmp/runtime"

    monkeypatch.setattr(deps, "FileService", StubFileService)
    monkeypatch.setattr(deps, "get_workspace_path", fake_workspace_path)

    first = await deps.get_file_service()
    second = await deps.get_file_service()

    assert first is second
    assert first.root_path == "/tmp/runtime"
    assert len(created) == 1


def test_get_file_service_sync_uses_settings_workspace_path(monkeypatch) -> None:
    class StubFileService:
        def __init__(self, root_path: str) -> None:
            self.root_path = root_path

    monkeypatch.setattr(deps, "FileService", StubFileService)
    monkeypatch.setattr(
        "app.config.settings.get_settings",
        lambda: SimpleNamespace(WORKSPACE_PATH="/workspace-sync"),
    )

    service = deps.get_file_service_sync()

    assert service.root_path == "/workspace-sync"
