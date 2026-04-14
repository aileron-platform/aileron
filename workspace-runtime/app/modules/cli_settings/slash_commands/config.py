"""CLI Slash Commands 設定

定義各 CLI 工具的 slash commands 目錄結構與格式。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class SlashCommandTool(str, Enum):
    """支援 slash commands 的 CLI 工具"""

    GEMINI = "gemini"
    CODEX = "codex"
    OPENCODE = "opencode"


class SlashCommandScope(str, Enum):
    """Slash command 檔案範圍"""

    PROJECT = "project"
    USER = "user"


class DocumentFormat(str, Enum):
    """文件格式"""

    MARKDOWN = "markdown"
    TOML = "toml"


@dataclass(frozen=True)
class SlashCommandToolConfig:
    """每個 CLI 工具的 slash commands 設定"""

    tool: SlashCommandTool
    dir_name: str  # 目錄名稱 (commands / prompts)
    file_extension: str  # .toml / .md
    format: DocumentFormat
    project_dot_dir: str  # 專案內的 dot 目錄 (.gemini / .codex / .opencode)
    user_root: Path  # 使用者根目錄
    supports_namespace: bool  # 是否支援子目錄命名空間


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
