"""Single transaction path for automation jobs and aggregate projections."""

from __future__ import annotations

import copy
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import and_, case, exists, false, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor

MAX_QUEUED_EXECUTIONS = 10
WEBHOOK_DUMMY_SECRET = "automation-webhook-dummy-secret"


def _authorization_service(db: Session):
    """Load the service lazily so repositories remain import-cycle free."""

    from app.modules.automation.authorization import (
        AutomationAuthorizationService,
    )

    return AutomationAuthorizationService(db)


def _schedule_service():
    """Load schedule policy lazily at the transaction call site."""

    from app.modules.automation.schedules import AutomationScheduleService

    return AutomationScheduleService()


class AutomationRepositoryError(RuntimeError):
    """Stable Automation repository failure."""

    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class AutomationWorkspaceDeletionError(AutomationRepositoryError):
    """Stable failure while converging executions before Workspace deletion."""

    def __init__(
        self,
        *,
        phase: str,
        execution_id: str | None = None,
    ) -> None:
        super().__init__("WORKSPACE_AUTOMATION_CANCELLATION_UNCONFIRMED", 409)
        self.phase = phase
        self.execution_id = execution_id


@dataclass(frozen=True)
class JobProjection:
    job: db_models.AutomationJob
    creator_display_name: str
    total_executions: int = 0
    successful_executions: int = 0
    average_duration: float = 0.0
    last_run_at: datetime | None = None
    last_duration: int | None = None


@dataclass(frozen=True)
class RunningCancellation:
    """Committed Runtime cancellation intent."""

    execution_id: str
    workspace_id: str
    runtime_url: str
    runner_instance_id: str
    claim_request_id: str


@dataclass(frozen=True)
class WorkspaceDeletionConvergencePlan:
    """Committed execution state and Runtime cancellation intents for deletion."""

    workspace_id: str
    queued_execution_ids: tuple[str, ...]
    running_execution_ids: tuple[str, ...]
    running_cancellations: tuple[RunningCancellation, ...]


