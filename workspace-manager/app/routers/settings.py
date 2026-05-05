"""Settings API Route"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.openapi import build_responses
from app.db import models as db_models
from app.db.database import SessionLocal, get_db
from app.modules.auth import get_current_user_id
from app.models import (
    UserSettingsResponse,
    UserSettingsUpdate,
)
from app.models.settings import SSHKeyPairResponse
from app.services import get_settings_service
from app.services.settings_service import SettingsService
from app.services.runtime_sync_service import RuntimeSyncService
from app.services.codex_login_service import (
    CodexLoginError,
    CodexLoginService,
    get_codex_login_service,
)

router = APIRouter(tags=["settings"])


def _translate_settings_error(translate, error: str, *, operation: str) -> str:
    if operation == "sync":
        return translate("sync.failed_simple")
    if operation == "ssh_key_generate":
        return translate("git.ssh_key_gen_failed_simple")
    return error


@router.get(
    "/users/{user_id}/settings",
    response_model=UserSettingsResponse,
    summary="GetUserSettings",
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
            detail=request.state.translate("user.not_found"),
        )
    return UserSettingsResponse(data=settings)


@router.put(
    "/users/{user_id}/settings",
    response_model=UserSettingsResponse,
    summary="UpdateUserSettings",
    responses=build_responses(404, 422, 500),
)
async def update_settings(
    user_id: str,
    payload: UserSettingsUpdate,
    request: Request,
    background_tasks: BackgroundTasks,
    service: SettingsService = Depends(get_settings_service),
) -> UserSettingsResponse:
    # 1. Get old settings for change detection
    old_settings = service.get_settings(user_id)
    if not old_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found"),
        )

    # 2. Update database settings (sync, complete immediately)
    updated_settings = service.update_settings(user_id, payload)
    if not updated_settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.not_found"),
        )

    # 3. Detect actual changes
    payload_data = payload.model_dump(exclude_unset=True, by_alias=True)
    changes = service.detect_setting_changes(old_settings, payload_data)

    # 4. If changed, background sync to workspace-runtime (non-blocking)
    if changes:
        background_tasks.add_task(
            _sync_settings_to_runtimes,
            user_id,
            changes,
        )

    # 5. Immediately respond to frontend
    return UserSettingsResponse(data=updated_settings)


@router.post(
    "/users/{user_id}/settings/sync",
    summary="Sync settings to all workspaces",
    responses=build_responses(401, 403, 404, 500),
)
async def sync_settings_to_workspaces(
    user_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: SettingsService = Depends(get_settings_service),
    db: Session = Depends(get_db),
):
    """Manually sync settings to all running workspaces"""
    from app.services.sync_service import SyncService
    from app.db.models import User

    # Check user permission
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    # Get user settings
    user = db.get(User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    # Get language settings
    language = getattr(request.state, "language", "zh-TW")

    try:
        result = await SyncService.sync_to_all_workspaces(
            user_id, user.settings, db, language
        )
        return {
            "success": result["success"],
            "message": result["message"],
            "workspaces": result["workspaces"],
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_settings_error(
                request.state.translate, str(e), operation="sync"
            ),
        )


@router.post(
    "/users/{user_id}/settings/sync/{workspace_id}",
    summary="Sync settings to specified workspace",
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
    """Sync settings to specified workspace"""
    from app.services.sync_service import SyncService
    from app.db.models import User, Workspace

    # Check user permission
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    # Get user settings
    user = db.get(User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    # Get workspace and check permissions
    workspace = db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("workspace.not_found"),
        )

    if workspace.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    # Get language settings
    language = getattr(request.state, "language", "zh-TW")

    try:
        sync_result = await SyncService.sync_settings_to_runtime(
            workspace, user.settings, language
        )

        # Check sync result
        return {
            "success": all(r["success"] for r in sync_result.values()),
            "workspace_id": workspace.id,
            "workspace_name": workspace.name,
            "details": sync_result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_settings_error(
                request.state.translate, str(e), operation="sync"
            ),
        )


@router.post(
    "/users/{user_id}/settings/codex/login/start",
    summary="Start Codex login",
    responses=build_responses(401, 403, 404, 500),
)
async def start_codex_login(
    user_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    codex_login_service: CodexLoginService = Depends(get_codex_login_service),
):
    """Start Codex login through workspace-manager-owned login state."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    user = db.get(db_models.User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    try:
        details = await codex_login_service.start_login(user_id)
    except CodexLoginError as exc:
        raise _codex_login_http_exception(exc) from exc

    _update_codex_settings(
        user.settings,
        {
            "loginStatus": "pending",
            "authFlow": {
                "loginId": details.get("loginId"),
                "verificationUrl": details.get("verificationUrl"),
                "userCode": details.get("userCode"),
            },
        },
    )
    db.commit()
    return {"success": True, "codex": _get_codex_settings(user.settings)}


