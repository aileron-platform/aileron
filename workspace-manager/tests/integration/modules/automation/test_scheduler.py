"""PostgreSQL tests for the bounded-coalescing Automation scheduler."""

from __future__ import annotations

import importlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import models as db_models
from app.db.database import Base


@pytest.fixture()
def scheduler_database():
    schema = f"automation_scheduler_{uuid4().hex}"
    database_url = os.environ["AUTOMATION_TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_size=10,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _scheduler_type():
    module = importlib.import_module("app.modules.automation.scheduler")
    scheduler_type = getattr(module, "AutomationScheduler", None)
    assert scheduler_type is not None, "missing AutomationScheduler"
    return scheduler_type


def _seed_due_jobs(engine, count: int) -> list[str]:
    due = datetime.now(timezone.utc) - timedelta(minutes=5)
    with Session(engine) as session:
        user = db_models.User(
            id="scheduler-user",
            username="scheduler-user",
            display_name="Scheduler User",
            is_active=True,
            identity_enabled=True,
            sync_status="synced",
            platform_role="member",
            role_status="valid",
        )
        workspace = db_models.Workspace(
            id="scheduler-workspace",
            owner_id=user.id,
            name="Scheduler Workspace",
            provisioner="kubernetes",
        )
        session.add_all([user, workspace])
        job_ids = []
        for index in range(count):
            job_id = f"scheduled-job-{index}"
            job_ids.append(job_id)
            session.add(
                db_models.AutomationJob(
                    id=job_id,
                    workspace_id=workspace.id,
                    creator_user_id=user.id,
                    name=job_id,
                    prompt="run",
                    status="active",
                    trigger="every",
                    schedule="1m",
                    exact=True,
                    agentic_tool="claude",
                    model="claude-sonnet",
                    agent_config={
                        "mode": "execute",
                        "permissionMode": "bypassPermissions",
                    },
                    worktree_key=f"automation/{job_id}",
                    worktree_branch=f"automation/{job_id}",
                    notification_config={},
                    next_run_at=due,
                    created_at=due,
                    updated_at=due,
                )
            )
        session.commit()
    return job_ids


def test_two_schedulers_enqueue_each_occurrence_once(
    scheduler_database, monkeypatch
) -> None:
    job_id = _seed_due_jobs(scheduler_database, 1)[0]
    factory = sessionmaker(bind=scheduler_database, autoflush=False, autocommit=False)
    barrier = Barrier(2)
    scheduler_type = _scheduler_type()
    repository_module = importlib.import_module("app.modules.automation.repository")
    original_list_due = repository_module.AutomationRepository.list_due_occurrences

    def list_due_together(repository):
        due = original_list_due(repository)
        barrier.wait()
        return due

    monkeypatch.setattr(
        repository_module.AutomationRepository,
        "list_due_occurrences",
        list_due_together,
    )

    def run_once() -> int:
        scheduler = scheduler_type(session_factory=factory)
        return scheduler.run_once()

    with ThreadPoolExecutor(max_workers=2) as executor:
        processed = list(executor.map(lambda _: run_once(), range(2)))

    assert sum(processed) == 1
    with Session(scheduler_database) as session:
        executions = session.scalars(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.job_id == job_id
            )
        ).all()
        assert len(executions) == 1
        job = session.get(db_models.AutomationJob, job_id)
        assert job.next_run_at > datetime.now(timezone.utc)


def test_two_hundred_jobs_use_one_scheduler_run(scheduler_database) -> None:
    _seed_due_jobs(scheduler_database, 200)
    factory = sessionmaker(bind=scheduler_database, autoflush=False, autocommit=False)
    scheduler = _scheduler_type()(session_factory=factory)
    assert scheduler.run_once() == 200
    assert not hasattr(scheduler, "job_tasks")


def test_scheduled_queue_full_notifies_once_after_terminal_commit(
    scheduler_database,
) -> None:
    job_id = _seed_due_jobs(scheduler_database, 1)[0]
    with Session(scheduler_database) as session:
        job = session.get(db_models.AutomationJob, job_id)
        job.notification_config = {
            "failure_destination": "https://failure.example/hook"
        }
        for index in range(10):
            session.add(
                db_models.AutomationExecution(
                    id=f"queued-{index}",
                    job_id=job_id,
                    workspace_id="scheduler-workspace",
                    status="queued",
                    trigger="manual",
                    scheduled_for=job.next_run_at + timedelta(seconds=index),
                    queued_at=job.next_run_at,
                    principal_user_id_snapshot="scheduler-user",
                    prompt_snapshot="run",
                    agentic_tool_snapshot="claude",
                    model_snapshot="claude-sonnet",
                    agent_config_snapshot={"permissionMode": "bypassPermissions"},
                    worktree_key_snapshot=f"automation/{job_id}",
                )
            )
        session.commit()

    calls = []

    class Notifications:
        def deliver_terminal(self, *, execution, notification_config):
            calls.append((execution.status, notification_config))
            return "delivered"

    factory = sessionmaker(bind=scheduler_database, autoflush=False, autocommit=False)
    scheduler = _scheduler_type()(
        session_factory=factory, notifications=Notifications()
    )
    assert scheduler.run_once() == 1
    assert calls == [
        ("failed", {"failure_destination": "https://failure.example/hook"})
    ]
    with Session(scheduler_database) as session:
        terminal = session.scalar(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.job_id == job_id,
                db_models.AutomationExecution.error_code == "queue_full",
            )
        )
        assert terminal.notification_status == "delivered"


def test_scheduled_queue_full_notification_status_failure_is_best_effort(
    scheduler_database, monkeypatch
) -> None:
    job_id = _seed_due_jobs(scheduler_database, 1)[0]
    with Session(scheduler_database) as session:
        job = session.get(db_models.AutomationJob, job_id)
        job.notification_config = {
            "failure_destination": "https://failure.example/hook"
        }
        for index in range(10):
            session.add(
                db_models.AutomationExecution(
                    id=f"queued-{index}",
                    job_id=job_id,
                    workspace_id="scheduler-workspace",
                    status="queued",
                    trigger="manual",
                    scheduled_for=job.next_run_at + timedelta(seconds=index),
                    queued_at=job.next_run_at,
                    principal_user_id_snapshot="scheduler-user",
                    prompt_snapshot="run",
                    agentic_tool_snapshot="claude",
                    model_snapshot="claude-sonnet",
                    agent_config_snapshot={"permissionMode": "bypassPermissions"},
                    worktree_key_snapshot=f"automation/{job_id}",
                )
            )
        session.commit()

    class Notifications:
        def deliver_terminal(self, *, execution, notification_config):
            return "delivered"

    def fail_status_update(*args, **kwargs):
        raise RuntimeError("notification status unavailable")

    repository_module = importlib.import_module("app.modules.automation.repository")
    monkeypatch.setattr(
        repository_module.AutomationRepository,
        "update_notification_status",
        fail_status_update,
    )
    factory = sessionmaker(bind=scheduler_database, autoflush=False, autocommit=False)
    scheduler = _scheduler_type()(
        session_factory=factory, notifications=Notifications()
    )

    assert scheduler.run_once() == 1
    with Session(scheduler_database) as session:
        terminal = session.scalar(
            select(db_models.AutomationExecution).where(
                db_models.AutomationExecution.job_id == job_id,
                db_models.AutomationExecution.error_code == "queue_full",
            )
        )
        assert terminal.status == "failed"
        assert terminal.notification_status is None
