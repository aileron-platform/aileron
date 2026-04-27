"""Workspace data service - for file service to get workspace data"""

from __future__ import annotations

import logging
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class WorkspaceInfo(BaseModel):
    """Workspace information"""

    id: str
    name: str
    workspace_path: str = "/workspace"
    runtime_status: str = "stopped"
    env_vars: list["WorkspaceEnvVar"] = Field(default_factory=list)
    acp_cli_args: list[str] = Field(default_factory=list)


class WorkspaceEnvVar(BaseModel):
    """Workspace environment variable"""

    key: str
    value: str


class WorkspaceDataService:
    """Workspace data access service"""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client = httpx.AsyncClient(timeout=10.0)

    async def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Get workspace information from Workspace Manager"""
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
            logger.error(f"Unable to get workspace {workspace_id} from Workspace Manager: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while getting workspace information: {e}")
            return None

    def get_current_workspace_id(self) -> str:
        """Get current workspace ID"""
        return self.settings.WORKSPACE_ID

    async def close(self) -> None:
        """Close HTTP client"""
        await self._client.aclose()


WorkspaceInfo.model_rebuild()

__all__ = ["WorkspaceDataService", "WorkspaceInfo", "WorkspaceEnvVar"]
