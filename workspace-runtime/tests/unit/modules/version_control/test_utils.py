from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from git import InvalidGitRepositoryError

from app.modules.version_control.utils import DiffEntry, GitUtils, VersionControlError


def test_workspace_path_and_get_repo_errors(monkeypatch, tmp_path: Path) -> None:
    utils = GitUtils(tmp_path)

    with pytest.raises(VersionControlError) as exc:
        utils.workspace_path("missing")
    assert exc.value.error_code == "WORKSPACE_NOT_FOUND"

    repo_dir = tmp_path / "ws-1"
    repo_dir.mkdir()
    monkeypatch.setattr("app.modules.version_control.utils.Repo", lambda path: (_ for _ in ()).throw(InvalidGitRepositoryError()))
    with pytest.raises(VersionControlError) as exc:
        utils.get_repo("ws-1")
    assert exc.value.error_code == "VC_REPOSITORY_NOT_INITIALIZED"


def test_branch_and_tracking_helpers(tmp_path: Path) -> None:
    class Branch:
        name = "main"

        def tracking_branch(self):
            return Tracking()

        def __str__(self):
            return "main"

    class Tracking:
        def __str__(self):
            return "origin/main"

    branch = Branch()
    repo = SimpleNamespace(
        active_branch=branch,
        head=SimpleNamespace(commit=SimpleNamespace(hexsha="abcdef123456")),
        iter_commits=lambda rev: [1, 2] if rev == "origin/main..main" else [1],
    )

    assert GitUtils.current_branch(repo) == ("main", False)
    assert GitUtils.tracking_delta(repo) == (2, 1)

    class DetachedRepo:
        head = SimpleNamespace(commit=SimpleNamespace(hexsha="abcdef123456"))

        @property
        def active_branch(self):
            raise TypeError()

    assert GitUtils.current_branch(DetachedRepo()) == ("abcdef1", True)


def test_last_fetch_ignore_map_change_and_normalize(tmp_path: Path) -> None:
    fetch_head = tmp_path / "FETCH_HEAD"
    fetch_head.write_text("x")
    repo = MagicMock()
    repo.git_dir = str(tmp_path)

    assert GitUtils.last_fetch_time(repo) is not None
    assert GitUtils.should_ignore_file(".git/config") is True
    assert GitUtils.should_ignore_file("src/app.py") is False
    assert GitUtils.map_change_type("R") == "renamed"
    assert GitUtils.map_change_type("?") == "modified"
    assert GitUtils.normalize_paths(repo, ["/a.py", "b\\c.py"]) == ["a.py", "b/c.py"]

    with pytest.raises(VersionControlError):
        GitUtils.normalize_paths(repo, ["/", ""])


def test_diff_index_and_ensure_remote(tmp_path: Path) -> None:
    utils = GitUtils(tmp_path)
    diff_item = SimpleNamespace(a_path="old.py", b_path="new.py", change_type="r")
    diff_obj = [diff_item]
    diff_obj = type("DiffList", (list,), {"stats": {"files": {"old.py => new.py": {"insertions": 3, "deletions": 1}}}})(diff_obj)
    repo = MagicMock()
    repo.index.diff.side_effect = [diff_obj, []]
    repo.head.commit.hexsha = "abc"

    entries = utils.diff_index(repo, staged=True)
    assert entries == [DiffEntry(path="new.py", status="R", change_type="r", additions=3, deletions=1, patch=None)]

    repo.remotes = [SimpleNamespace(name="origin")]
    GitUtils.ensure_remote(repo, "origin")
    with pytest.raises(VersionControlError):
        GitUtils.ensure_remote(repo, "upstream")


def test_list_contexts_and_resolve_context_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws-1"
    workspace_root.mkdir()
    worktree_root = workspace_root / ".worktrees" / "feature-auth"
    worktree_root.mkdir(parents=True)

    utils = GitUtils(tmp_path)
    repo = MagicMock()
    repo.git.worktree.return_value = "\n".join([
        f"worktree {workspace_root}",
        "HEAD abcdef1234567890",
        "branch refs/heads/main",
        "",
        f"worktree {worktree_root}",
        "HEAD 1234567890abcdef",
        "branch refs/heads/feature-auth",
        "locked",
        "prunable stale",
        "",
    ])
    repo.head.commit.hexsha = "abcdef1234567890"
    repo.active_branch.name = "main"

    utils.get_repo = MagicMock(return_value=repo)  # type: ignore[method-assign]
    contexts = utils.list_contexts("ws-1")

    assert contexts.activeContextId == "primary"
    assert [context.id for context in contexts.contexts] == ["primary", "worktree:feature-auth"]
    assert contexts.contexts[1].locked is True
    assert contexts.contexts[1].prunable is True
    assert utils.resolve_context_path("ws-1", "worktree:feature-auth") == worktree_root.resolve()
    assert utils.resolve_context_path("ws-1", "worktree:feature-auth") == worktree_root.resolve()
    assert repo.git.worktree.call_count == 2


def test_resolve_context_path_invalidates_missing_cached_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws-1"
    workspace_root.mkdir()
    worktree_root = workspace_root / ".worktrees" / "feature-auth"
    worktree_root.mkdir(parents=True)

    utils = GitUtils(tmp_path)
    utils.list_contexts = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            contexts=[
                SimpleNamespace(id="worktree:feature-auth", repoPath=str(worktree_root)),
            ],
        )
    )

    assert utils.resolve_context_path("ws-1", "worktree:feature-auth") == worktree_root.resolve()
    worktree_root.rmdir()

    with pytest.raises(VersionControlError):
        utils.resolve_context_path("ws-1", "worktree:feature-auth")
    assert utils.list_contexts.call_count == 2
