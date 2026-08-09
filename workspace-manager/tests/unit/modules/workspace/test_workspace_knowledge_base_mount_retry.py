"""Workspace knowledge base mount retry API tests."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select

from app.db import models as db_models
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


def _valid_user(create_user, *, user_id: str, role: str = "member"):
    return create_user(
        id=user_id,
        platform_role=role,
        role_status="valid",
        identity_enabled=True,
        sync_status="synced",
        is_active=True,
    )


def _failed_workspace(session_factory, *, owner_id: str) -> tuple[str, str]:
    workspace_id = f"workspace-{uuid4().hex[:8]}"
    failed_job_id = "failed-mount-job"
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=workspace_id,
            owner_id=owner_id,
            name="Failed mount",
            runtime="universal",
            provisioner="docker",
            runtime_status="running",
            runtime_instance_id=str(uuid4()),
            knowledge_base_mount_active_revision=3,
            knowledge_base_mount_desired_revision=4,
            knowledge_base_mount_observed_revision=3,
            knowledge_base_mount_sync_status="degraded",
            knowledge_base_mount_error_code="WORKSPACE_KB_MOUNT_RECONCILE_FAILED",
            knowledge_base_mount_active_snapshot=[],
            knowledge_base_mount_failed_snapshot=[],
            runtime_access_revision=0,
            runtime_access_observed_revision=0,
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        failed_job = db_models.WorkspaceRuntimeJob(
            id=failed_job_id,
            workspace_id=workspace_id,
            operation="knowledge_base_mount_reconcile",
            strategy="docker",
            status="failed",
            retries=0,
            target_revision=4,
            target_runtime_instance_id=workspace.runtime_instance_id,
            correlation_id="failed-attempt",
            root_correlation_id="mutation-root",
            job_metadata={
                "attempt": 0,
                "mount_action": "apply_candidate",
                "mutation_action": "attach",
            },
            dispatch_attempts=0,
            scheduled_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            finished_at=datetime.utcnow(),
            error_code="WORKSPACE_KB_MOUNT_RECONCILE_FAILED",
        )
        session.add_all([workspace, failed_job])
        session.commit()
    return workspace_id, failed_job_id


def test_retry_failed_mount_creates_immutable_lineage_and_audit(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    actor = _valid_user(create_user, user_id="retry-owner")
    workspace_id, failed_job_id = _failed_workspace(
        session_factory,
        owner_id=actor.id,
    )
    _authenticate_as(client, monkeypatch, actor)
    correlation_id = "11111111-1111-4111-8111-111111111111"

    response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry",
        headers={"X-Correlation-ID": correlation_id},
    )

    assert response.status_code == 202
    assert response.json() == {
        "knowledgeBaseMountSync": {
            "status": "syncing",
            "desiredRevision": 5,
            "observedRevision": 3,
            "lastKnownGoodRevision": 3,
            "errorCode": None,
            "compensating": False,
        }
    }
    with session_factory() as session:
        failed_job = session.get(db_models.WorkspaceRuntimeJob, failed_job_id)
        retry_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_job_id
            )
        )
        audit = session.scalar(
            select(db_models.AuditEvent).where(
                db_models.AuditEvent.correlation_id == correlation_id
            )
        )
        assert failed_job.status == "failed"
        assert retry_job.status == "queued"
        assert retry_job.target_revision == 5
        assert retry_job.root_correlation_id == "mutation-root"
        assert retry_job.job_metadata["attempt"] == 1
        assert audit.event_type == "runtime.mount_sync_retry_requested"
        assert audit.root_correlation_id == "mutation-root"


def test_retry_failed_mount_is_idempotent_for_existing_retry_child(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    actor = _valid_user(create_user, user_id="retry-owner")
    workspace_id, failed_job_id = _failed_workspace(
        session_factory,
        owner_id=actor.id,
    )
    _authenticate_as(client, monkeypatch, actor)

    first = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry",
        headers={"X-Correlation-ID": "11111111-1111-4111-8111-111111111111"},
    )
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        workspace.knowledge_base_mount_sync_status = "degraded"
        workspace.knowledge_base_mount_error_code = (
            "WORKSPACE_KB_MOUNT_RECONCILE_FAILED"
        )
        session.commit()
    second = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry",
        headers={"X-Correlation-ID": "22222222-2222-4222-8222-222222222222"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    with session_factory() as session:
        retries = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_job_id
                )
            ).all()
        )
        assert len(retries) == 1


def test_retry_rejects_nonfailed_sync(
    test_app,
    create_user,
    monkeypatch,
) -> None:
    client, session_factory = test_app
    actor = _valid_user(
        create_user,
        user_id="read-only-owner",
        role="member",
    )
    workspace_id, _ = _failed_workspace(session_factory, owner_id=actor.id)
    _authenticate_as(client, monkeypatch, actor)

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        workspace.knowledge_base_mount_sync_status = "ready"
        workspace.knowledge_base_mount_observed_revision = 4
        session.commit()
    nonretryable = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry"
    )

    assert nonretryable.status_code == 409
    assert nonretryable.json()["detail"]["errorCode"] == (
        "WORKSPACE_KB_MOUNT_SYNC_NOT_RETRYABLE"
    )
