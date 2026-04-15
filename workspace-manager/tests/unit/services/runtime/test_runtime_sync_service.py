"""RuntimeSyncService 單元測試"""

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
    """Mock 資料庫 Session"""
    session = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def sample_workspace():
    """範例工作區"""
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
    """範例運行時列表"""
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
    """SSH 設定變更"""
    return {
        "privateKey": "-----BEGIN RSA PRIVATE KEY-----\ntest-private-key\n-----END RSA PRIVATE KEY-----",
        "publicKey": "ssh-rsa test-public-key user@example.com",
    }


@pytest.fixture
def claude_code_changes():
    """Claude Code 設定變更"""
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
    """Git 設定變更"""
    return {
        "userName": "Test User",
        "userEmail": "test@example.com",
    }


@pytest.fixture
def mock_async_client():
    """創建支持異步上下文管理器的 mock httpx client"""
    def _create_mock_client():
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        return mock_client
    return _create_mock_client


@pytest.fixture
def firewall_changes():
    """防火牆設定變更"""
    return {
        "networkAccessEnabled": True,
        "domainAccessMode": "allowlist",
        "allowedDomains": ["github.com", "google.com", "anthropic.com"],
    }


@pytest.fixture
def sync_service(mock_db_session):
    """RuntimeSyncService 實例"""
    return RuntimeSyncService(mock_db_session)


# ============================================================================
# RuntimeSyncService Tests - 基本操作
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestRuntimeSyncServiceBasic:
    """RuntimeSyncService 基本操作測試"""

    async def test_get_user_workspace_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """測試：成功獲取用戶工作區運行時"""
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
        """測試：沒有運行中的工作區"""
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
        """測試：過濾沒有外部 URL 的工作區"""
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
# RuntimeSyncService Tests - SSH Keys 同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestSSHKeysSynchronization:
    """SSH Keys 同步測試"""

    async def test_sync_ssh_keys_success(
        self, sync_service, ssh_changes
    ):
        """測試：成功同步 SSH Keys"""
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
        """測試：SSH Keys 同步網絡錯誤"""
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
        """測試：SSH Keys 同步 HTTP 錯誤"""
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
# RuntimeSyncService Tests - Claude Code 同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestClaudeCodeSynchronization:
    """Claude Code 設定同步測試"""

    async def test_sync_claude_code_success(
        self, sync_service, claude_code_changes
    ):
        """測試：成功同步 Claude Code 設定"""
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
        """測試：使用 API Key 同步 Claude Code"""
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
        # 驗證請求包含正確的 payload
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["authMethod"] == "apiKey"
        assert call_kwargs["json"]["apiKey"] == "sk-ant-api-key-123"

    async def test_sync_claude_code_timeout(
        self, sync_service, claude_code_changes
    ):
        """測試：Claude Code 同步超時"""
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
# RuntimeSyncService Tests - Git 設定同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestGitSettingsSynchronization:
    """Git 設定同步測試"""

    async def test_sync_git_settings_success(
        self, sync_service, git_changes
    ):
        """測試：成功同步 Git 設定"""
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
        """測試：部分 Git 設定同步"""
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
# RuntimeSyncService Tests - 防火牆設定同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestFirewallSynchronization:
    """防火牆設定同步測試"""

    async def test_sync_firewall_success(
        self, sync_service, firewall_changes
    ):
        """測試：成功同步防火牆設定"""
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
        """測試：Runtime 未運行時同步防火牆"""
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
        """測試：成功同步防火牆到 Runtime"""
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
        """測試：禁用網絡訪問的防火牆同步"""
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
# RuntimeSyncService Tests - 設定批量同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestBatchSettingsSynchronization:
    """設定批量同步測試"""

    async def test_sync_settings_to_runtimes_success(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """測試：成功同步設定到多個 Runtime"""
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
        """測試：沒有 Runtime 時同步"""
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
        """測試：同步多種設定"""
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
        assert result["total_tasks"] == 3  # 3 種設定
        assert result["success_count"] == 3
        assert result["error_count"] == 0

    async def test_sync_settings_to_runtimes_partial_failure(
        self, sync_service, mock_db_session, sample_workspace,
        ssh_changes, claude_code_changes
    ):
        """測試：部分同步失敗"""
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
        # SSH 成功，Claude Code 失敗
        mock_client.post.side_effect = [
            mock_response_success,  # SSH 成功
            httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock(status_code=500)),  # Claude Code 失敗
        ]

        changes = {
            "ssh": ssh_changes,
            "claudeCode": claude_code_changes,
        }

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is False  # 因為有失敗
        assert result["total_tasks"] == 2
        assert result["success_count"] == 1
        assert result["error_count"] == 1

    async def test_sync_settings_to_runtimes_no_changes(
        self, sync_service, mock_db_session, sample_workspace
    ):
        """測試：沒有變更時同步"""
        # Arrange
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [sample_workspace]
        mock_db_session.execute.return_value = mock_execute_result

        changes = {}  # 空變更

        # Act
        result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["synced_runtimes"] == 1
        assert result["total_tasks"] == 0  # 沒有任務
        assert len(result["results"]) == 0


