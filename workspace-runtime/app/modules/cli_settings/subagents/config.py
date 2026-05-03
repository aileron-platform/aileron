"""CLI subagents configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.config.settings import get_workspace_path
from app.modules.claude_code.common import DocumentScope


class SubagentTool(str, Enum):
    """CLI tools that support markdown subagents."""

    CLAUDE = "claude-code"
    GEMINI = "gemini"


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
    home = Path.home()
    configs = {
        SubagentTool.CLAUDE: SubagentToolConfig(
            tool=SubagentTool.CLAUDE,
            project_dot_dir=".claude",
            agents_dir="agents",
            user_root=home / ".claude" / "agents",
            api_prefix="claude-code",
            supports_plugin=True,
        ),
        SubagentTool.GEMINI: SubagentToolConfig(
            tool=SubagentTool.GEMINI,
            project_dot_dir=".gemini",
            agents_dir="agents",
            user_root=home / ".gemini" / "agents",
            api_prefix="gemini",
            supports_plugin=False,
        ),
    }
    if tool not in configs:
        raise ValueError(f"Unsupported subagent tool: {tool}")
    return configs[tool]
