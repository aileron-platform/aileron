"""Authenticate Runtime HTTP requests with local Execution Grant verification."""

import logging

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
    get_execution_grant_verifier,
)
from app.modules.localization.catalog import get_i18n_service
from app.modules.workspace_access.route_inventory import (
    RuntimeRouteClassificationError,
    RuntimeRouteInventoryError,
    get_runtime_route_inventory,
)

logger = logging.getLogger(__name__)


def get_current_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid user identity",
        )
    return user_id


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Require a locally verified, route-action-bound Execution Grant."""

    PUBLIC_PATHS = {"/health", "/api/v1/client-browser-relay/health"}
    INTERNAL_API_PREFIXES = ("/api/v1/internal/", "/internal/")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if request.method == "OPTIONS" or path in self.PUBLIC_PATHS:
            return await call_next(request)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        if any(path.startswith(prefix) for prefix in self.INTERNAL_API_PREFIXES):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return self._unauthorized(
                request,
                error_code="WORKSPACE_EXECUTION_GRANT_MISSING",
                message_key="authorization.runtime.missing_auth_header",
            )
        grant = authorization[7:].strip()
        if not grant:
            return self._unauthorized(
                request,
                error_code="WORKSPACE_EXECUTION_GRANT_MISSING",
                message_key="authorization.runtime.empty_token",
            )
        try:
            action = get_runtime_route_inventory().classify(
                path=request.url.path,
                method=request.method,
                raw_path=request.scope.get("raw_path"),
            )
            claims = get_execution_grant_verifier().verify(grant, action=action)
        except RuntimeRouteClassificationError as exc:
            return self._authorization_error(
                request,
                status_code=403,
                error_code=exc.error_code,
                message_key="authorization.runtime.action_forbidden",
            )
        except RuntimeRouteInventoryError as exc:
            return self._authorization_error(
                request,
                status_code=503,
                error_code=exc.error_code,
                message_key="authorization.runtime.verification_failed",
            )
        except ExecutionGrantConflict as exc:
            return self._authorization_error(
                request,
                status_code=423,
                error_code=exc.error_code,
                message_key="authorization.runtime.locked",
            )
        except ExecutionGrantInvalid as exc:
            if exc.error_code == "WORKSPACE_EXECUTION_GRANT_ACTION_FORBIDDEN":
                return self._authorization_error(
                    request,
                    status_code=403,
                    error_code=exc.error_code,
                    message_key="authorization.runtime.action_forbidden",
                )
            return self._unauthorized(
                request,
                error_code=exc.error_code,
                message_key="authorization.runtime.token_expired",
            )
        request.state.user_id = claims.subject
        request.state.execution_grant = claims
        return await call_next(request)

    @staticmethod
    def _authorization_error(
        request: Request,
        *,
        status_code: int,
        error_code: str,
        message_key: str,
    ) -> JSONResponse:
        i18n = get_i18n_service()
        preferred_language = (
            request.headers.get("X-Language")
            or request.headers.get("Accept-Language")
            or "zh-TW"
        )
        language = i18n.resolve_language(preferred_language)
        response = JSONResponse(
            status_code=status_code,
            content={
                "detail": {
                    "errorCode": error_code,
                    "message": i18n.translate(message_key, language=language),
                    "details": {},
                }
            },
        )
        response.headers["Content-Language"] = language
        return response

    @classmethod
    def _unauthorized(
        cls,
        request: Request,
        *,
        error_code: str,
        message_key: str,
    ) -> JSONResponse:
        response = cls._authorization_error(
            request,
            status_code=401,
            error_code=error_code,
            message_key=message_key,
        )
        response.headers["WWW-Authenticate"] = "Bearer"
        return response
