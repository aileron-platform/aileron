"""OAuth2 AuthenticationRoute"""

from fastapi import APIRouter, HTTPException, Request, status, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import httpx

from app.core.logging import get_logger
from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models.oauth import (
    OAuthExchangeRequest,
    OAuthExchangeResponse,
    OAuthRefreshRequest,
    OAuthRefreshResponse,
)
from app.services.oauth_service import OAuthService, OAuthAccountInfo

logger = get_logger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])


def _translate_oauth_error(translate, *, category: str) -> str:
    mapping = {
        "provider": "oauth.provider_error",
        "exchange_failed": "oauth.exchange_failed",
        "authenticate_failed": "oauth.authenticate_failed",
        "refresh_failed": "oauth.refresh_failed",
    }
    return translate(mapping[category])


class OAuthInfoResponse(BaseModel):
    """OAuth information response"""
    client_id: str
    authorization_url: str
    redirect_uri: str
    scope: str


@router.get(
    "/info",
    response_model=OAuthInfoResponse,
    summary="Get OAuth settings information",
)
async def get_oauth_info(request: Request):
    """Get OAuth settings information"""
    return OAuthInfoResponse(
        client_id="9d1c250a-e61b-44d9-88ed-5944d1962f5e",
        authorization_url="https://claude.ai/oauth/authorize",
        redirect_uri="https://console.anthropic.com/oauth/code/callback",
        scope=request.state.translate("oauth.info.scope"),
    )


@router.post(
    "/exchange",
    response_model=OAuthExchangeResponse,
    summary="Exchange OAuth authorization code for access token",
    description="Exchange OAuth authorization code and PKCE verifier for access token and refresh token",
    responses=build_responses(400, 422, 500, 502),
)
async def exchange_oauth_code(
    oauth_request: OAuthExchangeRequest,
    request: Request,
) -> OAuthExchangeResponse:
    """
    Exchange OAuth authorization code for access token

    Args:
        oauth_request: Request containing authCode and verifier

    Returns:
        Response containing accessToken, refreshToken, expiresAt

    Raises:
        HTTPException: When exchange fails
    """
    try:
        logger.info(f"Exchanging OAuth code for access token")
        result = await OAuthService.exchange_code(
            code=oauth_request.auth_code,
            verifier=oauth_request.verifier,
        )

        logger.info(f"Successfully exchanged OAuth code")
        return OAuthExchangeResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=result.expires_at,
        )
    except ValueError as e:
        logger.error(f"Invalid OAuth code format: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=request.state.translate("oauth.invalid_code_format"),
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"OAuth provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_translate_oauth_error(request.state.translate, category="provider"),
        )
    except Exception as e:
        logger.error(f"Failed to exchange OAuth code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_oauth_error(request.state.translate, category="exchange_failed"),
        )


