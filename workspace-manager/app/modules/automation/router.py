"""Fresh Automation Job control-plane routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.automation.execution import AutomationExecutionService
from app.modules.automation.jobs import (
    AutomationJobService,
    AutomationServiceError,
)
from app.modules.automation.models import (
    AutomationExecution,
    AutomationExecutionListResponse,
    AutomationExecutionPageResponse,
    AutomationJob,
    AutomationJobListResponse,
    JobCreateRequest,
    JobUpdateRequest,
)
from app.modules.automation.repository import (
    AutomationRepository,
    AutomationRepositoryError,
)

router = APIRouter(prefix="/automation", tags=["Automation"])


def get_automation_job_service(db: Session = Depends(get_db)) -> AutomationJobService:
    return AutomationJobService(AutomationRepository(db))


def get_automation_execution_service(
    db: Session = Depends(get_db),
) -> AutomationExecutionService:
    return AutomationExecutionService(AutomationRepository(db))


AUTOMATION_ERRORS = (
    AutomationServiceError,
    AutomationRepositoryError,
    HTTPException,
)


def _translate_automation_error(exc: Exception, request: Request) -> HTTPException:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        authorization_code = (
            detail.get("errorCode") if isinstance(detail, dict) else None
        )
        if isinstance(authorization_code, str) and exc.status_code in {
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            message_key = {
                status.HTTP_401_UNAUTHORIZED: "auth.unauthenticated",
                status.HTTP_403_FORBIDDEN: "workspace.access_denied",
                status.HTTP_404_NOT_FOUND: "workspace.not_found",
            }[exc.status_code]
            return HTTPException(
                status_code=exc.status_code,
                detail=authorization_error_detail(
                    authorization_code,
                    request.state.translate(message_key),
                ),
            )
        code = (
            detail.get(
                "code",
                detail.get("errorCode", "automation_request_failed"),
            )
            if isinstance(detail, dict)
            else detail
        )
        status_code = exc.status_code
    else:
        code = getattr(exc, "code", "automation_request_failed")
        status_code = getattr(exc, "status_code", status.HTTP_500_INTERNAL_SERVER_ERROR)
    return HTTPException(status_code=status_code, detail={"code": str(code)})


@router.post("/jobs", response_model=AutomationJob, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJob:
    try:
        return service.create(actor=actor, payload=payload)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/jobs", response_model=AutomationJobListResponse)
def list_jobs(
    request: Request,
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJobListResponse:
    try:
        return service.list(actor=actor, workspace_id=workspace_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/jobs/{job_id}", response_model=AutomationJob)
def get_job(
    job_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJob:
    try:
        return service.get(actor=actor, job_id=job_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.patch("/jobs/{job_id}", response_model=AutomationJob)
def update_job(
    job_id: str,
    payload: JobUpdateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJob:
    try:
        return service.update(actor=actor, job_id=job_id, payload=payload)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.post("/jobs/{job_id}/pause", response_model=AutomationJob)
def pause_job(
    job_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJob:
    try:
        return service.pause(actor=actor, job_id=job_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.post("/jobs/{job_id}/resume", response_model=AutomationJob)
def resume_job(
    job_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> AutomationJob:
    try:
        return service.resume(actor=actor, job_id=job_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> Response:
    try:
        service.delete(actor=actor, job_id=job_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.post(
    "/jobs/{job_id}/run",
    response_model=AutomationExecution,
    status_code=status.HTTP_201_CREATED,
)
def run_job(
    job_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecution:
    try:
        return service.enqueue_manual(job_id=job_id, actor=actor)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.post(
    "/webhook/{job_id}",
    response_model=AutomationExecution,
    status_code=status.HTTP_201_CREATED,
)
def run_webhook(
    job_id: str,
    request: Request,
    webhook_key: str = Header(default="", alias="X-Automation-Webhook-Key"),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecution:
    try:
        return service.enqueue_webhook(
            job_id=job_id, presented_key=SecretStr(webhook_key)
        )
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/jobs/{job_id}/executions", response_model=AutomationExecutionPageResponse)
def list_job_executions(
    job_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, alias="pageSize", ge=1, le=100),
    range_start: datetime | None = Query(default=None, alias="rangeStart"),
    range_end: datetime | None = Query(default=None, alias="rangeEnd"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecutionPageResponse:
    try:
        return service.list_for_job(
            job_id=job_id,
            actor=actor,
            page=page,
            page_size=page_size,
            range_start=range_start,
            range_end=range_end,
        )
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/executions", response_model=AutomationExecutionListResponse)
def list_executions(
    request: Request,
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    limit: int = Query(default=100, ge=1, le=200),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecutionListResponse:
    try:
        return service.list(
            actor=actor,
            workspace_id=workspace_id,
            limit=limit,
        )
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/executions/{execution_id}", response_model=AutomationExecution)
def get_execution(
    execution_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecution:
    try:
        return service.get(execution_id=execution_id, actor=actor)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.post("/executions/{execution_id}/cancel", response_model=AutomationExecution)
def cancel_execution(
    execution_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationExecutionService = Depends(get_automation_execution_service),
) -> AutomationExecution:
    try:
        return service.cancel(execution_id=execution_id, actor=actor)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/metrics")
def get_metrics(
    request: Request,
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> dict:
    try:
        return service.metrics(actor=actor, workspace_id=workspace_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


@router.get("/calendar")
def get_calendar(
    request: Request,
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: AutomationJobService = Depends(get_automation_job_service),
) -> dict:
    try:
        return service.calendar(actor=actor, workspace_id=workspace_id)
    except AUTOMATION_ERRORS as exc:
        raise _translate_automation_error(exc, request) from exc


__all__ = [
    "get_automation_execution_service",
    "get_automation_job_service",
    "router",
]
