from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from git import GitCommandError

from app.modules.version_control.models import CheckoutRequest
from app.modules.version_control.status_ops import StatusOperations
from app.modules.version_control.utils import DiffEntry, VersionControlError


def test_get_status_handles_untracked_query_failure_and_conflicts() -> None:
    repo = MagicMock()
    repo.git.execute.side_effect = GitCommandError("ls-files", 1)
    repo.index.unmerged_blobs.return_value = {"a.py": object()}
    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)
    utils.tracking_delta.return_value = (2, 1)
    utils.diff_index.side_effect = [
        [DiffEntry("a.py", "A", "a", 1, 0, None)],
        [DiffEntry("b.py", "M", "m", 1, 1, None)],
    ]
    utils.last_fetch_time.return_value = "2026-03-28T00:00:00Z"
    utils.map_change_type.side_effect = lambda status: {"A": "added", "M": "modified"}[status]

    ops = StatusOperations(utils)
    result = ops.get_status("ws-1")

    assert result.branch == "main"
    assert result.hasConflicts is True
    assert result.untrackedCount == 0
    assert result.stagedCount == 1
    assert result.unstagedCount == 1


def test_list_branches_skips_duplicate_remote_and_handles_missing_commit() -> None:
    tracking = SimpleNamespace(__str__=lambda self: "origin/main")
    local_commit = SimpleNamespace(
        hexsha="c1",
        message="msg\n",
        author=SimpleNamespace(name="Alice", email="a@example.com"),
        committed_datetime=datetime(2026, 3, 28, tzinfo=UTC),
    )
    local_branch = MagicMock()
    local_branch.name = "main"
    local_branch.tracking_branch.return_value = tracking
    local_branch.commit = local_commit

    broken_branch = MagicMock()
    broken_branch.name = "feature"
    broken_branch.tracking_branch.return_value = None
    type(broken_branch).commit = property(lambda self: (_ for _ in ()).throw(ValueError("missing")))

    remote_origin_head = SimpleNamespace(name="origin/HEAD", remote_head="HEAD")
    remote_origin_main = SimpleNamespace(name="origin/main", remote_head="main")
    remote_origin_other = SimpleNamespace(name="origin/other", remote_head="other")
    repo = MagicMock()
    repo.branches = [local_branch, broken_branch]
    repo.remotes = [SimpleNamespace(refs=[remote_origin_head, remote_origin_main, remote_origin_other])]
    repo.iter_commits.side_effect = GitCommandError("iter", 1)
    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)

    ops = StatusOperations(utils)
    result = ops.list_branches("ws-1", include_remote=True)

    assert [branch.name for branch in result.branches] == ["main", "feature", "origin/other"]
    assert result.branches[0].ahead == 0
    assert result.branches[1].lastCommit is None


def test_list_branches_lightweight_mode_skips_expensive_metadata() -> None:
    local_branch = MagicMock()
    local_branch.name = "main"
    repo = MagicMock()
    repo.branches = [local_branch]
    repo.remotes = []
    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)

    ops = StatusOperations(utils)
    result = ops.list_branches("ws-1", include_remote=False, include_metadata=False)

    assert result.branches[0].name == "main"
    assert result.branches[0].isActive is True
    local_branch.tracking_branch.assert_not_called()
    repo.iter_commits.assert_not_called()


def test_checkout_branch_handles_stash_and_checkout_errors() -> None:
    repo = MagicMock()
    utils = MagicMock()
    utils.get_repo.return_value = repo
    ops = StatusOperations(utils)

    repo.git.stash.side_effect = GitCommandError("stash", 1)
    with pytest.raises(VersionControlError) as exc:
        ops.checkout_branch("ws-1", "feature/x", CheckoutRequest(stashChanges=True))
    assert exc.value.error_code == "VC_STASH_FAILED"

    repo.git.stash.side_effect = None
    repo.git.checkout.side_effect = GitCommandError("checkout", 1)
    with pytest.raises(VersionControlError) as exc:
        ops.checkout_branch("ws-1", "feature/x", CheckoutRequest(create=True, startPoint="origin/main"))
    assert exc.value.error_code == "VC_BRANCH_CHECKOUT_FAILED"


def test_checkout_branch_create_success_returns_stash_message() -> None:
    repo = MagicMock()
    repo.git.stash.return_value = "stash@{0}: WIP on main"
    utils = MagicMock()
    utils.get_repo.return_value = repo

    ops = StatusOperations(utils)
    result = ops.checkout_branch("ws-1", "feature/x", CheckoutRequest(create=True, startPoint="origin/main", stashChanges=True))

    assert result.branch == "feature/x"
    assert result.created is True
    assert result.stashedChanges == "stash@{0}: WIP on main"
    repo.git.checkout.assert_called_once_with("-b", "feature/x", "origin/main")
