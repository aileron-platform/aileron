"""CLI Slash Commands configuration

Defines slash commands directory structure and format for each CLI tool.
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


class SlashCommandTool(str, Enum):
    """CLI tools that support slash commands"""

    CODEX = "codex"
    OPENCODE = "opencode"


class SlashCommandScope(str, Enum):
    """Slash command file scope"""

    PROJECT = "project"
    USER = "user"


class DocumentFormat(str, Enum):
    """Document format"""

    MARKDOWN = "markdown"
    TOML = "toml"


@dataclass(frozen=True)
class SlashCommandToolConfig:
    """Slash commands configuration for each CLI tool"""

    tool: SlashCommandTool
    dir_name: str  # Directory name (commands / prompts)
    file_extension: str  # .toml / .md
    format: DocumentFormat
    project_dot_dir: str  # Dot directory within project (.codex / .opencode)
    user_root: Path  # User root directory


def _tool_configs() -> Dict[SlashCommandTool, SlashCommandToolConfig]:
    user_paths = get_user_scope_path_resolver()
    return {
        SlashCommandTool.CODEX: SlashCommandToolConfig(
            tool=SlashCommandTool.CODEX,
            dir_name="prompts",
            file_extension=".md",
            format=DocumentFormat.MARKDOWN,
            project_dot_dir=".codex",
            user_root=user_paths.resolve(
                UserScopeAgent.CODEX,
                UserScopeResource.PROMPTS,
            ).runtime_path,
        ),
        SlashCommandTool.OPENCODE: SlashCommandToolConfig(
            tool=SlashCommandTool.OPENCODE,
            dir_name="commands",
            file_extension=".md",
            format=DocumentFormat.MARKDOWN,
            project_dot_dir=".opencode",
            user_root=user_paths.resolve(
                UserScopeAgent.OPENCODE,
                UserScopeResource.COMMANDS,
            ).runtime_path,
        ),
    }


def get_slash_command_config(tool: SlashCommandTool) -> SlashCommandToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported slash command tool: {tool}")
    return configs[tool]
