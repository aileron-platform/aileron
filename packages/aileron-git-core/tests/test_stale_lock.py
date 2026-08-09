import os
import time
from pathlib import Path

from aileron_git_core.stale_lock import (
    DEFAULT_STALE_THRESHOLD_SECONDS,
    clear_locks,
    detect_stale_locks,
)


def _git_dir(repo_root: Path) -> Path:
    gd = repo_root / ".git"
    gd.mkdir(parents=True, exist_ok=True)
    return gd


def test_detect_returns_locks_older_than_threshold(tmp_path):
    gd = _git_dir(tmp_path)
    lock = gd / "index.lock"
    lock.write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 10)
    os.utime(lock, (old, old))
    assert detect_stale_locks(tmp_path, DEFAULT_STALE_THRESHOLD_SECONDS) == [lock]


def test_detect_ignores_locks_younger_than_threshold(tmp_path):
    gd = _git_dir(tmp_path)
    lock = gd / "index.lock"
    lock.write_text("")
    assert detect_stale_locks(tmp_path, DEFAULT_STALE_THRESHOLD_SECONDS) == []


def test_clear_force_false_only_touches_index_lock_and_only_when_stale(tmp_path):
    gd = _git_dir(tmp_path)
    index_lock = gd / "index.lock"
    config_lock = gd / "config.lock"
    index_lock.write_text("")
    config_lock.write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 5)
    os.utime(index_lock, (old, old))
    os.utime(config_lock, (old, old))
    cleared = clear_locks(tmp_path, force=False)
    assert cleared == [index_lock]
    assert not index_lock.exists()
    assert config_lock.exists()  # untouched in auto path


def test_clear_force_true_removes_all_locks_unconditionally(tmp_path):
    gd = _git_dir(tmp_path)
    index_lock = gd / "index.lock"
    config_lock = gd / "config.lock"
    index_lock.write_text("")
    config_lock.write_text("")
    cleared = clear_locks(tmp_path, force=True)
    assert set(cleared) == {index_lock, config_lock}
    assert not index_lock.exists() and not config_lock.exists()


def test_clear_when_no_lock_exists_is_idempotent(tmp_path):
    _git_dir(tmp_path)
    assert clear_locks(tmp_path, force=True) == []


def test_clear_force_false_skips_when_live_git_process_present(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    gd = _git_dir(tmp_path)
    lock = gd / "index.lock"
    lock.write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 60)
    os.utime(lock, (old, old))
    monkeypatch.setattr(mod, "has_live_git_process", lambda root: True)
    assert clear_locks(tmp_path, force=False) == []
    assert lock.exists()  # NOT cleared while a live process is present


def test_clear_force_false_skips_young_lock_even_without_live_process(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    gd = _git_dir(tmp_path)
    lock = gd / "index.lock"
    lock.write_text("")  # age ~0, below threshold
    monkeypatch.setattr(mod, "has_live_git_process", lambda root: False)
    assert clear_locks(tmp_path, force=False) == []
    assert lock.exists()


from aileron_git_core.command_runner import GitCommandError
from aileron_git_core.errors import GitStaleLockError
from aileron_git_core.stale_lock import with_stale_lock_recovery


def _lock_error():
    return GitCommandError(
        ["git", "status"], 128, stdout="", stderr="Another git process holds index.lock"
    )


def test_recovery_retries_once_after_clearing_stale_lock(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    gd = _git_dir(tmp_path)
    (gd / "index.lock").write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 5)
    os.utime(gd / "index.lock", (old, old))
    monkeypatch.setattr(mod, "has_live_git_process", lambda root: False)

    calls = {"n": 0}

    def callback():
        calls["n"] += 1
        if calls["n"] == 1:
            raise _lock_error()
        return "ok"

    assert with_stale_lock_recovery(tmp_path, callback) == "ok"
    assert calls["n"] == 2


def test_recovery_raises_stale_lock_error_when_retry_still_blocked(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    gd = _git_dir(tmp_path)
    (gd / "index.lock").write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 5)
    os.utime(gd / "index.lock", (old, old))
    monkeypatch.setattr(mod, "has_live_git_process", lambda root: False)

    def callback():
        raise _lock_error()

    try:
        with_stale_lock_recovery(tmp_path, callback)
    except GitStaleLockError:
        return
    raise AssertionError("expected GitStaleLockError")


def test_recovery_does_not_retry_non_lock_errors(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    monkeypatch.setattr(mod, "has_live_git_process", lambda root: False)
    err = GitCommandError(["git", "x"], 1, stdout="", stderr="not a real repo")

    def callback():
        raise err

    try:
        with_stale_lock_recovery(tmp_path, callback)
    except GitCommandError as exc:
        assert exc is err
        return
    raise AssertionError("expected original GitCommandError to propagate")


def test_recovery_skips_clear_when_live_process_present(tmp_path, monkeypatch):
    import aileron_git_core.stale_lock as mod

    gd = _git_dir(tmp_path)
    (gd / "index.lock").write_text("")
    old = time.time() - (DEFAULT_STALE_THRESHOLD_SECONDS + 5)
    os.utime(gd / "index.lock", (old, old))
    monkeypatch.setattr(mod, "has_live_git_process", lambda root: True)  # live op

    def callback():
        raise _lock_error()

    try:
        with_stale_lock_recovery(tmp_path, callback)
    except GitStaleLockError:
        assert (gd / "index.lock").exists()  # not cleared
        return
    raise AssertionError("expected GitStaleLockError without clearing")
