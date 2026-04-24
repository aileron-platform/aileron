from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.modules.version_control.snapshot import WorkingTreeSnapshotProvider
from app.modules.version_control.utils import DiffEntry


def test_working_tree_snapshot_collects_shared_status_and_changes(tmp_path: Path) -> None:
    repo = MagicMock()
    repo.working_tree_dir = str(tmp_path)
    repo.git.execute.return_value = "a.txt\nb.txt"
    repo.index.unmerged_blobs.return_value = {"conflict.txt": object()}
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)
    utils.tracking_delta.return_value = (1, 2)
    utils.diff_index.side_effect = [
        [DiffEntry("staged.py", "A", "a", 1, 0, None)],
        [DiffEntry("changed.py", "M", "m", 3, 1, None)],
    ]
    utils.map_change_type.side_effect = lambda status: {"A": "added", "M": "modified"}[status]
    utils.last_fetch_time.return_value = "2026-04-24T00:00:00Z"

    snapshot = WorkingTreeSnapshotProvider(utils).get_snapshot("ws-1", page=1, page_size=1)

    assert snapshot.branch == "main"
    assert snapshot.ahead == 1
    assert snapshot.behind == 2
    assert snapshot.hasConflicts is True
    assert [item.path for item in snapshot.staged] == ["staged.py"]
    assert [item.path for item in snapshot.unstaged] == ["changed.py"]
    assert [item.path for item in snapshot.untracked] == ["a.txt"]
    assert snapshot.untrackedTotal == 2
    assert snapshot.untrackedHasMore is True


def test_working_tree_snapshot_reuses_cache() -> None:
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
    utils = MagicMock()

    snapshot = WorkingTreeSnapshotProvider(utils, cache).get_snapshot("ws-1", context_id="primary")

    assert snapshot.branch == "main"
    utils.get_repo.assert_not_called()
