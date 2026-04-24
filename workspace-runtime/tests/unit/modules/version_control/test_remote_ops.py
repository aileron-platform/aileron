from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from git import GitCommandError

from app.modules.version_control.models import FetchRequest, PullRequest, PushRequest
from app.modules.version_control.remote_ops import RemoteOperations
from app.modules.version_control.utils import VersionControlError


def _git_error(message: str) -> GitCommandError:
    return GitCommandError("git", 1, stderr=message)


def test_push_maps_statuses_and_errors() -> None:
    repo = Mock()
    remote = Mock()
    repo.remote.return_value = remote
    info_ok = SimpleNamespace(flags=0, ERROR=1, REJECTED=2, remote_ref_path="refs/heads/main")
    info_error = SimpleNamespace(flags=1, ERROR=1, REJECTED=2, remote_ref_path=None)
    info_rejected = SimpleNamespace(flags=2, ERROR=1, REJECTED=2, remote_ref_path="refs/heads/dev")
    remote.push.return_value = [info_ok, info_error, info_rejected]

    utils = Mock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)

    cache = Mock()
    ops = RemoteOperations(utils, cache)
    response = ops.push("ws-1", PushRequest(remote="origin", force=True))

    utils.ensure_remote.assert_called_once_with(repo, "origin")
    remote.push.assert_called_once_with("main", force=True)
    assert [update.status for update in response.updates] == ["ok", "error", "rejected"]
    assert response.updates[1].ref == "main"
    assert cache.invalidate.call_count == 3

    remote.push.side_effect = _git_error("push failed")
    with pytest.raises(VersionControlError, match="push failed"):
        ops.push("ws-1", PushRequest())


def test_pull_collects_commits_fast_forward_and_errors() -> None:
    repo = Mock()
    remote = Mock()
    repo.remote.return_value = remote
    repo.head.commit.hexsha = "old"
    repo.iter_commits.return_value = [
        SimpleNamespace(hexsha="new2", message="Second\n", author=SimpleNamespace(name="Bob")),
        SimpleNamespace(hexsha="new1", message="First\n", author=SimpleNamespace(name="Alice")),
    ]
    repo.commit.return_value = SimpleNamespace(parents=[SimpleNamespace(hexsha="old")])

    utils = Mock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)
    utils.has_head.side_effect = [True, True]

    def pull_side_effect(*args, **kwargs):
        repo.head.commit.hexsha = "new"
        return []

    remote.pull.side_effect = pull_side_effect

    cache = Mock()
    ops = RemoteOperations(utils, cache)
    response = ops.pull("ws-1", PullRequest(remote="origin", rebase=True, autostash=True))

    remote.pull.assert_called_once_with("main", rebase=True, autostash=True)
    assert response.fastForward is True
    assert [commit.id for commit in response.commits] == ["new1", "new2"]
    assert cache.invalidate.call_count == 5

    repo.commit.side_effect = ValueError("bad commit")
    utils.has_head.side_effect = [True, True]
    repo.head.commit.hexsha = "old"
    remote.pull.side_effect = pull_side_effect
    response = ops.pull("ws-1", PullRequest())
    assert response.fastForward is False

    utils.has_head.side_effect = [True]
    remote.pull.side_effect = _git_error("pull failed")
    with pytest.raises(VersionControlError, match="pull failed"):
        ops.pull("ws-1", PullRequest())


def test_pull_handles_missing_head_and_fetch_returns_refs() -> None:
    repo = Mock()
    remote = Mock()
    repo.remote.return_value = remote
    remote.fetch.return_value = [SimpleNamespace(name="origin/main"), SimpleNamespace(name="")]

    utils = Mock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("main", False)
    utils.has_head.return_value = False

    cache = Mock()
    ops = RemoteOperations(utils, cache)
    pull_response = ops.pull("ws-1", PullRequest(branch="feature"))
    fetch_response = ops.fetch("ws-1", FetchRequest(prune=True))

    remote.pull.assert_called_once_with("feature")
    assert pull_response.fastForward is False
    assert pull_response.commits == []
    remote.fetch.assert_called_once_with(prune=True)
    assert fetch_response.fetchedRefs == ["origin/main"]
    assert cache.invalidate.call_count == 8

    remote.fetch.side_effect = _git_error("fetch failed")
    with pytest.raises(VersionControlError, match="fetch failed"):
        ops.fetch("ws-1", FetchRequest())
