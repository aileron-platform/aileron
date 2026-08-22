"""Real PostgreSQL concurrency tests for Runtime capability snapshots."""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.modules.workspace.router as workspace_router
from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
    workspace_advisory_key,
    workspace_session_advisory_lock,
)
from app.modules.workspace.capabilities import ToolCapability, WorkspaceCapabilities
from app.modules.workspace.catalog import WorkspaceService
from app.modules.workspace.models import WorkspaceUpdateRequest
from app.modules.workspace.runtime.sync import (
    RuntimeCapabilitiesSyncError,
    RuntimeSyncService,
)

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


def _docker_capability_snapshot() -> WorkspaceCapabilities:
    return WorkspaceCapabilities(
        default_tool="claude",
        tools=[
            ToolCapability(
                id="claude",
                models=["claude-model"],
                default_model="claude-model",
                modes=["execute", "plan"],
                default_mode="execute",
                context_window=200_000,
            ),
            ToolCapability(
                id="codex",
                models=["codex-model"],
                default_model="codex-model",
                context_window=200_000,
            ),
        ],
    )


def _seed_running_docker_workspace(engine: Engine) -> WorkspaceCapabilities:
    _seed_workspace(engine)
    snapshot = _docker_capability_snapshot()
    with Session(engine) as db:
        workspace = db.get(db_models.Workspace, _WORKSPACE_ID)
        assert workspace is not None
        workspace.provisioner = "docker"
        workspace.runtime_status = "running"
        workspace.runtime_internal_url = "http://runtime-current:3002"
        workspace.runtime_instance_id = "11111111-1111-4111-8111-111111111111"
        workspace.agentic_tools = ["claude-code"]
        workspace.agentic_capabilities = snapshot.model_dump(by_alias=True)
        db.commit()
    return snapshot


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


