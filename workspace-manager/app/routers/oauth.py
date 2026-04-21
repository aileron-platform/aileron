"""OAuth2 認證路由"""

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
    """OAuth 資訊回應"""
    client_id: str
    authorization_url: str
    redirect_uri: str
    scope: str


@router.get(
    "/info",
    response_model=OAuthInfoResponse,
    summary="取得 OAuth 設定資訊",
)
async def get_oauth_info(request: Request):
    """取得 OAuth 設定資訊"""
    return OAuthInfoResponse(
        client_id="9d1c250a-e61b-44d9-88ed-5944d1962f5e",
        authorization_url="https://claude.ai/oauth/authorize",
        redirect_uri="https://console.anthropic.com/oauth/code/callback",
        scope=request.state.translate("oauth.info.scope"),
    )


@router.post(
    "/exchange",
    response_model=OAuthExchangeResponse,
    summary="交換 OAuth 認證碼取得 Access Token",
    description="使用 OAuth 認證碼和 PKCE verifier 交換 access token 和 refresh token",
    responses=build_responses(400, 422, 500, 502),
)
async def exchange_oauth_code(
    oauth_request: OAuthExchangeRequest,
    request: Request,
) -> OAuthExchangeResponse:
    """
    交換 OAuth 認證碼取得 Access Token

    Args:
        oauth_request: 包含 authCode 和 verifier 的請求

    Returns:
        包含 accessToken, refreshToken, expiresAt 的回應

    Raises:
        HTTPException: 當交換失敗時
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
    summary="OAuth 認證並儲存",
    description="交換 OAuth 認證碼、抓取帳戶資訊，並直接儲存到目前登入使用者的設定。",
    responses=build_responses(400, 401, 404, 422, 500, 502),
)
async def authenticate_and_save(
    oauth_request: OAuthExchangeRequest,
    http_request: Request,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    交換 OAuth 認證碼並直接儲存到資料庫

    這個端點會：
    1. 使用 authCode 和 verifier 呼叫 Anthropic OAuth API
    2. 取得 access_token, refresh_token
    3. 直接儲存到用戶的設定中

    Args:
        request: 包含 authCode 和 verifier 的請求
        user_id: 當前用戶 ID（從認證中間件取得）
        db: 資料庫 session

    Returns:
        成功訊息和 token 資訊
    """
    try:
        logger.info(f"Authenticating user {user_id} with OAuth code")

        # 1. 呼叫 OAuth exchange
        result = await OAuthService.exchange_code(
            code=oauth_request.auth_code,
            verifier=oauth_request.verifier,
        )

        logger.info(f"Successfully exchanged OAuth code for user {user_id}")

        # 2. 取得帳戶資訊
        try:
            account_info = await OAuthService.get_account_info(result.access_token)
            logger.info(f"Successfully retrieved account info for user {user_id}")
            logger.info(f"Account: {account_info.email_address} ({account_info.display_name})")
            logger.info(f"Organization: {account_info.organization_name} (Role: {account_info.organization_role})")
        except Exception as e:
            logger.error(f"Failed to get account info for user {user_id}: {e}")
            # 即使取得帳戶資訊失敗，仍然繼續儲存 token
            account_info = None

        # 3. 取得用戶設定（資料庫模型）
        from app.db.models import User
        user = db.get(User, user_id)
        if not user or not user.settings:
            logger.error(f"User or settings not found for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=http_request.state.translate("user.settings_not_found"),
            )

        db_settings = user.settings

        # 4. 更新 additional_settings 中的 claudeCode
        additional_settings = db_settings.additional_settings or {}
        claude_additional = additional_settings.get("claudeCode", {})

        claude_additional["subscriptionAuthCode"] = oauth_request.auth_code
        claude_additional["subscriptionAccessToken"] = result.access_token
        claude_additional["subscriptionRefreshToken"] = result.refresh_token
        claude_additional["subscriptionExpiresAt"] = result.expires_at  # 直接儲存毫秒時間戳

        # 儲存帳戶資訊
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

        # 標記 JSONB 欄位已修改（SQLAlchemy 需要這個來偵測 JSONB 變更）
        flag_modified(db_settings, "additional_settings")

        # 5. 提交到資料庫
        db.commit()
        db.refresh(db_settings)

        logger.info(f"Successfully saved OAuth tokens and account info for user {user_id}")

        # 準備回應資料
        response_data = {
            "success": True,
            "message": http_request.state.translate("oauth.auth_success"),
            "accessToken": result.access_token,
            "refreshToken": result.refresh_token,
            "expiresAt": result.expires_at,  # 直接返回毫秒時間戳
            "needsSync": True,  # 提示前端需要同步到 workspace
        }

        # 如果有帳戶資訊，也一併返回
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
    summary="更新 Access Token",
    description="使用 refresh token 更新 access token",
    responses=build_responses(422, 500, 502),
)
async def refresh_oauth_token(
    oauth_request: OAuthRefreshRequest,
    http_request: Request,
) -> OAuthRefreshResponse:
    """
    更新 Access Token

    Args:
        oauth_request: 包含 refreshToken 的請求

    Returns:
        包含新的 accessToken, refreshToken, expiresAt 的回應

    Raises:
        HTTPException: 當更新失敗時
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
    summary="OAuth 服務健康檢查",
)
async def oauth_health_check(request: Request):
    """OAuth 服務健康檢查"""
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
