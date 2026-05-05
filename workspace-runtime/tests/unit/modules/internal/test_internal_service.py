"""Internal Service unit tests."""

from __future__ import annotations

import json
import os
import pytest
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from app.modules.internal.service import InternalService
from app.modules.internal.models import (
    SSHKeysRequest,
    ClaudeCodeRequest,
    CodexSettingsRequest,
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
            service.codex_auth_dir = tmp_path / ".codex"
            service.codex_sessions_dir = tmp_path / ".codex-sessions"
            return service


@pytest.fixture
def tmp_paths(tmp_path):
    """Create temporary paths fixture"""
    return {
        "home": tmp_path,
        "ssh": tmp_path / ".ssh",
        "claude": tmp_path / ".claude",
        "codex": tmp_path / ".codex",
        "codex_sessions": tmp_path / ".codex-sessions",
    }


class TestInternalServiceInitialization:
    """Test Internal Service initialization"""

    def test_init(self):
        """Test service initialization"""
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
    """Test setting up SSH Keys"""

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_success(self, internal_service, tmp_paths):
        """Test successfully setting up SSH Keys"""
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

        # Verify files exist
        assert (tmp_paths["ssh"] / "id_rsa").exists()
        assert (tmp_paths["ssh"] / "id_rsa.pub").exists()
        assert (tmp_paths["ssh"] / "authorized_keys").exists()

    @pytest.mark.asyncio
    async def test_setup_ssh_keys_adds_newline(self, internal_service, tmp_paths):
        """Test automatically adding newline"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        request = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",  # No trailing newline
            public_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com",  # No trailing newline
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
        """Test duplicate public key is not added twice"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com"

        # Add once first
        request1 = SSHKeysRequest(
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
            public_key=public_key,
        )
        await internal_service.setup_ssh_keys(request1)

        # Act - Add same public key again
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
        """Test preserving existing authorized_keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Pre-add a public key
        existing_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ existing@example.com"
        (tmp_paths["ssh"] / "authorized_keys").write_text(f"{existing_key}\n")

        # Act - Add new public key
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
        """Test SSH directory permissions"""
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
        """Test SSH file permissions"""
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
        """Test SSH Keys setup error handling"""
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
    """Test setting up Claude Code"""

    @pytest.mark.asyncio
    async def test_setup_claude_code_subscription(self, internal_service, tmp_paths):
        """Test setting up Subscription authentication"""
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

        # Verify credentials content
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert credentials["authMethod"] == "subscription"
        assert credentials["claudeAiOauth"]["accessToken"] == "test-access-token"
        assert credentials["claudeAiOauth"]["refreshToken"] == "test-refresh-token"

        # Verify .claude.json content
        claude_json = json.loads((tmp_paths["home"] / ".claude.json").read_text())
        assert "oauthAccount" in claude_json
        assert claude_json["oauthAccount"]["emailAddress"] == "test@example.com"


class TestSetupCodex:
    """Test setting up Codex."""

    @pytest.mark.asyncio
    async def test_setup_codex_writes_env_block(self, internal_service, tmp_paths):
        """Test Codex environment variables are written to managed shell block."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        request = CodexSettingsRequest(
            auth_method="apikey",
            login_status="notConnected",
            model="gpt-5.3-codex",
            environment_variables=[
                EnvironmentVariable(key="OPENAI_BASE_URL", value="https://example.test"),
            ],
        )

        result = await internal_service.setup_codex(request)

        assert result["codex_home"] == str(tmp_paths["codex"])
        assert result["environment_variables_set"] == ["OPENAI_BASE_URL"]
        assert os.environ["CODEX_AUTH_METHOD"] == "apikey"
        bashrc = (tmp_paths["home"] / ".bashrc").read_text()
        assert "# Aileron - Codex Environment Variables - START" in bashrc
        assert 'export OPENAI_BASE_URL="https://example.test"' in bashrc

    @pytest.mark.asyncio
    async def test_setup_codex_rejects_codex_home_override(self, internal_service, tmp_paths):
        """Test CODEX_HOME is system-managed and cannot be overridden."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        request = CodexSettingsRequest(
            environment_variables=[
                EnvironmentVariable(key="CODEX_HOME", value="/tmp/override"),
            ],
        )

        with pytest.raises(ValueError):
            await internal_service.setup_codex(request)

    @pytest.mark.asyncio
    async def test_setup_codex_clears_auth_but_preserves_env(self, internal_service, tmp_paths):
        """Test logout clears auth without deleting Codex env settings."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        tmp_paths["codex"].mkdir(parents=True)
        (tmp_paths["codex"] / "auth.json").write_text("{}")
        (tmp_paths["codex"] / "installation_id").write_text("installation-1\n")
        (tmp_paths["codex"] / "config.toml").write_text("model = \"gpt-5.3-codex\"\n")

        request = CodexSettingsRequest(
            clear_auth=True,
            environment_variables=[
                EnvironmentVariable(key="OPENAI_BASE_URL", value="https://example.test"),
            ],
        )

        result = await internal_service.setup_codex(request)

        assert result["has_cli_auth"] is False
        assert not (tmp_paths["codex"] / "auth.json").exists()
        assert not (tmp_paths["codex"] / "installation_id").exists()
        assert (tmp_paths["codex"] / "config.toml").exists()
        assert "OPENAI_BASE_URL" in (tmp_paths["home"] / ".bashrc").read_text()

    @pytest.mark.asyncio
    async def test_setup_codex_writes_synchronized_cli_state(self, internal_service, tmp_paths):
        """Test synchronized Codex CLI files are written to CODEX_HOME."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        request = CodexSettingsRequest(
            login_status="connected",
            cliState={
                "authJson": {
                    "auth_mode": "chatgpt",
                    "OPENAI_API_KEY": None,
                    "tokens": {
                        "access_token": "access-token",
                        "refresh_token": "refresh-token",
                        "id_token": "id-token",
                        "account_id": "account-1",
                    },
                    "last_refresh": "2026-05-05T00:53:48Z",
                },
                "configToml": '[projects."/workspace"]\ntrust_level = "trusted"\n',
                "installationId": "installation-1",
            },
        )

        result = await internal_service.setup_codex(request)

        auth_json = json.loads((tmp_paths["codex"] / "auth.json").read_text())
        assert auth_json["auth_mode"] == "chatgpt"
        assert auth_json["tokens"]["refresh_token"] == "refresh-token"
        assert (tmp_paths["codex"] / "config.toml").read_text() == '[projects."/workspace"]\ntrust_level = "trusted"\n'
        assert (tmp_paths["codex"] / "installation_id").read_text() == "installation-1\n"
        assert result["has_cli_auth"] is True
        assert result["has_config"] is True
        assert result["has_installation_id"] is True

    @pytest.mark.asyncio
    async def test_setup_codex_cli_state_replaces_auth_and_preserves_unprovided_config(self, internal_service, tmp_paths):
        """Test synchronized Codex CLI state replaces auth and preserves unprovided config."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        tmp_paths["codex"].mkdir(parents=True)
        (tmp_paths["codex"] / "auth.json").write_text('{"auth_mode":"chatgpt"}')
        (tmp_paths["codex"] / "config.toml").write_text("stale = true\n")
        (tmp_paths["codex"] / "installation_id").write_text("stale-installation\n")

        request = CodexSettingsRequest(
            login_status="connected",
            cliState={
                "authJson": {
                    "auth_mode": "chatgpt",
                    "tokens": {"access_token": "new-access"},
                },
                "configToml": None,
                "installationId": "new-installation",
            },
        )

        result = await internal_service.setup_codex(request)

        auth_json = json.loads((tmp_paths["codex"] / "auth.json").read_text())
        assert auth_json["tokens"]["access_token"] == "new-access"
        assert (tmp_paths["codex"] / "config.toml").read_text() == "stale = true\n"
        assert (tmp_paths["codex"] / "installation_id").read_text() == "new-installation\n"
        assert result["has_cli_auth"] is True
        assert result["has_config"] is True
        assert result["has_installation_id"] is True

    @pytest.mark.asyncio
    async def test_setup_codex_cli_state_merges_existing_config(self, internal_service, tmp_paths):
        """Test synchronized Codex config merges into existing config.toml."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]
        tmp_paths["codex"].mkdir(parents=True)
        (tmp_paths["codex"] / "config.toml").write_text(
            'model = "gpt-5.3-codex"\n'
            'approval_policy = "on-request"\n\n'
            '[projects."/workspace"]\n'
            'trust_level = "untrusted"\n'
            'existing = "keep"\n\n'
            "[features]\n"
            "codex_hooks = true\n"
        )

        request = CodexSettingsRequest(
            login_status="connected",
            cliState={
                "configToml": (
                    'model = "gpt-5.5"\n\n'
                    '[projects."/workspace"]\n'
                    'trust_level = "trusted"\n'
                ),
            },
        )

        await internal_service.setup_codex(request)

        config = (tmp_paths["codex"] / "config.toml").read_text()
        assert 'model = "gpt-5.5"' in config
        assert 'approval_policy = "on-request"' in config
        assert 'trust_level = "trusted"' in config
        assert 'existing = "keep"' in config
        assert "codex_hooks = true" in config

    @pytest.mark.asyncio
    async def test_setup_codex_cli_state_does_not_require_codex_binary(self, internal_service, tmp_paths):
        """Test synchronized Codex CLI state can be applied without Codex binary."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        internal_service.codex_sessions_dir = tmp_paths["codex_sessions"]

        request = CodexSettingsRequest(
            login_status="connected",
            cliState={
                "authJson": {
                    "auth_mode": "chatgpt",
                    "tokens": {"refresh_token": "refresh-token"},
                },
            },
        )

        result = await internal_service.setup_codex(request)

        assert result["has_cli_auth"] is True
        assert json.loads((tmp_paths["codex"] / "auth.json").read_text())["tokens"]["refresh_token"] == "refresh-token"

    def test_check_codex_status_reports_success_for_auth(self, internal_service, tmp_paths):
        """Test setup status reports Codex auth."""
        internal_service.codex_auth_dir = tmp_paths["codex"]
        tmp_paths["codex"].mkdir(parents=True)
        (tmp_paths["codex"] / "auth.json").write_text("{}")

        status = internal_service._check_codex_status()

        assert status["status"] == "success"

    @pytest.mark.asyncio
    async def test_setup_claude_code_api_key(self, internal_service, tmp_paths):
        """Test setting up API Key authentication"""
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
        """Test switching to API Key clears stale OAuth state"""
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
        """Test subscription mode preserves existing ~/.claude.json fields and updates oauthAccount."""
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
        """Test setting up environment variables to .bashrc"""
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
        """Test Subscription mode does not sync environment variables"""
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
        # Subscription mode should not write to .bashrc
        if bashrc_path.exists():
            bashrc_content = bashrc_path.read_text()
            assert "TEST_VAR" not in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_auto_detect_auth_method(self, internal_service, tmp_paths):
        """Test auto-detecting authentication method"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # Test 1: Has subscription token -> subscription
        request1 = ClaudeCodeRequest(
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,
        )

        result1 = await internal_service.setup_claude_code(request1)
        assert result1["auth_method"] == "subscription"

        # Test 2: Has api_key -> api_key
        request2 = ClaudeCodeRequest(
            api_key="test-api-key",
        )

        result2 = await internal_service.setup_claude_code(request2)
        assert result2["auth_method"] == "api_key"

    @pytest.mark.asyncio
    async def test_setup_claude_code_normalize_expires_at_integer(self, internal_service, tmp_paths):
        """Test normalizing integer type expiresAt"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at=1234567890000,  # Integer
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert credentials["claudeAiOauth"]["expiresAt"] == 1234567890000

    @pytest.mark.asyncio
    async def test_setup_claude_code_normalize_expires_at_iso_string(self, internal_service, tmp_paths):
        """Test normalizing ISO8601 string expiresAt"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
            subscription_refresh_token="test-refresh",
            subscription_expires_at="2024-01-01T00:00:00Z",  # ISO8601 string
        )

        # Act
        await internal_service.setup_claude_code(request)

        # Assert
        credentials = json.loads((tmp_paths["claude"] / ".credentials.json").read_text())
        assert isinstance(credentials["claudeAiOauth"]["expiresAt"], int)

    @pytest.mark.asyncio
    @patch("app.modules.internal.service.SettingsService")
    async def test_setup_claude_code_with_model_override(self, mock_settings_service, internal_service, tmp_paths):
        """Test model override setting"""
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
    """Test expiresAt normalization"""

    def test_normalize_expires_at_integer(self):
        """Test integer"""
        result = InternalService._normalize_expires_at(1234567890000)
        assert result == 1234567890000

    def test_normalize_expires_at_string_integer(self):
        """Test string integer"""
        result = InternalService._normalize_expires_at("1234567890000")
        assert result == 1234567890000

    def test_normalize_expires_at_iso8601(self):
        """Test ISO8601 format"""
        result = InternalService._normalize_expires_at("2024-01-01T00:00:00Z")
        assert isinstance(result, int)
        assert result > 0

    def test_normalize_expires_at_none(self):
        """Test None"""
        result = InternalService._normalize_expires_at(None)
        assert result is None

    def test_normalize_expires_at_empty_string(self):
        """Test empty string"""
        result = InternalService._normalize_expires_at("")
        assert result is None

    def test_normalize_expires_at_invalid_string(self):
        """Test invalid string"""
        result = InternalService._normalize_expires_at("invalid")
        assert result is None


class TestSetupGitSettings:
    """Test setting up Git settings"""

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_setup_git_settings_success(self, mock_run, internal_service):
        """Test successfully setting up Git settings"""
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

        # Verify git config commands were called
        assert mock_run.call_count == 4  # set name, set email, verify name, verify email

    @pytest.mark.asyncio
    async def test_setup_git_settings_verify(self, internal_service):
        """Test verifying Git settings"""
        # Arrange
        def run_side_effect(*args, **kwargs):
            cmd = args[0]
            # Set command: ["git", "config", "--global", "user.name", "Test User"]  (5 elements)
            # Verify command: ["git", "config", "--global", "user.name"]  (4 elements)
            if "user.name" in cmd and len(cmd) == 4:
                # This is read command
                return MagicMock(returncode=0, stdout="Test User\n", stderr="")
            elif "user.email" in cmd and len(cmd) == 4:
                # This is read command
                return MagicMock(returncode=0, stdout="test@example.com\n", stderr="")
            else:
                # This is set command or other
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
        """Test Git command failure"""
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
    """Test getting setup status"""

    @pytest.mark.asyncio
    async def test_get_setup_status(self, internal_service):
        """Test getting setup status"""
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
    """Test checking SSH status"""

    def test_check_ssh_status_success(self, internal_service, tmp_paths):
        """Test SSH fully configured"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Create required files
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")
        (tmp_paths["ssh"] / "authorized_keys").write_text("public key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "success"

    def test_check_ssh_status_pending(self, internal_service, tmp_paths):
        """Test SSH not configured"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "pending"

    def test_check_ssh_status_incomplete(self, internal_service, tmp_paths):
        """Test SSH configuration incomplete"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Only create private key
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"


class TestCheckClaudeStatus:
    """Test checking Claude Code status"""

    def test_check_claude_status_subscription(self, tmp_path):
        """Test Subscription authentication status"""
        # Arrange - Create isolated service instance to avoid state leakage
        import os
        # Clear environment variables that may affect test
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

                    # Ensure file exists and is readable
                    assert credentials_file.exists()
                    assert credentials_file.is_file()

                    # Act
                    result = service._check_claude_status()

                    # Assert
                    assert result["status"] == "success", f"Expected 'success' but got '{result['status']}'. Message: {result.get('message', 'N/A')}"
        finally:
            # Restore environment variables
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_check_claude_status_pending(self, internal_service, tmp_paths):
        """Test not configured status"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # Act
        result = internal_service._check_claude_status()

        # Assert
        assert result["status"] == "pending"


class TestCheckGitStatus:
    """Test checking Git status"""

    @patch("subprocess.run")
    def test_check_git_status_success(self, mock_run, internal_service):
        """Test Git fully configured"""
        # Arrange
        mock_run.return_value = MagicMock(returncode=0, stdout="Test User\n", stderr="")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "success"

    @patch("subprocess.run")
    def test_check_git_status_pending(self, mock_run, internal_service):
        """Test Git not configured"""
        # Arrange
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "pending"

    @patch("subprocess.run")
    def test_check_git_status_incomplete(self, mock_run, internal_service):
        """Test Git configuration incomplete"""
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
    """Test applying firewall settings"""

    @staticmethod
    def _load_firewall_template() -> str:
        return (
            Path(__file__).resolve().parents[4]
            / "app"
            / "jinja_templates"
            / "firewall.sh.j2"
        ).read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_success(self, internal_service):
        """Test successfully applying firewall settings"""
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
    async def test_apply_firewall_settings_renders_blocking_rules_when_network_disabled(
        self, internal_service
    ):
        template_content = self._load_firewall_template()

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=template_content):
                with patch.object(Path, "write_text") as mock_write_text:
                    with patch.object(Path, "chmod"):
                        with patch("subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

                            request = FirewallConfigRequest(
                                network_access_enabled=False,
                                domain_access_mode="all",
                                allowed_domains=[],
                            )

                            result = await internal_service.apply_firewall_settings(request)

        assert result["status"] == "success"
        rendered_script = mock_write_text.call_args.args[0]
        assert "iptables -P OUTPUT DROP" in rendered_script
        assert "iptables -A OUTPUT -p udp --dport 53 -j ACCEPT" in rendered_script
        assert "log \"Network access disabled" in rendered_script

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_renders_allowlist_rules_for_specific_domains(
        self, internal_service
    ):
        template_content = self._load_firewall_template()

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=template_content):
                with patch.object(Path, "write_text") as mock_write_text:
                    with patch.object(Path, "chmod"):
                        with patch("subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="Success", stderr="")

                            request = FirewallConfigRequest(
                                network_access_enabled=True,
                                domain_access_mode="specific",
                                allowed_domains=["example.com"],
                            )

                            result = await internal_service.apply_firewall_settings(request)

        assert result["status"] == "success"
        rendered_script = mock_write_text.call_args.args[0]
        assert "iptables -P OUTPUT DROP" in rendered_script
        assert "DOMAIN_IPS=$(dig +short example.com A example.com AAAA" in rendered_script
        assert 'iptables -A OUTPUT -d "$IP" -j ACCEPT' in rendered_script

    @pytest.mark.asyncio
    async def test_apply_firewall_settings_script_failure(self, internal_service):
        """Test firewall script execution failure"""
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
        """Test template file not found"""
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
        """Test firewall script timeout"""
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
                    assert "timeout" in result["message"]


class TestSetupClaudeCodeEdgeCases:
    """Test edge cases for Claude Code setup"""

    @pytest.mark.asyncio
    async def test_setup_claude_code_with_existing_malformed_claude_json(self, internal_service, tmp_paths):
        """Test handling when .claude.json exists but has malformed format"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]

        # Create malformed .claude.json
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

        # Assert - Should create new .claude.json instead of raising exception
        assert result["auth_method"] == "subscription"
        assert claude_json_path.exists()
        claude_json = json.loads(claude_json_path.read_text())
        assert "oauthAccount" in claude_json

    @pytest.mark.asyncio
    async def test_setup_claude_code_with_empty_env_vars(self, internal_service, tmp_paths):
        """Test empty environment variables are skipped"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        env_vars = [
            EnvironmentVariable(key="VALID_KEY", value="value1"),
            EnvironmentVariable(key="", value="value2"),  # Empty key
            EnvironmentVariable(key="EMPTY_VALUE", value=""),  # Empty value
            EnvironmentVariable(key="ANOTHER_VALID", value="value3"),
        ]

        request = ClaudeCodeRequest(
            auth_method="api_key",
            environment_variables=env_vars,
        )

        # Act
        result = await internal_service.setup_claude_code(request)

        # Assert - Only valid environment variables are set
        assert len(result["environment_variables_set"]) == 2
        assert bashrc_path.exists()

        bashrc_content = bashrc_path.read_text()
        assert 'export VALID_KEY="value1"' in bashrc_content
        assert 'export ANOTHER_VALID="value3"' in bashrc_content
        assert "EMPTY_VALUE" not in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_env_vars_with_special_chars(self, internal_service, tmp_paths):
        """Test escaping when environment variable values contain special characters"""
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

        # Verify special characters are properly escaped
        assert 'export VAR_WITH_QUOTES="value with \\"quotes\\""' in bashrc_content
        assert 'export VAR_WITH_DOLLAR="value with \\$VAR"' in bashrc_content
        assert 'export VAR_WITH_BACKTICK="value with \\`command\\`"' in bashrc_content
        assert 'export VAR_WITH_BACKSLASH="value with \\\\backslash"' in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_env_vars_update_existing_bashrc(self, internal_service, tmp_paths):
        """Test updating existing .bashrc file"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        internal_service.home_dir = tmp_paths["home"]
        bashrc_path = tmp_paths["home"] / ".bashrc"

        # Create existing .bashrc content
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

        # Old environment variables should be removed
        assert "OLD_VAR" not in bashrc_content

        # New environment variables should be added
        assert 'export NEW_VAR="new_value"' in bashrc_content

        # Original other content should be preserved
        assert "export PATH=/usr/local/bin:$PATH" in bashrc_content
        assert "alias ll='ls -la'" in bashrc_content

    @pytest.mark.asyncio
    async def test_setup_claude_code_without_auth_method(self, internal_service, tmp_paths):
        """Test no environment variables set when no auth_method"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            # No auth_method, api_key, subscription_access_token
            environment_variables=[],
        )

        with patch.dict("os.environ", {internal_service._auth_method_env: "old_value"}, clear=False):
            # Act
            await internal_service.setup_claude_code(request)

            # Assert
            import os
            # Should remove old environment variables
            assert os.environ.get(internal_service._auth_method_env) is None

    @pytest.mark.asyncio
    async def test_setup_claude_code_general_exception(self, internal_service, tmp_paths):
        """Test general exception handling"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        request = ClaudeCodeRequest(
            auth_method="subscription",
            subscription_access_token="test-token",
        )

        # Mock mkdir to raise exception
        with patch.object(Path, 'mkdir', side_effect=OSError("Disk full")):
            # Act & Assert
            with pytest.raises(OSError):
                await internal_service.setup_claude_code(request)

    @pytest.mark.asyncio
    async def test_setup_git_settings_general_exception(self, internal_service):
        """Test general exception handling for Git settings"""
        # Arrange
        with patch("subprocess.run", side_effect=RuntimeError("Unexpected error")):
            request = GitSettingsRequest(
                user_name="Test User",
                user_email="test@example.com",
            )

            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await internal_service.setup_git_settings(request)
            assert "Git setup failed" in str(exc_info.value) or "Unexpected error" in str(exc_info.value)


