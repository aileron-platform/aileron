"""Durable knowledge base mount reconcile orchestration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, NoReturn, cast
from uuid import uuid4

import httpx
from celery import current_app
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db import models as db_models
from app.modules.workspace.runtime.job_repository import (
    KNOWLEDGE_BASE_MOUNT_RECONCILE,
    WORKSPACE_PROVISIONER_MISMATCH,
    RetryJobResult,
    WorkspaceRuntimeJobRepository,
)
from app.modules.audit.events import AuditEventService
from app.modules.knowledge_base.mount_snapshot import canonical_mount_snapshot
from app.modules.knowledge_base.access import KnowledgeBaseConflictError
from app.modules.workspace.orchestrator.models import RuntimeInfo
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.workspace.runtime.assertions import RuntimeAssertionService
from app.modules.workspace.runtime.provisioning import (
    RuntimeProvisionService,
    WorkspaceExecutionPlaneIdentity,
)
from app.modules.workspace.advisory_lock import (
    WorkspaceAdvisoryLockLostError,
    WorkspaceAdvisoryLockUnavailableError,
    acquire_workspace_transaction_lock,
    workspace_session_advisory_lock,
)
from app.modules.workspace.custom_resources import (
    WorkspaceCustomResourceExecutionIdentity,
    WorkspaceCustomResourceService,
)
from app.modules.workspace.execution_plane import (
    ExecutionPlanePlan,
    WorkspaceExecutionPlaneService,
)
from app.modules.workspace.runtime.job_execution import (
    RuntimeJobClaimLease,
    RuntimeJobClaimLostError,
    WorkspaceRuntimeJobRunResult,
    normalize_utc,
)
from app.modules.workspace.catalog import (
    WorkspaceNotFoundError,
)

logger = logging.getLogger(__name__)

_STABLE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_SERVICE_ACTOR_ID = "workspace-runtime-reconciler"
_RUNTIME_JOB_TASK = "workspace_runtime.reconcile_job"


@dataclass(frozen=True)
class _ClaimedMountWork:
    job_id: str
    workspace_id: str
    claim_token: str
    target_revision: int
    correlation_id: str
    root_correlation_id: str
    attempt: int
    mount_action: str
    offline_promotion: bool
    target_runtime_revision: int | None
    workspace_identity: WorkspaceExecutionPlaneIdentity
    custom_resource_identity: WorkspaceCustomResourceExecutionIdentity | None
    plan: ExecutionPlanePlan | None


class KnowledgeBaseMountReconcileService(WorkspaceExecutionPlaneService):
    """Own durable mount retry, claim, side effects, and terminal transactions."""

    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        runtime_provision: RuntimeProvisionService | None = None,
        custom_resource_service: WorkspaceCustomResourceService | None = None,
        assertion_service_factory: Callable[[], RuntimeAssertionService] | None = None,
        http_client_factory: Callable[..., httpx.Client] | None = None,
    ) -> None:
        super().__init__(
            db,
            settings=settings,
            runtime_provision=runtime_provision,
            custom_resource_service=custom_resource_service,
            assertion_service_factory=assertion_service_factory,
            http_client_factory=http_client_factory,
        )
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.audit_events = AuditEventService(db)
        self.authorization = AuthorizationOperationPolicy(db)

    def reconcile_mount_job(self, job_id: str) -> WorkspaceRuntimeJobRunResult:
        """Claim and reconcile one mount intent with session and lease fencing."""

        job = self.db.get(db_models.WorkspaceRuntimeJob, job_id)
        if job is None or job.operation != KNOWLEDGE_BASE_MOUNT_RECONCILE:
            self.db.rollback()
            return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
        workspace_id = job.workspace_id
        self.db.rollback()

        claimed_work: _ClaimedMountWork | None = None
        try:
            bind = cast(Engine, self.db.get_bind())
            with workspace_session_advisory_lock(bind, workspace_id) as session_lock:
                claimed_work, terminal_result = self._claim_and_prepare(job_id)
                if terminal_result is not None:
                    return terminal_result
                if claimed_work is None:
                    return WorkspaceRuntimeJobRunResult.NOT_CLAIMED

                heartbeat = RuntimeJobClaimLease(
                    bind=bind,
                    job_id=claimed_work.job_id,
                    claim_token=claimed_work.claim_token,
                    timeout_seconds=(self.settings.RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS),
                )

                def assert_claim() -> None:
                    heartbeat.assert_valid(session_lock)

                runtime_result: RuntimeInfo | None = None
                with heartbeat:
                    if claimed_work.offline_promotion:
                        assert_claim()
                        self._prove_execution_plane_absent(
                            claimed_work.workspace_identity,
                            claimed_work.custom_resource_identity,
                            assert_claim=assert_claim,
                        )
                    else:
                        if claimed_work.plan is None:
                            raise RuntimeError(
                                "Claimed mount work has no execution plan"
                            )
                        self.best_effort_drain(
                            workspace_id=claimed_work.workspace_id,
                            workspace_identity=claimed_work.workspace_identity,
                            expected_mounted_revision=(
                                claimed_work.plan.observed_mount_revision
                            ),
                            target_mounted_revision=(claimed_work.plan.mount_revision),
                            job_id=claimed_work.job_id,
                            assert_claim=assert_claim,
                        )
                        assert_claim()
                        if claimed_work.target_runtime_revision is None:
                            raise RuntimeError(
                                "Claimed mount work has no Runtime revision"
                            )
                        runtime_result = self._apply_runtime_component(
                            workspace_id=claimed_work.workspace_id,
                            target_revision=claimed_work.target_runtime_revision,
                            plan=claimed_work.plan,
                            assert_claim=assert_claim,
                        )
                        assert_claim()

                    if not self._target_is_current(claimed_work):
                        return self._complete_superseded(claimed_work)
                    return self._complete_success(
                        claimed_work,
                        runtime_result=runtime_result,
                    )
        except WorkspaceAdvisoryLockUnavailableError:
            self.db.rollback()
            return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
        except (RuntimeJobClaimLostError, WorkspaceAdvisoryLockLostError):
            self.db.rollback()
            return WorkspaceRuntimeJobRunResult.CLAIM_LOST
        except Exception as exc:
            self.db.rollback()
            logger.error(
                "Workspace mount reconcile failed",
                extra={
                    "job_id": job_id,
                    "workspace_id": workspace_id,
                    "error_code": self._stable_error_code(exc),
                },
            )
            if claimed_work is None:
                return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            return self._complete_failure(claimed_work, exc)

    def _claim_and_prepare(
        self,
        job_id: str,
    ) -> tuple[
        _ClaimedMountWork | None,
        WorkspaceRuntimeJobRunResult | None,
    ]:
        now = datetime.now(timezone.utc)
        try:
            job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                job is None
                or job.operation != KNOWLEDGE_BASE_MOUNT_RECONCILE
                or job.status not in {"queued", "running"}
            ):
                self.db.rollback()
                return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            acquire_workspace_transaction_lock(self.db, job.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == job.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            if workspace.provisioner != job.strategy:
                return self._fail_mount_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code=WORKSPACE_PROVISIONER_MISMATCH,
                )
            if job.target_revision != workspace.knowledge_base_mount_desired_revision:
                transitioned = (
                    self.jobs.supersede_queued_job(
                        job_id=job.id,
                        finished_at=now,
                    )
                    if job.status == "queued"
                    else self.jobs.supersede_running_job(
                        job_id=job.id,
                        claim_token=job.claim_token or "",
                        finished_at=now,
                    )
                )
                if not transitioned:
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                self._record_mount_audit(
                    workspace=workspace,
                    job=job,
                    event_type="runtime.mount_sync_superseded",
                    action="supersede_mount_sync",
                    result="success",
                    error_code=None,
                    reason="desired_revision_advanced",
                )
                self.db.commit()
                return None, WorkspaceRuntimeJobRunResult.SUPERSEDED

            mount_action = job.job_metadata.get("mount_action")
            if mount_action not in {"apply_candidate", "compensate"}:
                return self._fail_mount_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code="WORKSPACE_KB_MOUNT_JOB_INVALID",
                )
            expected_sync_statuses = (
                {"compensating"}
                if mount_action == "compensate"
                else {"preflighting", "applying"}
            )
            try:
                canonical_mount_snapshot(
                    workspace.knowledge_base_mount_candidate_snapshot
                )
            except ValueError:
                return self._fail_mount_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code="WORKSPACE_KB_MOUNT_SNAPSHOT_INVALID",
                )
            if workspace.knowledge_base_mount_sync_status not in expected_sync_statuses:
                return self._fail_mount_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code="WORKSPACE_KB_MOUNT_STATE_INVALID",
                )
            offline_promotion = job.job_metadata.get("offline_promotion", False)
            eligible_statuses: set[str]
            if offline_promotion:
                if (
                    workspace.runtime_status != "stopped"
                    or workspace.runtime_instance_id is not None
                    or any(
                        (
                            workspace.runtime_container_id,
                            workspace.browser_container_id,
                            workspace.canvas_container_id,
                        )
                    )
                ):
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                eligible_statuses = {"stopped"}
            else:
                if workspace.runtime_status != "running":
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                eligible_statuses = {"running"}

            if (
                not offline_promotion
                and job.status == "queued"
                and job.target_runtime_instance_id != workspace.runtime_instance_id
            ):
                replacement = self.jobs.supersede_stale_queued_and_enqueue_replacement(
                    job_id=job.id,
                    target_runtime_instance_id=workspace.runtime_instance_id,
                    correlation_id=str(uuid4()),
                    scheduled_at=now,
                )
                if replacement is None:
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                stale_job, _replacement_job = replacement
                self._record_mount_audit(
                    workspace=workspace,
                    job=stale_job,
                    event_type="runtime.mount_sync_superseded",
                    action="supersede_mount_sync",
                    result="success",
                    error_code=None,
                    reason="runtime_instance_advanced",
                )
                self.db.commit()
                return None, WorkspaceRuntimeJobRunResult.SUPERSEDED

            if job.status == "queued":
                claim_token = str(uuid4())
                claimed_job = self.jobs.claim_queued_job(
                    job_id=job.id,
                    claim_token=claim_token,
                    claimed_at=now,
                    claim_expires_at=now
                    + timedelta(
                        seconds=self.settings.RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS
                    ),
                    eligible_runtime_statuses=eligible_statuses,
                )
                if claimed_job is None:
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            else:
                claim_token = job.claim_token or ""
                if (
                    not claim_token
                    or job.claim_expires_at is None
                    or normalize_utc(job.claim_expires_at) <= now
                ):
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                claimed_job = job

            attempt = int(claimed_job.job_metadata.get("attempt", 0)) + int(
                claimed_job.retries
            )
            workspace_identity = self._execution_plane_identity(workspace)
            custom_resource_identity = (
                self._custom_resource_execution_identity(workspace)
                if workspace.provisioner == "kubernetes"
                else None
            )
            plan: ExecutionPlanePlan | None = None
            target_runtime_revision: int | None = None
            try:
                self.runtime_provision.preflight_knowledge_base_mounts(workspace)
                if workspace.provisioner == "kubernetes":
                    self.custom_resources.preflight_knowledge_base_mounts(workspace)
            except Exception as exc:
                return self._fail_mount_before_side_effect(
                    workspace=workspace,
                    job=claimed_job,
                    now=now,
                    error_code=self._stable_error_code(exc),
                )
            if not offline_promotion:
                if (
                    claimed_job.target_runtime_instance_id
                    != workspace.runtime_instance_id
                ):
                    if not self.jobs.supersede_running_job(
                        job_id=claimed_job.id,
                        claim_token=claim_token,
                        finished_at=now,
                    ):
                        self.db.rollback()
                        return None, WorkspaceRuntimeJobRunResult.CLAIM_LOST
                    self._record_mount_audit(
                        workspace=workspace,
                        job=claimed_job,
                        event_type="runtime.mount_sync_superseded",
                        action="supersede_mount_sync",
                        result="success",
                        error_code=None,
                        reason="runtime_instance_advanced",
                    )
                    self.db.commit()
                    return None, WorkspaceRuntimeJobRunResult.SUPERSEDED
                if (
                    workspace.runtime_desired_revision
                    != workspace.runtime_observed_revision
                    and mount_action != "compensate"
                ):
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                workspace.runtime_desired_revision += 1
                target_runtime_revision = workspace.runtime_desired_revision
                try:
                    plan = self._prepare_execution_plane(workspace)
                except Exception as exc:
                    return self._fail_mount_before_side_effect(
                        workspace=workspace,
                        job=claimed_job,
                        now=now,
                        error_code=self._stable_error_code(exc),
                    )

            if mount_action == "apply_candidate":
                workspace.knowledge_base_mount_sync_status = "applying"

            self._record_mount_audit(
                workspace=workspace,
                job=claimed_job,
                event_type="runtime.mount_sync_started",
                action="start_mount_sync",
                result="success",
                error_code=None,
                attempt=attempt,
            )
            claimed_work = _ClaimedMountWork(
                job_id=claimed_job.id,
                workspace_id=workspace.id,
                claim_token=claim_token,
                target_revision=claimed_job.target_revision or 0,
                correlation_id=claimed_job.correlation_id,
                root_correlation_id=claimed_job.root_correlation_id,
                attempt=attempt,
                mount_action=mount_action,
                offline_promotion=offline_promotion,
                target_runtime_revision=target_runtime_revision,
                workspace_identity=workspace_identity,
                custom_resource_identity=custom_resource_identity,
                plan=plan,
            )
            self.db.commit()
            return claimed_work, None
        except Exception:
            self.db.rollback()
            raise

    def _fail_mount_before_side_effect(
        self,
        *,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        now: datetime,
        error_code: str,
    ) -> tuple[None, WorkspaceRuntimeJobRunResult]:
        if job.status == "queued":
            transitioned = self.jobs.fail_queued_job(
                job_id=job.id,
                finished_at=now,
                error_code=error_code,
            )
            lost_result = WorkspaceRuntimeJobRunResult.NOT_CLAIMED
        else:
            transitioned = bool(job.claim_token) and self.jobs.fail_running_job(
                job_id=job.id,
                claim_token=job.claim_token or "",
                finished_at=now,
                error_code=error_code,
            )
            lost_result = WorkspaceRuntimeJobRunResult.CLAIM_LOST
        if not transitioned:
            self.db.rollback()
            return None, lost_result
        compensation_job = self._stage_failure_outcome(
            workspace=workspace,
            failed_job=job,
            error_code=error_code,
            now=now,
        )
        self._record_mount_audit(
            workspace=workspace,
            job=job,
            event_type="runtime.mount_sync_failed",
            action="fail_mount_sync",
            result=(
                "compensation_required" if compensation_job is not None else "failure"
            ),
            error_code=error_code,
            attempt=int(job.job_metadata.get("attempt", 0)) + int(job.retries),
        )
        self.db.commit()
        if compensation_job is not None:
            self._publish_after_commit(compensation_job.id)
        return None, WorkspaceRuntimeJobRunResult.FAILED

    def _target_is_current(self, work: _ClaimedMountWork) -> bool:
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.id == work.job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            current = bool(
                job is not None
                and workspace is not None
                and job.status == "running"
                and job.claim_token == work.claim_token
                and workspace.knowledge_base_mount_desired_revision
                == work.target_revision
                and (
                    work.target_runtime_revision is None
                    or workspace.runtime_desired_revision
                    == work.target_runtime_revision
                )
            )
            self.db.rollback()
            return current
        except Exception:
            self.db.rollback()
            raise

    def _complete_success(
        self,
        work: _ClaimedMountWork,
        *,
        runtime_result: RuntimeInfo | None,
    ) -> WorkspaceRuntimeJobRunResult:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                workspace is None
                or workspace.knowledge_base_mount_desired_revision
                != work.target_revision
                or (
                    work.target_runtime_revision is not None
                    and workspace.runtime_desired_revision
                    != work.target_runtime_revision
                )
            ):
                self.db.rollback()
                raise RuntimeJobClaimLostError("Mount target changed before completion")
            if work.target_runtime_revision is not None:
                self._apply_runtime_component_result(
                    workspace,
                    work.plan,
                    runtime_result,
                )
                workspace.runtime_observed_revision = work.target_runtime_revision
                workspace.runtime_status = "running"
                workspace.runtime_reason = None
                workspace.runtime_error_code = None
                workspace.runtime_last_transition_at = now
            self._promote_candidate(
                workspace=workspace,
                work=work,
            )

            job = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
            if job is None or not self.jobs.complete_running_job(
                job_id=work.job_id,
                claim_token=work.claim_token,
                finished_at=now,
            ):
                self.db.rollback()
                raise RuntimeJobClaimLostError(
                    "Mount job claim was lost before completion"
                )
            self._record_mount_audit(
                workspace=workspace,
                job=job,
                event_type=(
                    "runtime.mount_compensation_succeeded"
                    if work.mount_action == "compensate"
                    else "runtime.mount_sync_ready"
                ),
                action=(
                    "complete_mount_compensation"
                    if work.mount_action == "compensate"
                    else "complete_mount_sync"
                ),
                result="success",
                error_code=None,
                attempt=work.attempt,
                new_runtime_instance_id=(
                    workspace.runtime_instance_id
                    if work.target_runtime_revision is not None
                    else None
                ),
            )
            self.db.commit()
            return WorkspaceRuntimeJobRunResult.SUCCEEDED
        except Exception:
            self.db.rollback()
            raise

    def _complete_superseded(
        self,
        work: _ClaimedMountWork,
    ) -> WorkspaceRuntimeJobRunResult:
        now = datetime.now(timezone.utc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            replacement = self.jobs.supersede_running_and_preserve_successor(
                job_id=work.job_id,
                claim_token=work.claim_token,
                target_revision=workspace.knowledge_base_mount_desired_revision,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id=str(uuid4()),
                scheduled_at=now,
            )
            if replacement is None:
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            job, _successor, _created = replacement
            self._record_mount_audit(
                workspace=workspace,
                job=job,
                event_type="runtime.mount_sync_superseded",
                action="supersede_mount_sync",
                result="success",
                error_code=None,
                reason="desired_revision_advanced",
                attempt=work.attempt,
            )
            self.db.commit()
            return WorkspaceRuntimeJobRunResult.SUPERSEDED
        except Exception:
            self.db.rollback()
            raise

    def _complete_failure(
        self,
        work: _ClaimedMountWork,
        exc: Exception,
    ) -> WorkspaceRuntimeJobRunResult:
        now = datetime.now(timezone.utc)
        error_code = self._stable_error_code(exc)
        try:
            acquire_workspace_transaction_lock(self.db, work.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == work.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            job = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
            if workspace is None or job is None:
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            if workspace.knowledge_base_mount_desired_revision != work.target_revision:
                self.db.rollback()
                return self._complete_superseded(work)
            if not self.jobs.fail_running_job(
                job_id=work.job_id,
                claim_token=work.claim_token,
                finished_at=now,
                error_code=error_code,
            ):
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            compensation_job = self._stage_failure_outcome(
                workspace=workspace,
                failed_job=job,
                error_code=error_code,
                now=now,
                mount_action=work.mount_action,
                offline_promotion=work.offline_promotion,
            )
            if work.plan is not None and compensation_job is None:
                workspace.runtime_status = "error"
                workspace.runtime_reason = "MountReconcileFailed"
                workspace.runtime_error_code = error_code
                workspace.runtime_last_transition_at = now
            self._record_mount_audit(
                workspace=workspace,
                job=job,
                event_type="runtime.mount_sync_failed",
                action="fail_mount_sync",
                result=(
                    "compensation_required"
                    if compensation_job is not None
                    else "failure"
                ),
                error_code=error_code,
                attempt=work.attempt,
            )
            self.db.commit()
            if compensation_job is not None:
                self._publish_after_commit(compensation_job.id)
            return WorkspaceRuntimeJobRunResult.FAILED
        except Exception:
            self.db.rollback()
            raise

    def _promote_candidate(
        self,
        *,
        workspace: db_models.Workspace,
        work: _ClaimedMountWork,
    ) -> None:
        candidate = canonical_mount_snapshot(
            workspace.knowledge_base_mount_candidate_snapshot
        )
        self._replace_active_attachments(
            workspace=workspace,
            candidate=candidate,
            work=work,
        )
        workspace.knowledge_base_mount_active_snapshot = candidate
        workspace.knowledge_base_mount_active_revision = work.target_revision
        workspace.knowledge_base_mount_observed_revision = work.target_revision
        workspace.knowledge_base_mount_candidate_snapshot = None
        if work.mount_action == "compensate":
            workspace.knowledge_base_mount_sync_status = "degraded"
        else:
            workspace.knowledge_base_mount_sync_status = "ready"
            workspace.knowledge_base_mount_error_code = None
            workspace.knowledge_base_mount_failed_snapshot = None

    def _replace_active_attachments(
        self,
        *,
        workspace: db_models.Workspace,
        candidate: list[dict[str, object]],
        work: _ClaimedMountWork,
    ) -> None:
        current = list(
            self.db.scalars(
                select(db_models.WorkspaceKnowledgeBaseAttachment)
                .where(
                    db_models.WorkspaceKnowledgeBaseAttachment.workspace_id
                    == workspace.id
                )
                .order_by(db_models.WorkspaceKnowledgeBaseAttachment.id)
                .with_for_update()
            ).all()
        )
        current_by_id = {attachment.id: attachment for attachment in current}
        candidate_ids = {str(entry["attachmentId"]) for entry in candidate}

        for attachment in current:
            attachment.mount_alias = f"pending-{attachment.id}"
        if current:
            self.db.flush()

        for attachment in current:
            if attachment.id in candidate_ids:
                continue
            self.audit_events.record(
                event_type="workspace.knowledge_base_detached",
                actor_type="service",
                actor_id=_SERVICE_ACTOR_ID,
                actor_user_id=None,
                target_type="workspace",
                target_id=workspace.id,
                action="detach_knowledge_base",
                result="success",
                error_code=None,
                correlation_id=work.correlation_id,
                root_correlation_id=work.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "kb_id": attachment.kb_id,
                    "target_revision": work.target_revision,
                },
            )
            self.db.delete(attachment)

        for entry in candidate:
            attachment_id = str(entry["attachmentId"])
            attachment = current_by_id.get(attachment_id)
            if attachment is None:
                attachment = db_models.WorkspaceKnowledgeBaseAttachment(
                    id=attachment_id,
                    workspace_id=workspace.id,
                    kb_id=str(entry["knowledgeBaseId"]),
                    mount_alias=str(entry["mountAlias"]),
                    attached_by_id=(
                        str(entry["attachedById"])
                        if entry.get("attachedById") is not None
                        else None
                    ),
                )
                self.db.add(attachment)
                continue
            attachment.kb_id = str(entry["knowledgeBaseId"])
            attachment.mount_alias = str(entry["mountAlias"])
            attachment.attached_by_id = (
                str(entry["attachedById"])
                if entry.get("attachedById") is not None
                else None
            )

    def _stage_failure_outcome(
        self,
        *,
        workspace: db_models.Workspace,
        failed_job: db_models.WorkspaceRuntimeJob,
        error_code: str,
        now: datetime,
        mount_action: str | None = None,
        offline_promotion: bool | None = None,
    ) -> db_models.WorkspaceRuntimeJob | None:
        action = mount_action or str(failed_job.job_metadata.get("mount_action", ""))
        offline = (
            offline_promotion
            if offline_promotion is not None
            else bool(failed_job.job_metadata.get("offline_promotion", False))
        )
        workspace.knowledge_base_mount_error_code = error_code
        if action != "apply_candidate":
            workspace.knowledge_base_mount_candidate_snapshot = None
            workspace.knowledge_base_mount_sync_status = "degraded"
            return None

        try:
            failed_snapshot = canonical_mount_snapshot(
                workspace.knowledge_base_mount_candidate_snapshot
            )
        except ValueError:
            workspace.knowledge_base_mount_candidate_snapshot = None
            workspace.knowledge_base_mount_sync_status = "degraded"
            return None
        workspace.knowledge_base_mount_failed_snapshot = failed_snapshot
        if offline:
            workspace.knowledge_base_mount_candidate_snapshot = None
            workspace.knowledge_base_mount_observed_revision = (
                workspace.knowledge_base_mount_active_revision
            )
            workspace.knowledge_base_mount_sync_status = "degraded"
            return None

        workspace.knowledge_base_mount_desired_revision += 1
        workspace.knowledge_base_mount_candidate_snapshot = canonical_mount_snapshot(
            workspace.knowledge_base_mount_active_snapshot
        )
        workspace.knowledge_base_mount_sync_status = "compensating"
        compensation_job, _ = self.jobs.supersede_queued_and_enqueue_mount_reconcile(
            workspace=workspace,
            correlation_id=str(uuid4()),
            root_correlation_id=failed_job.root_correlation_id,
            retry_of_job_id=failed_job.id,
            scheduled_at=now,
            job_metadata={
                "mount_action": "compensate",
                "mutation_action": "compensate",
            },
        )
        return compensation_job

    def stage_terminal_recovery(
        self,
        *,
        workspace: db_models.Workspace,
        failed_job: db_models.WorkspaceRuntimeJob,
        error_code: str,
        now: datetime,
        offline_promotion: bool | None = None,
    ) -> db_models.WorkspaceRuntimeJob | None:
        """Persist the canonical failure outcome for a terminal mount claim."""

        return self._stage_failure_outcome(
            workspace=workspace,
            failed_job=failed_job,
            error_code=error_code,
            now=now,
            offline_promotion=offline_promotion,
        )

    @staticmethod
    def _publish_after_commit(job_id: str) -> None:
        try:
            current_app.send_task(_RUNTIME_JOB_TASK, args=[job_id])
        except Exception:
            logger.warning(
                "Workspace mount job publish failed; recovery will retry",
                extra={"job_id": job_id},
            )

    def _record_mount_audit(
        self,
        *,
        workspace: db_models.Workspace,
        job: db_models.WorkspaceRuntimeJob,
        event_type: str,
        action: str,
        result: str,
        error_code: str | None,
        reason: str | None = None,
        attempt: int | None = None,
        new_runtime_instance_id: str | None = None,
    ) -> None:
        metadata: dict[str, object] = {
            "workspace_id": workspace.id,
            "target_revision": job.target_revision or 0,
            "desired_mount_revision": workspace.knowledge_base_mount_desired_revision,
            "observed_mount_revision": (
                workspace.knowledge_base_mount_observed_revision
            ),
        }
        if reason is not None:
            metadata["reason"] = reason
        if attempt is not None:
            metadata["attempt"] = attempt
        if new_runtime_instance_id is not None:
            metadata["new_runtime_instance_id"] = new_runtime_instance_id
        self.audit_events.record(
            event_type=event_type,
            actor_type="service",
            actor_id=_SERVICE_ACTOR_ID,
            actor_user_id=None,
            target_type="workspace",
            target_id=workspace.id,
            action=action,
            result=result,
            error_code=error_code,
            correlation_id=job.correlation_id,
            root_correlation_id=job.root_correlation_id,
            metadata=metadata,
        )

    @staticmethod
    def _stable_error_code(exc: Exception) -> str:
        candidate = getattr(exc, "code", None)
        if isinstance(candidate, str) and _STABLE_ERROR_CODE.fullmatch(candidate):
            return candidate
        return "WORKSPACE_KB_MOUNT_RECONCILE_FAILED"

    def retry_failed_mount(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        correlation_id: str,
    ) -> tuple[db_models.Workspace, RetryJobResult]:
        """Create an immutable retry child without reopening a failed row."""

        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_ATTACHMENT_WRITE,
            )
            probe = self.db.get(db_models.Workspace, workspace_id)
            if probe is None:
                raise WorkspaceNotFoundError(
                    "Workspace does not exist",
                    code="WORKSPACE_NOT_FOUND",
                )
            provisioner = probe.provisioner
            self.db.rollback()
            if provisioner == "kubernetes":
                snapshot = self.custom_resources.fetch_workspace_status_snapshot(
                    workspace_id
                )
                if snapshot is not None:
                    self.custom_resources.apply_workspace_status_snapshot(snapshot)
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
            )
            if workspace is None:
                raise WorkspaceNotFoundError(
                    "Workspace does not exist",
                    code="WORKSPACE_NOT_FOUND",
                )
            if (
                workspace.runtime_status in {"stopping", "deleting"}
                or workspace.knowledge_base_mount_sync_status != "degraded"
                or workspace.knowledge_base_mount_failed_snapshot is None
            ):
                self._raise_not_retryable()

            failed_job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation
                    == KNOWLEDGE_BASE_MOUNT_RECONCILE,
                    db_models.WorkspaceRuntimeJob.status == "failed",
                    db_models.WorkspaceRuntimeJob.job_metadata[
                        "mount_action"
                    ].as_string()
                    == "apply_candidate",
                )
                .order_by(
                    db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                    db_models.WorkspaceRuntimeJob.id.desc(),
                )
                .limit(1)
                .with_for_update()
            )
            if failed_job is None:
                self._raise_not_retryable()

            existing_retry = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_job.id,
                    db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
                )
                .order_by(
                    db_models.WorkspaceRuntimeJob.scheduled_at,
                    db_models.WorkspaceRuntimeJob.id,
                )
                .limit(1)
                .with_for_update()
            )
            if existing_retry is not None:
                retry_result = RetryJobResult(
                    job=existing_retry,
                    created=False,
                )
            else:
                previous_attempt = failed_job.job_metadata.get("attempt", 0)
                if type(previous_attempt) is not int or previous_attempt < 0:
                    self._raise_not_retryable()
                workspace.knowledge_base_mount_desired_revision += 1
                workspace.knowledge_base_mount_candidate_snapshot = (
                    canonical_mount_snapshot(
                        workspace.knowledge_base_mount_failed_snapshot
                    )
                )
                workspace.knowledge_base_mount_sync_status = "preflighting"
                workspace.knowledge_base_mount_error_code = None
                retry_job, _ = self.jobs.supersede_queued_and_enqueue_mount_reconcile(
                    workspace=workspace,
                    correlation_id=correlation_id,
                    root_correlation_id=failed_job.root_correlation_id,
                    retry_of_job_id=failed_job.id,
                    scheduled_at=datetime.now(timezone.utc),
                    job_metadata={
                        "attempt": previous_attempt + 1,
                        "mount_action": "apply_candidate",
                        "mutation_action": "retry",
                    },
                )
                retry_result = RetryJobResult(job=retry_job, created=True)
            self.audit_events.record(
                event_type="runtime.mount_sync_retry_requested",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type="workspace",
                target_id=workspace.id,
                action="retry_mount_sync",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=retry_result.job.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "target_revision": retry_result.job.target_revision or 0,
                    "retry_attempt": retry_result.job.job_metadata.get("attempt", 0),
                },
            )
            self.db.commit()
            if retry_result.created:
                self._publish_after_commit(retry_result.job.id)
            self.db.refresh(workspace)
            return workspace, retry_result
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _raise_not_retryable() -> NoReturn:
        raise KnowledgeBaseConflictError(
            "Knowledge base mount sync cannot be retried",
            code="WORKSPACE_KB_MOUNT_SYNC_NOT_RETRYABLE",
        )


__all__ = [
    "KnowledgeBaseMountReconcileService",
]
