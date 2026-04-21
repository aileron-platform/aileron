"""自動化服務實作：負責自動化任務 CRUD、執行紀錄與統計"""

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
    獲取系統時區設定

    優先順序：
    1. 環境變數 TZ
    2. 預設值 Asia/Taipei

    Returns:
        系統時區字串，例如 'Asia/Taipei'
    """
    return os.getenv("TZ", "Asia/Taipei")


class AutomationJobError(Exception):
    """自動化任務執行相關錯誤"""

    def __init__(self, message: str, *, code: str = "AUTOMATION_ERROR", params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class JobNotFoundError(AutomationJobError):
    """指定任務不存在"""


class JobNotRunnableError(AutomationJobError):
    """任務狀態不允許執行"""


class JobDispatchError(AutomationJobError):
    """無法派送自動化任務"""


class AutomationService:
    """管理自動化任務、執行紀錄與統計資料"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 任務 CRUD
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
        """取得資料庫中的自動化任務模型"""

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
                # value 已經是 dict（來自 model_dump()），不需要再調用 .model_dump()
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
            raise JobNotFoundError(f"自動化任務 {job_id} 不存在", code="AUTOMATION_JOB_NOT_FOUND", params={"jobId": job_id})

        if job.status not in {"active", "paused"}:
            raise JobNotRunnableError(
                f"自動化任務 {job_id} 目前狀態為 {job.status}，不可執行",
                code="AUTOMATION_JOB_NOT_RUNNABLE",
                params={"jobId": job_id, "status": job.status},
            )

        execution = self.enqueue_execution(
            job_id,
            trigger="manual",
            summary="手動立即觸發自動化任務",
        )
        if not execution:
            raise JobDispatchError("無法建立任務執行紀錄", code="AUTOMATION_EXECUTION_CREATE_FAILED")

        try:
            from app.tasks import run_automation_job
            from celery.exceptions import CeleryError

            # 使用 apply_async 明確指定隊列
            run_automation_job.apply_async(
                args=[job_id, execution.id],
                queue='default'
            )
        except (CeleryError, ConnectionError, OSError) as exc:  # pragma: no cover - Celery 連線失敗
            logger.exception("派送自動化任務 %s 立即執行失敗", job_id)
            self._mark_execution_dispatch_failed(execution, str(exc))
            raise JobDispatchError("無法派送自動化任務至 Celery", code="AUTOMATION_DISPATCH_FAILED") from exc

        self.db.refresh(execution)
        return self._to_execution_model(execution)

    # ------------------------------------------------------------------
    # 執行紀錄管理
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
        """獲取執行記錄

        Args:
            execution_id: 執行記錄 ID

        Returns:
            執行記錄，如果不存在則返回 None
        """
        return self.db.get(db_models.JobExecution, execution_id)

    def get_stuck_executions(
        self, timeout_minutes: int = 60
    ) -> list[db_models.JobExecution]:
        """獲取卡住的執行記錄（超過指定時間仍在 running 狀態）

        Args:
            timeout_minutes: 超時時間（分鐘），預設 60 分鐘

        Returns:
            卡住的執行記錄列表
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
            # queued 狀態已建立完畢
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
            summary=summary or "自動化任務等待執行",
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
                    "無法計算自動化任務 %s 的下一次執行時間，保留原值", job_id
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
            # 使用統一的時區處理工具計算時長
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
    # 任務排程查詢
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
    # 統計與行事曆
    # ------------------------------------------------------------------
    def get_metrics(self) -> AutomationMetrics:
        # 從執行紀錄表中統計真實的成功和失敗次數（更可靠，避免重試導致的重複計數）
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

        # 計算各種狀態的自動化任務數量
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
        # 注意：這裡的 failed_count 應該是失敗執行次數的總和，而不是狀態為 failed 的任務數
        # 使用 total_failed 變數（已在上面計算）
        draft_count = (
            self.db.execute(
                select(func.count()).where(db_models.AutomationJob.status == "draft")
            ).scalar_one()
        )

        # 計算執行中和佇列中的任務數
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

        # 計算平均執行時間
        total_duration = (
            self.db.execute(
                select(func.coalesce(func.sum(db_models.AutomationJob.total_duration), 0))
            ).scalar_one()
        )
        average_duration = (total_duration / completed) if completed else 0.0

        return AutomationMetrics(
            active_count=active_count,
            paused_count=paused_count,
            failed_count=total_failed,  # 修正：使用失敗執行次數總和
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
            # 確保所有 datetime 對象都有相同的時區處理
            if job.next_run_at:
                start = job.next_run_at
                # 如果 next_run_at 是 naive datetime，加上 UTC 時區
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
    # 工具函式
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
        # 截斷 summary 到 100 個字元（用於列表顯示）
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
            # 使用統一的時區處理工具比較時間
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
        execution.summary = "自動化任務派送失敗"
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
        """標記執行記錄為等待狀態

        Args:
            execution_id: 執行記錄 ID
            position: 排隊位置
            summary: 執行摘要

        Returns:
            更新後的執行記錄，如果不存在則返回 None
        """
        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return None

        record.status = "waiting"
        record.queue_position = position
        record.queued_at = utcnow()
        record.summary = summary or f"排隊中（位置：{position}）"
        record.updated_at = utcnow()

        self.db.commit()
        self.db.refresh(record)

        logger.info(
            "標記執行記錄為等待狀態 - execution_id=%s, position=%d",
            execution_id, position
        )

        return record

    def cancel_execution(self, execution_id: str) -> dict:
        """取消排隊中的執行記錄

        Args:
            execution_id: 執行記錄 ID

        Returns:
            取消結果字典
        """
        from app.utils.automation_queue import get_queue_manager

        record = self.db.get(db_models.JobExecution, execution_id)
        if not record:
            return {
                "execution_id": execution_id,
                "status": "not_found",
                "message": "執行記錄不存在",
                "cancelled": False,
            }

        # 只能取消 waiting 狀態的任務
        if record.status != "waiting":
            return {
                "execution_id": execution_id,
                "status": record.status,
                "message": f"無法取消 {record.status} 狀態的任務，只能取消 waiting 狀態的任務",
                "cancelled": False,
            }

        # 從 Redis 佇列移除
        job = self.db.get(db_models.AutomationJob, record.job_id)
        if job:
            queue_manager = get_queue_manager()
            queue_manager.cancel(job.workspace_id, execution_id)

        # 更新資料庫狀態
        record.status = "cancelled"
        record.summary = "使用者取消排隊"
        record.finished_at = utcnow()
        record.duration = calculate_duration(record.queued_at) if record.queued_at else 0
        record.updated_at = utcnow()

        self.db.commit()

        logger.info("取消排隊任務 - execution_id=%s", execution_id)

        return {
            "execution_id": execution_id,
            "status": "cancelled",
            "message": "已成功取消排隊任務",
            "cancelled": True,
        }

    def get_workspace_queue(self, workspace_id: str) -> dict:
        """獲取工作區佇列資訊

        Args:
            workspace_id: 工作區 ID

        Returns:
            佇列資訊字典
        """
        from app.utils.automation_queue import get_queue_manager

        queue_manager = get_queue_manager()

        # 獲取佇列中的執行記錄 ID
        execution_ids = queue_manager.list_queued_executions(workspace_id, limit=50)

        # 查詢執行記錄詳情
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
            except Exception:  # pragma: no cover - 無效時區回退 UTC
                tz = ZoneInfo("UTC")

            base = ensure_utc(reference) or utcnow()
            base_local = base.astimezone(tz)

            with suppress(Exception):
                iterator = croniter(schedule, base_local)
                next_time_local = iterator.get_next(datetime)
                return next_time_local.astimezone(ZoneInfo("UTC"))
            logger.warning("無法解析排程表達式 %s (%s)", schedule, trigger)
            return None

        # manual 或 webhook 排程不計算下一次執行時間
        return None


__all__ = [
    "AutomationService",
    "AutomationJobError",
    "JobNotFoundError",
    "JobNotRunnableError",
    "JobDispatchError",
]
