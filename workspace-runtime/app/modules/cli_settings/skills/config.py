"""CLI Skills 設定

定義各 CLI 工具的 skills 目錄結構。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict


class SkillTool(str, Enum):
    """支援 skills 的 CLI 工具"""

    CLAUDE = "claude"
    GEMINI = "gemini"
    CODEX = "codex"
    OPENCODE = "opencode"


class SkillScope(str, Enum):
    """Skill 檔案範圍"""

    PROJECT = "project"
    USER = "user"
    PLUGIN = "plugin"  # Claude 專用


@dataclass(frozen=True)
class SkillToolConfig:
    """每個 CLI 工具的 skills 設定"""

    tool: SkillTool
    project_dot_dir: str  # 專案內的 dot 目錄 (.claude / .gemini / .agents / .opencode)
    skill_dir_name: str  # skills 子目錄名稱
    user_root: Path  # 使用者級別 skills 根目錄
    supports_plugin: bool  # 是否支援 plugin scope
    api_prefix: str  # API 路徑前綴 (claude-code / gemini / codex / opencode)


def _tool_configs() -> Dict[SkillTool, SkillToolConfig]:
    home = Path.home()
    return {
        SkillTool.CLAUDE: SkillToolConfig(
            tool=SkillTool.CLAUDE,
            project_dot_dir=".claude",
            skill_dir_name="skills",
            user_root=home / ".claude" / "skills",
            supports_plugin=True,
            api_prefix="claude-code",
        ),
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
