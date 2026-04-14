"""CLI Skills 模組依賴注入"""

from __future__ import annotations

from typing import Callable

from .config import SkillTool, get_skill_config
from .service import CliSkillService


def make_skill_service_dependency(
    tool: SkillTool,
) -> Callable[..., CliSkillService]:
    def _get_service(workspace_id: str) -> CliSkillService:
        config = get_skill_config(tool)
        return CliSkillService(config, workspace_id)

    return _get_service
