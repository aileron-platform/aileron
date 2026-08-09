"""Synchronization service - Sync settings to workspace-runtime"""

from __future__ import annotations

import httpx

from app.config.model_registry import normalize_model_selection
from app.core.logging import get_logger
from app.db.models import UserSetting, Workspace
from app.modules.localization.translator import get_i18n_service
from app.modules.workspace.runtime.command_auth import runtime_command_headers

logger = get_logger(__name__)
i18n = get_i18n_service()


class RuntimeSettingsSnapshotSyncService:
    """Synchronization service - Responsible for syncing database settings to workspace-runtime"""

    @staticmethod
    async def sync_settings_to_runtime(
        workspace: Workspace,
        settings: UserSetting,
        language: str = "en",
    ) -> dict:
        """
        Sync user settings to specified workspace-runtime

        Args:
            workspace: Workspace Object
            settings: UserSetting Object

        Returns:
            Sync result dictionary
        """
        if not workspace.runtime_internal_url:
            raise ValueError(
                f"Workspace {workspace.id} does not have runtime_internal_url"
            )

        results = {
            "ssh": {"success": False, "message": ""},
            "claude_code": {"success": False, "message": ""},
            "codex": {"success": False, "message": ""},
            "git": {"success": False, "message": ""},
        }

        base_url = workspace.runtime_internal_url.rstrip("/")

        def command_headers() -> dict[str, str]:
            runtime_instance_id = workspace.runtime_instance_id
            if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
                raise RuntimeError("Runtime instance identity is unavailable")
            return runtime_command_headers(
                workspace_id=workspace.id,
                runtime_instance_id=runtime_instance_id,
                action="settings.sync",
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Sync SSH keys
            if settings.ssh_private_key and settings.ssh_public_key:
                try:
                    logger.info(f"Sync SSH keys to workspace {workspace.id}")
                    logger.info(
                        f"Request URL: {base_url}/api/v1/internal/settings/ssh-keys"
                    )
                    response = await client.post(
                        f"{base_url}/api/v1/internal/settings/ssh-keys",
                        json={
                            "privateKey": settings.ssh_private_key,
                            "publicKey": settings.ssh_public_key,
                        },
                        headers=command_headers(),
                    )
                    logger.info(f"SSH keys response status: {response.status_code}")
                    logger.info(f"SSH keys response content: {response.text}")
                    response.raise_for_status()
                    results["ssh"]["success"] = True
                    results["ssh"]["message"] = i18n.translate(
                        "sync.ssh.success", language=language
                    )
                    logger.info(f"SSH keys sync succeeded: {workspace.id}")
                except Exception as e:
                    logger.error(f"SSH keys sync failed: {e}", exc_info=True)
                    results["ssh"]["message"] = i18n.translate(
                        "sync.ssh.failed", language=language
                    )
            else:
                results["ssh"]["success"] = True
                results["ssh"]["message"] = "No SSH keys need to sync"

            # 2. Sync Claude Code settings
            try:
                logger.info(f"Sync Claude Code settings to workspace {workspace.id}")

                # Read Claude Code settings from additional_settings
                additional_settings = settings.additional_settings or {}
                claude_settings = additional_settings.get("claudeCode", {})

                api_key = claude_settings.get("authKey") or settings.claude_auth_key
                auth_method = claude_settings.get("authMethod")
                if not auth_method:
                    auth_method = "api_key" if api_key else "subscription"

                # Get model settings from claude_selected_model or model in additional_settings
                model = claude_settings.get("model") or settings.claude_selected_model

                claude_payload = {
                    "authMethod": auth_method,
                    "subscriptionAccessToken": claude_settings.get(
                        "subscriptionAccessToken"
                    ),
                    "subscriptionRefreshToken": claude_settings.get(
                        "subscriptionRefreshToken"
                    ),
                    "subscriptionExpiresAt": claude_settings.get(
                        "subscriptionExpiresAt"
                    ),
                    "oauthAccount": claude_settings.get("oauthAccount"),
                    "apiKey": api_key,
                    "model": model,
                    "environmentVariables": claude_settings.get(
                        "environmentVariables", []
                    ),
                }

                logger.info(
                    "Claude Code sync payload prepared: auth_method=%s model=%s env_count=%s",
                    auth_method,
                    model,
                    len(claude_payload["environmentVariables"]),
                )
                logger.info(
                    f"Request URL: {base_url}/api/v1/internal/settings/claude-code"
                )

                response = await client.post(
                    f"{base_url}/api/v1/internal/settings/claude-code",
                    json=claude_payload,
                    headers=command_headers(),
                )

                # Record detailed response information
                logger.info(f"Response status code: {response.status_code}")
                logger.info(f"ResponseHeader: {dict(response.headers)}")

                if response.status_code != 200:
                    response_text = response.text
                    logger.error(
                        f"Claude Code sync failed, status code: {response.status_code}, response content: {response_text}"
                    )
                    response.raise_for_status()
                else:
                    response_data = response.json()
                    logger.info(f"Claude Code sync response: {response_data}")

                results["claude_code"]["success"] = True
                results["claude_code"]["message"] = i18n.translate(
                    "sync.claude_code.success", language=language
                )
                logger.info(f"Claude Code settings sync succeeded: {workspace.id}")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Claude Code HTTP Error: {e.response.status_code} - {e.response.text}"
                )
                results["claude_code"]["message"] = i18n.translate(
                    "sync.claude_code.failed", language=language
                )
            except httpx.TimeoutException as e:
                logger.error(f"Claude Code request timeout: {e}")
                results["claude_code"]["message"] = i18n.translate(
                    "sync.claude_code.failed", language=language
                )
            except httpx.ConnectError as e:
                logger.error(f"Claude Code connection error: {e}")
                results["claude_code"]["message"] = i18n.translate(
                    "sync.claude_code.failed", language=language
                )
            except Exception as e:
                logger.error(f"Claude Code settings sync failed: {e}")
                results["claude_code"]["message"] = i18n.translate(
                    "sync.claude_code.failed", language=language
                )

            # 3. Sync Codex settings
            try:
                logger.info(f"Sync Codex settings to workspace {workspace.id}")

                additional_settings = settings.additional_settings or {}
                codex_settings = additional_settings.get("codex", {})
                codex_model_selection = normalize_model_selection(
                    "codex", codex_settings.get("modelSelection"), mode="read"
                )

                is_not_connected = codex_settings.get("loginStatus") == "notConnected"
                codex_payload = {
                    "loginStatus": codex_settings.get("loginStatus", "notConnected"),
                    "account": codex_settings.get("account"),
                    "model": codex_settings.get("model")
                    or codex_model_selection.default_model,
                    "authFlow": codex_settings.get("authFlow"),
                    "cliState": (
                        None if is_not_connected else codex_settings.get("cliState")
                    ),
                    "environmentVariables": codex_settings.get(
                        "environmentVariables", []
                    ),
                    "clearAuth": is_not_connected,
                }

                logger.info(
                    "Codex sync payload prepared: login_status=%s model=%s env_count=%s",
                    codex_payload["loginStatus"],
                    codex_payload["model"],
                    len(codex_payload["environmentVariables"]),
                )
                response = await client.post(
                    f"{base_url}/api/v1/internal/settings/codex",
                    json=codex_payload,
                    headers=command_headers(),
                )
                response.raise_for_status()
                results["codex"]["success"] = True
                results["codex"]["message"] = i18n.translate(
                    "sync.codex.success", language=language
                )
                logger.info(f"Codex settings sync succeeded: {workspace.id}")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Codex HTTP Error: {e.response.status_code} - {e.response.text}"
                )
                results["codex"]["message"] = i18n.translate(
                    "sync.codex.failed", language=language
                )
            except httpx.TimeoutException as e:
                logger.error(f"Codex request timeout: {e}")
                results["codex"]["message"] = i18n.translate(
                    "sync.codex.failed", language=language
                )
            except httpx.ConnectError as e:
                logger.error(f"Codex connection error: {e}")
                results["codex"]["message"] = i18n.translate(
                    "sync.codex.failed", language=language
                )
            except Exception as e:
                logger.error(f"Codex settings sync failed: {e}")
                results["codex"]["message"] = i18n.translate(
                    "sync.codex.failed", language=language
                )

            # 4. Sync Git settings
            if settings.git_user_name and settings.git_user_email:
                try:
                    logger.info(f"Sync Git settings to workspace {workspace.id}")
                    response = await client.post(
                        f"{base_url}/api/v1/internal/settings/git",
                        json={
                            "userName": settings.git_user_name,
                            "userEmail": settings.git_user_email,
                        },
                        headers=command_headers(),
                    )
                    response.raise_for_status()
                    results["git"]["success"] = True
                    results["git"]["message"] = i18n.translate(
                        "sync.git.success", language=language
                    )
                    logger.info(f"Git settings sync succeeded: {workspace.id}")
                except Exception as e:
                    logger.error(f"Git settings sync failed: {e}")
                    results["git"]["message"] = i18n.translate(
                        "sync.git.failed", language=language
                    )
            else:
                results["git"]["success"] = True
                results["git"]["message"] = "No Git settings need to sync"

        return results

    @staticmethod
    async def sync_to_all_workspaces(
        user_id: str, settings: UserSetting, db, language: str = "en"
    ) -> dict:
        """
        Sync settings to all running workspaces of user

        Args:
            user_id: User ID
            settings: UserSetting object
            db: Database session
            language: Language code

        Returns:
            Sync result dictionary
        """
        from sqlalchemy import select

        # Query all running workspaces for user
        query = select(Workspace).where(
            Workspace.owner_id == user_id, Workspace.runtime_status == "running"
        )
        workspaces = db.execute(query).scalars().all()

        if not workspaces:
            return {
                "success": True,
                "message": "No running workspaces need to sync",
                "workspaces": [],
            }

        results = []
        for workspace in workspaces:
            try:
                sync_result = (
                    await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                        workspace, settings, language
                    )
                )
                # Check if any actual sync operations succeeded
                # If no items need sync, still consider as success
                results.append(
                    {
                        "workspace_id": workspace.id,
                        "workspace_name": workspace.name,
                        "success": all(r["success"] for r in sync_result.values()),
                        "details": sync_result,
                    }
                )
            except Exception as e:
                logger.error(f"Sync to workspace {workspace.id} failed: {e}")
                results.append(
                    {
                        "workspace_id": workspace.id,
                        "workspace_name": workspace.name,
                        "success": False,
                        "error": str(e),
                    }
                )

        all_success = all(r["success"] for r in results)

        if all_success:
            message = i18n.translate(
                "sync.success", language=language, count=len(results)
            )
        else:
            message = i18n.translate(
                "sync.partial_failed", language=language, count=len(results)
            )

        return {
            "success": all_success,
            "message": message,
            "workspaces": results,
        }


__all__ = ["RuntimeSettingsSnapshotSyncService"]
