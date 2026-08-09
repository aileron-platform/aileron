"""Real Redis, Celery worker, and beat recovery integration tests."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from celery import Celery
from redis import Redis
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

import app.modules.workspace.tasks as tasks
from app.celery.app import celery_app
from app.db import models as db_models
from app.db.database import Base

_OWNER_ID = "celery-recovery-owner"
_QUEUED_WORKSPACE_ID = "99999999-9999-4999-8999-999999999991"
_EXPIRED_WORKSPACE_ID = "99999999-9999-4999-8999-999999999992"
_QUEUED_JOB_ID = "99999999-9999-4999-8999-999999999993"
_EXPIRED_JOB_ID = "99999999-9999-4999-8999-999999999994"
_QUEUED_CORRELATION_ID = "celery-recovery-queued"
_EXPIRED_CORRELATION_ID = "celery-recovery-expired"
_PROCESS_STARTUP_TIMEOUT_SECONDS = 60


@pytest.fixture()
def celery_recovery_database() -> Iterator[tuple[Engine, str]]:
    database_url = os.environ.get("AUTOMATION_TEST_DATABASE_URL")
    if not database_url or not database_url.startswith("postgresql"):
        pytest.fail("A real PostgreSQL integration database is required")

    schema = f"celery_recovery_{uuid4().hex}"
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engine = create_engine(
        database_url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    worker_database_url = (
        make_url(database_url)
        .update_query_dict({"options": f"-csearch_path={schema}"})
        .render_as_string(hide_password=False)
    )
    try:
        yield engine, worker_database_url
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


def _seed_queued_job(engine: Engine) -> datetime:
    now = datetime.now(timezone.utc)
    runtime_instance_id = str(uuid4())
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
                id=_QUEUED_WORKSPACE_ID,
                owner_id=_OWNER_ID,
                name="Queued broker recovery",
                provisioner="docker",
                runtime_status="running",
                runtime_instance_id=runtime_instance_id,
                knowledge_base_mount_desired_revision=2,
                knowledge_base_mount_observed_revision=0,
                knowledge_base_mount_sync_status="preflighting",
                knowledge_base_mount_candidate_snapshot=[],
            )
        )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=_QUEUED_JOB_ID,
                workspace_id=_QUEUED_WORKSPACE_ID,
                operation="knowledge_base_mount_reconcile",
                strategy="docker",
                status="queued",
                retries=0,
                target_revision=1,
                target_runtime_instance_id=runtime_instance_id,
                correlation_id=_QUEUED_CORRELATION_ID,
                root_correlation_id=_QUEUED_CORRELATION_ID,
                job_metadata={"attempt": 0},
                dispatch_attempts=0,
                scheduled_at=now,
            )
        )
        db.commit()
    return now


def _seed_expired_running_job(engine: Engine) -> None:
    now = datetime.now(timezone.utc)
    runtime_instance_id = str(uuid4())
    with Session(engine) as db:
        db.add(
            db_models.Workspace(
                id=_EXPIRED_WORKSPACE_ID,
                owner_id=_OWNER_ID,
                name="Expired worker recovery",
                provisioner="docker",
                runtime_status="running",
                runtime_instance_id=runtime_instance_id,
                knowledge_base_mount_desired_revision=2,
                knowledge_base_mount_observed_revision=0,
                knowledge_base_mount_sync_status="preflighting",
                knowledge_base_mount_candidate_snapshot=[],
            )
        )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=_EXPIRED_JOB_ID,
                workspace_id=_EXPIRED_WORKSPACE_ID,
                operation="knowledge_base_mount_reconcile",
                strategy="docker",
                status="running",
                retries=0,
                target_revision=1,
                target_runtime_instance_id=runtime_instance_id,
                correlation_id=_EXPIRED_CORRELATION_ID,
                root_correlation_id=_EXPIRED_CORRELATION_ID,
                job_metadata={"attempt": 0},
                claim_token=str(uuid4()),
                claim_expires_at=now - timedelta(seconds=1),
                last_heartbeat_at=now - timedelta(minutes=1),
                dispatch_attempts=0,
                scheduled_at=now - timedelta(minutes=1),
                started_at=now - timedelta(minutes=1),
            )
        )
        db.commit()


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float,
    failure_message: str,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError(failure_message)


def _read_log(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _wait_for_process_log(
    process: subprocess.Popen[bytes],
    path: Path,
    expected: str,
) -> None:
    def ready() -> bool:
        if process.poll() is not None:
            failure = (
                f"Celery process exited with {process.returncode}: {_read_log(path)}"
            )
            raise AssertionError(failure)
        return expected in _read_log(path)

    try:
        _wait_until(
            ready,
            timeout=_PROCESS_STARTUP_TIMEOUT_SECONDS,
            failure_message=f"Timed out waiting for Celery log marker: {expected}",
        )
    except AssertionError as exc:
        if process.poll() is not None:
            raise
        raise AssertionError(f"{exc}\nCELERY LOG:\n{_read_log(path)}") from exc


def _stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        process.wait(timeout=5)


def _job_statuses(engine: Engine) -> dict[str, str]:
    with Session(engine) as db:
        return {
            job_id: status
            for job_id, status in db.execute(
                select(
                    db_models.WorkspaceRuntimeJob.id,
                    db_models.WorkspaceRuntimeJob.status,
                ).where(
                    db_models.WorkspaceRuntimeJob.id.in_(
                        [_QUEUED_JOB_ID, _EXPIRED_JOB_ID]
                    )
                )
            )
        }


def _jobs_are_terminal(engine: Engine) -> bool:
    return _job_statuses(engine) == {
        _QUEUED_JOB_ID: "superseded",
        _EXPIRED_JOB_ID: "superseded",
    }


def test_real_beat_recovers_broker_failure_and_expired_worker_once(
    celery_recovery_database: tuple[Engine, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine, worker_database_url = celery_recovery_database
    broker_url = os.environ.get("CELERY_INTEGRATION_BROKER_URL")
    if not broker_url:
        pytest.fail("CELERY_INTEGRATION_BROKER_URL is required")
    redis_client = Redis.from_url(broker_url)
    try:
        redis_client.ping()
    except Exception as exc:
        pytest.fail(f"A real Redis integration broker is required: {exc}")
    redis_client.flushdb()

    queued_at = _seed_queued_job(engine)
    integration_session = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    monkeypatch.setattr(tasks, "SessionLocal", integration_session)
    settings = tasks.get_settings()
    monkeypatch.setattr(settings, "RUNTIME_JOB_DISPATCH_BASE_DELAY_SECONDS", 1)
    monkeypatch.setattr(settings, "RUNTIME_JOB_DISPATCH_MAX_DELAY_SECONDS", 4)

    failure_app = Celery(
        "runtime-recovery-broker-failure",
        broker="redis://127.0.0.1:1/15",
        backend="cache+memory://",
    )
    failure_app.conf.task_publish_retry = False
    failure_app.conf.broker_transport_options = {
        "socket_connect_timeout": 0.2,
        "socket_timeout": 0.2,
        "retry_on_timeout": False,
    }
    failure_app.set_current()
    try:
        first_tick = tasks.recover_and_dispatch_workspace_runtime_jobs.run()
    finally:
        celery_app.set_current()
        failure_app.close()

    assert first_tick["dispatched"] == 0
    assert first_tick["publish_failed"] == 1
    with Session(engine) as db:
        queued_job = db.get(db_models.WorkspaceRuntimeJob, _QUEUED_JOB_ID)
        assert queued_job is not None
        assert queued_job.status == "queued"
        assert queued_job.dispatch_attempts == 1
        assert queued_job.scheduled_at > queued_at

    _seed_expired_running_job(engine)
    worker_log = tmp_path / "celery-worker.log"
    beat_log = tmp_path / "celery-beat.log"
    worker_environment = os.environ.copy()
    worker_environment.update(
        {
            "CELERY_BROKER_URL": broker_url,
            "CELERY_RESULT_BACKEND": broker_url,
            "DATABASE_URL": worker_database_url,
            "PYTHONPATH": "/workspace-manager",
            "RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS": "31",
            "RUNTIME_JOB_DISPATCH_BASE_DELAY_SECONDS": "1",
            "RUNTIME_JOB_DISPATCH_MAX_DELAY_SECONDS": "4",
            "RUNTIME_JOB_RECOVERY_INTERVAL_SECONDS": "8",
            "C_FORCE_ROOT": "1",
            "PYTHONUNBUFFERED": "1",
        }
    )
    worker_process: subprocess.Popen[bytes] | None = None
    beat_process: subprocess.Popen[bytes] | None = None
    worker_handle = worker_log.open("wb")
    beat_handle = beat_log.open("wb")
    celery_binary = str(Path(os.sys.executable).with_name("celery"))
    try:
        worker_process = subprocess.Popen(
            [
                celery_binary,
                "-A",
                "app.celery.app",
                "worker",
                "--loglevel=INFO",
                "--pool=solo",
                "--concurrency=1",
                "--queues=celery",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "--hostname=runtime-recovery-test@%h",
            ],
            env=worker_environment,
            stdout=worker_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _wait_for_process_log(worker_process, worker_log, " ready.")

        beat_process = subprocess.Popen(
            [
                celery_binary,
                "-A",
                "app.celery.app",
                "beat",
                "--loglevel=INFO",
                f"--schedule={tmp_path / 'celerybeat-schedule'}",
                f"--pidfile={tmp_path / 'celerybeat.pid'}",
                "--max-interval=1",
            ],
            env=worker_environment,
            stdout=beat_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        _wait_for_process_log(
            beat_process,
            beat_log,
            "workspace-runtime-recover-and-dispatch-jobs",
        )
        try:
            _wait_until(
                lambda: _jobs_are_terminal(engine),
                timeout=45,
                failure_message="Durable jobs did not become terminal",
            )
        except AssertionError as exc:
            diagnostics = (
                f"{exc}; statuses={_job_statuses(engine)}\n"
                f"WORKER LOG:\n{_read_log(worker_log)}\n"
                f"BEAT LOG:\n{_read_log(beat_log)}"
            )
            raise AssertionError(diagnostics) from exc
    finally:
        _stop_process(beat_process)
        _stop_process(worker_process)
        beat_handle.close()
        worker_handle.close()

    worker_output = _read_log(worker_log)
    beat_output = _read_log(beat_log)
    runtime_receives = re.findall(
        r"Task workspace_runtime\.reconcile_job\[[^]]+\] received",
        worker_output,
    )
    assert len(runtime_receives) == 2
    assert "Task workspace_runtime.recover_and_dispatch_jobs[" in worker_output
    assert "workspace-runtime-recover-and-dispatch-jobs" in beat_output

    with Session(engine) as db:
        queued_job = db.get(db_models.WorkspaceRuntimeJob, _QUEUED_JOB_ID)
        expired_job = db.get(db_models.WorkspaceRuntimeJob, _EXPIRED_JOB_ID)
        assert queued_job is not None
        assert expired_job is not None
        assert queued_job.status == "superseded"
        assert queued_job.dispatch_attempts == 1
        assert queued_job.retries == 0
        assert expired_job.status == "superseded"
        assert expired_job.retries == 1
        assert expired_job.claim_token is None
        superseded_filter = (
            db_models.AuditEvent.event_type == "runtime.mount_sync_superseded"
        )
        audit_counts = dict(
            db.execute(
                select(
                    db_models.AuditEvent.correlation_id,
                    func.count(db_models.AuditEvent.id),
                )
                .where(
                    superseded_filter,
                    db_models.AuditEvent.correlation_id.in_(
                        [_QUEUED_CORRELATION_ID, _EXPIRED_CORRELATION_ID]
                    ),
                )
                .group_by(db_models.AuditEvent.correlation_id)
            ).all()
        )
        assert audit_counts == {
            _QUEUED_CORRELATION_ID: 1,
            _EXPIRED_CORRELATION_ID: 1,
        }

    redis_client.flushdb()
