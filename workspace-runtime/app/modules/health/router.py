"""Health Check Router"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from .checks import HealthCheckService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get("", summary="Service health check")
async def health_check(request: Request) -> JSONResponse:
    """Provide process-local health without platform database access."""
    logger.debug("Health check called")
    try:
        result = HealthCheckService().check_runtime_status()
        runner = getattr(request.app.state, "automation_runner", None)
        if runner is not None:
            result["automation_runner"] = {
                "healthy": runner.is_healthy,
                "fatal_reason": runner.fatal_reason,
            }
            if not runner.is_healthy:
                result["status"] = "degraded"
        logger.debug("Health check result: %s", result.get("status"))
        response_status = (
            status.HTTP_200_OK
            if result.get("status") == "healthy"
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        return JSONResponse(status_code=response_status, content=result)
    except Exception:
        logger.exception("Runtime health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "service": "workspace-runtime"},
        )
