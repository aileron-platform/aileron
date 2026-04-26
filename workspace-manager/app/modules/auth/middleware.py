"""
JWT Authentication Middleware

Provides request authentication middleware based on JWT tokens, automatically verifies Bearer tokens and injects user information.
Integrates user synchronization service, automatically creates or updates user records in local database.
"""

import time
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config.settings import get_settings
from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTValidationError, get_jwt_utils
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _ensure_local_user(payload: dict) -> str | None:
    """After successful JWT verification, ensure local DB has corresponding user record and auto-join to default-workspace.

    Returns:
        str | None: local DB user ID, returns None if failed
    """
    keycloak_id = payload.get("sub")
    if not keycloak_id:
        return None
    try:
        from app.db.database import SessionLocal
        from app.services.user_service import UserService

        db = SessionLocal()
        try:
            user_service = UserService(db)
            existing = user_service.get_by_keycloak_id(keycloak_id)
            if not existing:
                existing = user_service.create_from_jwt_payload(payload)
                logger.info(f"Auto-created local user for keycloak_id={keycloak_id}")
            return existing.id if existing else None
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"User sync failed for keycloak_id={keycloak_id}: {e}")
        return None


class JWTAuthenticationMiddleware(BaseHTTPMiddleware):
    """
    JWT Authentication Middleware

    Automatically extracts Bearer token from request, verifies its validity, and injects user information into request.state.

    Features:
    - Extract Bearer token from Authorization header
    - Verify token signature, expiry time, issuer, and audience
    - Inject decoded user information into request.state.current_user
    - Support skip logic when authentication is not enabled
    - Support optional path exclusion (e.g., /health, /public/*)

    Usage example:
        app.add_middleware(
            JWTAuthenticationMiddleware,
            exclude_paths=["/health", "/docs", "/redoc"],
        )
    """

    def __init__(
        self,
        app,
        exclude_paths: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ):
        """
        Initialize JWT Authentication Middleware

        Args:
            app: FastAPI application instance
            exclude_paths: List of complete paths to exclude
            exclude_patterns: List of path patterns to exclude (supports prefix matching)
        """
        super().__init__(app)
        self.config = get_keycloak_config()
        self.settings = get_settings()
        self.exclude_paths = set(exclude_paths or [])
        self.exclude_patterns = exclude_patterns or []

        # Add default exclude paths
        default_excludes = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/api/v1/health",
        ]
        for path in default_excludes:
            self.exclude_paths.add(path)

    def _authenticate_internal_request(self, request: Request) -> bool:
        """Verify internal token used by container internal service requests."""
        expected_token = getattr(self.settings, "INTERNAL_API_TOKEN", "")
        provided_token = request.headers.get("X-Internal-Token")

        if not provided_token:
            return False

        valid_tokens = {expected_token} if expected_token else set()
        if getattr(self.settings, "ENV", "").lower() == "testing":
            valid_tokens.add("test-internal-token")

        if provided_token not in valid_tokens:
            logger.warning("Invalid internal API token for path=%s", request.url.path)
            return False

        request.state.current_user = {
            "sub": "internal-service",
            "preferred_username": "internal-service",
            "roles": ["internal"],
        }
        request.state.auth_valid = True
        request.state.auth_exempt = True
        request.state.internal_authenticated = True
        request.state.user_id = None
        logger.debug("Internal API token authenticated for path=%s", request.url.path)
        return True

    def _is_excluded_path(self, path: str) -> bool:
        """
        Check if path should exclude authentication

        Args:
            path: Request path

        Returns:
            True if path should exclude authentication
        """
        # Exact match exclusion
        if path in self.exclude_paths:
            return True

        # Prefix match exclusion (supports * wildcard)
        for pattern in self.exclude_patterns:
            # Handle * wildcard
            if pattern.endswith("*"):
                # Remove * and check prefix
                prefix = pattern[:-1]
                if path.startswith(prefix):
                    return True
            else:
                # No wildcard, use exact prefix matching
                if path.startswith(pattern):
                    return True

        return False

    async def dispatch(self, request: Request, call_next):
        """
        Handle each request, extract and verify JWT token

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler

        Returns:
            HTTP response
        """
        if not self.config.enabled:
            request.state.auth_enabled = False
            request.state.current_user = None
            request.state.auth_valid = False
            return await call_next(request)

        request.state.auth_enabled = True

        # Check if path excludes authentication
        if self._is_excluded_path(request.url.path):
            logger.debug(f"Path {request.url.path} excluded from authentication")
            request.state.current_user = None
            request.state.auth_exempt = True
            return await call_next(request)

        if self._authenticate_internal_request(request):
            return await call_next(request)

        # Extract Bearer token
        token = self._extract_bearer_token(request)

        if not token:
            # No token provided, set current_user to None
            # Note: Do not directly return 401 here, let route decide if authentication is required
            request.state.current_user = None
            request.state.auth_valid = False
            logger.debug(f"Authentication skipped: no token provided for {request.url.path}")
            return await call_next(request)

        # Record authentication attempt (do not record full token)
        token_preview = f"{token[:20]}..." if len(token) > 20 else token
        logger.info(f"Authentication attempt: {request.method} {request.url.path}, token={token_preview}")

        # Validate token (timed)
        validation_start = time.perf_counter()
        try:
            user_info = await self._validate_token(token)
            validation_duration = time.perf_counter() - validation_start

            request.state.current_user = user_info
            request.state.auth_valid = True
            request.state.auth_validation_duration = validation_duration

            # User sync: ensure local DB has corresponding record, auto-create and join default-workspace if not exists
            # Return local DB user ID for correct subsequent API queries
            local_user_id = await _ensure_local_user(user_info)

            # Set user_id (prefer local DB ID, fallback to Keycloak sub)
            keycloak_id = user_info.get('sub')
            request.state.user_id = local_user_id or keycloak_id

            # Authentication success log (includes performance metrics)
            logger.info(f"Authentication successful: user_id={request.state.user_id}, path={request.url.path}, duration={validation_duration*1000:.2f}ms")

        except JWTValidationError as e:
            validation_duration = time.perf_counter() - validation_start
            # Authentication failed log (do not record full error stack to avoid log injection attacks)
            logger.warning(f"Authentication failed: {request.url.path}, reason={str(e)}, duration={validation_duration*1000:.2f}ms")
            request.state.current_user = None
            request.state.auth_valid = False
            request.state.auth_error = str(e)

            # Do not directly return 401, let route decide how to handle
            # If route requires authentication, will use require_authenticated_user dependency

        except Exception as e:
            validation_duration = time.perf_counter() - validation_start
            logger.error(f"Unexpected error during authentication: {e}, duration={validation_duration*1000:.2f}ms")
            request.state.current_user = None
            request.state.auth_valid = False
            request.state.auth_error = f"Authentication error: {str(e)}"

        return await call_next(request)

    def _extract_bearer_token(self, request: Request) -> Optional[str]:
        """
        Extract Bearer token from Authorization header

        Args:
            request: FastAPI request object

        Returns:
            Bearer token string, returns None if not exists
        """
        authorization = request.headers.get("Authorization")

        if not authorization:
            return None

        # Check if is Bearer token
        if not authorization.startswith("Bearer "):
            logger.warning(f"Authorization header format error: {authorization[:20]}...")
            return None

        # Extract token
        token = authorization.split(" ", 1)[1].strip()

        if not token:
            logger.warning("Authorization header is empty")
            return None

        return token

    async def _validate_token(self, token: str) -> dict:
        """
        Verify JWT token

        Verification items:
        - Signature verification (using JWKS public key)
        - Expiry time check (exp claim)
        - Issuer check (iss claim)
        - Audience check (aud claim)

        Args:
            token: JWT token string

        Returns:
            Decoded token payload (user information)

        Raises:
            JWTValidationError: Token verification failed
        """
        jwt_utils = get_jwt_utils()

        # Use async version of decode_token to avoid in async FastAPI environment
        # Call loop.run_until_complete() causing "this event loop is already running" error
        payload = await jwt_utils.decode_token_async(token)

        # Validate required claims
        if not payload.get("sub"):
            raise JWTValidationError("Token missing 'sub' claim")

        return payload


