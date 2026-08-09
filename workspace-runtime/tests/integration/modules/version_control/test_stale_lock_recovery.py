"""End-to-end stale-lock recovery integration test.

Proves the stale on-disk ``.git/index.lock`` recovery works through the
real ``GitService.stage`` path (Phase A/B behavior):

* Case 1 (auto-recover): a real repo with a planted, aged ``index.lock`` and
  NO live git process pointing at it -> ``stage`` SUCCEEDS because
  ``with_stale_lock_recovery`` clears the stale lock and retries once. The
  lock file is gone afterwards.
* Case 2 (refuse while a live process is present): with
  ``has_live_git_process`` monkeypatched -> True (simulating a live git op on
  the repo), the SAME aged stale lock -> ``stage`` raises
  ``VersionControlError`` with ``status_code=409`` and
  ``stale=True`` and ``can_force_unlock=True``.

Why ``stale=True`` (not False) for Case 2: when ``has_live_git_process`` is
True, ``clear_locks(force=False)`` refuses to clear (treats it as live), the
single retry still hits the lock -> ``GitStaleLockError`` -> ``_run_operation``
maps that to the shared error-envelope lock flags (the on-disk lock remains
and the client MAY force-unlock). Only the in-memory collision path
(``GitOperationInProgressError``) yields ``stale=False``.

Avoiding the real 35s wait: each service is built with
``GIT_STALE_LOCK_THRESHOLD_SECONDS=1`` (read in ``GitService.__init__``) and
the planted lock is aged a few seconds past that with ``os.utime``.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import pytest

from aileron_git_core import stale_lock as stale_lock_module
from aileron_git_core.testkit import Actor, Repo

from app.config.settings import get_settings
from app.modules.version_control.models import StageRequest
from app.modules.version_control.git_operations import GitService
from app.modules.version_control.repository import VersionControlError

# Small stale threshold so we never wait the real 35s. Picked >1 so a planted
# lock aged a couple of seconds is unambiguously past the threshold even with
# filesystem mtime jitter.
STALE_THRESHOLD_SECONDS = 1
# How old to make the planted lock (well past the small threshold).
LOCK_AGE_SECONDS = 5


def _make_service_with_repo(tmp_path: Path) -> tuple[GitService, str, Path]:
    """Build a real GitService + workspace git repo for a single test case.

    Mirrors the conftest ``git_workspace`` fixture pattern (base_path =
    tmp dir, workspace_id subdir, real ``Repo.init`` + initial commit) but
    self-contained per case so the two cases never share state.
    """
    # GitService reads GIT_STALE_LOCK_THRESHOLD_SECONDS in __init__; set it
    # for this process before construction.
    os.environ["GIT_STALE_LOCK_THRESHOLD_SECONDS"] = str(STALE_THRESHOLD_SECONDS)
    get_settings.cache_clear()
    try:
        service = GitService(base_path=tmp_path)
    finally:
        # Restore the default so we do not leak the small threshold to other
        # tests in the same process.
        os.environ.pop("GIT_STALE_LOCK_THRESHOLD_SECONDS", None)
        get_settings.cache_clear()

    workspace_id = "ws-" + uuid.uuid4().hex[:8]
    repo_path = tmp_path / workspace_id
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(repo_path)

    readme = repo_path / "README.md"
    readme.write_text("# Demo\n\nInitial content.\n", encoding="utf-8")
    repo.index.add(["README.md"])
    actor = Actor("Test User", "test@example.com")
    repo.index.commit("Initial commit", author=actor, committer=actor)
    try:
        repo.git.branch("-m", "main")
    except Exception:  # pragma: no cover - rename no-op if already main
        pass

    # An untracked file for the stage operation to act on. The stage must
    # succeed against this path once the lock is cleared.
    untracked = repo_path / "untracked.txt"
    untracked.write_text("new file\n", encoding="utf-8")

    return service, workspace_id, repo_path


def _plant_stale_index_lock(repo_path: Path) -> Path:
    """Create an aged ``.git/index.lock`` inside the real repo."""
    lock = repo_path / ".git" / "index.lock"
    lock.write_text("", encoding="utf-8")
    old = time.time() - LOCK_AGE_SECONDS
    os.utime(lock, (old, old))
    return lock


@pytest.mark.integration
def test_stale_index_lock_is_auto_cleared_and_stage_succeeds(tmp_path: Path) -> None:
    """Case 1: stale lock + no live process -> stage auto-recovers."""
    service, workspace_id, repo_path = _make_service_with_repo(tmp_path)
    lock = _plant_stale_index_lock(repo_path)

    # Sanity: the lock is in place and considered stale at the small threshold.
    assert lock.exists()
    stale = stale_lock_module.detect_stale_locks(repo_path, STALE_THRESHOLD_SECONDS)
    assert lock in stale

    # No live git process points at this temp repo in the test container, so
    # has_live_git_process should be False here. Assert it to make the premise
    # of Case 1 explicit and fail loudly if the environment ever changes.
    assert stale_lock_module.has_live_git_process(repo_path) is False

    response = service.stage(workspace_id, StageRequest(paths=["untracked.txt"]))

    # The wrapper cleared the stale lock and retried the stage -> success.
    assert response.staged == ["untracked.txt"]
    assert not lock.exists(), "stale index.lock should have been auto-cleared"


@pytest.mark.integration
def test_stale_index_lock_with_live_process_raises_409_stale_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Case 2: stale lock + live process -> 409 with stale=True / canForceUnlock=True.

    When ``has_live_git_process`` reports a live op, ``clear_locks(force=False)``
    refuses to clear, the retry still hits the lock -> ``GitStaleLockError`` ->
    the shared application maps it to ``VersionControlError(409, stale=True,
    can_force_unlock=True)``. The on-disk lock remains and
    the client MAY force-unlock it.
    """
    service, workspace_id, repo_path = _make_service_with_repo(tmp_path)
    lock = _plant_stale_index_lock(repo_path)

    # Monkeypatch at the module the recovery wrapper resolves the name from.
    # `with_stale_lock_recovery` -> `clear_locks` both live in
    # aileron_git_core.stale_lock and reference `has_live_git_process` in that
    # module's namespace, so patching it there intercepts both call sites.
    monkeypatch.setattr(stale_lock_module, "has_live_git_process", lambda root: True)

    with pytest.raises(VersionControlError) as exc_info:
        service.stage(workspace_id, StageRequest(paths=["untracked.txt"]))

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == "operation_locked"

    # Real semantics: the on-disk lock is still there (could not be safely
    # cleared because a live process is present), so it IS stale and the
    # client is allowed to force-unlock it.
    assert exc_info.value.stale is True
    assert exc_info.value.can_force_unlock is True

    # The lock must still be on disk (force-clear was not used).
    assert lock.exists()
