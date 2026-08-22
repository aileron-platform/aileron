"""Durable shared execution-plane recycle after Workspace access reduction."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, cast
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.db import models as db_models
from app.modules.workspace.runtime.job_repository import (
    WORKSPACE_ACCESS_RECYCLE,
    WORKSPACE_PROVISIONER_MISMATCH,
    WorkspaceRuntimeJobRepository,
)
from app.modules.audit.events import AuditEventService
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
    WorkspaceCustomResourceService,
)
from app.modules.workspace.execution_plane import (
    GenerationClaim,
    GenerationOutcome,
    WorkspaceExecutionPlane,
)
from app.modules.workspace.runtime.job_execution import (
    RuntimeJobClaimLease,
    RuntimeJobClaimLostError,
    WorkspaceRuntimeJobRunResult,
    normalize_utc,
)

logger = logging.getLogger(__name__)

_STABLE_ERROR_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True)
class _ClaimedAccessWork:
    job_id: str
    workspace_id: str
    claim_token: str
    target_revision: int
    correlation_id: str
    root_correlation_id: str
    attempt: int
    target_runtime_revision: int
    workspace_identity: WorkspaceExecutionPlaneIdentity
    plan: object


class WorkspaceAccessRecycleService(WorkspaceExecutionPlane):
    """Recycle all shared workloads before reopening action gates."""

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
            custom_resources=custom_resource_service,
            assertion_service_factory=assertion_service_factory,
            http_client_factory=http_client_factory,
        )
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.audit_events = AuditEventService(db)

    def reconcile_job(self, job_id: str) -> WorkspaceRuntimeJobRunResult:
        job = self.db.get(db_models.WorkspaceRuntimeJob, job_id)
        if job is None or job.operation != WORKSPACE_ACCESS_RECYCLE:
            self.db.rollback()
            return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
        workspace_id = job.workspace_id
        self.db.rollback()

        work: _ClaimedAccessWork | None = None
        try:
            bind = cast(Engine, self.db.get_bind())
            with workspace_session_advisory_lock(bind, workspace_id) as session_lock:
                work, terminal_result = self._claim_and_prepare_access(job_id)
                if terminal_result is not None:
                    return terminal_result
                if work is None:
                    return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                heartbeat = RuntimeJobClaimLease(
                    bind=bind,
                    job_id=work.job_id,
                    claim_token=work.claim_token,
                    timeout_seconds=(self.settings.RUNTIME_JOB_CLAIM_TIMEOUT_SECONDS),
                )

                def assert_claim() -> None:
                    heartbeat.assert_valid(session_lock)

                with heartbeat:
                    outcome = self.reconcile(
                        GenerationClaim(
                            workspace_id=work.workspace_id,
                            job_id=work.job_id,
                            assert_owned=assert_claim,
                            runtime_instance_id=work.plan.runtime_instance_id,
                            expected_mounted_revision=(
                                work.plan.observed_mount_revision
                            ),
                            target_mounted_revision=work.plan.mount_revision,
                            identity=work.workspace_identity,
                        ),
                        attempt=work.plan,
                    )
                    outcome.raise_for_failure()
                    assert_claim()
                    if not self._access_target_is_current(work):
                        self._discard_ready(
                            outcome,
                            assert_claim=assert_claim,
                        )
                        return self._complete_access_superseded(work)
                    return self._complete_access_success(
                        work,
                        outcome,
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
                "Workspace access recycle failed",
                extra={
                    "job_id": job_id,
                    "workspace_id": workspace_id,
                    "error_code": self._access_error_code(exc),
                },
            )
            if work is None:
                return WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            return self._complete_access_failure(work, exc)

    def _claim_and_prepare_access(
        self,
        job_id: str,
    ) -> tuple[_ClaimedAccessWork | None, WorkspaceRuntimeJobRunResult | None]:
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
                or job.operation != WORKSPACE_ACCESS_RECYCLE
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
                return self._fail_access_before_side_effect(
                    workspace=workspace,
                    job=job,
                    now=now,
                    error_code=WORKSPACE_PROVISIONER_MISMATCH,
                )
            if workspace.runtime_status != "running":
                self.db.rollback()
                return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            if job.target_revision != workspace.runtime_access_revision:
                return self._supersede_access_before_side_effect(
                    job=job,
                    workspace=workspace,
                    now=now,
                    reason="access_revision_advanced",
                )
            if (
                job.status == "queued"
                and job.target_runtime_instance_id != workspace.runtime_instance_id
            ):
                queued_replacement = (
                    self.jobs.supersede_stale_queued_and_enqueue_replacement(
                        job_id=job.id,
                        target_runtime_instance_id=workspace.runtime_instance_id,
                        correlation_id=str(uuid4()),
                        scheduled_at=now,
                    )
                )
                if queued_replacement is None:
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
                stale_job, _replacement = queued_replacement
                self._record_access_audit(
                    workspace=workspace,
                    job=stale_job,
                    event_type="runtime.access_recycle_superseded",
                    action="supersede_access_recycle",
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
                    eligible_runtime_statuses={"running"},
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

            if claimed_job.target_runtime_instance_id != workspace.runtime_instance_id:
                running_replacement = (
                    self.jobs.supersede_running_and_preserve_successor(
                        job_id=claimed_job.id,
                        claim_token=claim_token,
                        target_revision=workspace.runtime_access_revision,
                        target_runtime_instance_id=workspace.runtime_instance_id,
                        correlation_id=str(uuid4()),
                        scheduled_at=now,
                    )
                )
                if running_replacement is None:
                    self.db.rollback()
                    return None, WorkspaceRuntimeJobRunResult.CLAIM_LOST
                stale_job, _successor, _created = running_replacement
                self._record_access_audit(
                    workspace=workspace,
                    job=stale_job,
                    event_type="runtime.access_recycle_superseded",
                    action="supersede_access_recycle",
                    result="success",
                    error_code=None,
                    reason="runtime_instance_advanced",
                )
                self.db.commit()
                return None, WorkspaceRuntimeJobRunResult.SUPERSEDED

            if (
                workspace.runtime_desired_revision
                != workspace.runtime_observed_revision
            ):
                self.db.rollback()
                return None, WorkspaceRuntimeJobRunResult.NOT_CLAIMED
            workspace_identity = self._execution_plane_identity(workspace)
            workspace.runtime_desired_revision += 1
            workspace.runtime_status = "restarting"
            target_runtime_revision = workspace.runtime_desired_revision
            plan = self._prepare_execution_plane(workspace)
            attempt = int(claimed_job.job_metadata.get("attempt", 0)) + int(
                claimed_job.retries
            )
            self._record_access_audit(
                workspace=workspace,
                job=claimed_job,
                event_type="runtime.access_recycle_started",
                action="start_access_recycle",
                result="success",
                error_code=None,
                attempt=attempt,
            )
            work = _ClaimedAccessWork(
                job_id=claimed_job.id,
                workspace_id=workspace.id,
                claim_token=claim_token,
                target_revision=claimed_job.target_revision or 0,
                correlation_id=claimed_job.correlation_id,
                root_correlation_id=claimed_job.root_correlation_id,
                attempt=attempt,
                target_runtime_revision=target_runtime_revision,
                workspace_identity=workspace_identity,
                plan=plan,
            )
            self.db.commit()
            return work, None
        except Exception:
            self.db.rollback()
            raise

    def _fail_access_before_side_effect(
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
        workspace.runtime_status = "error"
        self._record_access_audit(
            workspace=workspace,
            job=job,
            event_type="runtime.access_recycle_failed",
            action="fail_access_recycle",
            result="failure",
            error_code=error_code,
            attempt=int(job.job_metadata.get("attempt", 0)) + int(job.retries),
        )
        self.db.commit()
        return None, WorkspaceRuntimeJobRunResult.FAILED

    def _supersede_access_before_side_effect(
        self,
        *,
        job: db_models.WorkspaceRuntimeJob,
        workspace: db_models.Workspace,
        now: datetime,
        reason: str,
    ) -> tuple[None, WorkspaceRuntimeJobRunResult]:
        if job.status == "queued":
            transitioned = self.jobs.supersede_queued_job(
                job_id=job.id,
                finished_at=now,
            )
        else:
            transitioned = self.jobs.supersede_running_job(
                job_id=job.id,
                claim_token=job.claim_token or "",
                finished_at=now,
            )
        if not transitioned:
            self.db.rollback()
            return None, WorkspaceRuntimeJobRunResult.CLAIM_LOST
        self._record_access_audit(
            workspace=workspace,
            job=job,
            event_type="runtime.access_recycle_superseded",
            action="supersede_access_recycle",
            result="success",
            error_code=None,
            reason=reason,
        )
        self.db.commit()
        return None, WorkspaceRuntimeJobRunResult.SUPERSEDED

    def _access_target_is_current(self, work: _ClaimedAccessWork) -> bool:
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
                and workspace.runtime_access_revision == work.target_revision
                and workspace.knowledge_base_mount_desired_revision
                == work.plan.mount_revision
                and workspace.runtime_desired_revision == work.target_runtime_revision
            )
            self.db.rollback()
            return current
        except Exception:
            self.db.rollback()
            raise

    def _complete_access_success(
        self,
        work: _ClaimedAccessWork,
        outcome: GenerationOutcome,
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
            job = self.db.get(db_models.WorkspaceRuntimeJob, work.job_id)
            if (
                workspace is None
                or job is None
                or workspace.runtime_access_revision != work.target_revision
                or workspace.knowledge_base_mount_desired_revision
                != work.plan.mount_revision
                or workspace.runtime_desired_revision != work.target_runtime_revision
                or not self.jobs.complete_running_job(
                    job_id=work.job_id,
                    claim_token=work.claim_token,
                    finished_at=now,
                )
            ):
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            self._stage_ready(workspace, outcome)
            workspace.runtime_observed_revision = work.target_runtime_revision
            workspace.runtime_status = "running"
            workspace.runtime_reason = None
            workspace.runtime_error_code = None
            workspace.runtime_last_transition_at = now
            workspace.runtime_access_observed_revision = work.target_revision
            self._record_access_audit(
                workspace=workspace,
                job=job,
                event_type="runtime.access_recycle_ready",
                action="complete_access_recycle",
                result="success",
                error_code=None,
                attempt=work.attempt,
                new_runtime_instance_id=workspace.runtime_instance_id,
            )
            self.db.commit()
            return WorkspaceRuntimeJobRunResult.SUCCEEDED
        except Exception:
            self.db.rollback()
            raise

    def _complete_access_superseded(
        self,
        work: _ClaimedAccessWork,
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
                target_revision=workspace.runtime_access_revision,
                target_runtime_instance_id=workspace.runtime_instance_id,
                correlation_id=str(uuid4()),
                scheduled_at=now,
            )
            if replacement is None:
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            job, _successor, _created = replacement
            self._record_access_audit(
                workspace=workspace,
                job=job,
                event_type="runtime.access_recycle_superseded",
                action="supersede_access_recycle",
                result="success",
                error_code=None,
                reason="desired_state_advanced",
                attempt=work.attempt,
            )
            self.db.commit()
            return WorkspaceRuntimeJobRunResult.SUPERSEDED
        except Exception:
            self.db.rollback()
            raise

    def _complete_access_failure(
        self,
        work: _ClaimedAccessWork,
        exc: Exception,
    ) -> WorkspaceRuntimeJobRunResult:
        now = datetime.now(timezone.utc)
        error_code = self._access_error_code(exc)
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
            if (
                workspace.runtime_access_revision != work.target_revision
                or workspace.knowledge_base_mount_desired_revision
                != work.plan.mount_revision
            ):
                self.db.rollback()
                return self._complete_access_superseded(work)
            if not self.jobs.fail_running_job(
                job_id=work.job_id,
                claim_token=work.claim_token,
                finished_at=now,
                error_code=error_code,
            ):
                self.db.rollback()
                return WorkspaceRuntimeJobRunResult.CLAIM_LOST
            workspace.runtime_status = "error"
            self._record_access_audit(
                workspace=workspace,
                job=job,
                event_type="runtime.access_recycle_failed",
                action="fail_access_recycle",
                result="failure",
                error_code=error_code,
                attempt=work.attempt,
            )
            self.db.commit()
            return WorkspaceRuntimeJobRunResult.FAILED
        except Exception:
            self.db.rollback()
            raise

    def _record_access_audit(
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
            "runtime_access_revision": job.target_revision or 0,
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
            actor_id="workspace-access-reconciler",
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
    def _access_error_code(exc: Exception) -> str:
        candidate = getattr(exc, "code", None)
        if isinstance(candidate, str) and _STABLE_ERROR_CODE.fullmatch(candidate):
            return candidate
        return "WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED"


__all__ = ["WorkspaceAccessRecycleService"]
