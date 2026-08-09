"""Admin-only platform resource inventory routes."""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.db.database import get_db
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.authorization.platform_resources import (
    OwnerReassignment,
    OwnerReassignmentError,
    OwnerReassignmentRequest,
    PlatformKnowledgeBaseListResponse,
    PlatformKnowledgeBaseSummary,
    PlatformResourceInventory,
    PlatformWorkspaceListResponse,
    PlatformWorkspaceSummary,
)

router = APIRouter(prefix="/platform-resources", tags=["platform-resources"])


def get_platform_resource_inventory(
    db: Session = Depends(get_db),
) -> PlatformResourceInventory:
    return PlatformResourceInventory(db)


def get_owner_reassignment(
    db: Session = Depends(get_db),
) -> OwnerReassignment:
    return OwnerReassignment(db)


@router.get("/workspaces", response_model=PlatformWorkspaceListResponse)
def list_platform_workspaces(
    request: Request,
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    health: str | None = Query(None),
    capacity_risk: str | None = Query(None, alias="capacityRisk"),
    sort: str = Query("createdAt"),
    order: str = Query("desc"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    inventory: PlatformResourceInventory = Depends(get_platform_resource_inventory),
) -> PlatformWorkspaceListResponse:
    try:
        return inventory.list_workspaces(
            actor=actor,
            q=q,
            page=page,
            page_size=page_size,
            health=health,
            capacity_risk=capacity_risk,
            sort=sort,
            order=order,
        )
    except (AuthorizationOperationError, OwnerReassignmentError) as exc:
        _raise_domain_error(request, exc)


@router.get("/knowledge-bases", response_model=PlatformKnowledgeBaseListResponse)
def list_platform_knowledge_bases(
    request: Request,
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    visibility: str | None = Query(None),
    indexing_health: str | None = Query(None, alias="indexingHealth"),
    capacity_risk: str | None = Query(None, alias="capacityRisk"),
    sort: str = Query("createdAt"),
    order: str = Query("desc"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    inventory: PlatformResourceInventory = Depends(get_platform_resource_inventory),
) -> PlatformKnowledgeBaseListResponse:
    try:
        return inventory.list_knowledge_bases(
            actor=actor,
            q=q,
            page=page,
            page_size=page_size,
            visibility=visibility,
            indexing_health=indexing_health,
            capacity_risk=capacity_risk,
            sort=sort,
            order=order,
        )
    except (AuthorizationOperationError, OwnerReassignmentError) as exc:
        _raise_domain_error(request, exc)


@router.post(
    "/workspaces/{workspace_id}/owner-reassignment",
    response_model=PlatformWorkspaceSummary,
)
def reassign_platform_workspace_owner(
    workspace_id: str,
    payload: OwnerReassignmentRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    owner_reassignment: OwnerReassignment = Depends(get_owner_reassignment),
) -> PlatformWorkspaceSummary:
    try:
        return owner_reassignment.reassign_workspace_owner(
            actor=actor,
            workspace_id=workspace_id,
            payload=payload,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
    except (AuthorizationOperationError, OwnerReassignmentError) as exc:
        _raise_domain_error(request, exc)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/owner-reassignment",
    response_model=PlatformKnowledgeBaseSummary,
)
def reassign_platform_knowledge_base_owner(
    knowledge_base_id: str,
    payload: OwnerReassignmentRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    owner_reassignment: OwnerReassignment = Depends(get_owner_reassignment),
) -> PlatformKnowledgeBaseSummary:
    try:
        return owner_reassignment.reassign_knowledge_base_owner(
            actor=actor,
            kb_id=knowledge_base_id,
            payload=payload,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
    except (AuthorizationOperationError, OwnerReassignmentError) as exc:
        _raise_domain_error(request, exc)


def _raise_domain_error(
    request: Request,
    error: AuthorizationOperationError | OwnerReassignmentError,
) -> NoReturn:
    message_keys = {
        "PLATFORM_AUTHORIZATION_DENIED": "platform_resources.permission_denied",
        "PLATFORM_RESOURCE_INVALID_REQUEST": "platform_resources.invalid_request",
        "PLATFORM_RESOURCE_NOT_FOUND": "platform_resources.not_found",
        "PLATFORM_RESOURCE_OWNER_NOT_FOUND": "platform_resources.owner_not_found",
        "PLATFORM_RESOURCE_TARGET_NOT_AUTHORIZABLE": "platform_resources.target_not_authorizable",
        "PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED": "platform_resources.target_manager_required",
        "PLATFORM_RESOURCE_OWNER_UNCHANGED": "platform_resources.owner_unchanged",
        "PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED": "platform_resources.notification_failed",
        "PLATFORM_RESOURCE_ACCESS_RECYCLE_FAILED": "platform_resources.access_recycle_failed",
    }
    raise HTTPException(
        status_code=error.http_status,
        detail=authorization_error_detail(
            error.error_code,
            request.state.translate(
                message_keys.get(
                    error.error_code,
                    "platform_resources.invalid_request",
                )
            ),
            details={"correlationId": request.state.correlation_id},
        ),
    ) from error
