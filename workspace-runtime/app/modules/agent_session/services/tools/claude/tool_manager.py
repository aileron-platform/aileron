"""
Claude Tool Manager - Global singleton management

Ensures all ExecutionService instances share the same ClaudeTool instance,
so stop_task can correctly access abort_events.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from .claude_tool import ClaudeTool


class ClaudeToolManager:
    """
    Claude Tool global manager.

    Uses singleton pattern to ensure all ExecutionService instances share the same ClaudeTool.
    ClaudeTool is stateless (does not hold DB session), so it can be safely shared.
    """

    _instance: Optional["ClaudeToolManager"] = None
    _tool: Optional[ClaudeTool] = None

    def __new__(cls) -> "ClaudeToolManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_tool(self) -> ClaudeTool:
        """
        Get or create ClaudeTool instance.

        Returns existing instance if available.
        Creates and caches new instance if not exists.
        """
        if self._tool is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self._tool = ClaudeTool(api_key=api_key)
        return self._tool

    def get_existing_tool(self) -> Optional[ClaudeTool]:
        """
        Get existing ClaudeTool instance (if available).

        Used for operations like stop_task, does not create new instance.
        """
        return self._tool

    def reset(self) -> None:
        """
        Reset manager (mainly for testing).
        """
        self._tool = None


def get_claude_tool_manager() -> ClaudeToolManager:
    """Get global ClaudeToolManager instance."""
    return ClaudeToolManager()
