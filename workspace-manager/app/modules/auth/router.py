"""
OAuth2 Authentication Routes

Provides API endpoints for Keycloak OAuth2/OIDC authentication process.
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
# Request/response models
# ============================================================================


class LoginURLResponse(BaseModel):
    """Login URL response"""
    authorization_url: str = Field(..., description="Keycloak AuthorizationEndpoint URL")
    state: str = Field(..., description="CSRF protection token")


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Expiration time (seconds)")
    scope: str = Field(..., description="Token scope")


class CallbackRequest(BaseModel):
    """OAuth callback request"""
    code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="CSRF token")


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Refresh token")


class UserInfo(BaseModel):
    """User information"""
    sub: str = Field(..., description="User unique identifier")
    preferred_username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="Email")
    given_name: Optional[str] = Field(None, description="Given name")
    family_name: Optional[str] = Field(None, description="Family name")
    roles: list[str] = Field(default_factory=list, description="User roles")
    local_user_id: Optional[str] = Field(None, description="Local DB user ID")


# ============================================================================
# Dependency injection
# ============================================================================


async def require_auth_enabled():
    """Require authentication feature enabled"""
    config = get_keycloak_config()
    if not config.enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication is not enabled"
        )
    return config


# ============================================================================
# RouterEndpoint
# ============================================================================


@router.get(
    "/login",
    response_model=LoginURLResponse,
    summary="Get Keycloak login URL",
    responses=build_responses(501),
)
async def login(
    request: Request,
    redirect_uri: Optional[str] = None,
    config = Depends(require_auth_enabled)
):
    """
    Generate Keycloak authorization URL and redirect user to login page

    Args:
        request: FastAPI request object
        redirect_uri: Redirect URL after login (optional)
        config: Keycloak configuration

    Returns:
        LoginURLResponse: Contains authorization URL and state token

    When redirect_uri is None, use request's Referer or default frontend URL
    """
    from secrets import token_urlsafe

    # Generate CSRF protection token
    state = token_urlsafe(32)

    # Build redirect URI
    if redirect_uri is None:
        referer = request.headers.get("referer")
        if referer:
            # Extract base URL from referer
            parsed = urlparse(referer)
            redirect_uri = f"{parsed.scheme}://{parsed.netloc}/"
        else:
            # Use default frontend URL
            redirect_uri = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:8082/")

    # Build Keycloak authorization URL
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
    summary="Redirect directly to Keycloak login page",
    responses=build_responses(501),
)
async def login_redirect(
    request: Request,
    redirect_uri: Optional[str] = None,
    config = Depends(require_auth_enabled)
):
    """
    Redirect to Keycloak login page

    This is a convenient endpoint that directly redirects browser to Keycloak

    Args:
        request: FastAPI request object
        redirect_uri: Redirect URL after login
        config: Keycloak configuration

    Returns:
        RedirectResponse: Redirect to Keycloak
    """
    from secrets import token_urlsafe

    # Generate CSRF protection token
    state = token_urlsafe(32)

    # Build redirect URI
    if redirect_uri is None:
        redirect_uri = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:8082/")

    # Build Keycloak authorization URL
    auth_url = (
        f"{config.external_server_url}/protocol/openid-connect/auth"
        f"?client_id={config.client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid profile email"
        f"&state={state}"
    )

    # Redirect to Keycloak
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/callback",
    response_model=TokenResponse,
    summary="Handle Keycloak OAuth2 callback",
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
    Handle Keycloak OAuth2 callback

    Keycloak will redirect to this endpoint after user login succeeds

    Args:
        request: FastAPI request object
        code: OAuth authorization code
        state: CSRF token
        error: Error code (if login fails)
        error_description: Error description
        config: Keycloak configuration

    Returns:
        TokenResponse or error response

    Note: This is a simplified implementation, actual production environment needs:
    - Verify state token
    - Handle token storage (httpOnly cookie)
    - Create or update local user record
    """
    # Handle error scenarios
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {error_description or error}"
        )

    # TODO: Verify state token（CSRF protection）

    try:
        # Exchange authorization code for tokens
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

        # TODO: Store refresh token to database
        # TODO: Create or update local user record
        # TODO: Set httpOnly cookie

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
    summary="Use refresh token to update access token",
    responses=build_responses(400, 502, 501),
)
async def refresh_token(
    request: RefreshTokenRequest,
    config = Depends(require_auth_enabled)
):
    """
    Use refresh token to get new access token

    Args:
        request: Request containing refresh token
        config: Keycloak configuration

    Returns:
        TokenResponse: New token

    Note: Actual implementation needs to verify refresh token is valid and not revoked
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
    Logout user

    Clear local session and optionally call Keycloak logout

    Args:
        request: FastAPI request object
        config: Keycloak configuration

    Returns:
        Success message

    Note: Actual implementation needs:
    - Get refresh token from request
    - Delete refresh token from database
    - Clear httpOnly cookie
    - Optional: Call Keycloak end session endpoint
    """
    # TODO: Implement complete logout logic
    return {"message": "Logout endpoint - implementation pending"}


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    request: Request,
    config = Depends(require_auth_enabled)
):
    """
    Get current authenticated user information

    Parse user information from JWT token in Authorization header

    Args:
        request: FastAPI request object (should contain Authorization header)
        config: Keycloak configuration

    Returns:
        UserInfo: Current user information

    Raises:
        HTTPException: When token is invalid or missing
    """
    # Extract token from authorization header
    authorization = request.headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ")[1]

    try:
        # Validate and decode token
        jwt_utils = get_jwt_utils()
        payload = jwt_utils.decode_token(token)

        # Extract roles (from realm_access.roles)
        realm_access = payload.get("realm_access", {})
        roles = realm_access.get("roles", [])

        # Query local DB user ID
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

        # Build user info response
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
    Get authentication configuration information (public endpoint)

    Return OpenID Connect configuration needed by frontend

    Args:
        config: Keycloak configuration

    Returns:
        OpenID Connect configuration
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
