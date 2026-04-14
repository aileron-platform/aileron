"""Internal Service 單元測試"""

from __future__ import annotations

import json
import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from app.modules.internal.service import InternalService
from app.modules.internal.models import (
    SSHKeysRequest,
    ClaudeCodeRequest,
    GitSettingsRequest,
    FirewallConfigRequest,
    EnvironmentVariable,
    OAuthAccountInfo,
)


@pytest.fixture
def internal_service(tmp_path):
    """Internal service fixture with mocked paths"""
    with patch("app.modules.internal.service.Path.home", return_value=tmp_path):
        with patch("app.modules.internal.service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(WORKSPACE_ID="test-workspace")
            service = InternalService()
            service.home_dir = tmp_path
            service.ssh_dir = tmp_path / ".ssh"
            service.claude_dir = tmp_path / ".claude"
            return service


@pytest.fixture
def tmp_paths(tmp_path):
    """Create temporary paths fixture"""
    return {
        "home": tmp_path,
        "ssh": tmp_path / ".ssh",
        "claude": tmp_path / ".claude",
    }


class TestInternalServiceInitialization:
    """測試 Internal Service 初始化"""

    def test_init(self):
        """測試服務初始化"""
        # Act
        with patch("app.modules.internal.service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(WORKSPACE_ID="test-workspace")
            service = InternalService()

        # Assert
        assert service.home_dir == Path("/home/developer")
        assert service.ssh_dir == Path("/home/developer/.ssh")
        assert service.claude_dir == Path("/home/developer/.claude")
        assert service._workspace_id == "test-workspace"


class TestSetupSSHKeys:
    """測試設定 SSH Keys"""

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_success(self, internal_service, tmp_paths):
        """測試成功設定 SSH Keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com",
        )

        # Act
        result = await internal_service.setup_ssh_keys(request)

        # Assert
        assert result["private_key_path"] == str(tmp_paths["ssh"] / "id_rsa")
        assert result["public_key_path"] == str(tmp_paths["ssh"] / "id_rsa.pub")
        assert result["authorized_keys_path"] == str(tmp_paths["ssh"] / "authorized_keys")
        assert result["authorized_keys_added"] is True
        assert result["total_authorized_keys"] == 1

        # 驗證文件存在
        assert (tmp_paths["ssh"] / "id_rsa").exists()
        assert (tmp_paths["ssh"] / "id_rsa.pub").exists()
        assert (tmp_paths["ssh"] / "authorized_keys").exists()

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_adds_newline(self, internal_service, tmp_paths):
        """測試自動添加換行符"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",  # 沒有結尾換行
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com",  # 沒有結尾換行
        )

        # Act
        await internal_service.setup_ssh_keys(request)

        # Assert
        private_content = (tmp_paths["ssh"] / "id_rsa").read_text()
        public_content = (tmp_paths["ssh"] / "id_rsa.pub").read_text()
        assert private_content.endswith('\n')
        assert public_content.endswith('\n')

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_duplicate_public_key(self, internal_service, tmp_paths):
        """測試重複的公鑰不會被重複添加"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com"

        # 先添加一次
        request1 = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key=public_key,
        )
        await internal_service.setup_ssh_keys(request1)

        # Act - 再次添加相同的公鑰
        request2 = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key=public_key,
        )
        result = await internal_service.setup_ssh_keys(request2)

        # Assert
        assert result["authorized_keys_added"] is False
        assert result["total_authorized_keys"] == 1

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_preserves_existing_keys(self, internal_service, tmp_paths):
        """測試保留現有的 authorized_keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 預先添加一個公鑰
        existing_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ existing@example.com"
        (tmp_paths["ssh"] / "authorized_keys").write_text(f"{existing_key}\n")

        # Act - 添加新公鑰
        new_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ new@example.com"
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key=new_key,
        )
        result = await internal_service.setup_ssh_keys(request)

        # Assert
        assert result["total_authorized_keys"] == 2
        authorized_content = (tmp_paths["ssh"] / "authorized_keys").read_text()
        assert existing_key in authorized_content
        assert new_key in authorized_content

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_directory_permissions(self, internal_service, tmp_paths):
        """測試 SSH 目錄權限"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com",
        )

        # Act
        await internal_service.setup_ssh_keys(request)

        # Assert
        ssh_dir_stat = tmp_paths["ssh"].stat()
        assert oct(ssh_dir_stat.st_mode)[-3:] == '700'

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_file_permissions(self, internal_service, tmp_paths):
        """測試 SSH 文件權限"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com",
        )

        # Act
        await internal_service.setup_ssh_keys(request)

        # Assert
        private_stat = (tmp_paths["ssh"] / "id_rsa").stat()
        public_stat = (tmp_paths["ssh"] / "id_rsa.pub").stat()
        authorized_stat = (tmp_paths["ssh"] / "authorized_keys").stat()

        assert oct(private_stat.st_mode)[-3:] == '600'
        assert oct(public_stat.st_mode)[-3:] == '644'
        assert oct(authorized_stat.st_mode)[-3:] == '600'

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_error_handling(self, internal_service):
        """測試 SSH Keys 設定錯誤處理"""
        # Arrange - Mock mkdir to raise permission error
        with patch.object(Path, 'mkdir', side_effect=PermissionError("Permission denied")):
            internal_service.ssh_dir = Path("/test/.ssh")
            request = SSHKeysRequest(
                private_key="test",
                public_key="test",
            )

            # Act & Assert
            with pytest.raises(PermissionError):
                await internal_service.setup_ssh_keys(request)


