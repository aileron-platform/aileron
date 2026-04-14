"""CLI Settings 模組集合"""

from __future__ import annotations

from fastapi import APIRouter

from .hooks import HookTool, create_hooks_router
from .agents_md import AgentsMdTool, create_agents_md_router
from .mcp import McpTool, create_mcp_router
from .skills import SkillTool, create_skills_router
from .slash_commands import SlashCommandTool, create_slash_commands_router

router = APIRouter(prefix="/workspaces/{workspace_id}")

# Agents MD 路由
router.include_router(create_agents_md_router(AgentsMdTool.GEMINI))
router.include_router(create_agents_md_router(AgentsMdTool.OPENCODE))
router.include_router(create_agents_md_router(AgentsMdTool.CODEX))

# MCP 路由
router.include_router(create_mcp_router(McpTool.GEMINI))
router.include_router(create_mcp_router(McpTool.OPENCODE))
router.include_router(create_mcp_router(McpTool.CODEX))

# Hooks 路由
router.include_router(create_hooks_router(HookTool.GEMINI))

# Skills 路由
router.include_router(create_skills_router(SkillTool.CLAUDE))
router.include_router(create_skills_router(SkillTool.GEMINI))
router.include_router(create_skills_router(SkillTool.OPENCODE))
router.include_router(create_skills_router(SkillTool.CODEX))

# Slash Commands 路由
router.include_router(create_slash_commands_router(SlashCommandTool.GEMINI))
router.include_router(create_slash_commands_router(SlashCommandTool.OPENCODE))
router.include_router(create_slash_commands_router(SlashCommandTool.CODEX))

__all__ = ["router"]