class TestCheckSSHStatusEdgeCases:
    """Test edge cases for SSH status check"""

    def test_check_ssh_status_public_key_not_in_authorized_keys(self, internal_service, tmp_paths):
        """Test public key not in authorized_keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Create files - use complete SSH public key format
        public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ test@example.com"
        different_key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ different@example.com"

        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text(public_key)
        (tmp_paths["ssh"] / "authorized_keys").write_text(different_key)

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"
        assert "does not contain current public key" in result["message"]

    def test_check_ssh_status_read_error(self, internal_service, tmp_paths):
        """Test reading SSH files failure"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Create files
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")
        (tmp_paths["ssh"] / "authorized_keys").write_text("content")

        # Mock read_text to raise exception
        with patch.object(Path, 'read_text', side_effect=PermissionError("Cannot read")):
            # Act
            result = internal_service._check_ssh_status()

            # Assert
            assert result["status"] == "success"  # Should fallback to basic check

    def test_check_ssh_status_missing_authorized_keys(self, internal_service, tmp_paths):
        """Test missing authorized_keys"""
        # Arrange
        internal_service.ssh_dir = tmp_paths["ssh"]
        tmp_paths["ssh"].mkdir(parents=True, exist_ok=True)

        # Only create private and public keys
        (tmp_paths["ssh"] / "id_rsa").write_text("private key")
        (tmp_paths["ssh"] / "id_rsa.pub").write_text("public key")

        # Act
        result = internal_service._check_ssh_status()

        # Assert
        assert result["status"] == "failed"
        assert "authorized_keys not configured" in result["message"]

    def test_check_ssh_status_check_exception(self, internal_service):
        """Test exception during check"""
        # Arrange
        internal_service.ssh_dir = Path("/nonexistent/path")

        with patch.object(Path, 'is_file', side_effect=RuntimeError("Disk error")):
            # Act
            result = internal_service._check_ssh_status()

            # Assert
            assert result["status"] == "failed"
            assert "Check failed" in result["message"]


