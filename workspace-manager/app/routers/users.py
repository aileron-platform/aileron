"""UserRoute"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.core.openapi import build_responses
from app.models import User, UserCreate, UserListResponse, UserUpdate, UserProfile, UserProfileResponse, UserProfileUpdate
from app.services import get_user_service
from app.services.user_service import UserService
from app.services.user_profile_service import UserProfileService, get_user_profile_service

router = APIRouter(prefix="/users", tags=["User"])


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List users",
    responses=build_responses(500),
)
async def list_users(
    query: str | None = Query(default=None, description="Search by email, username, or display name"),
    limit: int | None = Query(default=None, ge=1, le=50, description="Limit number of results"),
    service: UserService = Depends(get_user_service),
) -> UserListResponse:
    """Get user list."""
    return service.list(query=query, limit=limit)


@router.post(
    "/",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    responses=build_responses(409, 422, 500),
)
async def create_user(
    payload: UserCreate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """Create new user."""
    try:
        return service.create(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=request.state.translate("user.conflict")
        ) from exc


@router.get(
    "/{user_id}",
    response_model=User,
    summary="Get user",
    responses=build_responses(404, 500),
)
async def get_user(
    user_id: str,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """Get specified user."""
    user = service.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return user


@router.put(
    "/{user_id}",
    response_model=User,
    summary="Update user",
    responses=build_responses(404, 422, 500),
)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """Update user data."""
    user = service.update(user_id, payload)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return user


@router.patch(
    "/{user_id}",
    response_model=User,
    summary="Partially update user",
    responses=build_responses(404, 422, 500),
)
async def patch_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """Partially update user data."""
    user = service.update(user_id, payload)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    responses=build_responses(404, 500),
)
async def delete_user(
    user_id: str,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> None:
    """Delete specified user."""
    user = service.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    service.delete(user_id)


@router.get(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    summary="Get user profile",
    responses=build_responses(404, 500),
)
async def get_user_profile(
    user_id: str,
    request: Request,
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """Get specified user profile."""
    profile = service.get_profile(user_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return UserProfileResponse(data=profile)


@router.put(
    "/{user_id}/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
    responses=build_responses(404, 422, 500),
)
async def update_user_profile(
    user_id: str,
    payload: UserProfileUpdate,
    request: Request,
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """Update specified user profile."""
    # Get access token to sync with Keycloak
    access_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        access_token = auth_header[7:]

    profile = await service.update_profile(user_id, payload, access_token=access_token)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return UserProfileResponse(data=profile)
