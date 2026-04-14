"""Internal API 依賴注入"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config.settings import get_settings
from app.modules.claude_code.mcp import McpService
from app.modules.claude_code.hooks import HookService
from app.modules.claude_code.claude_md import ClaudeMdService
from .service import InternalService
from .template_install_service import TemplateInstallService

logger = logging.getLogger(__name__)
settings = get_settings()


async def verify_internal_token(
    authorization: Annotated[str, Header(description="內部 API 認證 Token")]
) -> None:
    """驗證內部 API 呼叫權限"""
    if not authorization.startswith("Bearer "):
        logger.warning("Internal API 呼叫缺少 Bearer token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Bearer token for internal API",
        )

    token = authorization[7:]  # 移除 "Bearer " 前綴

    # 檢查 token 是否有效
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
    """取得單例 MCP 服務"""
    return McpService()


@lru_cache()
def get_hook_service() -> HookService:
    """取得單例 Hook 服務"""
    return HookService()


@lru_cache()
def get_claude_md_service() -> ClaudeMdService:
    """取得單例 Claude.md 服務"""
    return ClaudeMdService()


def get_internal_service() -> InternalService:
    """取得 Internal Service 實例"""
    return InternalService()


def get_template_install_service(
    mcp_service: McpService = Depends(get_mcp_service),
    hook_service: HookService = Depends(get_hook_service),
    claude_md_service: ClaudeMdService = Depends(get_claude_md_service),
) -> TemplateInstallService:
    """取得 Template Install Service 實例（注入依賴）"""
    return TemplateInstallService(
        mcp_service=mcp_service,
        hook_service=hook_service,
        claude_md_service=claude_md_service,
    )


__all__ = [
    "verify_internal_token",
    "get_internal_service",
    "get_template_install_service",
    "get_mcp_service",
    "get_hook_service",
    "get_claude_md_service",
]