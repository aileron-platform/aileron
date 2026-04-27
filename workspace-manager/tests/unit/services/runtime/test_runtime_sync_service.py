"""RuntimeSyncService UnitTest"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch, AsyncMock
from typing import Dict, List

import pytest
import httpx

from app.services.runtime_sync_service import RuntimeSyncService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def sample_workspace():
    """範例Workspace"""
    from app.db import models as db_models

    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-123"
    workspace.name = "Test Workspace"
    workspace.owner_id = "user-123"
    workspace.runtime_status = "running"
    workspace.runtime_external_url = "http://localhost:8080"
    workspace.runtime_internal_url = "http://workspace-runtime-workspace-123:3002"
    return workspace


@pytest.fixture
def sample_runtimes():
    """範例Run時List"""
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
    """SSH SettingsChange"""
    return {
        "privateKey": "-----BEGIN RSA PRIVATE KEY-----\ntest-private-key\n-----END RSA PRIVATE KEY-----",
        "publicKey": "ssh-rsa test-public-key user@example.com",
    }


@pytest.fixture
def claude_code_changes():
    """Claude Code SettingsChange"""
    return {
        "authMethod": "subscription",
        "subscriptionAccessToken": "access-token-123",
        "subscriptionRefreshToken": "refresh-token-456",
        "subscriptionExpiresAt": "2025-12-31T23:59:59Z",
        "authKey": "api-key-789",
        "environmentVariables": [
            {"key": "VAR1", "value": "value1"},
            {"key": "VAR2", "value": "value2"},
        ],
    }


@pytest.fixture
def git_changes():
    """Git SettingsChange"""
    return {
        "userName": "Test User",
        "userEmail": "test@example.com",
    }


@pytest.fixture
def mock_async_client():
    """CreateSupportingAsyncAboveBelow文Management器的 mock httpx client"""
    def _create_mock_client():
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        return mock_client
    return _create_mock_client


@pytest.fixture
def firewall_changes():
    """防火牆SettingsChange"""
    return {
        "networkAccessEnabled": True,
        "domainAccessMode": "allowlist",
        "allowedDomains": ["github.com", "google.com", "anthropic.com"],
    }


@pytest.fixture
def sync_service(mock_db_session):
    """RuntimeSyncService Instance"""
    return RuntimeSyncService(mock_db_session)


# ============================================================================
# RuntimeSyncService Tests - BasicOperation
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestRuntimeSyncServiceBasic:
    """RuntimeSyncService BasicOperationTest"""

    async def test_get_user_workspace_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test：SuccessGetUserWorkspaceRun時"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert len(result) == 1
        assert result[0]["workspace_id"] == "workspace-123"
        assert result[0]["url"] == "http://localhost:8080"

    async def test_get_user_workspace_runtimes_no_running(
        self, sync_service, mock_db_session
    ):
        """Test：NoneRun中的Workspace"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert len(result) == 0

    async def test_get_user_workspace_runtimes_without_external_url(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test：過濾NoneOutside部 URL 的Workspace"""
        # Arrange
        sample_workspace.runtime_external_url = None
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service._get_user_workspace_runtimes("user-123")

        # Assert
        assert len(result) == 0


# ============================================================================
# RuntimeSyncService Tests - SSH Keys Sync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestSSHKeysSynchronization:
    """SSH Keys SyncTest"""

    async def test_sync_ssh_keys_success(
        self, sync_service, ssh_changes
    ):
        """Test：SuccessSync SSH Keys"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "SSH keys updated"}
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
                "http://localhost:8080",
                ssh_changes,
                "workspace-123"
            )

        # Assert
        assert result["type"] == "ssh_keys"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()

    async def test_sync_ssh_keys_network_error(
        self, sync_service, ssh_changes
    ):
        """Test：SSH Keys SyncNetworkError"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )

    async def test_sync_ssh_keys_http_error(
        self, sync_service, ssh_changes
    ):
        """Test：SSH Keys Sync HTTP Error"""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Claude Code Sync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestClaudeCodeSynchronization:
    """Claude Code SettingsSyncTest"""

    async def test_sync_claude_code_success(
        self, sync_service, claude_code_changes
    ):
        """Test：SuccessSync Claude Code Settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "Claude Code updated"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_claude_code(
                "http://localhost:8080",
                claude_code_changes,
                "workspace-123"
            )

        # Assert
        assert result["type"] == "claude_code"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()

    async def test_sync_claude_code_with_api_key(
        self, sync_service
    ):
        """Test：Use API Key Sync Claude Code"""
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
                "http://localhost:8080",
                changes,
                "workspace-123"
            )

        # Assert
        assert result["success"] is True
        # VerifyRequest包含Correctly的 payload
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["authMethod"] == "apiKey"
        assert call_kwargs["json"]["apiKey"] == "sk-ant-api-key-123"

    async def test_sync_claude_code_timeout(
        self, sync_service, claude_code_changes
    ):
        """Test：Claude Code Sync超時"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Request timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="Claude Code sync failed"):
                await sync_service._sync_claude_code(
                    "http://localhost:8080",
                    claude_code_changes,
                    "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - Git SettingsSync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestGitSettingsSynchronization:
    """Git SettingsSyncTest"""

    async def test_sync_git_settings_success(
        self, sync_service, git_changes
    ):
        """Test：SuccessSync Git Settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "Git settings updated"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_git_settings(
                "http://localhost:8080",
                git_changes,
                "workspace-123"
            )

        # Assert
        assert result["type"] == "git_settings"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        mock_client.post.assert_called_once()

    async def test_sync_git_settings_partial_data(
        self, sync_service
    ):
        """Test：Part Git SettingsSync"""
        # Arrange
        changes = {
            "userName": "Test User",
            # userEmail 缺失
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
                "http://localhost:8080",
                changes,
                "workspace-123"
            )

        # Assert
        assert result["success"] is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["userName"] == "Test User"
        assert call_kwargs["json"]["userEmail"] is None


