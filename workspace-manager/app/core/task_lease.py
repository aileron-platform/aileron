"""Named PostgreSQL advisory leases for periodic platform tasks."""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import blake2b
from typing import Iterator

from sqlalchemy import text
from sqlalchemy.engine import Engine

_LEASE_PERSON = b"aileron-task-v1"


def task_lease_key(lease_name: str) -> int:
    """Map one lease name to a stable signed bigint advisory-lock key.

    The dedicated personalization keeps task leases in a key space separate
    from per-Workspace advisory locks.
    """

    digest = blake2b(
        lease_name.encode("utf-8"),
        digest_size=8,
        person=_LEASE_PERSON,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


@contextmanager
def task_lease(engine: Engine, lease_name: str) -> Iterator[bool]:
    """Own one named lease for the duration of the block.

    The lock lives on a dedicated AUTOCOMMIT connection so it survives commits
    and rollbacks on the caller's session and is never leaked back to the pool.
    Yields False when another worker already owns the lease.
    """

    if engine.dialect.name != "postgresql":
        yield True
        return

    lock_key = task_lease_key(lease_name)
    connection = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    acquired = False
    try:
        acquired = (
            connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            )
            is True
        )
        yield acquired
    finally:
        if acquired and not connection.closed and not connection.invalidated:
            try:
                connection.scalar(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                )
            finally:
                connection.close()
        else:
            connection.close()


__all__ = ["task_lease", "task_lease_key"]
