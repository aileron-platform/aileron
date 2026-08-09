import threading
import time

import pytest

import aileron_file_core.write_lock as write_lock_module
from aileron_file_core import ResourceWriteLockManager, ResourceWriteLockTimeoutError


def test_same_key_blocks_other_thread() -> None:
    manager = ResourceWriteLockManager()
    entered = threading.Event()
    release = threading.Event()
    errors: list[Exception] = []

    def holder() -> None:
        with manager.lock(("workspace", "project", "README.md")):
            entered.set()
            release.wait(timeout=2)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(timeout=2)

    try:
        with pytest.raises(ResourceWriteLockTimeoutError):
            with manager.lock(("workspace", "project", "README.md"), timeout=0.01):
                errors.append(AssertionError("lock should not be acquired"))
    finally:
        release.set()
        thread.join(timeout=2)

    assert errors == []


def test_different_keys_can_run_concurrently() -> None:
    manager = ResourceWriteLockManager()
    with manager.lock(("workspace", "project", "a.txt"), timeout=0.01):
        with manager.lock(("workspace", "project", "b.txt"), timeout=0.01):
            assert True


def test_same_thread_reentrant_lock_is_allowed() -> None:
    manager = ResourceWriteLockManager()
    key = ("kb", "kb-1", "doc.md")
    with manager.lock(key, timeout=0.01):
        with manager.lock(key, timeout=0.01):
            assert manager.is_locked(key)


def test_lock_released_after_context_exit() -> None:
    manager = ResourceWriteLockManager()
    key = ("marketplace", "user-1", "registry", "pkg/manifest.json")
    with manager.lock(key, timeout=0.01):
        assert manager.is_locked(key)
    assert not manager.is_locked(key)


def test_is_locked_stays_consistent_with_nonblocking_acquire(monkeypatch) -> None:
    manager = ResourceWriteLockManager()
    key = ("workspace", "project", "consistent.txt")
    real_rlock = threading.RLock
    release_started = threading.Event()
    allow_release = threading.Event()

    class DelayedReleaseRLock:
        def __init__(self) -> None:
            self._lock = real_rlock()

        def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
            if timeout == -1:
                return self._lock.acquire(blocking)
            return self._lock.acquire(blocking, timeout)

        def release(self) -> None:
            release_started.set()
            allow_release.wait(timeout=2)
            self._lock.release()

    monkeypatch.setattr(write_lock_module.threading, "RLock", DelayedReleaseRLock)

    entered = threading.Event()
    begin_exit = threading.Event()
    observer_done = threading.Event()
    false_negatives: list[Exception] = []

    def holder() -> None:
        with manager.lock(key):
            entered.set()
            begin_exit.wait(timeout=2)

    def observer() -> None:
        while not observer_done.is_set():
            if not manager.is_locked(key):
                try:
                    with manager.lock(key, timeout=0):
                        pass
                except ResourceWriteLockTimeoutError as exc:
                    false_negatives.append(exc)
                    observer_done.set()
                    return
            time.sleep(0)

    holder_thread = threading.Thread(target=holder)
    observer_thread = threading.Thread(target=observer)
    holder_thread.start()
    assert entered.wait(timeout=2)
    observer_thread.start()

    try:
        begin_exit.set()
        release_started.wait(timeout=0.5)
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline and not false_negatives:
            time.sleep(0.001)
    finally:
        observer_done.set()
        allow_release.set()
        holder_thread.join(timeout=2)
        observer_thread.join(timeout=2)

    assert false_negatives == []
