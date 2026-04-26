"""Automation task related routes"""

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


router = APIRouter(prefix="/automation", tags=["Automation"])
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
    summary="List automation tasks",
    responses=build_responses(500),
)
async def list_jobs(service: AutomationService = Depends(get_automation_service)) -> JobListResponse:
    return service.list_tasks()


@router.post(
    "/jobs",
    response_model=AutomationJob,
    status_code=status.HTTP_201_CREATED,
    summary="CreateAutomation task",
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
    summary="GetAutomation task",
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
    summary="UpdateAutomation task",
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
    summary="DeleteAutomation task",
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
    summary="UpdateTaskStatus",
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
    summary="Execute automation task immediately",
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
        logger.exception("Unexpected error while executing automation task %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.execution_failed_simple")
        )


@router.post(
    "/jobs/{job_id}/executions",
    response_model=JobExecution,
    status_code=status.HTTP_201_CREATED,
    summary="Create new task execution",
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
    summary="List task execution records",
    responses=build_responses(422, 500),
)
async def list_executions(
    job_id: Optional[str] = Query(default=None, alias="jobId", description="Automation task ID"),
    limit: Optional[int] = Query(default=None, ge=0, le=100, description="Limit number of results"),
    service: AutomationService = Depends(get_automation_service),
) -> JobExecutionListResponse:
    return service.list_executions(job_id=job_id, limit=limit)


@router.get(
    "/executions/{execution_id}/logs",
    summary="Get execution logs",
    responses=build_responses(404, 500),
)
async def get_execution_logs(
    execution_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> dict[str, Any]:
    """Get execution logs

    Args:
        execution_id: Execution record ID

    Returns:
        Dictionary containing log list and total count
    """
    execution_record = service.get_execution_record(execution_id)
    if not execution_record:
        raise HTTPException(
            status_code=404,
            detail=request.state.translate("automation.execution_not_found", execution_id=execution_id),
        )

    # Extract logs from execution_metadata
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
    summary="Get automation statistics",
    responses=build_responses(500),
)
async def get_metrics(service: AutomationService = Depends(get_automation_service)) -> AutomationMetrics:
    return service.get_metrics()


@router.get(
    "/calendar",
    response_model=JobCalendarResponse,
    summary="Get task calendar events",
    responses=build_responses(500),
)
async def get_calendar(service: AutomationService = Depends(get_automation_service)) -> JobCalendarResponse:
    return service.get_calendar_events()


@router.post(
    "/webhook/{job_id}",
    response_model=JobExecution,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger automation task via webhook",
    responses=build_responses(400, 401, 404, 500, 503),
)
async def trigger_webhook(
    job_id: str,
    request: Request,
    x_api_key: str = Header(..., alias="X-API-Key", description="Webhook API Key"),
    service: AutomationService = Depends(get_automation_service),
) -> JobExecution:
    """
    Trigger automation task execution via webhook

    Requires valid X-API-Key in header
    """
    try:
        # Validate API Key
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

        # Execute task
        execution = service.enqueue_execution(
            job_id=job_id,
            trigger="webhook",
            summary="Triggered execution via webhook"
        )

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=request.state.translate("automation.execution_create_failed")
            )

        # Trigger Celery task execution
        from app.celery.app import celery_app
        celery_app.send_task("automation.run_job", args=[job_id, execution.id])

        return service._to_execution_model(execution)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while triggering webhook task %s", job_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.trigger_failed_simple")
        )


@router.get(
    "/workspaces/{workspace_id}/queue",
    response_model=WorkspaceQueueResponse,
    summary="Query workspace queue",
    responses=build_responses(500),
)
async def get_workspace_queue(
    workspace_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> WorkspaceQueueResponse:
    """Query task queue for specified workspace

    Args:
        workspace_id: Workspace ID
        service: Automation service

    Returns:
        Workspace queue information
    """
    try:
        result = service.get_workspace_queue(workspace_id)
        return WorkspaceQueueResponse(**result)
    except Exception as exc:
        logger.exception("Error while querying workspace queue %s", workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.queue_fetch_failed")
        )


@router.post(
    "/executions/{execution_id}/cancel",
    response_model=ExecutionCancelResponse,
    summary="Cancel queued task",
    responses=build_responses(400, 404, 500),
)
async def cancel_execution(
    execution_id: str,
    request: Request,
    service: AutomationService = Depends(get_automation_service),
) -> ExecutionCancelResponse:
    """Cancel queued task

    Only tasks with waiting status can be cancelled.

    Args:
        execution_id: Execution record ID
        service: Automation service

    Returns:
        Cancellation result
    """
    try:
        result = service.cancel_execution(execution_id)
        return ExecutionCancelResponse(**result)
    except Exception as exc:
        logger.exception("Error while cancelling execution record %s", execution_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("automation.cancel_failed")
        )


__all__ = ["router"]