@pytest.mark.parametrize(
    "lock_order",
    ["delivery_then_update", "update_then_delivery"],
)
def test_docker_delivery_converges_for_both_workspace_lock_orders(
    runtime_capabilities_database: Engine,
    monkeypatch: pytest.MonkeyPatch,
    lock_order: str,
) -> None:
    snapshot = _seed_running_docker_workspace(runtime_capabilities_database)
    session_factory = sessionmaker(
        bind=runtime_capabilities_database,
        expire_on_commit=False,
    )
    monkeypatch.setattr(workspace_router, "SessionLocal", session_factory)

    real_acquire = acquire_workspace_transaction_lock
    background_lock_attempted = Event()
    background_backend_pids: list[int] = []

    def record_background_lock(db: Session, workspace_id: str) -> None:
        background_backend_pids.append(
            db.execute(text("SELECT pg_backend_pid()")).scalar_one()
        )
        background_lock_attempted.set()
        real_acquire(db, workspace_id)

    monkeypatch.setattr(
        workspace_router,
        "acquire_workspace_transaction_lock",
        record_background_lock,
    )

    delivered_tool_ids: list[list[str]] = []
    delivered_lock = Lock()
    first_delivery_entered = Event()
    release_first_delivery = Event()

    async def deliver_capabilities(
        _service,
        workspace_id: str,
        runtime_url: str,
        capabilities: WorkspaceCapabilities,
    ) -> dict[str, object]:
        assert workspace_id == _WORKSPACE_ID
        assert runtime_url == "http://runtime-current:3002"
        tool_ids = [tool.id for tool in capabilities.tools]
        with delivered_lock:
            delivered_tool_ids.append(tool_ids)
            delivery_number = len(delivered_tool_ids)
        if lock_order == "delivery_then_update" and delivery_number == 1:
            first_delivery_entered.set()
            assert release_first_delivery.wait(timeout=5)
        return {"success": True}

    monkeypatch.setattr(
        RuntimeSyncService,
        "sync_capabilities_to_runtime_url",
        deliver_capabilities,
    )

    update_started = Event()
    update_has_lock = Event()
    release_update = Event()
    update_backend_pids: list[int] = []

    def update_to_codex(*, acquire_first: bool) -> None:
        with Session(runtime_capabilities_database) as db:
            update_backend_pids.append(
                db.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            if acquire_first:
                real_acquire(db, _WORKSPACE_ID)
                update_has_lock.set()
                assert release_update.wait(timeout=5)
            else:
                update_started.set()
            updated = WorkspaceService(db).update(
                _WORKSPACE_ID,
                WorkspaceUpdateRequest(agenticTools=["codex"]),
                actor=AuthorizationActor(_OWNER_ID, "member"),
            )
            assert updated is not None

    def run_delivery() -> None:
        asyncio.run(
            workspace_router._sync_capabilities_to_runtime(
                _WORKSPACE_ID,
                "http://scheduled-stale:3002",
            )
        )

    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            if lock_order == "delivery_then_update":
                stale_delivery = executor.submit(run_delivery)
                assert first_delivery_entered.wait(timeout=5)
                update = executor.submit(update_to_codex, acquire_first=False)
                assert update_started.wait(timeout=2)
                assert len(update_backend_pids) == 1
                assert _wait_for_advisory_lock_wait(
                    runtime_capabilities_database,
                    backend_pid=update_backend_pids[0],
                ) == workspace_advisory_key(_WORKSPACE_ID)
                release_first_delivery.set()
            else:
                update = executor.submit(update_to_codex, acquire_first=True)
                assert update_has_lock.wait(timeout=5)
                stale_delivery = executor.submit(run_delivery)
                assert background_lock_attempted.wait(timeout=2)
                assert len(background_backend_pids) == 1
                assert _wait_for_advisory_lock_wait(
                    runtime_capabilities_database,
                    backend_pid=background_backend_pids[0],
                ) == workspace_advisory_key(_WORKSPACE_ID)
                release_update.set()

            stale_delivery.result(timeout=5)
            update.result(timeout=5)
            executor.submit(run_delivery).result(timeout=5)
    finally:
        release_first_delivery.set()
        release_update.set()

    expected_deliveries = (
        [["claude"], ["codex"]]
        if lock_order == "delivery_then_update"
        else [["codex"], ["codex"]]
    )
    assert delivered_tool_ids == expected_deliveries
    with Session(runtime_capabilities_database) as db:
        workspace = db.get(db_models.Workspace, _WORKSPACE_ID)
        assert workspace is not None
        assert workspace.agentic_tools == ["codex"]
        assert workspace.agentic_capabilities == snapshot.model_dump(by_alias=True)


def test_failed_docker_delivery_releases_lock_and_preserves_selection(
    runtime_capabilities_database: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    snapshot = _seed_running_docker_workspace(runtime_capabilities_database)
    with Session(runtime_capabilities_database) as db:
        updated = WorkspaceService(db).update(
            _WORKSPACE_ID,
            WorkspaceUpdateRequest(agenticTools=["codex"]),
            actor=AuthorizationActor(_OWNER_ID, "member"),
        )
        assert updated is not None

    session_factory = sessionmaker(
        bind=runtime_capabilities_database,
        expire_on_commit=False,
    )
    monkeypatch.setattr(workspace_router, "SessionLocal", session_factory)
    delivery_attempts: list[list[str]] = []

    async def fail_once(
        _service,
        _workspace_id: str,
        _runtime_url: str,
        capabilities: WorkspaceCapabilities,
    ) -> dict[str, object]:
        delivery_attempts.append([tool.id for tool in capabilities.tools])
        if len(delivery_attempts) == 1:
            raise RuntimeCapabilitiesSyncError("delivery failed")
        return {"success": True}

    monkeypatch.setattr(
        RuntimeSyncService,
        "sync_capabilities_to_runtime_url",
        fail_once,
    )

    asyncio.run(
        workspace_router._sync_capabilities_to_runtime(
            _WORKSPACE_ID,
            "http://scheduled-stale:3002",
        )
    )
    asyncio.run(
        workspace_router._sync_capabilities_to_runtime(
            _WORKSPACE_ID,
            "http://scheduled-stale:3002",
        )
    )

    assert delivery_attempts == [["codex"], ["codex"]]
    with Session(runtime_capabilities_database) as db:
        workspace = db.get(db_models.Workspace, _WORKSPACE_ID)
        assert workspace is not None
        assert workspace.agentic_tools == ["codex"]
        assert workspace.agentic_capabilities == snapshot.model_dump(by_alias=True)
