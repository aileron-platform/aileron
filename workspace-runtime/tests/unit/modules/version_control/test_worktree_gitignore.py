from __future__ import annotations

import os
from pathlib import Path

from app.modules.version_control.worktree_gitignore import (
    BEGIN_MARKER,
    END_MARKER,
    WorktreeGitignoreManager,
)


def test_ensure_creates_missing_gitignore(tmp_path: Path) -> None:
    changed = WorktreeGitignoreManager(tmp_path).ensure("worktree")

    assert changed is True
    assert (tmp_path / ".gitignore").read_text() == (
        f"{BEGIN_MARKER}\n"
        "/worktree/\n"
        "/.aileron/local-history/\n"
        f"{END_MARKER}\n"
    )


def test_ensure_appends_after_user_content(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n")

    changed = WorktreeGitignoreManager(tmp_path).ensure("worktree")

    assert changed is True
    assert gitignore.read_text() == (
        "node_modules/\n\n"
        f"{BEGIN_MARKER}\n"
        "/worktree/\n"
        "/.aileron/local-history/\n"
        f"{END_MARKER}\n"
    )


def test_ensure_replaces_existing_block(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "dist/\n" f"{BEGIN_MARKER}\n" "/.worktrees/\n" f"{END_MARKER}\n" "coverage/\n"
    )

    changed = WorktreeGitignoreManager(tmp_path).ensure("worktree")

    assert changed is True
    assert gitignore.read_text() == (
        "dist/\n"
        f"{BEGIN_MARKER}\n"
        "/worktree/\n"
        "/.aileron/local-history/\n"
        f"{END_MARKER}\n"
        "coverage/\n"
    )


def test_ensure_uses_atomic_rename(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[Path, Path]] = []
    real_replace = os.replace

    def capture_replace(source: Path, target: Path) -> None:
        calls.append((source, target))
        real_replace(source, target)

    monkeypatch.setattr(
        "app.modules.version_control.worktree_gitignore.os.replace", capture_replace
    )

    WorktreeGitignoreManager(tmp_path).ensure("worktree")

    assert calls == [(tmp_path / ".gitignore.tmp", tmp_path / ".gitignore")]


def test_ensure_returns_false_when_unchanged(tmp_path: Path) -> None:
    manager = WorktreeGitignoreManager(tmp_path)

    assert manager.ensure("worktree") is True
    assert manager.ensure("worktree") is False


def test_ensure_always_ignores_local_history(tmp_path: Path) -> None:
    changed = WorktreeGitignoreManager(tmp_path).ensure("worktree")

    assert changed is True
    assert "/.aileron/local-history/\n" in (tmp_path / ".gitignore").read_text()


def test_ensure_supports_nested_relative_worktree_paths(tmp_path: Path) -> None:
    changed = WorktreeGitignoreManager(tmp_path).ensure("branches/team-a")

    assert changed is True
    assert (tmp_path / ".gitignore").read_text() == (
        f"{BEGIN_MARKER}\n"
        "/branches/team-a/\n"
        "/.aileron/local-history/\n"
        f"{END_MARKER}\n"
    )


def test_ensure_removes_block_for_empty_subdir(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text(
        "dist/\n" f"{BEGIN_MARKER}\n" "/worktree/\n" f"{END_MARKER}\n" "coverage/\n"
    )

    changed = WorktreeGitignoreManager(tmp_path).ensure("")

    assert changed is True
    assert gitignore.read_text() == "dist/\ncoverage/\n"
