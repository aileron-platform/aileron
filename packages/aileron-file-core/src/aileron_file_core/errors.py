from __future__ import annotations

from typing import Any, Mapping, Optional


class FileCoreError(Exception):
    """Base error for shared file safety primitives."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Mapping[str, Any]] = None,
        status_hint: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})
        self.status_hint = status_hint


class PathOutsideRootError(FileCoreError):
    """Raised when a requested path escapes the configured root."""

    def __init__(self, path: str) -> None:
        super().__init__(
            code="PATH_OUTSIDE_ROOT",
            message=f"Path escapes root: {path}",
            details={"path": path},
            status_hint=400,
        )
        self.path = path


class VersionConflictError(FileCoreError):
    """Raised when expected and actual version tokens differ."""

    def __init__(self, path: str, expected_version: str, actual_version: str) -> None:
        super().__init__(
            code="CONTENT_CONFLICT",
            message=(
                f"Content conflict for {path}: "
                f"expected {expected_version}, got {actual_version}"
            ),
            details={
                "path": path,
                "expectedVersion": expected_version,
                "actualVersion": actual_version,
            },
            status_hint=409,
        )
        self.path = path
        self.expected_version = expected_version
        self.actual_version = actual_version
