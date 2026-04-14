"""健康檢查路由"""

import httpx
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.auth.config import get_keycloak_config

router = APIRouter(prefix="/health", tags=["健康檢查"])


@router.get(
    "",
    summary="服務健康檢查",
    responses=build_responses(500),
)
async def health_check() -> dict[str, object]:
    """回傳服務健康狀態與版本資訊"""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "workspace-manager",
        "version": settings.VERSION,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@router.get(
    "/keycloak",
    summary="Keycloak 健康檢查",
    responses=build_responses(500, 503),
)
async def keycloak_health_check() -> dict[str, object]:
    """檢查 Keycloak 服務是否可用

    返回 Keycloak 的連接狀態和配置資訊。
    如果認證未啟用，返回 skipped 狀態。
    """
    keycloak_config = get_keycloak_config()
    settings = get_settings()

    # 如果認證未啟用，返回跳過狀態
    if not keycloak_config.enabled:
        return {
            "status": "skipped",
            "service": "keycloak",
            "message": "Authentication is not enabled",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # 檢查 Keycloak 連接
    try:
        # 使用 Keycloak 的健康檢查端點或 realm 資訊端點
        health_url = f"{keycloak_config.server_url}/protocol/openid-connect/certs"

        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(health_url)
            response.raise_for_status()

        return {
            "status": "healthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": "Keycloak is reachable",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except httpx.TimeoutException:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": "Keycloak connection timeout",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except httpx.HTTPError as e:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "server_url": keycloak_config.server_url,
            "realm": keycloak_config.realm,
            "message": f"Keycloak connection failed: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "keycloak",
            "message": f"Unexpected error: {str(e)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
