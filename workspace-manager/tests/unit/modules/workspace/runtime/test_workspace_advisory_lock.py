"""Workspace advisory lock key and SQLite fake tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
    try_acquire_workspace_transaction_lock,
    workspace_advisory_key,
)


def test_workspace_advisory_key_is_stable_signed_bigint() -> None:
    workspace_id = "c33eae8f-e2dd-403e-aa67-cd606227efdc"

    first = workspace_advisory_key(workspace_id)
    second = workspace_advisory_key(workspace_id)

    assert first == second
    assert -(1 << 63) <= first < (1 << 63)


@pytest.mark.parametrize(
    "workspace_id",
    [
        "C33EAE8F-E2DD-403E-AA67-CD606227EFDC",
        "workspace-1",
        " c33eae8f-e2dd-403e-aa67-cd606227efdc",
    ],
)
def test_workspace_advisory_key_rejects_noncanonical_identifiers(
    workspace_id: str,
) -> None:
    with pytest.raises(ValueError):
        workspace_advisory_key(workspace_id)


def test_sqlite_transaction_lock_is_a_deterministic_noop() -> None:
    db = MagicMock(spec=Session)
    db.get_bind.return_value.dialect.name = "sqlite"

    acquire_workspace_transaction_lock(db, "workspace-fixture")

    db.execute.assert_not_called()


def test_postgresql_transaction_lock_try_does_not_wait() -> None:
    db = MagicMock(spec=Session)
    db.get_bind.return_value.dialect.name = "postgresql"
    db.scalar.return_value = False
    workspace_id = "c33eae8f-e2dd-403e-aa67-cd606227efdc"

    acquired = try_acquire_workspace_transaction_lock(db, workspace_id)

    assert acquired is False
    statement = str(db.scalar.call_args.args[0])
    assert "pg_try_advisory_xact_lock" in statement
    db.execute.assert_not_called()
