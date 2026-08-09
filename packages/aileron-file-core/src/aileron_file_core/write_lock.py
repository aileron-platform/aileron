from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Hashable, Iterator, Optional, Tuple


ResourceWriteLockKey = Tuple[Hashable, ...]


class ResourceWriteLockTimeoutError(Exception):
    """Raised when a resource write lock cannot be acquired in time."""

    def __init__(self, key: ResourceWriteLockKey) -> None:
        super().__init__(f"Resource write lock is busy: {key!r}")
        self.key = key


@dataclass
class _LockEntry:
    condition: threading.Condition
    owner_thread_id: Optional[int] = None
    depth: int = 0
    waiters: int = 0


class ResourceWriteLockManager:
    """Process-local keyed write lock manager for compare-and-write sections."""

    def __init__(self) -> None:
        self._entries: dict[ResourceWriteLockKey, _LockEntry] = {}
        self._guard = threading.RLock()

    @contextmanager
    def lock(
        self,
        key: ResourceWriteLockKey,
        timeout: Optional[float] = None,
    ) -> Iterator[None]:
        self._acquire(key, timeout)
        try:
            yield
        finally:
            self._release(key)

    def is_locked(self, key: ResourceWriteLockKey) -> bool:
        with self._guard:
            entry = self._entries.get(key)
            return entry is not None and entry.owner_thread_id is not None

    def _acquire(
        self,
        key: ResourceWriteLockKey,
        timeout: Optional[float],
    ) -> None:
        thread_id = threading.get_ident()
        with self._guard:
            entry = self._entry_for_locked(key)
            if entry.owner_thread_id == thread_id:
                entry.depth += 1
                return

            if entry.owner_thread_id is None:
                entry.owner_thread_id = thread_id
                entry.depth = 1
                return

            deadline = time.monotonic() + timeout if timeout is not None else None
            entry.waiters += 1
            try:
                while entry.owner_thread_id is not None:
                    if deadline is None:
                        entry.condition.wait()
                        continue

                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ResourceWriteLockTimeoutError(key)
                    entry.condition.wait(timeout=remaining)

                entry.owner_thread_id = thread_id
                entry.depth = 1
            finally:
                entry.waiters -= 1
                self._cleanup_entry_locked(key, entry)

    def _release(self, key: ResourceWriteLockKey) -> None:
        thread_id = threading.get_ident()
        with self._guard:
            entry = self._entries[key]
            if entry.owner_thread_id != thread_id:
                raise RuntimeError(
                    f"Cannot release resource write lock not owned by this thread: {key!r}"
                )

            entry.depth -= 1
            if entry.depth > 0:
                return

            entry.owner_thread_id = None
            entry.condition.notify_all()
            self._cleanup_entry_locked(key, entry)

    def _entry_for_locked(self, key: ResourceWriteLockKey) -> _LockEntry:
        entry = self._entries.get(key)
        if entry is None:
            entry = _LockEntry(condition=threading.Condition(self._guard))
            self._entries[key] = entry
        return entry

    def _cleanup_entry_locked(
        self,
        key: ResourceWriteLockKey,
        entry: _LockEntry,
    ) -> None:
        if entry.owner_thread_id is None and entry.waiters == 0:
            self._entries.pop(key, None)
