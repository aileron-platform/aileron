"""ACP Tool Manager."""

from __future__ import annotations

import logging
from typing import Optional

from app.modules.agent_session.services.tools.base.types import ToolType
from app.modules.file_system.workspace_service import WorkspaceDataService

from .acp_tool import AcpTool
from .connection_manager import AcpConnectionManager

logger = logging.getLogger(__name__)


class AcpToolManager:
    """Global ACP tool manager.

    AcpTool is stateless (does not hold DB session), so it can be safely shared.
    """

    _instance: Optional["AcpToolManager"] = None
    _tools: dict[str, AcpTool]

    def __new__(cls) -> "AcpToolManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._connection_manager = AcpConnectionManager()
        return cls._instance

    def get_tool(
        self,
        tool_type: ToolType,
        workspace_service: Optional[WorkspaceDataService] = None,
    ) -> AcpTool:
        key = tool_type.value
        tool = self._tools.get(key)
        if tool is None:
            tool = AcpTool(
                tool_type=tool_type,
                workspace_service=workspace_service,
                connection_manager=self._connection_manager,
            )
            self._tools[key] = tool
        elif workspace_service:
            tool.workspace_service = workspace_service

        return tool

    def get_existing_tool(self, tool_type: ToolType) -> Optional[AcpTool]:
        return self._tools.get(tool_type.value)

    def reset(self) -> None:
        self._tools = {}
        self._connection_manager = AcpConnectionManager()


def get_acp_tool_manager() -> AcpToolManager:
    return AcpToolManager()


__all__ = ["AcpToolManager", "get_acp_tool_manager"]
