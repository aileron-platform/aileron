"""Real PostgreSQL runtime job heartbeat integration tests."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.workspace.runtime.job_execution import (
    RuntimeJobClaimLease,
    RuntimeJobClaimLostError,
)

_OWNER_ID = "runtime-job-heartbeat-owner"
_WORKSPACE_ID = "88888888-8888-4888-8888-888888888888"


@pytest.fixture()
def runtime_job_database() -> Engine:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")

    schema = f"runtime_job_heartbeat_{uuid4().hex}"
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


def _seed_running_job(engine: Engine) -> tuple[str, str, datetime]:
    job_id = str(uuid4())
    claim_token = str(uuid4())
    heartbeat_at = datetime.now(timezone.utc)
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
                name="Runtime job heartbeat",
                provisioner="docker",
                runtime_status="running",
                knowledge_base_mount_desired_revision=1,
                knowledge_base_mount_observed_revision=0,
                knowledge_base_mount_sync_status="preflighting",
                knowledge_base_mount_candidate_snapshot=[],
            )
        )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=_WORKSPACE_ID,
                operation="knowledge_base_mount_reconcile",
                strategy="docker",
                status="running",
                target_revision=1,
                correlation_id="heartbeat-attempt",
                root_correlation_id="heartbeat-root",
                job_metadata={"attempt": 0},
                retries=0,
                claim_token=claim_token,
                claim_expires_at=heartbeat_at + timedelta(seconds=10),
                last_heartbeat_at=heartbeat_at,
                dispatch_attempts=0,
                scheduled_at=heartbeat_at,
                started_at=heartbeat_at,
            )
        )
        db.commit()
    return job_id, claim_token, heartbeat_at


def _heartbeat_at(engine: Engine, job_id: str) -> datetime:
    with Session(engine) as db:
        value = db.get(db_models.WorkspaceRuntimeJob, job_id).last_heartbeat_at
        assert value is not None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def test_slow_job_renews_lease_and_stops_heartbeating_after_context(
    runtime_job_database: Engine,
) -> None:
    job_id, claim_token, _ = _seed_running_job(runtime_job_database)
    lease = RuntimeJobClaimLease(
        bind=runtime_job_database,
        job_id=job_id,
        claim_token=claim_token,
        timeout_seconds=4,
    )

    with lease:
        entered_at = _heartbeat_at(runtime_job_database, job_id)
        deadline = time.monotonic() + 3
        renewed_at = _heartbeat_at(runtime_job_database, job_id)
        while renewed_at <= entered_at and time.monotonic() < deadline:
            time.sleep(0.1)
            renewed_at = _heartbeat_at(runtime_job_database, job_id)
        assert renewed_at > entered_at

    stopped_at = _heartbeat_at(runtime_job_database, job_id)
    time.sleep(1.2)
    assert _heartbeat_at(runtime_job_database, job_id) == stopped_at


def test_claim_token_replacement_is_detected_before_next_side_effect(
    runtime_job_database: Engine,
) -> None:
    job_id, claim_token, _ = _seed_running_job(runtime_job_database)
    lease = RuntimeJobClaimLease(
        bind=runtime_job_database,
        job_id=job_id,
        claim_token=claim_token,
        timeout_seconds=4,
    )

    with lease:
        with Session(runtime_job_database) as db:
            job = db.get(db_models.WorkspaceRuntimeJob, job_id)
            job.claim_token = str(uuid4())
            db.commit()

        with pytest.raises(RuntimeJobClaimLostError):
            lease.heartbeat_once()
