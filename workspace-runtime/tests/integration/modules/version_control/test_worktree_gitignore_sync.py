from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

from app.modules.internal.dependencies import verify_manager_assertion
from app.modules.version_control.worktree_config import (
    DEFAULT_WORKTREE_SUBDIR,
    get_worktree_subdir,
    set_worktree_subdir,
)
from app.modules.version_control.worktree_gitignore import (
    BEGIN_MARKER,
    END_MARKER,
    LOCAL_HISTORY_IGNORE_RULE,
)

from .dependency_overrides import override_dependency

internal_router_module = importlib.import_module("app.modules.internal.router")


class FakeGitService:
    def __init__(self) -> None:
        self.subdirs: list[str] = []
        self.invalidated = False

    def set_worktree_subdir(self, subdir: str) -> None:
        self.subdirs.append(subdir)

    def invalidate_context_path_cache(self, workspace_id: str | None = None) -> None:
        self.invalidated = True


def test_sync_endpoint_rejects_unauthenticated_requests(
    client, tmp_path: Path, monkeypatch
) -> None:
    client.headers.clear()
    monkeypatch.setattr(
        internal_router_module,
        "get_settings",
        lambda: SimpleNamespace(AILERON_WORKSPACE_PATH=str(tmp_path)),
    )

    response = client.post(
        "/api/v1/internal/worktree/sync-gitignore",
        json={"subdir": "worktree", "previous": ".worktrees"},
    )

    assert response.status_code == 401
    assert not (tmp_path / ".gitignore").exists()


def test_sync_endpoint_rewrites_gitignore_updates_cache_and_invalidates_contexts(
    client,
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_service = FakeGitService()
    monkeypatch.setattr(internal_router_module, "get_git_service", lambda: fake_service)
    monkeypatch.setattr(
        internal_router_module,
        "get_settings",
        lambda: SimpleNamespace(AILERON_WORKSPACE_PATH=str(tmp_path)),
    )

    with override_dependency(verify_manager_assertion, lambda: None):
        response = client.post(
            "/api/v1/internal/worktree/sync-gitignore",
            json={"subdir": "worktree", "previous": ".worktrees"},
        )

    assert response.status_code == 200
    assert response.json() == {"changed": True}
    assert get_worktree_subdir() == "worktree"
    assert fake_service.subdirs == ["worktree"]
    assert fake_service.invalidated is True
    assert (tmp_path / ".gitignore").read_text() == (
        f"{BEGIN_MARKER}\n"
        "/worktree/\n"
        f"{LOCAL_HISTORY_IGNORE_RULE}\n"
        f"{END_MARKER}\n"
    )
    set_worktree_subdir(DEFAULT_WORKTREE_SUBDIR)
