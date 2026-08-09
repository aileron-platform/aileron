"""CLI Skills module dependency injection"""

from __future__ import annotations

from typing import Callable

from .config import SkillTool, get_skill_config
from .catalog import CliSkillService


def make_skill_service_dependency(
    tool: SkillTool,
) -> Callable[..., CliSkillService]:
    def _get_service(workspace_id: str) -> CliSkillService:
        config = get_skill_config(tool)
        return CliSkillService(config, workspace_id)

    return _get_service
