"""MCP Module Dependencies"""

from __future__ import annotations

from functools import lru_cache

from .configuration import McpService


@lru_cache()
def get_mcp_service() -> McpService:
    """Provide singleton MCP service"""

    return McpService()
