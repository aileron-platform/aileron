"""Internal API dependency injection"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config.settings import get_settings
from app.modules.claude_code.mcp import McpService
from app.modules.claude_code.hooks import HookService
from app.modules.cli_settings.agents_md.service import (
    AgentsMdService,
    AgentsMdTool,
    get_agents_md_config,
)
from .service import InternalService
from .template_install_service import TemplateInstallService

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_internal_token(
    authorization: Annotated[str, Header(description="Internal API authentication Token")]
) -> None:
    """Verify internal API call permission"""
    if not authorization.startswith("Bearer "):
        logger.warning("Internal API call missing Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token for internal API",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Check if token is valid
    expected_token = getattr(settings, 'INTERNAL_API_TOKEN', 'dev-internal-token')
    if token != expected_token:
        logger.warning(f"Invalid internal API token: {token}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API token",
        )

    logger.debug("Internal API token verified successfully")


@lru_cache()
def get_mcp_service() -> McpService:
    """Get singleton MCP service"""
    return McpService()


@lru_cache()
def get_hook_service() -> HookService:
    """Get singleton Hook service"""
    return HookService()


@lru_cache()
def get_agents_md_service() -> AgentsMdService:
    """Get singleton CLAUDE.md service."""
    return AgentsMdService(get_agents_md_config(AgentsMdTool.CLAUDE))


def get_internal_service() -> InternalService:
    """Get Internal Service instance"""
    return InternalService()


def get_template_install_service(
    mcp_service: McpService = Depends(get_mcp_service),
    hook_service: HookService = Depends(get_hook_service),
    agents_md_service: AgentsMdService = Depends(get_agents_md_service),
) -> TemplateInstallService:
    """Get Template Install Service instance (inject dependencies)"""
    return TemplateInstallService(
        mcp_service=mcp_service,
        hook_service=hook_service,
        agents_md_service=agents_md_service,
    )


__all__ = [
    "verify_internal_token",
    "get_internal_service",
    "get_template_install_service",
    "get_mcp_service",
    "get_hook_service",
    "get_agents_md_service",
]
