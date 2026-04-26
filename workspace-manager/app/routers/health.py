"""Health check routes"""

from datetime import datetime

import httpx
from fastapi import APIRouter, Request

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.auth.config import get_keycloak_config

router = APIRouter(prefix="/health", tags=["Health check"])


@router.get(
    "",
    summary="Service health check",
    responses=build_responses(500),
)
async def health_check() -> dict[str, object]:
    """Return service health status and version information"""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "workspace-manager",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get(
    "/keycloak",
    summary="Keycloak health check",
    responses=build_responses(500, 503),
)
async def keycloak_health_check(request: Request) -> dict[str, object]:
    """Check if Keycloak service is available

    Returns Keycloak connection status and configuration information.
    Returns skipped status if authentication is not enabled.
    """
    keycloak_config = get_keycloak_config()
    settings = get_settings()
    translate = request.state.translate

    # If authentication not enabled, return skip status
    if not keycloak_config.enabled:
        return {
            "status": "skipped",
            "service": "keycloak",
            "message": translate("health.keycloak.auth_disabled"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # Check Keycloak connection
    try:
        # Use Keycloak health check endpoint or realm info endpoint
        health_url = f"{keycloak_config.server_url}/protocol/openid-connect/certs"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            response.raise_for_status()

        return {
            "status": "healthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": translate("health.keycloak.reachable"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except httpx.TimeoutException:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": translate("health.keycloak.timeout"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except httpx.HTTPError:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": translate("health.keycloak.connection_failed"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "message": translate("health.keycloak.unexpected_error"),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