class TestSetupClaudeCode:
    """測試設定 Claude Code"""

    @pytest.mark.asyncio
    async def test_setup_claude_code_subscription(self, internal_service, tmp_paths):
        """測試設定 Subscription 認證"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        oauth_account = OAuthAccountInfo(
            account_uuid="test-uuid",
            email_address="test@example.com",
            organization_uuid="org-uuid",
            display_name="Test User",
            organization_billing_type="pro",
            organization_role="member",
            workspace_role="editor",
            organization_name="Test Org",
        )

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-access-token",
            subscription_refresh_token="test-refresh-token",
            subscription_expires_at=1234567890000,
            oauth_account=oauth_account,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert
        assert result["auth_method"] == "subscription"
        assert result["has_credentials"] is True
        assert (tmp_paths["claude"] / ".credentials.json").exists()

        # 驗證 credentials 內容
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert credentials["authMethod"] == "subscription"
        assert credentials["claudeAiOauth"]["accessToken"] == "test-access-token"
        assert credentials["claudeAiOauth"]["refreshToken"] == "test-refresh-token"

        # 驗證 .claude.json 內容
        claude_json = json.loads((tmp_paths["home"] / ".claude.json").read_text())
        assert "oauthAccount" in claude_json
        assert claude_json["oauthAccount"]["emailAddress"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_setup_claude_code_api_key(self, internal_service, tmp_paths):
        """測試設定 API Key 認證"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            api_key="test-api-key",
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert
        assert result["auth_method"] == "api_key"
        assert result["has_credentials"] is True
        assert not (tmp_paths["claude"] / ".credentials.json").exists()

    @pytest.mark.asyncio
    async def test_setup_claude_code_api_key_clears_stale_oauth_state(self, internal_service, tmp_paths):
        """測試切換到 API Key 時會清除舊的 OAuth 狀態"""
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        (tmp_paths["claude"] / ".credentials.json").write_text(
            json.dumps({"authMethod": "subscription", "claudeAiOauth": {"accessToken": "old"}})
        )
        (tmp_paths["home"] / ".claude.json").write_text(
            json.dumps({"oauthAccount": {"emailAddress": "old@example.com"}, "other": True})
        )

        request = ClaudeCodeRequest(
            auth_method="api_key",
            api_key="test-api-key",
        )

        await internal_service.setup_claude_code(request)

        assert not (tmp_paths["claude"] / ".credentials.json").exists()
        claude_json = json.loads((tmp_paths["home"] / ".claude.json").read_text())
        assert "oauthAccount" not in claude_json
        assert claude_json["other"] is True

    @pytest.mark.asyncio
    async def test_setup_claude_code_subscription_merges_existing_claude_json(
        self, internal_service, tmp_paths
    ):
        """測試 subscription 模式會保留既有 ~/.claude.json 欄位並更新 oauthAccount。"""
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        (tmp_paths["home"] / ".claude.json").write_text(json.dumps({"existing": "value"}))

        oauth_account = OAuthAccountInfo(
            account_uuid="acct-123",
            email_address="test@example.com",
            organization_uuid="org-123",
            organization_role="member",
            workspace_role="editor",
            organization_name="Test Org",
        )
        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="refresh-token",
            subscription_expires_at=1234567890000,
            oauth_account=oauth_account,
        )

        await internal_service.setup_claude_code(request)

        claude_json = json.loads((tmp_paths["home"] / ".claude.json").read_text())
        assert claude_json["existing"] == "value"
        assert claude_json["oauthAccount"]["emailAddress"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_setup_claude_code_environment_variables(self, internal_service, tmp_paths):
        """測試設定環境變數到 .bashrc"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        env_vars = [
            EnvironmentVariable(key="TEST_VAR1", value="value1"),
            EnvironmentVariable(key="TEST_VAR2", value="value2"),
        ]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            environment_variables=env_vars,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert
        assert len(result["environment_variables_set"]) == 2
        assert bashrc_path.exists()

        bashrc_content = bashrc_path.read_text()
        assert "# Aileron - Claude Code Environment Variables - START" in bashrc_content
        assert 'export TEST_VAR1="value1"' in bashrc_content
        assert 'export TEST_VAR2="value2"' in bashrc_content
        assert "# Aileron - Claude Code Environment Variables - END" in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_subscription_no_env_vars(self, internal_service, tmp_paths):
        """測試 Subscription 模式不同步環境變數"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        env_vars = [
            EnvironmentVariable(key="TEST_VAR", value="value"),
        ]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,
            environment_variables=env_vars,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert
        assert len(result["environment_variables_set"]) == 0
        # Subscription 模式不應該寫入 .bashrc
        if bashrc_path.exists():
            bashrc_content = bashrc_path.read_text()
            assert "TEST_VAR" not in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_auto_detect_auth_method(self, internal_service, tmp_paths):
        """測試自動檢測認證方式"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # 測試 1: 有 subscription token -> subscription
        request1 = ClaudeCodeRequest(
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,
        )

        result1 = await internal_service.setup_claude_code(request1)
        assert result1["auth_method"] == "subscription"

        # 測試 2: 有 api_key -> api_key
        request2 = ClaudeCodeRequest(
            api_key="test-api-key",
        )

        result2 = await internal_service.setup_claude_code(request2)
        assert result2["auth_method"] == "api_key"

    @pytest.mark.asyncio
    async def test_setup_claude_code_normalize_expires_at_integer(self, internal_service, tmp_paths):
        """測試正規化整數類型的 expiresAt"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,  # 整數
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert credentials["claudeAiOauth"]["expiresAt"] == 1234567890000

    @pytest.mark.asyncio
    async def test_setup_claude_code_normalize_expires_at_iso_string(self, internal_service, tmp_paths):
        """測試正規化 ISO8601 字符串的 expiresAt"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at="2024-01-01T00:00:00Z",  # ISO8601 字符串
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert isinstance(credentials["claudeAiOauth"]["expiresAt"], int)

    @pytest.mark.asyncio
    @patch("app.modules.internal.service.SettingsService")
    async def test_setup_claude_code_with_model_override(self, mock_settings_service, internal_service, tmp_paths):
        """測試模型覆蓋設定"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        mock_instance = MagicMock()
        internal_service._claude_settings_service = mock_instance

        request = ClaudeCodeRequest(
            auth_method="api_key",
            model="claude-3-opus-20240229",
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        mock_instance.update_settings.assert_called_once()


class TestNormalizeExpiresAt:
    """測試 expiresAt 正規化"""

    def test_normalize_expires_at_integer(self):
        """測試整數"""
        result = InternalService._normalize_expires_at(1234567890000)
        assert result == 1234567890000

    def test_normalize_expires_at_string_integer(self):
        """測試字符串整數"""
        result = InternalService._normalize_expires_at("1234567890000")
        assert result == 1234567890000

    def test_normalize_expires_at_iso8601(self):
        """測試 ISO8601 格式"""
        result = InternalService._normalize_expires_at("2024-01-01T00:00:00Z")
        assert isinstance(result, int)
        assert result > 0

    def test_normalize_expires_at_none(self):
        """測試 None"""
        result = InternalService._normalize_expires_at(None)
        assert result is None

    def test_normalize_expires_at_empty_string(self):
        """測試空字符串"""
        result = InternalService._normalize_expires_at("")
        assert result is None

    def test_normalize_expires_at_invalid_string(self):
        """測試無效字符串"""
        result = InternalService._normalize_expires_at("invalid")
        assert result is None


class TestSetupGitSettings:
    """測試設定 Git 設定"""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_setup_git_settings_success(self, mock_run, internal_service):
        """測試成功設定 Git 設定"""
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        request = GitSettingsRequest(
            user_name="Test User",
            user_email="test@example.com",
        )

        # Act
        result = await internal_service.setup_git_settings(request)

        # Assert
        assert result["user_name_set"] == "Test User"
        assert result["user_email_set"] == "test@example.com"
        assert result["verified_name"] == ""
        assert result["verified_email"] == ""

        # 驗證 git config 命令被調用
        assert mock_run.call_count == 4  # set name, set email, verify name, verify email

    @pytest.mark.asyncio
    async def test_setup_git_settings_verify(self, internal_service):
        """測試驗證 Git 設定"""
        # Arrange
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            # 設置命令：["git", "config", "--global", "user.name", "Test User"]  (5 個元素)
            # 驗證命令：["git", "config", "--global", "user.name"]  (4 個元素)
            if "user.name" in cmd and len(cmd) == 4:
                # 這是讀取命令
                return MagicMock(returncode=0, stdout="Test User\n", stderr="")
            elif "user.email" in cmd and len(cmd) == 4:
                # 這是讀取命令
                return MagicMock(returncode=0, stdout="test@example.com\n", stderr="")
            else:
                # 這是設置命令或其他
                return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=run_side_effect):
            request = GitSettingsRequest(
                user_name="Test User",
                user_email="test@example.com",
            )

            # Act
            result = await internal_service.setup_git_settings(request)

            # Assert
            assert result["verified_name"] == "Test User"
            assert result["verified_email"] == "test@example.com"

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_setup_git_settings_command_failure(self, mock_run, internal_service):
        """測試 Git 命令失敗"""
        # Arrange
        mock_run.side_effect = subprocess.CalledProcessError(1, "git")

        request = GitSettingsRequest(
            user_name="Test User",
            user_email="test@example.com",
        )

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await internal_service.setup_git_settings(request)
        assert "Git configuration failed" in str(exc_info.value)


