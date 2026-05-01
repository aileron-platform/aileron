"""健康檢查服務"""

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
    """健康檢查服務，負責檢查並更新資料庫狀態"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def get_container_id(self) -> Optional[str]:
        """
        獲取當前容器的 Container ID
        
        在 Docker 容器內，hostname 通常就是 container ID 的前 12 位
        """
        try:
            return socket.gethostname()
        except Exception as e:
            logger.warning(f"無法獲取容器 ID: {e}")
            return None

    @staticmethod
    def get_terminal_service_status() -> dict[str, object]:
        return get_terminal_service_status()

    def check_and_update_workspace_status(self) -> HealthCheckResult:
        """
        檢查並更新 workspace 的 runtime 狀態

        Returns:
            健康檢查結果
        """
        workspace_id = self.settings.WORKSPACE_ID
        container_id = self.get_container_id()
        current_time = utcnow()

        try:
            # 查詢 workspace
            workspace = self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

            if not workspace:
                logger.error(f"找不到 workspace: {workspace_id}")
                return {
                    "status": "unhealthy",
                    "service": "workspace-runtime",
                    "workspace_id": workspace_id,
                    "error": "Workspace not found in database",
                    "timestamp": current_time.isoformat() + "Z",
                    "terminal_service": self.get_terminal_service_status(),
                }

            # 檢查並更新狀態
            needs_update = False
            updates = {}

            # 檢查 runtime_status
            if not workspace.runtime_status or workspace.runtime_status not in ["running", "starting"]:
                updates["runtime_status"] = "running"
                needs_update = True
                logger.info(f"更新 runtime_status: {workspace.runtime_status} -> running")

            # 檢查 runtime_container_id
            if container_id and workspace.runtime_container_id != container_id:
                updates["runtime_container_id"] = container_id
                needs_update = True
                logger.info(f"更新 runtime_container_id: {workspace.runtime_container_id} -> {container_id}")

            # 更新 last_seen
            updates["runtime_last_seen"] = current_time
            needs_update = True

            # 執行更新
            if needs_update:
                for key, value in updates.items():
                    setattr(workspace, key, value)
                
                self.db.commit()
                logger.info(f"已更新 workspace {workspace_id} 的狀態: {updates}")

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
            logger.error(f"健康檢查時更新資料庫失敗: {e}", exc_info=True)
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
