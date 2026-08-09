"""Shared Git operation execution lifecycle."""

from pathlib import Path
from typing import Callable, Sequence, TypeVar

from .models import OperationKind
from .operation_lock import OperationManager
from .stale_lock import DEFAULT_STALE_THRESHOLD_SECONDS, with_stale_lock_recovery

T = TypeVar("T")


def run_operation(
    manager: OperationManager,
    *,
    key: str,
    kind: OperationKind,
    operation_name: str,
    repo_root: Path,
    callback: Callable[[], T],
    cache_effects: Sequence[str] = (),
    stale_threshold_seconds: int = DEFAULT_STALE_THRESHOLD_SECONDS,
) -> T:
    """Run one operation under the shared in-process and on-disk lock lifecycle."""
    with manager.acquire(
        key,
        kind,
        operation_name=operation_name,
        cache_effects=cache_effects,
    ):
        if kind == OperationKind.READ:
            return callback()
        return with_stale_lock_recovery(
            repo_root,
            callback,
            threshold_seconds=stale_threshold_seconds,
        )
