"""
Claude Tool 管理器 - 全域單例管理

確保所有 ExecutionService 實例共享同一個 ClaudeTool 實例，
這樣 stop_task 可以正確存取 abort_events。
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

from .claude_tool import ClaudeTool


class ClaudeToolManager:
    """
    Claude Tool 全域管理器.

    使用單例模式確保所有 ExecutionService 實例共享同一個 ClaudeTool。
    ClaudeTool 為無狀態設計（不持有 DB session），因此可安全共享。
    """

    _instance: Optional["ClaudeToolManager"] = None
    _tool: Optional[ClaudeTool] = None

    def __new__(cls) -> "ClaudeToolManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_tool(self) -> ClaudeTool:
        """
        取得或創建 ClaudeTool 實例.

        如果已存在實例，返回現有的。
        如果不存在，創建新的並緩存。
        """
        if self._tool is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            self._tool = ClaudeTool(api_key=api_key)
        return self._tool

    def get_existing_tool(self) -> Optional[ClaudeTool]:
        """
        取得現有的 ClaudeTool 實例（如果存在）.

        用於 stop_task 等操作，不需要創建新實例。
        """
        return self._tool

    def reset(self) -> None:
        """
        重置管理器（主要用於測試）.
        """
        self._tool = None


# 全域實例
_claude_tool_manager: Optional[ClaudeToolManager] = None


def get_claude_tool_manager() -> ClaudeToolManager:
    """取得全域 ClaudeToolManager 實例."""
    global _claude_tool_manager
    if _claude_tool_manager is None:
        _claude_tool_manager = ClaudeToolManager()
    return _claude_tool_manager
