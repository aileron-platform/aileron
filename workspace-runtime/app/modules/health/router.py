"""Health Check Router"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.utils.datetime_utils import utcnow

from .service import HealthCheckService, get_terminal_service_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get("", summary="Service health check")
async def health_check(db: Session = Depends(get_db)) -> dict[str, object]:
    """
    Provide health status of runtime service

    Check and update the following fields in the database:
    - runtime_status: ensure it is 'running'
    - runtime_container_id: update to current container ID
    - runtime_last_seen: update to current time
    """
    logger.debug("Health check called")
    try:
        service = HealthCheckService(db)
        result = service.check_and_update_workspace_status()
        logger.debug("Health check result: %s", result.get('status'))
        return result
    except Exception as e:
        # If database connection fails, still return basic health status
        settings = get_settings()
        terminal_status = get_terminal_service_status()
        return {
            "status": "degraded",
            "service": "workspace-runtime",
            "workspace_id": settings.WORKSPACE_ID,
            "error": f"Database connection failed: {str(e)}",
            "timestamp": utcnow().isoformat() + "Z",
            "terminal_service": terminal_status,
        }