class AutomationRepository:
    """Own all automation job locking, writes, and aggregate queries."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._committed_running_cancellations: list[RunningCancellation] = []

    def transaction_now(self) -> datetime:
        value = self.db.scalar(select(func.now()))
        if value is None:
            value = datetime.now(timezone.utc)
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def create_job(self, values: dict[str, Any]) -> db_models.AutomationJob:
        job = db_models.AutomationJob(**values)
        self.db.add(job)
        self.db.flush()
        return job

    def enqueue_manual(
        self, *, job_id: str, actor: AuthorizationActor
    ) -> db_models.AutomationExecution:
        """Serialize and enqueue an actor-requested execution."""
        try:
            job = self._require_locked_job(job_id)
            authorization = _authorization_service(self.db)
            authorization.require_execute(actor=actor, workspace_id=job.workspace_id)
            authorization.require_creator_execute(
                user_id=job.creator_user_id, workspace_id=job.workspace_id
            )
            now = self.transaction_now()
            execution = self._enqueue_queued(job=job, trigger="manual", now=now)
            self.db.commit()
            return execution
        except Exception:
            self.db.rollback()
            raise

    def enqueue_webhook(
        self, *, job_id: str, presented_key: SecretStr
    ) -> db_models.AutomationExecution:
        """Authenticate and enqueue a webhook execution without user identity."""
        try:
            job = self.lock_job(job_id)
            configured_key = (
                (job.notification_config or {}).get("webhook_api_key")
                if job is not None
                else None
            )
            expected_key = configured_key or WEBHOOK_DUMMY_SECRET
            valid_key = secrets.compare_digest(
                presented_key.get_secret_value(), expected_key
            )
            if job is None or configured_key is None or not valid_key:
                raise AutomationRepositoryError("automation_webhook_unauthorized", 401)
            _authorization_service(self.db).require_creator_execute(
                user_id=job.creator_user_id, workspace_id=job.workspace_id
            )
            if job.status == "paused":
                raise AutomationRepositoryError("automation_job_paused", 409)
            now = self.transaction_now()
            execution = self._enqueue_queued(job=job, trigger="webhook", now=now)
            self.db.commit()
            return execution
        except Exception:
            self.db.rollback()
            raise

    def enqueue_scheduled_occurrence(
        self, *, job_id: str, expected_scheduled_for: datetime
    ) -> db_models.AutomationExecution | None:
        """Enqueue one stored due occurrence and coalesce all older schedule ticks."""
        self._committed_running_cancellations = []
        try:
            identity = self.db.execute(
                select(
                    db_models.AutomationJob.creator_user_id,
                    db_models.AutomationJob.workspace_id,
                ).where(
                    db_models.AutomationJob.id == job_id,
                    db_models.AutomationJob.deleted_at.is_(None),
                )
            ).one_or_none()
            if identity is None:
                self.db.rollback()
                return None
            principal_user_id, identity_workspace_id = identity
            self._lock_principal_row(principal_user_id=principal_user_id)
            job = self.lock_job(job_id)
            if (
                job is None
                or job.creator_user_id != principal_user_id
                or job.workspace_id != identity_workspace_id
            ):
                self.db.rollback()
                return None
            now = self.transaction_now()
            expected = self._utc(expected_scheduled_for)
            current_due = self._utc(job.next_run_at) if job.next_run_at else None
            if (
                job.status != "active"
                or current_due is None
                or current_due != expected
                or current_due > now
            ):
                self.db.rollback()
                return None
            try:
                _authorization_service(self.db).require_creator_execute(
                    user_id=job.creator_user_id, workspace_id=job.workspace_id
                )
            except HTTPException:
                cancellations = self._converge_principal_authorization_in_transaction(
                    principal_user_id=job.creator_user_id,
                    workspace_id=job.workspace_id,
                )
                self.db.flush()
                self.db.commit()
                self._committed_running_cancellations = cancellations
                return None
            if job.trigger == "at":
                job.status = "completed"
                job.next_run_at = None
            else:
                job.next_run_at = _schedule_service().next_strictly_after(
                    trigger=job.trigger,
                    schedule=job.schedule,
                    exact=job.exact,
                    reference=now,
                )
            job.updated_at = now
            if self._queued_count(job.id) >= MAX_QUEUED_EXECUTIONS:
                execution = self._new_execution(
                    job=job,
                    trigger=job.trigger,
                    scheduled_for=expected,
                    status="failed",
                    queued_at=None,
                    finished_at=now,
                    error_code="queue_full",
                )
            else:
                execution = self._new_execution(
                    job=job,
                    trigger=job.trigger,
                    scheduled_for=expected,
                    status="queued",
                    queued_at=now,
                )
            self.db.add(execution)
            self.db.flush()
            self.db.commit()
            return execution
        except HTTPException:
            self.db.rollback()
            self._committed_running_cancellations = []
            raise
        except Exception:
            self.db.rollback()
            self._committed_running_cancellations = []
            raise

    def get_execution_for_actor(
        self, *, execution_id: str, actor: AuthorizationActor
    ) -> db_models.AutomationExecution:
        execution = self.db.get(db_models.AutomationExecution, execution_id)
        if execution is None:
            raise AutomationRepositoryError("automation_execution_not_found", 404)
        _authorization_service(self.db).require_read(
            actor=actor, workspace_id=execution.workspace_id
        )
        return execution

    def list_job_executions(
        self,
        *,
        job_id: str,
        actor: AuthorizationActor,
        page: int,
        page_size: int,
        range_start: datetime | None = None,
        range_end: datetime | None = None,
    ) -> tuple[list[db_models.AutomationExecution], int]:
        job = self.db.get(db_models.AutomationJob, job_id)
        if job is None:
            raise AutomationRepositoryError("automation_job_not_found", 404)
        _authorization_service(self.db).require_read(
            actor=actor, workspace_id=job.workspace_id
        )
        occurred_at = func.coalesce(
            db_models.AutomationExecution.started_at,
            db_models.AutomationExecution.queued_at,
            db_models.AutomationExecution.scheduled_for,
        )
        filters = [db_models.AutomationExecution.job_id == job_id]
        if range_start is not None:
            filters.append(occurred_at >= range_start)
        if range_end is not None:
            filters.append(occurred_at <= range_end)
        total = (
            self.db.scalar(
                select(func.count())
                .select_from(db_models.AutomationExecution)
                .where(*filters)
            )
            or 0
        )
        items = list(
            self.db.scalars(
                select(db_models.AutomationExecution)
                .where(*filters)
                .order_by(
                    db_models.AutomationExecution.scheduled_for.desc(),
                    db_models.AutomationExecution.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return items, total

    def list_executions_for_actor(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str | None,
        limit: int,
    ) -> list[db_models.AutomationExecution]:
        authorization = _authorization_service(self.db)
        if workspace_id is not None:
            authorization.require_read(actor=actor, workspace_id=workspace_id)
            workspace_ids = [workspace_id]
        else:
            workspace_ids = authorization.accessible_workspace_ids(actor=actor)
        scope = (
            db_models.AutomationExecution.workspace_id.in_(workspace_ids)
            if workspace_ids
            else false()
        )
        return list(
            self.db.scalars(
                select(db_models.AutomationExecution)
                .where(scope)
                .order_by(
                    db_models.AutomationExecution.scheduled_for.desc(),
                    db_models.AutomationExecution.id.desc(),
                )
                .limit(limit)
            )
        )

    def list_due_occurrences(self) -> list[tuple[str, datetime]]:
        now = self.transaction_now()
        return list(
            self.db.execute(
                select(
                    db_models.AutomationJob.id,
                    db_models.AutomationJob.next_run_at,
                )
                .where(
                    db_models.AutomationJob.status == "active",
                    db_models.AutomationJob.deleted_at.is_(None),
                    db_models.AutomationJob.next_run_at.is_not(None),
                    db_models.AutomationJob.next_run_at <= now,
                )
                .order_by(
                    db_models.AutomationJob.next_run_at,
                    db_models.AutomationJob.id,
                )
            )
        )

    def claim_execution(
        self,
        *,
        workspace_id: str,
        runner_instance_id: UUID,
        claim_request_id: UUID,
    ) -> db_models.AutomationExecution | None:
        """Claim the globally oldest eligible per-job FIFO head."""
        runner_value = str(runner_instance_id)
        request_value = str(claim_request_id)
        pending_cancellations: list[RunningCancellation] = []
        self._committed_running_cancellations = []
        try:
            existing = self.db.scalar(
                select(db_models.AutomationExecution).where(
                    db_models.AutomationExecution.workspace_id == workspace_id,
                    db_models.AutomationExecution.claim_request_id == request_value,
                )
            )
            if existing is not None:
                if existing.runner_instance_id != runner_value:
                    raise AutomationRepositoryError("claim_request_conflict", 409)
                return existing

            queued = db_models.AutomationExecution
            earlier = db_models.AutomationExecution.__table__.alias("earlier_execution")
            running = db_models.AutomationExecution.__table__.alias("running_execution")
            candidates = list(
                self.db.scalars(
                    select(queued)
                    .where(
                        queued.workspace_id == workspace_id,
                        queued.status == "queued",
                        ~exists(
                            select(1).where(
                                earlier.c.job_id == queued.job_id,
                                earlier.c.status == "queued",
                                or_(
                                    earlier.c.scheduled_for < queued.scheduled_for,
                                    and_(
                                        earlier.c.scheduled_for == queued.scheduled_for,
                                        earlier.c.id < queued.id,
                                    ),
                                ),
                            )
                        ),
                        ~exists(
                            select(1).where(
                                running.c.job_id == queued.job_id,
                                running.c.status == "running",
                            )
                        ),
                    )
                    .order_by(queued.scheduled_for, queued.id)
                )
            )
            revoked_principal = False
            for candidate in candidates:
                principal_user_id = candidate.principal_user_id_snapshot
                self._lock_principal_row(principal_user_id=principal_user_id)
                existing = self.db.scalar(
                    select(db_models.AutomationExecution)
                    .where(
                        db_models.AutomationExecution.workspace_id == workspace_id,
                        db_models.AutomationExecution.claim_request_id == request_value,
                    )
                    .execution_options(populate_existing=True)
                )
                if existing is not None:
                    if existing.runner_instance_id != runner_value:
                        raise AutomationRepositoryError("claim_request_conflict", 409)
                    return existing
                job = self.db.scalar(
                    select(db_models.AutomationJob)
                    .where(
                        db_models.AutomationJob.id == candidate.job_id,
                        db_models.AutomationJob.deleted_at.is_(None),
                    )
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
                if job is None:
                    continue
                head = self.db.scalar(
                    select(db_models.AutomationExecution)
                    .where(
                        db_models.AutomationExecution.job_id == job.id,
                        db_models.AutomationExecution.status == "queued",
                    )
                    .order_by(
                        db_models.AutomationExecution.scheduled_for,
                        db_models.AutomationExecution.id,
                    )
                    .limit(1)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                if head is None or head.id != candidate.id:
                    continue
                if head.principal_user_id_snapshot != principal_user_id:
                    continue
                has_running = self.db.scalar(
                    select(func.count(db_models.AutomationExecution.id)).where(
                        db_models.AutomationExecution.job_id == job.id,
                        db_models.AutomationExecution.status == "running",
                    )
                )
                if has_running:
                    continue
                try:
                    _authorization_service(self.db).require_creator_execute(
                        user_id=head.principal_user_id_snapshot,
                        workspace_id=workspace_id,
                    )
                except HTTPException:
                    cancellations = (
                        self._converge_principal_authorization_in_transaction(
                            principal_user_id=principal_user_id,
                            workspace_id=workspace_id,
                            principal_locked=True,
                        )
                    )
                    pending_cancellations.extend(cancellations)
                    revoked_principal = True
                    continue
                now = self.transaction_now()
                head.status = "running"
                head.runner_instance_id = runner_value
                head.claim_request_id = request_value
                head.started_at = now
                head.updated_at = now
                self.db.flush()
                self.db.commit()
                self._committed_running_cancellations = pending_cancellations
                return head
            if revoked_principal:
                self.db.commit()
                self._committed_running_cancellations = pending_cancellations
            else:
                self.db.rollback()
            return None
        except IntegrityError:
            self.db.rollback()
            self._committed_running_cancellations = []
            existing = self.db.scalar(
                select(db_models.AutomationExecution).where(
                    db_models.AutomationExecution.workspace_id == workspace_id,
                    db_models.AutomationExecution.claim_request_id == request_value,
                )
            )
            if existing is None:
                raise
            if existing.runner_instance_id != runner_value:
                raise AutomationRepositoryError("claim_request_conflict", 409)
            return existing
        except Exception:
            self.db.rollback()
            self._committed_running_cancellations = []
            raise

    def complete_execution(
        self,
        *,
        execution_id: str,
        runner_instance_id: UUID,
        claim_request_id: UUID,
        status: str,
        error_code: str | None,
        error_message: str | None,
    ) -> db_models.AutomationExecution:
        """Apply an owned running-to-terminal compare-and-set transition."""
        try:
            execution = self._require_locked_execution(execution_id)
            if execution.runner_instance_id != str(
                runner_instance_id
            ) or execution.claim_request_id != str(claim_request_id):
                raise AutomationRepositoryError("execution_not_owned", 409)
            if execution.status in {"success", "failed", "cancelled"}:
                if (
                    execution.status == "failed"
                    and execution.error_code == "runner_restarted"
                ):
                    raise AutomationRepositoryError("execution_already_terminal", 409)
                if (
                    execution.status == status
                    and execution.error_code == error_code
                    and execution.error_message == error_message
                ):
                    execution._terminal_transition_won = False
                    self.db.commit()
                    return execution
                raise AutomationRepositoryError("execution_already_terminal", 409)
            if execution.status != "running":
                raise AutomationRepositoryError("execution_invalid_transition", 409)
            if status == "failed" and error_code == "runner_restarted":
                raise AutomationRepositoryError("execution_invalid_transition", 409)
            if execution.cancel_requested_at is not None and status != "cancelled":
                raise AutomationRepositoryError("execution_cancel_requested", 409)
            now = self.transaction_now()
            execution.status = status
            execution.error_code = error_code
            execution.error_message = error_message
            execution.finished_at = now
            execution.updated_at = now
            execution._terminal_transition_won = True
            self.db.flush()
            self.db.commit()
            return execution
        except Exception:
            self.db.rollback()
            raise

    def cancel_execution(
        self, *, execution_id: str, actor: AuthorizationActor
    ) -> db_models.AutomationExecution:
        """Commit queued cancellation or a running cancellation intent."""
        try:
            execution = self._require_locked_execution(execution_id)
            _authorization_service(self.db).require_execute(
                actor=actor, workspace_id=execution.workspace_id
            )
            if execution.status in {"success", "failed", "cancelled"}:
                self.db.commit()
                return execution
            now = self.transaction_now()
            if execution.status == "queued":
                execution.status = "cancelled"
                execution.finished_at = now
            elif (
                execution.status == "running" and execution.cancel_requested_at is None
            ):
                execution.cancel_requested_at = now
            execution.updated_at = now
            self.db.flush()
            self.db.commit()
            return execution
        except Exception:
            self.db.rollback()
            raise

    def reconcile_restart(
        self, *, workspace_id: str, new_runner_instance_id: UUID
    ) -> list[db_models.AutomationExecution]:
        """Terminalize only running rows owned by older Runtime instances."""
        try:
            executions = list(
                self.db.scalars(
                    select(db_models.AutomationExecution)
                    .where(
                        db_models.AutomationExecution.workspace_id == workspace_id,
                        db_models.AutomationExecution.status == "running",
                        db_models.AutomationExecution.runner_instance_id
                        != str(new_runner_instance_id),
                    )
                    .order_by(db_models.AutomationExecution.id)
                    .with_for_update()
                )
            )
            now = self.transaction_now()
            for execution in executions:
                execution.status = "failed"
                execution.error_code = "runner_restarted"
                execution.error_message = None
                execution.finished_at = now
                execution.updated_at = now
                execution._terminal_transition_won = True
            self.db.flush()
            self.db.commit()
            return executions
        except Exception:
            self.db.rollback()
            raise

    def queue_position(self, execution_id: str) -> int | None:
        execution = self.db.get(db_models.AutomationExecution, execution_id)
        if execution is None or execution.status != "queued":
            return None
        ahead = self.db.scalar(
            select(func.count(db_models.AutomationExecution.id)).where(
                db_models.AutomationExecution.job_id == execution.job_id,
                db_models.AutomationExecution.status == "queued",
                or_(
                    db_models.AutomationExecution.scheduled_for
                    < execution.scheduled_for,
                    and_(
                        db_models.AutomationExecution.scheduled_for
                        == execution.scheduled_for,
                        db_models.AutomationExecution.id < execution.id,
                    ),
                ),
            )
        )
        return int(ahead or 0) + 1

    def update_notification_status(
        self, *, execution_id: str, notification_status: str
    ) -> None:
        self.db.execute(
            update(db_models.AutomationExecution)
            .where(db_models.AutomationExecution.id == execution_id)
            .values(notification_status=notification_status)
        )
        self.db.commit()

    def converge_principal_authorization(
        self, *, principal_user_id: str, workspace_id: str | None = None
    ) -> list[RunningCancellation]:
        """Commit authorization convergence and return running cancel intents."""
        try:
            cancellations = self.converge_principal_authorization_in_transaction(
                principal_user_id=principal_user_id,
                workspace_id=workspace_id,
            )
            self.db.commit()
            return cancellations
        except Exception:
            self.db.rollback()
            raise

    def converge_principal_authorization_in_transaction(
        self,
        *,
        principal_user_id: str,
        workspace_id: str | None = None,
    ) -> list[RunningCancellation]:
        """Converge DB authorization while leaving commit to the caller."""

        cancellations = self._converge_principal_authorization_in_transaction(
            principal_user_id=principal_user_id,
            workspace_id=workspace_id,
        )
        self.db.flush()
        return cancellations

    def converge_workspace_deletion(
        self, *, workspace_id: str
    ) -> WorkspaceDeletionConvergencePlan:
        """Commit cancellation intents for every non-terminal Workspace execution."""
        try:
            plan = self.converge_workspace_deletion_in_transaction(
                workspace_id=workspace_id
            )
            self.db.commit()
            return plan
        except Exception:
            self.db.rollback()
            raise

    def converge_workspace_deletion_in_transaction(
        self, *, workspace_id: str
    ) -> WorkspaceDeletionConvergencePlan:
        """Prepare Workspace deletion convergence without committing the caller."""
        workspace = self.db.scalar(
            select(db_models.Workspace)
            .where(db_models.Workspace.id == workspace_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if workspace is None:
            raise AutomationRepositoryError("workspace_not_found", 404)

        jobs = list(
            self.db.scalars(
                select(db_models.AutomationJob)
                .where(
                    db_models.AutomationJob.workspace_id == workspace_id,
                    db_models.AutomationJob.deleted_at.is_(None),
                    db_models.AutomationJob.status == "active",
                )
                .order_by(db_models.AutomationJob.id)
                .with_for_update()
            )
        )
        now = self.transaction_now()
        for job in jobs:
            job.status = "paused"
            job.next_run_at = None
            job.updated_at = now

        executions = list(
            self.db.scalars(
                select(db_models.AutomationExecution)
                .where(db_models.AutomationExecution.workspace_id == workspace_id)
                .order_by(db_models.AutomationExecution.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        queued_execution_ids: list[str] = []
        running_execution_ids: list[str] = []
        cancellations: list[RunningCancellation] = []
        runtime_url = workspace.runtime_internal_url

        for execution in executions:
            if execution.status == "queued":
                execution.status = "cancelled"
                execution.error_code = "authorization_revoked"
                execution.finished_at = now
                execution.updated_at = now
                queued_execution_ids.append(execution.id)
                continue
            if execution.status != "running":
                continue

            running_execution_ids.append(execution.id)
            if execution.cancel_requested_at is None:
                execution.cancel_requested_at = now
                execution.updated_at = now
            cancellations.append(
                RunningCancellation(
                    execution_id=execution.id,
                    workspace_id=workspace_id,
                    runtime_url=runtime_url or "",
                    runner_instance_id=execution.runner_instance_id or "",
                    claim_request_id=execution.claim_request_id or "",
                )
            )

        self.db.flush()
        return WorkspaceDeletionConvergencePlan(
            workspace_id=workspace_id,
            queued_execution_ids=tuple(queued_execution_ids),
            running_execution_ids=tuple(running_execution_ids),
            running_cancellations=tuple(cancellations),
        )

    def execution_statuses(self, *, execution_ids: tuple[str, ...]) -> dict[str, str]:
        """Read current execution statuses without relying on ORM identity state."""
        if not execution_ids:
            return {}
        rows = self.db.execute(
            select(
                db_models.AutomationExecution.id,
                db_models.AutomationExecution.status,
            ).where(db_models.AutomationExecution.id.in_(execution_ids))
        )
        return {row.id: row.status for row in rows}

    def take_committed_running_cancellations(self) -> list[RunningCancellation]:
        """Drain cancel intents committed by claim or scheduled enqueue."""
        cancellations = self._committed_running_cancellations
        self._committed_running_cancellations = []
        return cancellations

    def lock_job(self, job_id: str) -> db_models.AutomationJob | None:
        return self.db.scalar(
            select(db_models.AutomationJob)
            .where(
                db_models.AutomationJob.id == job_id,
                db_models.AutomationJob.deleted_at.is_(None),
            )
            .with_for_update()
        )

    def update_job(
        self, job: db_models.AutomationJob, values: dict[str, Any]
    ) -> db_models.AutomationJob:
        for key, value in values.items():
            setattr(job, key, value)
        self.db.flush()
        return job

    def has_active_executions(self, job_id: str) -> bool:
        return bool(
            self.db.scalar(
                select(func.count(db_models.AutomationExecution.id)).where(
                    db_models.AutomationExecution.job_id == job_id,
                    db_models.AutomationExecution.status.in_(["queued", "running"]),
                )
            )
        )

    def get_job(self, job_id: str) -> JobProjection | None:
        statement = self._projection_statement().where(
            db_models.AutomationJob.id == job_id,
            db_models.AutomationJob.deleted_at.is_(None),
        )
        row = self.db.execute(statement).one_or_none()
        return self._projection(row) if row else None

    def list_jobs(self, workspace_ids: list[str]) -> list[JobProjection]:
        scope = (
            db_models.AutomationJob.workspace_id.in_(workspace_ids)
            if workspace_ids
            else false()
        )
        rows = self.db.execute(
            self._projection_statement()
            .where(db_models.AutomationJob.deleted_at.is_(None), scope)
            .order_by(db_models.AutomationJob.created_at.desc())
        ).all()
        return [self._projection(row) for row in rows]

    def metrics(self, workspace_ids: list[str]) -> dict[str, int | float]:
        job_scope = (
            db_models.AutomationJob.workspace_id.in_(workspace_ids)
            if workspace_ids
            else false()
        )
        active_count, paused_count = self.db.execute(
            select(
                func.count(case((db_models.AutomationJob.status == "active", 1))),
                func.count(case((db_models.AutomationJob.status == "paused", 1))),
            ).where(db_models.AutomationJob.deleted_at.is_(None), job_scope)
        ).one()
        execution_scope = (
            db_models.AutomationExecution.workspace_id.in_(workspace_ids)
            if workspace_ids
            else false()
        )
        total, successes, failures, running, queued, average = self.db.execute(
            select(
                func.count(db_models.AutomationExecution.id),
                func.count(
                    case((db_models.AutomationExecution.status == "success", 1))
                ),
                func.count(case((db_models.AutomationExecution.status == "failed", 1))),
                func.count(
                    case((db_models.AutomationExecution.status == "running", 1))
                ),
                func.count(case((db_models.AutomationExecution.status == "queued", 1))),
                func.avg(self._duration_expression()),
            ).where(execution_scope)
        ).one()
        return {
            "activeCount": int(active_count or 0),
            "pausedCount": int(paused_count or 0),
            "failedCount": int(failures or 0),
            "draftCount": 0,
            "successRate": float(successes or 0) / int(total or 1),
            "runningExecutions": int(running or 0),
            "queuedExecutions": int(queued or 0),
            "averageDuration": round(float(average or 0.0), 3),
        }

    def calendar(self, workspace_ids: list[str]) -> list[dict[str, Any]]:
        scope = (
            db_models.AutomationExecution.workspace_id.in_(workspace_ids)
            if workspace_ids
            else false()
        )
        rows = self.db.execute(
            select(db_models.AutomationExecution, db_models.AutomationJob.name)
            .join(
                db_models.AutomationJob,
                db_models.AutomationJob.id == db_models.AutomationExecution.job_id,
            )
            .where(scope, db_models.AutomationJob.deleted_at.is_(None))
            .order_by(db_models.AutomationExecution.scheduled_for.desc())
        ).all()
        return [
            {
                "id": execution.id,
                "jobId": execution.job_id,
                "title": name,
                "start": execution.started_at or execution.scheduled_for,
                "end": execution.finished_at
                or execution.started_at
                or execution.scheduled_for,
                "status": execution.status,
            }
            for execution, name in rows
        ]

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def _require_locked_job(self, job_id: str) -> db_models.AutomationJob:
        job = self.lock_job(job_id)
        if job is None:
            raise AutomationRepositoryError("automation_job_not_found", 404)
        return job

    def _require_locked_execution(
        self, execution_id: str
    ) -> db_models.AutomationExecution:
        execution = self.db.scalar(
            select(db_models.AutomationExecution)
            .where(db_models.AutomationExecution.id == execution_id)
            .with_for_update()
        )
        if execution is None:
            raise AutomationRepositoryError("automation_execution_not_found", 404)
        return execution

    def _converge_principal_authorization_in_transaction(
        self,
        *,
        principal_user_id: str,
        workspace_id: str | None,
        principal_locked: bool = False,
    ) -> list[RunningCancellation]:
        if not principal_locked:
            self._lock_principal_row(principal_user_id=principal_user_id)
        job_scope = [
            db_models.AutomationJob.creator_user_id == principal_user_id,
            db_models.AutomationJob.deleted_at.is_(None),
        ]
        execution_scope = [
            db_models.AutomationExecution.principal_user_id_snapshot
            == principal_user_id,
            db_models.AutomationExecution.status.in_(["queued", "running"]),
        ]
        if workspace_id is not None:
            job_scope.append(db_models.AutomationJob.workspace_id == workspace_id)
            execution_scope.append(
                db_models.AutomationExecution.workspace_id == workspace_id
            )

        jobs = list(
            self.db.scalars(
                select(db_models.AutomationJob)
                .where(*job_scope)
                .order_by(db_models.AutomationJob.id)
                .with_for_update()
            )
        )
        now = self.transaction_now()
        for job in jobs:
            if job.status == "active":
                job.status = "paused"
                job.next_run_at = None
                job.updated_at = now

        executions = list(
            self.db.scalars(
                select(db_models.AutomationExecution)
                .where(*execution_scope)
                .order_by(db_models.AutomationExecution.id)
                .with_for_update()
            )
        )
        workspace_ids = {execution.workspace_id for execution in executions}
        workspaces = (
            {
                workspace.id: workspace
                for workspace in self.db.scalars(
                    select(db_models.Workspace).where(
                        db_models.Workspace.id.in_(workspace_ids)
                    )
                )
            }
            if workspace_ids
            else {}
        )
        cancellations: list[RunningCancellation] = []
        for execution in executions:
            if execution.status == "queued":
                execution.status = "cancelled"
                execution.error_code = "authorization_revoked"
                execution.finished_at = now
                execution.updated_at = now
                continue
            if execution.cancel_requested_at is None:
                execution.cancel_requested_at = now
                execution.updated_at = now
            workspace = workspaces.get(execution.workspace_id)
            runtime_url = (
                workspace.runtime_internal_url if workspace is not None else None
            )
            if (
                runtime_url
                and execution.runner_instance_id
                and execution.claim_request_id
            ):
                cancellations.append(
                    RunningCancellation(
                        execution_id=execution.id,
                        workspace_id=execution.workspace_id,
                        runtime_url=runtime_url,
                        runner_instance_id=execution.runner_instance_id,
                        claim_request_id=execution.claim_request_id,
                    )
                )
        return cancellations

    def _lock_principal_row(self, *, principal_user_id: str) -> None:
        """Serialize candidate and convergence locks by principal first."""
        self.db.scalar(
            select(db_models.User.id)
            .where(db_models.User.id == principal_user_id)
            .with_for_update()
        )

    def _enqueue_queued(
        self, *, job: db_models.AutomationJob, trigger: str, now: datetime
    ) -> db_models.AutomationExecution:
        workspace = self.db.get(db_models.Workspace, job.workspace_id)
        if workspace is not None and workspace.runtime_status == "deleting":
            raise AutomationRepositoryError("WORKSPACE_DELETING", 409)
        if self._queued_count(job.id) >= MAX_QUEUED_EXECUTIONS:
            raise AutomationRepositoryError("automation_queue_full", 409)
        execution = self._new_execution(
            job=job,
            trigger=trigger,
            scheduled_for=now,
            status="queued",
            queued_at=now,
        )
        self.db.add(execution)
        self.db.flush()
        return execution

    def _queued_count(self, job_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count(db_models.AutomationExecution.id)).where(
                    db_models.AutomationExecution.job_id == job_id,
                    db_models.AutomationExecution.status == "queued",
                )
            )
            or 0
        )

    @staticmethod
    def _new_execution(
        *,
        job: db_models.AutomationJob,
        trigger: str,
        scheduled_for: datetime,
        status: str,
        queued_at: datetime | None,
        finished_at: datetime | None = None,
        error_code: str | None = None,
    ) -> db_models.AutomationExecution:
        now = queued_at if queued_at is not None else finished_at
        return db_models.AutomationExecution(
            id=str(uuid4()),
            job_id=job.id,
            workspace_id=job.workspace_id,
            status=status,
            trigger=trigger,
            scheduled_for=scheduled_for,
            queued_at=queued_at,
            finished_at=finished_at,
            principal_user_id_snapshot=job.creator_user_id,
            prompt_snapshot=job.prompt,
            agentic_tool_snapshot=job.agentic_tool,
            model_snapshot=job.model,
            agent_config_snapshot=copy.deepcopy(job.agent_config),
            worktree_key_snapshot=job.worktree_key,
            error_code=error_code,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _projection_statement(self):
        latest_execution = aliased(db_models.AutomationExecution)
        last_duration = (
            select(self._duration_expression(latest_execution))
            .where(
                latest_execution.job_id == db_models.AutomationJob.id,
                latest_execution.started_at.is_not(None),
                latest_execution.finished_at.is_not(None),
            )
            .order_by(latest_execution.finished_at.desc(), latest_execution.id.desc())
            .limit(1)
            .correlate(db_models.AutomationJob)
            .scalar_subquery()
        )
        return (
            select(
                db_models.AutomationJob,
                db_models.User.display_name,
                func.count(db_models.AutomationExecution.id),
                func.count(
                    case((db_models.AutomationExecution.status == "success", 1))
                ),
                func.avg(self._duration_expression()),
                func.max(db_models.AutomationExecution.finished_at),
                last_duration,
            )
            .join(
                db_models.User,
                db_models.User.id == db_models.AutomationJob.creator_user_id,
            )
            .outerjoin(
                db_models.AutomationExecution,
                db_models.AutomationExecution.job_id == db_models.AutomationJob.id,
            )
            .group_by(db_models.AutomationJob.id, db_models.User.display_name)
        )

    def _duration_expression(
        self, execution_model: Any = db_models.AutomationExecution
    ):
        if self.db.bind is not None and self.db.bind.dialect.name == "sqlite":
            duration = (
                func.julianday(execution_model.finished_at)
                - func.julianday(execution_model.started_at)
            ) * 86400.0
        else:
            duration = func.extract(
                "epoch",
                execution_model.finished_at - execution_model.started_at,
            )
        return case(
            (
                execution_model.finished_at.is_not(None)
                & execution_model.started_at.is_not(None),
                duration,
            )
        )

    @staticmethod
    def _projection(row: Any) -> JobProjection:
        job, display_name, total, successful, average, last_run, last_duration = row
        return JobProjection(
            job=job,
            creator_display_name=display_name,
            total_executions=int(total or 0),
            successful_executions=int(successful or 0),
            average_duration=round(float(average or 0.0), 3),
            last_run_at=last_run,
            last_duration=(
                int(round(float(last_duration))) if last_duration is not None else None
            ),
        )


__all__ = [
    "AutomationRepository",
    "AutomationRepositoryError",
    "AutomationWorkspaceDeletionError",
    "JobProjection",
    "MAX_QUEUED_EXECUTIONS",
    "WorkspaceDeletionConvergencePlan",
]
