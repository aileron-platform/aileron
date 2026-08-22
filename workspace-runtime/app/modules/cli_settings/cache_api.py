"""Manual cache refresh contract for Agent Settings."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Path
from pydantic import BaseModel, Field


class AgentSettingsCacheRefreshRequest(BaseModel):
    """One scoped cache clear requested by the settings UI."""

    provider: Literal["claude-code", "codex"]
    capability: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1)


class AgentSettingsCacheRefreshResponse(BaseModel):
    """Acknowledge that completed cache entries were removed."""

    refreshed: Literal[True] = True


def clear_agent_settings_cache(
    *,
    provider: Literal["claude-code", "codex"],
    workspace_id: str,
    capability: str | None = None,
    scope: str | None = None,
) -> None:
    """Clear only the simple process caches that can affect a provider view."""

    from app.modules.cli_settings.skills.catalog import clear_skill_tree_cache

    if provider == "claude-code":
        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.plugins.plugin_inventory import (
            clear_claude_plugin_inventory_cache,
        )
        from app.modules.claude_code.settings.dependencies import get_settings_service

        clear_claude_plugin_inventory_cache()
        get_plugin_loader(get_settings_service()).clear_cache(workspace_id)
        if capability in {None, "subagents"}:
            from app.modules.cli_settings.subagents.config import SubagentTool
            from app.modules.cli_settings.subagents.dependencies import (
                get_subagent_service,
            )

            get_subagent_service(SubagentTool.CLAUDE).clear_cache(
                workspace_id,
                scope,
            )
        if capability in {None, "skills"}:
            clear_skill_tree_cache(
                tool="claude-code",
                workspace_id=workspace_id,
                scope=scope,
            )
        return

    from app.modules.cli_settings.codex.app_server_hooks import (
        clear_codex_hooks_cache,
    )
    from app.modules.cli_settings.codex.plugin_resources import (
        clear_codex_plugin_inventory_cache,
    )
    from app.modules.cli_settings.codex.settings import (
        CodexSettingsIntent,
        get_codex_agent_settings,
    )

    clear_codex_plugin_inventory_cache()
    get_codex_agent_settings().execute(
        CodexSettingsIntent.REFRESH_CACHE,
        workspace_id=workspace_id,
        capability=capability,
        scope=scope,
    )
    if capability in {None, "hooks"}:
        clear_codex_hooks_cache()
    if capability in {None, "skills"}:
        clear_skill_tree_cache(
            tool="codex",
            workspace_id=workspace_id,
            scope=scope,
        )


router = APIRouter(prefix="/agent-settings/cache", tags=["Agent Settings Cache"])


@router.post(
    "/refresh",
    response_model=AgentSettingsCacheRefreshResponse,
)
async def refresh_agent_settings_cache(
    payload: AgentSettingsCacheRefreshRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
) -> AgentSettingsCacheRefreshResponse:
    """Clear scoped backend cache entries before the UI refetches once."""

    clear_agent_settings_cache(
        provider=payload.provider,
        workspace_id=workspace_id,
        capability=payload.capability,
        scope=payload.scope,
    )
    return AgentSettingsCacheRefreshResponse()


__all__ = [
    "AgentSettingsCacheRefreshRequest",
    "AgentSettingsCacheRefreshResponse",
    "clear_agent_settings_cache",
    "router",
]
