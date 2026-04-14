"""CLI Hooks 工具設定

定義各 CLI 工具的 hooks 設定檔路徑與讀寫策略。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List

from ..mcp.config_strategies import ConfigFileStrategy, JsonConfigStrategy


class HookTool(str, Enum):
    """支援 Hooks 的 CLI 工具"""

    GEMINI = "gemini"


class CliHookScope(str, Enum):
    """CLI Hooks 支援的設定範圍"""

    PROJECT = "project"
    USER = "user"


@dataclass(frozen=True)
class CliHookToolConfig:
    """每個 CLI 工具的 Hooks 設定檔資訊"""

    tool: HookTool
    project_file: str          # 相對於 workspace root 的路徑
    user_file_path: Path       # 絕對路徑
    hooks_key: str             # JSON 中存放 hooks 的 key
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
