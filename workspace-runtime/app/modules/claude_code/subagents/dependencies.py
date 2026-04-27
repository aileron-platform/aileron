"""Subagents Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .service import SubagentService


@lru_cache()
def get_subagent_service() -> SubagentService:
    """Provide SubagentService"""

    return SubagentService()
