"""使用者設定服務"""

from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import models as db_models
from app.models import (
    ClaudeCodeSettings,
    ClaudeModelInfo,
    ClaudeProviderInfo,
    GeneralSettings,
    GitSettings,
    SSHSettings,
    UserProfile,
    UserProfileUpdate,
    UserSettings,
    UserSettingsUpdate,
)
from app.models.settings import SSHKeyPairResponse

logger = logging.getLogger(__name__)

DEFAULT_PROVIDERS = [
    ClaudeProviderInfo(provider="anthropic", display_name="Anthropic"),
    ClaudeProviderInfo(provider="aws-bedrock", display_name="AWS Bedrock"),
]


class SettingsService:
    """處理使用者個人資料與設定"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- 個人資料 ---------------------------------------------------------

    def get_profile(self, user_id: str) -> Optional[UserProfile]:
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None
        return UserProfile(
            user_id=user.id,
            username=user.username or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            email=user.email or "",
            avatar_url=user.avatar_url,
        )

    def update_profile(self, user_id: str, payload: UserProfileUpdate) -> Optional[UserProfile]:
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None

        if payload.first_name is not None:
            user.first_name = payload.first_name
        if payload.last_name is not None:
            user.last_name = payload.last_name
        if payload.avatar_url is not None:
            user.avatar_url = payload.avatar_url

        # 自動計算 display_name
        fn = user.first_name or ""
        ln = user.last_name or ""
        user.display_name = f"{fn} {ln}".strip() or user.username

        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        return self.get_profile(user_id)

    # -- 使用者設定 -------------------------------------------------------

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
            # 標記 JSONB 欄位已修改
            flag_modified(settings, "general_settings")

        if "ssh" in data and isinstance(data["ssh"], dict):
            ssh_data = data["ssh"]
            old_private_key = settings.ssh_private_key
            old_public_key = settings.ssh_public_key

            settings.ssh_public_key = ssh_data.get("publicKey", settings.ssh_public_key)
            settings.ssh_private_key = ssh_data.get("privateKey", settings.ssh_private_key)
            settings.ssh_fingerprint = ssh_data.get("fingerprint", settings.ssh_fingerprint)
            last_rotated_at = ssh_data.get("lastRotatedAt")
            if last_rotated_at and isinstance(last_rotated_at, str) and last_rotated_at != "null":
                try:
                    settings.ssh_last_rotated_at = datetime.fromisoformat(
                        last_rotated_at.replace("Z", "+00:00")
                    )
                except (ValueError, TypeError):
                    # 如果日期格式錯誤，保持原值
                    pass

            # 如果 SSH key 有變更，同步寫入檔案系統
            if (settings.ssh_private_key != old_private_key or
                settings.ssh_public_key != old_public_key):
                if settings.ssh_private_key and settings.ssh_public_key:
                    try:
                        self._write_ssh_keys_to_filesystem(
                            settings.ssh_private_key,
                            settings.ssh_public_key
                        )
                    except Exception as e:
                        logger.warning(f"無法將 SSH key 寫入檔案系統: {e}")

        if "claudeCode" in data and isinstance(data["claudeCode"], dict):
            claude_data = data["claudeCode"]

            # 處理基本設定
            if "authKey" in claude_data:
                settings.claude_auth_key = claude_data["authKey"]
            # 統一使用 model 欄位,但也支援舊的 selectedModel
            if "model" in claude_data:
                settings.claude_selected_model = claude_data["model"]
            if "selectedProvider" in claude_data:
                settings.claude_selected_provider = claude_data["selectedProvider"]

            # 處理新的設定欄位，存儲在additional_settings中
            additional_settings = settings.additional_settings or {}
            claude_additional = additional_settings.get("claudeCode", {})

            # 更新新的ClaudeCode設定欄位
            if "authMethod" in claude_data:
                claude_additional["authMethod"] = claude_data["authMethod"]
            if "subscriptionAuthCode" in claude_data:
                claude_additional["subscriptionAuthCode"] = claude_data["subscriptionAuthCode"]
            if "subscriptionAccessToken" in claude_data:
                claude_additional["subscriptionAccessToken"] = claude_data["subscriptionAccessToken"]
            if "subscriptionRefreshToken" in claude_data:
                claude_additional["subscriptionRefreshToken"] = claude_data["subscriptionRefreshToken"]
            if "subscriptionExpiresAt" in claude_data:
                claude_additional["subscriptionExpiresAt"] = claude_data["subscriptionExpiresAt"]
            if "oauthAccount" in claude_data:
                claude_additional["oauthAccount"] = claude_data["oauthAccount"]
            if "apiProvider" in claude_data:
                claude_additional["apiProvider"] = claude_data["apiProvider"]
            if "environmentVariables" in claude_data:
                claude_additional["environmentVariables"] = claude_data["environmentVariables"]
            if "availableModels" in claude_data:
                claude_additional["availableModels"] = claude_data["availableModels"]
            if "availableProviders" in claude_data:
                claude_additional["availableProviders"] = claude_data["availableProviders"]

            additional_settings["claudeCode"] = claude_additional
            settings.additional_settings = additional_settings
            # 標記 JSONB 欄位已修改
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

    def detect_setting_changes(self, old_settings: UserSettings, new_data: dict) -> dict:
        """檢測哪些設定實際發生變更"""
        changes = {}

        # 檢測 SSH 設定變更
        if "ssh" in new_data:
            ssh_data = new_data["ssh"]
            old_ssh = old_settings.ssh

            # 比較 SSH 金鑰是否有變更
            if (ssh_data.get("privateKey") != old_ssh.private_key or
                ssh_data.get("publicKey") != old_ssh.public_key):
                changes["ssh"] = {
                    "privateKey": ssh_data.get("privateKey"),
                    "publicKey": ssh_data.get("publicKey")
                }

        # 檢測 Claude Code 設定變更
        if "claudeCode" in new_data:
            claude_data = new_data["claudeCode"]
            old_claude = old_settings.claude_code

            # 檢查是否有任何變更
            has_changes = False
            claude_changes = {}

            # 比較認證方式
            if claude_data.get("authMethod") != old_claude.auth_method:
                has_changes = True
                claude_changes["authMethod"] = claude_data.get("authMethod")

            # 比較 OAuth tokens
            if claude_data.get("subscriptionAccessToken") != old_claude.subscription_access_token:
                has_changes = True
                claude_changes["subscriptionAccessToken"] = claude_data.get("subscriptionAccessToken")
                claude_changes["subscriptionRefreshToken"] = claude_data.get("subscriptionRefreshToken")
                claude_changes["subscriptionExpiresAt"] = claude_data.get("subscriptionExpiresAt")

            # 比較 API Key
            if claude_data.get("authKey") != old_claude.auth_key:
                has_changes = True
                claude_changes["authKey"] = claude_data.get("authKey")

            # 比較環境變數
            new_env_vars = claude_data.get("environmentVariables", [])
            old_env_vars = old_claude.environment_variables
            if self._env_vars_changed(old_env_vars, new_env_vars):
                has_changes = True
                claude_changes["environmentVariables"] = new_env_vars

            if has_changes:
                changes["claudeCode"] = claude_changes

        # 檢測 Git 設定變更
        if "git" in new_data:
            git_data = new_data["git"]
            old_git = old_settings.git

            # 比較 Git 使用者資訊是否有變更
            if (git_data.get("userName") != old_git.user_name or
                git_data.get("userEmail") != old_git.user_email):
                changes["git"] = {
                    "userName": git_data.get("userName"),
                    "userEmail": git_data.get("userEmail")
                }

        return changes

    def _env_vars_changed(self, old_vars: list, new_vars: list) -> bool:
        """比較環境變數列表是否有變更"""
        if len(old_vars) != len(new_vars):
            return True

        # 轉換為字典以便比較
        old_dict = {var.key: var.value for var in old_vars}
        new_dict = {var.get("key"): var.get("value") for var in new_vars if var.get("key")}

        return old_dict != new_dict

    # -- 私有函式 ---------------------------------------------------------

    def _get_or_create_settings(self, user: db_models.User) -> db_models.UserSetting:
        settings = user.settings
        if settings:
            return settings

        settings = db_models.UserSetting(
            id=str(uuid4()),
            user_id=user.id,
            claude_selected_model="claude-3-7-sonnet-20250219",
            claude_selected_provider="anthropic",
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

        claude_models = self._list_active_models()

        # 從additional_settings中讀取新的ClaudeCode設定
        additional_settings = settings.additional_settings or {}
        claude_additional = additional_settings.get("claudeCode", {})

        # 處理 oauthAccount
        oauth_account = None
        oauth_account_data = claude_additional.get("oauthAccount")
        if oauth_account_data:
            from app.models.settings import OAuthAccountInfo
            oauth_account = OAuthAccountInfo(**oauth_account_data)

        # 處理 subscription_expires_at：將空字符串轉換為 None
        subscription_expires_at = claude_additional.get("subscriptionExpiresAt")
        if subscription_expires_at == "":
            subscription_expires_at = None

        claude_model = ClaudeCodeSettings(
            auth_key=settings.claude_auth_key,
            model=settings.claude_selected_model,
            selected_provider=settings.claude_selected_provider,
            available_models=claude_models,
            available_providers=DEFAULT_PROVIDERS,
            # 新增的設定欄位
            auth_method=claude_additional.get("authMethod", "subscription"),
            subscription_auth_code=claude_additional.get("subscriptionAuthCode") or None,
            subscription_access_token=claude_additional.get("subscriptionAccessToken") or None,
            subscription_refresh_token=claude_additional.get("subscriptionRefreshToken") or None,
            subscription_expires_at=subscription_expires_at,
            oauth_account=oauth_account,
            api_provider=claude_additional.get("apiProvider") or None,
            environment_variables=claude_additional.get("environmentVariables", []),
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
            git=git_model,
        )

    def _list_active_models(self) -> list[ClaudeModelInfo]:
        query = (
            select(db_models.ModelConfig)
            .where(db_models.ModelConfig.is_active.is_(True))
            .order_by(db_models.ModelConfig.sort_order.asc())
        )
        records = self.db.execute(query).scalars().all()
        return [
            ClaudeModelInfo(model_key=record.model_key, model_name=record.model_name)
            for record in records
        ]

    @staticmethod
    def _merge_dict(original: dict, updates: dict) -> dict:
        merged = dict(original)
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(original.get(key), dict):
                merged[key] = SettingsService._merge_dict(original[key], value)
            else:
                merged[key] = value
        return merged

    # -- SSH Key 管理 -----------------------------------------------------

    def generate_and_save_ssh_keys(self, user_id: str) -> Optional[SSHKeyPairResponse]:
        """產生新的 SSH Key Pair 並儲存到使用者設定"""
        user = self.db.get(db_models.User, user_id)
        if not user:
            return None

        # 產生 SSH Key Pair
        private_key, public_key = self._generate_ssh_key_pair()

        # 計算 fingerprint
        fingerprint = self._calculate_ssh_fingerprint(public_key)

        # 儲存到資料庫
        settings = self._get_or_create_settings(user)
        settings.ssh_private_key = private_key
        settings.ssh_public_key = public_key
        settings.ssh_fingerprint = fingerprint
        settings.ssh_last_rotated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(settings)

        # 同時將 SSH key 寫入到 workspace-manager 的 ~/.ssh 目錄
        # 這樣 workspace-manager 可以使用這些 key 來 clone 私有倉庫
        try:
            self._write_ssh_keys_to_filesystem(private_key, public_key)
        except Exception as e:
            logger.warning(f"無法將 SSH key 寫入檔案系統: {e}")
            # 不影響主要流程，繼續執行

        return SSHKeyPairResponse(
            public_key=public_key,
            private_key=private_key,
            fingerprint=fingerprint,
            generated_at=settings.ssh_last_rotated_at,
        )

    @staticmethod
    def _generate_ssh_key_pair() -> tuple[str, str]:
        """使用 ssh-keygen 產生 SSH Key Pair"""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = Path(tmpdir) / "id_rsa"

            # 使用 ssh-keygen 產生金鑰
            # -t rsa: 使用 RSA 演算法
            # -b 4096: 4096 位元金鑰長度
            # -f: 指定輸出檔案
            # -N "": 不設定密碼
            # -C: 註解（使用時間戳記）
            subprocess.run(
                [
                    "ssh-keygen",
                    "-t", "rsa",
                    "-b", "4096",
                    "-f", str(key_path),
                    "-N", "",
                    "-C", f"generated-{datetime.utcnow().isoformat()}"
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            # 讀取私鑰
            private_key = key_path.read_text()

            # 讀取公鑰
            public_key = (key_path.with_suffix(".pub")).read_text().strip()

            return private_key, public_key

    @staticmethod
    def _calculate_ssh_fingerprint(public_key: str) -> str:
        """計算 SSH 公鑰的 fingerprint (SHA256)"""
        # 取得公鑰的 base64 部分
        parts = public_key.split()
        if len(parts) < 2:
            return ""

        import base64
        key_data = base64.b64decode(parts[1])

        # 計算 SHA256 hash
        sha256_hash = hashlib.sha256(key_data).digest()

        # 轉換為 base64 並移除 padding
        fingerprint = base64.b64encode(sha256_hash).decode().rstrip("=")

        return f"SHA256:{fingerprint}"

    @staticmethod
    def _write_ssh_keys_to_filesystem(private_key: str, public_key: str) -> None:
        """
        將 SSH key 寫入到 workspace-manager 的檔案系統

        這樣 workspace-manager 可以使用這些 key 來認證 Git 操作

        Args:
            private_key: SSH 私鑰內容
            public_key: SSH 公鑰內容
        """
        # 確定 SSH 目錄路徑
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

        # 寫入私鑰
        private_key_path = ssh_dir / "id_rsa"
        private_key_content = private_key
        if not private_key_content.endswith('\n'):
            private_key_content += '\n'
        private_key_path.write_text(private_key_content)
        private_key_path.chmod(0o600)
        logger.info(f"SSH 私鑰已寫入: {private_key_path}")

        # 寫入公鑰
        public_key_path = ssh_dir / "id_rsa.pub"
        public_key_content = public_key
        if not public_key_content.endswith('\n'):
            public_key_content += '\n'
        public_key_path.write_text(public_key_content)
        public_key_path.chmod(0o644)
        logger.info(f"SSH 公鑰已寫入: {public_key_path}")

        # 設定 known_hosts（避免首次連線時的提示）
        known_hosts_path = ssh_dir / "known_hosts"
        if not known_hosts_path.exists():
            known_hosts_path.touch(mode=0o644)
            logger.info(f"已建立 known_hosts: {known_hosts_path}")


__all__ = ["SettingsService"]
