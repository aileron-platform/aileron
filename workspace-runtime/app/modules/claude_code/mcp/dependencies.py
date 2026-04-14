"""MCP 模組依賴"""

from __future__ import annotations

from functools import lru_cache

from .service import McpService


@lru_cache()
def get_mcp_service() -> McpService:
    """提供單例 MCP 服務"""

    return McpService()
