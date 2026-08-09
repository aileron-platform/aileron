"""CLI subagents configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.config.settings import get_workspace_path
from app.modules.claude_code.documents import DocumentScope
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import get_user_scope_path_resolver


class SubagentTool(str, Enum):
    """CLI tools that support markdown subagents.

    Codex subagents are not listed here: they are stored as .toml files with
    rename-on-save semantics, incompatible with the markdown-per-record model
    this module provides. Codex keeps its own storage in cli_settings/codex/.
    """

    CLAUDE = "claude-code"
    OPENCODE = "opencode"


@dataclass(frozen=True)
class SubagentToolConfig:
    """Subagents configuration for each CLI tool."""

    tool: SubagentTool
    project_dot_dir: str
    agents_dir: str
    user_root: Path
    api_prefix: str
    supports_plugin: bool

    def scope_root(self, workspace_id: str, scope: DocumentScope) -> Path:
        """Resolve the root directory that contains the agents folder."""

        if scope == DocumentScope.USER:
            return self.user_root.parent
        return Path(get_workspace_path()) / self.project_dot_dir


def get_subagent_config(tool: SubagentTool) -> SubagentToolConfig:
    user_paths = get_user_scope_path_resolver()
    configs = {
        SubagentTool.CLAUDE: SubagentToolConfig(
            tool=SubagentTool.CLAUDE,
            project_dot_dir=".claude",
            agents_dir="agents",
            user_root=user_paths.resolve(
                UserScopeAgent.CLAUDE_CODE,
                UserScopeResource.SUBAGENTS,
            ).runtime_path,
            api_prefix="claude-code",
            supports_plugin=True,
        ),
        SubagentTool.OPENCODE: SubagentToolConfig(
            tool=SubagentTool.OPENCODE,
            project_dot_dir=".opencode",
            agents_dir="agents",
            user_root=user_paths.resolve(
                UserScopeAgent.OPENCODE,
                UserScopeResource.SUBAGENTS,
            ).runtime_path,
            api_prefix="opencode",
            supports_plugin=False,
        ),
    }
    if tool not in configs:
        raise ValueError(f"Unsupported subagent tool: {tool}")
    return configs[tool]
