"""UserRoute"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.core.api_error import authorization_error_detail
from app.core.openapi import build_responses
from app.db import models as db_models
from app.modules.auth.auth_decorators import get_current_user_id
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import AuthorizationOperationError
from app.modules.identity.dependencies import get_user_service
from app.modules.identity.profile import (
    UserProfileService,
    get_user_profile_service,
)
from app.modules.identity.user_models import UserListResponse
from app.modules.identity.users import UserService
from app.modules.settings.models import UserProfileResponse
from app.modules.workspace.dependencies import get_workspace_service
from app.modules.workspace.catalog import WorkspaceService

router = APIRouter(prefix="/users", tags=["User"])


class RecentWorkspaceResponse(BaseModel):
    workspace_id: str | None


class RecentWorkspaceUpdateRequest(BaseModel):
    workspace_id: str


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    responses=build_responses(401, 500),
)
async def list_users(
    query: str | None = Query(
        default=None, description="Search by email, username, or display name"
    ),
    limit: int | None = Query(
        default=None, ge=1, le=50, description="Limit number of results"
    ),
    _current_user_id: str = Depends(get_current_user_id),
    service: UserService = Depends(get_user_service),
) -> UserListResponse:
    """Get user list."""
    return service.list(query=query, limit=limit)


@router.get(
    "/me/recent-workspace",
    response_model=RecentWorkspaceResponse,
    summary="Get recent workspace",
    responses=build_responses(401, 404, 500),
)
async def get_recent_workspace(
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    user_service: UserService = Depends(get_user_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> RecentWorkspaceResponse:
    """Get authenticated user's recent workspace."""
    user = user_service.db.get(db_models.User, actor.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found"),
        )

    if not user.recent_workspace_id:
        return RecentWorkspaceResponse(workspace_id=None)

    try:
        workspace = workspace_service.get(
            user.recent_workspace_id,
            actor=actor,
        )
    except AuthorizationOperationError:
        return RecentWorkspaceResponse(workspace_id=None)
    if not workspace:
        return RecentWorkspaceResponse(workspace_id=None)

    return RecentWorkspaceResponse(workspace_id=user.recent_workspace_id)


@router.put(
    "/me/recent-workspace",
    response_model=RecentWorkspaceResponse,
    summary="Update recent workspace",
    responses=build_responses(401, 403, 404, 422, 500),
)
async def update_recent_workspace(
    payload: RecentWorkspaceUpdateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    user_service: UserService = Depends(get_user_service),
    workspace_service: WorkspaceService = Depends(get_workspace_service),
) -> RecentWorkspaceResponse:
    """Update authenticated user's recent workspace."""
    user = user_service.db.get(db_models.User, actor.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found"),
        )

    try:
        workspace = workspace_service.get(
            payload.workspace_id,
            actor=actor,
        )
    except AuthorizationOperationError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                request.state.translate("workspace.access_denied"),
            ),
        ) from exc
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("workspace.access_denied"),
        )

    user.recent_workspace_id = payload.workspace_id
    user_service.db.commit()
    return RecentWorkspaceResponse(workspace_id=payload.workspace_id)


@router.get(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    summary="Get user profile",
    responses=build_responses(401, 404, 500),
)
async def get_user_profile(
    user_id: str,
    request: Request,
    _current_user_id: str = Depends(get_current_user_id),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """Get specified user profile."""
    profile = service.get_profile(user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found"),
        )
    return UserProfileResponse(data=profile)