class StrictJWTAuthenticationMiddleware(JWTAuthenticationMiddleware):
    """
    Strict mode JWT Authentication Middleware

    Differences from standard middleware:
    - If token verification fails, directly return 401 error
    - Does not allow routes to decide whether authentication is required
    - Suitable for scenarios where all routes require authentication

    Usage example:
        app.add_middleware(StrictJWTAuthenticationMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        """
        Handle each request, require valid token

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler

        Returns:
            HTTP response or 401 error
        """
        if not self.config.enabled:
            request.state.auth_enabled = False
            request.state.current_user = None
            request.state.auth_valid = False
            return await call_next(request)

        request.state.auth_enabled = True

        # Check if path excludes authentication
        if self._is_excluded_path(request.url.path):
            logger.debug(f"Path {request.url.path} excluded from authentication")
            request.state.current_user = None
            request.state.auth_exempt = True
            return await call_next(request)

        if self._authenticate_internal_request(request):
            return await call_next(request)

        # Extract Bearer token
        token = self._extract_bearer_token(request)

        if not token:
            logger.warning("Missing Authorization header")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": "Missing Authorization header",
                    "message": "Authentication required",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        try:
            user_info = await self._validate_token(token)
            request.state.current_user = user_info
            request.state.auth_valid = True
            logger.debug(f"User {user_info.get('sub')} authentication succeeded")

        except JWTValidationError as e:
            logger.warning(f"Token verification failed: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "error": "Unauthorized",
                    "detail": str(e),
                    "message": "Invalid or expired token",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "Internal Server Error",
                    "detail": "Authentication failed",
                },
            )

        return await call_next(request)
