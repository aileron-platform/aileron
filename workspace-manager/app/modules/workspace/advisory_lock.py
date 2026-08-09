"""PostgreSQL advisory locks shared by Workspace runtime operations."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import blake2b
from typing import Iterator
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

_LOCK_PERSON = b"aileron-ws-v1"
_BACKEND_PID_QUERY = text("SELECT pg_backend_pid()")


class WorkspaceAdvisoryLockUnavailableError(RuntimeError):
    """Another worker already owns the Workspace side-effect boundary."""

    code = "WORKSPACE_RUNTIME_LOCK_UNAVAILABLE"


class WorkspaceAdvisoryLockLostError(RuntimeError):
    """The dedicated PostgreSQL session no longer owns the lock."""

    code = "WORKSPACE_RUNTIME_CLAIM_LOST"


def workspace_advisory_key(workspace_id: str) -> int:
    """Map one canonical Workspace UUID to a stable signed bigint key."""

    canonical_id = str(UUID(workspace_id))
    if canonical_id != workspace_id:
        raise ValueError("Workspace identifier must be canonical")
    digest = blake2b(
        canonical_id.encode("ascii"),
        digest_size=8,
        person=_LOCK_PERSON,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def acquire_workspace_transaction_lock(db: Session, workspace_id: str) -> None:
    """Serialize row/revision changes for one Workspace transaction."""

    if db.get_bind().dialect.name != "postgresql":
        return
    key = workspace_advisory_key(workspace_id)
    session_lock = _CURRENT_SESSION_LOCKS.get().get(key)
    if session_lock is not None:
        # Reacquiring the same key from another PostgreSQL connection would
        # self-deadlock while this execution context owns the session lock.
        session_lock.assert_owned()
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": key},
    )


def try_acquire_workspace_transaction_lock(db: Session, workspace_id: str) -> bool:
    """Try to serialize one Workspace transaction without waiting."""

    if db.get_bind().dialect.name != "postgresql":
        return True
    key = workspace_advisory_key(workspace_id)
    session_lock = _CURRENT_SESSION_LOCKS.get().get(key)
    if session_lock is not None:
        session_lock.assert_owned()
        return True
    return (
        db.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": key},
        )
        is True
    )


@dataclass
class WorkspaceSessionAdvisoryLock:
    """Dedicated connection holding a session-level lock.

    The connection stays dedicated while external I/O is in progress.
    """

    connection: Connection | None
    lock_key: int
    backend_pid: int | None

    def assert_owned(self) -> None:
        """Fail closed if the dedicated session disappears or changes."""

        if self.connection is None:
            return
        if self.connection.closed or self.connection.invalidated:
            raise WorkspaceAdvisoryLockLostError(
                "Workspace advisory lock connection is unavailable"
            )
        try:
            current_pid = self.connection.scalar(_BACKEND_PID_QUERY)
            if current_pid != self.backend_pid:
                raise WorkspaceAdvisoryLockLostError(
                    "Workspace advisory lock session changed"
                )
            reacquired = self.connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": self.lock_key},
            )
            if reacquired is not True:
                raise WorkspaceAdvisoryLockLostError(
                    "Workspace advisory lock ownership was lost"
                )
            released_reentrant = self.connection.scalar(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": self.lock_key},
            )
            if released_reentrant is not True:
                raise WorkspaceAdvisoryLockLostError(
                    "Workspace advisory lock ownership could not be verified"
                )
        except WorkspaceAdvisoryLockLostError:
            raise
        except Exception as exc:
            raise WorkspaceAdvisoryLockLostError(
                "Workspace advisory lock ownership could not be verified"
            ) from exc


_CURRENT_SESSION_LOCKS: ContextVar[dict[int, WorkspaceSessionAdvisoryLock]] = (
    ContextVar("workspace_session_locks", default={})
)


@contextmanager
def workspace_session_advisory_lock(
    engine: Engine,
    workspace_id: str,
) -> Iterator[WorkspaceSessionAdvisoryLock]:
    """Try to own one Workspace side-effect boundary outside a transaction."""

    key = workspace_advisory_key(workspace_id)
    if engine.dialect.name != "postgresql":
        yield WorkspaceSessionAdvisoryLock(None, key, None)
        return

    connection = engine.connect()
    connection = connection.execution_options(isolation_level="AUTOCOMMIT")
    acquired = False
    backend_pid: int | None = None
    context_token = None
    try:
        backend_pid = connection.scalar(_BACKEND_PID_QUERY)
        acquired = (
            connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": key},
            )
            is True
        )
        if not acquired:
            raise WorkspaceAdvisoryLockUnavailableError(
                "Workspace advisory lock is already owned"
            )
        lock = WorkspaceSessionAdvisoryLock(connection, key, backend_pid)
        lock.assert_owned()
        current_locks = dict(_CURRENT_SESSION_LOCKS.get())
        current_locks[key] = lock
        context_token = _CURRENT_SESSION_LOCKS.set(current_locks)
        yield lock
    finally:
        if context_token is not None:
            _CURRENT_SESSION_LOCKS.reset(context_token)
        if acquired and not connection.closed and not connection.invalidated:
            try:
                if connection.scalar(_BACKEND_PID_QUERY) == backend_pid:
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_key)"),
                        {"lock_key": key},
                    )
            finally:
                connection.close()
        else:
            connection.close()


__all__ = [
    "WorkspaceAdvisoryLockLostError",
    "WorkspaceAdvisoryLockUnavailableError",
    "WorkspaceSessionAdvisoryLock",
    "acquire_workspace_transaction_lock",
    "try_acquire_workspace_transaction_lock",
    "workspace_advisory_key",
    "workspace_session_advisory_lock",
]
