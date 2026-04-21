"""模板安裝服務 - 將模板配置安裝到 workspace-runtime"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Template as TemplateDB, Workspace
from app.models.template import TemplateFileNode
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


def _flatten_template_file_nodes(nodes: list[TemplateFileNode]) -> list[TemplateFileNode]:
    """將模板檔案樹展平成檔案節點列表。"""
    flattened: list[TemplateFileNode] = []

    for node in nodes:
        if node.type == "file":
            flattened.append(node)
            continue
        if node.children:
            flattened.extend(_flatten_template_file_nodes(node.children))

    return flattened


class TemplateInstallError(Exception):
    """模板安裝失敗，但屬於可預期且可向使用者說明的錯誤。"""

    def __init__(self, message: str, *, code: str = "TEMPLATE_INSTALL_FAILED", params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class TemplateInstallService:
    """模板安裝服務 - 負責將模板配置安裝到 workspace-runtime"""

    def __init__(self, db: Session):
        self.db = db
        self.template_service = TemplateService(db)
        # 動態獲取 settings，確保在測試環境中使用正確的配置
        settings = get_settings()
        self.internal_api_token = settings.INTERNAL_API_TOKEN
        self.timeout = 60.0  # 安裝可能需要較長時間

    async def install_template_to_workspace(
        self,
        workspace_id: str,
        template_id: str
    ) -> Dict[str, Any]:
        """
        將模板安裝到指定的 workspace

        Args:
            workspace_id: Workspace ID
            template_id: Template ID

        Returns:
            安裝結果
        """
        logger.info(f"開始安裝模板 {template_id} 到 workspace {workspace_id}")

        # 1. 取得 workspace 資訊
        workspace = self._get_workspace(workspace_id)
        if not workspace:
            raise TemplateInstallError(
                f"Workspace {workspace_id} not found",
                code="TEMPLATE_INSTALL_WORKSPACE_NOT_FOUND",
                params={"workspace_id": workspace_id},
            )

        if workspace.runtime_status != "running":
            raise TemplateInstallError(
                f"Workspace {workspace_id} is not running",
                code="TEMPLATE_INSTALL_WORKSPACE_NOT_RUNNING",
                params={"workspace_id": workspace_id},
            )

        # 2. 取得模板資料
        template = self.template_service._get_template(template_id)
        if not template:
            raise TemplateInstallError(
                f"Template {template_id} not found",
                code="TEMPLATE_INSTALL_TEMPLATE_NOT_FOUND",
                params={"template_id": template_id},
            )

        # 3. 準備安裝資料
        install_payload = await self._prepare_install_payload(template)

        # 4. 呼叫 workspace-runtime Internal API
        runtime_url = self._get_runtime_url(workspace)
        result = await self._call_runtime_install_api(
            runtime_url,
            workspace_id,
            install_payload
        )

        logger.info(f"模板 {template_id} 安裝完成: {result.get('success', False)}")
        return result

    async def _prepare_install_payload(self, template: TemplateDB) -> Dict[str, Any]:
        """準備安裝資料"""
        payload = {
            "templateId": template.id,
            "templateName": template.name,
            "cliType": template.cli_type,
        }

        # 初始化指令
        if template.init_commands:
            payload["initCommands"] = template.init_commands

        # Claude.md
        claude_md = self.template_service.get_claude_md(template.id)
        if claude_md:
            payload["claudeMd"] = {"content": claude_md}

        # Slash Commands
        slash_commands = self.template_service._load_commands(template.id)
        if slash_commands:
            payload["slashCommands"] = [
                {
                    # 保留完整的檔案名稱（可能包含 namespace/）
                    "fileName": f"{cmd.fileName}.md" if not cmd.fileName.endswith('.md') else cmd.fileName,
                    "content": cmd.content
                }
                for cmd in slash_commands
            ]

        # Subagents
        subagents = self.template_service._load_agents(template.id)
        if subagents:
            payload["subagents"] = [
                {
                    "fileName": agent.fileName,
                    "content": agent.content
                }
                for agent in subagents
            ]

        # Output Styles
        output_styles = self.template_service._load_output_styles(template.id)
        if output_styles:
            payload["outputStyles"] = [
                {
                    "fileName": style.fileName,
                    "content": style.content
                }
                for style in output_styles
            ]

        # MCP Servers
        mcp_servers = self.template_service._load_mcp_servers(template.id)
        if mcp_servers:
            mcp_dict = {}
            for server in mcp_servers:
                server_config = {
                    "type": server.type or "stdio"
                }
                if server.command:
                    server_config["command"] = server.command
                if server.args:
                    server_config["args"] = server.args
                if server.env:
                    server_config["env"] = server.env
                if server.url:
                    server_config["url"] = server.url
                if server.headers:
                    server_config["headers"] = server.headers

                mcp_dict[server.name] = server_config

            payload["mcpServers"] = mcp_dict

        # Hooks
        hooks = self.template_service._load_hooks(template.id)
        if hooks:
            hooks_dict = {}
            for hook in hooks:
                if hook.event not in hooks_dict:
                    hooks_dict[hook.event] = []

                hook_rule = {
                    "matcher": hook.matcher or "*"
                }

                # 建立 hooks 列表
                hook_actions = []
                if hook.action:
                    hook_action = {
                        "type": hook.action
                    }
                    if hook.command:
                        hook_action["command"] = hook.command
                    if hook.timeout:
                        hook_action["timeout"] = hook.timeout
                    hook_actions.append(hook_action)

                hook_rule["hooks"] = hook_actions
                hooks_dict[hook.event].append(hook_rule)

            payload["hooks"] = hooks_dict

        # Scripts
        scripts = self.template_service._load_files(template.id)
        if scripts:
            scripts_list = []
            for script in scripts:
                if script.type == "file" and script.content:
                    script_item = {
                        "path": script.path,
                        "content": script.content,
                        "executable": script.path.endswith(('.sh', '.bash', '.zsh', '.py'))
                    }
                    scripts_list.append(script_item)

            if scripts_list:
                payload["scripts"] = scripts_list

        # Skills
        skills = _flatten_template_file_nodes(self.template_service.file_service.load_skills(template.id))
        if skills:
            skills_list = []
            for skill in skills:
                if skill.type == "file" and skill.content is not None:
                    skills_list.append({
                        "path": skill.path,
                        "content": skill.content,
                    })

            if skills_list:
                payload["skills"] = skills_list

        return payload

    async def _call_runtime_install_api(
        self,
        runtime_url: str,
        workspace_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """呼叫 workspace-runtime 的 Internal API"""
        url = f"{runtime_url}/api/v1/internal/workspaces/{workspace_id}/templates/install"
        headers = {
            "Authorization": f"Bearer {self.internal_api_token}",
            "Content-Type": "application/json"
        }

        logger.debug(f"呼叫 Runtime Install API: {url}")
        logger.debug(f"Payload keys: {list(payload.keys())}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Runtime API 回應錯誤: {e.response.status_code} - {e.response.text}")
                raise TemplateInstallError(
                    f"安裝模板失敗：Runtime 回應 {e.response.status_code}，{e.response.text}",
                    code="TEMPLATE_INSTALL_RUNTIME_HTTP_ERROR",
                    params={
                        "status_code": str(e.response.status_code),
                        "response_text": e.response.text,
                    },
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Runtime API 請求失敗: {e}")
                raise TemplateInstallError(
                    f"無法連線到 Workspace Runtime：{str(e)}",
                    code="TEMPLATE_INSTALL_RUNTIME_CONNECTION_ERROR",
                ) from e

    def _get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """取得 workspace"""
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def _get_runtime_url(self, workspace: Workspace) -> str:
        """取得 runtime URL"""
        settings = get_settings()
        is_kubernetes = (
            settings.RUNTIME_PROVISIONER == "kubernetes"
            or workspace.provisioner == "kubernetes"
        )

        if is_kubernetes and workspace.runtime_internal_url:
            logger.info(
                "Kubernetes mode: Using internal URL: %s (external=%s)",
                workspace.runtime_internal_url,
                workspace.runtime_external_url,
            )
            return workspace.runtime_internal_url.rstrip('/')

        if workspace.runtime_internal_url:
            logger.info(
                "Using internal runtime URL: %s (provisioner=%s)",
                workspace.runtime_internal_url,
                workspace.provisioner,
            )
            return workspace.runtime_internal_url.rstrip('/')

        if workspace.runtime_external_url:
            logger.info(
                "Internal runtime URL unavailable, fallback to external URL: %s",
                workspace.runtime_external_url,
            )
            return workspace.runtime_external_url.rstrip('/')

        raise TemplateInstallError(
            f"Workspace {workspace.id} 沒有可用的 runtime URL",
            code="TEMPLATE_INSTALL_RUNTIME_URL_MISSING",
            params={"workspace_id": workspace.id},
        )


__all__ = ["TemplateInstallService"]