@router.post(
    "/authenticate",
    summary="OAuth authentication and save",
    description="Exchange OAuth authorization code, fetch account information, and save to current logged-in user's settings",
    responses=build_responses(400, 401, 404, 422, 500, 502),
)
async def authenticate_and_save(
    oauth_request: OAuthExchangeRequest,
    http_request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Exchange OAuth authorization code and save directly to database

    This endpoint will:
    1. Use authCode and verifier to call Anthropic OAuth API
    2. Get access_token, refresh_token
    3. Save directly to user's settings

    Args:
        request: Request containing authCode and verifier
        user_id: Current user ID (from authentication middleware)
        db: Database session

    Returns:
        Success message and token information
    """
    try:
        logger.info(f"Authenticating user {user_id} with OAuth code")

        # 1. Call OAuth exchange
        result = await OAuthService.exchange_code(
            code=oauth_request.auth_code,
            verifier=oauth_request.verifier,
        )

        logger.info(f"Successfully exchanged OAuth code for user {user_id}")

        # 2. Get account information
        try:
            account_info = await OAuthService.get_account_info(result.access_token)
            logger.info(f"Successfully retrieved account info for user {user_id}")
            logger.info(f"Account: {account_info.email_address} ({account_info.display_name})")
            logger.info(f"Organization: {account_info.organization_name} (Role: {account_info.organization_role})")
        except Exception as e:
            logger.error(f"Failed to get account info for user {user_id}: {e}")
            # Even if getting account information fails, continue saving token
            account_info = None

        # 3. Get user settings (database model)
        from app.db.models import User
        user = db.get(User, user_id)
        if not user or not user.settings:
            logger.error(f"User or settings not found for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=http_request.state.translate("user.settings_not_found"),
            )

        db_settings = user.settings

        # 4. Update claudeCode in additional_settings
        additional_settings = db_settings.additional_settings or {}
        claude_additional = additional_settings.get("claudeCode", {})

        claude_additional["subscriptionAuthCode"] = oauth_request.auth_code
        claude_additional["subscriptionAccessToken"] = result.access_token
        claude_additional["subscriptionRefreshToken"] = result.refresh_token
        claude_additional["subscriptionExpiresAt"] = result.expires_at  # Save millisecond timestamp directly

        # Save account information
        if account_info:
            claude_additional["oauthAccount"] = {
                "accountUuid": account_info.account_uuid,
                "emailAddress": account_info.email_address,
                "organizationUuid": account_info.organization_uuid,
                "displayName": account_info.display_name,
                "organizationBillingType": account_info.organization_billing_type,
                "organizationRole": account_info.organization_role,
                "workspaceRole": account_info.workspace_role,
                "organizationName": account_info.organization_name,
            }

        additional_settings["claudeCode"] = claude_additional
        db_settings.additional_settings = additional_settings

        # Mark JSONB column as modified (SQLAlchemy needs this to detect JSONB changes)
        flag_modified(db_settings, "additional_settings")

        # 5. Commit to database
        db.commit()
        db.refresh(db_settings)

        logger.info(f"Successfully saved OAuth tokens and account info for user {user_id}")

        # Prepare response data
        response_data = {
            "success": True,
            "message": http_request.state.translate("oauth.auth_success"),
            "accessToken": result.access_token,
            "refreshToken": result.refresh_token,
            "expiresAt": result.expires_at,  # Return millisecond timestamp directly
            "needsSync": True,  # Prompt frontend to sync to workspace
        }

        # If there is account information, return together
        if account_info:
            response_data["oauthAccount"] = {
                "accountUuid": account_info.account_uuid,
                "emailAddress": account_info.email_address,
                "organizationUuid": account_info.organization_uuid,
                "displayName": account_info.display_name,
                "organizationBillingType": account_info.organization_billing_type,
                "organizationRole": account_info.organization_role,
                "workspaceRole": account_info.workspace_role,
                "organizationName": account_info.organization_name,
            }

        return response_data

    except httpx.HTTPStatusError as e:
        logger.error(f"OAuth provider error for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_translate_oauth_error(http_request.state.translate, category="provider"),
        )
    except ValueError as e:
        logger.error(f"Invalid OAuth code format for user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=http_request.state.translate("oauth.invalid_code_format"),
        )
    except Exception as e:
        logger.error(f"Failed to authenticate user {user_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_oauth_error(http_request.state.translate, category="authenticate_failed"),
        )


@router.post(
    "/refresh",
    response_model=OAuthRefreshResponse,
    summary="Refresh access token",
    description="Use refresh token to renew access token",
    responses=build_responses(422, 500, 502),
)
async def refresh_oauth_token(
    oauth_request: OAuthRefreshRequest,
    http_request: Request,
) -> OAuthRefreshResponse:
    """
    Refresh access token

    Args:
        oauth_request: Request containing refreshToken

    Returns:
        Response containing new accessToken, refreshToken, expiresAt

    Raises:
        HTTPException: When refresh fails
    """
    try:
        logger.info(f"Refreshing OAuth access token")
        result = await OAuthService.refresh_access_token(
            refresh_token=oauth_request.refresh_token,
        )

        logger.info(f"Successfully refreshed OAuth access token")
        return OAuthRefreshResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            expires_at=result.expires_at,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"OAuth provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_translate_oauth_error(http_request.state.translate, category="provider"),
        )
    except Exception as e:
        logger.error(f"Failed to refresh OAuth token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_translate_oauth_error(http_request.state.translate, category="refresh_failed"),
        )


@router.get(
    "/health",
    summary="OAuth service health check",
)
async def oauth_health_check(request: Request):
    """OAuth service health check"""
    return {
        "status": "healthy",
        "service": request.state.translate("oauth.health.service"),
        "description": request.state.translate("oauth.health.description"),
        "endpoints": [
            "GET /api/v1/oauth/info",
            "POST /api/v1/oauth/exchange",
            "POST /api/v1/oauth/authenticate",
            "POST /api/v1/oauth/refresh",
            "GET /api/v1/oauth/health",
        ],
    }
