from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aileron_git_core import GitCommandResult, run_git

from app.modules.version_control.repository import (
    GitRepository,
    GitUtils,
    VersionControlError,
)


def test_workspace_path_and_get_repo_errors(tmp_path: Path) -> None:
    utils = GitUtils(tmp_path)

    with pytest.raises(VersionControlError) as exc:
        utils.workspace_path("missing")
    assert exc.value.error_code == "WORKSPACE_NOT_FOUND"

    repo_dir = tmp_path / "ws-1"
    repo_dir.mkdir()
    with pytest.raises(VersionControlError) as exc:
        utils.get_repo("ws-1")
    assert exc.value.error_code == "repository_not_initialized"


def test_branch_and_tracking_helpers(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run_git(repo_root, "init", "-b", "main")
    run_git(repo_root, "config", "user.name", "Test Bot")
    run_git(repo_root, "config", "user.email", "test@example.com")
    (repo_root / "tracked.txt").write_text("committed\n", encoding="utf-8")
    run_git(repo_root, "add", "tracked.txt")
    run_git(repo_root, "commit", "-m", "initial commit")
    repo = GitRepository(repo_root)

    assert GitUtils.current_branch(repo) == ("main", False)
    assert GitUtils.tracking_delta(repo) == (0, 0)

    run_git(repo_root, "checkout", "--detach")
    assert GitUtils.current_branch(repo) == (GitUtils.head_sha(repo)[:7], True)


def test_last_fetch_ignore_and_normalize(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    fetch_head = git_dir / "FETCH_HEAD"
    fetch_head.write_text("x")
    repo = GitRepository(tmp_path)

    assert GitUtils.last_fetch_time(repo) is not None
    assert GitUtils.should_ignore_file(".git/config") is True
    assert GitUtils.should_ignore_file("src/app.py") is False
    assert GitUtils.normalize_paths(repo, ["/a.py", "b\\c.py"]) == ["a.py", "b/c.py"]

    with pytest.raises(VersionControlError):
        GitUtils.normalize_paths(repo, ["/", ""])


def test_ensure_remote(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    run_git(repo_root, "init")
    repo = GitRepository(repo_root)
    run_git(repo_root, "remote", "add", "origin", "https://example.test/repo.git")
    GitUtils.ensure_remote(repo, "origin")
    with pytest.raises(VersionControlError):
        GitUtils.ensure_remote(repo, "upstream")


def test_list_contexts_and_resolve_context_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace_root = tmp_path / "ws-1"
    workspace_root.mkdir()
    worktree_root = workspace_root / "worktree" / "feature-auth"
    worktree_root.mkdir(parents=True)

    utils = GitUtils(tmp_path, worktree_subdir="worktree")
    repo = GitRepository(workspace_root)
    worktree_output = "\n".join(
        [
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
        ]
    )
    run_git_mock = MagicMock(
        return_value=GitCommandResult(
            args=["git"], returncode=0, stdout=worktree_output, stderr=""
        )
    )
    monkeypatch.setattr("app.modules.version_control.repository.run_git", run_git_mock)
    utils.current_branch = MagicMock(return_value=("main", False))  # type: ignore[method-assign]
    utils.head_sha = MagicMock(return_value="abcdef1234567890")  # type: ignore[method-assign]

    utils.get_repo = MagicMock(return_value=repo)  # type: ignore[method-assign]
    contexts = utils.list_contexts("ws-1")

    assert contexts.activeContextId == "primary"
    assert [context.id for context in contexts.contexts] == [
        "primary",
        "worktree:feature-auth",
    ]
    assert contexts.contexts[1].locked is True
    assert contexts.contexts[1].prunable is True
    assert (
        utils.resolve_context_path("ws-1", "worktree:feature-auth")
        == worktree_root.resolve()
    )
    assert (
        utils.resolve_context_path("ws-1", "worktree:feature-auth")
        == worktree_root.resolve()
    )
    assert run_git_mock.call_count == 2


def test_resolve_context_path_invalidates_missing_cached_path(tmp_path: Path) -> None:
    workspace_root = tmp_path / "ws-1"
    workspace_root.mkdir()
    worktree_root = workspace_root / ".worktrees" / "feature-auth"
    worktree_root.mkdir(parents=True)

    utils = GitUtils(tmp_path)
    utils.list_contexts = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(
            contexts=[
                SimpleNamespace(
                    id="worktree:feature-auth", repoPath=str(worktree_root)
                ),
            ],
        )
    )

    assert (
        utils.resolve_context_path("ws-1", "worktree:feature-auth")
        == worktree_root.resolve()
    )
    worktree_root.rmdir()

    with pytest.raises(VersionControlError):
        utils.resolve_context_path("ws-1", "worktree:feature-auth")
    assert utils.list_contexts.call_count == 2


def test_list_contexts_skips_worktrees_outside_configured_subdir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workspace_root = tmp_path / "ws-1"
    workspace_root.mkdir()
    legacy_worktree_root = workspace_root / ".worktrees" / "legacy"
    legacy_worktree_root.mkdir(parents=True)

    utils = GitUtils(tmp_path, worktree_subdir="worktree")
    repo = GitRepository(workspace_root)
    worktree_output = "\n".join(
        [
            f"worktree {workspace_root}",
            "HEAD abcdef1234567890",
            "branch refs/heads/main",
            "",
            f"worktree {legacy_worktree_root}",
            "HEAD 1234567890abcdef",
            "branch refs/heads/legacy",
            "",
        ]
    )
    monkeypatch.setattr(
        "app.modules.version_control.repository.run_git",
        MagicMock(
            return_value=GitCommandResult(
                args=["git"], returncode=0, stdout=worktree_output, stderr=""
            )
        ),
    )
    utils.current_branch = MagicMock(return_value=("main", False))  # type: ignore[method-assign]
    utils.head_sha = MagicMock(return_value="abcdef1234567890")  # type: ignore[method-assign]

    utils.get_repo = MagicMock(return_value=repo)  # type: ignore[method-assign]
    contexts = utils.list_contexts("ws-1")

    assert [context.id for context in contexts.contexts] == ["primary"]
