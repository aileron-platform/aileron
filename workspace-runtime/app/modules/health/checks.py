"""Health Check Service"""

from __future__ import annotations

import logging
import socket
from typing import Literal, Optional, TypedDict

from app.config.settings import get_settings
from app.core.timestamps import utcnow

logger = logging.getLogger(__name__)


def get_terminal_service_status() -> dict[str, object]:
    """Report terminal-service readiness, avoiding confusion with main API health status."""
    port = get_settings().TERMINAL_PORT

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return {"status": "ready", "port": port}
    except OSError:
        return {"status": "starting", "port": port}


class HealthCheckResult(TypedDict, total=False):
    """Health check result type"""

    status: Literal["healthy", "unhealthy", "degraded"]
    service: str
    workspace_id: str
    container_id: Optional[str]
    runtime_status: Optional[str]
    last_seen: Optional[str]
    timestamp: str
    updated: bool
    error: str
    terminal_service: dict[str, object]
    automation_runner: dict[str, object]


class HealthCheckService:
    """Report process-local Runtime health without Manager-owned data access."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def get_container_id(self) -> Optional[str]:
        """
        Get current container ID

        In Docker container, hostname is usually the first 12 characters of container ID
        """
        try:
            return socket.gethostname()
        except Exception as e:
            logger.warning(f"Cannot get container ID: {e}")
            return None

    @staticmethod
    def get_terminal_service_status() -> dict[str, object]:
        return get_terminal_service_status()

    def check_runtime_status(self) -> HealthCheckResult:
        """Return health for the current Runtime generation."""
        workspace_id = self.settings.AILERON_WORKSPACE_ID
        container_id = self.get_container_id()
        current_time = utcnow()
        return {
            "status": "healthy",
            "service": "workspace-runtime",
            "workspace_id": workspace_id,
            "container_id": container_id,
            "runtime_status": "running",
            "last_seen": current_time.isoformat() + "Z",
            "timestamp": current_time.isoformat() + "Z",
            "updated": False,
            "terminal_service": self.get_terminal_service_status(),
        }


__all__ = ["HealthCheckService", "get_terminal_service_status"]
