"""Internal API Business Logic Service"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Template

from app.config.settings import get_settings
from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.settings import (
    ClaudeCodeSettingsUpdateRequest,
    SettingsService,
)

from .models import ClaudeCodeRequest, FirewallConfigRequest, GitSettingsRequest, SSHKeysRequest

logger = logging.getLogger(__name__)


class InternalService:
    """Internal API business logic service"""

    def __init__(self):
        self.home_dir = Path("/home/developer")
        self.ssh_dir = self.home_dir / ".ssh"
        self.claude_dir = self.home_dir / ".claude"
        self._credentials_filename = ".credentials.json"
        self._env_keys_env = "CLAUDE_CODE_SYNCED_KEYS"
        self._auth_method_env = "CLAUDE_CODE_AUTH_METHOD"
        runtime_settings = get_settings()
        self._workspace_id = runtime_settings.WORKSPACE_ID
        self._claude_settings_service = SettingsService()

    async def setup_ssh_keys(self, request: SSHKeysRequest) -> Dict[str, str]:
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
            if not private_key_content.endswith('\n'):
                private_key_content += '\n'
            private_key_path.write_text(private_key_content)
            private_key_path.chmod(0o600)
            logger.debug(f"Private key configured: {private_key_path}")

            # Write public key
            public_key_path = self.ssh_dir / "id_rsa.pub"
            # Ensure public key ends with newline
            public_key_content = request.public_key
            if not public_key_content.endswith('\n'):
                public_key_content += '\n'
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
                    if line.strip() and not line.strip().startswith('#')
                }
                logger.debug(f"Existing authorized_keys contains {len(existing_keys)} keys")

            # Get current public key fingerprint (to check if already exists)
            new_key = public_key_content.strip()

            # Check if identical key already exists
            if new_key in existing_keys:
                logger.info("Public key already exists in authorized_keys, no need to add duplicate")
                authorized_keys_added = False
            else:
                # Add new public key to set
                existing_keys.add(new_key)
                logger.info("Adding public key to authorized_keys")

                # Write authorized_keys
                authorized_keys_content = '\n'.join(sorted(existing_keys)) + '\n'
                authorized_keys_path.write_text(authorized_keys_content)
                authorized_keys_path.chmod(0o600)
                authorized_keys_added = True
                logger.debug(f"authorized_keys updated, now contains {len(existing_keys)} keys")

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

    async def setup_claude_code(self, request: ClaudeCodeRequest) -> Dict[str, str]:
        """Setup Claude Code"""
        try:
            logger.info("Starting Claude Code setup")

            # Debug: Log received request data
            logger.info(f"Received request: auth_method={request.auth_method}")
            logger.info(f"subscription_access_token exists: {bool(request.subscription_access_token)}")
            logger.info(f"subscription_refresh_token exists: {bool(request.subscription_refresh_token)}")
            logger.info(f"subscription_expires_at: {request.subscription_expires_at}")

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
            if resolved_auth_method == "subscription" and request.subscription_access_token:
                expires_at_ms = self._normalize_expires_at(request.subscription_expires_at)
                logger.info(f"Subscription expiresAt parsing result: {expires_at_ms}")

                credentials_data = {
                    "authMethod": "subscription",
                    "claudeAiOauth": {
                        "accessToken": request.subscription_access_token,
                        "refreshToken": request.subscription_refresh_token,
                        "expiresAt": expires_at_ms,
                        "scopes": ["user:inference", "user:profile"],
                        "subscriptionType": "pro"
                    }
                }

                credentials_path.write_text(json.dumps(credentials_data, indent=2))
                credentials_path.chmod(0o600)
                logger.debug(f"Credentials file created: {credentials_path}")
                logger.info("Stored Subscription OAuth Token (Claude Code format)")

                # Write oauthAccount info to ~/.claude.json
                if request.oauth_account:
                    claude_json_path = self.home_dir / ".claude.json"
                    claude_json_data = {}

                    # Read existing .claude.json (if exists)
                    if claude_json_path.exists():
                        try:
                            claude_json_data = json.loads(claude_json_path.read_text())
                            logger.debug(f"Read existing .claude.json: {len(claude_json_data)} fields")
                        except Exception as e:
                            logger.warning(f"Failed to read existing .claude.json: {e}, will create new file")

                    # Update oauthAccount field
                    claude_json_data["oauthAccount"] = {
                        "accountUuid": request.oauth_account.account_uuid,
                        "emailAddress": request.oauth_account.email_address,
                        "organizationUuid": request.oauth_account.organization_uuid,
                        "displayName": request.oauth_account.display_name,
                        "organizationBillingType": request.oauth_account.organization_billing_type,
                        "organizationRole": request.oauth_account.organization_role,
                        "workspaceRole": request.oauth_account.workspace_role,
                        "organizationName": request.oauth_account.organization_name,
                    }

                    # Write .claude.json
                    claude_json_path.write_text(json.dumps(claude_json_data, indent=2))
                    logger.info(f"Stored OAuth account info to ~/.claude.json: {request.oauth_account.email_address} ({request.oauth_account.display_name})")
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
                            escaped_value = env_var.value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
                            new_env_lines.append(f'export {env_var.key}="{escaped_value}"\n')
                            synced_keys.append(env_var.key)
                            env_vars_set.append(f"{env_var.key}={env_var.value}")
                            logger.debug(f"Environment variable set: {env_var.key}")
                        else:
                            logger.warning(f"Skipping empty environment variable: key={env_var.key}, value={'<empty>' if not env_var.value else '<set>'}")
                    new_env_lines.append(marker_end)

                # Write back to .bashrc
                with open(bashrc_path, "w", encoding="utf-8") as f:
                    f.writelines(filtered_lines)
                    f.writelines(new_env_lines)

                logger.info(f"Updated {bashrc_path}, set {len(synced_keys)} environment variables")
            else:
                logger.info("Using Subscription authentication mode, skipping environment variable sync")

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

            logger.info(f"Claude Code setup completed, set {len(env_vars_set)} environment variables")
            return {
                "credentials_path": str(credentials_path),
                "auth_method": resolved_auth_method or "none",
                "has_credentials": bool(credentials_data),
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

        claude_json_path = self.home_dir / ".claude.json"
        if not claude_json_path.exists():
            return

        try:
            claude_json_data = json.loads(claude_json_path.read_text())
        except Exception as exc:
            logger.warning(f"Failed to read .claude.json while clearing OAuth account info: {exc}")
            return

        if not isinstance(claude_json_data, dict):
            return

        if "oauthAccount" not in claude_json_data:
            return

        claude_json_data.pop("oauthAccount", None)
        claude_json_path.write_text(json.dumps(claude_json_data, indent=2))

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
                check=True
            )
            results["user_name_set"] = request.user_name
            logger.debug(f"Git user name configured: {request.user_name}")

            # Set Git user email
            subprocess.run(
                ["git", "config", "--global", "user.email", request.user_email],
                capture_output=True,
                text=True,
                check=True
            )
            results["user_email_set"] = request.user_email
            logger.debug(f"Git user email configured: {request.user_email}")

            # Verify settings
            verify_name = subprocess.run(
                ["git", "config", "--global", "user.name"],
                capture_output=True,
                text=True,
                check=True
            )
            verify_email = subprocess.run(
                ["git", "config", "--global", "user.email"],
                capture_output=True,
                text=True,
                check=True
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
            "git": self._check_git_status(),
        }

    def _check_ssh_status(self) -> Dict[str, str]:
        try:
            private_key_path = self.ssh_dir / "id_rsa"
            public_key_path = self.ssh_dir / "id_rsa.pub"
            authorized_keys_path = self.ssh_dir / "authorized_keys"

            has_private = private_key_path.is_file() and private_key_path.stat().st_size > 0
            has_public = public_key_path.is_file() and public_key_path.stat().st_size > 0
            has_authorized_keys = authorized_keys_path.is_file() and authorized_keys_path.stat().st_size > 0

            # Complete check: private key, public key, and authorized_keys all exist
            if has_private and has_public and has_authorized_keys:
                # Additional verification: check if authorized_keys contains current public key
                try:
                    public_key_content = public_key_path.read_text().strip()
                    authorized_keys_content = authorized_keys_path.read_text()

                    if public_key_content in authorized_keys_content:
                        return {"status": "success", "message": "SSH Keys ready and authorized_keys configured"}
                    else:
                        return {"status": "failed", "message": "authorized_keys does not contain current public key, please re-sync"}
                except Exception as read_exc:
                    logger.warning(f"Failed to read SSH file content: {read_exc}")
                    return {"status": "success", "message": "SSH Keys ready"}

            # Basic check: only check private key and public key
            if has_private and has_public:
                if not has_authorized_keys:
                    return {"status": "failed", "message": "SSH Keys exist but authorized_keys not configured, please re-sync"}
                return {"status": "success", "message": "SSH Keys ready"}

            if has_private or has_public or has_authorized_keys:
                return {"status": "failed", "message": "SSH Keys setup incomplete, please re-sync"}

            return {"status": "pending", "message": "SSH Keys not yet synced"}
        except Exception as exc:
            logger.error(f"Failed to check SSH Keys status: {exc}")
            return {"status": "failed", "message": f"Check failed: {exc}"}

    def _check_claude_status(self) -> Dict[str, str]:
        try:
            credentials_paths = [
                self.claude_dir / self._credentials_filename
            ]
            credentials_path = next((path for path in credentials_paths if path.is_file()), None)

            credentials_data = None
            if credentials_path and credentials_path.stat().st_size > 0:
                try:
                    credentials_data = json.loads(credentials_path.read_text())
                except Exception as cred_exc:
                    logger.warning(f"Failed to read Claude Code credentials file: {cred_exc}")

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
                if credentials_path and credentials_path.stat().st_size > 0:
                    return {"status": "success", "message": "Claude Code subscription credentials synced"}
                return {"status": "pending", "message": "Claude Code subscription credentials not yet synced"}

            # API Key mode, check user-configured environment variables
            if recorded_env_keys:
                missing_keys = [key for key in recorded_env_keys if not os.environ.get(key)]
                if missing_keys:
                    return {
                        "status": "failed",
                        "message": f"Missing required environment variables: {', '.join(missing_keys)}",
                    }
                return {"status": "success", "message": "Claude Code environment variables synced"}

            # If no environment variables recorded, not yet configured
            if auth_method == "api_key":
                return {"status": "pending", "message": "Claude Code environment variables not yet configured"}

            return {"status": "pending", "message": "Claude Code settings not yet synced"}
        except Exception as exc:
            logger.error(f"Failed to check Claude Code status: {exc}")
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

            user_name = name_result.stdout.strip() if name_result.returncode == 0 else ""
            user_email = email_result.stdout.strip() if email_result.returncode == 0 else ""

            if user_name and user_email:
                return {"status": "success", "message": "Git user info configured"}
            if user_name or user_email:
                return {"status": "failed", "message": "Git configuration incomplete, please re-sync"}
            return {"status": "pending", "message": "Git settings not yet synced"}
        except Exception as exc:
            logger.error(f"Failed to check Git status: {exc}")
            return {"status": "failed", "message": f"Check failed: {exc}"}

    def _ensure_directory_exists(self, directory: Path, mode: int = 0o755) -> None:
        """Ensure directory exists and set correct permissions"""
        directory.mkdir(mode=mode, parents=True, exist_ok=True)
        logger.debug(f"Directory ensured to exist: {directory} (permissions: {oct(mode)})")

    async def apply_firewall_settings(self, request: FirewallConfigRequest) -> Dict[str, str]:
        """Apply firewall settings"""
        try:
            logger.info("Starting firewall settings application")
            logger.debug(f"Firewall configuration: {request.model_dump()}")

            # Read firewall script template
            template_path = Path("/workspace-runtime/app/jinja_templates/firewall.sh.j2")
            if not template_path.exists():
                raise FileNotFoundError(f"Firewall script template does not exist: {template_path}")

            template_content = template_path.read_text()
            template = Template(template_content)

            # Docker enforcement happens inside the runtime container by rendering
            # and executing an iptables script for the workspace runtime scope.
            script_content = template.render(
                firewall={
                    "network_access_enabled": request.network_access_enabled,
                    "domain_access_mode": request.domain_access_mode,
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
                return {"status": "error", "message": error_msg, "output": result.stdout}

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
