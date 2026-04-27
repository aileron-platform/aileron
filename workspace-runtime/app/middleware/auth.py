"""Authentication middleware"""

import logging
import os
from fastapi import Request, status, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import get_auth_service
from app.utils.datetime_utils import utcnow

# Read internal API token from environment variable (for dev/test environments only)
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN")

logger = logging.getLogger(__name__)


def get_current_user_id(request: Request) -> str:
    """
    Get current user ID from request

    This function is used for FastAPI Depends dependency injection

    Args:
        request: FastAPI Request object

    Returns:
        str: User ID

    Raises:
        HTTPException: When user is not authenticated
    """
    if not hasattr(request.state, "user_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: User not authenticated",
        )
    return request.state.user_id


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Token validation middleware"""

    PUBLIC_PATHS = {
        "/",
        "/favicon.ico",
    }
    PUBLIC_PREFIXES = (
        "/docs",
        "/openapi",
        "/redoc",
        "/health",
        "/static",
        "/api/v1/client-browser-relay",  # dev-browser client relay API (no token required)
        "/api/v1/oauth2",  # Keycloak OAuth2 endpoints (handled by JWT middleware in workspace-manager)
    )
    INTERNAL_API_PREFIXES = (
        "/api/v1/internal/",  # Internal API uses different authentication mechanism
    )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        normalized_path = path.rstrip("/") or "/"

        # Skip public paths and OPTIONS requests
        if request.method == "OPTIONS" or self._is_public(path, normalized_path):
            return await call_next(request)

        # Skip WebSocket upgrade requests
        # Design decision: WebSocket connections cannot be authenticated via HTTP middleware because
        # middleware cannot reject connections and send WebSocket close frames before handshake.
        # WS endpoints requiring authentication (e.g., agent-session) call
        # authenticate_websocket() after accept; unauthenticated WS endpoints (e.g., terminal,
        # browser-relay) rely on container network isolation as security boundary.
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Internal API paths skip authentication middleware (handled by router dependency)
        if self._is_internal_api(path):
            return await call_next(request)

        # Check internal API token (for testing and internal service calls)
        # This feature is only enabled when INTERNAL_API_TOKEN environment variable is set
        if INTERNAL_API_TOKEN:
            internal_token = request.headers.get("X-Internal-Token")
            if internal_token and internal_token == INTERNAL_API_TOKEN:
                # Create a test user for internal API token
                class TestUser:
                    def __init__(self):
                        self.id = 'internal-test-user'
                        self.user_id = 'internal-test-user'

                request.state.user = TestUser()
                request.state.user_id = 'internal-test-user'
                logger.debug(f"Internal token auth successful for {path}")
                return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.lower().startswith("bearer "):
            logger.warning(f"Missing or invalid auth header for {path}")
            return self._unauthorized("Missing or invalid Authorization header", "MISSING_AUTH_HEADER")

        try:
            token = auth_header.split(" ", 1)[1].strip()

            if not token:
                logger.warning(f"Empty token for {path}")
                return self._unauthorized("Empty authentication token", "EMPTY_TOKEN")

            # Validate token
            service = get_auth_service()
            user = await service.validate_access_token(token)

            if not user:
                logger.warning(f"Invalid or expired token for {path}, token: {token[:20]}...")
                return self._unauthorized(
                    "Token expired or invalid. Please refresh your token or login again.",
                    "TOKEN_EXPIRED"
                )

            # Set user info to request state
            request.state.user = user
            request.state.user_id = user.id
            logger.debug(f"Auth successful for {path}: user_id={user.id}")
            return await call_next(request)
        except Exception as e:
            logger.error(f"Auth error for {path}: {e}", exc_info=True)
            return self._unauthorized("Authentication failed", "AUTH_ERROR")

    def _is_public(self, path: str, normalized_path: str) -> bool:
        """Check if path is public"""
        if normalized_path in self.PUBLIC_PATHS:
            return True

        return any(path.startswith(prefix) for prefix in self.PUBLIC_PREFIXES)

    def _is_internal_api(self, path: str) -> bool:
        """Check if path is internal API"""
        return any(path.startswith(prefix) for prefix in self.INTERNAL_API_PREFIXES)

    @staticmethod
    def _unauthorized(message: str = "Unauthorized", error_code: str = "UNAUTHORIZED") -> JSONResponse:
        """Return unauthorized response with error code for frontend handling"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "detail": message,
                "error_code": error_code,
                "timestamp": utcnow().isoformat()
            },
            headers={"WWW-Authenticate": "Bearer"},
        )