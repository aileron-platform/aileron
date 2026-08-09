"""Celery tasks owned by the Workspace module."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from celery import current_app

from app.config.settings import get_settings
from app.core.task_lease import task_lease
from app.db import models as db_models
from app.db.database import SessionLocal, engine
from app.modules.workspace.runtime.job_repository import (
    COMPONENT_OPERATIONS,
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
    WORKSPACE_ACCESS_RECYCLE,
    ExpiredJobRecoveryAction,
    WorkspaceRuntimeJobRepository,
)
from app.modules.audit.events import AuditEventService
from app.modules.knowledge_base.mount_reconcile import (
    KnowledgeBaseMountReconcileService,
)
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
)
from app.modules.workspace.browser_connectivity_reconcile import (
    BROWSER_CONNECTIVITY_RECONCILE_LEASE,
    DockerBrowserConnectivityReconcileService,
)
from app.modules.workspace.firewall_delivery import (
    WorkspaceFirewallDeliveryService,
)
from app.modules.workspace.kubernetes_status import (
    KUBERNETES_STATUS_RECONCILE_LEASE,
    WorkspaceKubernetesStatusReconcileService,
)

logger = logging.getLogger(__name__)

_RUNTIME_JOB_TASK = "workspace_runtime.reconcile_job"
_RECOVERY_ERROR_CODE = "WORKSPACE_RUNTIME_JOB_RETRIES_EXHAUSTED"


@current_app.task(name="workspace_firewall.reconcile_commands")
def reconcile_workspace_firewall_commands() -> dict[str, int]:
    """Deliver due firewall desired-state commands."""

    db = SessionLocal()
    try:
        return WorkspaceFirewallDeliveryService(db).reconcile_due()
    finally:
        db.close()


@current_app.task(name="workspace_kubernetes.reconcile_status")
def reconcile_kubernetes_workspace_status() -> dict[str, int]:
    """Persist Kubernetes Workspace status outside request transactions."""

    settings = get_settings()
    with task_lease(engine, KUBERNETES_STATUS_RECONCILE_LEASE) as acquired:
        if not acquired:
            return {
                "candidates": 0,
                "observed": 0,
                "skipped": 0,
                "not_found": 0,
                "failed": 0,
                "overlap_skipped": 1,
            }
        result = WorkspaceKubernetesStatusReconcileService().reconcile_batch(
            limit=settings.KUBERNETES_STATUS_RECONCILIATION_BATCH_SIZE,
        )
        result["overlap_skipped"] = 0
        return result


@current_app.task(name="workspace_browser_connectivity.reconcile")
def reconcile_docker_browser_connectivity() -> dict[str, int]:
    """Project Docker Browser connectivity evidence outside request transactions."""

    settings = get_settings()
    with task_lease(engine, BROWSER_CONNECTIVITY_RECONCILE_LEASE) as acquired:
        if not acquired:
            return {
                "candidates": 0,
                "reconciled": 0,
                "skipped": 0,
                "failed": 0,
                "overlap_skipped": 1,
            }
        result = DockerBrowserConnectivityReconcileService().reconcile_batch(
            limit=settings.TURN_BROWSER_CONNECTIVITY_RECONCILIATION_BATCH_SIZE,
        )
        result["overlap_skipped"] = 0
        return result


@current_app.task(name="workspace_browser_connectivity.reconcile_workspace")
def reconcile_docker_browser_connectivity_workspace(workspace_id: str) -> str:
    """Immediately reconcile one Docker Browser after its lifecycle commit."""

    return DockerBrowserConnectivityReconcileService().reconcile_workspace(workspace_id)


@current_app.task(
    name=_RUNTIME_JOB_TASK,
    acks_late=True,
    reject_on_worker_lost=True,
)
def reconcile_workspace_runtime_job(job_id: str) -> str:
    """Execute one durable job using only its database identifier."""

    db = SessionLocal()
    try:
        job = db.get(db_models.WorkspaceRuntimeJob, job_id)
        if job is None:
            return "not_found"
        operation = job.operation
        db.rollback()
        if operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
            return (
                KnowledgeBaseMountReconcileService(db).reconcile_mount_job(job_id).value
            )
        if operation == WORKSPACE_ACCESS_RECYCLE:
            from app.modules.workspace.access_recycle import (
                WorkspaceAccessRecycleService,
            )

            return WorkspaceAccessRecycleService(db).reconcile_job(job_id).value
        from app.modules.workspace.lifecycle import (
            WorkspaceLifecycleService,
        )

        return WorkspaceLifecycleService(db).run_durable_job(job_id).value
    finally:
        db.close()


@current_app.task(name="workspace_runtime.recover_and_dispatch_jobs")
def recover_and_dispatch_workspace_runtime_jobs() -> dict[str, int]:
    """Recover expired claims and republish every due durable intent."""

    settings = get_settings()
    now = datetime.now(timezone.utc)
    counts = {
        "revision_recovered": 0,
        "reclaimed": 0,
        "superseded": 0,
        "failed": 0,
        "dispatched": 0,
        "publish_failed": 0,
    }

    recovery_db = SessionLocal()
    try:
        expired_ids = [
            job.id
            for job in WorkspaceRuntimeJobRepository(
                recovery_db
            ).find_expired_running_jobs(now=now)
        ]
        recovery_db.rollback()
    finally:
        recovery_db.close()

    reclaimed_ids: list[str] = []
    for job_id in expired_ids:
        db = SessionLocal()
        try:
            job = db.get(db_models.WorkspaceRuntimeJob, job_id)
            if job is None:
                db.rollback()
                continue
            acquire_workspace_transaction_lock(db, job.workspace_id)
            result = WorkspaceRuntimeJobRepository(db).recover_expired_running_job(
                job_id=job_id,
                recovered_at=now,
                replacement_claim_token=str(uuid4()),
                replacement_claim_expires_at=now
                + timedelta(seconds=settings.RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS),
                max_retries=settings.RUNTIME_MAX_RETRIES,
                exhausted_error_code=_RECOVERY_ERROR_CODE,
            )
            if result.action == ExpiredJobRecoveryAction.RECLAIMED:
                counts["reclaimed"] += 1
                reclaimed_ids.append(job_id)
            elif result.action == ExpiredJobRecoveryAction.SUPERSEDED:
                counts["superseded"] += 1
                _record_recovery_terminal_audit(
                    db,
                    result.job,
                    event_suffix="superseded",
                    result="success",
                    error_code=None,
                    reason="newer_intent_queued",
                )
            elif result.action == ExpiredJobRecoveryAction.FAILED:
                counts["failed"] += 1
                _apply_recovery_failure(db, result.job)
            db.commit()
        except Exception:
            db.rollback()
            logger.error(
                "Workspace runtime job recovery transaction failed",
                extra={"job_id": job_id},
            )
        finally:
            db.close()

    try:
        WorkspaceKubernetesStatusReconcileService(
            session_factory=SessionLocal,
        ).reconcile_batch(
            limit=settings.KUBERNETES_STATUS_RECONCILIATION_BATCH_SIZE,
        )
    except Exception:
        logger.exception(
            "Kubernetes Workspace orphan reconciliation sweep failed",
        )

    lifecycle_db = SessionLocal()
    try:
        from app.modules.workspace.lifecycle import (
            WorkspaceLifecycleService,
        )

        lifecycle_service = WorkspaceLifecycleService(lifecycle_db)
        counts["revision_recovered"] = lifecycle_service.recover_missing_revision_jobs()
    finally:
        lifecycle_db.close()

    dispatch_db = SessionLocal()
    try:
        queued_snapshots: list[tuple[str, int]] = []
        for job in WorkspaceRuntimeJobRepository(
            dispatch_db
        ).find_dispatchable_queued_jobs(now=now):
            workspace = dispatch_db.get(db_models.Workspace, job.workspace_id)
            if workspace is not None and _is_dispatch_eligible(job, workspace):
                queued_snapshots.append((job.id, job.dispatch_attempts))
        dispatch_db.rollback()
    finally:
        dispatch_db.close()

    for job_id, dispatch_attempts in [
        *((job_id, -1) for job_id in reclaimed_ids),
        *queued_snapshots,
    ]:
        try:
            current_app.send_task(_RUNTIME_JOB_TASK, args=[job_id])
            counts["dispatched"] += 1
        except Exception:
            counts["publish_failed"] += 1
            logger.error(
                "Workspace runtime job broker publish failed",
                extra={"job_id": job_id},
            )
            if dispatch_attempts < 0:
                continue
            db = SessionLocal()
            try:
                WorkspaceRuntimeJobRepository(db).record_dispatch_failure(
                    job_id=job_id,
                    expected_dispatch_attempts=dispatch_attempts,
                    failed_at=now,
                    base_delay_seconds=(
                        settings.RUNTIME_JOB_DISPATCH_BASE_DELAY_SECONDS
                    ),
                    max_delay_seconds=(settings.RUNTIME_JOB_DISPATCH_MAX_DELAY_SECONDS),
                )
                db.commit()
            except Exception:
                db.rollback()
                logger.error(
                    "Workspace runtime job dispatch backoff failed",
                    extra={"job_id": job_id},
                )
            finally:
                db.close()
    return counts


def _is_dispatch_eligible(
    job: db_models.WorkspaceRuntimeJob,
    workspace: db_models.Workspace,
) -> bool:
    if job.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
        return workspace.runtime_status == "running" or bool(
            workspace.runtime_status == "stopped"
            and job.job_metadata.get("offline_promotion", False)
        )
    if job.operation == WORKSPACE_ACCESS_RECYCLE:
        return workspace.runtime_status == "running"
    lifecycle_statuses = {
        "workspace_start": {"starting"},
        "workspace_stop": {"stopping"},
        "workspace_delete": {"deleting"},
    }
    if job.operation in COMPONENT_OPERATIONS and job.target_component is not None:
        component_status = getattr(
            workspace,
            f"{job.target_component}_status",
        )
        return component_status in {"running", "restarting"}
    return workspace.runtime_status in lifecycle_statuses.get(job.operation, set())


def _apply_recovery_failure(
    db,
    job: db_models.WorkspaceRuntimeJob | None,
) -> None:
    if job is None:
        return
    workspace = db.get(db_models.Workspace, job.workspace_id)
    if workspace is not None:
        if job.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
            KnowledgeBaseMountReconcileService(db).stage_terminal_recovery(
                workspace=workspace,
                failed_job=job,
                error_code=_RECOVERY_ERROR_CODE,
                now=datetime.now(timezone.utc),
            )
        elif job.operation in {
            WORKSPACE_ACCESS_RECYCLE,
            "workspace_start",
            "workspace_stop",
        }:
            workspace.runtime_status = "error"
        elif job.operation in COMPONENT_OPERATIONS and job.target_component is not None:
            setattr(workspace, f"{job.target_component}_status", "error")
    _record_recovery_terminal_audit(
        db,
        job,
        event_suffix="failed",
        result="failure",
        error_code=_RECOVERY_ERROR_CODE,
        reason="claim_retries_exhausted",
    )


def _record_recovery_terminal_audit(
    db,
    job: db_models.WorkspaceRuntimeJob | None,
    *,
    event_suffix: str,
    result: str,
    error_code: str | None,
    reason: str,
) -> None:
    if job is None:
        return
    event_prefix = {
        KNOWLEDGE_BASE_MOUNT_RECONCILE: "runtime.mount_sync",
        WORKSPACE_ACCESS_RECYCLE: "runtime.access_recycle",
    }.get(job.operation, "workspace.lifecycle")
    AuditEventService(db).record(
        event_type=f"{event_prefix}_{event_suffix}",
        actor_type="service",
        actor_id="workspace-runtime-recovery",
        actor_user_id=None,
        target_type="workspace",
        target_id=job.workspace_id,
        action=f"recover_{job.operation}",
        result=result,
        error_code=error_code,
        correlation_id=job.correlation_id,
        root_correlation_id=job.root_correlation_id,
        metadata={
            "workspace_id": job.workspace_id,
            "target_revision": job.target_revision or 0,
            "attempt": job.retries,
            "reason": reason,
        },
    )


__all__ = [
    "reconcile_workspace_firewall_commands",
    "reconcile_kubernetes_workspace_status",
    "reconcile_workspace_runtime_job",
    "recover_and_dispatch_workspace_runtime_jobs",
]
