"""CLI subagents dependency helpers."""

from __future__ import annotations

from functools import lru_cache

from .config import SubagentTool, get_subagent_config
from .catalog import SubagentService


@lru_cache()
def get_subagent_service(tool: SubagentTool = SubagentTool.CLAUDE) -> SubagentService:
    """Provide the subagent service for a CLI tool."""

    return SubagentService(get_subagent_config(tool))


def get_claude_subagent_service() -> SubagentService:
    """Provide the Claude Code subagent service for FastAPI routes."""

    return get_subagent_service(SubagentTool.CLAUDE)
