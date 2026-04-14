"""Settings API 路由"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status

from app.core.openapi import build_responses
from app.models import (
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.models.settings import SSHKeyPairResponse
from app.services import get_settings_service
from app.services.settings_service import SettingsService
from app.services.runtime_sync_service import RuntimeSyncService
from app.db.database import SessionLocal, get_db
from app.modules.auth import get_current_user_id
from sqlalchemy.orm import Session

router = APIRouter(tags=["settings"])


@router.get(
    "/users/{user_id}/settings",
    response_model=UserSettingsResponse,
    summary="取得使用者設定",
    responses=build_responses(404, 500),
)
def get_settings(
    user_id: str,
    request: Request,
    service: SettingsService = Depends(get_settings_service),
) -> UserSettingsResponse:
    settings = service.get_settings(user_id)
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )
    return UserSettingsResponse(data=settings)


@router.put(
    "/users/{user_id}/settings",
    response_model=UserSettingsResponse,
    summary="更新使用者設定",
    responses=build_responses(404, 422, 500),
)
async def update_settings(
    user_id: str,
    payload: UserSettingsUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    service: SettingsService = Depends(get_settings_service),
) -> UserSettingsResponse:
    # 1. 取得舊設定用於變更檢測
    old_settings = service.get_settings(user_id)
    if not old_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )

    # 2. 更新資料庫設定（同步，立即完成）
    updated_settings = service.update_settings(user_id, payload)
    if not updated_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found")
        )

    # 3. 檢測實際變更
    payload_data = payload.model_dump(exclude_unset=True, by_alias=True)
    changes = service.detect_setting_changes(old_settings, payload_data)

    # 4. 如果有變更，背景同步到 workspace-runtime（非阻塞）
    if changes:
        background_tasks.add_task(
            _sync_settings_to_runtimes,
            user_id,
            changes,
        )

    # 5. 立即回應前端
    return UserSettingsResponse(data=updated_settings)


@router.post(
    "/users/{user_id}/settings/sync",
    summary="同步設定到所有 Workspace",
    responses=build_responses(401, 403, 404, 500),
)
async def sync_settings_to_workspaces(
    user_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
):
    """手動同步設定到所有運行中的 workspace"""
    from app.services.sync_service import SyncService
    from app.db.models import User

    # 檢查用戶權限
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied")
        )

    # 取得用戶設定
    user = db.get(User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found")
        )

    # 取得語言設定
    language = getattr(request.state, "language", "zh-TW")

    try:
        result = await SyncService.sync_to_all_workspaces(user_id, user.settings, db, language)
        return {
            "success": result["success"],
            "message": result["message"],
            "workspaces": result["workspaces"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("sync.failed", error=str(e))
        )


@router.post(
    "/users/{user_id}/settings/sync/{workspace_id}",
    summary="同步設定到指定 Workspace",
    responses=build_responses(401, 403, 404, 500),
)
async def sync_settings_to_workspace(
    user_id: str,
    workspace_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
):
    """同步設定到指定的 workspace"""
    from app.services.sync_service import SyncService
    from app.db.models import User, Workspace

    # 檢查用戶權限
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied")
        )

    # 取得用戶設定
    user = db.get(User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found")
        )

    # 取得 workspace 並檢查權限
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found")
        )

    if workspace.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied")
        )

    # 取得語言設定
    language = getattr(request.state, "language", "zh-TW")

    try:
        sync_result = await SyncService.sync_settings_to_runtime(workspace, user.settings, language)

        # 檢查同步結果
        return {
            "success": not any(
                not r["success"]
                and "無" not in r["message"]
                and "沒有" not in r["message"]
                for r in sync_result.values()
            ),
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "details": sync_result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("sync.failed", error=str(e))
        )


@router.post(
    "/users/{user_id}/ssh-keys/generate",
    response_model=SSHKeyPairResponse,
    summary="產生並儲存 SSH Key Pair",
    responses=build_responses(404, 500),
)
def generate_ssh_keys(
    user_id: str,
    request: Request,
    service: SettingsService = Depends(get_settings_service),
) -> SSHKeyPairResponse:
    """產生新的 SSH Key Pair 並自動儲存到使用者設定"""
    try:
        ssh_keys = service.generate_and_save_ssh_keys(user_id)
        if not ssh_keys:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("user.not_found")
            )
        return ssh_keys
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=request.state.translate("git.ssh_key_gen_failed", error=str(e))
        )


async def _sync_settings_to_runtimes(user_id: str, changes: dict):
    """背景任務：同步設定到所有 workspace-runtime"""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"開始背景同步設定 - user_id: {user_id}, changes: {list(changes.keys())}")

    db = SessionLocal()
    try:
        # 創建新的資料庫連線用於背景任務
        sync_service = RuntimeSyncService(db)
        result = await sync_service.sync_settings_to_runtimes(user_id, changes)

        if result["success"]:
            logger.info(f"設定同步成功 - user_id: {user_id}, 成功: {result['success_count']}, 失敗: {result['error_count']}")
        else:
            logger.error(f"設定同步有錯誤 - user_id: {user_id}, 成功: {result['success_count']}, 失敗: {result['error_count']}")

    except Exception as e:
        logger.error(f"背景同步設定失敗 - user_id: {user_id}, error: {e}")
    finally:
        db.close()


__all__ = ["router"]
