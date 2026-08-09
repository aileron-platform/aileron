"""Real PostgreSQL concurrency tests for firewall desired-state delivery."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
from typing import Iterator
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.advisory_lock import workspace_session_advisory_lock
from app.modules.workspace.firewall_delivery import (
    WorkspaceFirewallDeliveryService,
)


@pytest.fixture()
def firewall_delivery_database() -> Iterator[Engine]:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")

    schema = f"workspace_firewall_delivery_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_current_delivery(
    engine: Engine,
    *,
    revision: int = 2,
    observed_revision: int = 1,
) -> tuple[str, str, datetime]:
    owner_id = f"firewall-delivery-owner-{uuid4()}"
    workspace_id = str(uuid4())
    command_id = str(uuid4())
    scheduled_at = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(
            db_models.User(
                id=owner_id,
                username=owner_id,
                email=f"{owner_id}@example.com",
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Firewall delivery concurrency",
                provisioner="kubernetes",
                runtime_status="running",
                firewall_revision=revision,
                firewall_observed_revision=observed_revision,
                firewall_sync_status="applying",
                firewall_target_delivery_id=command_id,
                workspace_firewall_egress_mode="allowlist",
                workspace_firewall_allowed_domains=["desired.example.com"],
                browser_firewall_allowed_domains=[],
            )
        )
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=command_id,
                workspace_id=workspace_id,
                firewall_revision=revision,
                retry_of_command_id=None,
                root_command_id=command_id,
                status="pending",
                attempt_count=0,
                next_attempt_at=scheduled_at,
                created_at=scheduled_at,
                updated_at=scheduled_at,
            )
        )
        db.commit()
    return workspace_id, command_id, scheduled_at


def _run_delivery(engine: Engine, worker_id: str) -> dict[str, int]:
    with Session(engine) as db:
        service = WorkspaceFirewallDeliveryService(db)
        service.settings = SimpleNamespace(
            FIREWALL_SYNC_BATCH_SIZE=1,
            FIREWALL_SYNC_LEASE_SECONDS=30,
            FIREWALL_SYNC_MAX_ATTEMPTS=3,
            FIREWALL_SYNC_BASE_DELAY_SECONDS=1,
            FIREWALL_SYNC_MAX_DELAY_SECONDS=10,
        )
        return service.reconcile_due(worker_id=worker_id)


def test_same_workspace_contention_defers_then_two_workers_deliver_once(
    firewall_delivery_database: Engine,
) -> None:
    engine = firewall_delivery_database
    workspace_id, command_id, _ = _seed_current_delivery(engine)

    with workspace_session_advisory_lock(engine, workspace_id):
        contended_result = _run_delivery(engine, "firewall-worker-contended")

    assert contended_result == {"delivered": 0, "failed": 0}
    with Session(engine) as db:
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        assert command is not None
        assert command.status == "pending"
        assert command.attempt_count == 0
        assert command.lease_owner is None
        assert command.lease_expires_at is None
        command.next_attempt_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()

    apply_started = Event()
    release_apply = Event()
    applied_delivery_ids: list[str] = []

    def blocking_apply(
        _service: object,
        _workspace: db_models.Workspace,
        *,
        delivery_id: str,
    ) -> None:
        applied_delivery_ids.append(delivery_id)
        apply_started.set()
        if not release_apply.wait(timeout=10):
            raise AssertionError("Timed out waiting to release firewall apply")

    with patch(
        "app.modules.workspace.firewall_delivery."
        "WorkspaceCustomResourceService.apply_firewall_spec",
        autospec=True,
        side_effect=blocking_apply,
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                _run_delivery,
                engine,
                "firewall-worker-first",
            )
            try:
                assert apply_started.wait(timeout=10)
                second = executor.submit(
                    _run_delivery,
                    engine,
                    "firewall-worker-second",
                )
                second_result = second.result(timeout=10)
            finally:
                release_apply.set()
            first_result = first.result(timeout=10)

    assert first_result == {"delivered": 1, "failed": 0}
    assert second_result == {"delivered": 0, "failed": 0}
    assert applied_delivery_ids == [command_id]
    with Session(engine) as db:
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        workspace = db.get(db_models.Workspace, workspace_id)
        assert command is not None
        assert workspace is not None
        assert command.status == "delivered"
        assert command.attempt_count == 1
        assert command.lease_owner is None
        assert command.lease_expires_at is None
        assert workspace.firewall_revision == 2
        assert workspace.firewall_observed_revision == 1
        assert workspace.firewall_sync_status == "applying"


def test_expired_lease_is_reclaimed_and_stale_owner_cannot_finish(
    firewall_delivery_database: Engine,
) -> None:
    engine = firewall_delivery_database
    workspace_id, command_id, scheduled_at = _seed_current_delivery(engine)
    takeover_at = scheduled_at + timedelta(seconds=2)

    with Session(engine) as db:
        command = WorkspaceFirewallSyncCommandRepository(db).claim_due(
            worker_id="firewall-worker-old",
            now=scheduled_at,
            lease_seconds=1,
        )
        assert command is not None
        assert command.id == command_id
        db.commit()

    with Session(engine) as db:
        command = WorkspaceFirewallSyncCommandRepository(db).claim_due(
            worker_id="firewall-worker-new",
            now=takeover_at,
            lease_seconds=30,
        )
        assert command is not None
        assert command.id == command_id
        assert command.attempt_count == 2
        db.commit()

    with Session(engine) as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)
        assert (
            repository.complete(
                command_id=command_id,
                worker_id="firewall-worker-old",
                completed_at=takeover_at,
                observed=True,
            )
            is False
        )
        assert (
            repository.fail(
                command_id=command_id,
                worker_id="firewall-worker-old",
                failed_at=takeover_at,
                error_code="FIREWALL_DELIVERY_FAILED",
                max_attempts=3,
                base_delay_seconds=1,
                max_delay_seconds=10,
            )
            is False
        )
        db.commit()

    with Session(engine) as db:
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        workspace = db.get(db_models.Workspace, workspace_id)
        assert command is not None
        assert workspace is not None
        assert command.status == "processing"
        assert command.lease_owner == "firewall-worker-new"
        assert command.attempt_count == 2
        assert workspace.firewall_observed_revision == 1

    completed_at = takeover_at + timedelta(seconds=1)
    with Session(engine) as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)
        assert repository.complete(
            command_id=command_id,
            worker_id="firewall-worker-new",
            completed_at=completed_at,
            observed=True,
        )
        db.commit()

    with Session(engine) as db:
        command = db.get(db_models.WorkspaceFirewallSyncCommand, command_id)
        workspace = db.get(db_models.Workspace, workspace_id)
        assert command is not None
        assert workspace is not None
        assert command.status == "delivered"
        assert command.lease_owner is None
        assert command.lease_expires_at is None
        assert workspace.firewall_observed_revision == 2
        assert workspace.firewall_sync_status == "applied"


def test_old_revision_cannot_overwrite_new_target_or_observed_revision(
    firewall_delivery_database: Engine,
) -> None:
    engine = firewall_delivery_database
    workspace_id, old_command_id, scheduled_at = _seed_current_delivery(engine)

    with Session(engine) as db:
        old_command = WorkspaceFirewallSyncCommandRepository(db).claim_due(
            worker_id="firewall-worker-old-revision",
            now=scheduled_at,
            lease_seconds=30,
        )
        assert old_command is not None
        db.commit()

    new_command_id = str(uuid4())
    new_revision_at = scheduled_at + timedelta(seconds=1)
    with Session(engine) as db:
        workspace = db.get(
            db_models.Workspace,
            workspace_id,
            with_for_update=True,
        )
        assert workspace is not None
        workspace.firewall_revision = 3
        workspace.firewall_target_delivery_id = new_command_id
        workspace.firewall_sync_status = "applying"
        workspace.workspace_firewall_allowed_domains = ["new.example.com"]
        db.add(
            db_models.WorkspaceFirewallSyncCommand(
                id=new_command_id,
                workspace_id=workspace_id,
                firewall_revision=3,
                retry_of_command_id=None,
                root_command_id=new_command_id,
                status="pending",
                attempt_count=0,
                next_attempt_at=new_revision_at,
                created_at=new_revision_at,
                updated_at=new_revision_at,
            )
        )
        db.commit()

    with Session(engine) as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)
        assert repository.complete(
            command_id=old_command_id,
            worker_id="firewall-worker-old-revision",
            completed_at=new_revision_at,
            observed=True,
        )
        db.commit()

    with Session(engine) as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        old_command = db.get(
            db_models.WorkspaceFirewallSyncCommand,
            old_command_id,
        )
        new_command = db.get(
            db_models.WorkspaceFirewallSyncCommand,
            new_command_id,
        )
        assert workspace is not None
        assert old_command is not None
        assert new_command is not None
        assert old_command.status == "superseded"
        assert old_command.lease_owner is None
        assert workspace.firewall_revision == 3
        assert workspace.firewall_observed_revision == 1
        assert workspace.firewall_target_delivery_id == new_command_id
        assert workspace.workspace_firewall_allowed_domains == ["new.example.com"]
        assert new_command.status == "pending"

    completed_at = new_revision_at + timedelta(seconds=1)
    with Session(engine) as db:
        repository = WorkspaceFirewallSyncCommandRepository(db)
        new_command = repository.claim_due(
            worker_id="firewall-worker-new-revision",
            now=new_revision_at,
            lease_seconds=30,
        )
        assert new_command is not None
        assert new_command.id == new_command_id
        assert repository.complete(
            command_id=new_command_id,
            worker_id="firewall-worker-new-revision",
            completed_at=completed_at,
            observed=True,
        )
        db.commit()

    with Session(engine) as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        new_command = db.get(
            db_models.WorkspaceFirewallSyncCommand,
            new_command_id,
        )
        assert workspace is not None
        assert new_command is not None
        assert new_command.status == "delivered"
        assert workspace.firewall_revision == 3
        assert workspace.firewall_observed_revision == 3
        assert workspace.firewall_sync_status == "applied"
