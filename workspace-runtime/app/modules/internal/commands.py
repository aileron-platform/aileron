"""Internal API Business Logic Service"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template
from openai_codex import AsyncCodex
from openai_codex.client import CodexConfig
from openai_codex.generated.v2_all import (
    CancelLoginAccountResponse,
    GetAccountResponse,
    LoginAccountResponse,
    LogoutAccountResponse,
)
from aileron_marketplace_core import (
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
)

from app.config.settings import get_settings
from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.settings.models import ClaudeCodeSettingsUpdateRequest
from app.modules.claude_code.settings.configuration import SettingsService
from app.modules.cli_settings.toml_codec import merge_known_values
from app.modules.cli_settings.user_scope.codecs import (
    JsonDocumentCodec,
    TomlDocumentCodec,
    write_text_atomic,
)
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import (
    UserScopePathResolver,
    runtime_user_home,
)
from app.modules.marketplace_operations.plugin_installation import (
    MarketplacePluginInstallService,
)
from app.modules.marketplace_operations.user_copy import (
    MarketplaceUserCopyService,
)

from .models import (
    ClaudeCodeRequest,
    CodexSettingsRequest,
    EnvironmentVariable,
    FirewallConfigRequest,
    GitSettingsRequest,
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
    SSHKeysRequest,
)

logger = logging.getLogger(__name__)

_codex_login_sessions: dict[str, AsyncCodex] = {}


class InternalService:
    """Internal API business logic service"""

    def __init__(self) -> None:
        self.home_dir = runtime_user_home()
        user_scope_paths = UserScopePathResolver(user_home=self.home_dir)
        self.ssh_dir = self.home_dir / ".ssh"
        self.claude_dir = user_scope_paths.resolve_root(
            UserScopeAgent.CLAUDE_CODE
        ).runtime_path
        self.codex_auth_dir = user_scope_paths.resolve_root(
            UserScopeAgent.CODEX
        ).runtime_path
        self.codex_sessions_dir = self.home_dir / ".codex-sessions"
        self._json_document_codec = JsonDocumentCodec()
        self._toml_document_codec = TomlDocumentCodec()
        self._credentials_filename = ".credentials.json"
        self._env_keys_env = "CLAUDE_CODE_SYNCED_KEYS"
        self._auth_method_env = "CLAUDE_CODE_AUTH_METHOD"
        self._codex_env_keys_env = "CODEX_SYNCED_KEYS"
        self._codex_auth_method_env = "CODEX_AUTH_METHOD"
        self._codex_login_status_env = "CODEX_LOGIN_STATUS"
        self._codex_model_env = "CODEX_MODEL"
        runtime_settings = get_settings()
        self._workspace_id = runtime_settings.AILERON_WORKSPACE_ID
        self._claude_settings_service = SettingsService()
        self._marketplace_plugin_installs = MarketplacePluginInstallService(
            settings=runtime_settings
        )
        self._marketplace_user_copies = MarketplaceUserCopyService(
            settings=runtime_settings
        )

    @property
    def marketplace_user_copy_max_archive_bytes(self) -> int:
        """Maximum accepted one-shot ZIP body size."""

        return self._marketplace_user_copies.max_archive_bytes

    async def preflight_marketplace_user_copy(
        self,
        request: UserCopyProjectionPreflightRequestContract,
    ) -> UserCopyProjectionPreflightResultContract:
        """Run one-shot user-copy target preflight."""

        return await asyncio.to_thread(
            self._marketplace_user_copies.preflight,
            request,
        )

    async def apply_marketplace_user_copy(
        self,
        metadata: UserCopyProjectionApplyMetadataContract,
        bundle: bytes,
    ) -> UserCopyProjectionApplyResultContract:
        """Stage and apply one canonical user-copy snapshot."""

        return await asyncio.to_thread(
            self._marketplace_user_copies.apply,
            metadata,
            bundle,
        )

    async def setup_ssh_keys(self, request: SSHKeysRequest) -> Dict[str, Any]:
        """Setup SSH Keys"""
        try:
            logger.info("Starting SSH Keys setup")

            # Ensure .ssh directory exists
            self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            logger.debug(f"SSH directory prepared: {self.ssh_dir}")

            # Write private key
            private_key_path = self.ssh_dir / "id_rsa"
            # Ensure private key ends with newline
            private_key_content = request.private_key
            if not private_key_content.endswith("\n"):
                private_key_content += "\n"
            private_key_path.write_text(private_key_content)
            private_key_path.chmod(0o600)
            logger.debug(f"Private key configured: {private_key_path}")

            # Write public key
            public_key_path = self.ssh_dir / "id_rsa.pub"
            # Ensure public key ends with newline
            public_key_content = request.public_key
            if not public_key_content.endswith("\n"):
                public_key_content += "\n"
            public_key_path.write_text(public_key_content)
            public_key_path.chmod(0o644)
            logger.debug(f"Public key configured: {public_key_path}")

            # Add public key to authorized_keys
            authorized_keys_path = self.ssh_dir / "authorized_keys"
            logger.debug(f"Preparing to update authorized_keys: {authorized_keys_path}")

            # Read existing authorized_keys (if exists)
            existing_keys = set()
            if authorized_keys_path.exists():
                content = authorized_keys_path.read_text()
                existing_keys = {
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("#")
                }
                logger.debug(
                    f"Existing authorized_keys contains {len(existing_keys)} keys"
                )

            # Get current public key fingerprint (to check if already exists)
            new_key = public_key_content.strip()

            # Check if identical key already exists
            if new_key in existing_keys:
                logger.info(
                    "Public key already exists in authorized_keys, no need to add duplicate"
                )
                authorized_keys_added = False
            else:
                # Add new public key to set
                existing_keys.add(new_key)
                logger.info("Adding public key to authorized_keys")

                # Write authorized_keys
                authorized_keys_content = "\n".join(sorted(existing_keys)) + "\n"
                authorized_keys_path.write_text(authorized_keys_content)
                authorized_keys_path.chmod(0o600)
                authorized_keys_added = True
                logger.debug(
                    f"authorized_keys updated, now contains {len(existing_keys)} keys"
                )

            logger.info("SSH Keys setup completed")
            return {
                "private_key_path": str(private_key_path),
                "public_key_path": str(public_key_path),
                "authorized_keys_path": str(authorized_keys_path),
                "authorized_keys_added": authorized_keys_added,
                "total_authorized_keys": len(existing_keys),
                "ssh_dir_permissions": oct(self.ssh_dir.stat().st_mode)[-3:],
            }

        except Exception as e:
            logger.error(f"SSH Keys setup failed: {e}")
            raise

    async def install_marketplace_plugin(
        self,
        request: MarketplacePluginInstallRequest,
    ) -> MarketplacePluginCommandResult:
        """Run one target client CLI installation without durable install state."""

        return await asyncio.to_thread(
            self._marketplace_plugin_installs.install,
            request,
        )

    async def setup_codex(
        self, request: CodexSettingsRequest
    ) -> Dict[str, str | list[str] | bool]:
        """Setup Codex CLI auth state and environment variables."""
        try:
            logger.info(
                "Starting Codex setup: login_status=%s clear_auth=%s has_tokens=%s env_count=%s",
                request.login_status,
                request.clear_auth,
                bool(request.auth_tokens and request.auth_tokens.access_token),
                len(request.environment_variables),
            )

            self.codex_auth_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.codex_sessions_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            self.codex_auth_dir.chmod(0o700)
            self.codex_sessions_dir.chmod(0o700)

            if request.clear_auth:
                self._clear_codex_auth_state()
            elif request.cli_state:
                self._write_codex_cli_state(request.cli_state.model_dump(by_alias=True))
            elif request.auth_tokens and request.auth_tokens.access_token:
                self._write_codex_auth_state(request)

            synced_keys = self._sync_codex_environment_variables(
                request.environment_variables
            )

            if request.login_status:
                os.environ[self._codex_login_status_env] = request.login_status
            elif (self.codex_auth_dir / "auth.json").is_file():
                os.environ[self._codex_login_status_env] = "connected"
            else:
                os.environ.pop(self._codex_login_status_env, None)

            if request.auth_method:
                os.environ[self._codex_auth_method_env] = request.auth_method
            else:
                os.environ.pop(self._codex_auth_method_env, None)

            if request.model:
                os.environ[self._codex_model_env] = request.model
            else:
                os.environ.pop(self._codex_model_env, None)

            if synced_keys:
                os.environ[self._codex_env_keys_env] = ",".join(synced_keys)
            else:
                os.environ.pop(self._codex_env_keys_env, None)

            auth_path = self.codex_auth_dir / "auth.json"
            logger.info(
                "Codex setup completed, auth_present=%s env_count=%s",
                auth_path.is_file(),
                len(synced_keys),
            )
            return {
                "codex_home": str(self.codex_auth_dir),
                "session_state_dir": str(self.codex_sessions_dir),
                "has_cli_auth": auth_path.is_file(),
                "has_config": (self.codex_auth_dir / "config.toml").is_file(),
                "has_installation_id": (
                    self.codex_auth_dir / "installation_id"
                ).is_file(),
                "environment_variables_set": synced_keys,
                "model": request.model or "",
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error("Codex setup failed: %s", e)
            raise

    async def start_codex_login(self) -> Dict[str, str]:
        """Start a Codex-native ChatGPT device-code login flow."""
        self.codex_auth_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        codex = AsyncCodex(
            config=CodexConfig(
                cwd="/workspace",
                env={"CODEX_HOME": str(self.codex_auth_dir)},
            )
        )
        try:
            await codex._ensure_initialized()
            response = await codex._client.request(
                "account/login/start",
                {"type": "chatgptDeviceCode"},
                response_model=LoginAccountResponse,
            )
            login = response.root
            login_id = getattr(login, "login_id", None)
            if not login_id:
                raise RuntimeError("Codex login response did not include loginId")
            _codex_login_sessions[login_id] = codex
            logger.info("Codex login flow started")
            return {
                "loginId": login_id,
                "verificationUrl": getattr(login, "verification_url", ""),
                "userCode": getattr(login, "user_code", ""),
                "type": getattr(login, "type", "chatgptDeviceCode"),
            }
        except Exception:
            await codex.close()
            raise

    async def get_codex_login_status(self) -> Dict[str, object]:
        """Read Codex account status from the managed auth home."""
        codex = AsyncCodex(
            config=CodexConfig(
                cwd="/workspace",
                env={"CODEX_HOME": str(self.codex_auth_dir)},
            )
        )
        try:
            await codex._ensure_initialized()
            response = await codex._client.request(
                "account/read",
                {"refreshToken": True},
                response_model=GetAccountResponse,
            )
            account = response.account.root if response.account else None
            if account is None:
                return {"loginStatus": "notConnected", "account": None}
            account_type = getattr(account, "type", None)
            if account_type != "chatgpt":
                return {
                    "loginStatus": "connected",
                    "account": {"type": account_type},
                    "cliState": self._read_codex_cli_state(),
                }
            return {
                "loginStatus": "connected",
                "account": {
                    "email": getattr(account, "email", None),
                    "planType": getattr(
                        getattr(account, "plan_type", None), "value", None
                    ),
                },
                "cliState": self._read_codex_cli_state(),
            }
        finally:
            await codex.close()

    async def cancel_codex_login(self, login_id: str) -> Dict[str, str]:
        """Cancel a pending Codex login flow."""
        codex = _codex_login_sessions.pop(login_id, None)
        if not codex:
            return {"status": "notFound"}
        try:
            response = await codex._client.request(
                "account/login/cancel",
                {"loginId": login_id},
                response_model=CancelLoginAccountResponse,
            )
            return {"status": response.status.value}
        finally:
            await codex.close()

    async def logout_codex(self) -> Dict[str, str]:
        """Logout Codex and clear persisted CLI auth state."""
        for login_id, codex in list(_codex_login_sessions.items()):
            _codex_login_sessions.pop(login_id, None)
            await codex.close()

        codex = AsyncCodex(
            config=CodexConfig(
                cwd="/workspace",
                env={"CODEX_HOME": str(self.codex_auth_dir)},
            )
        )
        try:
            await codex._ensure_initialized()
            await codex._client.request(
                "account/logout",
                None,
                response_model=LogoutAccountResponse,
            )
        except Exception as exc:
            logger.info("Codex app-server logout returned non-fatal error: %s", exc)
        finally:
            await codex.close()
        self._clear_codex_auth_state()
        return {"status": "loggedOut"}

    async def setup_claude_code(self, request: ClaudeCodeRequest) -> Dict[str, Any]:
        """Setup Claude Code"""
        try:
            logger.info("Starting Claude Code setup")

            logger.info(
                "Received Claude Code setup request: auth_method=%s model=%s env_count=%s has_oauth_account=%s has_subscription_token=%s",
                request.auth_method,
                request.model,
                len(request.environment_variables),
                bool(request.oauth_account),
                bool(request.subscription_access_token),
            )

            # Ensure .claude directory exists
            self.claude_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
            logger.debug(f"Claude directory prepared: {self.claude_dir}")

            # Create credentials.json file
            credentials_path = self.claude_dir / self._credentials_filename
            credentials_data = {}

            resolved_auth_method = request.auth_method
            if not resolved_auth_method:
                if request.subscription_access_token:
                    resolved_auth_method = "subscription"
                elif request.api_key or request.environment_variables:
                    resolved_auth_method = "api_key"

            # Store different credentials based on authentication method
            if (
                resolved_auth_method == "subscription"
                and request.subscription_access_token
            ):
                expires_at_ms = self._normalize_expires_at(
                    request.subscription_expires_at
                )
                logger.info(f"Subscription expiresAt parsing result: {expires_at_ms}")

                credentials_data = {
                    "authMethod": "subscription",
                    "claudeAiOauth": {
                        "accessToken": request.subscription_access_token,
                        "refreshToken": request.subscription_refresh_token,
                        "expiresAt": expires_at_ms,
                        "scopes": [
                            "user:file_upload",
                            "user:inference",
                            "user:mcp_servers",
                            "user:profile",
                            "user:sessions:claude_code",
                        ],
                        "subscriptionType": "pro",
                        "rateLimitTier": "default_claude_ai",
                    },
                }

                self._json_document_codec.write(
                    credentials_path,
                    credentials_data,
                )
                credentials_path.chmod(0o600)
                logger.debug(f"Credentials file created: {credentials_path}")
                logger.info("Stored Subscription OAuth Token (Claude Code format)")

                if request.oauth_account:
                    self._write_claude_user_state(request.oauth_account)
                    logger.info(
                        "Stored Claude Code OAuth account state to ~/.claude.json"
                    )
            elif resolved_auth_method == "api_key" and request.api_key:
                credentials_data = {
                    "authMethod": "api_key",
                    "apiKey": request.api_key,
                }
                self._clear_claude_oauth_state()
                logger.info("Stored API Key")
            else:
                self._clear_claude_oauth_state()

            # Set environment variables - do not sync environment variables when using subscription mode
            synced_keys: List[str] = []
            env_vars_set = []
            if resolved_auth_method != "subscription":
                # Write to .bashrc file
                bashrc_path = self.home_dir / ".bashrc"

                # Read existing .bashrc content
                existing_lines = []
                if bashrc_path.exists():
                    with open(bashrc_path, "r", encoding="utf-8") as f:
                        existing_lines = f.readlines()

                # Remove old environment variable settings (managed by this system)
                marker_start = "# Aileron - Claude Code Environment Variables - START\n"
                marker_end = "# Aileron - Claude Code Environment Variables - END\n"

                filtered_lines = []
                skip = False
                for line in existing_lines:
                    if line == marker_start:
                        skip = True
                        continue
                    if line == marker_end:
                        skip = False
                        continue
                    if not skip:
                        filtered_lines.append(line)

                # Prepare new environment variable settings
                new_env_lines = []
                if request.environment_variables:
                    new_env_lines.append(marker_start)
                    for env_var in request.environment_variables:
                        # Ensure key and value are not empty strings
                        if env_var.key and env_var.value:
                            # Escape special characters to avoid shell injection
                            escaped_value = (
                                env_var.value.replace("\\", "\\\\")
                                .replace('"', '\\"')
                                .replace("$", "\\$")
                                .replace("`", "\\`")
                            )
                            new_env_lines.append(
                                f'export {env_var.key}="{escaped_value}"\n'
                            )
                            synced_keys.append(env_var.key)
                            env_vars_set.append(env_var.key)
                            logger.debug(f"Environment variable set: {env_var.key}")
                        else:
                            logger.warning(
                                f"Skipping empty environment variable: key={env_var.key}, value={'<empty>' if not env_var.value else '<set>'}"
                            )
                    new_env_lines.append(marker_end)

                # Write back to .bashrc
                with open(bashrc_path, "w", encoding="utf-8") as f:
                    f.writelines(filtered_lines)
                    f.writelines(new_env_lines)

                logger.info(
                    f"Updated {bashrc_path}, set {len(synced_keys)} environment variables"
                )
            else:
                logger.info(
                    "Using Subscription authentication mode, skipping environment variable sync"
                )

            # Record synced authentication method and environment variable keys for subsequent status checks
            if resolved_auth_method:
                os.environ[self._auth_method_env] = resolved_auth_method
            else:
                os.environ.pop(self._auth_method_env, None)

            if synced_keys:
                os.environ[self._env_keys_env] = ",".join(synced_keys)
            else:
                os.environ.pop(self._env_keys_env, None)

            if "model" in request.model_fields_set:
                logger.info("Syncing Claude Code settings model override (scope=USER)")
                update_request = ClaudeCodeSettingsUpdateRequest(model=request.model)
                settings_state = self._claude_settings_service.update_settings(
                    self._workspace_id,
                    update_request,
                    DocumentScope.USER,
                )
                logger.info(
                    "USER scope Claude Code settings updated, current model value: %s",
                    settings_state.model,
                )

            logger.info(
                f"Claude Code setup completed, set {len(env_vars_set)} environment variables"
            )
            claude_user_state_path = self._claude_user_state_path()
            return {
                "credentials_path": str(credentials_path),
                "claude_json_path": str(claude_user_state_path),
                "auth_method": resolved_auth_method or "none",
                "has_credentials": bool(credentials_data),
                "has_claude_json": claude_user_state_path.is_file(),
                "environment_variables_set": env_vars_set,
                "claude_dir_permissions": oct(self.claude_dir.stat().st_mode)[-3:],
            }

        except Exception as e:
            logger.error(f"Claude Code setup failed: {e}")
            raise

    @staticmethod
    def _normalize_expires_at(raw_value: Optional[int | str]) -> Optional[int]:
        """Convert expiration time to millisecond timestamp, compatible with integer and ISO8601 strings."""
        if raw_value is None:
            return None

        if isinstance(raw_value, int):
            return raw_value

        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                return None

            # Try to convert directly to integer milliseconds
            try:
                return int(value)
            except ValueError:
                pass

            # Try to parse ISO8601
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to parse subscriptionExpiresAt value: %s (error=%s)",
                    value,
                    exc,
                )

        return None

    def _clear_claude_oauth_state(self) -> None:
        """Clean up OAuth-specific state to avoid residual subscription info when switching to API key."""
        credentials_path = self.claude_dir / self._credentials_filename
        if credentials_path.exists():
            credentials_path.unlink()

        claude_json_path = self._claude_user_state_path()
        if not claude_json_path.exists():
            return

        try:
            claude_json_data = self._json_document_codec.parse(
                claude_json_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning(
                f"Failed to read .claude.json while clearing OAuth account info: {exc}"
            )
            return

        if "oauthAccount" not in claude_json_data:
            return

        claude_json_data.pop("oauthAccount", None)
        self._json_document_codec.write(claude_json_path, claude_json_data)
        claude_json_path.chmod(0o600)

    def _write_claude_user_state(self, oauth_account: Any) -> None:
        """Write stable Claude Code user state required by CLI login."""
        claude_json_path = self._claude_user_state_path()
        claude_json_data: dict[str, Any] = {}

        if claude_json_path.exists():
            try:
                claude_json_data = self._json_document_codec.parse(
                    claude_json_path.read_text(encoding="utf-8")
                )
                logger.debug(
                    "Read existing .claude.json with %d top-level fields",
                    len(claude_json_data),
                )
            except Exception as exc:
                logger.warning(
                    "Failed to read existing .claude.json, rebuilding minimal state: %s",
                    exc,
                )

        account_data = oauth_account.model_dump(by_alias=True, exclude_none=True)
        user_identity = (
            account_data.get("accountUuid")
            or account_data.get("emailAddress")
            or "claude-code"
        )
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        claude_json_data.setdefault(
            "firstStartTime",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        claude_json_data["opusProMigrationComplete"] = True
        claude_json_data.setdefault("opusProMigrationTimestamp", now_ms)
        claude_json_data["sonnet1m45MigrationComplete"] = True
        claude_json_data["migrationVersion"] = 12
        claude_json_data["userID"] = hashlib.sha256(
            str(user_identity).encode("utf-8")
        ).hexdigest()
        claude_json_data["oauthAccount"] = account_data
        claude_json_data["hasCompletedOnboarding"] = True
        claude_json_data.setdefault("lastOnboardingVersion", "2.1.119")

        projects = claude_json_data.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        workspace_state = projects.get("/workspace")
        if not isinstance(workspace_state, dict):
            workspace_state = {}
        project_onboarding_seen_count = (
            workspace_state.get("projectOnboardingSeenCount") or 0
        )
        try:
            project_onboarding_seen_count = int(project_onboarding_seen_count)
        except (TypeError, ValueError):
            project_onboarding_seen_count = 0

        workspace_state.update(
            {
                "allowedTools": workspace_state.get("allowedTools", []),
                "mcpContextUris": workspace_state.get("mcpContextUris", []),
                "mcpServers": workspace_state.get("mcpServers", {}),
                "enabledMcpjsonServers": workspace_state.get(
                    "enabledMcpjsonServers", []
                ),
                "disabledMcpjsonServers": workspace_state.get(
                    "disabledMcpjsonServers", []
                ),
                "hasTrustDialogAccepted": True,
                "projectOnboardingSeenCount": max(project_onboarding_seen_count, 1),
                "hasClaudeMdExternalIncludesApproved": bool(
                    workspace_state.get("hasClaudeMdExternalIncludesApproved", False)
                ),
                "hasClaudeMdExternalIncludesWarningShown": bool(
                    workspace_state.get(
                        "hasClaudeMdExternalIncludesWarningShown", False
                    )
                ),
                "lastGracefulShutdown": bool(
                    workspace_state.get("lastGracefulShutdown", False)
                ),
            }
        )
        projects["/workspace"] = workspace_state
        claude_json_data["projects"] = projects

        self._json_document_codec.write(claude_json_path, claude_json_data)
        claude_json_path.chmod(0o600)

    def _claude_user_state_path(self) -> Path:
        """Resolve Claude user state through the shared user-scope contract."""

        return (
            UserScopePathResolver(user_home=self.home_dir)
            .resolve(
                UserScopeAgent.CLAUDE_CODE,
                UserScopeResource.MCP,
            )
            .runtime_path
        )

    def _write_codex_auth_state(self, request: CodexSettingsRequest) -> None:
        """Write Codex CLI auth state using the current CLI-readable format."""
        if not request.auth_tokens or not request.auth_tokens.access_token:
            return

        auth_path = self.codex_auth_dir / "auth.json"
        auth_data: dict[str, Any] = {
            "auth_mode": "chatgpt",
            "tokens": {
                "access_token": request.auth_tokens.access_token,
                "refresh_token": request.auth_tokens.refresh_token,
                "id_token": request.auth_tokens.id_token,
            },
        }

        if request.auth_tokens.expires_at is not None:
            auth_data["tokens"]["expires_at"] = request.auth_tokens.expires_at
        if request.account:
            auth_data["chatgpt_account_id"] = request.account.account_id
            auth_data["chatgpt_plan_type"] = request.account.plan_type

        self._json_document_codec.write(auth_path, auth_data)
        auth_path.chmod(0o600)

    def _write_codex_cli_state(self, cli_state: dict[str, Any]) -> None:
        """Write synchronized Codex CLI files."""
        auth_json = cli_state.get("authJson")
        auth_path = self.codex_auth_dir / "auth.json"
        if isinstance(auth_json, dict):
            self._json_document_codec.write(auth_path, auth_json)
            auth_path.chmod(0o600)
        elif auth_path.exists():
            auth_path.unlink()

        config_toml = cli_state.get("configToml")
        config_path = self.codex_auth_dir / "config.toml"
        if isinstance(config_toml, str):
            write_text_atomic(
                config_path,
                self._merged_codex_config_toml(config_path, config_toml),
            )
            config_path.chmod(0o600)

        installation_id = cli_state.get("installationId")
        installation_path = self.codex_auth_dir / "installation_id"
        if isinstance(installation_id, str) and installation_id.strip():
            write_text_atomic(installation_path, installation_id.strip() + "\n")
            installation_path.chmod(0o600)
        elif installation_path.exists():
            installation_path.unlink()

    def _read_codex_cli_state(self) -> dict[str, Any]:
        """Read Codex CLI files that are safe and necessary to synchronize."""
        cli_state: dict[str, Any] = {}

        auth_path = self.codex_auth_dir / "auth.json"
        if auth_path.is_file():
            try:
                cli_state["authJson"] = self._json_document_codec.parse(
                    auth_path.read_text(encoding="utf-8")
                )
            except Exception as exc:
                logger.warning(
                    "Failed to read Codex auth.json for synchronization: %s", exc
                )

        config_path = self.codex_auth_dir / "config.toml"
        if config_path.is_file():
            cli_state["configToml"] = config_path.read_text()

        installation_path = self.codex_auth_dir / "installation_id"
        if installation_path.is_file():
            cli_state["installationId"] = installation_path.read_text().strip()

        return cli_state

    def _merged_codex_config_toml(
        self,
        config_path: Path,
        incoming_toml: str,
    ) -> str:
        """Merge synchronized Codex config into an existing config.toml."""
        incoming_config = self._toml_document_codec.parse(incoming_toml)
        if not config_path.is_file():
            return self._toml_document_codec.serialize(incoming_config)

        existing_config = self._toml_document_codec.parse(
            config_path.read_text(encoding="utf-8")
        )
        return self._toml_document_codec.serialize(
            merge_known_values(existing_config, incoming_config)
        )

    def _clear_codex_auth_state(self) -> None:
        """Remove Codex CLI auth state while preserving settings such as env vars."""
        auth_path = self.codex_auth_dir / "auth.json"
        if auth_path.exists():
            auth_path.unlink()
        installation_path = self.codex_auth_dir / "installation_id"
        if installation_path.exists():
            installation_path.unlink()
        os.environ[self._codex_login_status_env] = "notConnected"

    def _sync_codex_environment_variables(
        self,
        environment_variables: List[EnvironmentVariable],
    ) -> List[str]:
        """Write managed Codex environment variables into the shell profile."""
        managed_keys = {"CODEX_HOME"}
        invalid_keys = [
            env_var.key
            for env_var in environment_variables
            if env_var.key and env_var.key.strip().upper() in managed_keys
        ]
        if invalid_keys:
            raise ValueError(
                "CODEX_HOME is managed by the system and cannot be overridden"
            )

        return self._write_managed_env_block(
            environment_variables,
            "# Aileron - Codex Environment Variables - START\n",
            "# Aileron - Codex Environment Variables - END\n",
        )

    def _write_managed_env_block(
        self,
        environment_variables: List[EnvironmentVariable],
        marker_start: str,
        marker_end: str,
    ) -> List[str]:
        """Replace a managed shell profile environment variable block."""
        bashrc_path = self.home_dir / ".bashrc"
        existing_lines = []
        if bashrc_path.exists():
            existing_lines = bashrc_path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )

        filtered_lines = []
        skip = False
        for line in existing_lines:
            if line == marker_start:
                skip = True
                continue
            if line == marker_end:
                skip = False
                continue
            if not skip:
                filtered_lines.append(line)

        synced_keys: List[str] = []
        new_env_lines = []
        valid_vars = [
            env_var
            for env_var in environment_variables
            if env_var.key and env_var.key.strip() and env_var.value
        ]
        if valid_vars:
            new_env_lines.append(marker_start)
            for env_var in valid_vars:
                escaped_value = (
                    env_var.value.replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("$", "\\$")
                    .replace("`", "\\`")
                )
                key = env_var.key.strip()
                new_env_lines.append(f'export {key}="{escaped_value}"\n')
                synced_keys.append(key)
                os.environ[key] = env_var.value
                logger.debug("Managed environment variable set: %s", key)
            new_env_lines.append(marker_end)

        bashrc_path.write_text(
            "".join(filtered_lines + new_env_lines), encoding="utf-8"
        )
        return synced_keys

    async def setup_git_settings(self, request: GitSettingsRequest) -> Dict[str, str]:
        """Setup Git global settings"""
        try:
            logger.info("Starting Git global settings setup")

            results = {}

            # Set Git user name
            subprocess.run(
                ["git", "config", "--global", "user.name", request.user_name],
                capture_output=True,
                text=True,
                check=True,
            )
            results["user_name_set"] = request.user_name
            logger.debug(f"Git user name configured: {request.user_name}")

            # Set Git user email
            subprocess.run(
                ["git", "config", "--global", "user.email", request.user_email],
                capture_output=True,
                text=True,
                check=True,
            )
            results["user_email_set"] = request.user_email
            logger.debug(f"Git user email configured: {request.user_email}")

            # Verify settings
            verify_name = subprocess.run(
                ["git", "config", "--global", "user.name"],
                capture_output=True,
                text=True,
                check=True,
            )
            verify_email = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True,
                text=True,
                check=True,
            )

            results["verified_name"] = verify_name.stdout.strip()
            results["verified_email"] = verify_email.stdout.strip()

            logger.info("Git global settings completed")
            return results

        except subprocess.CalledProcessError as e:
            logger.error(f"Git command execution failed: {e}")
            raise Exception(f"Git configuration failed: {e}")
        except Exception as e:
            logger.error(f"Git settings setup failed: {e}")
            raise

    async def get_setup_status(self) -> Dict[str, Dict[str, str]]:
        """Check status of all sync items"""
        return {
            "ssh": self._check_ssh_status(),
            "claudeCode": self._check_claude_status(),
            "codex": self._check_codex_status(),
            "git": self._check_git_status(),
        }

    def _check_ssh_status(self) -> Dict[str, str]:
        try:
            private_key_path = self.ssh_dir / "id_rsa"
            public_key_path = self.ssh_dir / "id_rsa.pub"
            authorized_keys_path = self.ssh_dir / "authorized_keys"

            has_private = (
                private_key_path.is_file() and private_key_path.stat().st_size > 0
            )
            has_public = (
                public_key_path.is_file() and public_key_path.stat().st_size > 0
            )
            has_authorized_keys = (
                authorized_keys_path.is_file()
                and authorized_keys_path.stat().st_size > 0
            )

            # Complete check: private key, public key, and authorized_keys all exist
            if has_private and has_public and has_authorized_keys:
                # Additional verification: check if authorized_keys contains current public key
                try:
                    public_key_content = public_key_path.read_text().strip()
                    authorized_keys_content = authorized_keys_path.read_text()

                    if public_key_content in authorized_keys_content:
                        return {
                            "status": "success",
                            "message": "SSH Keys ready and authorized_keys configured",
                        }
                    else:
                        return {
                            "status": "failed",
                            "message": "authorized_keys does not contain current public key, please re-sync",
                        }
                except Exception as read_exc:
                    logger.warning(f"Failed to read SSH file content: {read_exc}")
                    return {"status": "success", "message": "SSH Keys ready"}

            # Basic check: only check private key and public key
            if has_private and has_public:
                if not has_authorized_keys:
                    return {
                        "status": "failed",
                        "message": "SSH Keys exist but authorized_keys not configured, please re-sync",
                    }
                return {"status": "success", "message": "SSH Keys ready"}

            if has_private or has_public or has_authorized_keys:
                return {
                    "status": "failed",
                    "message": "SSH Keys setup incomplete, please re-sync",
                }

            return {"status": "pending", "message": "SSH Keys not yet synced"}
        except Exception as exc:
            logger.error(f"Failed to check SSH Keys status: {exc}")
            return {"status": "failed", "message": f"Check failed: {exc}"}

    def _check_claude_status(self) -> Dict[str, str]:
        try:
            credentials_paths = [self.claude_dir / self._credentials_filename]
            credentials_path = next(
                (path for path in credentials_paths if path.is_file()), None
            )

            credentials_data = None
            if credentials_path and credentials_path.stat().st_size > 0:
                try:
                    credentials_data = self._json_document_codec.parse(
                        credentials_path.read_text(encoding="utf-8")
                    )
                except Exception as cred_exc:
                    logger.warning(
                        f"Failed to read Claude Code credentials file: {cred_exc}"
                    )

            recorded_auth_method = os.environ.get(self._auth_method_env)
            recorded_env_keys = [
                key.strip()
                for key in (os.environ.get(self._env_keys_env) or "").split(",")
                if key.strip()
            ]

            auth_method = recorded_auth_method
            if not auth_method and isinstance(credentials_data, dict):
                auth_method = credentials_data.get("authMethod")
                if not auth_method and "claudeAiOauth" in credentials_data:
                    auth_method = "subscription"

            if auth_method == "subscription":
                if (
                    credentials_path
                    and credentials_path.stat().st_size > 0
                    and (
                        self._has_claude_subscription_credentials(credentials_data)
                        or self._has_claude_user_state()
                    )
                ):
                    return {
                        "status": "success",
                        "message": "Claude Code subscription credentials synced",
                    }
                return {
                    "status": "pending",
                    "message": "Claude Code subscription credentials not yet synced",
                }

            # API Key mode, check user-configured environment variables
            if recorded_env_keys:
                missing_keys = [
                    key for key in recorded_env_keys if not os.environ.get(key)
                ]
                if missing_keys:
                    return {
                        "status": "failed",
                        "message": f"Missing required environment variables: {', '.join(missing_keys)}",
                    }
                return {
                    "status": "success",
                    "message": "Claude Code environment variables synced",
                }

            # If no environment variables recorded, not yet configured
            if auth_method == "api_key":
                return {
                    "status": "pending",
                    "message": "Claude Code environment variables not yet configured",
                }

            return {
                "status": "pending",
                "message": "Claude Code settings not yet synced",
            }
        except Exception as exc:
            logger.error(f"Failed to check Claude Code status: {exc}")
            return {"status": "failed", "message": f"Check failed: {exc}"}

    def _has_claude_subscription_credentials(self, credentials_data: Any) -> bool:
        """Check if .credentials.json contains subscription OAuth token material."""
        if not isinstance(credentials_data, dict):
            return False
        if credentials_data.get("authMethod") != "subscription":
            return False
        oauth_data = credentials_data.get("claudeAiOauth")
        return isinstance(oauth_data, dict) and bool(oauth_data.get("accessToken"))

    def _has_claude_user_state(self) -> bool:
        """Check if .claude.json contains minimal login-ready user state."""
        claude_json_path = self._claude_user_state_path()
        if not claude_json_path.is_file() or claude_json_path.stat().st_size <= 0:
            return False

        try:
            claude_json_data = self._json_document_codec.parse(
                claude_json_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            logger.warning("Failed to read .claude.json for status check: %s", exc)
            return False

        oauth_account = claude_json_data.get("oauthAccount")
        projects = claude_json_data.get("projects")
        workspace_state = (
            projects.get("/workspace") if isinstance(projects, dict) else None
        )
        return (
            isinstance(oauth_account, dict)
            and bool(
                oauth_account.get("emailAddress") or oauth_account.get("accountUuid")
            )
            and isinstance(workspace_state, dict)
            and workspace_state.get("hasTrustDialogAccepted") is True
        )

    def _check_codex_status(self) -> Dict[str, str]:
        try:
            auth_path = self.codex_auth_dir / "auth.json"
            recorded_login_status = os.environ.get(self._codex_login_status_env)
            recorded_env_keys = [
                key.strip()
                for key in (os.environ.get(self._codex_env_keys_env) or "").split(",")
                if key.strip()
            ]

            missing_keys = [key for key in recorded_env_keys if not os.environ.get(key)]
            if missing_keys:
                return {
                    "status": "failed",
                    "message": f"Missing required Codex environment variables: {', '.join(missing_keys)}",
                }

            if auth_path.is_file() and auth_path.stat().st_size > 0:
                return {"status": "success", "message": "Codex CLI login synced"}

            if recorded_login_status in {"connected", "needsRelogin", "error"}:
                return {
                    "status": "pending",
                    "message": "Codex CLI login requires re-login",
                }

            if recorded_env_keys:
                return {
                    "status": "success",
                    "message": "Codex environment variables synced",
                }

            return {"status": "pending", "message": "Codex settings not yet synced"}
        except Exception as exc:
            logger.error("Failed to check Codex status: %s", exc)
            return {"status": "failed", "message": f"Check failed: {exc}"}

    def _check_git_status(self) -> Dict[str, str]:
        try:
            name_result = subprocess.run(
                ["git", "config", "--global", "user.name"],
                capture_output=True,
                text=True,
            )
            email_result = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True,
                text=True,
            )

            user_name = (
                name_result.stdout.strip() if name_result.returncode == 0 else ""
            )
            user_email = (
                email_result.stdout.strip() if email_result.returncode == 0 else ""
            )

            if user_name and user_email:
                return {"status": "success", "message": "Git user info configured"}
            if user_name or user_email:
                return {
                    "status": "failed",
                    "message": "Git configuration incomplete, please re-sync",
                }
            return {"status": "pending", "message": "Git settings not yet synced"}
        except Exception as exc:
            logger.error(f"Failed to check Git status: {exc}")
            return {"status": "failed", "message": f"Check failed: {exc}"}

    async def apply_firewall_settings(
        self, request: FirewallConfigRequest
    ) -> Dict[str, str]:
        """Apply firewall settings"""
        try:
            logger.info("Starting firewall settings application")
            logger.debug(f"Firewall configuration: {request.model_dump()}")

            # Read firewall script template
            template_path = Path(
                "/workspace-runtime/app/modules/internal/templates/firewall.sh.j2"
            )
            if not template_path.exists():
                raise FileNotFoundError(
                    f"Firewall script template does not exist: {template_path}"
                )

            template_content = template_path.read_text()
            template = Template(template_content)

            # Docker enforcement happens inside the runtime container by rendering
            # and executing an iptables script for the workspace runtime scope.
            script_content = template.render(
                firewall={
                    "egress_mode": request.egress_mode,
                    "allowed_domains": request.allowed_domains,
                }
            )

            # Write temporary script file
            script_path = Path("/tmp/firewall_apply.sh")
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            logger.debug(f"Firewall script generated: {script_path}")

            # Execute firewall script (requires sudo privileges)
            result = subprocess.run(
                ["sudo", "bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                error_msg = f"Firewall script execution failed: {result.stderr}"
                logger.error(error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "output": result.stdout,
                }

            logger.info("Firewall settings successfully applied")
            return {
                "status": "success",
                "message": "Firewall settings successfully applied",
                "output": result.stdout,
            }

        except subprocess.TimeoutExpired:
            error_msg = "Firewall script execution timeout"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        except Exception as exc:
            error_msg = f"Failed to apply firewall settings: {exc}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}


__all__ = ["InternalService"]
