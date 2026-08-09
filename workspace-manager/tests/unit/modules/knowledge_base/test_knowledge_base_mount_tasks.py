"""Durable Workspace runtime task dispatch tests."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

import app.modules.workspace.tasks as tasks
from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceStatusSnapshot,
)


def _seed_queued_job(
    session_factory,
    *,
    runtime_status: str = "running",
    offline_promotion: bool = False,
    provisioner: str = "docker",
    mount_desired_revision: int = 1,
) -> str:
    owner_id = f"owner-{uuid4()}"
    workspace_id = str(uuid4())
    job_id = str(uuid4())
    with session_factory() as db:
        db.add(
            db_models.User(
                id=owner_id,
                oidc_subject=f"kc-{owner_id}",
                username=owner_id,
                email=f"{owner_id}@example.com",
                platform_role="member",
                role_status="valid",
                sync_status="synced",
                identity_enabled=True,
                is_active=True,
            )
        )
        runtime_instance_id = None if runtime_status == "stopped" else str(uuid4())
        db.add(
            db_models.Workspace(
                id=workspace_id,
                owner_id=owner_id,
                name="Dispatch",
                runtime="universal",
                provisioner=provisioner,
                target_namespace=(
                    "workspace-system" if provisioner == "kubernetes" else None
                ),
                runtime_status=runtime_status,
                runtime_desired_state="running",
                runtime_desired_revision=1,
                runtime_observed_revision=1,
                runtime_instance_id=runtime_instance_id,
                knowledge_base_mount_active_revision=mount_desired_revision - 1,
                knowledge_base_mount_desired_revision=mount_desired_revision,
                knowledge_base_mount_observed_revision=mount_desired_revision - 1,
                knowledge_base_mount_sync_status="preflighting",
                knowledge_base_mount_active_snapshot=[],
                knowledge_base_mount_candidate_snapshot=[],
                knowledge_base_mount_failed_snapshot=None,
                runtime_access_revision=0,
                runtime_access_observed_revision=0,
                env_vars=[],
                workspace_firewall_allowed_domains=[],
                browser_firewall_allowed_domains=[],
                acp_cli_args=[],
            )
        )
        db.add(
            db_models.WorkspaceRuntimeJob(
                id=job_id,
                workspace_id=workspace_id,
                operation="knowledge_base_mount_reconcile",
                strategy=provisioner,
                status="queued",
                retries=0,
                target_revision=mount_desired_revision,
                target_runtime_instance_id=runtime_instance_id,
                correlation_id=f"correlation-{job_id}",
                root_correlation_id=f"correlation-{job_id}",
                job_metadata={
                    "mount_action": "apply_candidate",
                    "mutation_action": "detach" if offline_promotion else "attach",
                    **({"offline_promotion": True} if offline_promotion else {}),
                    "attempt": 0,
                },
                dispatch_attempts=0,
                scheduled_at=datetime.utcnow(),
            )
        )
        db.commit()
    return job_id


def test_recovery_tick_dispatches_due_eligible_job_without_mutating_it(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    job_id = _seed_queued_job(session_factory)
    sent: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tasks.current_app,
        "send_task",
        lambda name, args: sent.append((name, args)),
    )

    result = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert result["dispatched"] == 1
    assert sent == [("workspace_runtime.reconcile_job", [job_id])]
    with session_factory() as db:
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert job.status == "queued"
        assert job.dispatch_attempts == 0


def test_recovery_tick_does_not_infer_lifecycle_intent_from_observed_status(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    job_id = _seed_queued_job(
        session_factory,
        runtime_status="starting",
    )
    with session_factory() as db:
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        workspace_id = job.workspace_id
        workspace = db.get(db_models.Workspace, workspace_id)
        db.delete(job)
        workspace.knowledge_base_mount_active_revision = 1
        workspace.knowledge_base_mount_desired_revision = 1
        workspace.knowledge_base_mount_observed_revision = 1
        workspace.knowledge_base_mount_sync_status = "ready"
        workspace.knowledge_base_mount_candidate_snapshot = None
        db.commit()

    sent: list[str] = []
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tasks.current_app,
        "send_task",
        lambda _name, args: sent.append(args[0]),
    )

    result = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert result["revision_recovered"] == 0
    assert result["dispatched"] == 0
    assert sent == []
    with session_factory() as db:
        jobs = list(
            db.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id
                )
            ).all()
        )
        assert jobs == []


def test_publish_failure_keeps_job_queued_and_applies_bounded_backoff(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    job_id = _seed_queued_job(session_factory)
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)

    def publish_failure(_name, _args):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(tasks.current_app, "send_task", publish_failure)

    result = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert result["publish_failed"] == 1
    with session_factory() as db:
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        assert job.status == "queued"
        assert job.dispatch_attempts == 1
        assert job.scheduled_at > datetime.utcnow()


def test_stopped_job_dispatches_only_for_offline_promotion(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    regular_job_id = _seed_queued_job(
        session_factory,
        runtime_status="stopped",
    )
    offline_job_id = _seed_queued_job(
        session_factory,
        runtime_status="stopped",
        offline_promotion=True,
    )
    sent: list[str] = []
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(
        tasks.current_app,
        "send_task",
        lambda _name, args: sent.append(args[0]),
    )

    tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    assert sent == [offline_job_id]
    assert regular_job_id not in sent


def test_recovery_tick_heals_orphan_restarting_before_dispatching_mount(
    test_app,
    monkeypatch,
) -> None:
    _, session_factory = test_app
    job_id = _seed_queued_job(
        session_factory,
        runtime_status="restarting",
        provisioner="kubernetes",
        mount_desired_revision=2,
    )
    with session_factory() as db:
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        workspace = db.get(db_models.Workspace, job.workspace_id)
        workspace_id = workspace.id
        runtime_instance_id = workspace.runtime_instance_id

    snapshot = WorkspaceCustomResourceStatusSnapshot(
        workspace_id=workspace_id,
        resource_name=f"workspace-{workspace_id}",
        namespace=get_settings().RUNTIME_K8S_NAMESPACE,
        custom_resource={
            "metadata": {"generation": 2},
            "spec": {
                "runtime": {
                    "instanceId": runtime_instance_id,
                    "revision": 1,
                }
            },
            "status": {
                "observedGeneration": 2,
                "phase": "Running",
                "components": {
                    "runtime": {
                        "observedRevision": 1,
                        "mountObservedRevision": 1,
                        "accessObservedRevision": 0,
                        "phase": "Running",
                        "ready": True,
                        "terminalReady": True,
                    }
                },
            },
        },
    )
    sent: list[str] = []
    monkeypatch.setattr(tasks, "SessionLocal", session_factory)
    monkeypatch.setattr(
        "app.modules.workspace.custom_resources.WorkspaceCustomResourceService.fetch_workspace_status_snapshot",
        lambda _service, requested_workspace_id: (
            snapshot if requested_workspace_id == workspace_id else None
        ),
    )
    monkeypatch.setattr(
        tasks.current_app,
        "send_task",
        lambda _name, args: sent.append(args[0]),
    )

    result = tasks.recover_and_dispatch_workspace_runtime_jobs.run()

    with session_factory() as db:
        workspace = db.get(db_models.Workspace, workspace_id)
        job_status = db.get(db_models.WorkspaceRuntimeJob, job_id).status
        assert result["dispatched"] == 1, (
            result,
            sent,
            workspace.runtime_status,
            job_status,
        )
        assert sent == [job_id]
        assert workspace.runtime_status == "running"
        assert workspace.knowledge_base_mount_desired_revision == 2
        assert workspace.knowledge_base_mount_observed_revision == 1
        assert job_status == "queued"