class TestGetSetupStatus:
    """測試取得設定狀態"""

    @pytest.mark.asyncio
    async def test_get_setup_status(self, internal_service):
        """測試取得設定狀態"""
        # Act
        with patch.object(internal_service, "_check_ssh_status", return_value={"status": "success"}):
            with patch.object(internal_service, "_check_claude_status", return_value={"status": "success"}):
                with patch.object(internal_service, "_check_git_status", return_value={"status": "success"}):
                    result = await internal_service.get_setup_status()

        # Assert
        assert "ssh" in result
        assert "claudeCode" in result
        assert "git" in result


class TestCheckSSHStatus:
    """測試檢查 SSH 狀態"""

    def test_check_ssh_status_success(self, internal_service, tmp_paths):
        """測試 SSH 完全配置"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 創建所需文件
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")
        (tmp_paths["ssh"] / "authorized_keys").write_text("public key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "success"

    def test_check_ssh_status_pending(self, internal_service, tmp_paths):
        """測試 SSH 未配置"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "pending"

    def test_check_ssh_status_incomplete(self, internal_service, tmp_paths):
        """測試 SSH 配置不完整"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 只創建私鑰
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"


class TestCheckClaudeStatus:
    """測試檢查 Claude Code 狀態"""

    def test_check_claude_status_subscription(self, tmp_path):
        """測試 Subscription 認證狀態"""
        # Arrange - 創建獨立的服務實例以避免狀態泄漏
        import os
        # 清除可能影響測試的環境變數
        env_backup = {}
        for key in ['CLAUDE_CODE_AUTH_METHOD', 'CLAUDE_CODE_SYNCED_KEYS']:
            env_backup[key] = os.environ.pop(key, None)

        try:
            with patch("app.modules.internal.service.Path.home", return_value=tmp_path):
                with patch("app.modules.internal.service.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(WORKSPACE_ID="test-workspace")
                    service = InternalService()
                    service.claude_dir = tmp_path / ".claude"
                    service.claude_dir.mkdir(parents=True, exist_ok=True)

                    credentials = {
                        "authMethod": "subscription",
                        "claudeAiOauth": {
                            "accessToken": "test-token",
                        }
                    }
                    credentials_file = service.claude_dir / ".credentials.json"
                    credentials_file.write_text(json.dumps(credentials))

                    # 確保文件存在且可讀
                    assert credentials_file.exists()
                    assert credentials_file.is_file()

                    # Act
                    result = service._check_claude_status()

                    # Assert
                    assert result["status"] == "success", f"Expected 'success' but got '{result['status']}'. Message: {result.get('message', 'N/A')}"
        finally:
            # 恢復環境變數
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_check_claude_status_pending(self, internal_service, tmp_paths):
        """測試未配置狀態"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # Act
        result = internal_service._check_claude_status()

        # Assert
        assert result["status"] == "pending"


