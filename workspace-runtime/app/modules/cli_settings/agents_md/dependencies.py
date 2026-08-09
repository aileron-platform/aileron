"""Agents md dependency injection"""

from __future__ import annotations

from typing import Callable

from .documents import AgentsMdService, AgentsMdTool, get_agents_md_config


def make_agents_md_service_dependency(
    tool: AgentsMdTool,
) -> Callable[[], AgentsMdService]:
    def _get_service() -> AgentsMdService:
        config = get_agents_md_config(tool)
        return AgentsMdService(config)

    return _get_service
