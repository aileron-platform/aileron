"""Template Install Service - 模板安裝服務"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.mcp import McpService
from app.modules.claude_code.mcp.models import McpImportRequest, McpServerConfig
from app.modules.claude_code.hooks import HookService
from app.modules.claude_code.hooks.models import (
    HookImportRequest,
    HookImportMode,
    HookScopeDocument,
    HookRule,
    HookAction,
)
from app.modules.claude_code.claude_md import ClaudeMdService
from app.modules.claude_code.claude_md.models import (
    ClaudeMdScope,
    ClaudeMdUpdateRequest,
)
from app.modules.cli_settings.hooks.config import CliHookScope, HookTool, get_hook_tool_config
from app.modules.cli_settings.hooks.models import (
    CliHookImportMode,
    CliHookImportRequest,
    CliHookScopeDocument,
)
from app.modules.cli_settings.hooks.service import CliHookService
from app.modules.cli_settings.mcp.models import (
    CliMcpImportRequest,
    CliMcpScope,
    CliMcpServerConfig,
)
from app.modules.cli_settings.mcp.service import CliMcpService, McpTool, get_mcp_tool_config
from app.modules.cli_settings.skills.config import SkillTool, get_skill_config
from app.config.settings import get_workspace_path

from .template_install_models import (
    ClaudeMdInstallRequest,
    HooksInstallRequest,
    InstallResults,
    InstallPlanRequest,
    McpInstallRequest,
    OutputStyleInstallRequest,
    SkillsInstallRequest,
    ScriptsInstallRequest,
    SlashCommandInstallRequest,
    SubagentInstallRequest,
)

logger = logging.getLogger(__name__)


TARGET_INSTALL_MATRIX: Dict[str, Dict[str, Any]] = {
    "claude-code": {
        "agents_md_file": "CLAUDE.md",
        "output_style_mode": "native",
        "hooks_mode": "native",
        "mcp_mode": "native",
    },
    "codex": {
        "agents_md_file": "AGENTS.md",
        "output_style_mode": "inject-agents-md",
        "hooks_mode": "skip",
        "mcp_mode": "cli-settings",
    },
    "gemini": {
        "agents_md_file": "GEMINI.md",
        "output_style_mode": "inject-agents-md",
        "hooks_mode": "cli-settings",
        "mcp_mode": "cli-settings",
    },
    "opencode": {
        "agents_md_file": "AGENTS.md",
        "output_style_mode": "inject-agents-md",
        "hooks_mode": "skip",
        "mcp_mode": "cli-settings",
    },
}


class TemplateInstallService:
    """模板安裝服務 - 處理模板配置安裝到 user scope"""

    def __init__(
        self,
        mcp_service: McpService | None = None,
        hook_service: HookService | None = None,
        claude_md_service: ClaudeMdService | None = None,
    ):
        # 注入 Claude Code 服務（用於 MCP、Hooks、Claude.md）
        self.mcp_service = mcp_service or McpService()
        self.hook_service = hook_service or HookService()
        self.claude_md_service = claude_md_service or ClaudeMdService()

        # 使用環境變數或預設路徑（用於 Slash Commands、Subagents）
        self.home_dir = Path(os.environ.get("HOME", "/home/developer"))
        self.claude_dir = self.home_dir / ".claude"

        # Scripts 目錄：優先使用 /scripts（容器掛載點），否則使用環境變數或 home 目錄
        scripts_env = os.environ.get("SCRIPTS_DIR")
        if scripts_env:
            self.scripts_base_dir = Path(scripts_env)
        elif Path("/scripts").exists():
            # 容器環境使用 /scripts 掛載點
            self.scripts_base_dir = Path("/scripts")
        else:
            # 開發環境使用 home 目錄下的 scripts
            self.scripts_base_dir = self.home_dir / "scripts"

        # 確保基礎目錄存在
        try:
            self.claude_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
            self.scripts_base_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
        except PermissionError as e:
            logger.warning(f"無法建立目錄，將使用臨時目錄: {e}")
            # 如果沒有權限，使用臨時目錄
            import tempfile
            temp_base = Path(tempfile.gettempdir()) / "workspace-runtime"
            self.claude_dir = temp_base / ".claude"
            self.scripts_base_dir = temp_base / "scripts"
            self.claude_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
            self.scripts_base_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

    @staticmethod
    def _is_safe_relative_path(relative_path: str) -> bool:
        return bool(relative_path) and not relative_path.startswith("/") and ".." not in relative_path.split("/")

    @staticmethod
    def _classify_compiled_file(path: str) -> str:
        normalized = path.strip("/")
        name = Path(normalized).name
        if name in {"CLAUDE.md", "AGENTS.md", "GEMINI.md"}:
            return "claudeMd"
        if "/commands/" in normalized or "/prompts/" in normalized:
            return "slashCommands"
        if "/agents/" in normalized:
            return "subagents"
        if "/output-styles/" in normalized:
            return "outputStyles"
        return "files"

    @staticmethod
    def _get_target_strategy(cli_type: str) -> Dict[str, Any]:
        normalized = cli_type.strip().lower()
        if normalized not in TARGET_INSTALL_MATRIX:
            raise ValueError(f"Unsupported cli type for template installation: {cli_type}")
        return TARGET_INSTALL_MATRIX[normalized]

    async def install_compiled_files(
        self,
        workspace_id: str,
        request: InstallPlanRequest,
    ) -> Dict[str, InstallResults]:
        """安裝 compiled install plan 中的檔案到 workspace project scope。"""
        workspace_root = Path(get_workspace_path())
        workspace_root.mkdir(mode=0o755, parents=True, exist_ok=True)

        results_by_category: Dict[str, InstallResults] = {
            "claudeMd": InstallResults(),
            "slashCommands": InstallResults(),
            "subagents": InstallResults(),
            "outputStyles": InstallResults(),
            "files": InstallResults(),
        }

        for compiled in request.files:
            category = self._classify_compiled_file(compiled.path)
            category_results = results_by_category[category]
            try:
                if not self._is_safe_relative_path(compiled.path):
                    logger.warning("Invalid compiled file path: %s", compiled.path)
                    category_results.failed.append(compiled.path)
                    continue

                file_path = (workspace_root / compiled.path).resolve()
                if workspace_root.resolve() not in file_path.parents and file_path != workspace_root.resolve():
                    logger.warning("Compiled file path escaped workspace root: %s", compiled.path)
                    category_results.failed.append(compiled.path)
                    continue

                is_new = not file_path.exists()
                file_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                file_path.write_text(compiled.content, encoding="utf-8")
                file_path.chmod(0o644)

                if is_new:
                    category_results.created.append(compiled.path)
                else:
                    category_results.updated.append(compiled.path)
            except Exception as e:
                logger.error("Failed to install compiled file %s: %s", compiled.path, e)
                category_results.failed.append(compiled.path)

        return results_by_category
    # ============ Slash Commands ============

    async def install_slash_commands(
        self, workspace_id: str, request: SlashCommandInstallRequest
    ) -> Tuple[bool, InstallResults]:
        """安裝 Slash Commands 到 USER scope (~/.claude/commands/)

        根據檔案名稱決定安裝位置：
        - 如果檔案名稱包含 '/'，則視為有 namespace，保留完整路徑結構
        - 否則直接安裝到 commands 目錄下

        範例：
        - "command.md" -> ~/.claude/commands/command.md
        - "deploy/build.md" -> ~/.claude/commands/deploy/build.md
        - "git/hooks/pre-commit.md" -> ~/.claude/commands/git/hooks/pre-commit.md
        """
        results = InstallResults()
        commands_dir = self.claude_dir / "commands"
        commands_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        for cmd in request.commands:
            try:
                # 直接使用檔案名稱（可能包含路徑）
                file_path = commands_dir / cmd.fileName

                # 如果檔案名稱包含路徑，確保父目錄存在
                if "/" in cmd.fileName:
                    file_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

                is_new = not file_path.exists()

                # 寫入檔案（overwrite）
                file_path.write_text(cmd.content, encoding="utf-8")
                file_path.chmod(0o644)

                if is_new:
                    results.created.append(cmd.fileName)
                else:
                    results.updated.append(cmd.fileName)

                logger.info(
                    f"{'Created' if is_new else 'Updated'} slash command: {cmd.fileName}"
                )

            except Exception as e:
                logger.error(f"Failed to install slash command {cmd.fileName}: {e}")
                results.failed.append(cmd.fileName)

        success = len(results.failed) == 0
        return success, results

    # ============ Subagents ============

    async def install_subagents(
        self, workspace_id: str, request: SubagentInstallRequest
    ) -> Tuple[bool, InstallResults]:
        """安裝 Subagents 到 user scope"""
        results = InstallResults()
        agents_dir = self.claude_dir / "agents" / "user"
        agents_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        for agent in request.subagents:
            try:
                file_path = agents_dir / agent.fileName
                is_new = not file_path.exists()

                # 寫入檔案（overwrite）
                file_path.write_text(agent.content, encoding="utf-8")
                file_path.chmod(0o644)

                if is_new:
                    results.created.append(agent.fileName)
                else:
                    results.updated.append(agent.fileName)

                logger.info(
                    f"{'Created' if is_new else 'Updated'} subagent: {agent.fileName}"
                )

            except Exception as e:
                logger.error(f"Failed to install subagent {agent.fileName}: {e}")
                results.failed.append(agent.fileName)

        success = len(results.failed) == 0
        return success, results

    # ============ Output Styles ============

    async def install_output_styles(
        self, workspace_id: str, request: "OutputStyleInstallRequest"
    ) -> Tuple[bool, InstallResults]:
        """安裝 Output Styles 到 user scope"""
        results = InstallResults()
        # Output Styles 安裝到 ~/.claude/output-styles/ (user scope)
        styles_dir = self.claude_dir / "output-styles"
        styles_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        for style in request.outputStyles:
            try:
                file_path = styles_dir / style.fileName
                is_new = not file_path.exists()

                # 寫入檔案（overwrite）
                file_path.write_text(style.content, encoding="utf-8")
                file_path.chmod(0o644)

                if is_new:
                    results.created.append(style.fileName)
                else:
                    results.updated.append(style.fileName)

                logger.info(
                    f"{'Created' if is_new else 'Updated'} output style: {style.fileName}"
                )

            except Exception as e:
                logger.error(f"Failed to install output style {style.fileName}: {e}")
                results.failed.append(style.fileName)

        success = len(results.failed) == 0
        return success, results

    # ============ Claude.md ============

    async def install_claude_md(
        self, workspace_id: str, request: ClaudeMdInstallRequest
    ) -> bool:
        """安裝 Claude.md 到 user scope - 使用 ClaudeMdService"""
        try:
            # 使用 ClaudeMdService 的 update_document 方法
            update_request = ClaudeMdUpdateRequest(
                scope=ClaudeMdScope.USER,
                content=request.content,
            )

            self.claude_md_service.update_document(workspace_id, update_request)

            logger.info("Installed Claude.md to user scope")
            return True

        except Exception as e:
            logger.error(f"Failed to install Claude.md: {e}")
            return False

    # ============ MCP Servers ============

    async def install_mcp_servers(
        self, workspace_id: str, request: McpInstallRequest
    ) -> Tuple[bool, InstallResults]:
        """安裝 MCP Servers 到 user scope - 使用 McpService

        注意：使用 USER scope 會將 MCP servers 寫入到 ~/.claude.json 的
        root.mcpServers 路徑，這樣 MCP servers 會在所有 workspace 中生效（全域）。
        """
        results = InstallResults()

        try:
            # 轉換資料模型：McpServerConfigInstall -> McpServerConfig
            mcp_servers = {}
            for name, config in request.mcpServers.items():
                mcp_servers[name] = McpServerConfig(
                    type=config.type,
                    command=config.command,
                    args=config.args,
                    env=config.env,
                    url=config.url,
                    headers=config.headers,
                )

            # 使用 McpService 的 import_servers 方法
            # 使用 USER scope 將 MCP 寫入 ~/.claude.json 的 root.mcpServers
            import_request = McpImportRequest(
                scope=DocumentScope.USER,
                mcpServers=mcp_servers,
                overwrite=True,  # 模板安裝使用覆寫模式
            )

            response = self.mcp_service.import_servers(workspace_id, import_request)

            # 轉換回應為 InstallResults
            results.created = response.created
            results.updated = response.updated
            results.failed = []  # import_servers 不會失敗，只會 skip

            logger.info(
                f"Installed MCP servers to USER scope: {len(results.created)} created, "
                f"{len(results.updated)} updated"
            )
            return True, results

        except Exception as e:
            logger.error(f"Failed to install MCP servers: {e}")
            results.failed = list(request.mcpServers.keys())
            return False, results

    # ============ Hooks ============

    async def install_hooks(
        self, workspace_id: str, request: HooksInstallRequest
    ) -> Tuple[bool, InstallResults]:
        """安裝 Hooks 到 user scope - 使用 HookService"""
        results = InstallResults()

        try:
            # 轉換資料模型：HookRuleInstall -> HookRule
            hooks_dict = {}
            for event, rules in request.hooks.items():
                hook_rules = []
                for rule in rules:
                    hook_actions = [
                        HookAction(
                            type=rule_action.type,
                            command=rule_action.command,
                            timeout=rule_action.timeout,
                        )
                        for rule_action in rule.hooks
                    ]
                    hook_rules.append(
                        HookRule(
                            matcher=rule.matcher,
                            hooks=hook_actions,
                        )
                    )
                hooks_dict[event] = hook_rules

            # 建立 HookScopeDocument
            scope_document = HookScopeDocument(
                scope=DocumentScope.USER,
                hooks=hooks_dict,
            )

            # 使用 HookService 的 import_scopes 方法
            import_request = HookImportRequest(
                mode=HookImportMode.REPLACE,  # 模板安裝使用替換模式
                scopes=[scope_document],
            )

            response = self.hook_service.import_scopes(workspace_id, import_request)

            # 轉換回應為 InstallResults
            # HookImportResponse 回傳 imported/updated/skipped
            # 我們將 imported 視為 created
            if response.imported > 0:
                results.created = [f"hooks_imported_{i}" for i in range(response.imported)]
            if response.updated > 0:
                results.updated = [f"hooks_updated_{i}" for i in range(response.updated)]
            results.failed = []

            logger.info(
                f"Installed hooks: {response.imported} imported, "
                f"{response.updated} updated"
            )
            return True, results

        except Exception as e:
            logger.error(f"Failed to install hooks: {e}")
            results.failed = list(request.hooks.keys())
            return False, results

    # ============ Scripts ============

    async def install_scripts(
        self, workspace_id: str, request: ScriptsInstallRequest
    ) -> Tuple[bool, InstallResults, str, int]:
        """
        安裝 Scripts 到 /scripts/{templateName}/

        Returns:
            Tuple[success, results, target_path, total_size]
        """
        results = InstallResults()
        template_dir = self.scripts_base_dir / request.templateName
        template_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        total_size = 0

        for script in request.scripts:
            try:
                # 安全檢查：防止路徑遍歷
                if ".." in script.path or script.path.startswith("/"):
                    logger.warning(f"Invalid script path: {script.path}")
                    results.failed.append(script.path)
                    continue

                file_path = template_dir / script.path
                is_new = not file_path.exists()

                # 建立父目錄
                file_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)

                # 寫入檔案（overwrite）
                file_path.write_text(script.content, encoding="utf-8")

                # 設定權限
                if script.executable:
                    file_path.chmod(0o755)
                else:
                    file_path.chmod(0o644)

                # 計算大小
                total_size += len(script.content.encode("utf-8"))

                if is_new:
                    results.created.append(script.path)
                else:
                    results.updated.append(script.path)

                logger.info(
                    f"{'Created' if is_new else 'Updated'} script: {script.path}"
                )

            except Exception as e:
                logger.error(f"Failed to install script {script.path}: {e}")
                results.failed.append(script.path)

        success = len(results.failed) == 0
        target_path = str(template_dir)

        return success, results, target_path, total_size

    # ============ Skills ============

    async def install_skills(
        self, workspace_id: str, request: SkillsInstallRequest
    ) -> Tuple[bool, InstallResults, str, int]:
        """安裝 Skills 到工作區 project scope。"""
        results = InstallResults()
        total_size = 0

        cli_type = (request.cliType or "claude-code").strip().lower()
        tool = self._resolve_skill_tool(cli_type)
        config = get_skill_config(tool)
        target_dir = Path(get_workspace_path()) / config.project_dot_dir / config.skill_dir_name
        target_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        for skill in request.skills:
            try:
                if ".." in skill.path or skill.path.startswith("/"):
                    logger.warning("Invalid skill path: %s", skill.path)
                    results.failed.append(skill.path)
                    continue

                file_path = target_dir / skill.path
                is_new = not file_path.exists()
                file_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                file_path.write_text(skill.content, encoding="utf-8")
                file_path.chmod(0o644)

                total_size += len(skill.content.encode("utf-8"))
                if is_new:
                    results.created.append(skill.path)
                else:
                    results.updated.append(skill.path)

                logger.info(
                    "%s skill for %s: %s",
                    "Created" if is_new else "Updated",
                    cli_type,
                    skill.path,
                )
            except Exception as e:
                logger.error("Failed to install skill %s: %s", skill.path, e)
                results.failed.append(skill.path)

        success = len(results.failed) == 0
        return success, results, str(target_dir), total_size

    async def install_target_mcp_servers(
        self,
        workspace_id: str,
        cli_type: str,
        mcp_servers: Dict[str, Dict[str, Any]],
    ) -> Tuple[bool, InstallResults]:
        """依 target CLI 安裝 MCP 設定。"""
        if not mcp_servers:
            return True, InstallResults()

        normalized = cli_type.strip().lower()
        strategy = self._get_target_strategy(normalized)
        if strategy["mcp_mode"] == "native":
            request = McpInstallRequest(mcpServers=mcp_servers)
            return await self.install_mcp_servers(workspace_id, request)

        tool_map = {
            "gemini": McpTool.GEMINI,
            "codex": McpTool.CODEX,
            "opencode": McpTool.OPENCODE,
        }
        tool = tool_map.get(normalized)
        if tool is None:
            raise ValueError(f"Unsupported cli type for MCP installation: {cli_type}")

        service = CliMcpService(get_mcp_tool_config(tool))
        import_request = CliMcpImportRequest(
            scope=CliMcpScope.PROJECT,
            mcpServers={name: CliMcpServerConfig(**config) for name, config in mcp_servers.items()},
            overwrite=True,
        )
        response = service.import_servers(workspace_id, import_request)
        return True, InstallResults(
            created=response.created,
            updated=response.updated,
            failed=[],
        )

    async def install_target_hooks(
        self,
        workspace_id: str,
        cli_type: str,
        hooks: Dict[str, List[Dict[str, Any]]],
    ) -> Tuple[bool, InstallResults]:
        """依 target CLI 安裝 hooks 設定。"""
        if not hooks:
            return True, InstallResults()

        normalized = cli_type.strip().lower()
        strategy = self._get_target_strategy(normalized)
        if strategy["hooks_mode"] == "native":
            request = HooksInstallRequest(hooks=hooks)
            return await self.install_hooks(workspace_id, request)

        if strategy["hooks_mode"] == "skip":
            logger.info("Skipping hooks installation for unsupported cli type: %s", cli_type)
            return True, InstallResults()

        service = CliHookService(get_hook_tool_config(HookTool.GEMINI))
        import_request = CliHookImportRequest(
            mode=CliHookImportMode.REPLACE,
            scopes=[
                CliHookScopeDocument(
                    scope=CliHookScope.PROJECT,
                    hooks=hooks,
                )
            ],
        )
        response = service.import_scopes(workspace_id, import_request)
        created = [f"hooks_imported_{i}" for i in range(response.imported)]
        updated = [f"hooks_updated_{i}" for i in range(response.updated)]
        return True, InstallResults(created=created, updated=updated, failed=[])

    async def install_target_output_style(
        self,
        workspace_id: str,
        cli_type: str,
        output_styles: List[Dict[str, Any]],
    ) -> Tuple[bool, InstallResults]:
        """依 target CLI 安裝或降級注入 output style。"""
        if not output_styles:
            return True, InstallResults()

        normalized = cli_type.strip().lower()
        strategy = self._get_target_strategy(normalized)

        if strategy["output_style_mode"] == "native":
            request = OutputStyleInstallRequest(outputStyles=output_styles)
            return await self.install_output_styles(workspace_id, request)

        if strategy["output_style_mode"] != "inject-agents-md":
            logger.info("Skipping output style installation for cli type: %s", cli_type)
            return True, InstallResults()

        fallback_parts = [str(item.get("content") or "").strip() for item in output_styles]
        fallback_text = "\n\n".join(part for part in fallback_parts if part)
        if not fallback_text:
            return True, InstallResults()

        workspace_root = Path(get_workspace_path())
        agents_md_path = workspace_root / strategy["agents_md_file"]
        existing = agents_md_path.read_text(encoding="utf-8") if agents_md_path.exists() else ""
        injected = (
            f"{existing.rstrip()}\n\n"
            "## Output Style\n\n"
            f"{fallback_text}\n"
        ).lstrip()
        is_new = not agents_md_path.exists()
        agents_md_path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
        agents_md_path.write_text(injected, encoding="utf-8")
        agents_md_path.chmod(0o644)

        results = InstallResults()
        if is_new:
            results.created.append(strategy["agents_md_file"])
        else:
            results.updated.append(strategy["agents_md_file"])
        return True, results

    @staticmethod
    def _resolve_skill_tool(cli_type: str) -> SkillTool:
        normalized = cli_type.strip().lower()
        if normalized == "claude-code":
            return SkillTool.CLAUDE
        if normalized == "codex":
            return SkillTool.CODEX
        if normalized == "gemini":
            return SkillTool.GEMINI
        if normalized == "opencode":
            return SkillTool.OPENCODE
        raise ValueError(f"Unsupported cli type for skills installation: {cli_type}")

    # ============ Init Commands ============

    async def execute_init_commands(
        self, workspace_id: str, init_commands: str
    ) -> Tuple[bool, str, str]:
        """
        執行初始化指令

        Args:
            workspace_id: Workspace ID
            init_commands: 初始化指令（多行 bash 指令）

        Returns:
            Tuple[success, stdout, stderr]
        """
        if not init_commands or not init_commands.strip():
            logger.info("沒有初始化指令需要執行")
            return True, "", ""

        try:
            command_lines = len([line for line in init_commands.splitlines() if line.strip()])
            logger.info(
                "開始執行初始化指令 (workspace: %s, commands=%d)",
                workspace_id,
                command_lines,
            )

            # 在 home 目錄下執行指令
            process = await asyncio.create_subprocess_shell(
                init_commands,
                cwd=str(self.home_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=300,  # 5 分鐘超時
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.communicate()
                error_msg = "初始化指令執行超時（超過 5 分鐘）"
                logger.error(f"{error_msg} (workspace: {workspace_id})")
                return False, "", error_msg

            stdout = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
            stderr = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
            success = process.returncode == 0

            if success:
                logger.info(
                    "初始化指令執行成功 (workspace: %s, commands=%d)",
                    workspace_id,
                    command_lines,
                )
            else:
                logger.error(
                    "初始化指令執行失敗 (workspace: %s, returncode=%s)",
                    workspace_id,
                    process.returncode,
                )

            return success, stdout, stderr

        except Exception as e:
            error_msg = f"執行初始化指令時發生錯誤: {e}"
            logger.error(f"{error_msg} (workspace: {workspace_id})")
            return False, "", error_msg


__all__ = ["TemplateInstallService"]
