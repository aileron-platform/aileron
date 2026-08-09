from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import ContextManager, Iterator, Protocol, Sequence

from .models import FileLocator


class FileMutationHooks(Protocol):
    def write_barrier(self, locator: FileLocator, operation: str) -> ContextManager[None]:
        """Wrap quota, snapshot, filesystem mutation, size update, validation."""

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        """Raise when the mutation would exceed quota."""

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        """Snapshot existing file content before destructive mutation."""

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        """Persist size delta after successful filesystem mutation."""

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        """Run domain validation after filesystem mutation but before invalidation."""

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        """Invalidate domain caches after the barrier exits successfully."""


class NoopMutationHooks:
    @contextmanager
    def write_barrier(self, locator: FileLocator, operation: str) -> Iterator[None]:
        _ = (locator, operation)
        yield

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        _ = (locator, absolute_path, relative_path, operation)

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = (locator, operation, paths)

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = (locator, operation, paths)


class NoopQuotaHook(NoopMutationHooks):
    pass


class NoopValidationHook(NoopMutationHooks):
    pass
