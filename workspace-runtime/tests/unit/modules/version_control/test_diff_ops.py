from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from git import GitCommandError

from app.modules.version_control.diff_ops import DiffOperations
from app.modules.version_control.utils import VersionControlError


def test_blob_not_found_raises_version_control_error() -> None:
    repo = MagicMock()
    repo.git.show.side_effect = GitCommandError("show", 1)
    utils = MagicMock()
    utils.get_repo.return_value = repo

    ops = DiffOperations(utils)

    with pytest.raises(VersionControlError) as exc:
        ops.blob("ws-1", "/missing.txt")

    assert exc.value.error_code == "VC_BLOB_NOT_FOUND"


def test_get_worktree_diff_returns_new_file_diff_for_untracked_file(monkeypatch, tmp_path: Path) -> None:
    repo = MagicMock()
    repo.working_tree_dir = str(tmp_path)
    file_path = tmp_path / "new.txt"
    file_path.write_text("hello\nworld\n", encoding="utf-8")
    repo.git.execute.side_effect = ["", "new.txt"]
    ops = DiffOperations(MagicMock())
    monkeypatch.setattr(ops, "_is_binary_file", lambda path: False)

    diff_text = ops._get_worktree_diff(repo, "new.txt", 3)

    assert "--- /dev/null" in diff_text
    assert "+++ b/new.txt" in diff_text


def test_create_new_file_diff_handles_binary_and_large_text(monkeypatch, tmp_path: Path) -> None:
    repo = MagicMock()
    repo.working_tree_dir = str(tmp_path)
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x00\x01")
    large_file = tmp_path / "large.txt"
    large_file.write_text("a" * (1024 * 1024 + 1), encoding="utf-8")
    ops = DiffOperations(MagicMock())

    monkeypatch.setattr(ops, "_is_binary_file", lambda path: path.name == "data.bin")
    assert "Binary file: data.bin" in ops._create_new_file_diff(repo, "data.bin")
    assert "Large text file: large.txt" in ops._create_new_file_diff(repo, "large.txt")


def test_get_file_metadata_and_commit_diff_fallbacks() -> None:
    repo = MagicMock()
    repo.git.ls_tree.side_effect = GitCommandError("ls-tree", 1)
    repo.git.diff.side_effect = GitCommandError("diff", 1)
    ops = DiffOperations(MagicMock())

    assert ops._get_file_metadata(repo, "a.txt", "HEAD") is None
    assert ops._get_commit_diff(repo, "a.txt", "HEAD~1", "HEAD", 3) == ""
