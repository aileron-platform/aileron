"""工作區資料服務 - 用於檔案服務獲取工作區資料"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class WorkspaceInfo(BaseModel):
    """工作區資訊"""

    id: str
    name: str
    workspace_path: str = "/workspace"
    runtime_status: str = "stopped"
    env_vars: list["WorkspaceEnvVar"] = Field(default_factory=list)
    acp_cli_args: list[str] = Field(default_factory=list)


class WorkspaceEnvVar(BaseModel):
    """工作區環境變數"""

    key: str
    value: str


class WorkspaceDataService:
    """工作區資料存取服務"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """從 Workspace Manager 獲取工作區資訊"""
        try:
            url = f"{self.settings.MANAGER_URL}/api/v1/workspaces/{workspace_id}"
            headers = self.settings.manager_headers

            response = await self._client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()
            env_vars = data.get("envVars") or []
            return WorkspaceInfo(
                id=data["id"],
                name=data["name"],
                workspace_path=data.get("workspacePath", "/workspace"),
                runtime_status=data.get("runtimeStatus", {}).get("status", "stopped"),
                env_vars=[WorkspaceEnvVar(**item) for item in env_vars if isinstance(item, dict)],
                acp_cli_args=data.get("acpCliArgs") or [],
            )

        except httpx.HTTPError as e:
            logger.error(f"無法從 Workspace Manager 獲取工作區 {workspace_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"獲取工作區資訊時發生未預期的錯誤: {e}")
            return None

    def get_current_workspace_id(self) -> str:
        """獲取當前工作區 ID"""
        return self.settings.WORKSPACE_ID

    async def close(self) -> None:
        """關閉 HTTP 客戶端"""
        await self._client.aclose()


WorkspaceInfo.model_rebuild()

__all__ = ["WorkspaceDataService", "WorkspaceInfo", "WorkspaceEnvVar"]
