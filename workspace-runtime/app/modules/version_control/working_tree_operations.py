"""Shared coordination boundary for working-tree mutations."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from collections.abc import Callable, Sequence
from typing import ContextManager, Iterator, Protocol, TypeVar

from aileron_git_core import (
    OperationKind,
    OperationManager,
    clear_locks,
    run_operation,
)

from .cache import GitCacheInvalidator
from .repository import GitUtils, VersionControlError
from .worktree_config import get_worktree_subdir

T = TypeVar("T")


class WorkingTreeContextError(RuntimeError):
    def __init__(self, code: str, status_code: int, message: str) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def resolve_working_tree_context(workspace_root: Path, context_id: str) -> Path:
    utils = GitUtils(
        workspace_root.parent,
        worktree_subdir=get_worktree_subdir(),
    )
    try:
        return utils.resolve_context_path(workspace_root.name, context_id)
    except VersionControlError as exc:
        raise WorkingTreeContextError(
            exc.error_code,
            exc.status_code,
            str(exc),
        ) from exc


class WorkingTreeOperationPort(Protocol):
    """Coordinate mutations without exposing Git implementation details."""

    def mutate(
        self,
        operation_key: str,
        operation_name: str,
    ) -> ContextManager[None]: ...

    def execute(
        self,
        *,
        workspace_id: str,
        operation_key: str,
        kind: OperationKind,
        operation_name: str,
        repo_root: Path,
        callback: Callable[[], T],
        cache_effects: Sequence[str],
        stale_threshold_seconds: int,
    ) -> T: ...


class WorkingTreeOperations:
    """Own mutation exclusion and post-success cache recovery."""

    def __init__(
        self,
        operation_manager: OperationManager,
        cache_invalidator: GitCacheInvalidator,
    ) -> None:
        self._operation_manager = operation_manager
        self._cache_invalidator = cache_invalidator

    @property
    def operation_manager(self) -> OperationManager:
        """Share the lock coordinator with the version-control application."""
        return self._operation_manager

    @classmethod
    def create(cls, cache_invalidator: GitCacheInvalidator) -> "WorkingTreeOperations":
        return cls(OperationManager(), cache_invalidator)

    @contextmanager
    def mutate(
        self,
        operation_key: str,
        operation_name: str,
    ) -> Iterator[None]:
        with self._operation_manager.acquire_file_write_barrier(
            operation_key,
            operation_name=operation_name,
        ):
            yield
        workspace_id = operation_key.split(":", 2)[1]
        self._cache_invalidator.invalidate_operation(workspace_id, "file_write")

    def execute(
        self,
        *,
        workspace_id: str,
        operation_key: str,
        kind: OperationKind,
        operation_name: str,
        repo_root: Path,
        callback: Callable[[], T],
        cache_effects: Sequence[str],
        stale_threshold_seconds: int,
    ) -> T:
        result = run_operation(
            self._operation_manager,
            key=operation_key,
            kind=kind,
            operation_name=operation_name,
            repo_root=repo_root,
            callback=callback,
            cache_effects=cache_effects,
            stale_threshold_seconds=stale_threshold_seconds,
        )
        if kind != OperationKind.READ:
            self._cache_invalidator.invalidate_effects(
                workspace_id,
                list(cache_effects),
            )
        return result

    def is_blocking_active(self, operation_key: str) -> bool:
        return self._operation_manager.is_blocking_active(operation_key)

    @staticmethod
    def clear_locks(repo_root: Path) -> list[Path]:
        return clear_locks(repo_root, force=True)

    def acquire(
        self,
        operation_key: str,
        *,
        kind: OperationKind,
        operation_name: str,
    ) -> ContextManager[None]:
        return self._operation_manager.acquire(
            operation_key,
            kind,
            operation_name=operation_name,
            cache_effects=(),
        )
