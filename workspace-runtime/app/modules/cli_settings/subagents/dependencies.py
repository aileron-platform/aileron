"""CLI subagents dependency helpers."""

from __future__ import annotations

from functools import lru_cache

from .config import SubagentTool, get_subagent_config
from .service import SubagentService


@lru_cache()
def get_subagent_service() -> SubagentService:
    """Provide the Claude Code subagent service."""

    return SubagentService(get_subagent_config(SubagentTool.CLAUDE))


@lru_cache()
def get_gemini_subagent_service() -> SubagentService:
    """Provide the Gemini subagent service."""

    return SubagentService(get_subagent_config(SubagentTool.GEMINI))
