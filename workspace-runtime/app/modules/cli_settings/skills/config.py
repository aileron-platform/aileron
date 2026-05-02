"""CLI Skills configuration

Defines skills directory structure for each CLI tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class SkillTool(str, Enum):
    """CLI tools that support skills"""

    GEMINI = "gemini"
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
    project_dot_dir: str  # Dot directory within project (.claude / .gemini / .agents / .opencode)
    skill_dir_name: str  # Skills subdirectory name
    user_root: Path  # User-level skills root directory
    supports_plugin: bool  # Whether plugin scope is supported
    api_prefix: str  # API path prefix (claude-code / gemini / codex / opencode)


def _tool_configs() -> Dict[SkillTool, SkillToolConfig]:
    home = Path.home()
    return {
        SkillTool.GEMINI: SkillToolConfig(
            tool=SkillTool.GEMINI,
            project_dot_dir=".gemini",
            skill_dir_name="skills",
            user_root=home / ".gemini" / "skills",
            supports_plugin=False,
            api_prefix="gemini",
        ),
        SkillTool.CODEX: SkillToolConfig(
            tool=SkillTool.CODEX,
            project_dot_dir=".codex",
            skill_dir_name="skills",
            user_root=home / ".codex" / "skills",
            supports_plugin=False,
            api_prefix="codex",
        ),
        SkillTool.OPENCODE: SkillToolConfig(
            tool=SkillTool.OPENCODE,
            project_dot_dir=".opencode",
            skill_dir_name="skills",
            user_root=home / ".config" / "opencode" / "skills",
            supports_plugin=False,
            api_prefix="opencode",
        ),
    }


def get_skill_config(tool: SkillTool) -> SkillToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported skill tool: {tool}")
    return configs[tool]
