"""
Tool Registry.

Manages all available Agentic Tools.
"""

from typing import Dict, Optional

from .base.tool_interface import ITool
from .base.types import ToolCapabilities, ToolType
from .claude.claude_tool import ClaudeTool


class ToolRegistry:
    """Tool Registry - Manages all available Tools."""

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        Initialize Tool Registry.

        Args:
            api_key: API key
        """
        self.api_key = api_key

        # Register all tools
        self._tools: Dict[str, ITool] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all tools."""
        # Claude Code Tool (stateless)
        claude_tool = ClaudeTool(api_key=self.api_key)
        self._tools["claude-code"] = claude_tool

        # TODO: Register other tools
        # - Gemini Tool
        # - Codex Tool
        # - OpenCode Tool

    def get_tool(self, tool_name: str) -> Optional[ITool]:
        """
        Get Tool.

        Args:
            tool_name: Tool name

        Returns:
            Tool instance, returns None if not exists
        """
        return self._tools.get(tool_name)

    def get_all_tools(self) -> Dict[str, ITool]:
        """
        Get all Tools.

        Returns:
            Dictionary of all Tools
        """
        return self._tools.copy()

    def get_capabilities(self, tool_name: str) -> Optional[ToolCapabilities]:
        """
        Get Tool capabilities.

        Args:
            tool_name: Tool name

        Returns:
            Tool capabilities, returns None if not exists
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None
        return tool.get_capabilities()

    def get_all_capabilities(self) -> Dict[str, ToolCapabilities]:
        """
        Get capabilities of all Tools.

        Returns:
            Dictionary of all Tool capabilities
        """
        capabilities = {}
        for name, tool in self._tools.items():
            capabilities[name] = tool.get_capabilities()
        return capabilities

    def supports_feature(self, tool_name: str, feature: str) -> bool:
        """
        Check if Tool supports specific feature.

        Args:
            tool_name: Tool name
            feature: Feature name

        Returns:
            Whether supported
        """
        caps = self.get_capabilities(tool_name)
        if not caps:
            return False

        # Check feature
        feature_map = {
            "streaming": caps.streaming,
            "thinking": caps.thinking,
            "multimodal": caps.multimodal,
            "prompt_caching": caps.prompt_caching,
            "local_execution": caps.local_execution,
        }

        return feature_map.get(feature, False)


# Global registry instance (singleton pattern)
_registry: Optional[ToolRegistry] = None


def get_tool_registry(
    api_key: Optional[str] = None,
) -> ToolRegistry:
    """
    Get global Tool Registry.

    Args:
        api_key: API key (optional)

    Returns:
        Tool Registry instance
    """
    global _registry

    if _registry is None:
        _registry = ToolRegistry(api_key=api_key)

    return _registry

