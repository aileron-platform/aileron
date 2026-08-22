"""Internal API router"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from aileron_marketplace_core import (
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
)

from app.config.settings import get_settings
from app.database.session import get_async_db
from app.modules.marketplace_operations.errors import MarketplaceOperationError
from app.modules.thread.capabilities_store import CapabilitiesStore
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.worktree_config import set_worktree_subdir
from app.modules.version_control.worktree_gitignore import WorktreeGitignoreManager
from app.modules.auth.manager_assertion import (
    ManagerAssertionConflict,
    ManagerAssertionInvalid,
    get_manager_assertion_verifier,
)
from app.modules.runtime_control.drain import (
    RuntimeDrainConflict,
    RuntimeDrainTimeout,
    get_runtime_drain_service,
)

from .dependencies import (
    get_internal_service,
    verify_manager_assertion,
)
from .models import (
    CapabilitiesSyncRequest,
    ClaudeCodeRequest,
    CodexSettingsRequest,
    FirewallConfigRequest,
    GitSettingsRequest,
    InternalApiResponse,
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
    RuntimeDrainErrorResponse,
    SetupCheckDetail,
    SSHKeysRequest,
    WorkspaceSetupStatusResponse,
)
from .commands import InternalService

logger = logging.getLogger(__name__)

_MAX_USER_COPY_METADATA_BYTES = 2 * 1024 * 1024
_MAX_USER_COPY_MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class WorktreeGitignoreSyncRequest(BaseModel):
    """Request body for worktree gitignore synchronization."""

    subdir: str = Field(...)
    previous: str | None = None


router = APIRouter(
    prefix="/internal",
    tags=["Internal API"],
    dependencies=[Depends(verify_manager_assertion)],
)


@router.post(
    "/runtime/drain",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses={
        401: {"model": RuntimeDrainErrorResponse},
        409: {"model": RuntimeDrainErrorResponse},
        504: {"model": RuntimeDrainErrorResponse},
    },
    summary="Drain the current Runtime generation",
)
async def drain_runtime(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """Verify a one-time Manager assertion and close all local surfaces."""

    assertion = _bearer_assertion(authorization)
    if assertion is None:
        return _drain_error(401, "RUNTIME_ASSERTION_MISSING")
    try:
        claims = get_manager_assertion_verifier().verify_runtime_drain(assertion)
        await get_runtime_drain_service().drain(
            claims,
            automation_runner=getattr(request.app.state, "automation_runner", None),
        )
    except ManagerAssertionInvalid as exc:
        return _drain_error(401, exc.error_code)
    except (ManagerAssertionConflict, RuntimeDrainConflict) as exc:
        return _drain_error(409, exc.error_code)
    except RuntimeDrainTimeout as exc:
        return _drain_error(504, exc.error_code)
    except Exception:
        logger.exception("Runtime drain cleanup did not finish")
        return _drain_error(504, "WORKSPACE_RUNTIME_DRAIN_INCOMPLETE")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _bearer_assertion(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    assertion = authorization.removeprefix("Bearer ").strip()
    return assertion or None


def _drain_error(status_code: int, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"errorCode": error_code},
    )


@router.post("/worktree/sync-gitignore")
async def sync_worktree_gitignore(
    request: WorktreeGitignoreSyncRequest,
) -> dict[str, bool]:
    """Synchronize the managed worktree .gitignore block."""
    try:
        subdir = set_worktree_subdir(request.subdir)
        get_git_service().set_worktree_subdir(subdir)
        manager = WorktreeGitignoreManager(get_settings().AILERON_WORKSPACE_PATH)
        changed = manager.ensure(subdir)
        get_git_service().invalidate_context_path_cache()
        return {"changed": changed}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WORKTREE_SUBDIR_INVALID"},
        ) from exc


@router.post(
    "/settings/capabilities",
    response_model=InternalApiResponse,
    summary="Sync workspace capabilities",
)
async def sync_capabilities(
    request: CapabilitiesSyncRequest,
    db: Annotated[AsyncSession, Depends(get_async_db)],
) -> InternalApiResponse:
    """Sync workspace capabilities to workspace-runtime."""
    await CapabilitiesStore().put(db, request.workspace_id, request.capabilities)
    return InternalApiResponse(
        success=True,
        message="Capabilities synchronized successfully",
        details={"workspace_id": request.workspace_id},
    )


@router.post(
    "/settings/ssh-keys",
    response_model=InternalApiResponse,
    summary="Sync SSH Keys settings",
    description="Receive SSH private key and public key, create corresponding files in container",
)
async def sync_ssh_keys(
    request: SSHKeysRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> InternalApiResponse:
    """Sync SSH Keys settings to workspace-runtime"""
    try:
        logger.info("Received SSH Keys sync request")

        details = await service.setup_ssh_keys(request)

        logger.info("SSH Keys sync successful")
        return InternalApiResponse(
            success=True, message="SSH Keys configured successfully", details=details
        )

    except Exception as e:
        logger.error(f"SSH Keys sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSH Keys setup failed: {str(e)}",
        )


@router.post(
    "/settings/claude-code",
    response_model=InternalApiResponse,
    summary="Sync Claude Code settings",
    description="Configure Claude Code related files and environment variables",
)
async def sync_claude_code(
    request: ClaudeCodeRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
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
            details=details,
        )

    except Exception as e:
        logger.error(f"Claude Code sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claude Code setup failed: {str(e)}",
        )


@router.post(
    "/settings/codex",
    response_model=InternalApiResponse,
    summary="Sync Codex settings",
    description="Configure Codex CLI auth state and environment variables",
)
async def sync_codex(
    request: CodexSettingsRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
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
            details=details,
        )

    except ValueError as e:
        logger.warning("Codex sync validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    except Exception as e:
        logger.error("Codex sync failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Codex setup failed: {str(e)}",
        )


@router.post(
    "/settings/codex/login/start",
    response_model=InternalApiResponse,
    summary="Start Codex login",
    description="Start a Codex ChatGPT device-code login flow",
)
async def start_codex_login(
    service: Annotated[InternalService, Depends(get_internal_service)],
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
    description="Read Codex account status from the managed CLI auth home",
)
async def get_codex_login_status(
    service: Annotated[InternalService, Depends(get_internal_service)],
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
    description="Cancel a pending Codex login flow",
)
async def cancel_codex_login(
    login_id: str, service: Annotated[InternalService, Depends(get_internal_service)]
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
    description="Logout Codex and clear managed CLI auth state",
)
async def logout_codex(
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> InternalApiResponse:
    """Logout Codex."""
    details = await service.logout_codex()
    return InternalApiResponse(
        success=True,
        message="Codex logged out",
        details=details,
    )


@router.post(
    "/settings/git",
    response_model=InternalApiResponse,
    summary="Sync Git global settings",
    description="Configure Git global username and email",
)
async def sync_git_settings(
    request: GitSettingsRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> InternalApiResponse:
    """Sync Git settings to workspace-runtime"""
    try:
        logger.info("Received Git settings sync request")

        details = await service.setup_git_settings(request)

        logger.info("Git settings sync successful")
        return InternalApiResponse(
            success=True,
            message="Git global configuration completed successfully",
            details=details,
        )

    except Exception as e:
        logger.error(f"Git settings sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git settings setup failed: {str(e)}",
        )


@router.post(
    "/settings/firewall",
    response_model=InternalApiResponse,
    summary="Sync firewall settings",
    description="Apply firewall rules to container",
)
async def sync_firewall_settings(
    request: FirewallConfigRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> InternalApiResponse:
    """Sync firewall settings to workspace-runtime"""
    try:
        logger.info("Received firewall settings sync request")
        logger.debug(f"Firewall configuration: {request.model_dump()}")

        details = await service.apply_firewall_settings(request)

        if details.get("status") == "error":
            logger.error(
                f"Firewall settings application failed: {details.get('message')}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=details.get("message", "Firewall settings application failed"),
            )

        logger.info("Firewall settings sync successful")
        return InternalApiResponse(
            success=True,
            message="Firewall settings applied successfully",
            details=details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Firewall settings sync failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firewall settings sync failed: {str(e)}",
        )


@router.get(
    "/health",
    response_model=InternalApiResponse,
    summary="Internal API health check",
    description="Check internal API service status",
)
async def internal_health_check(
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> InternalApiResponse:
    """Internal API health check"""
    return InternalApiResponse(
        success=True,
        message="Internal API is healthy",
        details={
            "service": "workspace-runtime-internal",
            "version": "1.0.0",
            "runtimeInstanceId": get_settings().AILERON_RUNTIME_INSTANCE_ID,
        },
    )


@router.post(
    "/marketplace/plugins/install",
    response_model=MarketplacePluginCommandResult,
    summary="Install one Marketplace plugin through the target client CLI",
)
async def install_marketplace_plugin(
    request: MarketplacePluginInstallRequest,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> MarketplacePluginCommandResult:
    """Return one bounded terminal CLI result without lifecycle state."""

    try:
        return await service.install_marketplace_plugin(request)
    except MarketplaceOperationError as exc:
        raise _marketplace_http_error(exc) from exc


@router.post(
    "/marketplace/user-copies/preflight",
    response_model=UserCopyProjectionPreflightResultContract,
    summary="Preflight one user-scope Marketplace copy",
)
async def preflight_marketplace_user_copy(
    request: UserCopyProjectionPreflightRequestContract,
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> UserCopyProjectionPreflightResultContract:
    """Return exact merge, no-op, conflict, and blocking projections."""

    try:
        return await service.preflight_marketplace_user_copy(request)
    except MarketplaceOperationError as exc:
        raise _marketplace_http_error(exc) from exc


@router.post(
    "/marketplace/user-copies/apply",
    response_model=UserCopyProjectionApplyResultContract,
    summary="Apply one canonical user-copy snapshot",
)
async def apply_marketplace_user_copy(
    service: Annotated[InternalService, Depends(get_internal_service)],
    metadata: Annotated[str, Form(max_length=_MAX_USER_COPY_METADATA_BYTES)],
    bundle: Annotated[UploadFile, File()],
    content_length: Annotated[
        int | None,
        Header(alias="content-length", ge=0),
    ] = None,
) -> UserCopyProjectionApplyResultContract:
    """Verify multipart metadata and atomically apply the uploaded ZIP."""

    try:
        if content_length is not None and content_length > (
            service.marketplace_user_copy_max_archive_bytes
            + _MAX_USER_COPY_METADATA_BYTES
            + _MAX_USER_COPY_MULTIPART_OVERHEAD_BYTES
        ):
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "marketplace.user_copy.request_too_large"},
            )
        if len(metadata.encode("utf-8")) > _MAX_USER_COPY_METADATA_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "marketplace.user_copy.request_too_large"},
            )
        if bundle.content_type != "application/zip":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": ("marketplace.user_copy.archive_content_type_invalid")},
            )
        try:
            parsed_metadata = UserCopyProjectionApplyMetadataContract.model_validate_json(
                metadata
            )
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "marketplace.user_copy.runtime_contract_invalid"},
            ) from exc
        archive = await bundle.read(service.marketplace_user_copy_max_archive_bytes + 1)
        if len(archive) > service.marketplace_user_copy_max_archive_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={"code": "marketplace.user_copy.archive_too_large"},
            )
        return await service.apply_marketplace_user_copy(
            parsed_metadata,
            archive,
        )
    except MarketplaceOperationError as exc:
        raise _marketplace_http_error(exc) from exc
    finally:
        await bundle.close()


def _marketplace_http_error(
    error: MarketplaceOperationError,
) -> HTTPException:
    return HTTPException(
        status_code=error.http_status,
        detail={"code": error.code},
    )


@router.get(
    "/setup/status",
    response_model=WorkspaceSetupStatusResponse,
    summary="Query workspace initialization status",
    description="Check sync status of SSH, Git, Claude Code and other initialization items",
)
async def get_workspace_setup_status(
    service: Annotated[InternalService, Depends(get_internal_service)],
) -> WorkspaceSetupStatusResponse:
    """Get latest status of workspace initialization sync"""
    try:
        checks = await service.get_setup_status()
        return WorkspaceSetupStatusResponse(
            success=True,
            message="Fetch initialization status successful",
            checks={
                name: SetupCheckDetail.model_validate(detail)
                for name, detail in checks.items()
            },
        )
    except Exception as exc:
        logger.error(f"Failed to fetch workspace initialization status: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch setup status: {exc}",
        )


__all__ = ["router"]
