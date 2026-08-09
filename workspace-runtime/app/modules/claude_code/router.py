"""Claude Code route composition."""

from fastapi import APIRouter

from .hooks.router import router as hooks_router
from .mcp.router import router as mcp_router
from .memory.router import router as memory_router
from .output_styles.router import router as output_styles_router
from .plugins.router import router as plugins_router
from .settings.router import router as settings_router
from .slash_commands.router import router as slash_commands_router

router = APIRouter(prefix="/workspaces/{workspace_id}/claude-code")
router.include_router(mcp_router)
router.include_router(hooks_router)
router.include_router(memory_router)
router.include_router(slash_commands_router)
router.include_router(output_styles_router)
router.include_router(plugins_router)
router.include_router(settings_router)
