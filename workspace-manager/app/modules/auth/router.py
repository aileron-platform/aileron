"""Manager OIDC BFF login, callback, session bootstrap, and logout routes."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.database import get_db
from app.modules.auth.middleware import SESSION_COOKIE_NAME
from app.modules.auth.oidc_core import (
    OIDCCallbackError,
    OIDCCore,
    OIDCLoginRateLimitError,
)
from app.modules.auth.request_authentication import AuthenticatedManagerRequest
from app.modules.auth.session import ManagerSessionService
from app.modules.authorization.operation_policy import allowed_platform_operations

router = APIRouter(prefix="/oauth2", tags=["OIDC BFF"])
LOGIN_ATTEMPT_COOKIE_NAME = "aileron_login_attempt"
WORKSPACE_GATEWAY_SESSION_COOKIE_NAME = "aileron_workspace_gateway_session"
LOGIN_ATTEMPT_COOKIE_MAX_AGE = 600
MANAGER_COOKIE_PATH = "/api/v1"
WORKSPACE_GATEWAY_COOKIE_PATH = "/workspaces"


def _login_attempt_bucket(request: Request) -> str:
    existing = request.cookies.get(LOGIN_ATTEMPT_COOKIE_NAME)
    if existing and len(existing) >= 32 and len(existing) <= 128:
        return existing
    return secrets.token_urlsafe(32)


class SessionUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    username: str
    email: str | None
    display_name: str | None = None
    platform_role: str = "member"
    allowed_operations: list[str] = Field(default_factory=list)


class SessionBootstrap(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user: SessionUser
    csrf_token: str
    absolute_expires_at: str


class LogoutResponse(BaseModel):
    provider_logout_url: str | None = None


@router.get("/login")
async def login(
    request: Request,
    return_path: str = Query(default="/"),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    attempt_bucket = _login_attempt_bucket(request)
    try:
        start = await OIDCCore(db).begin_login(
            return_path=return_path,
            attempt_bucket=attempt_bucket,
        )
    except OIDCLoginRateLimitError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS) from exc
    response = RedirectResponse(
        start.authorization_url,
        status_code=status.HTTP_302_FOUND,
    )
    config = get_settings()
    response.set_cookie(
        LOGIN_ATTEMPT_COOKIE_NAME,
        attempt_bucket,
        secure=config.PLATFORM_PUBLIC_ORIGIN.startswith("https://"),
        httponly=True,
        samesite="lax",
        path=MANAGER_COOKIE_PATH,
        max_age=LOGIN_ATTEMPT_COOKIE_MAX_AGE,
    )
    return response


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        result = await OIDCCore(db).complete_callback(code=code, state=state)
    except OIDCCallbackError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "OIDC_CALLBACK_INVALID"},
        ) from exc
    config = get_settings()
    response = RedirectResponse(
        f"{config.PLATFORM_PUBLIC_ORIGIN}{result.return_path}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.set_cookie(
        SESSION_COOKIE_NAME,
        result.session.handle,
        secure=config.PLATFORM_PUBLIC_ORIGIN.startswith("https://"),
        httponly=True,
        samesite="lax",
        path=MANAGER_COOKIE_PATH,
        max_age=None,
    )
    response.set_cookie(
        WORKSPACE_GATEWAY_SESSION_COOKIE_NAME,
        result.session.handle,
        secure=True,
        httponly=True,
        samesite="none",
        path=WORKSPACE_GATEWAY_COOKIE_PATH,
        max_age=None,
    )
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        secure=config.PLATFORM_PUBLIC_ORIGIN.startswith("https://"),
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(
        WORKSPACE_GATEWAY_SESSION_COOKIE_NAME,
        secure=config.PLATFORM_PUBLIC_ORIGIN.startswith("https://"),
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(LOGIN_ATTEMPT_COOKIE_NAME, path=MANAGER_COOKIE_PATH)
    return response


@router.get("/session", response_model=SessionBootstrap)
async def session_bootstrap(
    request: Request,
) -> SessionBootstrap:
    authenticated = getattr(request.state, "authenticated_manager_request", None)
    if not isinstance(authenticated, AuthenticatedManagerRequest):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": "MANAGER_SESSION_REQUIRED"},
        )
    return SessionBootstrap(
        user=SessionUser(
            id=authenticated.user.id,
            username=authenticated.user.username,
            email=authenticated.user.email,
            display_name=authenticated.user.display_name,
            platform_role=authenticated.actor.platform_role.value,
            allowed_operations=list(
                allowed_platform_operations(authenticated.actor.platform_role)
            ),
        ),
        csrf_token=authenticated.csrf_token,
        absolute_expires_at=authenticated.absolute_expires_at.isoformat(),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LogoutResponse:
    authenticated = getattr(request.state, "authenticated_manager_request", None)
    if not isinstance(authenticated, AuthenticatedManagerRequest):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"errorCode": "MANAGER_SESSION_REQUIRED"},
        )
    ManagerSessionService(db).revoke_by_id(authenticated.session_id)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        secure=get_settings().PLATFORM_PUBLIC_ORIGIN.startswith("https://"),
        httponly=True,
        samesite="lax",
        path=MANAGER_COOKIE_PATH,
    )
    response.delete_cookie(
        WORKSPACE_GATEWAY_SESSION_COOKIE_NAME,
        secure=True,
        httponly=True,
        samesite="none",
        path=WORKSPACE_GATEWAY_COOKIE_PATH,
    )
    return LogoutResponse(provider_logout_url=await OIDCCore(db).provider_logout_url())
