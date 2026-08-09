"""UserSettingsService"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.config.model_registry import (
    AgenticToolId,
    normalize_model_selection,
    selection_to_persisted,
)
from app.db import models as db_models
from app.modules.settings.models import (
    ClaudeCodeSettings,
    CodexAccountInfo,
    CodexAuthFlow,
    CodexSettings,
    GeneralSettings,
    GitSettings,
    OpenCodeSettings,
    SSHSettings,
    UserSettings,
    UserSettingsUpdate,
)
from app.modules.workspace.capabilities import build_capabilities_from_settings
from app.modules.settings.models import SSHKeyPairResponse, default_tool_model

logger = logging.getLogger(__name__)


class SettingsService:
    """Handle user personal data and settings"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- UserSettings -------------------------------------------------------

    def get_settings(self, user_id: str) -> Optional[UserSettings]:
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None

        settings = self._get_or_create_settings(user)
        return self._build_user_settings(settings)

    def update_settings(
        self, user_id: str, payload: UserSettingsUpdate
    ) -> Optional[UserSettings]:
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None

        settings = self._get_or_create_settings(user)

        data = payload.model_dump(exclude_unset=True, by_alias=True)

        if "general" in data and isinstance(data["general"], dict):
            settings.general_settings = self._merge_dict(
                settings.general_settings or {}, data["general"]
            )
            # Mark JSONB column as modified
            flag_modified(settings, "general_settings")

        if "ssh" in data and isinstance(data["ssh"], dict):
            ssh_data = data["ssh"]
            old_private_key = settings.ssh_private_key
            old_public_key = settings.ssh_public_key

            settings.ssh_public_key = ssh_data.get("publicKey", settings.ssh_public_key)
            settings.ssh_private_key = ssh_data.get(
                "privateKey", settings.ssh_private_key
            )
            settings.ssh_fingerprint = ssh_data.get(
                "fingerprint", settings.ssh_fingerprint
            )
            last_rotated_at = ssh_data.get("lastRotatedAt")
            if (
                last_rotated_at
                and isinstance(last_rotated_at, str)
                and last_rotated_at != "null"
            ):
                try:
                    settings.ssh_last_rotated_at = datetime.fromisoformat(
                        last_rotated_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    # If date format error, keep original value
                    pass

            # If SSH key changed, sync to file system
            if (
                settings.ssh_private_key != old_private_key
                or settings.ssh_public_key != old_public_key
            ):
                if settings.ssh_private_key and settings.ssh_public_key:
                    try:
                        self._write_ssh_keys_to_filesystem(
                            settings.ssh_private_key, settings.ssh_public_key
                        )
                    except Exception as e:
                        logger.warning(f"Failed to write SSH key to filesystem: {e}")

        if "claudeCode" in data and isinstance(data["claudeCode"], dict):
            claude_data = self._persist_model_selection("claude", data["claudeCode"])

            # Handle basic settings
            if "authKey" in claude_data:
                settings.claude_auth_key = claude_data["authKey"]
            if "model" in claude_data:
                settings.claude_selected_model = claude_data["model"]

            # Handle new settings column, stored in additional_settings
            additional_settings = settings.additional_settings or {}
            claude_additional = additional_settings.get("claudeCode", {})

            # Update new ClaudeCodeSettings column
            if "authMethod" in claude_data:
                claude_additional["authMethod"] = claude_data["authMethod"]
            if "subscriptionAuthCode" in claude_data:
                claude_additional["subscriptionAuthCode"] = claude_data[
                    "subscriptionAuthCode"
                ]
            if "subscriptionAccessToken" in claude_data:
                claude_additional["subscriptionAccessToken"] = claude_data[
                    "subscriptionAccessToken"
                ]
            if "subscriptionRefreshToken" in claude_data:
                claude_additional["subscriptionRefreshToken"] = claude_data[
                    "subscriptionRefreshToken"
                ]
            if "subscriptionExpiresAt" in claude_data:
                claude_additional["subscriptionExpiresAt"] = claude_data[
                    "subscriptionExpiresAt"
                ]
            if "oauthAccount" in claude_data:
                claude_additional["oauthAccount"] = claude_data["oauthAccount"]
            if "apiProvider" in claude_data:
                claude_additional["apiProvider"] = claude_data["apiProvider"]
            if "environmentVariables" in claude_data:
                claude_additional["environmentVariables"] = claude_data[
                    "environmentVariables"
                ]
            if "modelSelection" in claude_data:
                claude_additional["modelSelection"] = claude_data["modelSelection"]

            additional_settings["claudeCode"] = claude_additional
            settings.additional_settings = additional_settings
            # Mark JSONB column as modified
            flag_modified(settings, "additional_settings")

        if "codex" in data and isinstance(data["codex"], dict):
            codex_data = self._persist_model_selection("codex", data["codex"])
            additional_settings = settings.additional_settings or {}
            codex_additional = additional_settings.get("codex", {})

            for key in (
                "authMethod",
                "loginStatus",
                "account",
                "model",
                "environmentVariables",
                "authFlow",
                "cliState",
                "lastSyncedAt",
                "lastSyncError",
                "modelSelection",
            ):
                if key in codex_data:
                    codex_additional[key] = codex_data[key]

            additional_settings["codex"] = codex_additional
            settings.additional_settings = additional_settings
            flag_modified(settings, "additional_settings")

        if "opencode" in data and isinstance(data["opencode"], dict):
            opencode_data = self._persist_model_selection("opencode", data["opencode"])
            additional_settings = settings.additional_settings or {}
            opencode_additional = additional_settings.get("opencode", {})

            for key in ("model", "environmentVariables", "modelSelection"):
                if key in opencode_data:
                    opencode_additional[key] = opencode_data[key]

            additional_settings["opencode"] = opencode_additional
            settings.additional_settings = additional_settings
            flag_modified(settings, "additional_settings")

        if "git" in data and isinstance(data["git"], dict):
            git_data = data["git"]
            if "userName" in git_data:
                settings.git_user_name = git_data["userName"]
            if "userEmail" in git_data:
                settings.git_user_email = git_data["userEmail"]
            if "signingKey" in git_data:
                settings.git_signing_key = git_data["signingKey"]

        settings.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(settings)
        return self._build_user_settings(settings)

    def detect_setting_changes(
        self, old_settings: UserSettings, new_data: dict
    ) -> dict:
        """Detect which settings actually changed"""
        changes = {}
        new_settings = old_settings.model_copy(deep=True)
        model_selection_changed = False

        # Detect SSH settings changes
        if "ssh" in new_data:
            ssh_data = new_data["ssh"]
            old_ssh = old_settings.ssh

            # Compare if SSH keys changed
            if (
                ssh_data.get("privateKey") != old_ssh.private_key
                or ssh_data.get("publicKey") != old_ssh.public_key
            ):
                changes["ssh"] = {
                    "privateKey": ssh_data.get("privateKey"),
                    "publicKey": ssh_data.get("publicKey"),
                }

        # Detect Claude Code settings changes
        if "claudeCode" in new_data:
            claude_data = new_data["claudeCode"]
            old_claude = old_settings.claude_code

            # Check if there are any changes
            has_changes = False
            claude_changes = {}

            # Compare authentication method
            if (
                "authMethod" in claude_data
                and claude_data["authMethod"] != old_claude.auth_method
            ):
                has_changes = True
                claude_changes["authMethod"] = claude_data["authMethod"]

            # Compare OAuth tokens
            for key, old_value in (
                ("subscriptionAccessToken", old_claude.subscription_access_token),
                ("subscriptionRefreshToken", old_claude.subscription_refresh_token),
                ("subscriptionExpiresAt", old_claude.subscription_expires_at),
            ):
                if key in claude_data and claude_data[key] != old_value:
                    has_changes = True
                    claude_changes[key] = claude_data[key]

            if "oauthAccount" in claude_data:
                old_oauth_account = (
                    old_claude.oauth_account.model_dump(by_alias=True)
                    if old_claude.oauth_account
                    else None
                )
                if claude_data.get("oauthAccount") != old_oauth_account:
                    has_changes = True
                    claude_changes["oauthAccount"] = claude_data.get("oauthAccount")

            if "model" in claude_data and claude_data["model"] != old_claude.model:
                has_changes = True
                claude_changes["model"] = claude_data["model"]

            # Compare API Key
            if (
                "authKey" in claude_data
                and claude_data["authKey"] != old_claude.auth_key
            ):
                has_changes = True
                claude_changes["authKey"] = claude_data["authKey"]

            # CompareEnvironmentVariable
            if "environmentVariables" in claude_data:
                new_env_vars = claude_data["environmentVariables"]
                old_env_vars = old_claude.environment_variables
                if self._env_vars_changed(old_env_vars, new_env_vars):
                    has_changes = True
                    claude_changes["environmentVariables"] = new_env_vars

            if "modelSelection" in claude_data:
                normalized_selection = normalize_model_selection(
                    "claude", claude_data["modelSelection"], mode="update"
                )
                selection = old_claude.model_selection.model_validate(
                    normalized_selection.model_dump(by_alias=True)
                )
                if selection != old_claude.model_selection:
                    new_settings.claude_code.model_selection = selection
                    model_selection_changed = True

            if has_changes:
                changes["claudeCode"] = claude_changes

        if "codex" in new_data:
            codex_data = new_data["codex"]
            old_codex = old_settings.codex
            has_changes = False
            codex_changes = {}

            for key, old_value in (
                ("authMethod", old_codex.auth_method),
                ("loginStatus", old_codex.login_status),
                ("model", old_codex.model),
            ):
                if key in codex_data and codex_data.get(key) != old_value:
                    has_changes = True
                    codex_changes[key] = codex_data.get(key)

            if "account" in codex_data:
                old_account = (
                    old_codex.account.model_dump(by_alias=True)
                    if old_codex.account
                    else None
                )
                if codex_data.get("account") != old_account:
                    has_changes = True
                    codex_changes["account"] = codex_data.get("account")

            if "authFlow" in codex_data:
                old_auth_flow = (
                    old_codex.auth_flow.model_dump(by_alias=True)
                    if old_codex.auth_flow
                    else None
                )
                if codex_data.get("authFlow") != old_auth_flow:
                    has_changes = True
                    codex_changes["authFlow"] = codex_data.get("authFlow")

            new_env_vars = codex_data.get("environmentVariables", [])
            if "environmentVariables" in codex_data and self._env_vars_changed(
                old_codex.environment_variables,
                new_env_vars,
            ):
                has_changes = True
                codex_changes["environmentVariables"] = new_env_vars

            if "modelSelection" in codex_data:
                normalized_selection = normalize_model_selection(
                    "codex", codex_data["modelSelection"], mode="update"
                )
                selection = old_codex.model_selection.model_validate(
                    normalized_selection.model_dump(by_alias=True)
                )
                if selection != old_codex.model_selection:
                    new_settings.codex.model_selection = selection
                    model_selection_changed = True

            if has_changes:
                changes["codex"] = codex_changes

        if "opencode" in new_data and "modelSelection" in new_data["opencode"]:
            normalized_selection = normalize_model_selection(
                "opencode", new_data["opencode"]["modelSelection"], mode="update"
            )
            selection = old_settings.opencode.model_selection.model_validate(
                normalized_selection.model_dump(by_alias=True)
            )
            if selection != old_settings.opencode.model_selection:
                new_settings.opencode.model_selection = selection
                model_selection_changed = True

        if model_selection_changed:
            changes["capabilities"] = build_capabilities_from_settings(
                new_settings
            ).model_dump(by_alias=True)

        # Detect Git settings changes
        if "git" in new_data:
            git_data = new_data["git"]
            old_git = old_settings.git

            if (
                git_data.get("userName") != old_git.user_name
                or git_data.get("userEmail") != old_git.user_email
            ):
                changes["git"] = {
                    "userName": git_data.get("userName"),
                    "userEmail": git_data.get("userEmail"),
                }

        return changes

    def _persist_model_selection(
        self,
        tool_id: AgenticToolId,
        payload: dict,
    ) -> dict:
        raw_selection = payload.get("modelSelection")
        if raw_selection is None:
            return payload

        selection = normalize_model_selection(tool_id, raw_selection, mode="update")
        return {
            **payload,
            "modelSelection": selection_to_persisted(selection),
        }

    def _env_vars_changed(self, old_vars: list, new_vars: list) -> bool:
        """Compare if environment variable list changed"""
        if len(old_vars) != len(new_vars):
            return True

        # Convert to dictionary for comparison
        old_dict = {var.key: var.value for var in old_vars}
        new_dict = {
            var.get("key"): var.get("value") for var in new_vars if var.get("key")
        }

        return old_dict != new_dict

    # -- Private functions ---------------------------------------------------------

    def _get_or_create_settings(self, user: db_models.User) -> db_models.UserSetting:
        settings = user.settings
        if settings:
            return settings

        settings = db_models.UserSetting(
            id=str(uuid4()),
            user_id=user.id,
            claude_selected_model=default_tool_model("claude"),
            general_settings=GeneralSettings().model_dump(by_alias=True),
        )
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)
        return settings

    def _build_user_settings(self, settings: db_models.UserSetting) -> UserSettings:
        general = settings.general_settings or {}
        general_model = GeneralSettings(**general)

        ssh_model = SSHSettings(
            public_key=settings.ssh_public_key,
            private_key=settings.ssh_private_key,
            fingerprint=settings.ssh_fingerprint,
            last_rotated_at=settings.ssh_last_rotated_at,
        )

        additional_settings = settings.additional_settings or {}
        claude_additional = additional_settings.get("claudeCode", {})
        codex_additional = additional_settings.get("codex", {})
        opencode_additional = additional_settings.get("opencode", {})

        claude_model_selection = normalize_model_selection(
            "claude",
            claude_additional.get("modelSelection"),
            mode="read",
        )
        codex_model_selection = normalize_model_selection(
            "codex",
            codex_additional.get("modelSelection"),
            mode="read",
        )
        opencode_model_selection = normalize_model_selection(
            "opencode",
            opencode_additional.get("modelSelection"),
            mode="read",
        )

        # Handle oauthAccount
        oauth_account = None
        oauth_account_data = claude_additional.get("oauthAccount")
        if oauth_account_data:
            from app.modules.settings.models import OAuthAccountInfo

            oauth_account = OAuthAccountInfo(**oauth_account_data)

        # Handle subscription_expires_at: convert empty string to None
        subscription_expires_at = claude_additional.get("subscriptionExpiresAt")
        if subscription_expires_at == "":
            subscription_expires_at = None

        claude_model = ClaudeCodeSettings(
            auth_key=settings.claude_auth_key,
            model=settings.claude_selected_model,
            auth_method=claude_additional.get("authMethod", "subscription"),
            subscription_auth_code=claude_additional.get("subscriptionAuthCode")
            or None,
            subscription_access_token=claude_additional.get("subscriptionAccessToken")
            or None,
            subscription_refresh_token=claude_additional.get("subscriptionRefreshToken")
            or None,
            subscription_expires_at=subscription_expires_at,
            oauth_account=oauth_account,
            api_provider=claude_additional.get("apiProvider") or None,
            environment_variables=claude_additional.get("environmentVariables", []),
            model_selection=claude_model_selection,
        )

        codex_account = None
        codex_account_data = codex_additional.get("account")
        if codex_account_data:
            codex_account = CodexAccountInfo(**codex_account_data)

        codex_auth_flow = None
        codex_auth_flow_data = codex_additional.get("authFlow")
        if codex_auth_flow_data:
            codex_auth_flow = CodexAuthFlow(**codex_auth_flow_data)

        codex_cli_state = None
        codex_cli_state_data = codex_additional.get("cliState")
        if codex_cli_state_data:
            from app.modules.settings.models import CodexCliState

            codex_cli_state = CodexCliState(**codex_cli_state_data)

        codex_model = CodexSettings(
            auth_method=codex_additional.get("authMethod", "subscription"),
            login_status=codex_additional.get("loginStatus", "notConnected"),
            account=codex_account,
            model=codex_additional.get("model") or default_tool_model("codex"),
            environment_variables=codex_additional.get("environmentVariables", []),
            auth_flow=codex_auth_flow,
            cli_state=codex_cli_state,
            last_synced_at=codex_additional.get("lastSyncedAt"),
            last_sync_error=codex_additional.get("lastSyncError"),
            model_selection=codex_model_selection,
        )

        opencode_model = OpenCodeSettings(
            model=opencode_additional.get("model") or OpenCodeSettings().model,
            environment_variables=opencode_additional.get("environmentVariables", []),
            model_selection=opencode_model_selection,
        )

        git_model = GitSettings(
            user_name=settings.git_user_name,
            user_email=settings.git_user_email,
            signing_key=settings.git_signing_key,
        )

        return UserSettings(
            general=general_model,
            ssh=ssh_model,
            claude_code=claude_model,
            codex=codex_model,
            opencode=opencode_model,
            git=git_model,
        )

    @staticmethod
    def _merge_dict(original: dict, updates: dict) -> dict:
        merged = dict(original)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(original.get(key), dict):
                merged[key] = SettingsService._merge_dict(original[key], value)
            else:
                merged[key] = value
        return merged

    # -- SSH Key management -----------------------------------------------------

    def generate_and_save_ssh_keys(self, user_id: str) -> Optional[SSHKeyPairResponse]:
        """Generate new SSH key pair and save to user settings"""
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None

        # Generate SSH key pair
        private_key, public_key = self._generate_ssh_key_pair()

        # Calculate fingerprint
        fingerprint = self._calculate_ssh_fingerprint(public_key)

        # Save to database
        settings = self._get_or_create_settings(user)
        settings.ssh_private_key = private_key
        settings.ssh_public_key = public_key
        settings.ssh_fingerprint = fingerprint
        settings.ssh_last_rotated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(settings)

        # Also write SSH key to workspace-manager's ~/.ssh directory
        # So workspace-manager can use these keys to clone private repositories
        try:
            self._write_ssh_keys_to_filesystem(private_key, public_key)
        except Exception as e:
            logger.warning(f"Failed to write SSH key to filesystem: {e}")
            # Do not affect main process, continue execution

        return SSHKeyPairResponse(
            public_key=public_key,
            private_key=private_key,
            fingerprint=fingerprint,
            generated_at=settings.ssh_last_rotated_at,
        )

    @staticmethod
    def _generate_ssh_key_pair() -> tuple[str, str]:
        """Generate SSH key pair using ssh-keygen"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "id_rsa"

            # Use ssh-keygen to generate keys
            # -t rsa: Use RSA algorithm
            # -b 4096: 4096-bit key length
            # -f: Specify output file
            # -N "": No password
            # -C: Comment (use timestamp)
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t",
                    "rsa",
                    "-b",
                    "4096",
                    "-f",
                    str(key_path),
                    "-N",
                    "",
                    "-C",
                    f"generated-{datetime.utcnow().isoformat()}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            # Read private key
            private_key = key_path.read_text()

            # Read public key
            public_key = (key_path.with_suffix(".pub")).read_text().strip()

            return private_key, public_key

    @staticmethod
    def _calculate_ssh_fingerprint(public_key: str) -> str:
        """Calculate SSH public key fingerprint (SHA256)"""
        # Get base64 part of public key
        parts = public_key.split()
        if len(parts) < 2:
            return ""

        import base64

        key_data = base64.b64decode(parts[1])

        # Calculate SHA256 hash
        sha256_hash = hashlib.sha256(key_data).digest()

        # Convert to base64 and remove padding
        fingerprint = base64.b64encode(sha256_hash).decode().rstrip("=")

        return f"SHA256:{fingerprint}"

    @staticmethod
    def _write_ssh_keys_to_filesystem(private_key: str, public_key: str) -> None:
        """
        Write SSH keys to workspace-manager filesystem

        This allows workspace-manager to use these keys for Git authentication

        Args:
            private_key: SSH private key content
            public_key: SSH public key content
        """
        # Determine SSH directory path
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        # Write private key
        private_key_path = ssh_dir / "id_rsa"
        private_key_content = private_key
        if not private_key_content.endswith("\n"):
            private_key_content += "\n"
        private_key_path.write_text(private_key_content)
        private_key_path.chmod(0o600)
        logger.info(f"SSH private key written: {private_key_path}")

        # Write public key
        public_key_path = ssh_dir / "id_rsa.pub"
        public_key_content = public_key
        if not public_key_content.endswith("\n"):
            public_key_content += "\n"
        public_key_path.write_text(public_key_content)
        public_key_path.chmod(0o644)
        logger.info(f"SSH public key written: {public_key_path}")

        # Configure known_hosts (avoid prompts on first connection)
        known_hosts_path = ssh_dir / "known_hosts"
        if not known_hosts_path.exists():
            known_hosts_path.touch(mode=0o644)
            logger.info(f"Created known_hosts: {known_hosts_path}")


__all__ = ["SettingsService"]
