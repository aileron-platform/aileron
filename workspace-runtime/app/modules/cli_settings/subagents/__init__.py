"""CLI subagents module."""

from .config import SubagentTool, SubagentToolConfig, get_subagent_config
from .router import create_subagents_router
from .service import SubagentService

__all__ = [
    "SubagentService",
    "SubagentTool",
    "SubagentToolConfig",
    "create_subagents_router",
    "get_subagent_config",
]
