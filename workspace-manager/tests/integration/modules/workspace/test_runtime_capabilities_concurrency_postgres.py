"""Real PostgreSQL concurrency tests for Runtime capability snapshots."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.workspace.capabilities import ToolCapability, WorkspaceCapabilities
from app.modules.workspace.runtime.sync import RuntimeSyncService
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
    workspace_advisory_key,
    workspace_session_advisory_lock,
)
from app.modules.workspace.catalog import WorkspaceService

_OWNER_ID = "runtime-capabilities-concurrency-owner"
_WORKSPACE_ID = "bc49af9d-5982-4fa6-a152-ae2f54e426f6"


@pytest.fixture()
def runtime_capabilities_database() -> Engine:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")

    schema = f"runtime_capabilities_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    engine: Engine | None = None
    schema_created = False
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        schema_created = True
        engine = create_engine(
            database_url,
            connect_args={"options": f"-csearch_path={schema}"},
            pool_pre_ping=True,
        )
        Base.metadata.create_all(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        try:
            if schema_created:
                with admin_engine.begin() as connection:
                    connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        finally:
            admin_engine.dispose()


def _capabilities(model: str) -> WorkspaceCapabilities:
    return WorkspaceCapabilities(
        default_tool="claude",
        tools=[
            ToolCapability(
                id="claude",
                models=[model],
                default_model=model,
                modes=["execute", "plan"],
                default_mode="execute",
                context_window=200_000,
            )
        ],
    )


def _seed_workspace(engine: Engine) -> None:
    with Session(engine) as db:
        db.add(
            db_models.User(
                id=_OWNER_ID,
                username=_OWNER_ID,
                email=f"{_OWNER_ID}@example.com",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        db.add(
            db_models.Workspace(
                id=_WORKSPACE_ID,
                owner_id=_OWNER_ID,
                name="Original workspace name",
                description="original description",
                provisioner="kubernetes",
                runtime_status="starting",
            )
        )
        db.commit()


def _wait_for_advisory_lock_wait(
    engine: Engine,
    *,
    backend_pid: int,
    timeout: float = 5.0,
) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting_lock = connection.execute(
                text(
                    "SELECT activity.wait_event_type, activity.wait_event, "
                    "locks.classid, locks.objid "
                    "FROM pg_stat_activity AS activity "
                    "JOIN pg_locks AS locks ON locks.pid = activity.pid "
                    "WHERE activity.pid = :backend_pid "
                    "AND locks.locktype = 'advisory' "
                    "AND locks.granted = false"
                ),
                {"backend_pid": backend_pid},
            ).one_or_none()
        if (
            waiting_lock is not None
            and waiting_lock.wait_event_type == "Lock"
            and waiting_lock.wait_event == "advisory"
        ):
            unsigned_lock_key = (waiting_lock.classid << 32) | waiting_lock.objid
            if unsigned_lock_key >= 1 << 63:
                return unsigned_lock_key - (1 << 64)
            return unsigned_lock_key
        time.sleep(0.01)
    pytest.fail("Capability writer did not wait for the Workspace advisory lock")


@pytest.mark.parametrize("writer", ["runtime_sync", "workspace_service"])
def test_capability_writers_follow_external_lifecycle_lock_order_without_lost_update(
    runtime_capabilities_database: Engine,
    writer: str,
) -> None:
    _seed_workspace(runtime_capabilities_database)
    capabilities_a = _capabilities("model-a")
    capabilities_b = _capabilities("model-b")
    writer_b_started = Event()
    writer_b_backend_pid: list[int] = []

    def write_capabilities_b() -> None:
        with Session(runtime_capabilities_database) as db:
            writer_b_backend_pid.append(
                db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            writer_b_started.set()
            if writer == "runtime_sync":
                RuntimeSyncService(db)._store_workspace_capabilities(
                    _WORKSPACE_ID,
                    capabilities_b,
                )
            else:
                WorkspaceService(db).update_capabilities(
                    _WORKSPACE_ID,
                    capabilities_b,
                    actor=AuthorizationActor(_OWNER_ID, "member"),
                )

    with ThreadPoolExecutor(max_workers=1) as executor:
        with workspace_session_advisory_lock(
            runtime_capabilities_database,
            _WORKSPACE_ID,
        ) as lifecycle_lock:
            with Session(runtime_capabilities_database) as lifecycle_db:
                lifecycle_backend_pid = lifecycle_db.execute(
                    text("SELECT pg_backend_pid()")
                ).scalar_one()
                acquire_workspace_transaction_lock(lifecycle_db, _WORKSPACE_ID)
                workspace = lifecycle_db.get(db_models.Workspace, _WORKSPACE_ID)
                assert workspace is not None
                workspace.name = "Lifecycle committed name"
                workspace.description = "lifecycle side effect"
                workspace.agentic_capabilities = capabilities_a.model_dump(
                    by_alias=True
                )
                lifecycle_db.flush()

                writer_b_future = executor.submit(write_capabilities_b)
                assert writer_b_started.wait(timeout=2)
                assert len(writer_b_backend_pid) == 1
                assert (
                    len(
                        {
                            lifecycle_lock.backend_pid,
                            lifecycle_backend_pid,
                            writer_b_backend_pid[0],
                        }
                    )
                    == 3
                )
                waiting_lock_key = _wait_for_advisory_lock_wait(
                    runtime_capabilities_database,
                    backend_pid=writer_b_backend_pid[0],
                )
                expected_lock_key = workspace_advisory_key(_WORKSPACE_ID)
                assert lifecycle_lock.lock_key == expected_lock_key
                assert waiting_lock_key == expected_lock_key
                assert not writer_b_future.done()

                lifecycle_db.commit()
                with Session(runtime_capabilities_database) as observer_db:
                    observed = observer_db.get(db_models.Workspace, _WORKSPACE_ID)
                    assert observed is not None
                    assert observed.name == "Lifecycle committed name"
                    assert observed.description == "lifecycle side effect"
                    assert observed.agentic_capabilities == capabilities_a.model_dump(
                        by_alias=True
                    )
                assert not writer_b_future.done()

        writer_b_future.result(timeout=5)

    with Session(runtime_capabilities_database) as db:
        workspace = db.get(db_models.Workspace, _WORKSPACE_ID)
        assert workspace is not None
        assert workspace.agentic_capabilities == capabilities_b.model_dump(
            by_alias=True
        )
        assert workspace.name == "Lifecycle committed name"
        assert workspace.description == "lifecycle side effect"
