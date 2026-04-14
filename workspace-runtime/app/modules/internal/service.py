"""Internal API 業務邏輯服務"""

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
    """內部 API 業務邏輯服務"""

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
        """設定 SSH Keys"""
        try:
            logger.info("開始設定 SSH Keys")

            # 確保 .ssh 目錄存在
            self.ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            logger.debug(f"SSH 目錄已準備: {self.ssh_dir}")

            # 寫入私鑰
            private_key_path = self.ssh_dir / "id_rsa"
            # 確保私鑰以換行符結尾，如果沒有的話就加上
            private_key_content = request.private_key
            if not private_key_content.endswith('\n'):
                private_key_content += '\n'
            private_key_path.write_text(private_key_content)
            private_key_path.chmod(0o600)
            logger.debug(f"私鑰已設定: {private_key_path}")

            # 寫入公鑰
            public_key_path = self.ssh_dir / "id_rsa.pub"
            # 確保公鑰以換行符結尾，如果沒有的話就加上
            public_key_content = request.public_key
            if not public_key_content.endswith('\n'):
                public_key_content += '\n'
            public_key_path.write_text(public_key_content)
            public_key_path.chmod(0o644)
            logger.debug(f"公鑰已設定: {public_key_path}")

            # 將公鑰加入 authorized_keys
            authorized_keys_path = self.ssh_dir / "authorized_keys"
            logger.debug(f"準備更新 authorized_keys: {authorized_keys_path}")

            # 讀取現有的 authorized_keys (如果存在)
            existing_keys = set()
            if authorized_keys_path.exists():
                content = authorized_keys_path.read_text()
                existing_keys = {
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith('#')
                }
                logger.debug(f"現有 authorized_keys 包含 {len(existing_keys)} 個金鑰")

            # 取得當前公鑰的指紋 (用於判斷是否已存在)
            new_key = public_key_content.strip()

            # 檢查是否已經存在相同的金鑰
            if new_key in existing_keys:
                logger.info("公鑰已存在於 authorized_keys 中，無需重複添加")
                authorized_keys_added = False
            else:
                # 將新公鑰加入集合
                existing_keys.add(new_key)
                logger.info("將公鑰加入 authorized_keys")

                # 寫入 authorized_keys
                authorized_keys_content = '\n'.join(sorted(existing_keys)) + '\n'
                authorized_keys_path.write_text(authorized_keys_content)
                authorized_keys_path.chmod(0o600)
                authorized_keys_added = True
                logger.debug(f"authorized_keys 已更新，現包含 {len(existing_keys)} 個金鑰")

            logger.info("SSH Keys 設定完成")
            return {
                "private_key_path": str(private_key_path),
                "public_key_path": str(public_key_path),
                "authorized_keys_path": str(authorized_keys_path),
                "authorized_keys_added": authorized_keys_added,
                "total_authorized_keys": len(existing_keys),
                "ssh_dir_permissions": oct(self.ssh_dir.stat().st_mode)[-3:],
            }

        except Exception as e:
            logger.error(f"SSH Keys 設定失敗: {e}")
            raise

    async def setup_claude_code(self, request: ClaudeCodeRequest) -> Dict[str, str]:
        """設定 Claude Code"""
        try:
            logger.info("開始設定 Claude Code")

            # 除錯：記錄接收到的請求資料
            logger.info(f"接收到的請求: auth_method={request.auth_method}")
            logger.info(f"subscription_access_token 是否存在: {bool(request.subscription_access_token)}")
            logger.info(f"subscription_refresh_token 是否存在: {bool(request.subscription_refresh_token)}")
            logger.info(f"subscription_expires_at: {request.subscription_expires_at}")

            # 確保 .claude 目錄存在
            self.claude_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
            logger.debug(f"Claude 目錄已準備: {self.claude_dir}")

            # 建立 credentials.json 檔案
            credentials_path = self.claude_dir / self._credentials_filename
            credentials_data = {}

            resolved_auth_method = request.auth_method
            if not resolved_auth_method:
                if request.subscription_access_token:
                    resolved_auth_method = "subscription"
                elif request.api_key or request.environment_variables:
                    resolved_auth_method = "api_key"

            # 根據認證方式儲存不同的憑證
            if resolved_auth_method == "subscription" and request.subscription_access_token:
                expires_at_ms = self._normalize_expires_at(request.subscription_expires_at)
                logger.info(f"Subscription expiresAt 解析結果: {expires_at_ms}")

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
                logger.debug(f"Credentials 檔案已建立: {credentials_path}")
                logger.info("儲存 Subscription OAuth Token (Claude Code 格式)")

                # 將 oauthAccount 資訊寫入 ~/.claude.json
                if request.oauth_account:
                    claude_json_path = self.home_dir / ".claude.json"
                    claude_json_data = {}

                    # 讀取現有的 .claude.json（如果存在）
                    if claude_json_path.exists():
                        try:
                            claude_json_data = json.loads(claude_json_path.read_text())
                            logger.debug(f"讀取現有的 .claude.json: {len(claude_json_data)} 個欄位")
                        except Exception as e:
                            logger.warning(f"無法讀取現有的 .claude.json: {e}，將建立新檔案")

                    # 更新 oauthAccount 欄位
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

                    # 寫入 .claude.json
                    claude_json_path.write_text(json.dumps(claude_json_data, indent=2))
                    logger.info(f"儲存 OAuth 帳戶資訊到 ~/.claude.json: {request.oauth_account.email_address} ({request.oauth_account.display_name})")
            elif resolved_auth_method == "api_key" and request.api_key:
                credentials_data = {
                    "authMethod": "api_key",
                    "apiKey": request.api_key,
                }
                self._clear_claude_oauth_state()
                logger.info("儲存 API Key")
            else:
                self._clear_claude_oauth_state()

            # 設定環境變數 - 當使用 subscription 模式時不同步環境變數
            synced_keys: List[str] = []
            env_vars_set = []
            if resolved_auth_method != "subscription":
                # 寫入 .bashrc 檔案
                bashrc_path = self.home_dir / ".bashrc"

                # 讀取現有的 .bashrc 內容
                existing_lines = []
                if bashrc_path.exists():
                    with open(bashrc_path, "r", encoding="utf-8") as f:
                        existing_lines = f.readlines()

                # 移除舊的環境變數設定（由本系統管理的）
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

                # 準備新的環境變數設定
                new_env_lines = []
                if request.environment_variables:
                    new_env_lines.append(marker_start)
                    for env_var in request.environment_variables:
                        # 確保 key 和 value 都不為空字串
                        if env_var.key and env_var.value:
                            # 轉義特殊字元以避免 shell 注入
                            escaped_value = env_var.value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
                            new_env_lines.append(f'export {env_var.key}="{escaped_value}"\n')
                            synced_keys.append(env_var.key)
                            env_vars_set.append(f"{env_var.key}={env_var.value}")
                            logger.debug(f"環境變數已設定: {env_var.key}")
                        else:
                            logger.warning(f"跳過空的環境變數: key={env_var.key}, value={'<empty>' if not env_var.value else '<set>'}")
                    new_env_lines.append(marker_end)

                # 寫回 .bashrc
                with open(bashrc_path, "w", encoding="utf-8") as f:
                    f.writelines(filtered_lines)
                    f.writelines(new_env_lines)

                logger.info(f"已更新 {bashrc_path}，共設定 {len(synced_keys)} 個環境變數")
            else:
                logger.info("使用 Subscription 認證模式,跳過環境變數同步")

            # 紀錄同步的認證方式與環境變數鍵名，提供後續狀態檢查
            if resolved_auth_method:
                os.environ[self._auth_method_env] = resolved_auth_method
            else:
                os.environ.pop(self._auth_method_env, None)

            if synced_keys:
                os.environ[self._env_keys_env] = ",".join(synced_keys)
            else:
                os.environ.pop(self._env_keys_env, None)

            if "model" in request.model_fields_set:
                logger.info("同步 Claude Code 基本設定的模型覆寫 (scope=USER)")
                update_request = ClaudeCodeSettingsUpdateRequest(model=request.model)
                settings_state = self._claude_settings_service.update_settings(
                    self._workspace_id,
                    update_request,
                    DocumentScope.USER,
                )
                logger.info(
                    "USER scope Claude Code 設定已更新，當前模型值：%s",
                    settings_state.model,
                )

            logger.info(f"Claude Code 設定完成，共設定 {len(env_vars_set)} 個環境變數")
            return {
                "credentials_path": str(credentials_path),
                "auth_method": resolved_auth_method or "none",
                "has_credentials": bool(credentials_data),
                "environment_variables_set": env_vars_set,
                "claude_dir_permissions": oct(self.claude_dir.stat().st_mode)[-3:],
            }

        except Exception as e:
            logger.error(f"Claude Code 設定失敗: {e}")
            raise

    @staticmethod
    def _normalize_expires_at(raw_value: Optional[int | str]) -> Optional[int]:
        """將過期時間轉換為毫秒時間戳，兼容整數與 ISO8601 字串。"""
        if raw_value is None:
            return None

        if isinstance(raw_value, int):
            return raw_value

        if isinstance(raw_value, str):
            value = raw_value.strip()
            if not value:
                return None

            # 嘗試直接轉成整數毫秒
            try:
                return int(value)
            except ValueError:
                pass

            # 嘗試解析 ISO8601
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "無法解析 subscriptionExpiresAt 值: %s (error=%s)",
                    value,
                    exc,
                )

        return None

    def _clear_claude_oauth_state(self) -> None:
        """清理 OAuth 專屬狀態，避免切換到 API key 後殘留舊 subscription 資訊。"""
        credentials_path = self.claude_dir / self._credentials_filename
        if credentials_path.exists():
            credentials_path.unlink()

        claude_json_path = self.home_dir / ".claude.json"
        if not claude_json_path.exists():
            return

        try:
            claude_json_data = json.loads(claude_json_path.read_text())
        except Exception as exc:
            logger.warning(f"清理 OAuth 帳戶資訊時無法讀取 .claude.json: {exc}")
            return

        if not isinstance(claude_json_data, dict):
            return

        if "oauthAccount" not in claude_json_data:
            return

        claude_json_data.pop("oauthAccount", None)
        claude_json_path.write_text(json.dumps(claude_json_data, indent=2))

    async def setup_git_settings(self, request: GitSettingsRequest) -> Dict[str, str]:
        """設定 Git 全域設定"""
        try:
            logger.info("開始設定 Git 全域設定")

            results = {}

            # 設定 Git 使用者名稱
            subprocess.run(
                ["git", "config", "--global", "user.name", request.user_name],
                capture_output=True,
                text=True,
                check=True
            )
            results["user_name_set"] = request.user_name
            logger.debug(f"Git 使用者名稱已設定: {request.user_name}")

            # 設定 Git 使用者信箱
            subprocess.run(
                ["git", "config", "--global", "user.email", request.user_email],
                capture_output=True,
                text=True,
                check=True
            )
            results["user_email_set"] = request.user_email
            logger.debug(f"Git 使用者信箱已設定: {request.user_email}")

            # 驗證設定
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

            logger.info("Git 全域設定完成")
            return results

        except subprocess.CalledProcessError as e:
            logger.error(f"Git 指令執行失敗: {e}")
            raise Exception(f"Git configuration failed: {e}")
        except Exception as e:
            logger.error(f"Git 設定失敗: {e}")
            raise

    async def get_setup_status(self) -> Dict[str, Dict[str, str]]:
        """檢查各同步項目的狀態"""
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

            # 完整檢查：私鑰、公鑰和 authorized_keys 都存在
            if has_private and has_public and has_authorized_keys:
                # 額外驗證：檢查 authorized_keys 中是否包含當前公鑰
                try:
                    public_key_content = public_key_path.read_text().strip()
                    authorized_keys_content = authorized_keys_path.read_text()

                    if public_key_content in authorized_keys_content:
                        return {"status": "success", "message": "SSH Keys 已就緒且 authorized_keys 已配置"}
                    else:
                        return {"status": "failed", "message": "authorized_keys 中未包含當前公鑰，請重新同步"}
                except Exception as read_exc:
                    logger.warning(f"讀取 SSH 檔案內容失敗: {read_exc}")
                    return {"status": "success", "message": "SSH Keys 已就緒"}

            # 基本檢查：只檢查私鑰和公鑰
            if has_private and has_public:
                if not has_authorized_keys:
                    return {"status": "failed", "message": "SSH Keys 存在但 authorized_keys 未配置，請重新同步"}
                return {"status": "success", "message": "SSH Keys 已就緒"}

            if has_private or has_public or has_authorized_keys:
                return {"status": "failed", "message": "SSH Keys 設定不完整，請重新同步"}

            return {"status": "pending", "message": "尚未同步 SSH Keys"}
        except Exception as exc:
            logger.error(f"檢查 SSH Keys 狀態失敗: {exc}")
            return {"status": "failed", "message": f"檢查失敗: {exc}"}

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
                    logger.warning(f"讀取 Claude Code 憑證檔案失敗: {cred_exc}")

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
                    return {"status": "success", "message": "Claude Code 訂閱憑證已同步"}
                return {"status": "pending", "message": "尚未同步 Claude Code 訂閱憑證"}

            # API Key 模式，檢查使用者設定的環境變數
            if recorded_env_keys:
                missing_keys = [key for key in recorded_env_keys if not os.environ.get(key)]
                if missing_keys:
                    return {
                        "status": "failed",
                        "message": f"缺少必要的環境變數: {', '.join(missing_keys)}",
                    }
                return {"status": "success", "message": "Claude Code 環境變數已同步"}

            # 如果沒有記錄任何環境變數，表示尚未設定
            if auth_method == "api_key":
                return {"status": "pending", "message": "尚未設定 Claude Code 環境變數"}

            return {"status": "pending", "message": "尚未同步 Claude Code 設定"}
        except Exception as exc:
            logger.error(f"檢查 Claude Code 狀態失敗: {exc}")
            return {"status": "failed", "message": f"檢查失敗: {exc}"}

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
                return {"status": "success", "message": "Git 使用者資訊已設定"}
            if user_name or user_email:
                return {"status": "failed", "message": "Git 設定不完整，請重新同步"}
            return {"status": "pending", "message": "尚未同步 Git 設定"}
        except Exception as exc:
            logger.error(f"檢查 Git 狀態失敗: {exc}")
            return {"status": "failed", "message": f"檢查失敗: {exc}"}

    def _ensure_directory_exists(self, directory: Path, mode: int = 0o755) -> None:
        """確保目錄存在並設定正確權限"""
        directory.mkdir(mode=mode, parents=True, exist_ok=True)
        logger.debug(f"目錄已確保存在: {directory} (權限: {oct(mode)})")

    async def apply_firewall_settings(self, request: FirewallConfigRequest) -> Dict[str, str]:
        """套用防火牆設定"""
        try:
            logger.info("開始套用防火牆設定")
            logger.debug(f"防火牆配置: {request.model_dump()}")

            # 讀取防火牆腳本模板
            template_path = Path("/workspace-runtime/app/jinja_templates/firewall.sh.j2")
            if not template_path.exists():
                raise FileNotFoundError(f"防火牆腳本模板不存在: {template_path}")

            template_content = template_path.read_text()
            template = Template(template_content)

            # 渲染腳本
            script_content = template.render(
                firewall={
                    "network_access_enabled": request.network_access_enabled,
                    "domain_access_mode": request.domain_access_mode,
                    "allowed_domains": request.allowed_domains,
                }
            )

            # 寫入臨時腳本檔案
            script_path = Path("/tmp/firewall_apply.sh")
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            logger.debug(f"防火牆腳本已生成: {script_path}")

            # 執行防火牆腳本（需要 sudo 權限）
            result = subprocess.run(
                ["sudo", "bash", str(script_path)],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                error_msg = f"防火牆腳本執行失敗: {result.stderr}"
                logger.error(error_msg)
                return {"status": "error", "message": error_msg, "output": result.stdout}

            logger.info("防火牆設定已成功套用")
            return {
                "status": "success",
                "message": "防火牆設定已成功套用",
                "output": result.stdout,
            }

        except subprocess.TimeoutExpired:
            error_msg = "防火牆腳本執行超時"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        except Exception as exc:
            error_msg = f"套用防火牆設定失敗: {exc}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}


__all__ = ["InternalService"]
