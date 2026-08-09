import threading
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from typing import Dict, Iterator, Optional, Sequence
from uuid import uuid4

from .errors import GitOperationInProgressError
from .contracts import LockScope, LockScopeKeys, VersionControlOperation, lock_scopes_for
from .models import OperationKind, OperationMetadata


@dataclass
class _BlockingOperation:
    owner_thread_id: int
    depth: int
    metadata: OperationMetadata


class OperationManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._blocking_operations: Dict[str, _BlockingOperation] = {}
        self._file_write_operations: Dict[str, Dict[int, int]] = {}
        self._read_operations: Dict[str, Dict[int, int]] = {}

    @contextmanager
    def acquire(
        self,
        key: str,
        kind: OperationKind,
        *,
        operation_name: str = "",
        cache_effects: Sequence[str] = (),
        actor_display_name: str = "",
        blocking_scope: Optional[LockScope] = None,
        cancellable: bool = False,
    ) -> Iterator[None]:
        acquired_blocking = False
        if kind != OperationKind.READ:
            self._acquire_blocking(
                key,
                OperationMetadata(
                    operation_id=uuid4().hex,
                    key=key,
                    kind=kind,
                    operation_name=operation_name or kind.value,
                    blocking=True,
                    cache_effects=tuple(cache_effects),
                    actor_display_name=actor_display_name,
                    blocking_scope=blocking_scope,
                    cancellable=cancellable,
                ),
            )
            acquired_blocking = True
        try:
            yield
        finally:
            if acquired_blocking:
                self._release_blocking(key)

    def active_operation(self, key: str) -> Optional[OperationMetadata]:
        with self._lock:
            active = self._blocking_operations.get(key)
            return active.metadata if active is not None else None

    def is_blocking_active(self, key: str) -> bool:
        return self.active_operation(key) is not None

    def update_progress(
        self,
        key: str,
        *,
        current: int,
        total: int,
        phase: str,
    ) -> Optional[OperationMetadata]:
        with self._lock:
            active = self._blocking_operations.get(key)
            if active is None:
                return None
            active.metadata = replace(
                active.metadata,
                progress_current=max(current, 0),
                progress_total=max(total, 0),
                phase=phase,
            )
            return active.metadata

    def request_cancel(self, key: str) -> bool:
        with self._lock:
            active = self._blocking_operations.get(key)
            if active is None or not active.metadata.cancellable:
                return False
            active.metadata = replace(active.metadata, cancel_requested=True)
            return True

    def is_cancel_requested(self, key: str) -> bool:
        with self._lock:
            active = self._blocking_operations.get(key)
            return bool(active and active.metadata.cancel_requested)

    @contextmanager
    def acquire_file_write_barrier(
        self,
        key: str,
        *,
        operation_name: str = "file-write",
    ) -> Iterator[None]:
        _ = operation_name
        self._acquire_file_write(key)
        try:
            yield
        finally:
            self._release_file_write(key)

    def _acquire_blocking(self, key: str, metadata: OperationMetadata) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            if (
                metadata.kind == OperationKind.WORKING_TREE
                and self._has_other_thread_file_write(key, thread_id)
            ):
                raise GitOperationInProgressError(key)
            if self._has_other_thread_read(key, thread_id):
                raise GitOperationInProgressError(key, metadata.blocking_scope)
            active = self._blocking_operations.get(key)
            if active is not None:
                if active.owner_thread_id != thread_id:
                    raise GitOperationInProgressError(
                        key, blocking_scope=active.metadata.blocking_scope
                    )
                active.depth += 1
                return
            self._blocking_operations[key] = _BlockingOperation(
                owner_thread_id=thread_id,
                depth=1,
                metadata=metadata,
            )

    def _acquire_read(self, key: str) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            active = self._blocking_operations.get(key)
            if active is not None and active.owner_thread_id != thread_id:
                raise GitOperationInProgressError(
                    key, blocking_scope=active.metadata.blocking_scope
                )
            owners = self._read_operations.setdefault(key, {})
            owners[thread_id] = owners.get(thread_id, 0) + 1

    def _release_read(self, key: str) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            owners = self._read_operations[key]
            owners[thread_id] -= 1
            if owners[thread_id] == 0:
                del owners[thread_id]
            if not owners:
                del self._read_operations[key]

    def _has_other_thread_read(self, key: str, thread_id: int) -> bool:
        owners = self._read_operations.get(key)
        return bool(owners) and any(owner != thread_id for owner in owners)

    def _release_blocking(self, key: str) -> None:
        with self._lock:
            active = self._blocking_operations[key]
            active.depth -= 1
            if active.depth == 0:
                del self._blocking_operations[key]

    def _acquire_file_write(self, key: str) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            active = self._blocking_operations.get(key)
            if (
                active is not None
                and active.metadata.kind == OperationKind.WORKING_TREE
                and active.owner_thread_id != thread_id
            ):
                raise GitOperationInProgressError(key)
            thread_counts = self._file_write_operations.setdefault(key, {})
            thread_counts[thread_id] = thread_counts.get(thread_id, 0) + 1

    def _release_file_write(self, key: str) -> None:
        thread_id = threading.get_ident()
        with self._lock:
            thread_counts = self._file_write_operations[key]
            thread_counts[thread_id] -= 1
            if thread_counts[thread_id] == 0:
                del thread_counts[thread_id]
            if not thread_counts:
                del self._file_write_operations[key]

    def _has_other_thread_file_write(self, key: str, thread_id: int) -> bool:
        thread_counts = self._file_write_operations.get(key)
        if not thread_counts:
            return False
        return any(owner_thread_id != thread_id for owner_thread_id in thread_counts)

    @contextmanager
    def acquire_scoped(
        self,
        keys: LockScopeKeys,
        operation: VersionControlOperation,
        *,
        actor_display_name: str = "",
        cache_effects: Sequence[str] = (),
    ) -> Iterator[None]:
        """Acquire every operation scope in the canonical deadlock-free order."""
        with ExitStack() as stack:
            for scope in lock_scopes_for(operation):
                key = (
                    keys.common_repository
                    if scope == LockScope.COMMON_REPOSITORY
                    else keys.working_tree_target
                )
                stack.enter_context(
                    self.acquire(
                        key,
                        OperationKind.WRITE,
                        operation_name=operation.value,
                        cache_effects=cache_effects,
                        actor_display_name=actor_display_name,
                        blocking_scope=scope,
                        cancellable=(
                            operation == VersionControlOperation.LFS_SNAPSHOT_CONVERT
                        ),
                    )
                )
            yield

    @contextmanager
    def acquire_read_scoped(self, keys: LockScopeKeys) -> Iterator[None]:
        """Fence a read across shared repository and target state."""
        ordered_keys = (keys.common_repository, keys.working_tree_target)
        with ExitStack() as stack:
            for key in ordered_keys:
                self._acquire_read(key)
                stack.callback(self._release_read, key)
            yield
