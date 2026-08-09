"""Authenticate Manager browser requests with opaque sessions and enforce CSRF."""

from __future__ import annotations

import fnmatch
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings
from app.core.api_error import authorization_error_detail
from app.db.database import SessionLocal
from app.modules.auth.request_authentication import (
    ManagerRequestAuthentication,
    ManagerRequestAuthenticationError,
    ManagerRequestEvidence,
)

SESSION_COOKIE_NAME = "aileron_session"
CSRF_HEADER_NAME = "X-CSRF-Token"

AUTHENTICATION_ERROR_MESSAGE_KEYS = {
    "MANAGER_SESSION_REQUIRED": "auth.manager_session.required",
    "PLATFORM_AUTHORIZATION_DENIED": "auth.platform_authorization.denied",
    "MANAGER_SESSION_ORIGIN_INVALID": "auth.manager_session.origin_invalid",
    "MANAGER_SESSION_CSRF_INVALID": "auth.manager_session.csrf_invalid",
}


class ManagerSessionAuthenticationMiddleware(BaseHTTPMiddleware):
    """Resolve local Manager sessions and reject unsafe cross-origin mutation."""

    def __init__(
        self,
        app,
        *,
        exclude_paths: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.config = get_settings()
        self.exclude_paths = set(
            exclude_paths
            or [
                "/",
                "/health",
                "/health/oidc",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/api/v1/oauth2/login",
                "/api/v1/oauth2/callback",
            ]
        )
        self.exclude_patterns = tuple(exclude_patterns or ["/docs/*", "/redoc/*"])

    def _is_excluded_path(self, path: str) -> bool:
        return path in self.exclude_paths or any(
            fnmatch.fnmatch(path, pattern) for pattern in self.exclude_patterns
        )

    @staticmethod
    def _capture_runtime_request(request: Request) -> bool:
        if not request.url.path.startswith("/api/v1/internal/"):
            return False
        authorization = request.headers.get("Authorization", "")
        token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
        request.state.auth_exempt = True
        request.state.auth_valid = False
        request.state.runtime_control_token = token or None
        request.state.runtime_workspace_id = request.headers.get("X-Workspace-ID")
        request.state.runtime_instance_id = request.headers.get("X-Runtime-Instance-ID")
        return True

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request.state.auth_enabled = True
        request.state.auth_valid = False
        request.state.user_id = None

        if self._capture_runtime_request(request) or self._is_excluded_path(
            request.url.path
        ):
            request.state.auth_exempt = True
            return await call_next(request)

        try:
            authenticated = ManagerRequestAuthentication(
                session_factory=SessionLocal,
                platform_public_origin=self.config.PLATFORM_PUBLIC_ORIGIN,
            ).authenticate(
                ManagerRequestEvidence(
                    session_handle=request.cookies.get(SESSION_COOKIE_NAME),
                    method=request.method,
                    origin=request.headers.get("Origin"),
                    csrf_token=request.headers.get(CSRF_HEADER_NAME),
                )
            )
        except ManagerRequestAuthenticationError as exc:
            message_key = AUTHENTICATION_ERROR_MESSAGE_KEYS[exc.error_code]
            translate = getattr(request.state, "translate", None)
            message = translate(message_key) if callable(translate) else message_key
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": authorization_error_detail(
                        exc.error_code,
                        message,
                    )
                },
            )

        request.state.auth_valid = True
        request.state.user_id = authenticated.user.id
        request.state.authenticated_manager_request = authenticated
        request.state.authorization_actor = authenticated.actor
        return await call_next(request)


__all__ = [
    "CSRF_HEADER_NAME",
    "ManagerSessionAuthenticationMiddleware",
    "SESSION_COOKIE_NAME",
]
