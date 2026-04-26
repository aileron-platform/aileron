"""Template installation service - Install template configuration to workspace-runtime"""

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
    """Template installation failed, but is an expected error that can be explained to users."""

    def __init__(self, message: str, *, code: str = "TEMPLATE_INSTALL_FAILED", params: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class TemplateInstallService:
    """Template installation service - Responsible for installing template configuration to workspace-runtime"""

    def __init__(self, db: Session):
        self.db = db
        self.template_service = TemplateService(db)
        self.template_compiler = TemplateCompilerService(db)
        self.artifact_cache = TemplateArtifactCacheService(db)
        # Dynamically get settings to ensure correct configuration in test environment
        settings = get_settings()
        self.internal_api_token = settings.INTERNAL_API_TOKEN
        self.timeout = 60.0  # Installation may take longer time

    async def install_template_to_workspace(
        self,
        workspace_id: str,
        template_id: str
    ) -> Dict[str, Any]:
        """
    Install template to specified workspace

    Args:
        workspace_id: Workspace ID
        template_id: Template ID

    Returns:
        Installation result
    """
        logger.info(f"Begin installing template {template_id} to workspace {workspace_id}")

        # 1. Get workspace Information
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

        # 2. GetTemplateData
        template = self.template_service._get_template(template_id)
        if not template:
            raise TemplateInstallError(
                f"Template {template_id} not found",
                code="TEMPLATE_INSTALL_TEMPLATE_NOT_FOUND",
                params={"template_id": template_id},
            )

        # 3. Prepare installation data
        install_payload = await self._prepare_install_payload(template)

        # 4. Call workspace-runtime Internal API
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

        logger.info(f"Template {template_id} installation completed: {result.get('success', False)}")
        return result

    async def _prepare_install_payload(self, template: TemplateDB) -> Dict[str, Any]:
        """Prepare installation data"""
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
        """Call workspace-runtime internal API"""
        url = f"{runtime_url}/api/v1/internal/workspaces/{workspace_id}/templates/install"
        headers = {
            "Authorization": f"Bearer {self.internal_api_token}",
            "Content-Type": "application/json"
        }

        logger.debug(f"Call Runtime Install API: {url}")
        logger.debug(f"Payload keys: {list(payload.keys())}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Runtime API ResponseError: {e.response.status_code} - {e.response.text}")
                raise TemplateInstallError(
                    f"Template installation failed: runtime response {e.response.status_code}, {e.response.text}",
                    code="TEMPLATE_INSTALL_RUNTIME_HTTP_ERROR",
                    params={
                        "status_code": str(e.response.status_code),
                        "response_text": e.response.text,
                    },
                ) from e
            except httpx.RequestError as e:
                logger.error(f"Runtime API request failed: {e}")
                raise TemplateInstallError(
                    f"Cannot connect to workspace runtime: {str(e)}",
                    code="TEMPLATE_INSTALL_RUNTIME_CONNECTION_ERROR",
                ) from e

    def _get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace"""
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def _get_runtime_url(self, workspace: Workspace) -> str:
        """Get runtime URL"""
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
            f"Workspace {workspace.id} does not have an available runtime URL",
            code="TEMPLATE_INSTALL_RUNTIME_URL_MISSING",
            params={"workspace_id": workspace.id},
        )


__all__ = ["TemplateInstallService"]
