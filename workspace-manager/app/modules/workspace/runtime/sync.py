"""Runtime synchronization service - Responsible for syncing settings to workspace-runtime"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Dict, List

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.modules.workspace.capabilities import (
    WorkspaceCapabilities,
    build_capabilities_from_settings,
)
from app.modules.settings.models import UserSettings
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
)
from app.modules.workspace.runtime.command_auth import runtime_command_headers

logger = logging.getLogger(__name__)


class RuntimeCapabilitiesSyncError(RuntimeError):
    """A ready Runtime generation could not accept its capabilities snapshot."""

    code = "RUNTIME_CAPABILITIES_SYNC_FAILED"


class RuntimeSyncService:
    """Runtime synchronization service"""

    def __init__(self, db: Session):
        self.db = db
        self.timeout = 30.0

    def _runtime_headers(
        self,
        workspace_id: str,
        *,
        runtime_instance_id: str | None = None,
    ) -> dict[str, str]:
        if runtime_instance_id is None:
            workspace = self.db.get(db_models.Workspace, workspace_id)
            runtime_instance_id = getattr(workspace, "runtime_instance_id", None)
        if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
            raise RuntimeError("Runtime instance identity is unavailable")
        return runtime_command_headers(
            workspace_id=workspace_id,
            runtime_instance_id=runtime_instance_id,
            action="settings.sync",
        )

    async def sync_settings_to_runtimes(
        self, user_id: str, changes: dict
    ) -> Dict[str, any]:
        """Sync settings to all related workspace-runtimes"""
        logger.info(
            f"Begin syncing settings to runtime, user_id: {user_id}, changes: {list(changes.keys())}"
        )

        # Get all workspace-runtimes for user
        runtimes = await self._get_user_workspace_runtimes(user_id)

        if not runtimes:
            logger.warning(f"No workspace-runtime found for user {user_id}")
            return {
                "success": True,
                "synced_runtimes": 0,
                "total_tasks": 0,
                "results": [],
            }

        # Concurrently call all runtimes
        tasks = []
        for runtime in runtimes:
            runtime_tasks = []

            if "ssh" in changes:
                runtime_tasks.append(
                    self._sync_ssh_keys(
                        runtime["url"], changes["ssh"], runtime["workspace_id"]
                    )
                )

            if "claudeCode" in changes:
                runtime_tasks.append(
                    self._sync_claude_code(
                        runtime["url"], changes["claudeCode"], runtime["workspace_id"]
                    )
                )

            if "codex" in changes:
                runtime_tasks.append(
                    self._sync_codex(
                        runtime["url"], changes["codex"], runtime["workspace_id"]
                    )
                )

            if "capabilities" in changes:
                self._store_workspace_capabilities(
                    runtime["workspace_id"],
                    changes["capabilities"],
                )
                runtime_tasks.append(
                    self._sync_capabilities(
                        runtime["url"],
                        self._normalize_capabilities(changes["capabilities"]),
                        runtime["workspace_id"],
                    )
                )

            if "git" in changes:
                runtime_tasks.append(
                    self._sync_git_settings(
                        runtime["url"], changes["git"], runtime["workspace_id"]
                    )
                )

            # Combine all tasks from each runtime
            if runtime_tasks:
                tasks.extend(runtime_tasks)

        if not tasks:
            logger.info("No changes to sync")
            return {
                "success": True,
                "synced_runtimes": len(runtimes),
                "total_tasks": 0,
                "results": [],
            }

        # Wait for all syncs to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze results
        success_count = 0
        error_count = 0
        detailed_results = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sync task {i} failed: {result}")
                error_count += 1
                detailed_results.append(
                    {"task_index": i, "success": False, "error": str(result)}
                )
            else:
                logger.info(f"Sync task {i} succeeded: {result}")
                success_count += 1
                detailed_results.append(
                    {"task_index": i, "success": True, "result": result}
                )

        return {
            "success": error_count == 0,
            "synced_runtimes": len(runtimes),
            "total_tasks": len(tasks),
            "success_count": success_count,
            "error_count": error_count,
            "results": detailed_results,
        }

    async def _get_running_runtimes(self) -> List[Dict[str, str]]:
        """Get all running workspace-runtime information"""
        # Query all running workspaces
        stmt = select(db_models.Workspace).where(
            db_models.Workspace.runtime_status == "running"
        )
        workspaces = self.db.execute(stmt).scalars().all()

        runtimes = []
        for workspace in workspaces:
            runtime_url = workspace.runtime_internal_url
            if runtime_url:
                runtimes.append(
                    {
                        "workspace_id": workspace.id,
                        "workspace_name": workspace.name,
                        "url": runtime_url,
                    }
                )

        logger.info(f"Found {len(runtimes)} running workspace-runtimes")
        return runtimes

    async def _get_user_workspace_runtimes(self, user_id: str) -> List[Dict[str, str]]:
        """Get all workspace-runtime information for user"""
        # Query all workspaces for user
        stmt = (
            select(db_models.Workspace)
            .where(db_models.Workspace.owner_id == user_id)
            .where(db_models.Workspace.runtime_status == "running")
        )
        workspaces = self.db.execute(stmt).scalars().all()

        runtimes = []
        for workspace in workspaces:
            runtime_url = workspace.runtime_internal_url
            if runtime_url:
                runtimes.append(
                    {
                        "workspace_id": workspace.id,
                        "workspace_name": workspace.name,
                        "url": runtime_url,
                    }
                )

        logger.info(f"Found {len(runtimes)} running workspace-runtimes")
        return runtimes

    async def _sync_ssh_keys(
        self, runtime_url: str, ssh_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync SSH keys to specified runtime"""
        url = f"{runtime_url}/api/v1/internal/settings/ssh-keys"
        headers = self._runtime_headers(workspace_id)

        payload = {
            "privateKey": ssh_data.get("privateKey"),
            "publicKey": ssh_data.get("publicKey"),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"SSH keys sync succeeded - workspace: {workspace_id}")
            return {
                "type": "ssh_keys",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
            }

        except Exception as e:
            logger.error(
                f"SSH keys sync failed - workspace: {workspace_id}, error: {e}"
            )
            raise Exception(f"SSH sync failed for {workspace_id}: {e}")

    async def _sync_claude_code(
        self, runtime_url: str, claude_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync Claude Code settings to specified runtime"""
        url = f"{runtime_url}/api/v1/internal/settings/claude-code"
        headers = self._runtime_headers(workspace_id)

        payload = {
            "authMethod": claude_data.get("authMethod"),
            "subscriptionAccessToken": claude_data.get("subscriptionAccessToken"),
            "subscriptionRefreshToken": claude_data.get("subscriptionRefreshToken"),
            "subscriptionExpiresAt": claude_data.get("subscriptionExpiresAt"),
            "oauthAccount": claude_data.get("oauthAccount"),
            "apiKey": claude_data.get("authKey"),
            "model": claude_data.get("model"),
            "environmentVariables": claude_data.get("environmentVariables", []),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info(
                    "Claude Code sync payload prepared - workspace: %s auth_method=%s model=%s env_count=%s has_oauth_account=%s has_subscription_token=%s",
                    workspace_id,
                    payload.get("authMethod"),
                    payload.get("model"),
                    len(payload["environmentVariables"]),
                    bool(payload.get("oauthAccount")),
                    bool(payload.get("subscriptionAccessToken")),
                )
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Claude Code sync succeeded - workspace: {workspace_id}")
            return {
                "type": "claude_code",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
            }

        except Exception as e:
            logger.error(
                f"Claude Code sync failed - workspace: {workspace_id}, error: {e}"
            )
            raise Exception(f"Claude Code sync failed for {workspace_id}: {e}")

    async def _sync_codex(
        self, runtime_url: str, codex_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync Codex settings to specified runtime"""
        url = f"{runtime_url}/api/v1/internal/settings/codex"
        headers = self._runtime_headers(workspace_id)

        is_not_connected = codex_data.get("loginStatus") == "notConnected"
        payload = {
            "authMethod": codex_data.get("authMethod"),
            "loginStatus": codex_data.get("loginStatus"),
            "account": codex_data.get("account"),
            "model": codex_data.get("model"),
            "authFlow": codex_data.get("authFlow"),
            "cliState": None if is_not_connected else codex_data.get("cliState"),
            "environmentVariables": codex_data.get("environmentVariables", []),
            "clearAuth": is_not_connected,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Codex sync succeeded - workspace: {workspace_id}")
            return {
                "type": "codex",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
            }

        except Exception as e:
            logger.error(f"Codex sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Codex sync failed for {workspace_id}: {e}")

    async def sync_running_runtime_capabilities(self) -> Dict[str, int]:
        """Push each running workspace capability snapshot once during startup."""
        runtimes = await self._get_running_runtimes()
        synced = 0
        failed = 0

        for runtime in runtimes:
            workspace_id = runtime["workspace_id"]
            try:
                capabilities = self._normalize_capabilities(
                    self.resolve_workspace_capabilities(workspace_id)
                )
                result = await self._sync_capabilities(
                    runtime["url"],
                    capabilities,
                    workspace_id,
                )
                if result.get("success"):
                    synced += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Startup capabilities sync failed - workspace: %s, error: %s",
                    workspace_id,
                    exc,
                )

        return {"synced": synced, "failed": failed}

    async def sync_capabilities_to_runtime_url(
        self,
        workspace_id: str,
        runtime_url: str,
        capabilities: dict | WorkspaceCapabilities,
    ) -> Dict[str, any]:
        """Sync capabilities snapshot to an already-resolved runtime URL."""
        return await self._sync_capabilities(
            runtime_url,
            self._normalize_capabilities(capabilities),
            workspace_id,
        )

    def sync_capabilities_to_runtime_generation(
        self,
        workspace_id: str,
        runtime_url: str,
        runtime_instance_id: str,
        capabilities: dict | WorkspaceCapabilities,
    ) -> Dict[str, any]:
        """Synchronously gate one ready generation on its capabilities snapshot."""

        url, headers, payload = self._capabilities_request(
            workspace_id=workspace_id,
            runtime_url=runtime_url,
            runtime_instance_id=runtime_instance_id,
            capabilities=self._normalize_capabilities(capabilities),
        )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
        except Exception as exc:
            logger.error(
                "Capabilities sync failed - workspace: %s, error: %s",
                workspace_id,
                exc,
            )
            raise RuntimeCapabilitiesSyncError(
                f"Capabilities sync failed for {workspace_id}: {exc}"
            ) from exc

        return self._capabilities_success_result(
            workspace_id=workspace_id,
            runtime_url=runtime_url,
            response=result,
        )

    async def _sync_capabilities(
        self, runtime_url: str, capabilities: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync workspace capabilities snapshot to specified runtime."""
        url, headers, payload = self._capabilities_request(
            workspace_id=workspace_id,
            runtime_url=runtime_url,
            runtime_instance_id=None,
            capabilities=capabilities,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            return self._capabilities_success_result(
                workspace_id=workspace_id,
                runtime_url=runtime_url,
                response=result,
            )

        except Exception as exc:
            logger.error(
                "Capabilities sync failed - workspace: %s, error: %s",
                workspace_id,
                exc,
            )
            raise RuntimeCapabilitiesSyncError(
                f"Capabilities sync failed for {workspace_id}: {exc}"
            ) from exc

    def resolve_workspace_capabilities(
        self,
        workspace_id: str,
    ) -> WorkspaceCapabilities:
        """Resolve the persisted snapshot or the owner's current model settings."""

        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace and workspace.agentic_capabilities is not None:
            return WorkspaceCapabilities.model_validate(workspace.agentic_capabilities)
        if workspace:
            from app.modules.settings.user_settings import SettingsService

            owner_settings = SettingsService(self.db).get_settings(workspace.owner_id)
            if owner_settings is not None:
                return build_capabilities_from_settings(owner_settings)
        return build_capabilities_from_settings(UserSettings())

    def _capabilities_request(
        self,
        *,
        workspace_id: str,
        runtime_url: str,
        runtime_instance_id: str | None,
        capabilities: dict,
    ) -> tuple[str, dict[str, str], dict]:
        return (
            f"{runtime_url}/api/v1/internal/settings/capabilities",
            self._runtime_headers(
                workspace_id,
                runtime_instance_id=runtime_instance_id,
            ),
            {"workspace_id": workspace_id, "capabilities": capabilities},
        )

    @staticmethod
    def _capabilities_success_result(
        *,
        workspace_id: str,
        runtime_url: str,
        response: dict,
    ) -> Dict[str, any]:
        logger.info("Capabilities sync succeeded - workspace: %s", workspace_id)
        return {
            "type": "capabilities",
            "workspace_id": workspace_id,
            "runtime_url": runtime_url,
            "success": True,
            "response": response,
        }

    def _store_workspace_capabilities(
        self,
        workspace_id: str,
        capabilities: dict | WorkspaceCapabilities,
    ) -> None:
        try:
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                logger.warning(
                    "Workspace %s not found while storing capabilities snapshot",
                    workspace_id,
                )
                self.db.rollback()
                return

            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if not workspace:
                logger.warning(
                    "Workspace %s disappeared while storing capabilities snapshot",
                    workspace_id,
                )
                self.db.rollback()
                return

            workspace.agentic_capabilities = WorkspaceCapabilities.model_validate(
                capabilities
            ).model_dump(by_alias=True)
            workspace.updated_at = datetime.utcnow()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _normalize_capabilities(
        capabilities: dict | WorkspaceCapabilities,
    ) -> dict:
        if isinstance(capabilities, WorkspaceCapabilities):
            return capabilities.model_dump()
        return WorkspaceCapabilities.model_validate(capabilities).model_dump()

    async def _sync_git_settings(
        self, runtime_url: str, git_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync Git settings to specified runtime"""
        url = f"{runtime_url}/api/v1/internal/settings/git"
        headers = self._runtime_headers(workspace_id)

        payload = {
            "userName": git_data.get("userName"),
            "userEmail": git_data.get("userEmail"),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Git settings sync succeeded - workspace: {workspace_id}")
            return {
                "type": "git_settings",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
            }

        except Exception as e:
            logger.error(
                f"Git settings sync failed - workspace: {workspace_id}, error: {e}"
            )
            raise Exception(f"Git sync failed for {workspace_id}: {e}")

    async def sync_firewall_to_runtime(
        self, workspace_id: str, firewall_config: dict
    ) -> Dict[str, any]:
        """Sync firewall settings to specified workspace runtime"""
        logger.info(f"Begin syncing firewall settings to workspace: {workspace_id}")

        # Get workspace runtime URL
        runtimes = await self._get_running_runtimes()
        target_runtime = next(
            (r for r in runtimes if r["workspace_id"] == workspace_id), None
        )

        if not target_runtime:
            logger.warning(
                f"Runtime of workspace {workspace_id} is not running, skip sync"
            )
            return {
                "type": "firewall",
                "workspace_id": workspace_id,
                "success": False,
                "message": "Runtime not running",
            }

        return await self._sync_firewall(
            target_runtime["url"], firewall_config, workspace_id
        )

    async def _sync_firewall(
        self, runtime_url: str, firewall_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync firewall settings to specified runtime"""
        url = f"{runtime_url}/api/v1/internal/settings/firewall"
        headers = self._runtime_headers(workspace_id)

        # Docker runtime enforcement currently applies to the workspace runtime
        # container only. The manager may persist a browser firewall group for API
        # consistency, but that scope does not yet have a dedicated Docker-side
        # enforcement channel here.
        workspace_firewall = firewall_data.get("workspace", firewall_data)
        unenforced_scopes = ["browser"] if "browser" in firewall_data else []

        payload = {
            "egressMode": workspace_firewall["egressMode"],
            "allowedDomains": workspace_firewall.get("allowedDomains", []),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Firewall settings sync succeeded - workspace: {workspace_id}")
            return {
                "type": "firewall",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
                "enforced_scopes": ["workspace"],
                "unenforced_scopes": unenforced_scopes,
            }

        except Exception as e:
            logger.error(
                f"Firewall settings sync failed - workspace: {workspace_id}, error: {e}"
            )
            raise Exception(f"Firewall sync failed for {workspace_id}: {e}")


__all__ = ["RuntimeCapabilitiesSyncError", "RuntimeSyncService"]
