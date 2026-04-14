"""同步服務 - 將設定同步到 workspace-runtime"""

from __future__ import annotations

import httpx
from typing import Optional

from app.core.logging import get_logger
from app.db.models import UserSetting, Workspace
from app.services.i18n_service import get_i18n_service

logger = get_logger(__name__)
i18n = get_i18n_service()


class SyncService:
    """同步服務 - 負責將資料庫設定同步到 workspace-runtime"""

    @staticmethod
    async def sync_settings_to_runtime(
        workspace: Workspace,
        settings: UserSetting,
        language: str = "en",
    ) -> dict:
        """
        將用戶設定同步到指定的 workspace-runtime

        Args:
            workspace: Workspace 物件
            settings: UserSetting 物件

        Returns:
            同步結果字典
        """
        if not workspace.runtime_internal_url:
            raise ValueError(f"Workspace {workspace.id} 沒有 runtime_internal_url")
        
        results = {
            "ssh": {"success": False, "message": ""},
            "claude_code": {"success": False, "message": ""},
            "git": {"success": False, "message": ""},
        }
        
        base_url = workspace.runtime_internal_url.rstrip("/")

        # Internal API 認證 token
        headers = {
            "Authorization": "Bearer dev-internal-token",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            # 1. 同步 SSH Keys
            if settings.ssh_private_key and settings.ssh_public_key:
                try:
                    logger.info(f"同步 SSH Keys 到 workspace {workspace.id}")
                    logger.info(f"請求 URL: {base_url}/api/v1/internal/settings/ssh-keys")
                    response = await client.post(
                        f"{base_url}/api/v1/internal/settings/ssh-keys",
                        json={
                            "privateKey": settings.ssh_private_key,
                            "publicKey": settings.ssh_public_key,
                        }
                    )
                    logger.info(f"SSH Keys 響應狀態: {response.status_code}")
                    logger.info(f"SSH Keys 響應內容: {response.text}")
                    response.raise_for_status()
                    results["ssh"]["success"] = True
                    results["ssh"]["message"] = i18n.translate("sync.ssh.success", language=language)
                    logger.info(f"SSH Keys 同步成功: {workspace.id}")
                except Exception as e:
                    logger.error(f"SSH Keys 同步失敗: {e}", exc_info=True)
                    results["ssh"]["message"] = i18n.translate("sync.ssh.failed", language=language)
            else:
                results["ssh"]["message"] = "無 SSH Keys 需要同步"
            
            # 2. 同步 Claude Code 設定
            try:
                logger.info(f"同步 Claude Code 設定到 workspace {workspace.id}")

                # 從 additional_settings 讀取 Claude Code 設定
                additional_settings = settings.additional_settings or {}
                claude_settings = additional_settings.get("claudeCode", {})

                api_key = claude_settings.get("authKey") or settings.claude_auth_key
                auth_method = claude_settings.get("authMethod")
                if not auth_method:
                    auth_method = "api_key" if api_key else "subscription"

                # 從 claude_selected_model 或 additional_settings 中的 model 取得模型設定
                model = claude_settings.get("model") or settings.claude_selected_model

                claude_payload = {
                    "authMethod": auth_method,
                    "subscriptionAccessToken": claude_settings.get("subscriptionAccessToken"),
                    "subscriptionRefreshToken": claude_settings.get("subscriptionRefreshToken"),
                    "subscriptionExpiresAt": claude_settings.get("subscriptionExpiresAt"),
                    "oauthAccount": claude_settings.get("oauthAccount"),
                    "apiKey": api_key,
                    "model": model,
                    "environmentVariables": claude_settings.get("environmentVariables", []),
                }

                # 除錯：記錄傳送的資料
                logger.info(f"Claude Code 同步 payload: {claude_payload}")
                logger.info(f"Additional settings: {additional_settings}")
                logger.info(f"Claude settings from additional_settings: {claude_settings}")
                logger.info(f"請求 URL: {base_url}/api/v1/internal/settings/claude-code")

                response = await client.post(
                    f"{base_url}/api/v1/internal/settings/claude-code",
                    json=claude_payload,
                )

                # 記錄詳細的回應資訊
                logger.info(f"回應狀態碼: {response.status_code}")
                logger.info(f"回應標頭: {dict(response.headers)}")

                if response.status_code != 200:
                    response_text = response.text
                    logger.error(f"Claude Code 同步失敗，狀態碼: {response.status_code}, 回應內容: {response_text}")
                    response.raise_for_status()
                else:
                    response_data = response.json()
                    logger.info(f"Claude Code 同步回應: {response_data}")

                results["claude_code"]["success"] = True
                results["claude_code"]["message"] = i18n.translate("sync.claude_code.success", language=language)
                logger.info(f"Claude Code 設定同步成功: {workspace.id}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Claude Code HTTP 錯誤: {e.response.status_code} - {e.response.text}")
                results["claude_code"]["message"] = i18n.translate("sync.claude_code.failed", language=language)
            except httpx.TimeoutException as e:
                logger.error(f"Claude Code 請求超時: {e}")
                results["claude_code"]["message"] = i18n.translate("sync.claude_code.failed", language=language)
            except httpx.ConnectError as e:
                logger.error(f"Claude Code 連接錯誤: {e}")
                results["claude_code"]["message"] = i18n.translate("sync.claude_code.failed", language=language)
            except Exception as e:
                logger.error(f"Claude Code 設定同步失敗: {e}")
                results["claude_code"]["message"] = i18n.translate("sync.claude_code.failed", language=language)
            
            # 3. 同步 Git 設定
            if settings.git_user_name and settings.git_user_email:
                try:
                    logger.info(f"同步 Git 設定到 workspace {workspace.id}")
                    response = await client.post(
                        f"{base_url}/api/v1/internal/settings/git",
                        json={
                            "userName": settings.git_user_name,
                            "userEmail": settings.git_user_email,
                        }
                    )
                    response.raise_for_status()
                    results["git"]["success"] = True
                    results["git"]["message"] = i18n.translate("sync.git.success", language=language)
                    logger.info(f"Git 設定同步成功: {workspace.id}")
                except Exception as e:
                    logger.error(f"Git 設定同步失敗: {e}")
                    results["git"]["message"] = i18n.translate("sync.git.failed", language=language)
            else:
                results["git"]["message"] = "無 Git 設定需要同步"
        
        return results

    @staticmethod
    async def sync_to_all_workspaces(user_id: str, settings: UserSetting, db, language: str = "en") -> dict:
        """
        將設定同步到用戶的所有運行中的 workspace

        Args:
            user_id: 用戶 ID
            settings: UserSetting 物件
            db: 資料庫 session
            language: 語言代碼

        Returns:
            同步結果字典
        """
        from sqlalchemy import select
        
        # 查詢用戶所有運行中的 workspace
        query = select(Workspace).where(
            Workspace.owner_id == user_id,
            Workspace.runtime_status == "running"
        )
        workspaces = db.execute(query).scalars().all()
        
        if not workspaces:
            return {
                "success": True,
                "message": "沒有運行中的 workspace 需要同步",
                "workspaces": []
            }
        
        results = []
        for workspace in workspaces:
            try:
                sync_result = await SyncService.sync_settings_to_runtime(workspace, settings, language)
                # 檢查是否有任何實際的同步操作成功
                # 如果沒有需要同步的項目，仍視為成功
                results.append({
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "success": not any(
                        not r["success"]
                        and "無" not in r["message"]
                        and "沒有" not in r["message"]
                        for r in sync_result.values()
                    ),
                    "details": sync_result,
                })
            except Exception as e:
                logger.error(f"同步到 workspace {workspace.id} 失敗: {e}")
                results.append({
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "success": False,
                    "error": str(e),
                })

        all_success = all(r["success"] for r in results)

        if all_success:
            message = i18n.translate("sync.success", language=language, count=len(results))
        else:
            message = i18n.translate("sync.partial_failed", language=language, count=len(results))

        return {
            "success": all_success,
            "message": message,
            "workspaces": results,
        }


__all__ = ["SyncService"]
