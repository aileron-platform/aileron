"""Capacity governance HTTP interface."""

from __future__ import annotations

from typing import Literal, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import AuthorizationOperationError

from .errors import PlatformResourceError
from .lifecycle import PlatformResourceCapacityAdministration
from .models import (
    KnowledgeBaseQuotaRequest,
    KnowledgeBaseQuotaResponse,
    WorkspaceCapacityExpansionRequest,
    WorkspaceCapacityExpansionResponse,
    WorkspaceCapacityResponse,
)
from .query import PlatformResourceCapacityQuery

router = APIRouter(tags=["platform-resource-capacity"])


def get_platform_resource_capacity_query(
    db: Session = Depends(get_db),
) -> PlatformResourceCapacityQuery:
    return PlatformResourceCapacityQuery(db)


def get_platform_resource_capacity_administration(
    db: Session = Depends(get_db),
) -> PlatformResourceCapacityAdministration:
    return PlatformResourceCapacityAdministration(db)


@router.get(
    "/workspaces/{workspace_id}/capacity", response_model=WorkspaceCapacityResponse
)
def get_workspace_capacity(
    workspace_id: str,
    request: Request,
    range_value: Literal["7d"] = Query("7d", alias="range"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    query: PlatformResourceCapacityQuery = Depends(
        get_platform_resource_capacity_query
    ),
) -> WorkspaceCapacityResponse:
    try:
        return query.get_workspace_capacity(
            actor=actor, workspace_id=workspace_id, range_value=range_value
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


@router.put(
    "/platform-resources/knowledge-bases/{knowledge_base_id}/quota",
    response_model=KnowledgeBaseQuotaResponse,
)
def set_knowledge_base_quota(
    knowledge_base_id: str,
    payload: KnowledgeBaseQuotaRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    administration: PlatformResourceCapacityAdministration = Depends(
        get_platform_resource_capacity_administration
    ),
) -> KnowledgeBaseQuotaResponse:
    try:
        return administration.set_knowledge_base_quota(
            actor=actor, knowledge_base_id=knowledge_base_id, payload=payload
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


@router.post(
    "/platform-resources/workspaces/{workspace_id}/capacity-expansions",
    response_model=WorkspaceCapacityExpansionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def request_workspace_capacity_expansion(
    workspace_id: str,
    payload: WorkspaceCapacityExpansionRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    administration: PlatformResourceCapacityAdministration = Depends(
        get_platform_resource_capacity_administration
    ),
) -> WorkspaceCapacityExpansionResponse:
    try:
        return administration.request_workspace_expansion(
            actor=actor,
            workspace_id=workspace_id,
            storage_kind=payload.storage_kind,
            requested_bytes=payload.requested_bytes,
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


@router.get(
    "/platform-resources/workspaces/{workspace_id}/capacity-expansions/{request_id}",
    response_model=WorkspaceCapacityExpansionResponse,
)
def get_workspace_capacity_expansion(
    workspace_id: str,
    request_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    administration: PlatformResourceCapacityAdministration = Depends(
        get_platform_resource_capacity_administration
    ),
) -> WorkspaceCapacityExpansionResponse:
    try:
        return administration.get_expansion(
            actor=actor, workspace_id=workspace_id, request_id=request_id
        )
    except (AuthorizationOperationError, PlatformResourceError) as exc:
        _raise_error(request, exc)


def _raise_error(
    request: Request,
    error: AuthorizationOperationError | PlatformResourceError,
) -> NoReturn:
    message_key = {
        "PLATFORM_AUTHORIZATION_DENIED": "platform_resources.permission_denied",
        "PLATFORM_RESOURCE_NOT_FOUND": "platform_resources.not_found",
        "KNOWLEDGE_BASE_QUOTA_BELOW_USAGE": "platform_resources.quota_below_usage",
        "WORKSPACE_CAPACITY_EXPANSION_IN_FLIGHT": "platform_resources.expansion_in_flight",
        "WORKSPACE_CAPACITY_EXPANSION_UNSUPPORTED": "platform_resources.expansion_unsupported",
        "WORKSPACE_CAPACITY_EXPANSION_ONLY": "platform_resources.expansion_only",
    }.get(error.error_code, "platform_resources.invalid_request")
    raise HTTPException(
        status_code=error.http_status,
        detail=authorization_error_detail(
            error.error_code,
            request.state.translate(message_key),
            details={"correlationId": request.state.correlation_id},
        ),
    ) from error
