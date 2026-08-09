"""Persistence operations for durable workspace runtime jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Collection, Mapping, Optional
from uuid import uuid4

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session, aliased

from app.db import models as db_models

KNOWLEDGE_BASE_MOUNT_RECONCILE = "knowledge_base_mount_reconcile"
WORKSPACE_ACCESS_RECYCLE = "workspace_access_recycle"
WORKSPACE_START = "workspace_start"
WORKSPACE_STOP = "workspace_stop"
WORKSPACE_DELETE = "workspace_delete"
RUNTIME_RESTART = "runtime_restart"
BROWSER_RESTART = "browser_restart"
CANVAS_RESTART = "canvas_restart"
BROWSER_CREDENTIAL_ROTATE = "browser_credential_rotate"
WORKSPACE_PROVISIONER_MISMATCH = "WORKSPACE_PROVISIONER_MISMATCH"
WORKSPACE_LIFECYCLE_OPERATIONS = frozenset(
    {
        WORKSPACE_START,
        WORKSPACE_STOP,
        WORKSPACE_DELETE,
    }
)
WORKSPACE_DELETE_PHASE_QUEUED = "queued"
WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS = "cancelling_automations"
WORKSPACE_DELETE_PHASE_STOPPING_RUNTIME = "stopping_runtime"
WORKSPACE_DELETE_PHASE_DELETING_RESOURCES = "deleting_resources"
WORKSPACE_DELETE_PHASE_FINALIZING = "finalizing"
WORKSPACE_DELETE_PHASES = frozenset(
    {
        WORKSPACE_DELETE_PHASE_QUEUED,
        WORKSPACE_DELETE_PHASE_CANCELLING_AUTOMATIONS,
        WORKSPACE_DELETE_PHASE_STOPPING_RUNTIME,
        WORKSPACE_DELETE_PHASE_DELETING_RESOURCES,
        WORKSPACE_DELETE_PHASE_FINALIZING,
    }
)
COMPONENT_OPERATIONS = frozenset(
    {
        RUNTIME_RESTART,
        BROWSER_RESTART,
        CANVAS_RESTART,
        BROWSER_CREDENTIAL_ROTATE,
    }
)
COMPONENT_OPERATION_TARGET = {
    RUNTIME_RESTART: "runtime",
    BROWSER_RESTART: "browser",
    CANVAS_RESTART: "canvas",
    BROWSER_CREDENTIAL_ROTATE: "browser",
}

WORKSPACE_RUNTIME_STATUSES = frozenset(
    {
        "starting",
        "running",
        "stopping",
        "stopped",
        "restarting",
        "error",
        "deleting",
    }
)

_MOUNT_JOB_METADATA_TYPES: dict[str, type] = {
    "attachment_id": str,
    "attempt": int,
    "knowledge_base_id": str,
    "mount_action": str,
    "mutation_action": str,
    "offline_promotion": bool,
}

_ACCESS_RECYCLE_JOB_METADATA_TYPES: dict[str, type] = {
    "attempt": int,
    "reason": str,
}


class ExpiredJobRecoveryAction(str, Enum):
    """Durable outcome of inspecting one expired running job."""

    NOOP = "noop"
    SUPERSEDED = "superseded"
    RECLAIMED = "reclaimed"
    FAILED = "failed"


@dataclass(frozen=True)
class ExpiredJobRecoveryResult:
    """Result returned without committing the surrounding recovery transaction."""

    action: ExpiredJobRecoveryAction
    job: Optional[db_models.WorkspaceRuntimeJob]
    successor: Optional[db_models.WorkspaceRuntimeJob] = None


@dataclass(frozen=True)
class RetryJobResult:
    """Idempotent retry enqueue result."""

    job: db_models.WorkspaceRuntimeJob
    created: bool


@dataclass(frozen=True)
class EnqueueLifecycleJobResult:
    """Idempotent lifecycle command persistence result."""

    job: db_models.WorkspaceRuntimeJob
    created: bool


class WorkspaceRuntimeJobRepository:
    """Lock and persist workspace runtime jobs without owning transactions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def enqueue_lifecycle_job(
        self,
        *,
        workspace: db_models.Workspace,
        operation: str,
        correlation_id: str,
        root_correlation_id: str,
        scheduled_at: datetime,
        target_runtime_instance_id: str | None,
        retry_of_job_id: str | None = None,
        job_metadata: Optional[Mapping[str, Any]] = None,
    ) -> EnqueueLifecycleJobResult:
        """Insert one durable lifecycle parent or return its active duplicate.

        The caller must hold the Workspace row/advisory lock and owns commit.
        """

        self._validate_workspace(workspace)
        self._validate_lifecycle_operation(operation)
        self._validate_correlation_id(correlation_id)
        self._validate_correlation_id(root_correlation_id)
        metadata = self._validate_lifecycle_job_metadata(job_metadata or {})
        active_job = self.find_active_lifecycle_job(
            workspace_id=workspace.id,
            operation=operation,
            for_update=True,
        )
        if active_job is not None:
            return EnqueueLifecycleJobResult(job=active_job, created=False)

        if retry_of_job_id is not None:
            self._validate_identifier(
                retry_of_job_id,
                label="Retry parent identifier",
            )
            retry_parent = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.id == retry_of_job_id,
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace.id,
                    db_models.WorkspaceRuntimeJob.operation == operation,
                    db_models.WorkspaceRuntimeJob.status == "failed",
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if retry_parent is None:
                raise ValueError("Lifecycle retry parent is not retryable")
            duplicate_retry = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(
                    db_models.WorkspaceRuntimeJob.retry_of_job_id == retry_parent.id,
                )
                .order_by(
                    db_models.WorkspaceRuntimeJob.scheduled_at,
                    db_models.WorkspaceRuntimeJob.id,
                )
                .limit(1)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if duplicate_retry is not None:
                return EnqueueLifecycleJobResult(
                    job=duplicate_retry,
                    created=False,
                )
            root_correlation_id = retry_parent.root_correlation_id
            previous_attempt = retry_parent.job_metadata.get("attempt", 0)
            if type(previous_attempt) is not int or previous_attempt < 0:
                raise ValueError("Lifecycle retry attempt is invalid")
            metadata["attempt"] = previous_attempt + 1

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation=operation,
            target_component=None,
            strategy=workspace.provisioner,
            status="queued",
            retries=0,
            target_revision=None,
            target_runtime_instance_id=target_runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=None,
            retry_of_job_id=retry_of_job_id,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(job)
        self.db.flush()
        return EnqueueLifecycleJobResult(job=job, created=True)

    def enqueue_component_job(
        self,
        *,
        workspace: db_models.Workspace,
        operation: str,
        correlation_id: str,
        scheduled_at: datetime,
        job_metadata: Optional[Mapping[str, Any]] = None,
    ) -> EnqueueLifecycleJobResult:
        """Insert one component-scoped desired revision command."""

        self._validate_workspace(workspace)
        if operation not in COMPONENT_OPERATIONS:
            raise ValueError("Workspace component operation is invalid")
        self._validate_correlation_id(correlation_id)
        component = COMPONENT_OPERATION_TARGET[operation]
        active_job = self.find_active_component_job(
            workspace_id=workspace.id,
            component=component,
            for_update=True,
        )
        if active_job is not None:
            return EnqueueLifecycleJobResult(job=active_job, created=False)

        target_revision = int(getattr(workspace, f"{component}_desired_revision"))
        metadata = dict(job_metadata or {})
        if operation == BROWSER_CREDENTIAL_ROTATE:
            if set(metadata) - {"browser_credential_revision"}:
                raise ValueError("Browser credential job metadata is invalid")
            credential_revision = metadata.get("browser_credential_revision")
            if type(credential_revision) is not int or credential_revision < 1:
                raise ValueError("Browser credential revision is invalid")
        elif metadata:
            raise ValueError("Component restart metadata is not supported")

        job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation=operation,
            target_component=component,
            strategy=workspace.provisioner,
            status="queued",
            retries=0,
            target_revision=target_revision,
            target_runtime_instance_id=workspace.runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=None,
            retry_of_job_id=None,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(job)
        self.db.flush()
        return EnqueueLifecycleJobResult(job=job, created=True)

    def find_active_component_job(
        self,
        *,
        workspace_id: str,
        component: str,
        for_update: bool = False,
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        """Return the queued/running job fencing one component."""

        self._validate_identifier(workspace_id, label="Workspace identifier")
        if component not in {"runtime", "browser", "canvas"}:
            raise ValueError("Workspace component is invalid")
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.target_component == component,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def enqueue_browser_credential_rotation(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> EnqueueLifecycleJobResult:
        """Persist rotation against the Browser component revision fence."""

        return self.enqueue_component_job(
            workspace=workspace,
            operation=BROWSER_CREDENTIAL_ROTATE,
            correlation_id=correlation_id,
            scheduled_at=scheduled_at,
            job_metadata={
                "browser_credential_revision": workspace.browser_credential_revision
            },
        )

    def find_active_lifecycle_job(
        self,
        *,
        workspace_id: str,
        operation: str,
        for_update: bool = False,
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        """Return the queued/running parent for one lifecycle command."""

        self._validate_identifier(workspace_id, label="Workspace identifier")
        self._validate_lifecycle_operation(operation)
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == operation,
                db_models.WorkspaceRuntimeJob.status.in_({"queued", "running"}),
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def find_latest_failed_job(
        self,
        *,
        workspace_id: str,
        operation: str,
        for_update: bool = False,
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        """Return the newest failed job for lifecycle or revision recovery."""

        self._validate_identifier(workspace_id, label="Workspace identifier")
        if operation not in {
            KNOWLEDGE_BASE_MOUNT_RECONCILE,
            WORKSPACE_ACCESS_RECYCLE,
            *WORKSPACE_LIFECYCLE_OPERATIONS,
        }:
            raise ValueError("Runtime job operation is invalid")
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == operation,
                db_models.WorkspaceRuntimeJob.status == "failed",
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.finished_at.desc(),
                db_models.WorkspaceRuntimeJob.id.desc(),
            )
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def supersede_queued_and_enqueue_mount_reconcile(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        scheduled_at: datetime,
        job_metadata: Optional[Mapping[str, Any]] = None,
        root_correlation_id: str | None = None,
        retry_of_job_id: str | None = None,
    ) -> tuple[
        db_models.WorkspaceRuntimeJob,
        list[db_models.WorkspaceRuntimeJob],
    ]:
        """Replace the queued mount intent while retaining every prior lineage."""

        self._validate_workspace(workspace)
        self._validate_correlation_id(correlation_id)
        root_id = root_correlation_id or correlation_id
        self._validate_correlation_id(root_id)
        if retry_of_job_id is not None:
            self._validate_identifier(
                retry_of_job_id,
                label="Retry parent identifier",
            )
        metadata = self._validate_mount_job_metadata(job_metadata or {})

        superseded_jobs = self._lock_queued_jobs(
            workspace_id=workspace.id,
            operation=KNOWLEDGE_BASE_MOUNT_RECONCILE,
        )
        for queued_job in superseded_jobs:
            queued_job.status = "superseded"
            queued_job.finished_at = scheduled_at

        # Flush terminal transitions before inserting the next queued row so the
        # partial unique index never observes two queued jobs for one operation.
        if superseded_jobs:
            self.db.flush()

        new_job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation=KNOWLEDGE_BASE_MOUNT_RECONCILE,
            target_component=None,
            strategy=workspace.provisioner,
            status="queued",
            retries=0,
            target_revision=workspace.knowledge_base_mount_desired_revision,
            target_runtime_instance_id=workspace.runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=root_id,
            job_metadata=metadata,
            lifecycle_job_id=None,
            retry_of_job_id=retry_of_job_id,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(new_job)
        self.db.flush()
        return new_job, superseded_jobs

    def supersede_queued_and_enqueue_access_recycle(
        self,
        *,
        workspace: db_models.Workspace,
        correlation_id: str,
        root_correlation_id: str,
        scheduled_at: datetime,
        job_metadata: Optional[Mapping[str, Any]] = None,
    ) -> tuple[
        db_models.WorkspaceRuntimeJob,
        list[db_models.WorkspaceRuntimeJob],
    ]:
        """Replace the queued access-recycle intent without committing."""

        self._validate_access_workspace(workspace)
        self._validate_correlation_id(correlation_id)
        self._validate_correlation_id(root_correlation_id)
        metadata = self._validate_access_recycle_job_metadata(job_metadata or {})

        superseded_jobs = self._lock_queued_jobs(
            workspace_id=workspace.id,
            operation=WORKSPACE_ACCESS_RECYCLE,
        )
        for queued_job in superseded_jobs:
            queued_job.status = "superseded"
            queued_job.finished_at = scheduled_at

        if superseded_jobs:
            self.db.flush()

        new_job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=workspace.id,
            operation=WORKSPACE_ACCESS_RECYCLE,
            target_component=None,
            strategy=workspace.provisioner,
            status="queued",
            retries=0,
            target_revision=workspace.runtime_access_revision,
            target_runtime_instance_id=workspace.runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=None,
            retry_of_job_id=None,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(new_job)
        self.db.flush()
        return new_job, superseded_jobs

    def supersede_stale_queued_and_enqueue_replacement(
        self,
        *,
        job_id: str,
        target_runtime_instance_id: str | None,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> Optional[tuple[db_models.WorkspaceRuntimeJob, db_models.WorkspaceRuntimeJob]]:
        """Replace an immutable queued intent after another operation advances generation."""

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_correlation_id(correlation_id)
        stale_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if stale_job is None:
            return None
        if stale_job.operation not in {
            KNOWLEDGE_BASE_MOUNT_RECONCILE,
            WORKSPACE_ACCESS_RECYCLE,
        }:
            raise ValueError("Only revision jobs can replace a stale generation target")
        metadata = dict(stale_job.job_metadata or {})
        previous_attempt = metadata.get("attempt", 0)
        if type(previous_attempt) is not int or previous_attempt < 0:
            raise ValueError("Replacement attempt must be a non-negative integer")
        metadata["attempt"] = previous_attempt + 1
        if stale_job.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
            metadata = self._validate_mount_job_metadata(metadata)
        else:
            metadata = self._validate_access_recycle_job_metadata(metadata)

        stale_job.status = "superseded"
        stale_job.finished_at = scheduled_at
        self.db.flush()
        replacement = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=stale_job.workspace_id,
            operation=stale_job.operation,
            target_component=stale_job.target_component,
            strategy=stale_job.strategy,
            status="queued",
            retries=0,
            target_revision=stale_job.target_revision,
            target_runtime_instance_id=target_runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=stale_job.root_correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=stale_job.lifecycle_job_id,
            retry_of_job_id=None,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(replacement)
        self.db.flush()
        return stale_job, replacement

    def supersede_running_and_preserve_successor(
        self,
        *,
        job_id: str,
        claim_token: str,
        target_revision: int,
        target_runtime_instance_id: str | None,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> Optional[
        tuple[
            db_models.WorkspaceRuntimeJob,
            db_models.WorkspaceRuntimeJob,
            bool,
        ]
    ]:
        """Fence stale running work and retain or create its latest successor."""

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_identifier(claim_token, label="Claim token")
        self._validate_correlation_id(correlation_id)
        if type(target_revision) is not int or target_revision < 0:
            raise ValueError("Replacement target revision must not be negative")
        running_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "running",
                db_models.WorkspaceRuntimeJob.claim_token == claim_token,
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_not(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at > scheduled_at,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if running_job is None:
            return None
        existing_successor = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == running_job.workspace_id,
                db_models.WorkspaceRuntimeJob.operation == running_job.operation,
                db_models.WorkspaceRuntimeJob.status == "queued",
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        running_job.status = "superseded"
        running_job.claim_token = None
        running_job.claim_expires_at = None
        running_job.finished_at = scheduled_at
        running_job.error_code = None
        self.db.flush()
        if existing_successor is not None:
            return running_job, existing_successor, False

        metadata = dict(running_job.job_metadata or {})
        previous_attempt = metadata.get("attempt", 0)
        if type(previous_attempt) is not int or previous_attempt < 0:
            raise ValueError("Replacement attempt must be a non-negative integer")
        metadata["attempt"] = previous_attempt + 1
        if running_job.operation == KNOWLEDGE_BASE_MOUNT_RECONCILE:
            metadata = self._validate_mount_job_metadata(metadata)
        elif running_job.operation == WORKSPACE_ACCESS_RECYCLE:
            metadata = self._validate_access_recycle_job_metadata(metadata)
        else:
            raise ValueError("Only revision jobs can create a running successor")
        replacement = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=running_job.workspace_id,
            operation=running_job.operation,
            target_component=running_job.target_component,
            strategy=running_job.strategy,
            status="queued",
            retries=0,
            target_revision=target_revision,
            target_runtime_instance_id=target_runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=running_job.root_correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=running_job.lifecycle_job_id,
            retry_of_job_id=None,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(replacement)
        self.db.flush()
        return running_job, replacement, True

    def claim_queued_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        claimed_at: datetime,
        claim_expires_at: datetime,
        eligible_runtime_statuses: Collection[str],
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        """CAS one due queued job to running when its Workspace is eligible.

        The caller still owns the surrounding transaction and any advisory lock.
        The query also rejects provisioner drift and a second running job for the
        same Workspace operation before the partial unique index is reached.
        """

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_claim(claim_token, claimed_at, claim_expires_at)
        statuses = self._validate_runtime_statuses(eligible_runtime_statuses)

        running_job = aliased(db_models.WorkspaceRuntimeJob)
        workspace_is_eligible = exists(
            select(db_models.Workspace.id).where(
                db_models.Workspace.id == db_models.WorkspaceRuntimeJob.workspace_id,
                db_models.Workspace.runtime_status.in_(statuses),
                db_models.Workspace.provisioner
                == db_models.WorkspaceRuntimeJob.strategy,
            )
        )
        no_running_job = ~exists(
            select(running_job.id).where(
                running_job.workspace_id == db_models.WorkspaceRuntimeJob.workspace_id,
                running_job.operation == db_models.WorkspaceRuntimeJob.operation,
                running_job.status == "running",
            )
        )
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.scheduled_at <= claimed_at,
                db_models.WorkspaceRuntimeJob.claim_token.is_(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_(None),
                workspace_is_eligible,
                no_running_job,
            )
            .values(
                status="running",
                claim_token=claim_token,
                claim_expires_at=claim_expires_at,
                last_heartbeat_at=claimed_at,
                started_at=claimed_at,
                finished_at=None,
                error_code=None,
            )
            .returning(db_models.WorkspaceRuntimeJob)
            .execution_options(
                synchronize_session=False,
                populate_existing=True,
            )
        )
        return self.db.scalar(statement)

    def heartbeat_running_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        heartbeat_at: datetime,
        claim_expires_at: datetime,
    ) -> bool:
        """Renew a live lease using job id and claim token as a fencing CAS."""

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_claim(claim_token, heartbeat_at, claim_expires_at)
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "running",
                db_models.WorkspaceRuntimeJob.claim_token == claim_token,
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_not(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at > heartbeat_at,
            )
            .values(
                last_heartbeat_at=heartbeat_at,
                claim_expires_at=claim_expires_at,
            )
            .returning(db_models.WorkspaceRuntimeJob.id)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement) is not None

    def complete_running_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        finished_at: datetime,
    ) -> bool:
        """CAS a live claimed job to succeeded."""

        return self._transition_claimed_job(
            job_id=job_id,
            claim_token=claim_token,
            finished_at=finished_at,
            target_status="succeeded",
            error_code=None,
        )

    def fail_running_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        finished_at: datetime,
        error_code: str,
    ) -> bool:
        """CAS a live claimed job to failed with a stable code only."""

        self._validate_error_code(error_code)
        return self._transition_claimed_job(
            job_id=job_id,
            claim_token=claim_token,
            finished_at=finished_at,
            target_status="failed",
            error_code=error_code,
        )

    def supersede_running_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        finished_at: datetime,
    ) -> bool:
        """CAS a live claimed job to superseded after desired state advances."""

        return self._transition_claimed_job(
            job_id=job_id,
            claim_token=claim_token,
            finished_at=finished_at,
            target_status="superseded",
            error_code=None,
        )

    def supersede_queued_job(
        self,
        *,
        job_id: str,
        finished_at: datetime,
    ) -> bool:
        """CAS an unclaimed queued intent to its immutable terminal state."""

        self._validate_identifier(job_id, label="Job identifier")
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.claim_token.is_(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_(None),
            )
            .values(
                status="superseded",
                finished_at=finished_at,
                error_code=None,
            )
            .returning(db_models.WorkspaceRuntimeJob.id)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement) is not None

    def fail_queued_job(
        self,
        *,
        job_id: str,
        finished_at: datetime,
        error_code: str,
    ) -> bool:
        """CAS an unclaimed queued intent to failed with a stable code."""

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_error_code(error_code)
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.claim_token.is_(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_(None),
            )
            .values(
                status="failed",
                finished_at=finished_at,
                error_code=error_code,
            )
            .returning(db_models.WorkspaceRuntimeJob.id)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement) is not None

    def enqueue_retry_for_failed_job(
        self,
        *,
        failed_job_id: str,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> Optional[RetryJobResult]:
        """Create one immutable retry child, or return its existing sibling.

        Locking the failed parent makes duplicate requests idempotent without
        reopening the failed row. The caller owns commit and rollback.
        """

        self._validate_identifier(failed_job_id, label="Failed job identifier")
        self._validate_correlation_id(correlation_id)
        failed_job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == failed_job_id,
                db_models.WorkspaceRuntimeJob.status == "failed",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if failed_job is None:
            return None

        existing_retry = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.retry_of_job_id == failed_job.id,
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at,
                db_models.WorkspaceRuntimeJob.id,
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if existing_retry is not None:
            return RetryJobResult(job=existing_retry, created=False)

        metadata = dict(failed_job.job_metadata or {})
        previous_attempt = metadata.get("attempt", 0)
        if type(previous_attempt) is not int or previous_attempt < 0:
            raise ValueError(
                "Retry job metadata attempt must be a non-negative integer"
            )
        metadata["attempt"] = previous_attempt + 1

        retry_job = db_models.WorkspaceRuntimeJob(
            id=str(uuid4()),
            workspace_id=failed_job.workspace_id,
            operation=failed_job.operation,
            target_component=failed_job.target_component,
            strategy=failed_job.strategy,
            status="queued",
            retries=0,
            target_revision=failed_job.target_revision,
            target_runtime_instance_id=failed_job.target_runtime_instance_id,
            correlation_id=correlation_id,
            root_correlation_id=failed_job.root_correlation_id,
            job_metadata=metadata,
            lifecycle_job_id=failed_job.lifecycle_job_id,
            retry_of_job_id=failed_job.id,
            claim_token=None,
            claim_expires_at=None,
            last_heartbeat_at=None,
            dispatch_attempts=0,
            scheduled_at=scheduled_at,
            started_at=None,
            finished_at=None,
            error_code=None,
        )
        self.db.add(retry_job)
        self.db.flush()
        return RetryJobResult(job=retry_job, created=True)

    def recover_expired_running_job(
        self,
        *,
        job_id: str,
        recovered_at: datetime,
        replacement_claim_token: str,
        replacement_claim_expires_at: datetime,
        max_retries: int,
        exhausted_error_code: str,
    ) -> ExpiredJobRecoveryResult:
        """Fence an expired worker and preserve any newer queued successor.

        With a successor, the expired row becomes superseded. Without one, the
        running row is reclaimed in place until its execution retry budget is
        exhausted, avoiding a queued-index collision.
        """

        self._validate_identifier(job_id, label="Job identifier")
        self._validate_claim(
            replacement_claim_token,
            recovered_at,
            replacement_claim_expires_at,
        )
        if type(max_retries) is not int or max_retries < 0:
            raise ValueError("Maximum retries must be a non-negative integer")
        self._validate_error_code(exhausted_error_code)

        job = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(db_models.WorkspaceRuntimeJob.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            job is None
            or job.status != "running"
            or job.claim_expires_at is None
            or job.claim_expires_at > recovered_at
        ):
            return ExpiredJobRecoveryResult(
                action=ExpiredJobRecoveryAction.NOOP,
                job=job,
            )

        successor = self.db.scalar(
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == job.workspace_id,
                db_models.WorkspaceRuntimeJob.operation == job.operation,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.id != job.id,
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at,
                db_models.WorkspaceRuntimeJob.id,
            )
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if successor is not None:
            job.status = "superseded"
            job.finished_at = recovered_at
            job.error_code = None
            self._clear_claim(job)
            self.db.flush()
            return ExpiredJobRecoveryResult(
                action=ExpiredJobRecoveryAction.SUPERSEDED,
                job=job,
                successor=successor,
            )

        if job.retries >= max_retries:
            job.status = "failed"
            job.finished_at = recovered_at
            job.error_code = exhausted_error_code
            self._clear_claim(job)
            self.db.flush()
            return ExpiredJobRecoveryResult(
                action=ExpiredJobRecoveryAction.FAILED,
                job=job,
            )

        job.retries += 1
        job.claim_token = replacement_claim_token
        job.claim_expires_at = replacement_claim_expires_at
        job.last_heartbeat_at = recovered_at
        job.finished_at = None
        job.error_code = None
        self.db.flush()
        return ExpiredJobRecoveryResult(
            action=ExpiredJobRecoveryAction.RECLAIMED,
            job=job,
        )

    def record_dispatch_failure(
        self,
        *,
        job_id: str,
        expected_dispatch_attempts: int,
        failed_at: datetime,
        base_delay_seconds: int,
        max_delay_seconds: int,
    ) -> Optional[db_models.WorkspaceRuntimeJob]:
        """CAS a broker publish failure into bounded exponential backoff."""

        self._validate_identifier(job_id, label="Job identifier")
        if (
            type(expected_dispatch_attempts) is not int
            or expected_dispatch_attempts < 0
        ):
            raise ValueError("Expected dispatch attempts must not be negative")
        if type(base_delay_seconds) is not int or base_delay_seconds <= 0:
            raise ValueError("Dispatch base delay must be a positive integer")
        if type(max_delay_seconds) is not int or max_delay_seconds <= 0:
            raise ValueError("Dispatch maximum delay must be a positive integer")
        if base_delay_seconds > max_delay_seconds:
            raise ValueError("Dispatch base delay must not exceed maximum delay")

        bounded_exponent = min(
            expected_dispatch_attempts,
            max_delay_seconds.bit_length(),
        )
        delay_seconds = min(
            max_delay_seconds,
            base_delay_seconds * (1 << bounded_exponent),
        )
        next_scheduled_at = failed_at + timedelta(seconds=delay_seconds)
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.dispatch_attempts
                == expected_dispatch_attempts,
                db_models.WorkspaceRuntimeJob.scheduled_at <= failed_at,
            )
            .values(
                dispatch_attempts=expected_dispatch_attempts + 1,
                scheduled_at=next_scheduled_at,
            )
            .returning(db_models.WorkspaceRuntimeJob)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement)

    def find_dispatchable_queued_jobs(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[db_models.WorkspaceRuntimeJob]:
        """Return due durable intents; duplicate broker delivery remains safe."""

        self._validate_limit(limit)
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.status == "queued",
                db_models.WorkspaceRuntimeJob.scheduled_at <= now,
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.scheduled_at,
                db_models.WorkspaceRuntimeJob.id,
            )
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return list(self.db.scalars(statement).all())

    def find_expired_running_jobs(
        self,
        *,
        now: datetime,
        limit: int = 100,
    ) -> list[db_models.WorkspaceRuntimeJob]:
        """Return recovery candidates without changing their state."""

        self._validate_limit(limit)
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.status == "running",
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_not(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at <= now,
            )
            .order_by(
                db_models.WorkspaceRuntimeJob.claim_expires_at,
                db_models.WorkspaceRuntimeJob.id,
            )
            .limit(limit)
            .execution_options(populate_existing=True)
        )
        return list(self.db.scalars(statement).all())

    def _lock_queued_jobs(
        self,
        *,
        workspace_id: str,
        operation: str,
    ) -> list[db_models.WorkspaceRuntimeJob]:
        statement = (
            select(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation == operation,
                db_models.WorkspaceRuntimeJob.status == "queued",
            )
            .order_by(db_models.WorkspaceRuntimeJob.id)
            .with_for_update()
        )
        return list(self.db.scalars(statement).all())

    def _transition_claimed_job(
        self,
        *,
        job_id: str,
        claim_token: str,
        finished_at: datetime,
        target_status: str,
        error_code: Optional[str],
    ) -> bool:
        self._validate_identifier(job_id, label="Job identifier")
        self._validate_identifier(claim_token, label="Claim token")
        if target_status not in {"succeeded", "failed", "superseded"}:
            raise ValueError("Claimed job terminal status is invalid")
        statement = (
            update(db_models.WorkspaceRuntimeJob)
            .where(
                db_models.WorkspaceRuntimeJob.id == job_id,
                db_models.WorkspaceRuntimeJob.status == "running",
                db_models.WorkspaceRuntimeJob.claim_token == claim_token,
                db_models.WorkspaceRuntimeJob.claim_expires_at.is_not(None),
                db_models.WorkspaceRuntimeJob.claim_expires_at > finished_at,
            )
            .values(
                status=target_status,
                claim_token=None,
                claim_expires_at=None,
                finished_at=finished_at,
                error_code=error_code,
            )
            .returning(db_models.WorkspaceRuntimeJob.id)
            .execution_options(synchronize_session=False)
        )
        return self.db.scalar(statement) is not None

    @staticmethod
    def _clear_claim(job: db_models.WorkspaceRuntimeJob) -> None:
        job.claim_token = None
        job.claim_expires_at = None

    @staticmethod
    def _validate_identifier(value: str, *, label: str) -> None:
        if not value or len(value) > 64:
            raise ValueError(f"{label} must contain 1 to 64 characters")

    @classmethod
    def _validate_claim(
        cls,
        claim_token: str,
        claim_started_at: datetime,
        claim_expires_at: datetime,
    ) -> None:
        cls._validate_identifier(claim_token, label="Claim token")
        if claim_expires_at <= claim_started_at:
            raise ValueError("Claim expiration must be later than claim time")

    @staticmethod
    def _validate_runtime_statuses(statuses: Collection[str]) -> tuple[str, ...]:
        status_set = set(statuses)
        if not status_set or not status_set <= WORKSPACE_RUNTIME_STATUSES:
            raise ValueError("Eligible Workspace runtime statuses are invalid")
        return tuple(sorted(status_set))

    @staticmethod
    def _validate_error_code(error_code: str) -> None:
        if not error_code or len(error_code) > 64:
            raise ValueError("Error code must contain 1 to 64 characters")

    @staticmethod
    def _validate_limit(limit: int) -> None:
        if type(limit) is not int or limit < 1 or limit > 1000:
            raise ValueError("Query limit must be between 1 and 1000")

    @staticmethod
    def _validate_workspace(workspace: db_models.Workspace) -> None:
        if workspace.provisioner not in {"docker", "kubernetes"}:
            raise ValueError("Workspace provisioner must be docker or kubernetes")
        if workspace.knowledge_base_mount_desired_revision < 0:
            raise ValueError("Workspace mount revision must not be negative")

    @staticmethod
    def _validate_access_workspace(workspace: db_models.Workspace) -> None:
        if workspace.provisioner not in {"docker", "kubernetes"}:
            raise ValueError("Workspace provisioner must be docker or kubernetes")
        if workspace.runtime_access_revision < 0:
            raise ValueError("Workspace access revision must not be negative")

    @staticmethod
    def _validate_correlation_id(correlation_id: str) -> None:
        if not correlation_id or len(correlation_id) > 64:
            raise ValueError("Correlation identifier must contain 1 to 64 characters")

    @staticmethod
    def _validate_mount_job_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
        unknown_keys = set(metadata) - set(_MOUNT_JOB_METADATA_TYPES)
        if unknown_keys:
            raise ValueError("Mount job metadata contains unsupported keys")

        validated: dict[str, Any] = {}
        for key, value in metadata.items():
            expected_type = _MOUNT_JOB_METADATA_TYPES[key]
            if type(value) is not expected_type:
                raise ValueError("Mount job metadata contains an invalid value type")
            if isinstance(value, str) and (not value or len(value) > 64):
                raise ValueError(
                    "Mount job metadata strings must contain 1 to 64 characters"
                )
            if key == "attempt" and isinstance(value, int) and value < 0:
                raise ValueError("Mount job attempt must not be negative")
            validated[key] = value
        return validated

    @staticmethod
    def _validate_access_recycle_job_metadata(
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        unknown_keys = set(metadata) - set(_ACCESS_RECYCLE_JOB_METADATA_TYPES)
        if unknown_keys:
            raise ValueError("Access recycle job metadata contains unsupported keys")

        validated: dict[str, Any] = {}
        for key, value in metadata.items():
            expected_type = _ACCESS_RECYCLE_JOB_METADATA_TYPES[key]
            if type(value) is not expected_type:
                raise ValueError("Access recycle job metadata is invalid")
            if isinstance(value, str) and (not value or len(value) > 64):
                raise ValueError("Access recycle metadata strings are invalid")
            if key == "attempt" and isinstance(value, int) and value < 0:
                raise ValueError("Access recycle attempt must not be negative")
            validated[key] = value
        return validated

    @staticmethod
    def _validate_lifecycle_operation(operation: str) -> None:
        if operation not in WORKSPACE_LIFECYCLE_OPERATIONS:
            raise ValueError("Workspace lifecycle operation is invalid")

    @staticmethod
    def _validate_lifecycle_job_metadata(
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        supported_keys = {
            "attempt",
            "intent",
            "phase",
            "requires_stop",
            "stop_confirmed",
        }
        if set(metadata) - supported_keys:
            raise ValueError("Lifecycle job metadata contains unsupported keys")
        attempt = metadata.get("attempt", 0)
        if type(attempt) is not int or attempt < 0:
            raise ValueError("Lifecycle job attempt must not be negative")
        intent = metadata.get("intent")
        if intent is not None and intent not in {"rebuild", "delete"}:
            raise ValueError("Lifecycle job intent is invalid")
        phase = metadata.get("phase")
        if phase is not None and (
            not isinstance(phase, str) or phase not in WORKSPACE_DELETE_PHASES
        ):
            raise ValueError("Lifecycle job phase is invalid")
        for key in ("requires_stop", "stop_confirmed"):
            value = metadata.get(key)
            if value is not None and type(value) is not bool:
                raise ValueError("Lifecycle deletion state is invalid")
        validated = {"attempt": attempt} if "attempt" in metadata else {}
        if intent is not None:
            validated["intent"] = intent
        if phase is not None:
            validated["phase"] = phase
        for key in ("requires_stop", "stop_confirmed"):
            if key in metadata:
                validated[key] = metadata[key]
        return validated
