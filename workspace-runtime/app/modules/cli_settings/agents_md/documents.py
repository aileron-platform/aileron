"""CLI Agents MD service"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, status

from app.config.settings import get_workspace_path
from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.codecs import (
    read_text,
    write_text_atomic,
)
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import get_user_scope_path_resolver

from .models import (
    AgentsMdDocument,
    AgentsMdScope,
    AgentsMdUpdateRequest,
    AgentsMdUpdateResponse,
)


class AgentsMdTool(str, Enum):
    """Supported CLI tools"""

    CLAUDE = "claude"
    OPENCODE = "opencode"
    CODEX = "codex"


@dataclass(frozen=True)
class AgentsMdToolConfig:
    tool: AgentsMdTool
    file_name: str
    user_root: Path
    endpoint_name: str
    project_subdir: str | None = None
    api_prefix: str = ""


_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


def _tool_configs() -> dict[AgentsMdTool, AgentsMdToolConfig]:
    user_paths = get_user_scope_path_resolver()
    return {
        AgentsMdTool.CLAUDE: AgentsMdToolConfig(
            tool=AgentsMdTool.CLAUDE,
            file_name="CLAUDE.md",
            user_root=user_paths.resolve(
                UserScopeAgent.CLAUDE_CODE,
                UserScopeResource.INSTRUCTIONS,
            ).runtime_path.parent,
            endpoint_name="claude-md",
            project_subdir=None,
            api_prefix="claude-code",
        ),
        AgentsMdTool.OPENCODE: AgentsMdToolConfig(
            tool=AgentsMdTool.OPENCODE,
            file_name="AGENTS.md",
            user_root=user_paths.resolve(
                UserScopeAgent.OPENCODE,
                UserScopeResource.INSTRUCTIONS,
            ).runtime_path.parent,
            endpoint_name="agents-md",
            project_subdir=None,
            api_prefix=AgentsMdTool.OPENCODE.value,
        ),
        AgentsMdTool.CODEX: AgentsMdToolConfig(
            tool=AgentsMdTool.CODEX,
            file_name="AGENTS.md",
            user_root=user_paths.resolve(
                UserScopeAgent.CODEX,
                UserScopeResource.INSTRUCTIONS,
            ).runtime_path.parent,
            endpoint_name="agents-md",
            project_subdir=None,
            api_prefix=AgentsMdTool.CODEX.value,
        ),
    }


def get_agents_md_config(tool: AgentsMdTool) -> AgentsMdToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported tool: {tool}")
    return configs[tool]


class AgentsMdService:
    """Service for managing CLI agents md files"""

    def __init__(self, config: AgentsMdToolConfig) -> None:
        self._config = config

    def get_document(self, workspace_id: str, scope: AgentsMdScope) -> AgentsMdDocument:
        file_path = self._resolve_path(workspace_id, scope)
        # A missing file is treated as an empty document so it can be created on save.
        content = read_text(file_path)
        return AgentsMdDocument(
            workspaceId=workspace_id,
            scope=scope,
            content=content,
            revision=compute_revision(content),
        )

    def update_document(
        self,
        workspace_id: str,
        request: AgentsMdUpdateRequest,
    ) -> AgentsMdUpdateResponse:
        file_path = self._resolve_path(workspace_id, request.scope)
        with _write_lock(file_path):
            current_content = read_text(file_path)
            assert_revision(compute_revision(current_content), request.revision)
            write_text_atomic(file_path, request.content)
        return AgentsMdUpdateResponse(
            workspaceId=workspace_id,
            scope=request.scope,
            revision=compute_revision(request.content),
        )

    def _resolve_path(self, workspace_id: str, scope: AgentsMdScope) -> Path:
        if scope == AgentsMdScope.PROJECT:
            project_root = Path(get_workspace_path())
            if self._config.project_subdir:
                project_root = project_root / self._config.project_subdir
            return project_root / self._config.file_name
        if scope == AgentsMdScope.USER:
            return self._config.user_root / self._config.file_name
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported scope")
