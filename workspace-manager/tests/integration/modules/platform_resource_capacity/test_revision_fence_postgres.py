"""Real PostgreSQL transaction tests for capacity revision fencing."""

from __future__ import annotations

import os
from threading import Event, Thread
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.platform_resource_capacity.lifecycle import (
    PlatformResourceCapacityAdministration,
)
from app.modules.platform_resource_capacity.models import (
    StorageObservation,
    WorkspaceStorageDesiredState,
    WorkspaceStorageObservation,
)

_OWNER_ID = "capacity-revision-fence-owner"
_ADMIN_ID = "capacity-revision-fence-admin"
_WORKSPACE_ID = "f97fa40e-cf2a-4c48-9392-c20e069ae973"


@pytest.fixture()
def capacity_database() -> Engine:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")
    schema = f"capacity_revision_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    engine: Engine | None = None
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
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
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed(engine: Engine) -> None:
    with Session(engine) as db:
        for user_id, role in ((_OWNER_ID, "member"), (_ADMIN_ID, "admin")):
            db.add(
                db_models.User(
                    id=user_id,
                    username=user_id,
                    email=f"{user_id}@example.com",
                    is_active=True,
                    identity_enabled=True,
                    sync_status="synced",
                    platform_role=role,
                    role_status="valid",
                )
            )
        db.add(
            db_models.Workspace(
                id=_WORKSPACE_ID,
                owner_id=_OWNER_ID,
                name="Capacity revision fence",
                provisioner="kubernetes",
                runtime_status="running",
            )
        )
        db.flush()
        db.add(
            db_models.WorkspaceStorageAllocation(
                workspace_id=_WORKSPACE_ID,
                storage_kind="workspace_data",
                desired_bytes=1024**3,
                observed_bytes=1024**3,
                revision=1,
                observed_revision=1,
                phase="completed",
            )
        )
        db.commit()


def test_request_and_late_status_share_lock_and_fence_revision(
    capacity_database: Engine,
) -> None:
    _seed(capacity_database)
    request_before_commit = Event()
    release_request = Event()
    status_started = Event()
    status_finished = Event()
    status_changed: list[bool] = []

    def request_revision_two() -> None:
        with Session(capacity_database) as db:

            def hold_before_commit(_session: Session) -> None:
                request_before_commit.set()
                assert release_request.wait(timeout=5)

            event.listen(db, "before_commit", hold_before_commit)
            PlatformResourceCapacityAdministration(db).request_workspace_expansion(
                actor=AuthorizationActor(user_id=_ADMIN_ID, platform_role="admin"),
                workspace_id=_WORKSPACE_ID,
                storage_kind="workspace_data",
                requested_bytes=2 * 1024**3,
            )

    def reconcile_late_revision_one() -> None:
        with Session(capacity_database) as db:
            status_started.set()
            changed = PlatformResourceCapacityAdministration(
                db
            ).reconcile_operator_observation(
                workspace_id=_WORKSPACE_ID,
                observation=WorkspaceStorageObservation(
                    items=(
                        StorageObservation(
                            storage_kind="workspace_data",
                            allocated_bytes=2 * 1024**3,
                            observed_revision=1,
                            expansion_supported=True,
                            error_code=None,
                            observed_at=None,
                        ),
                    )
                ),
            )
            db.commit()
            status_changed.append(changed)
            status_finished.set()

    request_thread = Thread(target=request_revision_two, daemon=True)
    request_thread.start()
    assert request_before_commit.wait(timeout=5)

    status_thread = Thread(target=reconcile_late_revision_one, daemon=True)
    status_thread.start()
    assert status_started.wait(timeout=2)
    assert not status_finished.wait(timeout=0.2)

    release_request.set()
    request_thread.join(timeout=5)
    status_thread.join(timeout=5)
    assert not request_thread.is_alive()
    assert not status_thread.is_alive()
    assert status_changed == [False]

    with Session(capacity_database) as db:
        allocation = db.scalar(
            select(db_models.WorkspaceStorageAllocation).where(
                db_models.WorkspaceStorageAllocation.workspace_id == _WORKSPACE_ID,
                db_models.WorkspaceStorageAllocation.storage_kind == "workspace_data",
            )
        )
        assert allocation is not None
        assert allocation.revision == 2
        assert allocation.observed_revision == 1
        assert allocation.phase == "pending"


def test_delivery_and_observation_share_lock_and_keep_terminal_phase(
    capacity_database: Engine,
) -> None:
    _seed(capacity_database)
    with Session(capacity_database) as db:
        allocation = db.scalar(
            select(db_models.WorkspaceStorageAllocation).where(
                db_models.WorkspaceStorageAllocation.workspace_id == _WORKSPACE_ID,
                db_models.WorkspaceStorageAllocation.storage_kind == "workspace_data",
            )
        )
        assert allocation is not None
        allocation.desired_bytes = 2 * 1024**3
        allocation.revision = 2
        allocation.phase = "applying"
        db.add(
            db_models.WorkspaceCapacityExpansionRequest(
                id="delivery-observation-request",
                workspace_id=_WORKSPACE_ID,
                storage_kind="workspace_data",
                previous_bytes=1024**3,
                requested_bytes=2 * 1024**3,
                target_revision=2,
                requested_by_user_id=_ADMIN_ID,
                phase="applying",
            )
        )
        db.commit()

    delivery_started = Event()
    release_delivery = Event()
    observation_started = Event()
    observation_finished = Event()

    def deliver_current_revision() -> None:
        with Session(capacity_database) as db:

            def deliver(
                _workspace: db_models.Workspace,
                _desired: WorkspaceStorageDesiredState,
            ) -> None:
                delivery_started.set()
                assert release_delivery.wait(timeout=5)

            PlatformResourceCapacityAdministration(db).deliver_reconciling(deliver)

    def complete_current_revision() -> None:
        with Session(capacity_database) as db:
            observation_started.set()
            changed = PlatformResourceCapacityAdministration(
                db
            ).reconcile_operator_observation(
                workspace_id=_WORKSPACE_ID,
                observation=WorkspaceStorageObservation(
                    items=(
                        StorageObservation(
                            storage_kind="workspace_data",
                            allocated_bytes=2 * 1024**3,
                            observed_revision=2,
                            expansion_supported=True,
                            error_code=None,
                            observed_at=None,
                        ),
                    )
                ),
            )
            db.commit()
            assert changed is True
            observation_finished.set()

    delivery_thread = Thread(target=deliver_current_revision, daemon=True)
    delivery_thread.start()
    assert delivery_started.wait(timeout=5)

    observation_thread = Thread(target=complete_current_revision, daemon=True)
    observation_thread.start()
    assert observation_started.wait(timeout=2)
    assert not observation_finished.wait(timeout=0.2)

    release_delivery.set()
    delivery_thread.join(timeout=5)
    observation_thread.join(timeout=5)
    assert not delivery_thread.is_alive()
    assert not observation_thread.is_alive()

    with Session(capacity_database) as db:
        allocation = db.scalar(
            select(db_models.WorkspaceStorageAllocation).where(
                db_models.WorkspaceStorageAllocation.workspace_id == _WORKSPACE_ID,
                db_models.WorkspaceStorageAllocation.storage_kind == "workspace_data",
            )
        )
        request = db.get(
            db_models.WorkspaceCapacityExpansionRequest,
            "delivery-observation-request",
        )
        assert allocation is not None
        assert request is not None
        assert allocation.phase == "completed"
        assert request.phase == "completed"
