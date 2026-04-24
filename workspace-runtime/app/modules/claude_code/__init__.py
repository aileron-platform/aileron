"""Claude Code 模組集合"""

from __future__ import annotations

from fastapi import APIRouter

from .claude_md.router import router as claude_md_router
from .file_collections import scripts_router, skills_router
from .hooks.router import router as hooks_router
from .memory.router import router as memory_router
from .mcp.router import router as mcp_router
from .output_styles.router import router as output_styles_router
from .settings.router import router as settings_router
from .slash_commands.router import router as slash_commands_router
from .subagents.router import router as subagents_router

router = APIRouter(
    prefix="/workspaces/{workspace_id}/claude-code",
)

router.include_router(claude_md_router)
router.include_router(mcp_router)
router.include_router(hooks_router)
router.include_router(memory_router)
router.include_router(slash_commands_router)
router.include_router(output_styles_router)
router.include_router(subagents_router)
router.include_router(settings_router)
router.include_router(skills_router)
router.include_router(scripts_router)

__all__ = ["router"]
