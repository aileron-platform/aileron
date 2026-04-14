"""CLI MCP 模組依賴注入"""

from __future__ import annotations

from typing import Callable

from .service import CliMcpService, McpTool, get_mcp_tool_config


def make_mcp_service_dependency(
    tool: McpTool,
) -> Callable[[], CliMcpService]:
    def _get_service() -> CliMcpService:
        config = get_mcp_tool_config(tool)
        return CliMcpService(config)

    return _get_service
