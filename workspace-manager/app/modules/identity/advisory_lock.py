"""PostgreSQL transaction locks for identity mutations and reconciliation."""

from __future__ import annotations

from collections.abc import Callable
from hashlib import blake2b

from sqlalchemy import text
from sqlalchemy.orm import Session

_LOCK_PERSON = b"aileron-id-v1"


def identity_advisory_key(identity_key: str) -> int:
    """Map a non-empty identity key to a stable signed PostgreSQL bigint."""

    if not identity_key or len(identity_key) > 4096:
        raise ValueError("Identity lock key must contain between 1 and 4096 characters")
    digest = blake2b(
        identity_key.encode("utf-8"),
        digest_size=8,
        person=_LOCK_PERSON,
    ).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def acquire_identity_transaction_lock(db: Session, identity_key: str) -> None:
    """Serialize one identity using a PostgreSQL transaction-scoped lock."""

    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Identity reconciliation requires an injected test lock outside PostgreSQL"
        )
    db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": identity_advisory_key(identity_key)},
    )


IdentityTransactionLock = Callable[[Session, str], None]


def acquire_identity_lock(
    db: Session,
    identity_key: str,
    *,
    acquirer: IdentityTransactionLock | None = None,
) -> None:
    """Use an injected acquirer or the PostgreSQL lock; no-op elsewhere."""

    if acquirer is not None:
        acquirer(db, identity_key)
        return
    if db.get_bind().dialect.name != "postgresql":
        return
    acquire_identity_transaction_lock(db, identity_key)


__all__ = [
    "IdentityTransactionLock",
    "acquire_identity_lock",
    "acquire_identity_transaction_lock",
    "identity_advisory_key",
]
