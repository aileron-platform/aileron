"""Real PostgreSQL Workspace advisory lock integration tests."""

from __future__ import annotations

import os
from threading import Event, Thread

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.modules.workspace.advisory_lock import (
    WorkspaceAdvisoryLockUnavailableError,
    acquire_workspace_transaction_lock,
    workspace_session_advisory_lock,
)


@pytest.fixture
def postgres_engine():
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("PostgreSQL integration database is not configured")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_session_lock_has_one_owner_and_releases_cleanly(
    postgres_engine,
) -> None:
    workspace_id = "8772513f-1f6b-4e36-9663-6d74691fe34c"

    with workspace_session_advisory_lock(
        postgres_engine,
        workspace_id,
    ) as lock:
        lock.assert_owned()
        with pytest.raises(WorkspaceAdvisoryLockUnavailableError):
            with workspace_session_advisory_lock(
                postgres_engine,
                workspace_id,
            ):
                pass

    with workspace_session_advisory_lock(
        postgres_engine,
        workspace_id,
    ) as lock:
        lock.assert_owned()


def test_transaction_lock_waits_for_external_side_effect_owner(
    postgres_engine,
) -> None:
    workspace_id = "928f5090-d62f-481c-909c-6e245f72a85d"
    started = Event()
    acquired = Event()

    def acquire_in_transaction() -> None:
        with Session(postgres_engine) as db:
            started.set()
            acquire_workspace_transaction_lock(db, workspace_id)
            acquired.set()
            db.rollback()

    with workspace_session_advisory_lock(postgres_engine, workspace_id):
        worker = Thread(target=acquire_in_transaction, daemon=True)
        worker.start()
        assert started.wait(timeout=2)
        assert not acquired.wait(timeout=0.2)

    worker.join(timeout=2)
    assert not worker.is_alive()
    assert acquired.is_set()


def test_transaction_lock_reuses_current_session_owner(
    postgres_engine,
) -> None:
    workspace_id = "ac46ac0e-278f-4111-9b34-cf2d7d7b6b3d"

    with workspace_session_advisory_lock(postgres_engine, workspace_id):
        with Session(postgres_engine) as db:
            acquire_workspace_transaction_lock(db, workspace_id)
            db.rollback()

    with Session(postgres_engine) as db:
        acquire_workspace_transaction_lock(db, workspace_id)
        db.rollback()
