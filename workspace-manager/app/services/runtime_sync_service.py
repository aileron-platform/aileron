"""Runtime synchronization service - Responsible for syncing settings to workspace-runtime"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models

logger = logging.getLogger(__name__)


class RuntimeSyncService:
    """Runtime synchronization service"""

    def __init__(self, db: Session):
        self.db = db
        self.internal_api_token = "dev-internal-token"  # TODO: Read from settings file
        self.timeout = 30.0

    async def sync_settings_to_runtimes(self, user_id: str, changes: dict) -> Dict[str, any]:
        """Sync settings to all related workspace-runtimes"""
        logger.info(f"Begin syncing settings to runtime, user_id: {user_id}, changes: {list(changes.keys())}")

        # Get all workspace-runtimes for user
        runtimes = await self._get_user_workspace_runtimes(user_id)

        if not runtimes:
            logger.warning(f"No workspace-runtime found for user {user_id}")
            return {"success": True, "synced_runtimes": 0, "total_tasks": 0, "results": []}

        # Concurrently call all runtimes
        tasks = []
        for runtime in runtimes:
            runtime_tasks = []

            if "ssh" in changes:
                runtime_tasks.append(
                    self._sync_ssh_keys(runtime["url"], changes["ssh"], runtime["workspace_id"])
                )

            if "claudeCode" in changes:
                runtime_tasks.append(
                    self._sync_claude_code(runtime["url"], changes["claudeCode"], runtime["workspace_id"])
                )

            if "codex" in changes:
                runtime_tasks.append(
                    self._sync_codex(runtime["url"], changes["codex"], runtime["workspace_id"])
                )

            if "git" in changes:
                runtime_tasks.append(
                    self._sync_git_settings(runtime["url"], changes["git"], runtime["workspace_id"])
                )

            if "gemini" in changes:
                runtime_tasks.append(
                    self._sync_gemini(runtime["url"], changes["gemini"], runtime["workspace_id"])
                )

            # Combine all tasks from each runtime
            if runtime_tasks:
                tasks.extend(runtime_tasks)

        if not tasks:
            logger.info("No changes to sync")
            return {"success": True, "synced_runtimes": len(runtimes), "total_tasks": 0, "results": []}

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
                detailed_results.append({
                    "task_index": i,
                    "success": False,
                    "error": str(result)
                })
            else:
                logger.info(f"Sync task {i} succeeded: {result}")
                success_count += 1
                detailed_results.append({
                    "task_index": i,
                    "success": True,
                    "result": result
                })

        return {
            "success": error_count == 0,
            "synced_runtimes": len(runtimes),
            "total_tasks": len(tasks),
            "success_count": success_count,
            "error_count": error_count,
            "results": detailed_results
        }

    async def _get_running_runtimes(self) -> List[Dict[str, str]]:
        """Get all running workspace-runtime information"""
        # Query all running workspaces
        stmt = (
            select(db_models.Workspace)
            .where(db_models.Workspace.runtime_status == "running")
        )
        workspaces = self.db.execute(stmt).scalars().all()

        runtimes = []
        for workspace in workspaces:
            if workspace.runtime_external_url:
                runtimes.append({
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "url": workspace.runtime_external_url
                })

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
            if workspace.runtime_external_url:
                runtimes.append({
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "url": workspace.runtime_external_url
                })

        logger.info(f"Found {len(runtimes)} running workspace-runtimes")
        return runtimes

    async def _sync_ssh_keys(self, runtime_url: str, ssh_data: dict, workspace_id: str) -> Dict[str, any]:
        """Sync SSH keys to specified runtime"""
        url = f"{runtime_url}/internal/settings/ssh-keys"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        payload = {
            "privateKey": ssh_data.get("privateKey"),
            "publicKey": ssh_data.get("publicKey")
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
                "response": result
            }

        except Exception as e:
            logger.error(f"SSH keys sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"SSH sync failed for {workspace_id}: {e}")

    async def _sync_claude_code(self, runtime_url: str, claude_data: dict, workspace_id: str) -> Dict[str, any]:
        """Sync Claude Code settings to specified runtime"""
        url = f"{runtime_url}/internal/settings/claude-code"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        payload = {
            "authMethod": claude_data.get("authMethod"),
            "subscriptionAccessToken": claude_data.get("subscriptionAccessToken"),
            "subscriptionRefreshToken": claude_data.get("subscriptionRefreshToken"),
            "subscriptionExpiresAt": claude_data.get("subscriptionExpiresAt"),
            "apiKey": claude_data.get("authKey"),
            "environmentVariables": claude_data.get("environmentVariables", [])
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Claude Code sync succeeded - workspace: {workspace_id}")
            return {
                "type": "claude_code",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result
            }

        except Exception as e:
            logger.error(f"Claude Code sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Claude Code sync failed for {workspace_id}: {e}")

    async def _sync_codex(self, runtime_url: str, codex_data: dict, workspace_id: str) -> Dict[str, any]:
        """Sync Codex settings to specified runtime"""
        url = f"{runtime_url}/internal/settings/codex"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        payload = {
            "authMethod": codex_data.get("authMethod"),
            "loginStatus": codex_data.get("loginStatus"),
            "account": codex_data.get("account"),
            "model": codex_data.get("model"),
            "authFlow": codex_data.get("authFlow"),
            "environmentVariables": codex_data.get("environmentVariables", []),
            "clearAuth": codex_data.get("loginStatus") == "notConnected",
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
                "response": result
            }

        except Exception as e:
            logger.error(f"Codex sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Codex sync failed for {workspace_id}: {e}")

    async def _sync_git_settings(self, runtime_url: str, git_data: dict, workspace_id: str) -> Dict[str, any]:
        """Sync Git settings to specified runtime"""
        url = f"{runtime_url}/internal/settings/git"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        payload = {
            "userName": git_data.get("userName"),
            "userEmail": git_data.get("userEmail")
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
                "response": result
            }

        except Exception as e:
            logger.error(f"Git settings sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Git sync failed for {workspace_id}: {e}")

    async def _sync_gemini(self, runtime_url: str, gemini_data: dict, workspace_id: str) -> Dict[str, any]:
        """Sync Gemini settings to specified runtime"""
        url = f"{runtime_url}/internal/settings/gemini"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        payload = {
            "authMethod": gemini_data.get("authMethod"),
            "accountEmail": gemini_data.get("account", {}).get("email"),
            "accessToken": gemini_data.get("accessToken"),
            "refreshToken": gemini_data.get("refreshToken"),
            "idToken": gemini_data.get("idToken"),
            "expiresAt": gemini_data.get("expiresAt"),
            "scope": gemini_data.get("scope"),
            "environmentVariables": gemini_data.get("environmentVariables", []),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()

            logger.info(f"Gemini sync succeeded - workspace: {workspace_id}")
            return {
                "type": "gemini",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result,
            }

        except Exception as e:
            logger.error(f"Gemini sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Gemini sync failed for {workspace_id}: {e}")

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
            logger.warning(f"Runtime of workspace {workspace_id} is not running, skip sync")
            return {
                "type": "firewall",
                "workspace_id": workspace_id,
                "success": False,
                "message": "Runtime not running"
            }

        return await self._sync_firewall(
            target_runtime["url"], firewall_config, workspace_id
        )

    async def _sync_firewall(
        self, runtime_url: str, firewall_data: dict, workspace_id: str
    ) -> Dict[str, any]:
        """Sync firewall settings to specified runtime"""
        url = f"{runtime_url}/internal/settings/firewall"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        # Docker runtime enforcement currently applies to the workspace runtime
        # container only. The manager may persist a browser firewall group for API
        # consistency, but that scope does not yet have a dedicated Docker-side
        # enforcement channel here.
        workspace_firewall = firewall_data.get("workspace", firewall_data)
        unenforced_scopes = ["browser"] if "browser" in firewall_data else []

        payload = {
            "networkAccessEnabled": workspace_firewall.get("networkAccessEnabled", True),
            "domainAccessMode": workspace_firewall.get("domainAccessMode", "all"),
            "allowedDomains": workspace_firewall.get("allowedDomains", [])
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
            logger.error(f"Firewall settings sync failed - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Firewall sync failed for {workspace_id}: {e}")


__all__ = ["RuntimeSyncService"]
