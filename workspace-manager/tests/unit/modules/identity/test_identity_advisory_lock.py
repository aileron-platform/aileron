"""Identity advisory lock tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.modules.identity.advisory_lock import (
    acquire_identity_lock,
    acquire_identity_transaction_lock,
    identity_advisory_key,
)


def test_identity_advisory_key_is_stable_signed_bigint() -> None:
    first = identity_advisory_key("local-user-id")
    second = identity_advisory_key("local-user-id")

    assert first == second
    assert -(2**63) <= first < 2**63
    assert first != identity_advisory_key("other-user-id")


def test_identity_transaction_lock_uses_postgresql_xact_lock() -> None:
    db = Mock()
    db.get_bind.return_value.dialect.name = "postgresql"

    acquire_identity_transaction_lock(db, "local-user-id")

    statement, parameters = db.execute.call_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(:lock_key)"
    assert parameters == {"lock_key": identity_advisory_key("local-user-id")}


def test_identity_transaction_lock_requires_injected_fake_outside_postgresql() -> None:
    db = Mock()
    db.get_bind.return_value.dialect.name = "sqlite"

    with pytest.raises(RuntimeError, match="injected test lock"):
        acquire_identity_transaction_lock(db, "local-user-id")


def test_identity_lock_uses_injected_acquirer_before_dialect_detection() -> None:
    db = Mock()
    acquirer = Mock()

    acquire_identity_lock(db, "local-user-id", acquirer=acquirer)

    acquirer.assert_called_once_with(db, "local-user-id")
    db.get_bind.assert_not_called()


def test_identity_lock_is_noop_outside_postgresql() -> None:
    db = Mock()
    db.get_bind.return_value.dialect.name = "sqlite"

    acquire_identity_lock(db, "local-user-id")

    db.execute.assert_not_called()


def test_identity_lock_uses_production_postgresql_lock() -> None:
    db = Mock()
    db.get_bind.return_value.dialect.name = "postgresql"

    acquire_identity_lock(db, "local-user-id")

    statement, parameters = db.execute.call_args.args
    assert str(statement) == "SELECT pg_advisory_xact_lock(:lock_key)"
    assert parameters == {"lock_key": identity_advisory_key("local-user-id")}


def test_identity_lock_propagates_injected_acquirer_errors() -> None:
    db = Mock()
    expected_error = RuntimeError("lock failed")
    acquirer = Mock(side_effect=expected_error)

    with pytest.raises(RuntimeError) as exc_info:
        acquire_identity_lock(db, "local-user-id", acquirer=acquirer)

    assert exc_info.value is expected_error