# ============================================================================
# RuntimeSyncService Tests - 防火牆SettingsSync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestFirewallSynchronization:
    """防火牆SettingsSyncTest"""

    async def test_sync_firewall_success(
        self, sync_service, firewall_changes
    ):
        """Test：SuccessSync防火牆Settings"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "Firewall updated"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service._sync_firewall(
                "http://localhost:8080",
                firewall_changes,
                "workspace-123"
            )

        # Assert
        assert result["type"] == "firewall"
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"
        assert result["enforced_scopes"] == ["workspace"]
        assert result["unenforced_scopes"] == []
        mock_client.post.assert_called_once()

    async def test_sync_firewall_reports_browser_scope_as_unenforced_for_docker_runtime(
        self, sync_service
    ):
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True, "message": "Firewall updated"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        firewall_changes = {
            "workspace": {
                "networkAccessEnabled": True,
                "domainAccessMode": "specific",
                "allowedDomains": ["example.com"],
            },
            "browser": {
                "networkAccessEnabled": False,
                "domainAccessMode": "all",
                "allowedDomains": ["browser.example.com"],
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
            "networkAccessEnabled": True,
            "domainAccessMode": "specific",
            "allowedDomains": ["example.com"],
        }

    async def test_sync_firewall_to_runtime_not_running(
        self, sync_service, firewall_changes
    ):
        """Test：Runtime 未Run時Sync防火牆"""
        # Arrange
        with patch.object(sync_service, '_get_running_runtimes', return_value=[]):
            # Act
            result = await sync_service.sync_firewall_to_runtime(
                "workspace-123",
                firewall_changes
            )

        # Assert
        assert result["success"] is False
        assert result["message"] == "Runtime not running"

    async def test_sync_firewall_to_runtime_success(
        self, sync_service, firewall_changes, sample_runtimes
    ):
        """Test：SuccessSync防火牆To Runtime"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch.object(sync_service, '_get_running_runtimes', return_value=sample_runtimes):
            with patch("httpx.AsyncClient", return_value=mock_client):
                # Act
                result = await sync_service.sync_firewall_to_runtime(
                    "workspace-123",
                    firewall_changes
                )

        # Assert
        assert result["success"] is True
        assert result["workspace_id"] == "workspace-123"

    async def test_sync_firewall_with_disabled_network_access(
        self, sync_service
    ):
        """Test：禁用NetworkAccess的防火牆Sync"""
        # Arrange
        changes = {
            "networkAccessEnabled": False,
            "domainAccessMode": "all",
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
                "http://localhost:8080",
                changes,
                "workspace-123"
            )

        # Assert
        assert result["success"] is True
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["networkAccessEnabled"] is False


