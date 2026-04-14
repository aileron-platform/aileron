"""使用者路由"""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.openapi import build_responses
from app.models import User, UserCreate, UserListResponse, UserUpdate, UserProfile, UserProfileResponse, UserProfileUpdate
from app.services import get_user_service
from app.services.user_service import UserService
from app.services.user_profile_service import UserProfileService, get_user_profile_service

router = APIRouter(prefix="/users", tags=["使用者"])


@router.get(
    "/",
    response_model=UserListResponse,
    summary="列出使用者",
    responses=build_responses(500),
)
async def list_users(service: UserService = Depends(get_user_service)) -> UserListResponse:
    """取得使用者列表"""
    return service.list()


@router.post(
    "/",
    response_model=User,
    status_code=status.HTTP_201_CREATED,
    summary="建立使用者",
    responses=build_responses(409, 422, 500),
)
async def create_user(
    payload: UserCreate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """建立新使用者"""
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
    summary="取得使用者",
    responses=build_responses(404, 500),
)
async def get_user(
    user_id: str,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """取得指定使用者"""
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
    summary="更新使用者",
    responses=build_responses(404, 422, 500),
)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """更新使用者資料"""
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
    summary="部分更新使用者",
    responses=build_responses(404, 422, 500),
)
async def patch_user(
    user_id: str,
    payload: UserUpdate,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> User:
    """部分更新使用者資料"""
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
    summary="刪除使用者",
    responses=build_responses(404, 500),
)
async def delete_user(
    user_id: str,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> None:
    """刪除指定使用者"""
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
    summary="取得使用者個人檔案",
    responses=build_responses(404, 500),
)
async def get_user_profile(
    user_id: str,
    request: Request,
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """取得指定使用者的個人檔案"""
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
    summary="更新使用者個人檔案",
    responses=build_responses(404, 422, 500),
)
async def update_user_profile(
    user_id: str,
    payload: UserProfileUpdate,
    request: Request,
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    """更新指定使用者的個人檔案"""
    # 取得 access token 以同步 Keycloak
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
