from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol

from .errors import PathOutsideRootError
from .models import FileLocator
from .path_guard import SafePath, resolve_safe_path
from .policies import PathExclusionPolicy
from .write_lock import ResourceWriteLockKey


class RootResolver(Protocol):
    def root_for(self, locator: FileLocator) -> Path:
        """Return the filesystem root for the locator."""


@dataclass(frozen=True)
class StaticRootResolver:
    root: Path

    def root_for(self, locator: FileLocator) -> Path:
        _ = locator
        return Path(self.root)


@dataclass(frozen=True)
class DynamicRootResolver:
    resolve: Callable[[FileLocator], Path]

    def root_for(self, locator: FileLocator) -> Path:
        return Path(self.resolve(locator))


@dataclass(frozen=True)
class ScopedRootResolver:
    roots: Mapping[str, Path]
    default_scope: str

    def root_for(self, locator: FileLocator) -> Path:
        scope = locator.scope or self.default_scope
        try:
            return Path(self.roots[scope])
        except KeyError as exc:
            raise PathOutsideRootError(scope) from exc


class FileOperationAdapter(Protocol):
    def root_for(self, locator: FileLocator) -> Path:
        """Return root for the locator."""

    def resolve_path(self, locator: FileLocator, relative_path: str) -> SafePath:
        """Resolve a relative path safely."""

    def lock_key_for(
        self,
        locator: FileLocator,
        relative_path: str,
        operation: str,
    ) -> ResourceWriteLockKey:
        """Return the resource write lock key for a mutation."""

    def can_read(self, locator: FileLocator, relative_path: str) -> None:
        """Raise when read is not allowed."""

    def can_write(self, locator: FileLocator, relative_path: str, operation: str) -> None:
        """Raise when write is not allowed."""

    def canonical_path(self, locator: FileLocator, absolute_path: Path) -> str:
        """Return canonical path inside root."""


@dataclass
class RootedFileAdapter:
    root_resolver: RootResolver
    path_exclusion: Optional[PathExclusionPolicy] = None

    def root_for(self, locator: FileLocator) -> Path:
        return self.root_resolver.root_for(locator)

    def resolve_path(self, locator: FileLocator, relative_path: str) -> SafePath:
        safe_path = resolve_safe_path(
            self.root_for(locator),
            _normalize_adapter_path(relative_path),
        )
        relative = Path(safe_path.relative_path)
        if self.path_exclusion and self.path_exclusion.is_excluded(relative):
            raise PathOutsideRootError(safe_path.relative_path)
        return safe_path

    def lock_key_for(
        self,
        locator: FileLocator,
        relative_path: str,
        operation: str,
    ) -> ResourceWriteLockKey:
        _ = operation
        safe_path = self.resolve_path(locator, relative_path)
        return (
            locator.domain,
            locator.resource_id,
            locator.scope or "",
            safe_path.relative_path,
        )

    def can_read(self, locator: FileLocator, relative_path: str) -> None:
        self.resolve_path(locator, relative_path)

    def can_write(self, locator: FileLocator, relative_path: str, operation: str) -> None:
        _ = operation
        self.resolve_path(locator, relative_path)

    def canonical_path(self, locator: FileLocator, absolute_path: Path) -> str:
        root = self.root_for(locator).resolve()
        try:
            return Path(absolute_path).resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise PathOutsideRootError(str(absolute_path)) from exc


def _normalize_adapter_path(relative_path: str) -> str:
    return relative_path.lstrip("/") or "."
