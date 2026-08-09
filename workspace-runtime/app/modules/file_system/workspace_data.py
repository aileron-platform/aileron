"""Workspace data service - for file service to get workspace data"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.config.settings import get_settings


class WorkspaceInfo(BaseModel):
    """Workspace information"""

    id: str
    name: str
    workspace_path: str = "/workspace"
    worktree_subdir: str = ".worktrees"
    runtime_status: str = "stopped"
    env_vars: list["WorkspaceEnvVar"] = Field(default_factory=list)
    acp_cli_args: list[str] = Field(default_factory=list)
    agentic_tools: list[str] = Field(default_factory=lambda: ["claude-code"])


class WorkspaceEnvVar(BaseModel):
    """Workspace environment variable"""

    key: str
    value: str


class WorkspaceDataService:
    """Expose immutable workspace configuration already bound to this Runtime."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Return only the workspace identity assigned to this process."""
        if workspace_id != self.settings.AILERON_WORKSPACE_ID:
            return None
        return WorkspaceInfo(
            id=self.settings.AILERON_WORKSPACE_ID,
            name=self.settings.AILERON_WORKSPACE_ID,
            workspace_path=self.settings.AILERON_WORKSPACE_PATH,
            worktree_subdir=self.settings.AILERON_WORKTREE_SUBDIR,
            runtime_status="running",
        )

    def get_current_workspace_id(self) -> str:
        """Get current workspace ID"""
        return self.settings.AILERON_WORKSPACE_ID

    async def close(self) -> None:
        """Retain the async lifecycle contract without external resources."""


WorkspaceInfo.model_rebuild()

__all__ = ["WorkspaceDataService", "WorkspaceInfo", "WorkspaceEnvVar"]
