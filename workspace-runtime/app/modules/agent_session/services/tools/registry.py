"""
Tool Registry.

管理所有可用的 Agentic Tools。
"""

from typing import Dict, Optional

from .base.tool_interface import ITool
from .base.types import ToolCapabilities, ToolType
from .claude.claude_tool import ClaudeTool


class ToolRegistry:
    """Tool Registry - 管理所有可用的 Tools."""

    def __init__(
        self,
        api_key: Optional[str] = None,
    ):
        """
        初始化 Tool Registry.

        Args:
            api_key: API key
        """
        self.api_key = api_key

        # 註冊所有 tools
        self._tools: Dict[str, ITool] = {}
        self._register_tools()

    def _register_tools(self) -> None:
        """註冊所有 tools."""
        # Claude Code Tool（無狀態）
        claude_tool = ClaudeTool(api_key=self.api_key)
        self._tools["claude-code"] = claude_tool

        # TODO: 註冊其他 tools
        # - Gemini Tool
        # - Codex Tool
        # - OpenCode Tool
    
    def get_tool(self, tool_name: str) -> Optional[ITool]:
        """
        取得 Tool.
        
        Args:
            tool_name: Tool 名稱
        
        Returns:
            Tool 實例，如果不存在則返回 None
        """
        return self._tools.get(tool_name)
    
    def get_all_tools(self) -> Dict[str, ITool]:
        """
        取得所有 Tools.
        
        Returns:
            所有 Tools 的字典
        """
        return self._tools.copy()
    
    def get_capabilities(self, tool_name: str) -> Optional[ToolCapabilities]:
        """
        取得 Tool 能力.
        
        Args:
            tool_name: Tool 名稱
        
        Returns:
            Tool 能力，如果不存在則返回 None
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return None
        return tool.get_capabilities()
    
    def get_all_capabilities(self) -> Dict[str, ToolCapabilities]:
        """
        取得所有 Tools 的能力.
        
        Returns:
            所有 Tools 的能力字典
        """
        capabilities = {}
        for name, tool in self._tools.items():
            capabilities[name] = tool.get_capabilities()
        return capabilities
    
    def supports_feature(self, tool_name: str, feature: str) -> bool:
        """
        檢查 Tool 是否支援特定功能.
        
        Args:
            tool_name: Tool 名稱
            feature: 功能名稱
        
        Returns:
            是否支援
        """
        caps = self.get_capabilities(tool_name)
        if not caps:
            return False
        
        # 檢查功能
        feature_map = {
            "streaming": caps.streaming,
            "thinking": caps.thinking,
            "multimodal": caps.multimodal,
            "prompt_caching": caps.prompt_caching,
            "local_execution": caps.local_execution,
        }
        
        return feature_map.get(feature, False)


# 全域 registry 實例（單例模式）
_registry: Optional[ToolRegistry] = None


def get_tool_registry(
    api_key: Optional[str] = None,
) -> ToolRegistry:
    """
    取得全域 Tool Registry.

    Args:
        api_key: API key（可選）

    Returns:
        Tool Registry 實例
    """
    global _registry

    if _registry is None:
        _registry = ToolRegistry(api_key=api_key)

    return _registry