@router.get(
    "/users/{user_id}/settings/codex/login/status",
    summary="Get Codex login status",
    responses=build_responses(401, 403, 404, 500),
)
async def get_codex_login_status(
    user_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    codex_login_service: CodexLoginService = Depends(get_codex_login_service),
):
    """Get Codex login status from workspace-manager-owned login state."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    user = db.get(db_models.User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    codex = _get_codex_settings(user.settings, include_cli_state=True)
    login_id = (codex.get("authFlow") or {}).get("loginId")
    try:
        details = await codex_login_service.get_status(user_id, login_id)
    except CodexLoginError as exc:
        raise _codex_login_http_exception(exc) from exc

    if details.get("loginStatus") == "connected":
        updates = {
            "loginStatus": "connected",
            "account": details.get("account"),
            "cliState": details.get("cliState"),
            "authFlow": None,
        }
        _update_codex_settings(user.settings, updates)
        db.commit()
        background_tasks.add_task(
            _sync_settings_to_runtimes,
            user_id,
            {"codex": _get_codex_settings(user.settings, include_cli_state=True)},
        )
    elif details.get("loginStatus") == "pending":
        _update_codex_settings(user.settings, {"loginStatus": "pending"})
        db.commit()

    return {"success": True, "codex": _get_codex_settings(user.settings)}


@router.post(
    "/users/{user_id}/settings/codex/login/cancel",
    summary="Cancel Codex login",
    responses=build_responses(401, 403, 404, 500),
)
async def cancel_codex_login(
    user_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    codex_login_service: CodexLoginService = Depends(get_codex_login_service),
):
    """Cancel pending manager-owned Codex login."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    user = db.get(db_models.User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    codex = _get_codex_settings(user.settings, include_cli_state=True)
    login_id = (codex.get("authFlow") or {}).get("loginId")
    try:
        await codex_login_service.cancel_login(user_id, login_id)
    except CodexLoginError as exc:
        raise _codex_login_http_exception(exc) from exc

    _update_codex_settings(
        user.settings,
        {
            "loginStatus": "connected" if codex.get("account") else "notConnected",
            "authFlow": None,
        },
    )
    db.commit()
    return {"success": True, "codex": _get_codex_settings(user.settings)}


@router.post(
    "/users/{user_id}/settings/codex/logout",
    summary="Logout Codex",
    responses=build_responses(401, 403, 404, 500),
)
async def logout_codex(
    user_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
    codex_login_service: CodexLoginService = Depends(get_codex_login_service),
):
    """Logout Codex from manager source state and converge running runtimes by sync."""
    if user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=request.state.translate("access_denied"),
        )

    user = db.get(db_models.User, user_id)
    if not user or not user.settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("user.settings_not_found"),
        )

    await codex_login_service.logout(user_id)

    _update_codex_settings(
        user.settings,
        {
            "loginStatus": "notConnected",
            "account": None,
            "authFlow": None,
            "cliState": None,
        },
    )
    db.commit()
    background_tasks.add_task(
        _sync_settings_to_runtimes,
        user_id,
        {"codex": _get_codex_settings(user.settings, include_cli_state=True)},
    )
    return {"success": True, "codex": _get_codex_settings(user.settings)}


@router.post(
    "/users/{user_id}/ssh-keys/generate",
    response_model=SSHKeyPairResponse,
    summary="Generate and save SSH key pair",
    responses=build_responses(404, 500),
)
def generate_ssh_keys(
    user_id: str,
    request: Request,
    service: SettingsService = Depends(get_settings_service),
) -> SSHKeyPairResponse:
    """Generate new SSH key pair and automatically save to user settings"""
    try:
        ssh_keys = service.generate_and_save_ssh_keys(user_id)
        if not ssh_keys:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=request.state.translate("user.not_found"),
            )
        return ssh_keys
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_settings_error(
                request.state.translate, str(e), operation="ssh_key_generate"
            ),
        )


async def _sync_settings_to_runtimes(user_id: str, changes: dict):
    """Background task: Sync settings to all workspace-runtimes."""
    import logging

    logger = logging.getLogger(__name__)
    logger.info(
        f"Starting background settings sync - user_id: {user_id}, changes: {list(changes.keys())}"
    )

    db = SessionLocal()
    try:
        # Create new database connection for background task
        sync_service = RuntimeSyncService(db)
        result = await sync_service.sync_settings_to_runtimes(user_id, changes)

        if result["success"]:
            logger.info(
                f"Settings sync succeeded - user_id: {user_id}, Success: {result['success_count']}, Failed: {result['error_count']}"
            )
        else:
            logger.error(
                f"Settings sync had errors - user_id: {user_id}, Success: {result['success_count']}, Failed: {result['error_count']}"
            )

    except Exception as e:
        logger.error(
            f"Background settings sync failed - user_id: {user_id}, error: {e}"
        )
    finally:
        db.close()


def _get_codex_settings(settings, *, include_cli_state: bool = False) -> dict:
    additional_settings = settings.additional_settings or {}
    codex = dict(additional_settings.get("codex", {}))
    codex.setdefault("loginStatus", "notConnected")
    codex.setdefault("model", "gpt-5.3-codex")
    codex.setdefault("environmentVariables", [])
    if not include_cli_state:
        codex.pop("cliState", None)
    return codex


def _update_codex_settings(settings, updates: dict) -> None:
    additional_settings = settings.additional_settings or {}
    codex = dict(additional_settings.get("codex", {}))
    codex.update(updates)
    additional_settings["codex"] = codex
    settings.additional_settings = additional_settings
    flag_modified(settings, "additional_settings")


def _codex_login_http_exception(exc: CodexLoginError) -> HTTPException:
    return HTTPException(
        status_code=(
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.code == "codex_login_service_unavailable"
            else status.HTTP_502_BAD_GATEWAY
        ),
        detail={
            "code": exc.code,
            "message": str(exc),
        },
    )


__all__ = ["router"]
