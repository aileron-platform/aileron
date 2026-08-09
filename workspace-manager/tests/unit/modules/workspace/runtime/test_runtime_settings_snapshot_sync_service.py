"""Sync service unit tests."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.modules.workspace.runtime.settings_snapshot_sync import (
    RuntimeSettingsSnapshotSyncService,
)


@pytest.fixture
def mock_workspace():
    """Create a mock workspace"""
    workspace = Mock()
    workspace.id = "workspace_123"
    workspace.name = "Test Workspace"
    workspace.runtime_internal_url = "http://runtime.local:8000"
    workspace.runtime_instance_id = "00000000-0000-4000-8000-000000000123"
    workspace.runtime_status = "running"
    workspace.owner_id = "user_123"
    return workspace


@pytest.fixture(autouse=True)
def mock_runtime_command_signing():
    """Keep settings sync tests focused on payload and failure isolation."""
    with patch(
        "app.modules.workspace.runtime.settings_snapshot_sync.runtime_command_headers",
        return_value={
            "Authorization": "Bearer signed-test-command",
            "Content-Type": "application/json",
        },
    ) as signer:
        yield signer


@pytest.fixture
def mock_settings():
    """Create a mock user settings"""
    settings = Mock()
    settings.ssh_private_key = (
        "-----BEGIN PRIVATE KEY-----\ntest_private_key\n-----END PRIVATE KEY-----"
    )
    settings.ssh_public_key = "ssh-rsa AAAAB3... test@example.com"
    settings.git_user_name = "Test User"
    settings.git_user_email = "test@example.com"
    settings.claude_auth_key = "test_api_key"
    settings.claude_selected_model = "claude-sonnet-5"
    settings.additional_settings = {
        "claudeCode": {
            "authMethod": "api_key",
            "apiKey": "test_api_key",
            "model": "claude-sonnet-5",
            "environmentVariables": [],
        },
        "codex": {
            "loginStatus": "connected",
            "model": "gpt-5.6-sol",
            "environmentVariables": [
                {"key": "OPENAI_BASE_URL", "value": "https://api.openai.com/v1"}
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
        },
    }
    return settings


class TestRuntimeSettingsSnapshotSyncService:
    """Test cases for RuntimeSettingsSnapshotSyncService"""

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_no_url(self, mock_workspace, mock_settings):
        """Test sync fails when workspace has no runtime URL"""
        mock_workspace.runtime_internal_url = None

        with pytest.raises(ValueError) as exc_info:
            await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

        assert "does not have runtime_internal_url" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_all_success(
        self,
        mock_workspace,
        mock_settings,
        mock_runtime_command_signing,
        httpx_response_factory,
    ):
        """Test successful sync of all settings"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert result["claude_code"]["success"] is True
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True
            assert mock_client.post.call_count == 4
            assert mock_runtime_command_signing.call_count == 4
            for signer_call in mock_runtime_command_signing.call_args_list:
                assert signer_call.kwargs == {
                    "workspace_id": "workspace_123",
                    "runtime_instance_id": "00000000-0000-4000-8000-000000000123",
                    "action": "settings.sync",
                }
            for request_call in mock_client.post.call_args_list:
                assert request_call.kwargs["headers"] == {
                    "Authorization": "Bearer signed-test-command",
                    "Content-Type": "application/json",
                }
            codex_call = next(
                call
                for call in mock_client.post.call_args_list
                if str(call.args[0]).endswith("/api/v1/internal/settings/codex")
            )
            assert (
                codex_call.kwargs["json"]["cliState"]["authJson"]["tokens"][
                    "refresh_token"
                ]
                == "refresh-token"
            )
            assert (
                codex_call.kwargs["json"]["cliState"]["configToml"]
                == '[projects."/workspace"]\ntrust_level = "trusted"\n'
            )
            assert (
                codex_call.kwargs["json"]["cliState"]["installationId"]
                == "installation-1"
            )

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_no_ssh_keys(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test sync when no SSH keys are configured"""
        mock_settings.ssh_private_key = None
        mock_settings.ssh_public_key = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert "No SSH keys need to sync" in result["ssh"]["message"]
            assert result["claude_code"]["success"] is True
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_no_git_settings(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test sync when no Git settings are configured"""
        mock_settings.git_user_name = None
        mock_settings.git_user_email = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert result["claude_code"]["success"] is True
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True
            assert "No Git settings need to sync" in result["git"]["message"]

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_ssh_error(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test SSH sync error handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "ssh-keys" in url:
                    raise Exception("SSH sync failed")
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is False
            assert result["claude_code"]["success"] is True
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_claude_code_http_error(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Claude Code sync HTTP error handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "claude-code" in url:
                    error_response = httpx_response_factory(
                        status_code=500, text="Internal Server Error"
                    )
                    raise httpx.HTTPStatusError(
                        "Error", request=Mock(), response=error_response
                    )
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert result["claude_code"]["success"] is False
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_claude_code_timeout(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Claude Code sync timeout handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "claude-code" in url:
                    raise httpx.TimeoutException("Request timeout")
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert result["claude_code"]["success"] is False
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_claude_code_connect_error(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Claude Code sync connection error handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "claude-code" in url:
                    raise httpx.ConnectError("Connection failed")
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["ssh"]["success"] is True
            assert result["claude_code"]["success"] is False
            assert result["codex"]["success"] is True
            assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_to_all_workspaces_no_workspaces(self, mock_settings):
        """Test sync to all workspaces when no workspaces are running"""
        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=Mock(
                scalars=Mock(return_value=Mock(all=Mock(return_value=[])))
            )
        )

        result = await RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces(
            "user_123", mock_settings, mock_db
        )

        assert result["success"] is True
        assert "No running workspaces need to sync" in result["message"]
        assert result["workspaces"] == []

    @pytest.mark.asyncio
    async def test_sync_to_all_workspaces_success(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test successful sync to all workspaces"""
        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=Mock(
                scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_workspace])))
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces(
                "user_123", mock_settings, mock_db
            )

            assert result["success"] is True
            assert len(result["workspaces"]) == 1
            assert result["workspaces"][0]["workspace_id"] == "workspace_123"
            assert result["workspaces"][0]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_to_all_workspaces_treats_missing_optional_settings_as_success(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test sync succeeds when optional SSH and Git settings are not configured"""
        mock_settings.ssh_private_key = None
        mock_settings.ssh_public_key = None
        mock_settings.git_user_name = None
        mock_settings.git_user_email = None
        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=Mock(
                scalars=Mock(return_value=Mock(all=Mock(return_value=[mock_workspace])))
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces(
                "user_123", mock_settings, mock_db
            )

            assert result["success"] is True
            assert result["workspaces"][0]["success"] is True
            assert result["workspaces"][0]["details"]["ssh"]["success"] is True
            assert result["workspaces"][0]["details"]["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_to_all_workspaces_partial_failure(
        self, mock_settings, httpx_response_factory
    ):
        """Test sync to all workspaces with partial failures"""
        workspace1 = Mock()
        workspace1.id = "workspace_1"
        workspace1.name = "Workspace 1"
        workspace1.runtime_internal_url = "http://runtime1.local:8000"
        workspace1.runtime_instance_id = "00000000-0000-4000-8000-000000000001"

        workspace2 = Mock()
        workspace2.id = "workspace_2"
        workspace2.name = "Workspace 2"
        workspace2.runtime_internal_url = None  # This will cause an error
        workspace2.runtime_instance_id = "00000000-0000-4000-8000-000000000002"

        mock_db = Mock()
        mock_db.execute = Mock(
            return_value=Mock(
                scalars=Mock(
                    return_value=Mock(all=Mock(return_value=[workspace1, workspace2]))
                )
            )
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_to_all_workspaces(
                "user_123", mock_settings, mock_db
            )

            assert result["success"] is False
            assert len(result["workspaces"]) == 2
            assert result["workspaces"][0]["success"] is True
            assert result["workspaces"][1]["success"] is False
            assert "error" in result["workspaces"][1]

    @pytest.mark.asyncio
    async def test_sync_settings_claude_code_from_additional_settings(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Claude Code settings are properly extracted from additional_settings"""
        mock_settings.claude_auth_key = None
        mock_settings.claude_selected_model = None
        mock_settings.additional_settings = {
            "claudeCode": {
                "authMethod": "subscription",
                "subscriptionAccessToken": "access_token",
                "subscriptionRefreshToken": "refresh_token",
                "subscriptionExpiresAt": "2024-12-31T23:59:59Z",
                "oauthAccount": "test@example.com",
                "model": "claude-fable-5",
                "environmentVariables": [{"name": "VAR1", "value": "value1"}],
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()

            captured_payload = {}

            async def capture_post(url, **kwargs):
                if "claude-code" in url:
                    captured_payload.update(kwargs.get("json", {}))
                return mock_response

            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

            assert result["claude_code"]["success"] is True
            assert captured_payload["authMethod"] == "subscription"
            assert captured_payload["model"] == "claude-fable-5"
            assert len(captured_payload["environmentVariables"]) == 1

    @pytest.mark.asyncio
    async def test_sync_settings_claude_code_auth_key_fallback(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Claude Code authMethod defaults to api_key when authKey exists in additional settings"""
        mock_settings.claude_auth_key = None
        mock_settings.additional_settings = {
            "claudeCode": {
                "authKey": "fallback-key",
                "model": "claude-3-7-sonnet",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = httpx_response_factory()
            captured_payload = {}

            async def capture_post(url, **kwargs):
                if "claude-code" in url:
                    captured_payload.update(kwargs.get("json", {}))
                return mock_response

            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

        assert result["claude_code"]["success"] is True
        assert captured_payload["apiKey"] == "fallback-key"
        assert captured_payload["authMethod"] == "api_key"
        assert captured_payload["model"] == "claude-3-7-sonnet"

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_claude_code_non_200_response(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test non-200 Claude Code response is treated as failed HTTP request"""
        error_response = httpx_response_factory(
            status_code=503,
            text="Service unavailable",
            raise_error=httpx.HTTPStatusError(
                "Service unavailable",
                request=Mock(),
                response=Mock(status_code=503, text="Service unavailable"),
            ),
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "claude-code" in url:
                    return error_response
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

        assert result["claude_code"]["success"] is False
        assert result["git"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_claude_code_unexpected_error(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test unexpected Claude Code error falls back to generic failure handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "claude-code" in url:
                    raise RuntimeError("boom")
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

        assert result["claude_code"]["success"] is False
        assert result["ssh"]["success"] is True

    @pytest.mark.asyncio
    async def test_sync_settings_to_runtime_git_error(
        self, mock_workspace, mock_settings, httpx_response_factory
    ):
        """Test Git sync error handling"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            async def post_side_effect(url, **kwargs):
                if "settings/git" in url:
                    raise RuntimeError("git failed")
                return httpx_response_factory()

            mock_client.post = AsyncMock(side_effect=post_side_effect)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime(
                mock_workspace, mock_settings
            )

        assert result["ssh"]["success"] is True
        assert result["claude_code"]["success"] is True
        assert result["git"]["success"] is False
