"""模板安裝服務 - 將模板配置安裝到 workspace-runtime"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Template as TemplateDB, Workspace
from app.services.template_compiler_service import TemplateCompilerService
from app.services.template_artifact_cache_service import TemplateArtifactCacheService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


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
        self.template_compiler = TemplateCompilerService(db)
        self.artifact_cache = TemplateArtifactCacheService(db)
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

        if result.get("success"):
            compiled_plan = self.template_compiler.compile_template(template.id, template.cli_type)
            self.artifact_cache.record_install_manifest(
                workspace_id=workspace_id,
                template_id=template.id,
                target=template.cli_type,
                plan=compiled_plan,
            )

        logger.info(f"模板 {template_id} 安裝完成: {result.get('success', False)}")
        return result

    async def _prepare_install_payload(self, template: TemplateDB) -> Dict[str, Any]:
        """準備安裝資料"""
        return await self._prepare_canonical_install_payload(template)

    async def _prepare_canonical_install_payload(self, template: TemplateDB) -> Dict[str, Any]:
        install_plan = self.template_compiler.compile_template(template.id, template.cli_type)
        payload = {
            "templateId": template.id,
            "templateName": template.name,
            "cliType": template.cli_type,
            "installPlan": install_plan.model_dump(by_alias=True, mode="json"),
        }
        if template.init_commands:
            payload["initCommands"] = template.init_commands

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
