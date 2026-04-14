from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from git import GitCommandError

from app.modules.version_control.commit_ops import CommitOperations
from app.modules.version_control.models import CommitRequest
from app.modules.version_control.utils import VersionControlError


def _commit_obj(hexsha: str = "abc123"):
    return SimpleNamespace(
        hexsha=hexsha,
        message="test commit\n",
        author=SimpleNamespace(name="Tester", email="t@example.com"),
        committed_datetime=datetime(2026, 3, 28, tzinfo=UTC),
        stats=SimpleNamespace(total={"insertions": 2, "deletions": 1}),
    )


def test_commit_staging_failure_raises_version_control_error() -> None:
    repo = MagicMock()
    repo.index.add.side_effect = GitCommandError("add", 1, stderr="stage failed")
    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.normalize_paths.return_value = ["a.py"]

    ops = CommitOperations(utils)

    with pytest.raises(VersionControlError) as exc:
        ops.commit("ws-1", CommitRequest(message="msg", paths=["a.py"]))

    assert exc.value.error_code == "VC_STAGE_FAILED"


def test_commit_amend_invalidates_cache_and_returns_summary() -> None:
    repo = MagicMock()
    repo.head.commit = _commit_obj("commit-amend")
    utils = MagicMock()
    utils.get_repo.return_value = repo
    cache = MagicMock()

    ops = CommitOperations(utils, cache)
    result = ops.commit("ws-1", CommitRequest(message="amended", amend=True))

    assert result.commit.id == "commit-amend"
    assert result.commit.author.name == "Tester"
    assert result.commit.additions == 2
    repo.git.commit.assert_called_once()
    assert cache.invalidate.call_count == 3


def test_list_commits_with_search_and_head_fallback_branch() -> None:
    commit_one = SimpleNamespace(
        hexsha="c1",
        message="Fix login bug",
        author=SimpleNamespace(name="Alice", email="a@example.com"),
        committed_datetime=datetime(2026, 3, 28, tzinfo=UTC),
    )
    commit_two = SimpleNamespace(
        hexsha="c2",
        message="Add tests",
        author=SimpleNamespace(name="Bob", email="b@example.com"),
        committed_datetime=datetime(2026, 3, 27, tzinfo=UTC),
    )
    repo = MagicMock()
    repo.branches = [SimpleNamespace(name="main"), SimpleNamespace(name="feature")]
    utils = MagicMock()
    utils.get_repo.return_value = repo
    utils.current_branch.return_value = ("HEAD", False)
    utils.has_head.return_value = True
    repo.iter_commits.return_value = [commit_one, commit_two]
    repo.active_branch.name = "main"

    ops = CommitOperations(utils)
    result = ops.list_commits("ws-1", page=1, page_size=10, search="alice")

    assert result.total == 1
    assert result.items[0].id == "c1"
    repo.iter_commits.assert_called_with("main", max_count=1000)


def test_get_commit_falls_back_to_null_tree_and_manual_stats() -> None:
    diff = SimpleNamespace(a_path=None, b_path="src/app.py", change_type="m")
    commit = MagicMock()
    commit.hexsha = "c1"
    commit.message = "message\n"
    commit.author = SimpleNamespace(name="Tester", email="t@example.com")
    commit.committed_datetime = datetime(2026, 3, 28, tzinfo=UTC)
    commit.parents = [SimpleNamespace(hexsha="p1")]
    commit.stats = SimpleNamespace(total={}, files={"src/app.py": {"insertions": 4, "deletions": 2}})
    commit.diff.side_effect = [GitCommandError("diff", 1), [diff]]
    repo = MagicMock()
    repo.commit.return_value = commit
    repo.active_branch.name = "main"
    repo.head.is_detached = False
    utils = MagicMock()
    utils.get_repo.return_value = repo

    ops = CommitOperations(utils)
    result = ops.get_commit("ws-1", "c1")

    assert result.id == "c1"
    assert result.stats.additions == 4
    assert result.stats.deletions == 2
    assert result.changes[0].path == "src/app.py"
    assert result.changes[0].status == "M"


def test_get_commit_files_parses_statuses_and_handles_numstat_failure() -> None:
    commit = SimpleNamespace(hexsha="c1")
    repo = MagicMock()
    repo.commit.return_value = commit
    repo.git.diff_tree.side_effect = GitCommandError("diff-tree", 1)
    repo.git.show.return_value = "\n".join(
        [
            "diff --git a/old.txt b/new.txt",
            "rename from old.txt",
            "rename to new.txt",
            "diff --git a/create.txt b/create.txt",
            "new file mode 100644",
            "diff --git a/delete.txt b/delete.txt",
            "deleted file mode 100644",
        ]
    )
    utils = MagicMock()
    utils.get_repo.return_value = repo

    ops = CommitOperations(utils)
    result = ops.get_commit_files("ws-1", "c1")

    assert result.commitId == "c1"
    assert [item.status for item in result.files] == ["R", "A", "D"]
