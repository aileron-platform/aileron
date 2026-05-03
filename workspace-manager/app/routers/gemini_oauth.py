"""Gemini Google OAuth route"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import httpx

from app.core.logging import get_logger
from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.services.gemini_oauth_service import GeminiOAuthService

logger = get_logger(__name__)

router = APIRouter(prefix="/gemini-oauth", tags=["gemini-oauth"])


class GeminiAuthRequest(BaseModel):
    auth_code: str
    verifier: str


class GeminiAuthResponse(BaseModel):
    success: bool
    message: str
    access_token: str
    refresh_token: str | None
    id_token: str | None
    expires_at: int
    scope: str
    email: str | None
    name: str | None
    needs_sync: bool


@router.post(
    "/authenticate",
    response_model=GeminiAuthResponse,
    summary="Gemini Google OAuth authenticate and save",
    responses=build_responses(400, 401, 404, 422, 500, 502),
)
async def authenticate_and_save(
    body: GeminiAuthRequest,
    http_request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> GeminiAuthResponse:
    try:
        logger.info(f"Gemini OAuth authenticate for user {user_id}")

        result = await GeminiOAuthService.exchange_code(body.auth_code, body.verifier)

        try:
            user_info = await GeminiOAuthService.get_userinfo(result.access_token)
            logger.info(f"Gemini userinfo: {user_info.email}")
        except Exception as e:
            logger.warning(f"Failed to get Gemini userinfo: {e}")
            user_info = None

        from app.db.models import User
        user = db.get(User, user_id)
        if not user or not user.settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=http_request.state.translate("user.settings_not_found"),
            )

        additional_settings = user.settings.additional_settings or {}
        gemini = additional_settings.get("gemini", {})

        gemini["authMethod"] = "subscription"
        gemini["accessToken"] = result.access_token
        gemini["refreshToken"] = result.refresh_token
        gemini["idToken"] = result.id_token
        gemini["expiresAt"] = result.expires_at
        gemini["scope"] = result.scope
        if user_info:
            gemini["account"] = {"email": user_info.email, "name": user_info.name}

        additional_settings["gemini"] = gemini
        user.settings.additional_settings = additional_settings
        flag_modified(user.settings, "additional_settings")
        db.commit()

        logger.info(f"Saved Gemini OAuth tokens for user {user_id}")

        return GeminiAuthResponse(
            success=True,
            message=http_request.state.translate("gemini_oauth.auth_success"),
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            id_token=result.id_token,
            expires_at=result.expires_at,
            scope=result.scope,
            email=user_info.email if user_info else None,
            name=user_info.name if user_info else None,
            needs_sync=True,
        )

    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"Google OAuth provider error for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=http_request.state.translate("gemini_oauth.provider_error"),
        )
    except Exception as e:
        logger.error(f"Gemini OAuth authenticate failed for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=http_request.state.translate("gemini_oauth.authenticate_failed"),
        )


@router.post(
    "/disconnect",
    summary="Disconnect Gemini OAuth",
    responses=build_responses(401, 404, 500),
)
async def disconnect(
    http_request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    try:
        logger.info(f"Gemini OAuth disconnect for user {user_id}")

        from app.db.models import User
        user = db.get(User, user_id)
        if not user or not user.settings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=http_request.state.translate("user.settings_not_found"),
            )

        additional_settings = user.settings.additional_settings or {}
        gemini = additional_settings.get("gemini", {})

        for key in ("accessToken", "refreshToken", "idToken", "expiresAt", "scope", "account"):
            gemini.pop(key, None)

        additional_settings["gemini"] = gemini
        user.settings.additional_settings = additional_settings
        flag_modified(user.settings, "additional_settings")
        db.commit()

        logger.info(f"Cleared Gemini OAuth tokens for user {user_id}")

        # Sync clear to running workspaces in background
        from app.services.runtime_sync_service import RuntimeSyncService
        sync_service = RuntimeSyncService(db)
        try:
            await sync_service.sync_settings_to_runtimes(user_id, {"gemini": gemini})
        except Exception as e:
            logger.warning(f"Failed to sync Gemini disconnect to runtimes: {e}")

        return {"success": True, "message": http_request.state.translate("gemini_oauth.disconnect_success")}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Gemini OAuth disconnect failed for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=http_request.state.translate("gemini_oauth.disconnect_failed"),
        )
