"""Internal API router"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from .dependencies import (
    get_internal_service,
    get_template_install_service,
    verify_internal_token,
)
from .models import (
    ClaudeCodeRequest,
    CodexSettingsRequest,
    FirewallConfigRequest,
    GitSettingsRequest,
    InternalApiResponse,
    SSHKeysRequest,
    WorkspaceSetupStatusResponse,
)
from .service import InternalService
from .template_install_models import (
    ClaudeMdInstallRequest,
    ClaudeMdInstallResponse,
    HooksInstallRequest,
    HooksInstallResponse,
    InstallResults,
    McpInstallRequest,
    McpInstallResponse,
    OutputStyleInstallRequest,
    OutputStyleInstallResponse,
    SkillsInstallRequest,
    SkillsInstallResponse,
    ScriptsInstallRequest,
    ScriptsInstallResponse,
    SlashCommandInstallRequest,
    SlashCommandInstallResponse,
    SubagentInstallRequest,
    SubagentInstallResponse,
    TemplateInstallRequest,
    TemplateInstallResponse,
    TemplateInstallItemResult,
    TemplateInstallResults,
)
from .template_install_service import TemplateInstallService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/internal",
    tags=["Internal API"],
    dependencies=[Depends(verify_internal_token)],
)


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
        logger.info("Received Claude Code sync request")
        logger.info(f"Original request object: {request}")
        logger.info(f"Request model_dump: {request.model_dump()}")
        logger.info(f"Request model_dump(by_alias=True): {request.model_dump(by_alias=True)}")

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


# ============ Template Install API ============


@router.post(
    "/workspaces/{workspace_id}/claude-code/slash-commands/install",
    response_model=SlashCommandInstallResponse,
    summary="Install Slash Commands",
    description="Install template Slash Commands to USER scope (~/.claude/commands/). If filename contains '/' (e.g., 'namespace/command.md'), install to corresponding namespace subdirectory; otherwise install directly to commands directory"
)
async def install_slash_commands(
    workspace_id: str,
    request: SlashCommandInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SlashCommandInstallResponse:
    """Install Slash Commands"""
    try:
        success, results = await service.install_slash_commands(workspace_id, request)

        total = len(request.commands)
        message = f"Successfully installed {total} slash commands"
        if results.failed:
            message = f"Install slash commands: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return SlashCommandInstallResponse(
            success=success,
            message=message,
            workspaceId=workspace_id,
            results=results
        )
    except Exception as e:
        logger.error(f"Failed to install slash commands: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install slash commands: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/claude-code/subagents/install",
    response_model=SubagentInstallResponse,
    summary="Install Subagents",
    description="Install template Subagents to workspace user scope"
)
async def install_subagents(
    workspace_id: str,
    request: SubagentInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SubagentInstallResponse:
    """Install Subagents"""
    try:
        success, results = await service.install_subagents(workspace_id, request)

        total = len(request.subagents)
        message = f"Successfully installed {total} subagents"
        if results.failed:
            message = f"Install subagents: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return SubagentInstallResponse(
            success=success,
            message=message,
            workspaceId=workspace_id,
            results=results
        )
    except Exception as e:
        logger.error(f"Failed to install subagents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install subagents: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/claude-code/output-styles/install",
    response_model=OutputStyleInstallResponse,
    summary="Install Output Styles",
    description="Install template Output Styles to workspace personal scope"
)
async def install_output_styles(
    workspace_id: str,
    request: OutputStyleInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> OutputStyleInstallResponse:
    """Install Output Styles"""
    try:
        success, results = await service.install_output_styles(workspace_id, request)

        total = len(request.outputStyles)
        message = f"Successfully installed {total} output styles"
        if results.failed:
            message = f"Install output styles: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return OutputStyleInstallResponse(
            success=success,
            message=message,
            workspaceId=workspace_id,
            results=results
        )
    except Exception as e:
        logger.error(f"Failed to install output styles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install output styles: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/claude-code/claude-md/install",
    response_model=ClaudeMdInstallResponse,
    summary="Install Claude.md",
    description="Install template Claude.md to workspace user scope"
)
async def install_claude_md(
    workspace_id: str,
    request: ClaudeMdInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> ClaudeMdInstallResponse:
    """Install Claude.md"""
    try:
        success = await service.install_claude_md(workspace_id, request)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to install Claude.md"
            )

        return ClaudeMdInstallResponse(
            success=True,
            message="Successfully installed Claude.md",
            workspaceId=workspace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install Claude.md: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install Claude.md: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/claude-code/mcp/install",
    response_model=McpInstallResponse,
    summary="Install MCP Servers",
    description="Install template MCP Servers to workspace user scope"
)
async def install_mcp_servers(
    workspace_id: str,
    request: McpInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> McpInstallResponse:
    """Install MCP Servers"""
    try:
        success, results = await service.install_mcp_servers(workspace_id, request)

        total = len(request.mcpServers)
        message = f"Successfully installed {total} MCP servers"
        if results.failed:
            message = f"Install MCP servers: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return McpInstallResponse(
            success=success,
            message=message,
            workspaceId=workspace_id,
            results=results
        )
    except Exception as e:
        logger.error(f"Failed to install MCP servers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install MCP servers: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/claude-code/hooks/install",
    response_model=HooksInstallResponse,
    summary="Install Hooks",
    description="Install template Hooks to workspace user scope"
)
async def install_hooks(
    workspace_id: str,
    request: HooksInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> HooksInstallResponse:
    """Install Hooks"""
    try:
        success = await service.install_hooks(workspace_id, request)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to install hooks"
            )

        return HooksInstallResponse(
            success=True,
            message="Successfully installed hooks configuration",
            workspaceId=workspace_id
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install hooks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install hooks: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/scripts/install",
    response_model=ScriptsInstallResponse,
    summary="Install Scripts",
    description="Copy template Scripts to workspace /scripts/{templateName}/ directory"
)
async def install_scripts(
    workspace_id: str,
    request: ScriptsInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> ScriptsInstallResponse:
    """Install Scripts"""
    try:
        success, results, target_path, total_size = await service.install_scripts(
            workspace_id, request
        )

        total = len(request.scripts)
        message = f"Successfully installed {total} scripts to {target_path}/"
        if results.failed:
            message = f"Install scripts: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return ScriptsInstallResponse(
            success=success,
            message=message,
            templateName=request.templateName,
            targetPath=target_path,
            results=results,
            totalFiles=total,
            totalSize=total_size
        )
    except Exception as e:
        logger.error(f"Failed to install scripts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install scripts: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/skills/install",
    response_model=SkillsInstallResponse,
    summary="Install Skills",
    description="Copy template Skills to workspace CLI's project scope directory"
)
async def install_skills(
    workspace_id: str,
    request: SkillsInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SkillsInstallResponse:
    """Install Skills to workspace project scope."""
    try:
        success, results, target_path, total_size = await service.install_skills(
            workspace_id, request
        )

        total = len(request.skills)
        message = f"Successfully installed {total} skills to {target_path}/"
        if results.failed:
            message = f"Install skills: {len(results.created)} created, {len(results.updated)} updated, {len(results.failed)} failed"

        return SkillsInstallResponse(
            success=success,
            message=message,
            cliType=request.cliType,
            targetPath=target_path,
            results=results,
            totalFiles=total,
            totalSize=total_size,
        )
    except Exception as e:
        logger.error(f"Failed to install skills: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to install skills: {str(e)}"
        )


@router.post(
    "/workspaces/{workspace_id}/templates/install",
    response_model=TemplateInstallResponse,
    summary="Batch install template configurations",
    description="Install all template configurations at once (Claude.md, Slash Commands, Subagents, MCP, Hooks, Scripts, Skills)"
)
async def install_template(
    workspace_id: str,
    request: TemplateInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> TemplateInstallResponse:
    """Batch install template configurations"""
    results = TemplateInstallResults()
    overall_success = True

    if request.installPlan:
        compiled_results = await service.install_compiled_files(
            workspace_id,
            request.installPlan,
        )

        def _to_item_result(install_results: InstallResults) -> TemplateInstallItemResult | None:
            total = (
                len(install_results.created)
                + len(install_results.updated)
                + len(install_results.failed)
            )
            if total == 0:
                return None
            success = len(install_results.failed) == 0
            return TemplateInstallItemResult(
                success=success,
                created=len(install_results.created),
                updated=len(install_results.updated),
                failed=len(install_results.failed),
            )

        results.claudeMd = _to_item_result(compiled_results["claudeMd"])
        results.slashCommands = _to_item_result(compiled_results["slashCommands"])
        results.subagents = _to_item_result(compiled_results["subagents"])
        results.outputStyles = _to_item_result(compiled_results["outputStyles"])

        if any(install_results.failed for install_results in compiled_results.values()):
            overall_success = False

        cli_type = (request.cliType or request.installPlan.target).strip().lower()
        install_hints = request.installPlan.install_hints

        if install_hints.get("outputStyles"):
            try:
                success, os_results = await service.install_target_output_style(
                    workspace_id,
                    cli_type,
                    install_hints["outputStyles"],
                )
                results.outputStyles = TemplateInstallItemResult(
                    success=success,
                    created=len(os_results.created),
                    updated=len(os_results.updated),
                    failed=len(os_results.failed),
                )
                if not success:
                    overall_success = False
            except Exception as e:
                logger.error(f"Failed to install output styles in compiled plan: {e}")
                results.outputStyles = TemplateInstallItemResult(
                    success=False,
                    created=0,
                    updated=0,
                    failed=len(install_hints["outputStyles"]),
                    error=str(e),
                )
                overall_success = False

        if install_hints.get("mcpServers"):
            try:
                success, mcp_results = await service.install_target_mcp_servers(
                    workspace_id,
                    cli_type,
                    install_hints["mcpServers"],
                )
                results.mcp = TemplateInstallItemResult(
                    success=success,
                    created=len(mcp_results.created),
                    updated=len(mcp_results.updated),
                    failed=len(mcp_results.failed),
                )
                if not success:
                    overall_success = False
            except Exception as e:
                logger.error(f"Failed to install MCP servers in compiled plan: {e}")
                results.mcp = TemplateInstallItemResult(
                    success=False,
                    created=0,
                    updated=0,
                    failed=len(install_hints["mcpServers"]),
                    error=str(e),
                )
                overall_success = False

        if install_hints.get("hooks"):
            try:
                success, hooks_results = await service.install_target_hooks(
                    workspace_id,
                    cli_type,
                    install_hints["hooks"],
                )
                results.hooks = TemplateInstallItemResult(
                    success=success,
                    created=len(hooks_results.created),
                    updated=len(hooks_results.updated),
                    failed=len(hooks_results.failed),
                )
                if not success:
                    overall_success = False
            except Exception as e:
                logger.error(f"Failed to install hooks in compiled plan: {e}")
                results.hooks = TemplateInstallItemResult(
                    success=False,
                    created=0,
                    updated=0,
                    failed=1,
                    error=str(e),
                )
                overall_success = False

        if install_hints.get("skills"):
            try:
                from .template_install_models import SkillsInstallRequest as SkillsRequest

                skills_request = SkillsRequest(
                    cliType=cli_type,
                    skills=install_hints["skills"],
                )
                success, skills_results, _, _ = await service.install_skills(
                    workspace_id, skills_request
                )
                results.skills = TemplateInstallItemResult(
                    success=success,
                    created=len(skills_results.created),
                    updated=len(skills_results.updated),
                    failed=len(skills_results.failed),
                )
                if not success:
                    overall_success = False
            except Exception as e:
                logger.error(f"Failed to install skills in compiled plan: {e}")
                results.skills = TemplateInstallItemResult(
                    success=False,
                    created=0,
                    updated=0,
                    failed=len(install_hints["skills"]),
                    error=str(e),
                )
                overall_success = False

        message = "Template installation completed" if overall_success else "Template installation completed (with some failures)"

        if request.initCommands and request.initCommands.strip():
            try:
                logger.info(f"Starting to execute template initialization commands: {request.templateName}")
                success, stdout, stderr = await service.execute_init_commands(
                    workspace_id, request.initCommands
                )
                if not success:
                    redacted = (stderr or "").strip()
                    redacted_msg = redacted[:200] + ("..." if len(redacted) > 200 else "")
                    logger.warning(
                        "Template initialization command execution failed (workspace=%s, template=%s): %s",
                        workspace_id,
                        request.templateId,
                        redacted_msg,
                    )
                    overall_success = False
                    message = "Template installation completed (initialization command failed)"
                else:
                    logger.info(
                        "Template initialization command execution succeeded (workspace=%s, template=%s, stdout_length=%d)",
                        workspace_id,
                        request.templateId,
                        len(stdout or ""),
                    )
            except Exception as e:
                logger.error(f"Failed to execute init commands in batch: {e}")
                overall_success = False
                message = "Template installation completed (initialization command failed)"

        return TemplateInstallResponse(
            success=overall_success,
            message=message,
            templateId=request.templateId,
            templateName=request.templateName,
            results=results,
        )

    # Install Claude.md
    if request.claudeMd:
        try:
            success = await service.install_claude_md(workspace_id, request.claudeMd)
            results.claudeMd = TemplateInstallItemResult(
                success=success,
                created=0,
                updated=1 if success else 0,
                failed=0 if success else 1
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install Claude.md in batch: {e}")
            results.claudeMd = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=1,
                error=str(e)
            )
            overall_success = False

    # Install Slash Commands
    if request.slashCommands:
        try:
            from .template_install_models import SlashCommandInstallRequest as SCRequest
            sc_request = SCRequest(commands=request.slashCommands)
            success, sc_results = await service.install_slash_commands(workspace_id, sc_request)
            results.slashCommands = TemplateInstallItemResult(
                success=success,
                created=len(sc_results.created),
                updated=len(sc_results.updated),
                failed=len(sc_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install slash commands in batch: {e}")
            results.slashCommands = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.slashCommands),
                error=str(e)
            )
            overall_success = False

    # Install Subagents
    if request.subagents:
        try:
            from .template_install_models import SubagentInstallRequest as SARequest
            sa_request = SARequest(subagents=request.subagents)
            success, sa_results = await service.install_subagents(workspace_id, sa_request)
            results.subagents = TemplateInstallItemResult(
                success=success,
                created=len(sa_results.created),
                updated=len(sa_results.updated),
                failed=len(sa_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install subagents in batch: {e}")
            results.subagents = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.subagents),
                error=str(e)
            )
            overall_success = False

    # Install Output Styles
    if request.outputStyles:
        try:
            from .template_install_models import OutputStyleInstallRequest as OSRequest
            os_request = OSRequest(outputStyles=request.outputStyles)
            success, os_results = await service.install_output_styles(workspace_id, os_request)
            results.outputStyles = TemplateInstallItemResult(
                success=success,
                created=len(os_results.created),
                updated=len(os_results.updated),
                failed=len(os_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install output styles in batch: {e}")
            results.outputStyles = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.outputStyles),
                error=str(e)
            )
            overall_success = False

    # Install MCP Servers
    if request.mcpServers:
        try:
            from .template_install_models import McpInstallRequest as McpRequest
            mcp_request = McpRequest(mcpServers=request.mcpServers)
            success, mcp_results = await service.install_mcp_servers(workspace_id, mcp_request)
            results.mcp = TemplateInstallItemResult(
                success=success,
                created=len(mcp_results.created),
                updated=len(mcp_results.updated),
                failed=len(mcp_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install MCP servers in batch: {e}")
            results.mcp = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.mcpServers),
                error=str(e)
            )
            overall_success = False

    # Install Hooks
    if request.hooks:
        try:
            from .template_install_models import HooksInstallRequest as HooksRequest
            hooks_request = HooksRequest(hooks=request.hooks)
            success, hooks_results = await service.install_hooks(workspace_id, hooks_request)
            results.hooks = TemplateInstallItemResult(
                success=success,
                created=len(hooks_results.created),
                updated=len(hooks_results.updated),
                failed=len(hooks_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install hooks in batch: {e}")
            results.hooks = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=1,
                error=str(e)
            )
            overall_success = False

    # Install Scripts
    if request.scripts:
        try:
            from .template_install_models import ScriptsInstallRequest as ScriptsRequest
            scripts_request = ScriptsRequest(
                templateName=request.templateName,
                scripts=request.scripts
            )
            success, scripts_results, _, _ = await service.install_scripts(
                workspace_id, scripts_request
            )
            results.scripts = TemplateInstallItemResult(
                success=success,
                created=len(scripts_results.created),
                updated=len(scripts_results.updated),
                failed=len(scripts_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install scripts in batch: {e}")
            results.scripts = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.scripts),
                error=str(e)
            )
            overall_success = False

    # Install Skills
    if request.skills:
        try:
            from .template_install_models import SkillsInstallRequest as SkillsRequest
            skills_request = SkillsRequest(
                cliType=request.cliType or "claude-code",
                skills=request.skills,
            )
            success, skills_results, _, _ = await service.install_skills(
                workspace_id, skills_request
            )
            results.skills = TemplateInstallItemResult(
                success=success,
                created=len(skills_results.created),
                updated=len(skills_results.updated),
                failed=len(skills_results.failed)
            )
            if not success:
                overall_success = False
        except Exception as e:
            logger.error(f"Failed to install skills in batch: {e}")
            results.skills = TemplateInstallItemResult(
                success=False,
                created=0,
                updated=0,
                failed=len(request.skills),
                error=str(e)
            )
            overall_success = False

    message = "Template installation completed" if overall_success else "Template installation completed (with some failures)"

    # Execute initialization commands (after all configurations are installed)
    if request.initCommands and request.initCommands.strip():
        try:
            logger.info(f"Starting to execute template initialization commands: {request.templateName}")
            success, stdout, stderr = await service.execute_init_commands(
                workspace_id, request.initCommands
            )
            if not success:
                redacted = (stderr or "").strip()
                redacted_msg = redacted[:200] + ("..." if len(redacted) > 200 else "")
                logger.warning(
                    "Initialization command execution failed, but does not affect template installation (workspace=%s, stderr=%s)",
                    workspace_id,
                    redacted_msg,
                )
                # Initialization command failure does not affect overall installation result
                # But will hint in message (only override when no error message exists)
                if overall_success:
                    message = "Template installation completed, but initialization command execution failed"
            else:
                logger.info(f"Initialization command execution succeeded: {request.templateName}")
        except Exception as e:
            logger.error(f"Exception occurred while executing initialization command: {e}")
            # Does not affect overall installation result

    return TemplateInstallResponse(
        success=overall_success,
        message=message,
        templateId=request.templateId,
        templateName=request.templateName,
        results=results
    )


__all__ = ["router"]
