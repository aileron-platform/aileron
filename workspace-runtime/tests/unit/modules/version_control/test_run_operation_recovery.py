import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aileron_git_core import GitCommandError, OperationKind
from aileron_git_core.errors import GitOperationInProgressError, GitStaleLockError

from app.modules.version_control.git_operations import GitService
from app.modules.version_control.repository import VersionControlError


def _service_factory(monkeypatch):
    svc = GitService.__new__(GitService)
    svc._working_tree_operations = MagicMock()
    svc._working_tree_operations.execute.side_effect = lambda **kwargs: kwargs[
        "callback"
    ]()
    svc._active_operations = {}
    svc._operation_status_lock = threading.Lock()
    svc._stale_threshold = 35
    svc._operation_key = lambda *a, **k: "k"
    svc._push_active_operation = lambda *a, **k: None
    svc._pop_active_operation = lambda *a, **k: None
    # repo root resolved internally via _utils.get_repo(...).working_tree_dir
    repo = MagicMock()
    repo.working_tree_dir = "/tmp/repo"
    utils = MagicMock()
    utils.get_repo.return_value = repo
    svc._utils = utils
    return svc


def test_run_operation_maps_stale_lock_to_force_unlockable(monkeypatch):
    svc = _service_factory(monkeypatch)
    svc._working_tree_operations.execute.side_effect = GitStaleLockError("k")
    with pytest.raises(VersionControlError) as ei:
        svc._run_operation(
            workspace_id="ws",
            context_id=None,
            kind=OperationKind.WRITE,
            operation_name="commit",
            cache_effects=[],
            callback=lambda: None,
        )
    assert ei.value.stale is True
    assert ei.value.can_force_unlock is True
    assert ei.value.error_code == "VC_OPERATION_IN_PROGRESS"


def test_run_operation_maps_collision_to_not_unlockable(monkeypatch):
    svc = _service_factory(monkeypatch)

    svc._working_tree_operations.execute.side_effect = GitOperationInProgressError("k")
    with pytest.raises(VersionControlError) as ei:
        svc._run_operation(
            workspace_id="ws",
            context_id=None,
            kind=OperationKind.WRITE,
            operation_name="commit",
            cache_effects=[],
            callback=lambda: None,
        )
    assert ei.value.stale is False
    assert ei.value.can_force_unlock is False


def test_run_operation_resolves_repo_root_internally_for_writes(monkeypatch):
    svc = _service_factory(monkeypatch)
    seen = {}
    svc._working_tree_operations.execute.side_effect = lambda **kwargs: (
        seen.__setitem__("root", kwargs["repo_root"]),
        kwargs["callback"](),
    )[1]
    svc._run_operation(
        workspace_id="ws",
        context_id=None,
        kind=OperationKind.WRITE,
        operation_name="stage",
        cache_effects=[],
        callback=lambda: "done",
    )
    assert seen["root"] == Path("/tmp/repo")
    svc._utils.get_repo.assert_called_once_with("ws", None)


def test_run_operation_maps_non_lock_git_command_error_to_500(monkeypatch):
    """A non-lock GitCommandError that escapes the recovery wrapper (and any
    GitCommandError raised by a READ callback) must become a structured
    VersionControlError(500, VC_OPERATION_FAILED) instead of a bare 500.

    The wrapper re-raises non-lock GitCommandError unchanged; the
    _run_operation safety net is what converts it.
    """
    svc = _service_factory(monkeypatch)
    non_lock = GitCommandError(["git", "add"], 1, stderr="not a lock error")

    def _propagate(*args, **kwargs):
        raise non_lock

    svc._working_tree_operations.execute.side_effect = _propagate
    with pytest.raises(VersionControlError) as ei:
        svc._run_operation(
            workspace_id="ws",
            context_id=None,
            kind=OperationKind.WRITE,
            operation_name="stage",
            cache_effects=[],
            callback=lambda: None,
        )
    assert ei.value.status_code == 500
    assert ei.value.error_code == "VC_OPERATION_FAILED"
    assert ei.value.__cause__ is non_lock


def test_run_operation_maps_read_git_command_error_to_500(monkeypatch):
    """READ callbacks bypass the recovery wrapper entirely, so a
    GitCommandError from a read (e.g. get_status) must still hit the safety
    net and become VC_OPERATION_FAILED rather than a bare 500.
    """
    svc = _service_factory(monkeypatch)
    non_lock = GitCommandError(["git", "status"], 1, stderr="boom")

    with pytest.raises(VersionControlError) as ei:
        svc._run_operation(
            workspace_id="ws",
            context_id=None,
            kind=OperationKind.READ,
            operation_name="get_status",
            cache_effects=[],
            callback=lambda: (_ for _ in ()).throw(non_lock),
        )
    assert ei.value.status_code == 500
    assert ei.value.error_code == "VC_OPERATION_FAILED"
    assert ei.value.__cause__ is non_lock
