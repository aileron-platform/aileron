"""Unit Tests for RuntimeSyncService"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import httpx
import pytest

from app.config.model_registry import normalize_model_selection
from app.modules.settings.models import CodexSettings, UserSettings
from app.modules.workspace.runtime.sync import RuntimeSyncService
from app.modules.settings.user_settings import SettingsService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=None)
    session.get.return_value.runtime_instance_id = "runtime-instance-123"
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def sample_workspace():
    """Sample Workspace"""
    from app.db import models as db_models

    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-123"
    workspace.name = "Test Workspace"
    workspace.owner_id = "user-123"
    workspace.runtime_status = "running"
    workspace.runtime_internal_url = "http://workspace-runtime-workspace-123:3002"
    workspace.runtime_instance_id = "runtime-instance-123"
    return workspace


@pytest.fixture
def sample_runtimes():
    """Sample Runtime List"""
    return [
        {
            "workspace_id": "workspace-123",
            "workspace_name": "Workspace 1",
            "url": "http://localhost:8080",
        },
        {
            "workspace_id": "workspace-456",
            "workspace_name": "Workspace 2",
            "url": "http://localhost:8081",
        },
    ]


@pytest.fixture
def ssh_changes():
    """SSH Settings Changes"""
    return {
        "privateKey": "-----BEGIN RSA PRIVATE KEY-----\ntest-private-key\n-----END RSA PRIVATE KEY-----",
        "publicKey": "ssh-rsa test-public-key user@example.com",
    }


@pytest.fixture
def claude_code_changes():
    """Claude Code Settings Changes"""
    return {
        "authMethod": "subscription",
        "subscriptionAccessToken": "access-token-123",
        "subscriptionRefreshToken": "refresh-token-456",
        "subscriptionExpiresAt": "2025-12-31T23:59:59Z",
        "authKey": "api-key-789",
        "oauthAccount": {
            "accountUuid": "account-1",
            "emailAddress": "claude@example.com",
            "organizationUuid": "org-1",
            "displayName": "Claude User",
        },
        "model": "claude-fable-5",
        "environmentVariables": [
            {"key": "VAR1", "value": "value1"},
            {"key": "VAR2", "value": "value2"},
        ],
    }


@pytest.fixture
def codex_changes():
    """Codex Settings Changes"""
    return {
        "authMethod": "subscription",
        "loginStatus": "connected",
        "account": {
            "accountId": "codex-account-1",
            "email": "codex@example.com",
            "planType": "pro",
        },
        "model": "gpt-5.6-sol",
        "environmentVariables": [
            {"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"},
        ],
        "cliState": {
            "authJson": {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": "access-token",
                    "refresh_token": "refresh-token",
                    "id_token": "id-token",
                    "account_id": "codex-account-1",
                },
            },
            "configToml": '[projects."/workspace"]\ntrust_level = "trusted"\n',
            "installationId": "installation-1",
        },
        "authFlow": None,
    }


@pytest.fixture
def git_changes():
    """Git Settings Changes"""
    return {
        "userName": "Test User",
        "userEmail": "test@example.com",
    }


@pytest.fixture
def capabilities_changes():
    """Manager capabilities payload emitted with API aliases."""
    return {
        "defaultTool": "claude",
        "tools": [
            {
                "id": "claude",
                "models": ["claude-opus-4-8"],
                "defaultModel": "claude-opus-4-8",
                "modes": ["execute", "plan"],
                "defaultMode": "execute",
                "contextWindow": 200000,
            }
        ],
    }


@pytest.fixture
def firewall_changes():
    """Firewall Settings Changes"""
    return {
        "egressMode": "allowlist",
        "allowedDomains": ["github.com", "google.com", "anthropic.com"],
    }


@pytest.fixture
def sync_service(mock_db_session, monkeypatch):
    """RuntimeSyncService Instance"""
    monkeypatch.setattr(
        "app.modules.workspace.runtime.sync.runtime_command_headers",
        lambda **_kwargs: {
            "Authorization": "Bearer signed-assertion",
            "Content-Type": "application/json",
        },
    )
    return RuntimeSyncService(mock_db_session)


# ============================================================================
# RuntimeSyncService Tests - Basic Operations
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestRuntimeSyncServiceBasic:
    """RuntimeSyncService Basic Operation Tests"""

    async def test_get_user_workspace_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test: Successfully Get User Workspace Runtimes"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert len(result) == 1
        assert result[0]["workspace_id"] == "workspace-123"
        assert result[0]["url"] == "http://workspace-runtime-workspace-123:3002"

    async def test_get_user_workspace_runtimes_no_running(
        self, sync_service, mock_db_session
    ):
        """Test: No Running Workspaces"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert len(result) == 0

    async def test_get_user_workspace_runtimes_ignores_external_only_runtime(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test: Runtime synchronization requires the cluster-internal URL."""
        # Arrange
        sample_workspace.runtime_internal_url = None
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert result == []


# ============================================================================
# RuntimeSyncService Tests - SSH Keys Sync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestSSHKeysSynchronization:
    """SSH Keys Synchronization Tests"""

    async def test_sync_ssh_keys_success(self, sync_service, ssh_changes):
        """Test: Successfully Sync SSH Keys"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "SSH keys updated",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_ssh_keys(
                "http://localhost:8080", ssh_changes, "workspace-123"
            )

        # Assert
        assert result["type"] == "ssh_keys"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()
        assert (
            mock_client.post.call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/ssh-keys"
        )

    async def test_sync_ssh_keys_network_error(self, sync_service, ssh_changes):
        """Test: SSH Keys sync network error"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )

    async def test_sync_ssh_keys_http_error(self, sync_service, ssh_changes):
        """Test: SSH Keys sync HTTP error"""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Claude Code Sync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestClaudeCodeSynchronization:
    """Claude Code SettingsSyncTest"""

    async def test_sync_claude_code_success(self, sync_service, claude_code_changes):
        """Test: successfully sync Claude Code settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Claude Code updated",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_claude_code(
                "http://localhost:8080", claude_code_changes, "workspace-123"
            )

        # Assert
        assert result["type"] == "claude_code"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()
        assert (
            mock_client.post.call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/claude-code"
        )
        call_kwargs = mock_client.post.call_args[1]
        assert (
            call_kwargs["json"]["oauthAccount"]["emailAddress"] == "claude@example.com"
        )
        assert call_kwargs["json"]["model"] == "claude-fable-5"

    async def test_sync_claude_code_with_api_key(self, sync_service):
        """Test: sync Claude Code using API Key"""
        # Arrange
        changes = {
            "authMethod": "apiKey",
            "authKey": "sk-ant-api-key-123",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_claude_code(
                "http://localhost:8080", changes, "workspace-123"
            )

        # Assert
        assert result["success"] is True
        # Verify request contains correct payload
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["authMethod"] == "apiKey"
        assert call_kwargs["json"]["apiKey"] == "sk-ant-api-key-123"

    async def test_sync_claude_code_timeout(self, sync_service, claude_code_changes):
        """Test: Claude Code Sync Timeout"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="Claude Code sync failed"):
                await sync_service._sync_claude_code(
                    "http://localhost:8080", claude_code_changes, "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Codex Sync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCodexSynchronization:
    """Codex Settings synchronization tests"""

    async def test_sync_codex_success(self, sync_service, codex_changes):
        """Test: successfully sync Codex settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "Codex updated"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_codex(
                "http://localhost:8080", codex_changes, "workspace-123"
            )

        # Assert
        assert result["type"] == "codex"
        assert result["success"] is True
        assert (
            mock_client.post.call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/codex"
        )
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["loginStatus"] == "connected"
        assert call_kwargs["json"]["authMethod"] == "subscription"
        assert call_kwargs["json"]["model"] == "gpt-5.6-sol"
        assert (
            call_kwargs["json"]["environmentVariables"][0]["key"] == "OPENAI_BASE_URL"
        )
        assert (
            call_kwargs["json"]["cliState"]["authJson"]["tokens"]["refresh_token"]
            == "refresh-token"
        )
        assert (
            call_kwargs["json"]["cliState"]["configToml"]
            == '[projects."/workspace"]\ntrust_level = "trusted"\n'
        )
        assert call_kwargs["json"]["cliState"]["installationId"] == "installation-1"
        assert call_kwargs["json"]["clearAuth"] is False
        assert "authTokens" not in call_kwargs["json"]

    async def test_sync_codex_clear_auth_when_not_connected(self, sync_service):
        """Test: Codex logout state clears runtime auth"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_codex(
                "http://localhost:8080",
                {"loginStatus": "notConnected", "environmentVariables": []},
                "workspace-123",
            )

        # Assert
        assert result["success"] is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["clearAuth"] is True
        assert call_kwargs["json"]["cliState"] is None

    async def test_sync_codex_timeout(self, sync_service, codex_changes):
        """Test: Codex sync timeout"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="Codex sync failed"):
                await sync_service._sync_codex(
                    "http://localhost:8080", codex_changes, "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Git SettingsSync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestCapabilitiesSynchronization:
    """Workspace capabilities synchronization tests"""

    async def test_normalize_capabilities_converts_manager_aliases_to_runtime_schema(
        self, sync_service, capabilities_changes
    ):
        payload = sync_service._normalize_capabilities(capabilities_changes)

        assert payload == {
            "default_tool": "claude",
            "tools": [
                {
                    "id": "claude",
                    "models": ["claude-opus-4-8"],
                    "default_model": "claude-opus-4-8",
                    "modes": ["execute", "plan"],
                    "default_mode": "execute",
                    "context_window": 200000,
                }
            ],
        }

    async def test_normalize_capabilities_accepts_detected_settings_payload(
        self, sync_service
    ):
        settings_service = SettingsService(MagicMock())
        changes = settings_service.detect_setting_changes(
            UserSettings(
                codex=CodexSettings(
                    model_selection=normalize_model_selection(
                        "codex", None, mode="read"
                    )
                )
            ),
            {
                "codex": {
                    "modelSelection": {
                        "customModels": ["gpt-custom"],
                        "allowedModels": ["gpt-custom"],
                        "defaultModel": "gpt-custom",
                    }
                }
            },
        )

        runtime_payload = sync_service._normalize_capabilities(changes["capabilities"])

        assert runtime_payload["default_tool"] == "claude"
        assert runtime_payload["tools"][1]["default_model"] == "gpt-custom"
        assert runtime_payload["tools"][1]["context_window"] == 200000
        assert "defaultTool" not in runtime_payload
        assert "defaultModel" not in runtime_payload["tools"][1]
        assert "contextWindow" not in runtime_payload["tools"][1]

    async def test_sync_capabilities_success(self, sync_service, capabilities_changes):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await sync_service._sync_capabilities(
                "http://localhost:8080",
                capabilities_changes,
                "workspace-123",
            )

        assert result["type"] == "capabilities"
        assert result["success"] is True
        mock_client.post.assert_awaited_once()
        call_args = mock_client.post.call_args
        assert (
            call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/capabilities"
        )
        assert call_args.kwargs["json"] == {
            "workspace_id": "workspace-123",
            "capabilities": capabilities_changes,
        }

    async def test_sync_capabilities_to_ready_generation_uses_explicit_identity(
        self,
        sync_service,
        capabilities_changes,
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response

        with (
            patch("httpx.Client", return_value=mock_client),
            patch(
                "app.modules.workspace.runtime.sync.runtime_command_headers",
                return_value={
                    "Authorization": "Bearer generation-assertion",
                    "Content-Type": "application/json",
                },
            ) as mock_headers,
        ):
            result = sync_service.sync_capabilities_to_runtime_generation(
                "workspace-123",
                "http://runtime-new:3002",
                "runtime-instance-new",
                capabilities_changes,
            )

        assert result["success"] is True
        mock_headers.assert_called_once_with(
            workspace_id="workspace-123",
            runtime_instance_id="runtime-instance-new",
            action="settings.sync",
        )
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert (
            call_args.args[0]
            == "http://runtime-new:3002/api/v1/internal/settings/capabilities"
        )
        assert call_args.kwargs["json"]["workspace_id"] == "workspace-123"
        assert call_args.kwargs["json"]["capabilities"]["default_tool"] == "claude"

    async def test_resolve_capabilities_uses_owner_settings_when_snapshot_missing(
        self,
        sync_service,
        mock_db_session,
    ):
        workspace = MagicMock(
            agentic_capabilities=None,
            owner_id="user-123",
        )
        mock_db_session.get.return_value = workspace
        owner_settings = UserSettings(
            codex=CodexSettings(
                model_selection=normalize_model_selection(
                    "codex",
                    {
                        "customModels": ["gpt-owner"],
                        "allowedModels": ["gpt-owner"],
                        "defaultModel": "gpt-owner",
                    },
                    mode="read",
                )
            )
        )

        with patch(
            "app.modules.settings.user_settings.SettingsService.get_settings",
            return_value=owner_settings,
        ):
            capabilities = sync_service.resolve_workspace_capabilities("workspace-123")

        codex = next(tool for tool in capabilities.tools if tool.id == "codex")
        assert codex.models == ["gpt-owner"]
        assert codex.default_model == "gpt-owner"

    async def test_store_workspace_capabilities_closes_missing_workspace_transaction(
        self,
        sync_service,
        mock_db_session,
        capabilities_changes,
    ):
        mock_db_session.get.return_value = None

        with patch(
            "app.modules.workspace.runtime.sync.acquire_workspace_transaction_lock"
        ) as acquire_lock:
            sync_service._store_workspace_capabilities(
                "workspace-missing",
                capabilities_changes,
            )

        acquire_lock.assert_not_called()
        mock_db_session.rollback.assert_called_once()
        mock_db_session.commit.assert_not_called()

    async def test_store_workspace_capabilities_rolls_back_commit_failure(
        self,
        sync_service,
        mock_db_session,
        capabilities_changes,
    ):
        workspace = MagicMock()
        mock_db_session.get.return_value = workspace
        mock_db_session.scalar.return_value = workspace
        mock_db_session.commit.side_effect = RuntimeError("commit failed")

        with (
            patch(
                "app.modules.workspace.runtime.sync.acquire_workspace_transaction_lock"
            ) as acquire_lock,
            pytest.raises(RuntimeError, match="commit failed"),
        ):
            sync_service._store_workspace_capabilities(
                "workspace-123",
                capabilities_changes,
            )

        acquire_lock.assert_called_once_with(mock_db_session, "workspace-123")
        mock_db_session.rollback.assert_called_once()

    async def test_sync_settings_to_runtimes_includes_capabilities(
        self, sync_service, mock_db_session, sample_runtimes, capabilities_changes
    ):
        sync_service._get_user_workspace_runtimes = AsyncMock(
            return_value=sample_runtimes
        )
        sync_service._sync_capabilities = AsyncMock(
            return_value={"type": "capabilities", "success": True}
        )
        workspace_123 = MagicMock()
        workspace_456 = MagicMock()
        mock_db_session.get.side_effect = [workspace_123, workspace_456]
        mock_db_session.scalar.side_effect = [workspace_123, workspace_456]

        with patch(
            "app.modules.workspace.runtime.sync.acquire_workspace_transaction_lock"
        ) as acquire_lock:
            result = await sync_service.sync_settings_to_runtimes(
                "user-123",
                {"capabilities": capabilities_changes},
            )

        assert result["success"] is True
        assert result["total_tasks"] == 2
        assert sync_service._sync_capabilities.await_args_list[0].args == (
            "http://localhost:8080",
            {
                "default_tool": "claude",
                "tools": [
                    {
                        "id": "claude",
                        "models": ["claude-opus-4-8"],
                        "default_model": "claude-opus-4-8",
                        "modes": ["execute", "plan"],
                        "default_mode": "execute",
                        "context_window": 200000,
                    }
                ],
            },
            "workspace-123",
        )
        assert workspace_123.agentic_capabilities == capabilities_changes
        assert workspace_456.agentic_capabilities == capabilities_changes
        assert mock_db_session.commit.call_count == 2
        assert acquire_lock.call_args_list == [
            call(mock_db_session, "workspace-123"),
            call(mock_db_session, "workspace-456"),
        ]

    async def test_sync_running_runtime_capabilities_uses_workspace_snapshots(
        self, sync_service, capabilities_changes
    ):
        sync_service._get_running_runtimes = AsyncMock(
            return_value=[
                {"workspace_id": "workspace-123", "url": "http://runtime-123:3002"},
                {"workspace_id": "workspace-456", "url": "http://runtime-456:3002"},
            ]
        )
        sync_service.resolve_workspace_capabilities = MagicMock(
            side_effect=[capabilities_changes, capabilities_changes]
        )
        sync_service._sync_capabilities = AsyncMock(
            side_effect=[
                {"type": "capabilities", "success": True},
                Exception("runtime unavailable"),
            ]
        )

        result = await sync_service.sync_running_runtime_capabilities()

        assert result == {"synced": 1, "failed": 1}
        assert sync_service._sync_capabilities.await_args_list[0].args == (
            "http://runtime-123:3002",
            {
                "default_tool": "claude",
                "tools": [
                    {
                        "id": "claude",
                        "models": ["claude-opus-4-8"],
                        "default_model": "claude-opus-4-8",
                        "modes": ["execute", "plan"],
                        "default_mode": "execute",
                        "context_window": 200000,
                    }
                ],
            },
            "workspace-123",
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestGitSettingsSynchronization:
    """Git Settings Synchronization Tests"""

    async def test_sync_git_settings_success(self, sync_service, git_changes):
        """Test: Successfully Sync Git Settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Git settings updated",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_git_settings(
                "http://localhost:8080", git_changes, "workspace-123"
            )

        # Assert
        assert result["type"] == "git_settings"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()
        assert (
            mock_client.post.call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/git"
        )

    async def test_sync_git_settings_partial_data(self, sync_service):
        """Test: Partial Git Settings Sync"""
        # Arrange
        changes = {
            "userName": "Test User",
            # userEmail missing
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_git_settings(
                "http://localhost:8080", changes, "workspace-123"
            )

        # Assert
        assert result["success"] is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["userName"] == "Test User"
        assert call_kwargs["json"]["userEmail"] is None


# ============================================================================
# RuntimeSyncService Tests - Firewall Settings Sync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestFirewallSynchronization:
    """Firewall Settings Synchronization Tests"""

    async def test_sync_firewall_success(self, sync_service, firewall_changes):
        """Test: Successfully Sync Firewall Settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Firewall updated",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_firewall(
                "http://localhost:8080", firewall_changes, "workspace-123"
            )

        # Assert
        assert result["type"] == "firewall"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        assert result["enforced_scopes"] == ["workspace"]
        assert result["unenforced_scopes"] == []
        mock_client.post.assert_called_once()
        assert (
            mock_client.post.call_args.args[0]
            == "http://localhost:8080/api/v1/internal/settings/firewall"
        )

    async def test_sync_firewall_reports_browser_scope_as_unenforced_for_docker_runtime(
        self, sync_service
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "message": "Firewall updated",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        firewall_changes = {
            "workspace": {
                "egressMode": "allowlist",
                "allowedDomains": ["example.com"],
            },
            "browser": {
                "egressMode": "blocked",
                "allowedDomains": [],
            },
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await sync_service._sync_firewall(
                "http://localhost:8080",
                firewall_changes,
                "workspace-123",
            )

        assert result["success"] is True
        assert result["enforced_scopes"] == ["workspace"]
        assert result["unenforced_scopes"] == ["browser"]
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"] == {
            "egressMode": "allowlist",
            "allowedDomains": ["example.com"],
        }

    async def test_sync_firewall_to_runtime_not_running(
        self, sync_service, firewall_changes
    ):
        """Test: Sync Firewall When Runtime Not Running"""
        # Arrange
        with patch.object(sync_service, "_get_running_runtimes", return_value=[]):
            # Act
            result = await sync_service.sync_firewall_to_runtime(
                "workspace-123", firewall_changes
            )

        # Assert
        assert result["success"] is False
        assert result["message"] == "Runtime not running"

    async def test_sync_firewall_to_runtime_success(
        self, sync_service, firewall_changes, sample_runtimes
    ):
        """Test: Successfully Sync Firewall to Runtime"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch.object(
            sync_service, "_get_running_runtimes", return_value=sample_runtimes
        ):
            with patch("httpx.AsyncClient", return_value=mock_client):
                # Act
                result = await sync_service.sync_firewall_to_runtime(
                    "workspace-123", firewall_changes
                )

        # Assert
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"

    async def test_sync_firewall_with_blocked_egress(self, sync_service):
        """Test: Firewall sync with blocked egress."""
        # Arrange
        changes = {
            "egressMode": "blocked",
            "allowedDomains": [],
        }

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_firewall(
                "http://localhost:8080", changes, "workspace-123"
            )

        # Assert
        assert result["success"] is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["egressMode"] == "blocked"


# ============================================================================
# RuntimeSyncService Tests - SettingsBatchSync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestBatchSettingsSynchronization:
    """Batch Settings Synchronization Tests"""

    async def test_sync_settings_to_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test: Successfully Sync Settings to Multiple Runtimes"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 1
        assert result["success_count"] == 1
        assert result["error_count"] == 0

    async def test_sync_settings_to_runtimes_no_runtimes(
        self, sync_service, mock_db_session
    ):
        """Test: Sync When No Runtime"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_execute_result

        changes = {"ssh": {"privateKey": "key", "publicKey": "pub"}}

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 0
        assert len(result["results"]) == 0

    async def test_sync_settings_to_runtimes_multiple_settings(
        self,
        sync_service,
        mock_db_session,
        sample_workspace,
        ssh_changes,
        claude_code_changes,
        codex_changes,
        git_changes,
    ):
        """Test: Sync Multiple Types of Settings"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        changes = {
            "ssh": ssh_changes,
            "claudeCode": claude_code_changes,
            "codex": codex_changes,
            "git": git_changes,
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 4
        assert result["success_count"] == 4
        assert result["error_count"] == 0

    async def test_sync_settings_to_runtimes_partial_failure(
        self,
        sync_service,
        mock_db_session,
        sample_workspace,
        ssh_changes,
        claude_code_changes,
    ):
        """Test: Partial Sync Failure"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response_success = MagicMock()
        mock_response_success.json.return_value = {"success": True}
        mock_response_success.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        # SSH Success, Claude Code Failed
        mock_client.post.side_effect = [
            mock_response_success,  # SSH Success
            httpx.HTTPStatusError(
                "Error", request=MagicMock(), response=MagicMock(status_code=500)
            ),  # Claude Code Failed
        ]

        changes = {
            "ssh": ssh_changes,
            "claudeCode": claude_code_changes,
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is False  # Because there are failures
        assert result["total_tasks"] == 2
        assert result["success_count"] == 1
        assert result["error_count"] == 1

    async def test_sync_settings_to_runtimes_no_changes(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test: Sync When No Changes"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        changes = {}  # Empty changes

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 0  # No tasks
        assert len(result["results"]) == 0


# ============================================================================
# RuntimeSyncService Tests - Conflict Handling
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestConflictResolution:
    """Conflict Resolution Tests"""

    async def test_sync_with_concurrent_modifications(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test: Sync During Concurrent Modifications"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "conflict": True,
            "resolved": "local_wins",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        # Should successfully handle conflicts

    async def test_sync_with_version_mismatch(self, sync_service, ssh_changes):
        """Test: Sync When Version Mismatch"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error": "version_mismatch",
            "message": "Configuration version conflict",
        }
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Conflict", request=MagicMock(), response=MagicMock(status_code=409)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Incremental Sync
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestIncrementalSync:
    """Incremental Sync Tests"""

    async def test_sync_only_changed_settings(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test: Only Sync Changed Settings"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "updated": ["ssh"]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        # Only SSH changed
        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 1  # Only 1 task
        # Should only call SSH Sync API
        assert mock_client.post.call_count == 1

    async def test_sync_efficiency_with_multiple_workspaces(
        self, sync_service, mock_db_session, ssh_changes
    ):
        """Test: Sync Efficiency with Multiple Workspaces"""
        # Arrange
        from app.db import models as db_models

        # Create 3 workspaces
        workspaces = []
        for i in range(3):
            ws = Mock(spec=db_models.Workspace)
            ws.id = f"workspace-{i}"
            ws.name = f"Workspace {i}"
            ws.runtime_status = "running"
            ws.runtime_internal_url = f"http://workspace-runtime-{i}:3002"
            workspaces.append(ws)

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = workspaces
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 3
        assert result["total_tasks"] == 3  # Each workspace has one task
        # Verify concurrent calls
        assert mock_client.post.call_count == 3


# ============================================================================
# RuntimeSyncService Tests - Error Handling and Edge Cases
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
class TestErrorHandlingAndEdgeCases:
    """Error Handling and Edge Cases Tests"""

    async def test_sync_with_invalid_url(self, sync_service, ssh_changes):
        """Test: Invalid URL"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.InvalidURL("Invalid URL")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "invalid-url", ssh_changes, "workspace-123"
                )

    async def test_sync_with_timeout_retry(self, sync_service, ssh_changes):
        """Test: Timeout Retry"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )

    async def test_sync_with_empty_changes(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test: Empty Changes"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", {})

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 0

    async def test_sync_with_malformed_response(self, sync_service, ssh_changes):
        """Test: Malformed Response"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )

    async def test_sync_with_authentication_failure(self, sync_service, ssh_changes):
        """Test: authentication failure during sync"""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=MagicMock(status_code=401)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080", ssh_changes, "workspace-123"
                )

    async def test_sync_with_custom_timeout(self, sync_service, ssh_changes):
        """Test: Custom Timeout"""
        # Arrange
        sync_service.timeout = 5.0

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient") as mock_async_client:
            mock_async_client.return_value = mock_client

            # Act
            await sync_service._sync_ssh_keys(
                "http://localhost:8080", ssh_changes, "workspace-123"
            )

            # Assert
            # Verify AsyncClient uses correct timeout value
            mock_async_client.assert_called_with(timeout=5.0)

    async def test_sync_all_settings_types(
        self,
        sync_service,
        mock_db_session,
        sample_workspace,
        ssh_changes,
        claude_code_changes,
        git_changes,
    ):
        """Test: Sync All Types of Settings"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        changes = {
            "ssh": ssh_changes,
            "claudeCode": claude_code_changes,
            "git": git_changes,
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 3
        assert result["success_count"] == 3
        # Verify all three types of API were called
        assert mock_client.post.call_count == 3
