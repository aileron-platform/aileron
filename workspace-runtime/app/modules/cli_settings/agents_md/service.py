"""CLI Agents MD 服務"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from fastapi import HTTPException, status

from app.config.settings import get_workspace_path

from .models import (
    AgentsMdDocument,
    AgentsMdScope,
    AgentsMdUpdateRequest,
    AgentsMdUpdateResponse,
)


class AgentsMdTool(str, Enum):
    """支援的 CLI 工具"""

    GEMINI = "gemini"
    OPENCODE = "opencode"
    CODEX = "codex"


@dataclass(frozen=True)
class AgentsMdToolConfig:
    tool: AgentsMdTool
    file_name: str
    user_root: Path
    endpoint_name: str


def _tool_configs() -> dict[AgentsMdTool, AgentsMdToolConfig]:
    home = Path.home()
    return {
        AgentsMdTool.GEMINI: AgentsMdToolConfig(
            tool=AgentsMdTool.GEMINI,
            file_name="GEMINI.md",
            user_root=home / ".gemini",
            endpoint_name="gemini-md",
        ),
        AgentsMdTool.OPENCODE: AgentsMdToolConfig(
            tool=AgentsMdTool.OPENCODE,
            file_name="AGENTS.md",
            user_root=home / ".config" / "opencode",
            endpoint_name="agents-md",
        ),
        AgentsMdTool.CODEX: AgentsMdToolConfig(
            tool=AgentsMdTool.CODEX,
            file_name="AGENTS.md",
            user_root=home / ".codex",
            endpoint_name="agents-md",
        ),
    }


def get_agents_md_config(tool: AgentsMdTool) -> AgentsMdToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported tool: {tool}")
    return configs[tool]


class AgentsMdService:
    """管理 CLI agents md 檔案的服務"""

    def __init__(self, config: AgentsMdToolConfig) -> None:
        self._config = config

    def get_document(self, workspace_id: str, scope: AgentsMdScope) -> AgentsMdDocument:
        file_path = self._resolve_path(workspace_id, scope)
        if not file_path.exists():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "404_NOT_FOUND",
                    "message": f"404: {self._config.file_name} not found",
                },
            )
        content = file_path.read_text(encoding="utf-8")
        return AgentsMdDocument(
            workspaceId=workspace_id,
            scope=scope,
            content=content,
        )

    def update_document(
        self,
        workspace_id: str,
        request: AgentsMdUpdateRequest,
    ) -> AgentsMdUpdateResponse:
        file_path = self._resolve_path(workspace_id, request.scope)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(request.content, encoding="utf-8")
        return AgentsMdUpdateResponse(
            workspaceId=workspace_id,
            scope=request.scope,
        )

    def _resolve_path(self, workspace_id: str, scope: AgentsMdScope) -> Path:
        if scope == AgentsMdScope.PROJECT:
            project_root = Path(get_workspace_path())
            return project_root / self._config.file_name
        if scope == AgentsMdScope.USER:
            return self._config.user_root / self._config.file_name
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported scope")
