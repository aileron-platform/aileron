"""CLI Slash Commands configuration

Defines slash commands directory structure and format for each CLI tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class SlashCommandTool(str, Enum):
    """CLI tools that support slash commands"""

    GEMINI = "gemini"
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
    project_dot_dir: str  # Dot directory within project (.gemini / .codex / .opencode)
    user_root: Path  # User root directory
    supports_namespace: bool  # Whether subdirectory namespaces are supported


def _tool_configs() -> Dict[SlashCommandTool, SlashCommandToolConfig]:
    home = Path.home()
    return {
        SlashCommandTool.GEMINI: SlashCommandToolConfig(
            tool=SlashCommandTool.GEMINI,
            dir_name="commands",
            file_extension=".toml",
            format=DocumentFormat.TOML,
            project_dot_dir=".gemini",
            user_root=home / ".gemini" / "commands",
            supports_namespace=True,
        ),
        SlashCommandTool.CODEX: SlashCommandToolConfig(
            tool=SlashCommandTool.CODEX,
            dir_name="prompts",
            file_extension=".md",
            format=DocumentFormat.MARKDOWN,
            project_dot_dir=".codex",
            user_root=home / ".codex" / "prompts",
            supports_namespace=False,
        ),
        SlashCommandTool.OPENCODE: SlashCommandToolConfig(
            tool=SlashCommandTool.OPENCODE,
            dir_name="commands",
            file_extension=".md",
            format=DocumentFormat.MARKDOWN,
            project_dot_dir=".opencode",
            user_root=home / ".config" / "opencode" / "commands",
            supports_namespace=True,
        ),
    }


def get_slash_command_config(tool: SlashCommandTool) -> SlashCommandToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported slash command tool: {tool}")
    return configs[tool]
