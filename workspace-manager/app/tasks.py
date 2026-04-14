"""Celery 任務定義：自動化任務派送與執行"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Iterator, Optional

import httpx
from celery import current_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.logging import get_celery_logger
from app.db import models as db_models
from app.db.database import SessionLocal
from app.services.automation_execution_logger import AutomationExecutionLogger
from app.services.automation_service import AutomationService
from app.utils.datetime_utils import calculate_duration, utcnow

logger = get_celery_logger()

DEFAULT_MODEL = "claude-3-7-sonnet-20250219"


@contextmanager
def automation_service() -> Iterator[AutomationService]:
    """建立 AutomationService 的資料庫工作階段"""

    db = SessionLocal()
    try:
        yield AutomationService(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@current_app.task(name="automation.dispatch_due_jobs")
def dispatch_due_jobs(limit: int = 50) -> dict[str, int]:
    """查找到期的自動化任務並分派 Celery 任務執行"""

    dispatched = 0
    with automation_service() as service:
        due_tasks = service.list_due_tasks(limit=limit)
        if not due_tasks:
            return {"dispatched": dispatched}

        for job in due_tasks:
            execution = service.enqueue_execution(
                job.id,
                trigger=job.trigger,
                summary="自動化任務已加入佇列",
            )
            if not execution:
                continue

            dispatched += 1
            current_app.send_task("automation.run_job", args=[job.id, execution.id])

    logger.info("派送 %s 個自動化任務等待執行", dispatched)
    return {"dispatched": dispatched}


@current_app.task(name="automation.cleanup_stuck_executions")
def cleanup_stuck_executions(timeout_minutes: int = 60) -> dict[str, int]:
    """清理卡住的任務執行記錄

    將超過指定時間仍在 running 狀態的任務標記為失敗。

    Args:
        timeout_minutes: 超時時間（分鐘），預設 60 分鐘

    Returns:
        清理統計資訊
    """
    cleaned = 0
    with automation_service() as service:
        stuck_executions = service.get_stuck_executions(timeout_minutes=timeout_minutes)

        if not stuck_executions:
            return {"cleaned": 0}

        logger.warning(
            "發現 %d 個卡住的任務執行記錄，開始清理（超時閾值：%d 分鐘）",
            len(stuck_executions), timeout_minutes
        )

        for execution in stuck_executions:
            try:
                duration = calculate_duration(execution.started_at) if execution.started_at else timeout_minutes * 60

                service.complete_execution(
                    execution.id,
                    status="failed",
                    summary=f"任務執行超時（超過 {timeout_minutes} 分鐘），已自動清理",
                    error_message="Execution timeout - cleaned up by system",
                    duration=duration,
                    metadata={
                        "error_type": "timeout",
                        "timeout_minutes": timeout_minutes,
                        "cleaned_at": utcnow().isoformat()
                    }
                )
                cleaned += 1

            except Exception as exc:
                logger.error(
                    "清理卡住的任務失敗 - execution_id=%s, error=%s",
                    execution.id, str(exc),
                    exc_info=True
                )

        logger.info("清理完成，共清理 %d 個卡住的任務", cleaned)
        return {"cleaned": cleaned, "total_stuck": len(stuck_executions)}


@current_app.task(name="automation.run_job", bind=True, max_retries=0)
def run_automation_job(self, job_id: str, execution_id: str) -> dict[str, Optional[str]]:
    """實際執行自動化任務：呼叫 Workspace Runtime 啟動 Session

    Args:
        job_id: 自動化任務 ID
        execution_id: 執行記錄 ID

    Returns:
        執行結果字典，包含 status 和 session_id
    """
    from app.utils.redis_lock import workspace_lock

    logger.debug(
        "Celery 任務開始 - task_id=%s, job_id=%s, execution_id=%s",
        self.request.id, job_id, execution_id
    )

    # 建立執行日誌記錄器
    exec_logger: Optional[AutomationExecutionLogger] = None

    try:
        with automation_service() as service:
            job = service.get_job_record(job_id)
            if not job:
                logger.error(
                    "自動化任務不存在 - job_id=%s, execution_id=%s",
                    job_id, execution_id
                )
                service.complete_execution(
                    execution_id,
                    status="failed",
                    summary="排程任務不存在，已取消執行",
                    error_message="Scheduled task not found",
                    duration=0,
                    metadata={"error_type": "job_not_found"}
                )
                return {"status": "not_found", "session_id": None}

            # 初始化執行日誌記錄器
            exec_logger = AutomationExecutionLogger(
                execution_id=execution_id,
                job_id=job_id,
                workspace_id=job.workspace_id
            )
            exec_logger.info("自動化任務開始執行", task_name=job.name, prompt_length=len(job.prompt))

            # 記錄執行上下文
            logger.info(
                "開始執行自動化任務 - job_id=%s, execution_id=%s, workspace_id=%s, prompt=%s",
                job_id, execution_id, job.workspace_id, job.prompt[:100]
            )

            # 使用 Redis 分散式鎖控制並發（確保同一個工作區同時只有一個任務執行）
            with workspace_lock(job.workspace_id, timeout=3600, blocking=False) as acquired:
                if not acquired:
                    # 無法獲取鎖，加入佇列等待
                    from app.utils.automation_queue import get_queue_manager

                    queue_manager = get_queue_manager()
                    position = queue_manager.enqueue(job.workspace_id, execution_id)

                    exec_logger.info(
                        "無法獲取工作區鎖，加入佇列等待",
                        workspace_id=job.workspace_id,
                        queue_position=position
                    )
                    logger.debug(
                        "Redis 佇列操作 - workspace_id=%s, execution_id=%s, position=%d",
                        job.workspace_id, execution_id, position
                    )

                    # 標記為 waiting 狀態
                    service.mark_execution_waiting(
                        execution_id,
                        position=position,
                        summary=f"排隊中（位置：{position}）"
                    )

                    return {"status": "queued", "session_id": None, "queue_position": position}

                # 成功獲取鎖，開始執行任務
                exec_logger.info("成功獲取工作區鎖，開始執行任務")
                execution = service.mark_execution_running(
                    execution_id, summary="排程任務執行中"
                )
                if not execution:
                    exec_logger.error("執行紀錄不存在")
                    logger.error(
                        "執行紀錄不存在 - job_id=%s, execution_id=%s",
                        job_id, execution_id
                    )
                    return {"status": "missing_execution", "session_id": None}

                start_time = execution.started_at or utcnow()
                session_id = None

                try:
                    exec_logger.info("開始執行任務")
                    session_id, summary, metadata = _execute_automation_job(service, job, exec_logger, execution_id)

                    # 成功執行
                    duration = calculate_duration(start_time)
                    exec_logger.info("任務執行成功", session_id=session_id, duration=duration)

                    # 合併執行日誌到 metadata
                    final_metadata = {**metadata, **exec_logger.to_metadata()}

                    service.complete_execution(
                        execution_id,
                        status="success",
                        summary=summary,
                        duration=duration,
                        session_id=session_id,
                        metadata=final_metadata,
                    )

                    logger.info(
                        "自動化任務執行成功 - job_id=%s, execution_id=%s, session_id=%s, duration=%ds",
                        job_id, execution_id, session_id, duration
                    )
                    return {"status": "success", "session_id": session_id}

                except Exception as exc:
                    duration = calculate_duration(start_time)
                    error_type = type(exc).__name__
                    error_message = str(exc)

                    # 檢查異常是否攜帶 session_id
                    if hasattr(exc, 'session_id'):
                        session_id = exc.session_id  # type: ignore

                    exec_logger.error("任務執行失敗", error_type=error_type, error_message=error_message)
                    logger.error(
                        "自動化任務執行失敗 - job_id=%s, execution_id=%s, session_id=%s, "
                        "error_type=%s, error=%s, duration=%ds",
                        job_id, execution_id, session_id or "N/A",
                        error_type, error_message, duration,
                        exc_info=True
                    )

                    try:
                        # 合併執行日誌到 metadata
                        final_metadata = {
                            **exec_logger.to_metadata(),
                            "error_type": error_type,
                            "error_message": error_message,
                            "execution_duration": duration,
                            "failed_at": utcnow().isoformat(),
                            "has_session": session_id is not None,
                        }

                        service.complete_execution(
                            execution_id,
                            status="failed",
                            summary=f"排程任務執行失敗 ({error_type}): {error_message}",
                            duration=duration,
                            session_id=session_id,
                            error_message=error_message,
                            metadata=final_metadata
                        )
                        logger.info(
                            "執行狀態已更新為失敗 - execution_id=%s",
                            execution_id
                        )
                    except Exception as update_exc:
                        logger.critical(
                            "無法更新執行狀態！- execution_id=%s, error=%s",
                            execution_id, str(update_exc),
                            exc_info=True
                        )

                    return {
                        "status": "failed",
                        "session_id": session_id,
                        "error_type": error_type
                    }

    except Exception as outer_exc:
        logger.critical(
            "自動化任務執行發生嚴重錯誤 - job_id=%s, execution_id=%s, error=%s",
            job_id, execution_id, str(outer_exc),
            exc_info=True
        )
        return {"status": "error", "session_id": None, "error": str(outer_exc)}
    finally:
        # 無論成功或失敗，都觸發下一個排隊任務
        # 注意：這裡需要重新獲取 job 資訊，因為可能在 except 區塊中
        try:
            with automation_service() as service:
                job = service.get_job_record(job_id)
                if job:
                    _trigger_next_queued_task(job.workspace_id)
        except Exception as trigger_exc:
            logger.error(
                "觸發下一個排隊任務失敗 - job_id=%s, error=%s",
                job_id, str(trigger_exc),
                exc_info=True
            )


def _trigger_next_queued_task(workspace_id: str) -> None:
    """觸發下一個排隊任務

    Args:
        workspace_id: 工作區 ID
    """
    from app.utils.automation_queue import get_queue_manager

    try:
        queue_manager = get_queue_manager()
        next_execution_id = queue_manager.dequeue(workspace_id)

        if next_execution_id:
            logger.info(
                "觸發下一個排隊任務 - workspace_id=%s, execution_id=%s",
                workspace_id, next_execution_id
            )

            # 使用 Celery 異步執行下一個任務
            # 需要先查詢 execution 的 job_id
            db = SessionLocal()
            try:
                execution = db.get(db_models.JobExecution, next_execution_id)
                if execution:
                    # 直接呼叫 run_automation_job 任務
                    run_automation_job.apply_async(
                        args=[execution.job_id, next_execution_id],
                        countdown=1  # 延遲 1 秒執行，確保鎖完全釋放
                    )
                    logger.info(
                        "已排程下一個任務 - job_id=%s, execution_id=%s",
                        execution.job_id, next_execution_id
                    )
                else:
                    logger.warning(
                        "找不到執行記錄 - execution_id=%s",
                        next_execution_id
                    )
            finally:
                db.close()
        else:
            logger.debug("佇列為空，無需觸發下一個任務 - workspace_id=%s", workspace_id)

    except Exception as exc:
        logger.error(
            "觸發下一個排隊任務失敗 - workspace_id=%s, error=%s",
            workspace_id, str(exc),
            exc_info=True
        )


def _execute_automation_job(
    service: AutomationService,
    job: db_models.AutomationJob,
    exec_logger: AutomationExecutionLogger,
    execution_id: str
) -> tuple[str, str, dict[str, Optional[str]]]:
    """呼叫 Workspace Runtime 建立並執行會話

    Args:
        service: AutomationService 實例
        job: 自動化任務記錄
        exec_logger: 執行日誌記錄器
        execution_id: 執行記錄 ID

    Returns:
        (session_id, summary, metadata) 元組

    Raises:
        RuntimeError: 當執行失敗時
    """

    db = service.db  # 使用 AutomationService 管理的 Session
    workspace = db.get(db_models.Workspace, job.workspace_id)
    if not workspace:
        exec_logger.error("找不到 Workspace", workspace_id=job.workspace_id)
        logger.error("找不到 Workspace - workspace_id=%s", job.workspace_id)
        raise RuntimeError("找不到對應的 Workspace")

    user = db.get(db_models.User, job.creator_user_id)
    if not user:
        exec_logger.error("找不到使用者", user_id=job.creator_user_id)
        logger.error("找不到使用者 - user_id=%s", job.creator_user_id)
        raise RuntimeError("找不到對應的使用者")

    runtime_url = workspace.runtime_internal_url or workspace.runtime_external_url
    if not runtime_url:
        exec_logger.error("Workspace Runtime 未啟動", workspace_name=workspace.name)
        logger.error(
            "Workspace Runtime 未啟動 - workspace_id=%s, workspace_name=%s",
            job.workspace_id, workspace.name
        )
        raise RuntimeError("Workspace Runtime 尚未啟動")

    base_url = runtime_url.rstrip("/")
    sessions_url = f"{base_url}/api/v1/agent-sessions"

    # 獲取 Internal API Token 用於內部服務認證
    settings = get_settings()
    internal_headers = {
        "X-Internal-Token": settings.INTERNAL_API_TOKEN,
        "Content-Type": "application/json"
    }

    # NOTE: model_key is now determined by the agentic tool on the runtime side.
    # We just select the tool here. Assuming 'claude-code' for automation jobs.
    agentic_tool = "claude-code"
    exec_logger.info("準備建立 Session", runtime_url=base_url, agentic_tool=agentic_tool)
    logger.info(
        "準備建立 Session - workspace_id=%s, runtime_url=%s, agentic_tool=%s",
        job.workspace_id, base_url, agentic_tool
    )

    # 準備執行參數
    metadata = job.task_metadata or {}
    images = []
    if isinstance(metadata, dict):
        images_value = metadata.get("images")
        if isinstance(images_value, list):
            images = images_value

    create_payload = {
        "workspace_id": job.workspace_id,
        "agentic_tool": agentic_tool,
        "source": "automation",
    }

    prompt_payload = {
        "prompt": job.prompt,
        "images": images,
        "stream": True,  # Streaming is handled by the pub/sub wait
        "automation_execution_id": execution_id,  # 用於完成通知
    }

    session_id = None

    try:
        with httpx.Client(timeout=60.0) as client:
            # 步驟 1: 建立 Session
            try:
                exec_logger.info("發送建立 Session 請求", url=sessions_url)
                logger.info(
                    "發送建立 Session 請求 - url=%s, workspace_id=%s",
                    sessions_url, job.workspace_id
                )
                response = client.post(sessions_url, json=create_payload, headers=internal_headers)
                response.raise_for_status()
                session_data = response.json()
                session_id = session_data["id"]  # API response uses "id" field
                exec_logger.info("Session 建立成功", session_id=session_id)
                logger.info(
                    "Session 建立成功 - session_id=%s, workspace_id=%s",
                    session_id, job.workspace_id
                )
            except httpx.HTTPStatusError as e:
                error_detail = _extract_http_error_detail(e)
                exec_logger.error("建立 Session 失敗", status_code=e.response.status_code, error=error_detail)
                logger.error(
                    "建立 Session 失敗 - status_code=%s, error=%s, url=%s",
                    e.response.status_code, error_detail, sessions_url
                )
                raise RuntimeError(
                    f"建立 Session 失敗 (HTTP {e.response.status_code}): {error_detail}"
                ) from e
            except httpx.RequestError as e:
                exec_logger.error("無法連接到 Workspace Runtime", error=str(e))
                logger.error(
                    "無法連接到 Workspace Runtime - error=%s, url=%s",
                    str(e), sessions_url
                )
                raise RuntimeError(f"無法連接到 Workspace Runtime: {e}") from e

            # 步驟 2: 執行指令（異步，立即返回）
            try:
                execute_url = f"{sessions_url}/{session_id}/prompt" # Changed from /execute to /prompt
                exec_logger.info("發送執行 Prompt 請求", session_id=session_id, execution_id=execution_id)
                logger.info(
                    "發送執行 Prompt 請求 - url=%s, session_id=%s, execution_id=%s",
                    execute_url, session_id, execution_id
                )
                response = client.post(execute_url, json=prompt_payload, headers=internal_headers)
                response.raise_for_status()
                exec_logger.info("執行 Prompt 請求已發送（異步執行）", session_id=session_id)
                logger.info(
                    "執行 Prompt 請求已發送（異步執行） - session_id=%s",
                    session_id
                )
            except httpx.HTTPStatusError as e:
                error_detail = _extract_http_error_detail(e)
                logger.error(
                    "執行 Prompt 失敗 - status_code=%s, error=%s, session_id=%s",
                    e.response.status_code, error_detail, session_id
                )
                raise RuntimeError(
                    f"執行 Prompt 失敗 (HTTP {e.response.status_code}): {error_detail}"
                ) from e
            except httpx.RequestError as e:
                logger.error(
                    "執行請求失敗 - error=%s, session_id=%s",
                    str(e), session_id
                )
                raise RuntimeError(f"執行請求失敗: {e}") from e

        # 步驟 3: 等待執行完成（通過 Redis Pub/Sub）
        from app.utils.redis_subscriber import wait_for_execution_completed_sync

        exec_logger.info("等待執行完成", execution_id=execution_id, timeout=3600)
        logger.info(
            "等待執行完成 - execution_id=%s, timeout=3600s",
            execution_id
        )

        # NOTE: This relies on the new execution_service publishing a compatible message.
        execution_result = wait_for_execution_completed_sync(
            execution_id=execution_id,
            timeout=3600  # 1 小時超時
        )

        if not execution_result:
            raise RuntimeError("等待執行完成超時（1小時）")

        exec_logger.info("收到執行完成事件", execution_id=execution_id, result=execution_result)
        logger.info(
            "收到執行完成事件 - execution_id=%s, status=%s, total_messages=%d",
            execution_id, execution_result.get("status"), execution_result.get("total_messages", 0)
        )

        # 檢查執行狀態
        exec_status = execution_result.get("status")
        has_error = execution_result.get("has_error", False)
        error_message = execution_result.get("error_message")
        total_messages = execution_result.get("total_messages", 0)

        if exec_status == "failed" or has_error:
            error_msg = error_message or "執行失敗"
            raise RuntimeError(f"排程任務執行失敗: {error_msg}")

        if exec_status == "aborted":
            raise RuntimeError("排程任務執行被中止")

        # 步驟 4: 獲取執行結果訊息
        # This part of the logic might need adjustment if the message structure from the new agent_session is different.
        # For now, we assume it's compatible enough to find a summary.
        messages_url = f"{base_url}/api/v1/sessions/{session_id}/messages"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(messages_url, params={"limit": 100})
                response.raise_for_status()
                messages_data = response.json()
                messages = messages_data.get("items", [])
                logger.info(
                    "獲取執行結果訊息 - session_id=%s, message_count=%d",
                    session_id, len(messages)
                )
        except Exception as e:
            logger.warning(f"獲取執行結果訊息失敗: {e}")
            messages = []

        # 查找結果訊息
        # This logic is highly dependent on the old message format.
        # The new format uses Content Blocks. This will likely fail or return a poor summary.
        # TODO: Re-implement summary extraction based on AgentMessage format.
        summary = "排程任務執行完成"
        if messages:
            last_message = messages[-1]
            if isinstance(last_message, dict) and last_message.get("content"):
                # Try to find a text block in the last assistant message
                if last_message.get("role") == "assistant" and isinstance(last_message.get("content"), list):
                    text_blocks = [block for block in last_message["content"] if block.get("type") == "text"]
                    if text_blocks and text_blocks[0].get("text"):
                        summary = text_blocks[0]["text"]

        metadata_out = {
            "totalMessages": total_messages,
            "lastMessageId": (
                messages[-1].get("message_id")
                if messages and isinstance(messages[-1], dict)
                else None
            ),
            "hasErrorMessage": has_error,
            "isError": False,
        }

        return session_id, summary, metadata_out

    except Exception as e:
        # 如果已經建立了 Session，將 session_id 附加到異常中
        if session_id:
            # 創建新的異常並附加 session_id
            error_with_session = RuntimeError(str(e))
            error_with_session.session_id = session_id  # type: ignore
            raise error_with_session from e
        else:
            raise


def _extract_http_error_detail(error: httpx.HTTPStatusError) -> str:
    """從 HTTP 錯誤響應中提取詳細資訊"""
    try:
        error_data = error.response.json()
        if isinstance(error_data, dict):
            return error_data.get("detail", str(error))
    except Exception:
        pass
    return str(error)


@current_app.task(name="automation.cleanup_expired_queue")
def cleanup_expired_queue() -> dict:
    """清理超時的排隊任務

    定期執行（每 5 分鐘），清理所有工作區中超時的排隊任務。

    Returns:
        清理結果字典
    """
    logger.info("開始清理超時排隊任務")

    from app.utils.automation_queue import get_queue_manager

    db = SessionLocal()
    try:
        service = AutomationService(db)
        queue_manager = get_queue_manager()

        # 查詢所有有排隊任務的工作區
        stmt = select(db_models.AutomationJob.workspace_id).distinct().where(
            db_models.AutomationJob.status == "active"
        )
        workspace_ids = db.execute(stmt).scalars().all()

        total_cleaned = 0
        total_timeout = 0

        for workspace_id in workspace_ids:
            # 獲取工作區的佇列配置（使用第一個 active job 的配置）
            job = db.execute(
                select(db_models.AutomationJob).where(
                    db_models.AutomationJob.workspace_id == workspace_id,
                    db_models.AutomationJob.status == "active"
                ).limit(1)
            ).scalar_one_or_none()

            if not job:
                continue

            timeout_seconds = job.queue_timeout

            # 清理 Redis 中超時的任務
            cleaned = queue_manager.cleanup_expired(workspace_id, timeout_seconds)
            total_cleaned += cleaned

            if cleaned > 0:
                logger.warning(
                    "清理超時排隊任務 - workspace_id=%s, cleaned=%d, timeout=%ds",
                    workspace_id, cleaned, timeout_seconds
                )

            # 查詢資料庫中 waiting 狀態超時的任務
            from app.utils.datetime_utils import utcnow
            cutoff_time = utcnow() - timedelta(seconds=timeout_seconds)

            timeout_executions = db.execute(
                select(db_models.JobExecution).where(
                    db_models.JobExecution.job_id.in_(
                        select(db_models.AutomationJob.id).where(
                            db_models.AutomationJob.workspace_id == workspace_id
                        )
                    ),
                    db_models.JobExecution.status == "waiting",
                    db_models.JobExecution.queued_at < cutoff_time
                )
            ).scalars().all()

            for execution in timeout_executions:
                execution.status = "timeout"
                execution.summary = f"排隊超時（超過 {timeout_seconds} 秒）"
                execution.finished_at = utcnow()
                execution.duration = calculate_duration(execution.queued_at) if execution.queued_at else 0
                execution.updated_at = utcnow()
                total_timeout += 1

                logger.warning(
                    "標記排隊任務為超時 - execution_id=%s, queued_at=%s",
                    execution.id, execution.queued_at
                )

            db.commit()

        logger.info(
            "清理超時排隊任務完成 - total_cleaned=%d, total_timeout=%d",
            total_cleaned, total_timeout
        )

        return {
            "status": "success",
            "total_cleaned": total_cleaned,
            "total_timeout": total_timeout,
            "workspaces_checked": len(workspace_ids)
        }

    except Exception as exc:
        logger.error(
            "清理超時排隊任務失敗 - error=%s",
            str(exc),
            exc_info=True
        )
        db.rollback()
        return {
            "status": "error",
            "error": str(exc)
        }
    finally:
        db.close()


__all__ = [
    "dispatch_due_jobs",
    "run_automation_job",
    "cleanup_expired_queue",
]
