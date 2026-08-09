"""Thread-safe lifecycle state for background file operations."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Callable, Dict, Generic, Mapping, Optional, TypeVar
from uuid import uuid4

T = TypeVar("T")


@dataclass
class BackgroundFileOperation(Generic[T]):
    operation_id: str
    scope_key: str
    status: str
    progress: float
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[T] = None
    artifact_path: Optional[Path] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, object] = field(default_factory=dict)


class BackgroundFileOperationStore(Generic[T]):
    """Own creation, mutation, lookup, expiry, and artifact cleanup."""

    def __init__(
        self,
        *,
        operation_prefix: str,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._operation_prefix = operation_prefix
        self._now = now
        self._lock = RLock()
        self._operations: Dict[tuple[str, str], BackgroundFileOperation[T]] = {}

    def create(
        self,
        *,
        scope_key: str,
        message: str,
        metadata: Optional[Mapping[str, object]] = None,
    ) -> BackgroundFileOperation[T]:
        self.cleanup_expired()
        operation_id = f"{self._operation_prefix}-{uuid4().hex[:12]}"
        operation = BackgroundFileOperation[T](
            operation_id=operation_id,
            scope_key=scope_key,
            status="pending",
            progress=0.0,
            message=message,
            started_at=self._now(),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            self._operations[(scope_key, operation_id)] = operation
        return operation

    def get(
        self, *, scope_key: str, operation_id: str
    ) -> Optional[BackgroundFileOperation[T]]:
        self.cleanup_expired()
        with self._lock:
            return self._operations.get((scope_key, operation_id))

    def update(
        self,
        *,
        scope_key: str,
        operation_id: str,
        status: Optional[str] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        error: Optional[str] = None,
        result: Optional[T] = None,
        artifact_path: Optional[Path] = None,
        expires_at: Optional[datetime] = None,
    ) -> Optional[BackgroundFileOperation[T]]:
        with self._lock:
            operation = self._operations.get((scope_key, operation_id))
            if operation is None:
                return None
            if status is not None:
                operation.status = status
            if progress is not None:
                operation.progress = min(1.0, max(0.0, progress))
            if message is not None:
                operation.message = message
            if error is not None:
                operation.error = error
            if result is not None:
                operation.result = result
            if artifact_path is not None:
                operation.artifact_path = artifact_path
            if expires_at is not None:
                operation.expires_at = expires_at
            if status in {"completed", "failed", "expired"}:
                operation.completed_at = self._now()
            return operation

    def cleanup_expired(self) -> None:
        now = self._now()
        with self._lock:
            expired_keys = [
                key
                for key, operation in self._operations.items()
                if operation.expires_at is not None and operation.expires_at <= now
            ]
            for key in expired_keys:
                operation = self._operations.pop(key)
                artifact_path = operation.artifact_path
                if artifact_path is None or not artifact_path.exists():
                    continue
                try:
                    artifact_path.unlink()
                except OSError:
                    pass
