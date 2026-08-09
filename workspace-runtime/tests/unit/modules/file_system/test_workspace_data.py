from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.file_system.workspace_data import WorkspaceDataService


@pytest.fixture
def service(monkeypatch) -> WorkspaceDataService:
    settings = SimpleNamespace(
        AILERON_WORKSPACE_ID="ws-current",
        AILERON_WORKSPACE_PATH="/workspace-bound",
        AILERON_WORKTREE_SUBDIR=".worktrees",
    )
    monkeypatch.setattr(
        "app.modules.file_system.workspace_data.get_settings", lambda: settings
    )
    return WorkspaceDataService()


@pytest.mark.asyncio
async def test_get_workspace_returns_current_workspace(
    service: WorkspaceDataService,
) -> None:
    workspace = await service.get_workspace("ws-current")

    assert workspace is not None
    assert workspace.id == "ws-current"
    assert workspace.name == "ws-current"
    assert workspace.workspace_path == "/workspace-bound"
    assert workspace.worktree_subdir == ".worktrees"
    assert workspace.runtime_status == "running"
    assert service.get_current_workspace_id() == "ws-current"


@pytest.mark.asyncio
async def test_get_workspace_rejects_different_workspace(
    service: WorkspaceDataService,
) -> None:
    assert await service.get_workspace("ws-other") is None


@pytest.mark.asyncio
async def test_get_workspace_uses_local_defaults(
    service: WorkspaceDataService,
) -> None:
    workspace = await service.get_workspace("ws-current")

    assert workspace is not None
    assert workspace.env_vars == []
    assert workspace.acp_cli_args == []
    assert workspace.agentic_tools == ["claude-code"]


@pytest.mark.asyncio
async def test_close_is_noop(service: WorkspaceDataService) -> None:
    assert await service.close() is None
