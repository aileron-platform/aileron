"""Internal API router"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.config.settings import get_settings
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.worktree_config import set_worktree_subdir
from app.modules.version_control.worktree_gitignore import WorktreeGitignoreManager

from .dependencies import (
    get_internal_service,
    verify_internal_token,
)
from .models import (
    ClaudeCodeRequest,
    CodexSettingsRequest,
    FirewallConfigRequest,
    GeminiRequest,
    GitSettingsRequest,
    InternalApiResponse,
    MarketplaceInstallExecutionRequest,
    MarketplaceInstallExecutionResult,
    SSHKeysRequest,
    WorkspaceSetupStatusResponse,
)
from .service import InternalService

logger = logging.getLogger(__name__)


class WorktreeGitignoreSyncRequest(BaseModel):
    """Request body for worktree gitignore synchronization."""

    subdir: str = Field(...)
    previous: str | None = None

router = APIRouter(
    prefix="/internal",
    tags=["Internal API"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/worktree/sync-gitignore")
async def sync_worktree_gitignore(request: WorktreeGitignoreSyncRequest) -> dict[str, bool]:
    """Synchronize the managed worktree .gitignore block."""
    try:
        subdir = set_worktree_subdir(request.subdir)
        get_git_service().set_worktree_subdir(subdir)
        manager = WorktreeGitignoreManager(get_settings().WORKSPACE_PATH)
        changed = manager.ensure(subdir)
        get_git_service().invalidate_context_path_cache()
        return {"changed": changed}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WORKTREE_SUBDIR_INVALID"},
        ) from exc


@router.post(
    "/settings/ssh-keys",
    response_model=InternalApiResponse,
    summary="Sync SSH Keys settings",
    description="Receive SSH private key and public key, create corresponding files in container"
)
async def sync_ssh_keys(
    request: SSHKeysRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync SSH Keys settings to workspace-runtime"""
    try:
        logger.info("Received SSH Keys sync request")

        details = await service.setup_ssh_keys(request)

        logger.info("SSH Keys sync successful")
        return InternalApiResponse(
            success=True,
            message="SSH Keys configured successfully",
            details=details
        )

    except Exception as e:
        logger.error(f"SSH Keys sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSH Keys setup failed: {str(e)}"
        )


