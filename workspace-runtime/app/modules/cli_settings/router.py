"""CLI settings route composition."""

from fastapi import APIRouter

from .agents_md.router import create_agents_md_router
from .agents_md.documents import AgentsMdTool
from .cache_api import router as cache_router
from .codex.router import router as codex_router
from .mcp.router import create_mcp_router
from .mcp.configuration import McpTool
from .skills.config import SkillTool
from .skills.router import create_skills_router
from .slash_commands.config import SlashCommandTool
from .slash_commands.router import create_slash_commands_router
from .subagents.config import SubagentTool
from .subagents.router import create_subagents_router

router = APIRouter(prefix="/workspaces/{workspace_id}")
router.include_router(cache_router)
router.include_router(codex_router)
router.include_router(create_agents_md_router(AgentsMdTool.CLAUDE))
router.include_router(create_agents_md_router(AgentsMdTool.CODEX))
router.include_router(create_agents_md_router(AgentsMdTool.OPENCODE))
router.include_router(create_mcp_router(McpTool.OPENCODE))
router.include_router(create_mcp_router(McpTool.CODEX))
router.include_router(create_skills_router(SkillTool.CLAUDE))
router.include_router(create_skills_router(SkillTool.OPENCODE))
router.include_router(create_skills_router(SkillTool.CODEX))
router.include_router(create_slash_commands_router(SlashCommandTool.OPENCODE))
router.include_router(create_slash_commands_router(SlashCommandTool.CODEX))
router.include_router(create_subagents_router(SubagentTool.CLAUDE))
router.include_router(create_subagents_router(SubagentTool.OPENCODE))
