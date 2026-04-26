"""Automation service implementation: Responsible for automation task CRUD, execution records and statistics"""

from __future__ import annotations

import logging
import os
from contextlib import suppress
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from croniter import croniter
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from app.db import models as db_models
from app.utils.datetime_utils import calculate_duration, ensure_utc, utcnow
from app.models.automation import (
    AutomationJob,
    AutomationMetrics,
    ExecutionCancelResponse,
    JobBase,
    JobCalendarEvent,
    JobCalendarResponse,
    JobCreateRequest,
    JobExecution,
    JobExecutionListResponse,
    JobExecutionStatus,
    JobListResponse,
    JobStatus,
    JobStatusUpdate,
    JobTrigger,
    JobUpdateRequest,
    QueuePosition,
    WorkspaceQueueResponse,
)

logger = logging.getLogger(__name__)


def get_system_timezone() -> str:
    """
    Get system timezone settings

    Priority:
    1. Environment variable TZ
    2. Default value Asia/Taipei

    Returns:
        System timezone string, e.g. 'Asia/Taipei'
    """
    return os.getenv("TZ", "Asia/Taipei")


class AutomationJobError(Exception):
    """Automation task execution related errors"""

    def __init__(self, message: str, *, code: str = "AUTOMATION_ERROR", params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class JobNotFoundError(AutomationJobError):
    """Specified task does not exist"""


class JobNotRunnableError(AutomationJobError):
    """Task status does not allow execution"""


class JobDispatchError(AutomationJobError):
    """Cannot dispatch automation task"""


class AutomationService:
    """Manage automation tasks, execution records and statistics data"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Task CRUD
    # ------------------------------------------------------------------
    def list_tasks(self) -> JobListResponse:
        query: Select[tuple[db_models.AutomationJob, db_models.Workspace]] = (
            select(db_models.AutomationJob, db_models.Workspace)
            .join(
                db_models.Workspace,
                db_models.AutomationJob.workspace_id == db_models.Workspace.id,
                isouter=True,
            )
            .order_by(db_models.AutomationJob.created_at.desc())
        )
        results = self.db.execute(query).all()
        items = [
            self._to_job_model(job_record, workspace_record)
            for job_record, workspace_record in results
        ]
        return JobListResponse(items=items, total=len(items))

    def get_job(self, job_id: str) -> Optional[AutomationJob]:
        record = self.db.get(db_models.AutomationJob, job_id)
        return self._to_job_model(record) if record else None

    def get_job_record(self, job_id: str) -> Optional[db_models.AutomationJob]:
        """Get automation task model from database"""

        return self.db.get(db_models.AutomationJob, job_id)

    def create_job(self, payload: JobCreateRequest) -> AutomationJob:
        task_id = payload.model_dump().get("id") or str(uuid4())
        now = utcnow()
        system_tz = get_system_timezone()
        next_run_at = self._estimate_next_run(
            payload.trigger, payload.schedule, system_tz, reference=now
        )

        record = db_models.AutomationJob(
            id=task_id,
            name=payload.name,
            description=payload.description,
            owner=payload.owner,
            creator_user_id=payload.user_id,
            workspace_id=payload.workspace_id,
            prompt=payload.prompt,
            status=payload.status,
            trigger=payload.trigger,
            schedule=payload.schedule,
            tags=list(payload.tags),
            notifications=payload.notifications.model_dump(),
            task_metadata=dict(payload.metadata or {}),
            webhook_api_key=payload.webhook_api_key,
            next_run_at=next_run_at,
            created_at=now,
            updated_at=now,
        )

        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return self._to_job_model(record)

    def update_job(
        self, job_id: str, payload: JobUpdateRequest
    ) -> Optional[AutomationJob]:
        record = self.db.get(db_models.AutomationJob, job_id)
        if not record:
            return None

        data = payload.model_dump(exclude_none=True)

        for field, value in data.items():
            if field == "notifications" and value is not None:
                # value is already dict (from model_dump()), no need to call .model_dump() again
                setattr(record, field, value)
            elif field == "tags" and value is not None:
                setattr(record, field, list(value))
            elif field == "metadata" and value is not None:
                setattr(record, field, dict(value))
            elif field == "workspace_id":
                setattr(record, "workspace_id", value)
            elif field == "user_id":
                setattr(record, "creator_user_id", value)
            elif field == "webhook_api_key":
                setattr(record, "webhook_api_key", value)
            else:
                setattr(record, field, value)

        record.updated_at = utcnow()

        if any(key in data for key in ("trigger", "schedule")):
            system_tz = get_system_timezone()
            record.next_run_at = self._estimate_next_run(
                record.trigger,
                record.schedule,
                system_tz,
                reference=utcnow(),
            )

        self.db.commit()
        self.db.refresh(record)
        return self._to_job_model(record)

    def delete_job(self, job_id: str) -> None:
        record = self.db.get(db_models.AutomationJob, job_id)
        if not record:
            return
        self.db.delete(record)
        self.db.commit()

    def update_task_status(
        self, job_id: str, payload: JobStatusUpdate
    ) -> Optional[AutomationJob]:
        record = self.db.get(db_models.AutomationJob, job_id)
        if not record:
            return None

        record.status = payload.status
        record.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(record)
        return self._to_job_model(record)

    def execute_task_now(self, job_id: str) -> JobExecution:
        job = self.db.get(db_models.AutomationJob, job_id)
        if not job:
            raise JobNotFoundError(f"Automation task {job_id} does not exist", code="AUTOMATION_JOB_NOT_FOUND", params={"jobId": job_id})

        if job.status not in {"active", "paused"}:
            raise JobNotRunnableError(
                f"Automation task {job_id} current status is {job.status}, cannot execute",
                code="AUTOMATION_JOB_NOT_RUNNABLE",
                params={"jobId": job_id, "status": job.status},
            )

        execution = self.enqueue_execution(
            job_id,
            trigger="manual",
            summary="Manually trigger automation task immediately",
        )
        if not execution:
            raise JobDispatchError("Cannot create task execution record", code="AUTOMATION_EXECUTION_CREATE_FAILED")

        try:
            from app.tasks import run_automation_job
            from celery.exceptions import CeleryError

            # Use apply_async to explicitly specify queue
            run_automation_job.apply_async(
                args=[job_id, execution.id],
                queue='default'
            )
        except (CeleryError, ConnectionError, OSError) as exc:  # pragma: no cover - Celery ConnectionFailed
            logger.exception("Dispatch automation task %s immediate execution failed", job_id)
            self._mark_execution_dispatch_failed(execution, str(exc))
            raise JobDispatchError("Cannot dispatch automation task to Celery", code="AUTOMATION_DISPATCH_FAILED") from exc

        self.db.refresh(execution)
        return self._to_execution_model(execution)

    # ------------------------------------------------------------------
    # Execution record management
    # ------------------------------------------------------------------
    def list_executions(
        self, job_id: Optional[str] = None, limit: Optional[int] = None
    ) -> JobExecutionListResponse:
        query: Select[tuple[db_models.JobExecution]] = (
            select(db_models.JobExecution)
            .order_by(db_models.JobExecution.created_at.desc())
        )
        if job_id:
            query = query.where(db_models.JobExecution.job_id == job_id)

        if limit is not None and limit >= 0:
            query = query.limit(limit)

        records = self.db.execute(query).scalars().all()
        items = [self._to_execution_model(record) for record in records]
        return JobExecutionListResponse(items=items, total=len(items))

    def get_execution_record(self, execution_id: str) -> Optional[db_models.JobExecution]:
        """Get execution record

        Args:
            execution_id: Execution record ID

        Returns:
            Execution record, returns None if not exists
        """
        return self.db.get(db_models.JobExecution, execution_id)

    def get_stuck_executions(
        self, timeout_minutes: int = 60
    ) -> list[db_models.JobExecution]:
        """Get stuck execution records (exceed specified time still in running status)

        Args:
            timeout_minutes: Timeout (minutes), default 60 minutes

        Returns:
            List of stuck execution records
        """
        timeout_threshold = utcnow() - timedelta(minutes=timeout_minutes)
        query = (
            select(db_models.JobExecution)
            .where(
                db_models.JobExecution.status == "running",
                db_models.JobExecution.started_at < timeout_threshold
            )
            .order_by(db_models.JobExecution.started_at.asc())
        )
        return list(self.db.execute(query).scalars().all())

    def create_execution(
        self,
        job_id: str,
        status: JobExecutionStatus,
        trigger: JobTrigger,
        summary: str,
        duration: Optional[int] = None,
        session_id: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[JobExecution]:
        record = self.enqueue_execution(job_id, trigger, summary)
        if not record:
            return None

        if status == "running":
            record = self.mark_execution_running(record.id, summary=summary)
            if not record:
                return None
        elif status in {"success", "failed"}:
            record = self.mark_execution_running(record.id, summary=summary)
            if not record:
                return None
            record = self.complete_execution(
                record.id,
                status=status,
                summary=summary,
                duration=duration,
                session_id=session_id,
                error_message=error_message,
            )
            if not record:
                return None
        else:
            # Queued status creation completed
            record.summary = summary
            record.error_message = error_message
            record.session_id = session_id
            self.db.commit()
            self.db.refresh(record)

        return self._to_execution_model(record)

    def enqueue_execution(
        self, job_id: str, trigger: JobTrigger, summary: str = ""
    ) -> Optional[db_models.JobExecution]:
        job = self.db.get(db_models.AutomationJob, job_id)
        if not job:
            return None

        record = db_models.JobExecution(
            id=str(uuid4()),
            job_id=job_id,
            status="queued",
            trigger=trigger,
            summary=summary or "Automation task pending execution",
        )
        self.db.add(record)
        now = utcnow()
        job.updated_at = now
        if trigger == "cron":
            reference = job.next_run_at or now
            system_tz = get_system_timezone()
            next_run = self._estimate_next_run(
                job.trigger,
                job.schedule,
                system_tz,
                reference=reference,
            )
            if next_run is not None:
                job.next_run_at = next_run
            else:
                logger.warning(
                    "Cannot calculate next execution time for automation task %s, keeping original value", job_id
                )
        self.db.commit()
        self.db.refresh(record)
        return record

    def mark_execution_running(
        self, execution_id: str, summary: Optional[str] = None
    ) -> Optional[db_models.JobExecution]:
        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return None

        now = utcnow()
        record.status = "running"
        record.started_at = now
        if summary:
            record.summary = summary
        record.error_message = None
        self.db.commit()
        self.db.refresh(record)
        return record

    def complete_execution(
        self,
        execution_id: str,
        status: JobExecutionStatus,
        summary: str,
        duration: Optional[int] = None,
        session_id: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[db_models.JobExecution]:
        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return None

        now = utcnow()
        record.status = status
        record.summary = summary
        record.session_id = session_id
        record.error_message = error_message
        if metadata is not None:
            record.execution_metadata = metadata

        if record.started_at and duration is None:
            # Use unified timezone handling utility to calculate duration
            duration = calculate_duration(record.started_at, now)

        record.finished_at = now
        record.duration = duration

        job = self.db.get(db_models.AutomationJob, record.job_id)
        if job:
            self._update_task_statistics(job, record)

        self.db.commit()
        self.db.refresh(record)
        return record

    # ------------------------------------------------------------------
    # TaskScheduleQuery
    # ------------------------------------------------------------------
    def list_due_tasks(self, limit: int = 20) -> list[db_models.AutomationJob]:
        now = utcnow()
        query: Select[tuple[db_models.AutomationJob]] = (
            select(db_models.AutomationJob)
            .where(db_models.AutomationJob.status == "active")
            .where(db_models.AutomationJob.next_run_at.is_not(None))
            .where(db_models.AutomationJob.next_run_at <= now)
            .order_by(db_models.AutomationJob.next_run_at.asc())
            .limit(limit)
        )
        return self.db.execute(query).scalars().all()

    # ------------------------------------------------------------------
    # Statistics and calendar
    # ------------------------------------------------------------------
    def get_metrics(self) -> AutomationMetrics:
        # Count actual success and failure from execution records table (more reliable, avoid duplicate counts from retries)
        exec_stats = (
            self.db.execute(
                select(
                    db_models.JobExecution.status,
                    func.count(db_models.JobExecution.id).label("count")
                )
                .where(db_models.JobExecution.status.in_(["success", "failed"]))
                .group_by(db_models.JobExecution.status)
            ).all()
        )

        stats_dict = {row[0]: row[1] for row in exec_stats}
        total_success = stats_dict.get("success", 0)
        total_failed = stats_dict.get("failed", 0)
        completed = total_success + total_failed
        success_rate = (total_success / completed) if completed else 0.0

        # Calculate automation task count for each status
        active_count = (
            self.db.execute(
                select(func.count()).where(db_models.AutomationJob.status == "active")
            ).scalar_one()
        )
        paused_count = (
            self.db.execute(
                select(func.count()).where(db_models.AutomationJob.status == "paused")
            ).scalar_one()
        )
        # Note: failed_count here should be sum of failed execution counts, not count of tasks with failed status
        # Use total_failed variable (calculated above)
        draft_count = (
            self.db.execute(
                select(func.count()).where(db_models.AutomationJob.status == "draft")
            ).scalar_one()
        )

        # Calculate tasks in execution and queue
        running_executions = (
            self.db.execute(
                select(func.count()).where(
                    db_models.JobExecution.status == "running"
                )
            ).scalar_one()
        )
        queued_executions = (
            self.db.execute(
                select(func.count()).where(
                    db_models.JobExecution.status == "queued"
                )
            ).scalar_one()
        )

        # Calculate average execution time
        total_duration = (
            self.db.execute(
                select(func.coalesce(func.sum(db_models.AutomationJob.total_duration), 0))
            ).scalar_one()
        )
        average_duration = (total_duration / completed) if completed else 0.0

        return AutomationMetrics(
            active_count=active_count,
            paused_count=paused_count,
            failed_count=total_failed,  # Fixed: use sum of failed execution counts
            draft_count=draft_count,
            success_rate=success_rate,
            running_executions=running_executions,
            queued_executions=queued_executions,
            average_duration=average_duration,
        )

    def get_calendar_events(self) -> JobCalendarResponse:
        records = self.db.execute(select(db_models.AutomationJob)).scalars().all()
        events: list[JobCalendarEvent] = []
        utc_tz = ZoneInfo("UTC")

        for job in records:
            # Ensure all datetime objects have same timezone handling
            if job.next_run_at:
                start = job.next_run_at
                # If next_run_at is naive datetime, add UTC timezone
                if start.tzinfo is None:
                    start = start.replace(tzinfo=utc_tz)
            else:
                start = datetime.now(utc_tz)

            duration = job.last_duration or 900
            end = start + timedelta(seconds=duration)
            events.append(
                JobCalendarEvent(
                    id=str(uuid4()),
                    job_id=job.id,
                    title=job.name,
                    start=start,
                    end=end,
                    status="queued",
                )
            )
        events.sort(key=lambda item: item.start)
        return JobCalendarResponse(items=events, total=len(events))

    # ------------------------------------------------------------------
    # Utility functions
    # ------------------------------------------------------------------
    def _to_job_model(
        self,
        record: db_models.AutomationJob,
        workspace: Optional[db_models.Workspace] = None,
    ) -> AutomationJob:
        total_completed = record.success_count + record.failure_count
        success_rate = (
            record.success_count / total_completed if total_completed else 0.0
        )
        failure_rate = (
            record.failure_count / total_completed if total_completed else 0.0
        )
        average_duration = (
            int(record.total_duration / total_completed) if total_completed else 0
        )

        return AutomationJob(
            id=record.id,
            name=record.name,
            description=record.description or "",
            owner=record.owner,
            user_id=record.creator_user_id,
            workspace_id=record.workspace_id,
            workspace_name=workspace.name if workspace else None,
            prompt=record.prompt,
            status=record.status,
            trigger=record.trigger,
            schedule=record.schedule,
            tags=record.tags or [],
            notifications=record.notifications or {},
            metadata=record.task_metadata or {},
            webhook_api_key=record.webhook_api_key,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_run_at=record.last_run_at,
            next_run_at=record.next_run_at,
            success_rate=success_rate,
            failure_rate=failure_rate,
            total_executions=total_completed,
            average_duration=average_duration,
            last_duration=record.last_duration,
        )

    def _to_execution_model(
        self, record: db_models.JobExecution
    ) -> JobExecution:
        # Truncate summary to 100 characters (for list display)
        summary = record.summary or ""
        max_length = 100
        truncated_summary = summary[:max_length] + "..." if len(summary) > max_length else summary

        return JobExecution(
            id=record.id,
            job_id=record.job_id,
            status=record.status,
            trigger=record.trigger,
            started_at=record.started_at,
            finished_at=record.finished_at,
            duration=record.duration,
            session_id=record.session_id,
            error_message=record.error_message,
            summary=truncated_summary,
            execution_metadata=record.execution_metadata,
            queue_position=record.queue_position,
            queued_at=record.queued_at,
        )

    def _update_task_statistics(
        self,
        job: db_models.AutomationJob,
        execution: db_models.JobExecution,
    ) -> None:
        if execution.status not in {"success", "failed"}:
            return

        job.updated_at = utcnow()
        completion_time = execution.finished_at or execution.started_at or utcnow()
        job.last_run_at = completion_time
        if execution.status == "success":
            job.success_count += 1
        elif execution.status == "failed":
            job.failure_count += 1

        if execution.duration:
            job.total_duration += execution.duration
            job.last_duration = execution.duration

        if job.trigger == "cron":
            reference = job.next_run_at or completion_time
            # Use unified timezone handling utility for time comparison
            completion_utc = ensure_utc(completion_time)
            next_run_utc = ensure_utc(job.next_run_at)

            needs_update = (
                next_run_utc is None or
                (completion_utc is not None and next_run_utc <= completion_utc)
            )

            if needs_update:
                system_tz = get_system_timezone()
                job.next_run_at = self._estimate_next_run(
                    job.trigger,
                    job.schedule,
                    system_tz,
                    reference=reference,
                )
        else:
            job.next_run_at = None

    def _mark_execution_dispatch_failed(
        self,
        execution: db_models.JobExecution,
        error_message: str,
    ) -> None:
        now = utcnow()
        execution.status = "failed"
        execution.summary = "Automation task dispatch failed"
        execution.error_message = error_message
        execution.started_at = execution.started_at or now
        execution.finished_at = now
        execution.duration = 0

        job = execution.job or self.db.get(db_models.AutomationJob, execution.job_id)
        if job:
            job.updated_at = now

        self.db.commit()
        self.db.refresh(execution)

    def mark_execution_waiting(
        self, execution_id: str, position: int, summary: Optional[str] = None
    ) -> Optional[db_models.JobExecution]:
        """Mark execution record as waiting status

        Args:
            execution_id: Execution record ID
            position: Queue position
            summary: Execution summary

        Returns:
            Updated execution record, returns None if not exists
        """
        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return None

        record.status = "waiting"
        record.queue_position = position
        record.queued_at = utcnow()
        record.summary = summary or f"In queue (position: {position})"
        record.updated_at = utcnow()

        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "Mark execution record as waiting status - execution_id=%s, position=%d",
            execution_id, position
        )

        return record

    def cancel_execution(self, execution_id: str) -> dict:
        """Cancel queued execution record

        Args:
            execution_id: Execution record ID

        Returns:
            Cancellation result dictionary
        """
        from app.utils.automation_queue import get_queue_manager

        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return {
                "execution_id": execution_id,
                "status": "not_found",
                "message": "Execution record does not exist",
                "cancelled": False,
            }

        # Only
        if record.status != "waiting":
            return {
                "execution_id": execution_id,
                "status": record.status,
                "message": f"Cannot cancel task with status {record.status}, can only cancel waiting status tasks",
                "cancelled": False,
            }

        # Remove from Redis queue
        job = self.db.get(db_models.AutomationJob, record.job_id)
        if job:
            queue_manager = get_queue_manager()
            queue_manager.cancel(job.workspace_id, execution_id)

        # Update database status
        record.status = "cancelled"
        record.summary = "User cancelled queue"
        record.finished_at = utcnow()
        record.duration = calculate_duration(record.queued_at) if record.queued_at else 0
        record.updated_at = utcnow()

        self.db.commit()

        logger.info("Cancel queued task - execution_id=%s", execution_id)

        return {
            "execution_id": execution_id,
            "status": "cancelled",
            "message": "Successfully cancelled queued task",
            "cancelled": True,
        }

    def get_workspace_queue(self, workspace_id: str) -> dict:
        """Get workspace queue information

        Args:
            workspace_id: Workspace ID

        Returns:
            Queue information dictionary
        """
        from app.utils.automation_queue import get_queue_manager

        queue_manager = get_queue_manager()

        # Get execution record IDs from queue
        execution_ids = queue_manager.list_queued_executions(workspace_id, limit=50)

        # Query execution record details
        executions = []
        if execution_ids:
            stmt = select(db_models.JobExecution).where(
                db_models.JobExecution.id.in_(execution_ids),
                db_models.JobExecution.status == "waiting"
            ).order_by(db_models.JobExecution.queued_at)

            results = self.db.execute(stmt).scalars().all()
            executions = [self._to_execution_model(e) for e in results]

        return {
            "workspace_id": workspace_id,
            "queue_length": len(executions),
            "executions": executions,
        }

    def _estimate_next_run(
        self,
        trigger: JobTrigger,
        schedule: str,
        timezone: str,
        reference: Optional[datetime] = None,
    ) -> Optional[datetime]:
        if trigger == "cron":
            try:
                tz = ZoneInfo(timezone)
            except Exception:  # pragma: no cover - fallback to UTC for invalid timezone
                tz = ZoneInfo("UTC")

            base = ensure_utc(reference) or utcnow()
            base_local = base.astimezone(tz)

            with suppress(Exception):
                iterator = croniter(schedule, base_local)
                next_time_local = iterator.get_next(datetime)
                return next_time_local.astimezone(ZoneInfo("UTC"))
            logger.warning("Cannot parse schedule expression %s (%s)", schedule, trigger)
            return None

        # manual or webhook schedules don't calculate next execution time
        return None


__all__ = [
    "AutomationService",
    "AutomationJobError",
    "JobNotFoundError",
    "JobNotRunnableError",
    "JobDispatchError",
]
