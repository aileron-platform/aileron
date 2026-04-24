"""Internal API 路由"""

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
    tags=["內部 API"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post(
    "/settings/ssh-keys",
    response_model=InternalApiResponse,
    summary="同步 SSH Keys 設定",
    description="接收 SSH 私鑰和公鑰，並在容器內建立對應的檔案"
)
async def sync_ssh_keys(
    request: SSHKeysRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """同步 SSH Keys 設定到 workspace-runtime"""
    try:
        logger.info("收到 SSH Keys 同步請求")

        details = await service.setup_ssh_keys(request)

        logger.info("SSH Keys 同步成功")
        return InternalApiResponse(
            success=True,
            message="SSH Keys 已成功設定",
            details=details
        )

    except Exception as e:
        logger.error(f"SSH Keys 同步失敗: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SSH Keys setup failed: {str(e)}"
        )


@router.post(
    "/settings/claude-code",
    response_model=InternalApiResponse,
    summary="同步 Claude Code 設定",
    description="設定 Claude Code 相關檔案和環境變數"
)
async def sync_claude_code(
    request: ClaudeCodeRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """同步 Claude Code 設定到 workspace-runtime"""
    try:
        logger.info("收到 Claude Code 同步請求")
        logger.info(f"原始請求物件: {request}")
        logger.info(f"請求 model_dump: {request.model_dump()}")
        logger.info(f"請求 model_dump(by_alias=True): {request.model_dump(by_alias=True)}")

        details = await service.setup_claude_code(request)

        logger.info("Claude Code 同步成功")
        return InternalApiResponse(
            success=True,
            message="Claude Code 設定已成功完成",
            details=details
        )

    except Exception as e:
        logger.error(f"Claude Code 同步失敗: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claude Code setup failed: {str(e)}"
        )


@router.post(
    "/settings/git",
    response_model=InternalApiResponse,
    summary="同步 Git 全域設定",
    description="設定 Git 全域使用者名稱和信箱"
)
async def sync_git_settings(
    request: GitSettingsRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """同步 Git 設定到 workspace-runtime"""
    try:
        logger.info("收到 Git 設定同步請求")

        details = await service.setup_git_settings(request)

        logger.info("Git 設定同步成功")
        return InternalApiResponse(
            success=True,
            message="Git 全域設定已成功完成",
            details=details
        )

    except Exception as e:
        logger.error(f"Git 設定同步失敗: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Git settings setup failed: {str(e)}"
        )


@router.post(
    "/settings/firewall",
    response_model=InternalApiResponse,
    summary="同步防火牆設定",
    description="套用防火牆規則到容器"
)
async def sync_firewall_settings(
    request: FirewallConfigRequest,
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> InternalApiResponse:
    """同步防火牆設定到 workspace-runtime"""
    try:
        logger.info("收到防火牆設定同步請求")
        logger.debug(f"防火牆配置: {request.model_dump()}")

        details = await service.apply_firewall_settings(request)

        if details.get("status") == "error":
            logger.error(f"防火牆設定套用失敗: {details.get('message')}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=details.get("message", "防火牆設定套用失敗")
            )

        logger.info("防火牆設定同步成功")
        return InternalApiResponse(
            success=True,
            message="防火牆設定已成功套用",
            details=details
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"防火牆設定同步失敗: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Firewall settings sync failed: {str(e)}"
        )


@router.get(
    "/health",
    response_model=InternalApiResponse,
    summary="內部 API 健康檢查",
    description="檢查內部 API 服務狀態"
)
async def internal_health_check() -> InternalApiResponse:
    """內部 API 健康檢查"""
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
    summary="查詢 Workspace 初始化狀態",
    description="檢查 SSH、Git 與 Claude Code 等初始化項目的同步狀態"
)
async def get_workspace_setup_status(
    service: Annotated[InternalService, Depends(get_internal_service)]
) -> WorkspaceSetupStatusResponse:
    """取得 Workspace 初始化同步的最新狀態"""
    try:
        checks = await service.get_setup_status()
        return WorkspaceSetupStatusResponse(
            success=True,
            message="取得初始化狀態成功",
            checks=checks,
        )
    except Exception as exc:
        logger.error(f"取得 Workspace 初始化狀態失敗: {exc}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch setup status: {exc}",
        )


# ============ Template Install API ============


@router.post(
    "/workspaces/{workspace_id}/claude-code/slash-commands/install",
    response_model=SlashCommandInstallResponse,
    summary="安裝 Slash Commands",
    description="將模板的 Slash Commands 安裝到 USER scope (~/.claude/commands/)。若檔案名稱包含 '/'（如 'namespace/command.md'），則安裝到對應的 namespace 子目錄；否則直接安裝到 commands 目錄下"
)
async def install_slash_commands(
    workspace_id: str,
    request: SlashCommandInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SlashCommandInstallResponse:
    """安裝 Slash Commands"""
    try:
        success, results = await service.install_slash_commands(workspace_id, request)

        total = len(request.commands)
        message = f"成功安裝 {total} 個 slash commands"
        if results.failed:
            message = f"安裝 slash commands: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="安裝 Subagents",
    description="將模板的 Subagents 安裝到 workspace 的 user scope"
)
async def install_subagents(
    workspace_id: str,
    request: SubagentInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SubagentInstallResponse:
    """安裝 Subagents"""
    try:
        success, results = await service.install_subagents(workspace_id, request)

        total = len(request.subagents)
        message = f"成功安裝 {total} 個 subagents"
        if results.failed:
            message = f"安裝 subagents: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="安裝 Output Styles",
    description="將模板的 Output Styles 安裝到 workspace 的 personal scope"
)
async def install_output_styles(
    workspace_id: str,
    request: OutputStyleInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> OutputStyleInstallResponse:
    """安裝 Output Styles"""
    try:
        success, results = await service.install_output_styles(workspace_id, request)

        total = len(request.outputStyles)
        message = f"成功安裝 {total} 個 output styles"
        if results.failed:
            message = f"安裝 output styles: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="安裝 Claude.md",
    description="將模板的 Claude.md 安裝到 workspace 的 user scope"
)
async def install_claude_md(
    workspace_id: str,
    request: ClaudeMdInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> ClaudeMdInstallResponse:
    """安裝 Claude.md"""
    try:
        success = await service.install_claude_md(workspace_id, request)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to install Claude.md"
            )

        return ClaudeMdInstallResponse(
            success=True,
            message="成功安裝 Claude.md",
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
    summary="安裝 MCP Servers",
    description="將模板的 MCP Servers 安裝到 workspace 的 user scope"
)
async def install_mcp_servers(
    workspace_id: str,
    request: McpInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> McpInstallResponse:
    """安裝 MCP Servers"""
    try:
        success, results = await service.install_mcp_servers(workspace_id, request)

        total = len(request.mcpServers)
        message = f"成功安裝 {total} 個 MCP servers"
        if results.failed:
            message = f"安裝 MCP servers: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="安裝 Hooks",
    description="將模板的 Hooks 安裝到 workspace 的 user scope"
)
async def install_hooks(
    workspace_id: str,
    request: HooksInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> HooksInstallResponse:
    """安裝 Hooks"""
    try:
        success = await service.install_hooks(workspace_id, request)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to install hooks"
            )

        return HooksInstallResponse(
            success=True,
            message="成功安裝 hooks 配置",
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
    summary="安裝 Scripts",
    description="將模板的 Scripts 複製到 workspace 的 /scripts/{templateName}/ 目錄"
)
async def install_scripts(
    workspace_id: str,
    request: ScriptsInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> ScriptsInstallResponse:
    """安裝 Scripts"""
    try:
        success, results, target_path, total_size = await service.install_scripts(
            workspace_id, request
        )

        total = len(request.scripts)
        message = f"成功安裝 {total} 個 scripts 到 {target_path}/"
        if results.failed:
            message = f"安裝 scripts: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="安裝 Skills",
    description="將模板的 Skills 複製到 workspace 對應 CLI 的 project scope 目錄"
)
async def install_skills(
    workspace_id: str,
    request: SkillsInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> SkillsInstallResponse:
    """安裝 Skills 到 workspace project scope。"""
    try:
        success, results, target_path, total_size = await service.install_skills(
            workspace_id, request
        )

        total = len(request.skills)
        message = f"成功安裝 {total} 個 skills 到 {target_path}/"
        if results.failed:
            message = f"安裝 skills: {len(results.created)} 新建, {len(results.updated)} 更新, {len(results.failed)} 失敗"

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
    summary="批次安裝模板配置",
    description="一次性安裝模板的所有配置（Claude.md, Slash Commands, Subagents, MCP, Hooks, Scripts, Skills）"
)
async def install_template(
    workspace_id: str,
    request: TemplateInstallRequest,
    service: Annotated[TemplateInstallService, Depends(get_template_install_service)]
) -> TemplateInstallResponse:
    """批次安裝模板配置"""
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

        message = "模板安裝完成" if overall_success else "模板安裝完成（部分失敗）"

        if request.initCommands and request.initCommands.strip():
            try:
                logger.info(f"開始執行模板初始化指令: {request.templateName}")
                success, stdout, stderr = await service.execute_init_commands(
                    workspace_id, request.initCommands
                )
                if not success:
                    redacted = (stderr or "").strip()
                    redacted_msg = redacted[:200] + ("..." if len(redacted) > 200 else "")
                    logger.warning(
                        "模板初始化指令執行失敗 (workspace=%s, template=%s): %s",
                        workspace_id,
                        request.templateId,
                        redacted_msg,
                    )
                    overall_success = False
                    message = "模板安裝完成（初始化指令失敗）"
                else:
                    logger.info(
                        "模板初始化指令執行成功 (workspace=%s, template=%s, stdout_length=%d)",
                        workspace_id,
                        request.templateId,
                        len(stdout or ""),
                    )
            except Exception as e:
                logger.error(f"Failed to execute init commands in batch: {e}")
                overall_success = False
                message = "模板安裝完成（初始化指令失敗）"

        return TemplateInstallResponse(
            success=overall_success,
            message=message,
            templateId=request.templateId,
            templateName=request.templateName,
            results=results,
        )

    # 安裝 Claude.md
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

    # 安裝 Slash Commands
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

    # 安裝 Subagents
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

    # 安裝 Output Styles
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

    # 安裝 MCP Servers
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

    # 安裝 Hooks
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

    # 安裝 Scripts
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

    # 安裝 Skills
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

    message = "模板安裝完成" if overall_success else "模板安裝完成（部分失敗）"

    # 執行初始化指令（在所有配置安裝完成後）
    if request.initCommands and request.initCommands.strip():
        try:
            logger.info(f"開始執行模板初始化指令: {request.templateName}")
            success, stdout, stderr = await service.execute_init_commands(
                workspace_id, request.initCommands
            )
            if not success:
                redacted = (stderr or "").strip()
                redacted_msg = redacted[:200] + ("..." if len(redacted) > 200 else "")
                logger.warning(
                    "初始化指令執行失敗，但不影響模板安裝 (workspace=%s, stderr=%s)",
                    workspace_id,
                    redacted_msg,
                )
                # 初始化指令失敗不影響整體安裝結果
                # 但會在 message 中提示（僅在未已有錯誤訊息時覆寫）
                if overall_success:
                    message = "模板安裝完成，但初始化指令執行失敗"
            else:
                logger.info(f"初始化指令執行成功: {request.templateName}")
        except Exception as e:
            logger.error(f"執行初始化指令時發生異常: {e}")
            # 不影響整體安裝結果

    return TemplateInstallResponse(
        success=overall_success,
        message=message,
        templateId=request.templateId,
        templateName=request.templateName,
        results=results
    )


__all__ = ["router"]
