"""CLI MCP module dependency injection"""

from __future__ import annotations

from typing import Callable

from .configuration import CliMcpService, McpTool, get_mcp_tool_config


def make_mcp_service_dependency(
    tool: McpTool,
) -> Callable[[], CliMcpService]:
    def _get_service() -> CliMcpService:
        config = get_mcp_tool_config(tool)
        return CliMcpService(config)

    return _get_service
