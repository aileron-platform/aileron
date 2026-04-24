from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from git import GitCommandError

from app.modules.version_control.models import DiscardRequest, StageRequest, UnstageRequest
from app.modules.version_control.staging_ops import StagingOperations
from app.modules.version_control.utils import DiffEntry, VersionControlError


def test_get_changes_uses_cache_and_limits_untracked(tmp_path: Path) -> None:
    utils = MagicMock()
    repo = MagicMock()
    repo.working_tree_dir = str(tmp_path)
    utils.get_repo.return_value = repo
    utils.diff_index.side_effect = [[], []]
    cache = MagicMock()
    cache.get.return_value = {
        "branch": "main",
        "ahead": 0,
        "behind": 0,
        "detached": False,
        "hasConflicts": False,
        "staged": [],
        "unstaged": [],
        "untracked": [],
        "untrackedTotal": 0,
        "untrackedPage": 1,
        "untrackedPageSize": 100,
        "untrackedHasMore": False,
        "lastFetchedAt": None,
    }

    ops = StagingOperations(utils, cache)
    result = ops.get_changes("ws-1")
    assert result.untrackedTotal == 0

    cache.get.return_value = None
    repo.git.execute.return_value = "a.txt\nb.txt"
    repo.index.unmerged_blobs.return_value = {}
    utils.current_branch.return_value = ("main", False)
    utils.tracking_delta.return_value = (0, 0)
    utils.last_fetch_time.return_value = None
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    result = ops.get_changes("ws-1", page=1, page_size=1)
    assert len(result.untracked) == 1
    assert result.untrackedHasMore is True
    cache.set.assert_called()


def test_stage_and_unstage_invalidate_cache_and_raise_errors() -> None:
    utils = MagicMock()
    repo = MagicMock()
    utils.get_repo.return_value = repo
    utils.normalize_paths.return_value = ["a.py"]
    utils.diff_index.side_effect = [[DiffEntry("a.py", "A", "a", 1, 0, None)], []]
    cache = MagicMock()
    ops = StagingOperations(utils, cache)

    stage_result = ops.stage("ws-1", StageRequest(paths=["a.py"]))
    assert stage_result.staged == ["a.py"]
    assert cache.invalidate.call_count == 3

    repo.index.add.side_effect = GitCommandError("add", 1)
    with pytest.raises(VersionControlError) as exc:
        ops.stage("ws-1", StageRequest(paths=["a.py"]))
    assert exc.value.error_code == "VC_STAGE_FAILED"

    repo.index.add.side_effect = None
    utils.has_head.return_value = True
    utils.diff_index.side_effect = None
    utils.diff_index.return_value = [DiffEntry("b.py", "M", "m", 1, 1, None)]
    unstage_result = ops.unstage("ws-1", UnstageRequest(paths=["a.py"]))
    assert unstage_result.remainingStaged == 1

    repo.git.reset.side_effect = GitCommandError("reset", 1)
    with pytest.raises(VersionControlError) as exc:
        ops.unstage("ws-1", UnstageRequest(paths=["a.py"]))
    assert exc.value.error_code == "VC_UNSTAGE_FAILED"


def test_discard_and_to_file_change(tmp_path: Path) -> None:
    utils = MagicMock()
    repo = MagicMock()
    repo.working_tree_dir = str(tmp_path)
    utils.get_repo.return_value = repo
    utils.normalize_paths.return_value = ["dir", "tracked.txt", "missing.txt"]

    target_dir = tmp_path / "dir"
    target_dir.mkdir()
    (target_dir / "a.txt").write_text("x")
    tracked_file = tmp_path / "tracked.txt"
    tracked_file.write_text("tracked")

    ops = StagingOperations(utils)
    result = ops.discard("ws-1", DiscardRequest(paths=["dir", "tracked.txt", "missing.txt"]))
    assert result.discarded == ["dir", "tracked.txt", "missing.txt"]
    repo.git.checkout.assert_called_once_with("--", "missing.txt")

    utils.map_change_type.return_value = "modified"
    change = ops._to_file_change(DiffEntry(path="a\\b.txt", status="M", change_type="m", additions=1, deletions=2, patch="x"))
    assert change.path == "a/b.txt"
    assert change.type == "modified"