class TestClearClaudeOauthState:
    """Test OAuth state cleanup helper."""

    def test_clear_claude_oauth_state_with_invalid_claude_json(self, internal_service, tmp_paths):
        """When ~/.claude.json cannot be parsed, should ignore that file but still delete old credentials."""
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
        """When ~/.claude.json is not an object, should not overwrite."""
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
        """When ~/.claude.json has no oauthAccount, should not do extra overwrite."""
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
    """Test edge cases for Claude status check"""

    def test_check_claude_status_invalid_credentials_json(self, internal_service, tmp_paths):
        """Test credentials file format error"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]
        tmp_paths["claude"].mkdir(parents=True, exist_ok=True)

        credentials_file = tmp_paths["claude"] / ".credentials.json"
        credentials_file.write_text("{ invalid json")

        # Clear environment variables that may affect result
        import os
        env_backup = {}
        for key in [internal_service._auth_method_env, internal_service._env_keys_env]:
            env_backup[key] = os.environ.pop(key, None)

        try:
            # Act
            result = internal_service._check_claude_status()

            # Assert - File format error and no environment variables, should return pending
            assert result["status"] == "pending"
        finally:
            # Restore environment variables
            for key, value in env_backup.items():
                if value is not None:
                    os.environ[key] = value

    def test_check_claude_status_legacy_oauth_format(self, internal_service, tmp_paths):
        """Test old OAuth format (only claudeAiOauth field)"""
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
        """Test subscription mode but file is empty"""
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
        """Test API Key mode but missing environment variables"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        import os
        os.environ[internal_service._auth_method_env] = "api_key"
        os.environ[internal_service._env_keys_env] = "REQUIRED_VAR1,REQUIRED_VAR2"

        try:
            # Act - Don't set actual environment variables
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "failed"
            assert "Missing required environment variables" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)
            os.environ.pop(internal_service._env_keys_env, None)

    def test_check_claude_status_api_key_no_env_vars(self, internal_service, tmp_paths):
        """Test API Key mode but no environment variables configured"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        import os
        os.environ[internal_service._auth_method_env] = "api_key"

        try:
            # Act
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "pending"
            assert "not yet configured" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)

    def test_check_claude_status_api_key_ignores_stale_oauth_credentials(self, internal_service, tmp_paths):
        """Test API Key mode is not misjudged by residual OAuth credentials"""
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
            assert "environment variables synced" in result["message"]
        finally:
            os.environ.pop(internal_service._auth_method_env, None)
            os.environ.pop(internal_service._env_keys_env, None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    def test_check_claude_status_no_config(self, internal_service, tmp_paths):
        """Test completely unconfigured"""
        # Arrange
        internal_service.claude_dir = tmp_paths["claude"]

        # Act
        result = internal_service._check_claude_status()

        # Assert
        assert result["status"] == "pending"
        assert "not yet synced" in result["message"]

    def test_check_claude_status_exception(self, internal_service):
        """Test exception during check"""
        # Arrange
        internal_service.claude_dir = Path("/nonexistent/path")

        with patch.object(Path, 'is_file', side_effect=RuntimeError("Disk error")):
            # Act
            result = internal_service._check_claude_status()

            # Assert
            assert result["status"] == "failed"
            assert "Check failed" in result["message"]


class TestCheckGitStatusEdgeCases:
    """Test edge cases for Git status check"""

    @patch("subprocess.run")
    def test_check_git_status_exception(self, mock_run, internal_service):
        """Test exception during check"""
        # Arrange
        mock_run.side_effect = RuntimeError("Git not found")

        # Act
        result = internal_service._check_git_status()

        # Assert
        assert result["status"] == "failed"
        assert "Check failed" in result["message"]


class TestEnsureDirectoryExists:
    """Test ensuring directory exists"""

    def test_ensure_directory_exists(self, internal_service, tmp_paths):
        """Test creating directory"""
        # Arrange
        test_dir = tmp_paths["home"] / "test_dir"

        # Act
        internal_service._ensure_directory_exists(test_dir, mode=0o755)

        # Assert
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_exists_already_exists(self, internal_service, tmp_paths):
        """Test directory already exists"""
        # Arrange
        test_dir = tmp_paths["home"] / "test_dir"
        test_dir.mkdir(mode=0o755, parents=True, exist_ok=True)

        # Act - Should not raise exception
        internal_service._ensure_directory_exists(test_dir, mode=0o755)

        # Assert
        assert test_dir.exists()
