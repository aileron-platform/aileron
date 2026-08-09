"""Service and provider-neutral OIDC health routes."""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.auth.token_validation import JWKSFetchError, get_jwt_utils
from app.modules.workspace.runtime.assertions import RuntimeAssertionService

router = APIRouter(prefix="/health", tags=["Health check"])


@router.get("", summary="Service health check", responses=build_responses(500))
async def health_check() -> dict[str, object]:
    """Return service health status and version information."""
    return {
        "status": "healthy",
        "service": "workspace-manager",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/oidc",
    summary="OIDC provider health check",
    responses=build_responses(500, 503),
)
async def oidc_health_check(request: Request) -> JSONResponse:
    """Check the configured issuer Discovery and JWKS endpoints."""
    config = get_settings()
    translate = request.state.translate
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        RuntimeAssertionService.from_settings()
        jwt_utils = get_jwt_utils()
        jwt_utils.config = config
        discovery = await jwt_utils.fetch_discovery(force=True)
        await jwt_utils.fetch_jwks(force=True)
        return JSONResponse(
            content={
                "status": "healthy",
                "service": "oidc",
                "issuer": discovery.issuer,
                "message": translate("health.oidc.reachable"),
                "timestamp": timestamp,
            }
        )
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "oidc",
                "issuer": config.OIDC_ISSUER_URL,
                "message": translate("health.oidc.timeout"),
                "timestamp": timestamp,
            },
        )
    except (JWKSFetchError, httpx.HTTPError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "oidc",
                "issuer": config.OIDC_ISSUER_URL,
                "message": translate("health.oidc.connection_failed"),
                "timestamp": timestamp,
            },
        )
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "oidc",
                "issuer": config.OIDC_ISSUER_URL,
                "message": translate("health.oidc.unexpected_error"),
                "timestamp": timestamp,
            },
        )