class TestCheckGitStatus:
    """測試檢查 Git 狀態"""

    @patch("subprocess.run")
    def test_check_git_status_success(self, mock_run, internal_service):
        """測試 Git 完全配置"""
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="Test User\n", stderr="")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "success"

    @patch("subprocess.run")
    def test_check_git_status_pending(self, mock_run, internal_service):
        """測試 Git 未配置"""
        # Arrange
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "pending"

    @patch("subprocess.run")
    def test_check_git_status_incomplete(self, mock_run, internal_service):
        """測試 Git 配置不完整"""
        # Arrange
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            if "user.name" in cmd:
                return MagicMock(returncode=0, stdout="Test User\n", stderr="")
            else:
                return MagicMock(returncode=1, stdout="", stderr="")

        mock_run.side_effect = run_side_effect

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "failed"


class TestApplyFirewallSettings:
    """測試套用防火牆設定"""

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_success(self, internal_service):
        """測試成功套用防火牆設定"""
        # Arrange
        template_content = "#!/bin/bash\necho 'Firewall configured'"

        with patch("builtins.open", mock_open(read_data=template_content)):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=template_content):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

                        request = FirewallConfigRequest(
                            network_access_enabled=True,
                            domain_access_mode="allowlist",
                            allowed_domains=["example.com"],
                        )

                        # Act
                        result = await internal_service.apply_firewall_settings(request)

                        # Assert
                        assert result["status"] == "success"
                        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_script_failure(self, internal_service):
        """測試防火牆腳本執行失敗"""
        # Arrange
        template_content = "#!/bin/bash\necho 'template'"

        with patch("builtins.open", mock_open(read_data=template_content)):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=template_content):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Error occurred")

                        request = FirewallConfigRequest(
                            network_access_enabled=True,
                            domain_access_mode="allowlist",
                            allowed_domains=["example.com"],
                        )

                        # Act
                        result = await internal_service.apply_firewall_settings(request)

                        # Assert
                        assert result["status"] == "error"
                        assert "Error occurred" in result["message"]

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_template_not_found(self, internal_service):
        """測試模板文件不存在"""
        # Arrange
        with patch.object(Path, "exists", return_value=False):
            request = FirewallConfigRequest(
                network_access_enabled=True,
                domain_access_mode="allowlist",
                allowed_domains=[],
            )

            # Act
            result = await internal_service.apply_firewall_settings(request)

            # Assert
            assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_timeout(self, internal_service):
        """測試防火牆腳本超時"""
        # Arrange
        template_content = "#!/bin/bash\nsleep 100"

        with patch("builtins.open", mock_open(read_data=template_content)):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=template_content):
                    with patch("subprocess.run") as mock_run:
                        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 60)

                        request = FirewallConfigRequest(
                            network_access_enabled=True,
                            domain_access_mode="allowlist",
                            allowed_domains=[],
                        )

                        # Act
                        result = await internal_service.apply_firewall_settings(request)

                        # Assert
                        assert result["status"] == "error"
                        assert "超時" in result["message"]


