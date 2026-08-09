"""Named advisory task lease unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.task_lease import task_lease, task_lease_key


def _postgres_engine(*lock_results: bool) -> tuple[MagicMock, MagicMock]:
    engine = MagicMock()
    engine.dialect.name = "postgresql"
    connection = MagicMock()
    engine.connect.return_value.execution_options.return_value = connection
    connection.closed = False
    connection.invalidated = False
    connection.scalar.side_effect = list(lock_results)
    return engine, connection


def test_task_lease_key_is_stable_and_namespaced() -> None:
    assert task_lease_key("kubernetes-workspace-status") == task_lease_key(
        "kubernetes-workspace-status"
    )
    assert task_lease_key("kubernetes-workspace-status") != task_lease_key(
        "docker-browser-connectivity"
    )


def test_task_lease_key_fits_a_signed_bigint() -> None:
    key = task_lease_key("platform-resources-hourly-aggregate")

    assert -(2**63) <= key < 2**63


def test_task_lease_is_a_noop_outside_postgresql() -> None:
    engine = MagicMock()
    engine.dialect.name = "sqlite"

    with task_lease(engine, "platform-resources-hourly-aggregate") as acquired:
        assert acquired is True

    engine.connect.assert_not_called()


def test_task_lease_skips_overlapping_execution() -> None:
    engine, connection = _postgres_engine(False)

    with task_lease(engine, "platform-resources-hourly-aggregate") as acquired:
        assert acquired is False

    assert connection.scalar.call_count == 1
    assert "pg_try_advisory_lock" in str(connection.scalar.call_args.args[0])
    connection.close.assert_called_once()


def test_task_lease_releases_on_a_dedicated_connection() -> None:
    engine, connection = _postgres_engine(True, True)

    with task_lease(engine, "docker-browser-connectivity") as acquired:
        assert acquired is True

    engine.connect.return_value.execution_options.assert_called_once_with(
        isolation_level="AUTOCOMMIT"
    )
    assert connection.scalar.call_count == 2
    assert "pg_try_advisory_lock" in str(connection.scalar.call_args_list[0].args[0])
    assert "pg_advisory_unlock" in str(connection.scalar.call_args_list[1].args[0])
    connection.close.assert_called_once()


def test_task_lease_releases_when_the_block_raises() -> None:
    engine, connection = _postgres_engine(True, True)

    try:
        with task_lease(engine, "platform-resources-daily-raw-prune") as acquired:
            assert acquired is True
            raise RuntimeError("reconcile failed")
    except RuntimeError:
        pass

    assert "pg_advisory_unlock" in str(connection.scalar.call_args_list[1].args[0])
    connection.close.assert_called_once()


def test_task_lease_closes_without_unlocking_an_invalidated_connection() -> None:
    engine, connection = _postgres_engine(True)
    connection.invalidated = True

    with task_lease(engine, "kubernetes-workspace-status") as acquired:
        assert acquired is True

    assert connection.scalar.call_count == 1
    connection.close.assert_called_once()
