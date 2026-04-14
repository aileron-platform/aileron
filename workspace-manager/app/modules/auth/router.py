"""
OAuth2 認證路由

提供 Keycloak OAuth2/OIDC 認證流程的 API 端點。
"""

import os
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.openapi import build_responses
from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTValidationError, get_jwt_utils

router = APIRouter(prefix="/oauth2", tags=["Keycloak OAuth2"])


# ============================================================================
# 請求/響應模型
# ============================================================================


class LoginURLResponse(BaseModel):
    """登入 URL 響應"""
    authorization_url: str = Field(..., description="Keycloak 授權端點 URL")
    state: str = Field(..., description="CSRF protection token")


class TokenResponse(BaseModel):
    """Token 響應"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field(default="Bearer", description="Token 類型")
    expires_in: int = Field(..., description="過期時間（秒）")
    scope: str = Field(..., description="Token 作用域")


class CallbackRequest(BaseModel):
    """OAuth callback 請求"""
    code: str = Field(..., description="OAuth 授權碼")
    state: Optional[str] = Field(None, description="CSRF token")


class RefreshTokenRequest(BaseModel):
    """刷新 token 請求"""
    refresh_token: str = Field(..., description="Refresh token")


class UserInfo(BaseModel):
    """用戶信息"""
    sub: str = Field(..., description="用戶唯一標識")
    preferred_username: str = Field(..., description="用戶名")
    email: Optional[str] = Field(None, description="Email")
    given_name: Optional[str] = Field(None, description="名字")
    family_name: Optional[str] = Field(None, description="姓氏")
    roles: list[str] = Field(default_factory=list, description="用戶角色")
    local_user_id: Optional[str] = Field(None, description="Local DB user ID")


# ============================================================================
# 依賴注入
# ============================================================================


async def require_auth_enabled():
    """要求認證功能已啟用"""
    config = get_keycloak_config()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication is not enabled"
        )
    return config


# ============================================================================
# 路由端點
# ============================================================================


@router.get(
    "/login",
    response_model=LoginURLResponse,
    summary="取得 Keycloak 登入 URL",
    responses=build_responses(501),
)
async def login(
    request: Request,
    redirect_uri: Optional[str] = None,
    config = Depends(require_auth_enabled)
):
    """
    生成 Keycloak 授權 URL 並重定向用戶到登入頁面

    Args:
        request: FastAPI 請求對象
        redirect_uri: 登入後的重定向 URL（可選）
        config: Keycloak 配置

    Returns:
        LoginURLResponse: 包含授權 URL 和 state token

    當 redirect_uri 為 None 時，使用請求的 Referer 或預設前端 URL
    """
    from secrets import token_urlsafe

    # 生成 CSRF protection token
    state = token_urlsafe(32)

    # 構建 redirect URI
    if redirect_uri is None:
        referer = request.headers.get("referer")
        if referer:
            # 從 referer 提取基礎 URL
            parsed = urlparse(referer)
            redirect_uri = f"{parsed.scheme}://{parsed.netloc}/"
        else:
            # 使用預設前端 URL
            redirect_uri = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:8082/")

    # 構建 Keycloak 授權 URL
    auth_url = (
        f"{config.external_server_url}/protocol/openid-connect/auth"
        f"?client_id={config.client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )

    return LoginURLResponse(
        authorization_url=auth_url,
        state=state
    )


@router.get(
    "/login/redirect",
    summary="直接重導到 Keycloak 登入頁",
    responses=build_responses(501),
)
async def login_redirect(
    request: Request,
    redirect_uri: Optional[str] = None,
    config = Depends(require_auth_enabled)
):
    """
    重定向到 Keycloak 登入頁面

    這是一個便捷端點，直接重定向瀏覽器到 Keycloak

    Args:
        request: FastAPI 請求對象
        redirect_uri: 登入後的重定向 URL
        config: Keycloak 配置

    Returns:
        RedirectResponse: 重定向到 Keycloak
    """
    from secrets import token_urlsafe

    # 生成 CSRF protection token
    state = token_urlsafe(32)

    # 構建 redirect URI
    if redirect_uri is None:
        redirect_uri = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:8082/")

    # 構建 Keycloak 授權 URL
    auth_url = (
        f"{config.external_server_url}/protocol/openid-connect/auth"
        f"?client_id={config.client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )

    # 重定向到 Keycloak
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/callback",
    response_model=TokenResponse,
    summary="處理 Keycloak OAuth2 Callback",
    responses=build_responses(400, 502, 501),
)
async def callback(
    request: Request,
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    config = Depends(require_auth_enabled)
):
    """
    處理 Keycloak OAuth2 callback

    Keycloak 在用戶登入成功後會重定向到此端點

    Args:
        request: FastAPI 請求對象
        code: OAuth 授權碼
        state: CSRF token
        error: 錯誤代碼（如果登入失敗）
        error_description: 錯誤描述
        config: Keycloak 配置

    Returns:
        TokenResponse 或錯誤響應

    注意：這是一個簡化實現，實際生產環境需要：
    - 驗證 state token
    - 處理 token 存儲（httpOnly cookie）
    - 創建或更新本地用戶記錄
    """
    # 處理錯誤情況
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {error_description or error}"
        )

    # TODO: 驗證 state token（CSRF protection）

    try:
        # 交換授權碼獲取 tokens
        import httpx

        token_url = f"{config.server_url}/protocol/openid-connect/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "redirect_uri": str(request.url_for("callback")),
                }
            )
            response.raise_for_status()
            token_data = response.json()

        # TODO: 存儲 refresh token 到資料庫
        # TODO: 創建或更新本地用戶記錄
        # TODO: 設置 httpOnly cookie

        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token"),
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", config.jwt_access_token_expire_minutes * 60),
            scope=token_data.get("scope", "openid"),
        )

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="使用 Refresh Token 更新 Access Token",
    responses=build_responses(400, 502, 501),
)
async def refresh_token(
    request: RefreshTokenRequest,
    config = Depends(require_auth_enabled)
):
    """
    使用 refresh token 獲取新的 access token

    Args:
        request: 包含 refresh token 的請求
        config: Keycloak 配置

    Returns:
        TokenResponse: 新的 token

    注意：實際實作需要驗證 refresh token 是否有效且未撤銷
    """
    try:
        import httpx

        token_url = f"{config.server_url}/protocol/openid-connect/token"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "refresh_token": request.refresh_token,
                }
            )
            response.raise_for_status()
            token_data = response.json()

        return TokenResponse(
            access_token=token_data["access_token"],
            refresh_token=token_data.get("refresh_token", request.refresh_token),
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", config.jwt_access_token_expire_minutes * 60),
            scope=token_data.get("scope", "openid"),
        )

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.post("/logout")
async def logout(
    request: Request,
    config = Depends(require_auth_enabled)
):
    """
    登出用戶

    清除本地 session 並可選調用 Keycloak logout

    Args:
        request: FastAPI 請求對象
        config: Keycloak 配置

    Returns:
        成功訊息

    注意：實際實作需要：
    - 從請求中獲取 refresh token
    - 從資料庫刪除 refresh token
    - 清除 httpOnly cookie
    - 可選：調用 Keycloak end session endpoint
    """
    # TODO: 實作完整的登出邏輯
    return {"message": "Logout endpoint - implementation pending"}


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    request: Request,
    config = Depends(require_auth_enabled)
):
    """
    獲取當前認證用戶的信息

    從 Authorization header 中的 JWT token 解析用戶信息

    Args:
        request: FastAPI 請求對象（應包含 Authorization header）
        config: Keycloak 配置

    Returns:
        UserInfo: 當前用戶信息

    Raises:
        HTTPException: 當 token 無效或缺失時
    """
    # 從 Authorization header 提取 token
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        # 驗證並解碼 token
        jwt_utils = get_jwt_utils()
        payload = jwt_utils.decode_token(token)

        # 提取角色（從 realm_access.roles）
        realm_access = payload.get("realm_access", {})
        roles = realm_access.get("roles", [])

        # 查詢 local DB user ID
        local_user_id = None
        keycloak_id = payload.get("sub")
        if keycloak_id:
            try:
                from app.db.database import SessionLocal
                from app.services.user_service import UserService
                db = SessionLocal()
                try:
                    user_service = UserService(db)
                    local_user = user_service.get_by_keycloak_id(keycloak_id)
                    if local_user:
                        local_user_id = local_user.id
                finally:
                    db.close()
            except Exception:
                pass

        # 構建用戶信息響應
        return UserInfo(
            sub=payload.get("sub", ""),
            preferred_username=payload.get("preferred_username", ""),
            email=payload.get("email"),
            given_name=payload.get("given_name"),
            family_name=payload.get("family_name"),
            roles=roles,
            local_user_id=local_user_id,
        )

    except JWTValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/config")
async def get_auth_config(config = Depends(get_keycloak_config)):
    """
    獲取認證配置信息（公開端點）

    返回前端需要的 OpenID Connect 配置

    Args:
        config: Keycloak 配置

    Returns:
        OpenID Connect 配置
    """
    if not config.enabled:
        return {"enabled": False}

    return {
        "enabled": True,
        "authority": config.external_server_url,
        "clientId": config.client_id,
        "scope": "openid profile email",
        "responseType": "code",
    }
