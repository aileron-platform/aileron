"""Health Check Service"""

from __future__ import annotations

import logging
import os
import socket
from typing import Literal, Optional, TypedDict

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.models import Workspace
from app.utils.datetime_utils import utcnow

logger = logging.getLogger(__name__)


def get_terminal_service_status() -> dict[str, object]:
    """Report terminal-service readiness, avoiding confusion with main API health status."""
    port = int(os.getenv("TERMINAL_PORT", "3004"))

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


class HealthCheckService:
    """Health check service, responsible for checking and updating database status"""

    def __init__(self, db: Session) -> None:
        self.db = db
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

    def check_and_update_workspace_status(self) -> HealthCheckResult:
        """
        Check and update workspace runtime status

        Returns:
            Health check result
        """
        workspace_id = self.settings.WORKSPACE_ID
        container_id = self.get_container_id()
        current_time = utcnow()

        try:
            # Query workspace
            workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

            if not workspace:
                logger.error(f"Workspace not found: {workspace_id}")
                return {
                    "status": "unhealthy",
                    "service": "workspace-runtime",
                    "workspace_id": workspace_id,
                    "error": "Workspace not found in database",
                    "timestamp": current_time.isoformat() + "Z",
                    "terminal_service": self.get_terminal_service_status(),
                }

            # Check and update status
            needs_update = False
            updates = {}

            # Check runtime_status
            if not workspace.runtime_status or workspace.runtime_status not in ["running", "starting"]:
                updates["runtime_status"] = "running"
                needs_update = True
                logger.info(f"Update runtime_status: {workspace.runtime_status} -> running")

            # Check runtime_container_id
            if container_id and workspace.runtime_container_id != container_id:
                updates["runtime_container_id"] = container_id
                needs_update = True
                logger.info(f"Update runtime_container_id: {workspace.runtime_container_id} -> {container_id}")

            # Update last_seen
            updates["runtime_last_seen"] = current_time
            needs_update = True

            # Execute update
            if needs_update:
                for key, value in updates.items():
                    setattr(workspace, key, value)
                
                self.db.commit()
                logger.info(f"Updated workspace {workspace_id} status: {updates}")

            return {
                "status": "healthy",
                "service": "workspace-runtime",
                "workspace_id": workspace_id,
                "container_id": container_id,
                "runtime_status": workspace.runtime_status,
                "last_seen": workspace.runtime_last_seen.isoformat() + "Z" if workspace.runtime_last_seen else None,
                "timestamp": current_time.isoformat() + "Z",
                "updated": needs_update,
                "terminal_service": self.get_terminal_service_status(),
            }

        except Exception as e:
            logger.error(f"Failed to update database during health check: {e}", exc_info=True)
            self.db.rollback()
            return {
                "status": "degraded",
                "service": "workspace-runtime",
                "workspace_id": workspace_id,
                "container_id": container_id,
                "error": str(e),
                "timestamp": current_time.isoformat() + "Z",
                "terminal_service": self.get_terminal_service_status(),
            }


__all__ = ["HealthCheckService", "get_terminal_service_status"]
