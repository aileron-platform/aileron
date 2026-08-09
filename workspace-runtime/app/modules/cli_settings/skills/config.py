"""CLI Skills configuration

Defines skills directory structure for each CLI tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict

from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import get_user_scope_path_resolver


class SkillTool(str, Enum):
    """CLI tools that support skills"""

    CLAUDE = "claude-code"
    CODEX = "codex"
    OPENCODE = "opencode"


class SkillScope(str, Enum):
    """Skill file scope"""

    PROJECT = "project"
    USER = "user"
    PLUGIN = "plugin"


@dataclass(frozen=True)
class SkillToolConfig:
    """Skills configuration for each CLI tool"""

    tool: SkillTool
    project_dot_dir: str  # Dot directory within project (.claude / .codex / .opencode)
    skill_dir_name: str  # Skills subdirectory name
    user_root: Path  # User-level skills root directory
    supports_plugin: bool  # Whether plugin scope is supported
    api_prefix: str  # API path prefix (claude-code / codex / opencode)


def _tool_configs() -> Dict[SkillTool, SkillToolConfig]:
    user_paths = get_user_scope_path_resolver()
    return {
        SkillTool.CLAUDE: SkillToolConfig(
            tool=SkillTool.CLAUDE,
            project_dot_dir=".claude",
            skill_dir_name="skills",
            user_root=user_paths.resolve(
                UserScopeAgent.CLAUDE_CODE,
                UserScopeResource.SKILLS,
            ).runtime_path,
            supports_plugin=True,
            api_prefix="claude-code",
        ),
        SkillTool.CODEX: SkillToolConfig(
            tool=SkillTool.CODEX,
            project_dot_dir=".codex",
            skill_dir_name="skills",
            user_root=user_paths.resolve(
                UserScopeAgent.CODEX,
                UserScopeResource.SKILLS,
            ).runtime_path,
            supports_plugin=False,
            api_prefix="codex",
        ),
        SkillTool.OPENCODE: SkillToolConfig(
            tool=SkillTool.OPENCODE,
            project_dot_dir=".opencode",
            skill_dir_name="skills",
            user_root=user_paths.resolve(
                UserScopeAgent.OPENCODE,
                UserScopeResource.SKILLS,
            ).runtime_path,
            supports_plugin=False,
            api_prefix="opencode",
        ),
    }


def get_skill_config(tool: SkillTool) -> SkillToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported skill tool: {tool}")
    return configs[tool]
