"""Runtime 同步服務 - 負責將設定同步到 workspace-runtime"""

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
    """Runtime 同步服務"""

    def __init__(self, db: Session):
        self.db = db
        self.internal_api_token = "dev-internal-token"  # TODO: 從設定檔讀取
        self.timeout = 30.0

    async def sync_settings_to_runtimes(self, user_id: str, changes: dict) -> Dict[str, any]:
        """同步設定到所有相關的 workspace-runtime"""
        logger.info(f"開始同步設定到 runtime，user_id: {user_id}, changes: {list(changes.keys())}")

        # 取得使用者的所有 workspace-runtime
        runtimes = await self._get_user_workspace_runtimes(user_id)

        if not runtimes:
            logger.warning(f"未找到 user {user_id} 的 workspace-runtime")
            return {"success": True, "synced_runtimes": 0, "total_tasks": 0, "results": []}

        # 並發呼叫所有 runtime
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

            if "git" in changes:
                runtime_tasks.append(
                    self._sync_git_settings(runtime["url"], changes["git"], runtime["workspace_id"])
                )

            # 將每個 runtime 的所有任務組合
            if runtime_tasks:
                tasks.extend(runtime_tasks)

        if not tasks:
            logger.info("沒有需要同步的變更")
            return {"success": True, "synced_runtimes": len(runtimes), "total_tasks": 0, "results": []}

        # 等待所有同步完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分析結果
        success_count = 0
        error_count = 0
        detailed_results = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"同步任務 {i} 失敗: {result}")
                error_count += 1
                detailed_results.append({
                    "task_index": i,
                    "success": False,
                    "error": str(result)
                })
            else:
                logger.info(f"同步任務 {i} 成功: {result}")
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
        """取得所有運行中的 workspace-runtime 資訊"""
        # 查詢所有運行中的 workspace
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

        logger.info(f"找到 {len(runtimes)} 個運行中的 workspace-runtime")
        return runtimes

    async def _get_user_workspace_runtimes(self, user_id: str) -> List[Dict[str, str]]:
        """取得使用者的所有 workspace-runtime 資訊"""
        # 查詢使用者的所有 workspace
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

        logger.info(f"找到 {len(runtimes)} 個運行中的 workspace-runtime")
        return runtimes

    async def _sync_ssh_keys(self, runtime_url: str, ssh_data: dict, workspace_id: str) -> Dict[str, any]:
        """同步 SSH Keys 到指定的 runtime"""
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

            logger.info(f"SSH Keys 同步成功 - workspace: {workspace_id}")
            return {
                "type": "ssh_keys",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result
            }

        except Exception as e:
            logger.error(f"SSH Keys 同步失敗 - workspace: {workspace_id}, error: {e}")
            raise Exception(f"SSH sync failed for {workspace_id}: {e}")

    async def _sync_claude_code(self, runtime_url: str, claude_data: dict, workspace_id: str) -> Dict[str, any]:
        """同步 Claude Code 設定到指定的 runtime"""
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

            logger.info(f"Claude Code 同步成功 - workspace: {workspace_id}")
            return {
                "type": "claude_code",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result
            }

        except Exception as e:
            logger.error(f"Claude Code 同步失敗 - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Claude Code sync failed for {workspace_id}: {e}")

    async def _sync_git_settings(self, runtime_url: str, git_data: dict, workspace_id: str) -> Dict[str, any]:
        """同步 Git 設定到指定的 runtime"""
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

            logger.info(f"Git 設定同步成功 - workspace: {workspace_id}")
            return {
                "type": "git_settings",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result
            }

        except Exception as e:
            logger.error(f"Git 設定同步失敗 - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Git sync failed for {workspace_id}: {e}")

    async def sync_firewall_to_runtime(
        self, workspace_id: str, firewall_config: dict
    ) -> Dict[str, any]:
        """同步防火牆設定到指定 workspace 的 runtime"""
        logger.info(f"開始同步防火牆設定到 workspace: {workspace_id}")

        # 獲取 workspace 的 runtime URL
        runtimes = await self._get_running_runtimes()
        target_runtime = next(
            (r for r in runtimes if r["workspace_id"] == workspace_id), None
        )

        if not target_runtime:
            logger.warning(f"Workspace {workspace_id} 的 runtime 未運行，跳過同步")
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
        """同步防火牆設定到指定的 runtime"""
        url = f"{runtime_url}/internal/settings/firewall"
        headers = {"Authorization": f"Bearer {self.internal_api_token}"}

        workspace_firewall = firewall_data.get("workspace", firewall_data)

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

            logger.info(f"防火牆設定同步成功 - workspace: {workspace_id}")
            return {
                "type": "firewall",
                "workspace_id": workspace_id,
                "runtime_url": runtime_url,
                "success": True,
                "response": result
            }

        except Exception as e:
            logger.error(f"防火牆設定同步失敗 - workspace: {workspace_id}, error: {e}")
            raise Exception(f"Firewall sync failed for {workspace_id}: {e}")


__all__ = ["RuntimeSyncService"]