# ============================================================================
# RuntimeSyncService Tests - 衝突處理
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestConflictResolution:
    """衝突解決測試"""

    async def test_sync_with_concurrent_modifications(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """測試：並發修改時的同步"""
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
        # 應該成功處理衝突

    async def test_sync_with_version_mismatch(
        self, sync_service, ssh_changes
    ):
        """測試：版本不匹配時的同步"""
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
# RuntimeSyncService Tests - 增量同步
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestIncrementalSync:
    """增量同步測試"""

    async def test_sync_only_changed_settings(
        self, sync_service, mock_db_session, sample_workspace, ssh_changes
    ):
        """測試：只同步變更的設定"""
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

        # 只有 SSH 變更
        changes = {"ssh": ssh_changes}

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Act
            result = await sync_service.sync_settings_to_runtimes("user-123", changes)

        # Assert
        assert result["success"] is True
        assert result["total_tasks"] == 1  # 只有 1 個任務
        # 應該只調用 SSH 同步 API
        assert mock_client.post.call_count == 1

    async def test_sync_efficiency_with_multiple_workspaces(
        self, sync_service, mock_db_session, ssh_changes
    ):
        """測試：多個工作區的同步效率"""
        # Arrange
        from app.db import models as db_models

        # 創建 3 個工作區
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
        assert result["total_tasks"] == 3  # 每個工作區一個任務
        # 驗證並發調用
        assert mock_client.post.call_count == 3


# ============================================================================
# RuntimeSyncService Tests - 錯誤處理和邊界情況
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
class TestErrorHandlingAndEdgeCases:
    """錯誤處理和邊界情況測試"""

    async def test_sync_with_invalid_url(
        self, sync_service, ssh_changes
    ):
        """測試：無效 URL"""
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
        """測試：超時重試"""
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
        """測試：空變更"""
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
        """測試：格式錯誤的響應"""
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
        """測試：認證失敗"""
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
        """測試：服務初始化"""
        # Act
        service = RuntimeSyncService(mock_db_session)

        # Assert
        assert service.db == mock_db_session
        assert service.internal_api_token == "dev-internal-token"
        assert service.timeout == 30.0

    async def test_sync_with_custom_timeout(
        self, sync_service, ssh_changes
    ):
        """測試：自定義超時"""
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
            # 驗證 AsyncClient 使用了正確的超時值
            mock_async_client.assert_called_with(timeout=5.0)

    async def test_sync_all_settings_types(
        self, sync_service, mock_db_session, sample_workspace,
        ssh_changes, claude_code_changes, git_changes
    ):
        """測試：同步所有類型的設定"""
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
        # 驗證三種類型的 API 都被調用
        assert mock_client.post.call_count == 3
