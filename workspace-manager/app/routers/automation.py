"""自動化任務相關路由"""

from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.core.logging import get_logger
from app.core.openapi import build_responses
from app.models.automation import (
    AutomationJob,
    AutomationMetrics,
    ExecutionCancelResponse,
    JobCalendarResponse,
    JobCreateRequest,
    JobExecution,
    JobExecutionCreateRequest,
    JobExecutionListResponse,
    JobListResponse,
    JobStatusUpdate,
    JobUpdateRequest,
    WorkspaceQueueResponse,
)
from app.services import get_automation_service
from app.services.automation_service import (
    AutomationService,
    JobDispatchError,
    JobNotFoundError,
    JobNotRunnableError,
)


router = APIRouter(prefix="/automation", tags=["自動化"])
logger = get_logger(__name__)


def _translate_automation_error(translate: Callable[..., str], exc: Exception) -> str:
    code = getattr(exc, "code", "")
    params = getattr(exc, "params", {}) or {}
    if code == "AUTOMATION_JOB_NOT_RUNNABLE":
        return translate("automation.job_not_runnable", job_id=params.get("jobId", ""), status=params.get("status", ""))
    if code == "AUTOMATION_DISPATCH_FAILED":
        return translate("automation.dispatch_failed")
    if code == "AUTOMATION_EXECUTION_CREATE_FAILED":
        return translate("automation.execution_create_failed")
    return translate("automation.execution_failed_simple")


@router.get(
    "/jobs",
    response_model=JobListResponse,
    summary="列出自動化任務",
    responses=build_responses(500),
)
async def list_jobs(service: AutomationService = Depends(get_automation_service)) -> JobListResponse:
    return service.list_tasks()


