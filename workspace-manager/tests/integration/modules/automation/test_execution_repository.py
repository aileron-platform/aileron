"""PostgreSQL admission tests for immutable Automation executions."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.db.database import Base
from app.modules.authorization.actor import AuthorizationActor
from app.modules.automation.repository import AutomationRepository


@pytest.fixture()
def automation_database():
    schema = f"automation_execution_{uuid4().hex}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=20,
        max_overflow=10,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_job(
    engine,
    *,
    job_id: str = "job-1",
    trigger: str = "manual",
    schedule: str = "",
    status: str = "active",
    next_run_at: datetime | None = None,
    webhook_key: str | None = "webhook-secret",
) -> tuple[str, str]:
    user_id = f"user-{job_id}"
    workspace_id = f"workspace-{job_id}"
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            db_models.User(
                id=user_id,
                username=user_id,
                display_name=user_id,
                is_active=True,
                identity_enabled=True,
                sync_status="synced",
                platform_role="member",
                role_status="valid",
            )
        )
        session.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=user_id,
                name=workspace_id,
                provisioner="kubernetes",
            )
        )
        session.add(
            db_models.AutomationJob(
                id=job_id,
                workspace_id=workspace_id,
                creator_user_id=user_id,
                name="Original name",
                prompt="original prompt",
                status=status,
                trigger=trigger,
                schedule=schedule,
                exact=True,
                agentic_tool="claude",
                model="claude-sonnet",
                agent_config={
                    "mode": "execute",
                    "permissionMode": "bypassPermissions",
                },
                worktree_key=f"automation/{job_id}",
                worktree_branch=f"automation/{job_id}",
                notification_config={"webhook_api_key": webhook_key},
                next_run_at=next_run_at,
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    return user_id, workspace_id


def _assert_enqueue_contract(repository: AutomationRepository, method: str) -> None:
    assert callable(getattr(repository, method, None)), f"missing {method}"


def _actor(user_id: str) -> AuthorizationActor:
    return AuthorizationActor(user_id=user_id, platform_role="member")


def _error_code(error: Exception) -> str:
    return str(getattr(error, "code", error))


def test_concurrent_manual_enqueue_never_exceeds_ten(automation_database) -> None:
    actor_id, _ = _seed_job(automation_database)
    barrier = Barrier(12)

    def enqueue(index: int) -> tuple[int, str]:
        with Session(automation_database) as session:
            repository = AutomationRepository(session)
            _assert_enqueue_contract(repository, "enqueue_manual")
            barrier.wait()
            try:
                execution = repository.enqueue_manual(
                    job_id="job-1", actor=_actor(actor_id)
                )
                return index, execution.status
            except Exception as exc:  # queue rejection is part of the contract
                return index, _error_code(exc)

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(enqueue, range(12)))

    assert [status for _, status in results].count("queued") == 10
    assert [status for _, status in results].count("automation_queue_full") == 2
    with Session(automation_database) as session:
        queued = session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.job_id == "job-1",
                db_models.AutomationExecution.status == "queued",
            )
        ).all()
        assert len(queued) == 10


def test_job_execution_history_supports_pagination_and_date_range(
    automation_database,
) -> None:
    actor_id, _ = _seed_job(automation_database)
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        for _ in range(3):
            repository.enqueue_manual(job_id="job-1", actor=_actor(actor_id))
        session.commit()

        items, total = repository.list_job_executions(
            job_id="job-1",
            actor=_actor(actor_id),
            page=2,
            page_size=2,
        )
        assert total == 3
        assert len(items) == 1

        future_items, future_total = repository.list_job_executions(
            job_id="job-1",
            actor=_actor(actor_id),
            page=1,
            page_size=10,
            range_start=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert future_total == 0
        assert future_items == []


def test_manual_snapshot_is_immutable_after_job_edit(automation_database) -> None:
    actor_id, workspace_id = _seed_job(automation_database)
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        _assert_enqueue_contract(repository, "enqueue_manual")
        execution = repository.enqueue_manual(job_id="job-1", actor=_actor(actor_id))
        assert execution.workspace_id == workspace_id
        assert execution.trigger == "manual"
        assert execution.status == "queued"
        assert execution.queued_at == execution.scheduled_for
        assert execution.principal_user_id_snapshot == actor_id
        assert execution.prompt_snapshot == "original prompt"
        assert execution.agentic_tool_snapshot == "claude"
        assert execution.model_snapshot == "claude-sonnet"
        assert execution.agent_config_snapshot == {
            "mode": "execute",
            "permissionMode": "bypassPermissions",
        }
        assert execution.worktree_key_snapshot == "automation/job-1"

        job = session.get(db_models.AutomationJob, "job-1")
        job.prompt = "edited prompt"
        job.model = "edited-model"
        job.agent_config = {
            "mode": "plan",
            "permissionMode": "bypassPermissions",
        }
        session.commit()
        session.refresh(execution)
        assert execution.prompt_snapshot == "original prompt"
        assert execution.model_snapshot == "claude-sonnet"
        assert execution.agent_config_snapshot["mode"] == "execute"


def test_webhook_uses_constant_contract_and_rejects_newest_when_full(
    automation_database,
) -> None:
    _seed_job(automation_database, trigger="webhook")
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        _assert_enqueue_contract(repository, "enqueue_webhook")
        for _ in range(10):
            assert (
                repository.enqueue_webhook(
                    job_id="job-1", presented_key=SecretStr("webhook-secret")
                ).status
                == "queued"
            )
        with pytest.raises(Exception) as error:
            repository.enqueue_webhook(
                job_id="job-1", presented_key=SecretStr("webhook-secret")
            )
        assert _error_code(error.value) == "automation_queue_full"


def test_scheduled_overflow_records_terminal_failure(automation_database) -> None:
    original_due = datetime.now(timezone.utc) - timedelta(minutes=10)
    actor_id, workspace_id = _seed_job(
        automation_database,
        trigger="every",
        schedule="1m",
        next_run_at=original_due,
    )
    with Session(automation_database) as session:
        now = AutomationRepository(session).transaction_now()
        for index in range(10):
            session.add(
                db_models.AutomationExecution(
                    id=f"queued-{index}",
                    job_id="job-1",
                    workspace_id=workspace_id,
                    status="queued",
                    trigger="manual",
                    scheduled_for=now + timedelta(microseconds=index),
                    queued_at=now,
                    principal_user_id_snapshot=actor_id,
                    prompt_snapshot="existing",
                    agentic_tool_snapshot="claude",
                    model_snapshot="claude-sonnet",
                    agent_config_snapshot={
                        "mode": "execute",
                        "permissionMode": "bypassPermissions",
                    },
                    worktree_key_snapshot="automation/job-1",
                )
            )
        session.commit()
        repository = AutomationRepository(session)
        _assert_enqueue_contract(repository, "enqueue_scheduled_occurrence")
        execution = repository.enqueue_scheduled_occurrence(
            job_id="job-1", expected_scheduled_for=original_due
        )
        assert execution is not None
        assert execution.status == "failed"
        assert execution.error_code == "queue_full"
        assert execution.scheduled_for == original_due
        assert execution.queued_at is None
        assert execution.started_at is None
        assert execution.finished_at is not None
        assert execution.prompt_snapshot == "original prompt"
        assert execution.principal_user_id_snapshot == actor_id
        assert execution.notification_status is None
        assert (
            len(
                session.scalars(
                    select(db_models.AutomationExecution).where(
                        db_models.AutomationExecution.job_id == "job-1",
                        db_models.AutomationExecution.status == "queued",
                    )
                ).all()
            )
            == 10
        )


def test_overdue_recurring_job_coalesces_one_occurrence(automation_database) -> None:
    original_due = datetime.now(timezone.utc) - timedelta(hours=2)
    _seed_job(
        automation_database,
        trigger="every",
        schedule="1m",
        next_run_at=original_due,
    )
    with Session(automation_database) as session:
        repository = AutomationRepository(session)
        _assert_enqueue_contract(repository, "enqueue_scheduled_occurrence")
        execution = repository.enqueue_scheduled_occurrence(
            job_id="job-1",
            expected_scheduled_for=original_due,
        )
        refreshed = session.get(db_models.AutomationJob, "job-1")
        assert execution is not None
        assert execution.scheduled_for == original_due
        assert execution.status in {"queued", "failed"}
        assert execution.created_at == execution.queued_at
        assert execution.updated_at == execution.queued_at
        assert execution.created_at != execution.scheduled_for
        assert refreshed.next_run_at > repository.transaction_now()
        assert (
            repository.enqueue_scheduled_occurrence(
                job_id="job-1", expected_scheduled_for=original_due
            )
            is None
        )