class TestSetupClaudeCodeEdgeCases:
    """測試 Claude Code 設定的邊緣情況"""

    @pytest.mark.asyncio
    async def test_setup_claude_code_with_existing_malformed_claude_json(self, internal_service, tmp_paths):
        """測試當 .claude.json 存在但格式錯誤時的處理"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]

        # 創建格式錯誤的 .claude.json
        claude_json_path = tmp_paths["home"] / ".claude.json"
        claude_json_path.write_text("{ invalid json }")

        oauth_account = OAuthAccountInfo(
            account_uuid="test-uuid",
            email_address="test@example.com",
            organization_uuid="org-uuid",
            display_name="Test User",
            organization_billing_type="pro",
            organization_role="member",
            workspace_role="editor",
            organization_name="Test Org",
        )

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,
            oauth_account=oauth_account,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert - 應該創建新的 .claude.json 而不是拋出異常
        assert result["auth_method"] == "subscription"
        assert claude_json_path.exists()
        claude_json = json.loads(claude_json_path.read_text())
        assert "oauthAccount" in claude_json

    @pytest.mark.asyncio
    async def test_setup_claude_code_with_empty_env_vars(self, internal_service, tmp_paths):
        """測試空的環境變數被跳過"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        env_vars = [
            EnvironmentVariable(key="VALID_KEY", value="value1"),
            EnvironmentVariable(key="", value="value2"),  # 空 key
            EnvironmentVariable(key="EMPTY_VALUE", value=""),  # 空 value
            EnvironmentVariable(key="ANOTHER_VALID", value="value3"),
        ]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            environment_variables=env_vars,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert - 只有有效的環境變數被設定
        assert len(result["environment_variables_set"]) == 2
        assert bashrc_path.exists()

        bashrc_content = bashrc_path.read_text()
        assert 'export VALID_KEY="value1"' in bashrc_content
        assert 'export ANOTHER_VALID="value3"' in bashrc_content
        assert "EMPTY_VALUE" not in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_env_vars_with_special_chars(self, internal_service, tmp_paths):
        """測試環境變數值包含特殊字元時的轉義"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        env_vars = [
            EnvironmentVariable(key="VAR_WITH_QUOTES", value='value with "quotes"'),
            EnvironmentVariable(key="VAR_WITH_DOLLAR", value="value with $VAR"),
            EnvironmentVariable(key="VAR_WITH_BACKTICK", value="value with `command`"),
            EnvironmentVariable(key="VAR_WITH_BACKSLASH", value="value with \\backslash"),
        ]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            environment_variables=env_vars,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert
        assert len(result["environment_variables_set"]) == 4
        bashrc_content = bashrc_path.read_text()

        # 驗證特殊字元被正確轉義
        assert 'export VAR_WITH_QUOTES="value with \\"quotes\\""' in bashrc_content
        assert 'export VAR_WITH_DOLLAR="value with \\$VAR"' in bashrc_content
        assert 'export VAR_WITH_BACKTICK="value with \\`command\\`"' in bashrc_content
        assert 'export VAR_WITH_BACKSLASH="value with \\\\backslash"' in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_env_vars_update_existing_bashrc(self, internal_service, tmp_paths):
        """測試更新現有的 .bashrc 檔案"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        # 建立現有的 .bashrc 內容
        existing_content = """# User's bashrc
export PATH=/usr/local/bin:$PATH
# Aileron - Claude Code Environment Variables - START
export OLD_VAR="old_value"
# Aileron - Claude Code Environment Variables - END
alias ll='ls -la'
"""
        bashrc_path.write_text(existing_content)

        env_vars = [
            EnvironmentVariable(key="NEW_VAR", value="new_value"),
        ]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            environment_variables=env_vars,
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        bashrc_content = bashrc_path.read_text()

        # 舊的環境變數應該被移除
        assert "OLD_VAR" not in bashrc_content

        # 新的環境變數應該被加入
        assert 'export NEW_VAR="new_value"' in bashrc_content

        # 原有的其他內容應該保留
        assert "export PATH=/usr/local/bin:$PATH" in bashrc_content
        assert "alias ll='ls -la'" in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_without_auth_method(self, internal_service, tmp_paths):
        """測試無 auth_method 時不設定環境變數"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            # 沒有 auth_method, api_key, subscription_access_token
            environment_variables=[],
        )

        with patch.dict("os.environ", {internal_service._auth_method_env: "old_value"}, clear=False):
            # Act
            await internal_service.setup_claude_code(request)

            # Assert
            import os
            # 應該移除舊的環境變數
            assert os.environ.get(internal_service._auth_method_env) is None

    @pytest.mark.asyncio
    async def test_setup_claude_code_general_exception(self, internal_service, tmp_paths):
        """測試一般異常處理"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
        )

        # Mock mkdir 拋出異常
        with patch.object(Path, 'mkdir', side_effect=OSError("Disk full")):
            # Act & Assert
            with pytest.raises(OSError):
                await internal_service.setup_claude_code(request)

    @pytest.mark.asyncio
    async def test_setup_git_settings_general_exception(self, internal_service):
        """測試 Git 設定的一般異常處理"""
        # Arrange
        with patch("subprocess.run", side_effect=RuntimeError("Unexpected error")):
            request = GitSettingsRequest(
                user_name="Test User",
                user_email="test@example.com",
            )

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await internal_service.setup_git_settings(request)
            assert "Git 設定失敗" in str(exc_info.value) or "Unexpected error" in str(exc_info.value)


