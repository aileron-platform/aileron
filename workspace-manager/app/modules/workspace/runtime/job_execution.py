"""Own durable Workspace Runtime Job execution state transitions."""

from __future__ import annotations

from collections.abc import Collection, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import Event, Lock, Thread
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker
from typing_extensions import Self

from app.db import models as db_models
from app.modules.workspace.advisory_lock import (
    WorkspaceSessionAdvisoryLock,
    acquire_workspace_transaction_lock,
)
from app.modules.workspace.runtime.job_repository import (
    COMPONENT_OPERATIONS,
    WorkspaceRuntimeJobRepository,
)


class WorkspaceRuntimeJobRunResult(str, Enum):
    """Stable worker outcome used by Workspace job dispatch and recovery."""

    NOT_CLAIMED = "not_claimed"
    SUCCEEDED = "succeeded"
    SUPERSEDED = "superseded"
    FAILED = "failed"
    CLAIM_LOST = "claim_lost"


class RuntimeJobClaimLostError(RuntimeError):
    """The worker lease or session lock is no longer valid."""

    code = "WORKSPACE_RUNTIME_CLAIM_LOST"


class RuntimeJobClaimLease:
    """Renew a claim in short transactions while external I/O is running."""

    def __init__(
        self,
        *,
        bind: Engine | Connection,
        job_id: str,
        claim_token: str,
        timeout_seconds: int,
    ) -> None:
        self._session_factory = sessionmaker(bind=bind, expire_on_commit=False)
        self._job_id = job_id
        self._claim_token = claim_token
        self._timeout_seconds = timeout_seconds
        self._interval_seconds = max(1.0, timeout_seconds / 4)
        self._stop = Event()
        self._lost = Event()
        self._mutex = Lock()
        self._thread: Thread | None = None
        self._background_enabled = bind.dialect.name == "postgresql"

    def __enter__(self) -> Self:
        self.heartbeat_once()
        if self._background_enabled:
            self._thread = Thread(
                target=self._run,
                name=f"workspace-job-heartbeat-{self._job_id}",
                daemon=True,
            )
            self._thread.start()
        return self

    def __exit__(
        self,
        _exc_type: object,
        _exc: object,
        _traceback: object,
    ) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval_seconds + 1)

    def assert_valid(self, session_lock: WorkspaceSessionAdvisoryLock) -> None:
        session_lock.assert_owned()
        if self._lost.is_set():
            raise RuntimeJobClaimLostError("Workspace runtime job claim was lost")
        self.heartbeat_once()

    def heartbeat_once(self) -> None:
        with self._mutex:
            if self._lost.is_set():
                raise RuntimeJobClaimLostError("Workspace runtime job claim was lost")
            now = datetime.now(timezone.utc)
            db = self._session_factory()
            try:
                renewed = WorkspaceRuntimeJobRepository(db).heartbeat_running_job(
                    job_id=self._job_id,
                    claim_token=self._claim_token,
                    heartbeat_at=now,
                    claim_expires_at=now + timedelta(seconds=self._timeout_seconds),
                )
                if not renewed:
                    db.rollback()
                    self._lost.set()
                    raise RuntimeJobClaimLostError(
                        "Workspace runtime job claim was lost"
                    )
                db.commit()
            except RuntimeJobClaimLostError:
                raise
            except Exception as exc:
                db.rollback()
                self._lost.set()
                raise RuntimeJobClaimLostError(
                    "Workspace runtime job heartbeat failed"
                ) from exc
            finally:
                db.close()

    def _run(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self.heartbeat_once()
            except RuntimeJobClaimLostError:
                return


def normalize_utc(value: datetime) -> datetime:
    """Return an aware UTC timestamp for database lease comparisons."""

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class JobExecutionOutcome(str, Enum):
    """Observable outcome of a durable job state transition."""

    CLAIMED = "claimed"
    NOT_CLAIMED = "not_claimed"
    SUPERSEDED = "superseded"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CLAIM_LOST = "claim_lost"


class JobTerminalState(str, Enum):
    """Terminal state requested for a queued or claimed job."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class ComponentJobClaim:
    """Immutable component job claim used across external side effects."""

    job_id: str
    workspace_id: str
    component: str
    target_revision: int
    claim_token: str


@dataclass(frozen=True)
class ComponentClaimResult:
    """Claim result without exposing persistence transition primitives."""

    outcome: JobExecutionOutcome
    claim: ComponentJobClaim | None = None


class WorkspaceRuntimeJobExecution:
    """Execute claim-fenced job transitions behind one state-machine interface."""

    def __init__(self, db: Session, *, claim_timeout_seconds: int) -> None:
        self.db = db
        self.claim_timeout_seconds = claim_timeout_seconds
        self._jobs = WorkspaceRuntimeJobRepository(db)

    def claim_component(
        self,
        job_id: str,
        *,
        claimed_at: datetime,
    ) -> ComponentClaimResult:
        """Claim a current component revision or terminally supersede stale work."""

        claim_token = str(uuid4())
        try:
            job = self.db.scalar(
                select(db_models.WorkspaceRuntimeJob)
                .where(db_models.WorkspaceRuntimeJob.id == job_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if (
                job is None
                or job.operation not in COMPONENT_OPERATIONS
                or job.target_component is None
                or job.target_revision is None
            ):
                self.db.rollback()
                return ComponentClaimResult(JobExecutionOutcome.NOT_CLAIMED)

            acquire_workspace_transaction_lock(self.db, job.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == job.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return ComponentClaimResult(JobExecutionOutcome.NOT_CLAIMED)

            desired_revision = int(
                getattr(workspace, f"{job.target_component}_desired_revision")
            )
            if job.target_revision != desired_revision:
                self._jobs.supersede_queued_job(
                    job_id=job.id,
                    finished_at=claimed_at,
                )
                self.db.commit()
                return ComponentClaimResult(JobExecutionOutcome.SUPERSEDED)

            claimed = self._jobs.claim_queued_job(
                job_id=job.id,
                claim_token=claim_token,
                claimed_at=claimed_at,
                claim_expires_at=claimed_at
                + timedelta(seconds=self.claim_timeout_seconds),
                eligible_runtime_statuses={"running", "restarting"},
            )
            if claimed is None:
                self.db.rollback()
                return ComponentClaimResult(JobExecutionOutcome.NOT_CLAIMED)
            claimed_component = claimed.target_component
            claimed_revision = claimed.target_revision
            if claimed_component is None or claimed_revision is None:
                self.db.rollback()
                return ComponentClaimResult(JobExecutionOutcome.NOT_CLAIMED)

            claim = ComponentJobClaim(
                job_id=claimed.id,
                workspace_id=workspace.id,
                component=claimed_component,
                target_revision=claimed_revision,
                claim_token=claim_token,
            )
            self.db.commit()
            return ComponentClaimResult(JobExecutionOutcome.CLAIMED, claim)
        except Exception:
            self.db.rollback()
            raise

    def claim_revision(
        self,
        job_id: str,
        *,
        claimed_at: datetime,
        eligible_runtime_statuses: Collection[str],
    ) -> tuple[db_models.WorkspaceRuntimeJob | None, str]:
        """Claim revision-owned work with the configured lease policy."""

        claim_token = str(uuid4())
        claimed = self._jobs.claim_queued_job(
            job_id=job_id,
            claim_token=claim_token,
            claimed_at=claimed_at,
            claim_expires_at=claimed_at + timedelta(seconds=self.claim_timeout_seconds),
            eligible_runtime_statuses=eligible_runtime_statuses,
        )
        return claimed, claim_token

    def finish_claim(
        self,
        *,
        job_id: str,
        claim_token: str,
        state: JobTerminalState,
        finished_at: datetime,
        error_code: str | None = None,
    ) -> bool:
        """Apply one terminal transition without exposing persistence primitives."""

        if state == JobTerminalState.SUCCEEDED:
            return self._jobs.complete_running_job(
                job_id=job_id,
                claim_token=claim_token,
                finished_at=finished_at,
            )
        if state == JobTerminalState.FAILED:
            if error_code is None:
                raise ValueError("Failed job transition requires an error code")
            return self._jobs.fail_running_job(
                job_id=job_id,
                claim_token=claim_token,
                finished_at=finished_at,
                error_code=error_code,
            )
        return self._jobs.supersede_running_job(
            job_id=job_id,
            claim_token=claim_token,
            finished_at=finished_at,
        )

    def finish_queued(
        self,
        *,
        job_id: str,
        state: JobTerminalState,
        finished_at: datetime,
        error_code: str | None = None,
    ) -> bool:
        """Terminally transition unclaimed work."""

        if state == JobTerminalState.SUPERSEDED:
            return self._jobs.supersede_queued_job(
                job_id=job_id,
                finished_at=finished_at,
            )
        if state != JobTerminalState.FAILED or error_code is None:
            raise ValueError("Queued job transition must fail or supersede")
        return self._jobs.fail_queued_job(
            job_id=job_id,
            finished_at=finished_at,
            error_code=error_code,
        )

    def supersede_revision(
        self,
        *,
        job_id: str,
        claim_token: str,
        target_revision: int,
        target_runtime_instance_id: str | None,
        correlation_id: str,
        scheduled_at: datetime,
    ) -> (
        tuple[
            db_models.WorkspaceRuntimeJob,
            db_models.WorkspaceRuntimeJob,
            bool,
        ]
        | None
    ):
        """Supersede a stale revision while preserving its current successor."""

        return self._jobs.supersede_running_and_preserve_successor(
            job_id=job_id,
            claim_token=claim_token,
            target_revision=target_revision,
            target_runtime_instance_id=target_runtime_instance_id,
            correlation_id=correlation_id,
            scheduled_at=scheduled_at,
        )

    @contextmanager
    def lease(
        self,
        *,
        job_id: str,
        claim_token: str,
        session_lock: WorkspaceSessionAdvisoryLock | None = None,
    ) -> Iterator[Callable[[], None]]:
        """Keep a claim alive and expose only its assertion operation."""

        with RuntimeJobClaimLease(
            bind=self.db.get_bind(),
            job_id=job_id,
            claim_token=claim_token,
            timeout_seconds=self.claim_timeout_seconds,
        ) as claim_lease:

            def assert_claim() -> None:
                if session_lock is None:
                    claim_lease.heartbeat_once()
                else:
                    claim_lease.assert_valid(session_lock)

            yield assert_claim

    def complete_component(
        self,
        claim: ComponentJobClaim,
        *,
        finished_at: datetime,
        apply_result: Callable[[db_models.Workspace], None],
    ) -> JobExecutionOutcome:
        """Fence, persist, and publish one component execution result."""

        try:
            acquire_workspace_transaction_lock(self.db, claim.workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == claim.workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if workspace is None:
                self.db.rollback()
                return JobExecutionOutcome.NOT_CLAIMED

            desired_revision = int(
                getattr(workspace, f"{claim.component}_desired_revision")
            )
            if desired_revision != claim.target_revision:
                if not self._jobs.supersede_running_job(
                    job_id=claim.job_id,
                    claim_token=claim.claim_token,
                    finished_at=finished_at,
                ):
                    self.db.rollback()
                    return JobExecutionOutcome.CLAIM_LOST
                self.db.commit()
                return JobExecutionOutcome.SUPERSEDED

            if not self._jobs.complete_running_job(
                job_id=claim.job_id,
                claim_token=claim.claim_token,
                finished_at=finished_at,
            ):
                self.db.rollback()
                return JobExecutionOutcome.CLAIM_LOST

            apply_result(workspace)
            setattr(
                workspace,
                f"{claim.component}_observed_revision",
                claim.target_revision,
            )
            setattr(workspace, f"{claim.component}_status", "running")
            setattr(workspace, f"{claim.component}_reason", None)
            setattr(workspace, f"{claim.component}_error_code", None)
            setattr(
                workspace,
                f"{claim.component}_last_transition_at",
                finished_at,
            )
            self.db.commit()
            return JobExecutionOutcome.SUCCEEDED
        except Exception:
            self.db.rollback()
            raise

    def fail_component(
        self,
        claim: ComponentJobClaim,
        *,
        failed_at: datetime,
        error_code: str,
    ) -> JobExecutionOutcome:
        """Fail a claimed component job and its observable component state."""

        self.db.rollback()
        try:
            job = self.db.get(db_models.WorkspaceRuntimeJob, claim.job_id)
            if (
                job is None
                or job.status != "running"
                or job.claim_token != claim.claim_token
            ):
                self.db.rollback()
                return JobExecutionOutcome.CLAIM_LOST
            if not self._jobs.fail_running_job(
                job_id=claim.job_id,
                claim_token=claim.claim_token,
                finished_at=failed_at,
                error_code=error_code,
            ):
                self.db.rollback()
                return JobExecutionOutcome.CLAIM_LOST
            workspace = self.db.get(db_models.Workspace, claim.workspace_id)
            if workspace is not None:
                setattr(workspace, f"{claim.component}_status", "error")
                setattr(workspace, f"{claim.component}_error_code", error_code)
                setattr(
                    workspace,
                    f"{claim.component}_last_transition_at",
                    failed_at,
                )
            self.db.commit()
            return JobExecutionOutcome.FAILED
        except Exception:
            self.db.rollback()
            raise