@router.post(
    "/settings/claude-code",
    response_model=InternalApiResponse,
    summary="Sync Claude Code settings",
    description="Configure Claude Code related files and environment variables"
)
async def sync_claude_code(
    request: ClaudeCodeRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync Claude Code settings to workspace-runtime"""
    try:
        logger.info(
            "Received Claude Code sync request: auth_method=%s model=%s env_count=%s has_oauth_account=%s has_subscription_token=%s",
            request.auth_method,
            request.model,
            len(request.environment_variables),
            bool(request.oauth_account),
            bool(request.subscription_access_token),
        )

        details = await service.setup_claude_code(request)

        logger.info("Claude Code sync successful")
        return InternalApiResponse(
            success=True,
            message="Claude Code configuration completed successfully",
            details=details
        )

    except Exception as e:
        logger.error(f"Claude Code sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claude Code setup failed: {str(e)}"
        )


@router.post(
    "/settings/codex",
    response_model=InternalApiResponse,
    summary="Sync Codex settings",
    description="Configure Codex CLI auth state and environment variables"
)
async def sync_codex(
    request: CodexSettingsRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync Codex settings to workspace-runtime"""
    try:
        logger.info(
            "Received Codex sync request: login_status=%s clear_auth=%s env_count=%s",
            request.login_status,
            request.clear_auth,
            len(request.environment_variables),
        )

        details = await service.setup_codex(request)

        logger.info("Codex sync successful")
        return InternalApiResponse(
            success=True,
            message="Codex configuration completed successfully",
            details=details
        )

    except ValueError as e:
        logger.warning("Codex sync validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Codex sync failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Codex setup failed: {str(e)}"
        )


@router.post(
    "/settings/codex/login/start",
    response_model=InternalApiResponse,
    summary="Start Codex login",
    description="Start a Codex ChatGPT device-code login flow"
)
async def start_codex_login(
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Start Codex login in workspace-runtime."""
    try:
        details = await service.start_codex_login()
        return InternalApiResponse(
            success=True,
            message="Codex login started",
            details=details,
        )
    except Exception as e:
        logger.error("Failed to start Codex login: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start Codex login: {str(e)}",
        )


@router.get(
    "/settings/codex/login/status",
    response_model=InternalApiResponse,
    summary="Get Codex login status",
    description="Read Codex account status from the managed CLI auth home"
)
async def get_codex_login_status(
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Get Codex login status."""
    details = await service.get_codex_login_status()
    return InternalApiResponse(
        success=True,
        message="Codex login status fetched",
        details=details,
    )


@router.post(
    "/settings/codex/login/cancel/{login_id}",
    response_model=InternalApiResponse,
    summary="Cancel Codex login",
    description="Cancel a pending Codex login flow"
)
async def cancel_codex_login(
    login_id: str,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Cancel Codex login."""
    details = await service.cancel_codex_login(login_id)
    return InternalApiResponse(
        success=True,
        message="Codex login canceled",
        details=details,
    )


@router.post(
    "/settings/codex/logout",
    response_model=InternalApiResponse,
    summary="Logout Codex",
    description="Logout Codex and clear managed CLI auth state"
)
async def logout_codex(
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Logout Codex."""
    details = await service.logout_codex()
    return InternalApiResponse(
        success=True,
        message="Codex logged out",
        details=details,
    )


@router.post(
    "/settings/gemini",
    response_model=InternalApiResponse,
    summary="Sync Gemini settings",
    description="Write Gemini oauth_creds.json and environment variables"
)
async def sync_gemini(
    request: GeminiRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync Gemini settings to workspace-runtime"""
    try:
        logger.info("Received Gemini sync request")
        details = await service.setup_gemini(request)
        logger.info("Gemini sync successful")
        return InternalApiResponse(
            success=True,
            message="Gemini configuration completed successfully",
            details=details,
        )
    except Exception as e:
        logger.error(f"Gemini sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gemini setup failed: {str(e)}",
        )


@router.post(
    "/settings/git",
    response_model=InternalApiResponse,
    summary="Sync Git global settings",
    description="Configure Git global username and email"
)
async def sync_git_settings(
    request: GitSettingsRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync Git settings to workspace-runtime"""
    try:
        logger.info("Received Git settings sync request")

        details = await service.setup_git_settings(request)

        logger.info("Git settings sync successful")
        return InternalApiResponse(
            success=True,
            message="Git global configuration completed successfully",
            details=details
        )

    except Exception as e:
        logger.error(f"Git settings sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git settings setup failed: {str(e)}"
        )


@router.post(
    "/settings/firewall",
    response_model=InternalApiResponse,
    summary="Sync firewall settings",
    description="Apply firewall rules to container"
)
async def sync_firewall_settings(
    request: FirewallConfigRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """Sync firewall settings to workspace-runtime"""
    try:
        logger.info("Received firewall settings sync request")
        logger.debug(f"Firewall configuration: {request.model_dump()}")

        details = await service.apply_firewall_settings(request)

        if details.get("status") == "error":
            logger.error(f"Firewall settings application failed: {details.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=details.get("message", "Firewall settings application failed")
            )

        logger.info("Firewall settings sync successful")
        return InternalApiResponse(
            success=True,
            message="Firewall settings applied successfully",
            details=details
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Firewall settings sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firewall settings sync failed: {str(e)}"
        )


@router.get(
    "/health",
    response_model=InternalApiResponse,
    summary="Internal API health check",
    description="Check internal API service status"
)
async def internal_health_check() -> InternalApiResponse:
    """Internal API health check"""
    return InternalApiResponse(
        success=True,
        message="Internal API is healthy",
        details={
            "service": "workspace-runtime-internal",
            "version": "1.0.0"
        }
    )


@router.post(
    "/marketplace/install/execute",
    response_model=MarketplaceInstallExecutionResult,
    summary="Execute Marketplace provider CLI install",
    description="Run a provider CLI install command and return a blocking sanitized result",
)
async def execute_marketplace_install(
    request: MarketplaceInstallExecutionRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> MarketplaceInstallExecutionResult:
    """Execute a Marketplace provider CLI install command."""
    return await service.execute_marketplace_install(request)


@router.get(
    "/setup/status",
    response_model=WorkspaceSetupStatusResponse,
    summary="Query workspace initialization status",
    description="Check sync status of SSH, Git, Claude Code and other initialization items"
)
async def get_workspace_setup_status(
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> WorkspaceSetupStatusResponse:
    """Get latest status of workspace initialization sync"""
    try:
        checks = await service.get_setup_status()
        return WorkspaceSetupStatusResponse(
            success=True,
            message="Fetch initialization status successful",
            checks=checks,
        )
    except Exception as exc:
        logger.error(f"Failed to fetch workspace initialization status: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch setup status: {exc}",
        )


__all__ = ["router"]
