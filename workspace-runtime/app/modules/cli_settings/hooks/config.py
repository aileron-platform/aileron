"""CLI Hooks tool configuration

Defines hooks configuration file paths and read/write strategies for each CLI tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

from ..mcp.config_strategies import ConfigFileStrategy, JsonConfigStrategy


class HookTool(str, Enum):
    """CLI tools that support Hooks"""

    GEMINI = "gemini"


class CliHookScope(str, Enum):
    """Configuration scopes supported by CLI Hooks"""

    PROJECT = "project"
    USER = "user"
    EXTENSION = "extension"


@dataclass(frozen=True)
class CliHookToolConfig:
    """Hooks configuration file information for each CLI tool"""

    tool: HookTool
    project_file: str          # Path relative to workspace root
    user_file_path: Path       # Absolute path
    hooks_key: str             # Key where hooks are stored in JSON
    strategy: ConfigFileStrategy
    supported_scopes: List[CliHookScope]


def _tool_configs() -> Dict[HookTool, CliHookToolConfig]:
    home = Path.home()
    json_strategy = JsonConfigStrategy()

    return {
        HookTool.GEMINI: CliHookToolConfig(
            tool=HookTool.GEMINI,
            project_file=".gemini/settings.json",
            user_file_path=home / ".gemini" / "settings.json",
            hooks_key="hooks",
            strategy=json_strategy,
            supported_scopes=[CliHookScope.PROJECT, CliHookScope.USER],
        ),
    }


def get_hook_tool_config(tool: HookTool) -> CliHookToolConfig:
    configs = _tool_configs()
    if tool not in configs:
        raise ValueError(f"Unsupported hook tool: {tool}")
    return configs[tool]