# ============================================================================
# RuntimeSyncService Tests - SettingsBatchSync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestBatchSettingsSynchronization:
    """SettingsBatchSyncTest"""

    async def test_sync_settings_to_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test：SuccessSyncSettingsToMany個 Runtime"""
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
        """Test：None Runtime 時Sync"""
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
        self, sync_service, mock_db_session, sample_workspace,
        ssh_changes, claude_code_changes, git_changes
    ):
        """Test：SyncMany種Settings"""
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
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 3  # 3 種Settings
        assert result["success_count"] == 3
        assert result["error_count"] == 0

    async def test_sync_settings_to_runtimes_partial_failure(
        self, sync_service, mock_db_session, sample_workspace,
        ssh_changes, claude_code_changes
    ):
        """Test：PartSyncFailed"""
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
        # SSH Success，Claude Code Failed
        mock_client.post.side_effect = [
            mock_response_success,  # SSH Success
            httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock(status_code=500)),  # Claude Code Failed
        ]

        changes = {
            "ssh": ssh_changes,
            "claudeCode": claude_code_changes,
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is False  # Because of有Failed
        assert result["total_tasks"] == 2
        assert result["success_count"] == 1
        assert result["error_count"] == 1

    async def test_sync_settings_to_runtimes_no_changes(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test：NoneChange時Sync"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        changes = {}  # 空Change

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 0  # NoneTask
        assert len(result["results"]) == 0


# ============================================================================
# RuntimeSyncService Tests - 衝突Handle
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestConflictResolution:
    """衝突解決Test"""

    async def test_sync_with_concurrent_modifications(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test：並發Modify時的Sync"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "conflict": True,
            "resolved": "local_wins"
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
        # ShouldSuccessHandle衝突

    async def test_sync_with_version_mismatch(
        self, sync_service, ssh_changes
    ):
        """Test：版本不匹配時的Sync"""
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": False,
            "error": "version_mismatch",
            "message": "Configuration version conflict"
        }
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Conflict",
            request=MagicMock(),
            response=MagicMock(status_code=409)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )


# ============================================================================
# RuntimeSyncService Tests - 增量Sync
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestIncrementalSync:
    """增量SyncTest"""

    async def test_sync_only_changed_settings(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """Test：只SyncChange的Settings"""
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

        # Only SSH Change
        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 1  # Only 1 個Task
        # Should只調用 SSH Sync API
        assert mock_client.post.call_count == 1

    async def test_sync_efficiency_with_multiple_workspaces(
        self, sync_service, mock_db_session, ssh_changes
    ):
        """Test：Many個Workspace的SyncEfficiency"""
        # Arrange
        from app.db import models as db_models

        # Create 3 個Workspace
        workspaces = []
        for i in range(3):
            ws = Mock(spec=db_models.Workspace)
            ws.id = f"workspace-{i}"
            ws.name = f"Workspace {i}"
            ws.runtime_status = "running"
            ws.runtime_external_url = f"http://localhost:808{i}"
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
        assert result["total_tasks"] == 3  # EachWorkspace一個Task
        # Verify並發調用
        assert mock_client.post.call_count == 3


# ============================================================================
# RuntimeSyncService Tests - ErrorHandle和BoundaryCircumstance
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestErrorHandlingAndEdgeCases:
    """ErrorHandle和BoundaryCircumstanceTest"""

    async def test_sync_with_invalid_url(
        self, sync_service, ssh_changes
    ):
        """Test：Invalid URL"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.InvalidURL("Invalid URL")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "invalid-url",
                    ssh_changes,
                    "workspace-123"
                )

    async def test_sync_with_timeout_retry(
        self, sync_service, ssh_changes
    ):
        """Test：超時Heavy試"""
        # Arrange
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )

    async def test_sync_with_empty_changes(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """Test：空Change"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", {})

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 0

    async def test_sync_with_malformed_response(
        self, sync_service, ssh_changes
    ):
        """Test：FormatError的Response"""
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
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )

    async def test_sync_with_authentication_failure(
        self, sync_service, ssh_changes
    ):
        """Test：AuthenticationFailed"""
        # Arrange
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401)
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post.return_value = mock_response

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act & Assert
            with pytest.raises(Exception, match="SSH sync failed"):
                await sync_service._sync_ssh_keys(
                    "http://localhost:8080",
                    ssh_changes,
                    "workspace-123"
                )

    async def test_sync_service_initialization(self, mock_db_session):
        """Test：ServiceInitialize"""
        # Act
        service = RuntimeSyncService(mock_db_session)

        # Assert
        assert service.db == mock_db_session
        assert service.internal_api_token == "dev-internal-token"
        assert service.timeout == 30.0

    async def test_sync_with_custom_timeout(
        self, sync_service, ssh_changes
    ):
        """Test：自定義超時"""
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
                "http://localhost:8080",
                ssh_changes,
                "workspace-123"
            )

            # Assert
            # Verify AsyncClient Use了Correctly的超時Value
            mock_async_client.assert_called_with(timeout=5.0)

    async def test_sync_all_settings_types(
        self, sync_service, mock_db_session, sample_workspace,
        ssh_changes, claude_code_changes, git_changes
    ):
        """Test：SyncAllType的Settings"""
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
        # Verify三Type型的 API 都被調用
        assert mock_client.post.call_count == 3