@router.post(
    "/jobs",
    response_model=AutomationJob,
    status_code=status.HTTP_201_CREATED,
    summary="建立自動化任務",
    responses=build_responses(422, 500),
)
async def create_job(
    payload: JobCreateRequest,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationJob:
    return service.create_job(payload)


@router.get(
    "/jobs/{job_id}",
    response_model=AutomationJob,
    summary="取得自動化任務",
    responses=build_responses(404, 500),
)
async def get_job(
    job_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationJob:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    return job


@router.patch(
    "/jobs/{job_id}",
    response_model=AutomationJob,
    summary="更新自動化任務",
    responses=build_responses(404, 422, 500),
)
async def update_job(
    job_id: str,
    payload: JobUpdateRequest,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationJob:
    job = service.update_job(job_id, payload)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    return job


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除自動化任務",
    responses=build_responses(404, 500),
)
async def delete_job(
    job_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> None:
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    service.delete_job(job_id)


@router.post(
    "/jobs/{job_id}/status",
    response_model=AutomationJob,
    summary="更新任務狀態",
    responses=build_responses(404, 422, 500),
)
async def update_job_status(
    job_id: str,
    payload: JobStatusUpdate,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> AutomationJob:
    job = service.update_task_status(job_id, payload)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    return job


@router.post(
    "/jobs/{job_id}/execute",
    response_model=JobExecution,
    status_code=status.HTTP_201_CREATED,
    summary="立即執行自動化任務",
    responses=build_responses(400, 404, 500, 503),
)
async def execute_job_now(
    job_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> JobExecution:
    try:
        return service.execute_task_now(job_id)
    except JobNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    except JobNotRunnableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_automation_error(request.state.translate, exc),
        )
    except JobDispatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_translate_automation_error(request.state.translate, exc),
        )
    except Exception as exc:
        logger.exception("執行自動化任務 %s 時發生未預期的錯誤", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.execution_failed_simple")
        )


@router.post(
    "/jobs/{job_id}/executions",
    response_model=JobExecution,
    status_code=status.HTTP_201_CREATED,
    summary="建立新的任務執行",
    responses=build_responses(404, 422, 500),
)
async def create_execution(
    job_id: str,
    payload: JobExecutionCreateRequest,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> JobExecution:
    execution = service.create_execution(
        job_id,
        status=payload.status,
        trigger=payload.trigger,
        summary=payload.summary,
        duration=payload.duration,
        session_id=payload.session_id,
        error_message=payload.error_message,
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("automation.job_not_found")
        )
    return execution


@router.get(
    "/executions",
    response_model=JobExecutionListResponse,
    summary="列出任務執行紀錄",
    responses=build_responses(422, 500),
)
async def list_executions(
    job_id: Optional[str] = Query(default=None, alias="jobId", description="自動化任務 ID"),
    limit: Optional[int] = Query(default=None, ge=0, le=100, description="限制回傳數量"),
    service: AutomationService = Depends(get_automation_service),
) -> JobExecutionListResponse:
    return service.list_executions(job_id=job_id, limit=limit)


@router.get(
    "/executions/{execution_id}/logs",
    summary="獲取執行日誌",
    responses=build_responses(404, 500),
)
async def get_execution_logs(
    execution_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    """獲取執行日誌

    Args:
        execution_id: 執行記錄 ID

    Returns:
        包含日誌列表和總數的字典
    """
    execution_record = service.get_execution_record(execution_id)
    if not execution_record:
        raise HTTPException(
            status_code=404,
            detail=request.state.translate("automation.execution_not_found", execution_id=execution_id),
        )

    # 從 execution_metadata 中提取日誌
    metadata = execution_record.execution_metadata or {}
    logs = metadata.get("execution_logs", [])

    return {
        "execution_id": execution_id,
        "logs": logs,
        "total": len(logs),
        "job_id": execution_record.job_id,
        "status": execution_record.status,
        "started_at": execution_record.started_at.isoformat() if execution_record.started_at else None,
        "finished_at": execution_record.finished_at.isoformat() if execution_record.finished_at else None,
    }


@router.get(
    "/metrics",
    response_model=AutomationMetrics,
    summary="取得自動化統計資訊",
    responses=build_responses(500),
)
async def get_metrics(service: AutomationService = Depends(get_automation_service)) -> AutomationMetrics:
    return service.get_metrics()


@router.get(
    "/calendar",
    response_model=JobCalendarResponse,
    summary="取得任務行事曆事件",
    responses=build_responses(500),
)
async def get_calendar(service: AutomationService = Depends(get_automation_service)) -> JobCalendarResponse:
    return service.get_calendar_events()


@router.post(
    "/webhook/{job_id}",
    response_model=JobExecution,
    status_code=status.HTTP_201_CREATED,
    summary="透過 Webhook 觸發自動化任務",
    responses=build_responses(400, 401, 404, 500, 503),
)
async def trigger_webhook(
    job_id: str,
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key", description="Webhook API Key"),
    service: AutomationService = Depends(get_automation_service),
) -> JobExecution:
    """
    透過 Webhook 觸發自動化任務執行

    需要在 Header 中提供正確的 X-API-Key
    """
    try:
        # 驗證 API Key
        job = service.get_job(job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("automation.job_not_found")
            )

        if job.trigger != "webhook":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=request.state.translate("automation.webhook_invalid_type")
            )

        if not job.webhook_api_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=request.state.translate("automation.webhook_no_api_key")
            )

        if job.webhook_api_key != x_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=request.state.translate("automation.webhook_invalid_api_key")
            )

        # 執行任務
        execution = service.enqueue_execution(
            job_id=job_id,
            trigger="webhook",
            summary="透過 Webhook 觸發執行"
        )

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=request.state.translate("automation.execution_create_failed")
            )

        # 觸發 Celery 任務執行
        from app.celery.app import celery_app
        celery_app.send_task("automation.run_job", args=[job_id, execution.id])

        return service._to_execution_model(execution)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Webhook 觸發任務 %s 時發生未預期的錯誤", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.trigger_failed_simple")
        )


@router.get(
    "/workspaces/{workspace_id}/queue",
    response_model=WorkspaceQueueResponse,
    summary="查詢工作區佇列",
    responses=build_responses(500),
)
async def get_workspace_queue(
    workspace_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> WorkspaceQueueResponse:
    """查詢指定工作區的任務佇列

    Args:
        workspace_id: 工作區 ID
        service: 自動化服務

    Returns:
        工作區佇列資訊
    """
    try:
        result = service.get_workspace_queue(workspace_id)
        return WorkspaceQueueResponse(**result)
    except Exception as exc:
        logger.exception("查詢工作區佇列 %s 時發生錯誤", workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.queue_fetch_failed")
        )


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutionCancelResponse,
    summary="取消排隊任務",
    responses=build_responses(400, 404, 500),
)
async def cancel_execution(
    execution_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> ExecutionCancelResponse:
    """取消排隊中的任務

    只能取消 waiting 狀態的任務。

    Args:
        execution_id: 執行記錄 ID
        service: 自動化服務

    Returns:
        取消結果
    """
    try:
        result = service.cancel_execution(execution_id)
        return ExecutionCancelResponse(**result)
    except Exception as exc:
        logger.exception("取消執行記錄 %s 時發生錯誤", execution_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.cancel_failed")
        )


__all__ = ["router"]