class TestCheckSSHStatusEdgeCases:
    """測試 SSH 狀態檢查的邊緣情況"""

    def test_check_ssh_status_public_key_not_in_authorized_keys(self, internal_service, tmp_paths):
        """測試公鑰不在 authorized_keys 中"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 創建文件 - 使用完整的 SSH 公鑰格式
        public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com"
        different_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ different@example.com"

        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text(public_key)
        (tmp_paths["ssh"] / "authorized_keys").write_text(different_key)

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"
        assert "未包含當前公鑰" in result["message"]

    def test_check_ssh_status_read_error(self, internal_service, tmp_paths):
        """測試讀取 SSH 文件失敗"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 創建文件
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")
        (tmp_paths["ssh"] / "authorized_keys").write_text("content")

        # Mock read_text 拋出異常
        with patch.object(Path, 'read_text', side_effect=PermissionError("Cannot read")):
            # Act
            result = internal_service._check_ssh_status()

            # Assert
            assert result["status"] == "success"  # 應該 fallback 到基本檢查

    def test_check_ssh_status_missing_authorized_keys(self, internal_service, tmp_paths):
        """測試缺少 authorized_keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # 只創建私鑰和公鑰
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"
        assert "authorized_keys 未配置" in result["message"]

    def test_check_ssh_status_check_exception(self, internal_service):
        """測試檢查時發生異常"""
        # Arrange
        internal_service.ssh_dir = Path("/nonexistent/path")

        with patch.object(Path, 'is_file', side_effect=RuntimeError("Disk error")):
            # Act
            result = internal_service._check_ssh_status()

            # Assert
            assert result["status"] == "failed"
            assert "檢查失敗" in result["message"]


class TestClearClaudeOauthState:
    """測試 OAuth 狀態清理 helper。"""

    def test_clear_claude_oauth_state_with_invalid_claude_json(self, internal_service, tmp_paths):
        """無法解析 ~/.claude.json 時，應忽略該檔但仍刪除舊 credentials。"""
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_path = tmp_paths["claude"] / ".credentials.json"
        credentials_path.write_text(json.dumps({"authMethod": "subscription"}))
        claude_json_path = tmp_paths["home"] / ".claude.json"
        claude_json_path.write_text("{invalid json")

        internal_service._clear_claude_oauth_state()

        assert not credentials_path.exists()
        assert claude_json_path.read_text() == "{invalid json"

    def test_clear_claude_oauth_state_with_non_dict_claude_json(self, internal_service, tmp_paths):
        """~/.claude.json 為非 object 時，不應改寫。"""
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_path = tmp_paths["claude"] / ".credentials.json"
        credentials_path.write_text(json.dumps({"authMethod": "subscription"}))
        claude_json_path = tmp_paths["home"] / ".claude.json"
        claude_json_path.write_text(json.dumps(["not", "an", "object"]))

        internal_service._clear_claude_oauth_state()

        assert not credentials_path.exists()
        assert json.loads(claude_json_path.read_text()) == ["not", "an", "object"]

    def test_clear_claude_oauth_state_without_oauth_account(self, internal_service, tmp_paths):
        """~/.claude.json 沒有 oauthAccount 時，不應多做改寫。"""
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_path = tmp_paths["claude"] / ".credentials.json"
        credentials_path.write_text(json.dumps({"authMethod": "subscription"}))
        claude_json_path = tmp_paths["home"] / ".claude.json"
        claude_json_path.write_text(json.dumps({"other": True}))

        internal_service._clear_claude_oauth_state()

        assert not credentials_path.exists()
        assert json.loads(claude_json_path.read_text()) == {"other": True}


class TestCheckClaudeStatusEdgeCases:
    """測試 Claude 狀態檢查的邊緣情況"""

    def test_check_claude_status_invalid_credentials_json(self, internal_service, tmp_paths):
        """測試憑證文件格式錯誤"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_file = tmp_paths["claude"] / ".credentials.json"
        credentials_file.write_text("{ invalid json")

        # 清理可能影響結果的環境變數
        import os
        env_backup = {}
        for key in [internal_service._auth_method_env, internal_service._env_keys_env]:
            env_backup[key] = os.environ.pop(key, None)

        try:
            # Act
            result = internal_service._check_claude_status()

            # Assert - 文件格式錯誤且無環境變數，應該返回 pending
            assert result["status"] == "pending"
        finally:
            # 恢復環境變數
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_check_claude_status_legacy_oauth_format(self, internal_service, tmp_paths):
        """測試舊格式的 OAuth（只有 claudeAiOauth 欄位）"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials = {"claudeAiOauth": {"accessToken": "token"}}
        credentials_file = tmp_paths["claude"] / ".credentials.json"
        credentials_file.write_text(json.dumps(credentials))

        import os
        env_backup = {}
        for key in [internal_service._auth_method_env, internal_service._env_keys_env]:
            env_backup[key] = os.environ.pop(key, None)

        try:
            result = internal_service._check_claude_status()

            assert result["status"] == "success"
        finally:
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_check_claude_status_subscription_empty_file(self, internal_service, tmp_paths):
        """測試 subscription 模式但文件為空"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        import os
        os.environ[internal_service._auth_method_env] = "subscription"

        credentials_file = tmp_paths["claude"] / ".credentials.json"
        credentials_file.write_text("")

        try:
            # Act
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "pending"
        finally:
            os.environ.pop(internal_service._auth_method_env, None)

    def test_check_claude_status_missing_env_vars(self, internal_service, tmp_paths):
        """測試 API Key 模式但缺少環境變數"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        import os
        os.environ[internal_service._auth_method_env] = "api_key"
        os.environ[internal_service._env_keys_env] = "REQUIRED_VAR1,REQUIRED_VAR2"

        try:
            # Act - 不設定實際的環境變數
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "failed"
            assert "缺少必要的環境變數" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)
            os.environ.pop(internal_service._env_keys_env, None)

    def test_check_claude_status_api_key_no_env_vars(self, internal_service, tmp_paths):
        """測試 API Key 模式但無設定環境變數"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        import os
        os.environ[internal_service._auth_method_env] = "api_key"

        try:
            # Act
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "pending"
            assert "尚未設定" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)

    def test_check_claude_status_api_key_ignores_stale_oauth_credentials(self, internal_service, tmp_paths):
        """測試 API Key 模式不會被殘留的 OAuth credentials 誤判"""
        internal_service.claude_dir = tmp_paths["claude"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_file = tmp_paths["claude"] / ".credentials.json"
        credentials_file.write_text(json.dumps({"claudeAiOauth": {"accessToken": "old-token"}}))

        import os
        os.environ[internal_service._auth_method_env] = "api_key"
        os.environ[internal_service._env_keys_env] = "ANTHROPIC_API_KEY"
        os.environ["ANTHROPIC_API_KEY"] = "live-key"

        try:
            result = internal_service._check_claude_status()

            assert result["status"] == "success"
            assert "環境變數已同步" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)
            os.environ.pop(internal_service._env_keys_env, None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_check_claude_status_no_config(self, internal_service, tmp_paths):
        """測試完全無設定"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # Act
        result = internal_service._check_claude_status()

        # Assert
        assert result["status"] == "pending"
        assert "尚未同步" in result["message"]

    def test_check_claude_status_exception(self, internal_service):
        """測試檢查時發生異常"""
        # Arrange
        internal_service.claude_dir = Path("/nonexistent/path")

        with patch.object(Path, 'is_file', side_effect=RuntimeError("Disk error")):
            # Act
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "failed"
            assert "檢查失敗" in result["message"]


class TestCheckGitStatusEdgeCases:
    """測試 Git 狀態檢查的邊緣情況"""

    @patch("subprocess.run")
    def test_check_git_status_exception(self, mock_run, internal_service):
        """測試檢查時發生異常"""
        # Arrange
        mock_run.side_effect = RuntimeError("Git not found")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "failed"
        assert "檢查失敗" in result["message"]


class TestEnsureDirectoryExists:
    """測試確保目錄存在"""

    def test_ensure_directory_exists(self, internal_service, tmp_paths):
        """測試創建目錄"""
        # Arrange
        test_dir = tmp_paths["home"] / "test_dir"

        # Act
        internal_service._ensure_directory_exists(test_dir, mode=0o755)

        # Assert
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_exists_already_exists(self, internal_service, tmp_paths):
        """測試目錄已存在"""
        # Arrange
        test_dir = tmp_paths["home"] / "test_dir"
        test_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        # Act - 應該不會拋出異常
        internal_service._ensure_directory_exists(test_dir, mode=0o755)

        # Assert
        assert test_dir.exists()
