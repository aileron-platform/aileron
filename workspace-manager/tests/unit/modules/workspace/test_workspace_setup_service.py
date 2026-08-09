"""Unit Tests for WorkspaceSetupService"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.workspace.models import WorkspaceSetupStatus, WorkspaceSetupTaskStatus
from app.modules.workspace.setup import WorkspaceSetupService

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    return session


@pytest.fixture
def sample_workspace():
    """Sample workspace"""
    workspace = MagicMock()
    workspace.id = "workspace-123"
    workspace.owner_id = "user-123"
    workspace.runtime_internal_url = "http://localhost:3002"
    workspace.runtime_instance_id = "runtime-instance-123"
    workspace.agentic_tools = ["claude-code"]

    # Mock owner and settings
    owner = MagicMock()
    owner.settings = MagicMock()
    owner.settings.additional_settings = {"ssh": {"publicKey": "key123"}}
    workspace.owner = owner

    return workspace


@pytest.fixture
def sample_workspace_without_runtime():
    """Workspace without runtime"""
    workspace = MagicMock()
    workspace.id = "workspace-456"
    workspace.owner_id = "user-456"
    workspace.runtime_internal_url = None
    workspace.agentic_tools = ["claude-code"]
    return workspace


@pytest.fixture
def setup_service(mock_db_session, monkeypatch):
    """WorkspaceSetupService Instance"""
    monkeypatch.setattr(
        "app.modules.workspace.setup.runtime_command_headers",
        lambda **_kwargs: {
            "Authorization": "Bearer signed-assertion",
            "Content-Type": "application/json",
        },
    )
    return WorkspaceSetupService(mock_db_session)


# ============================================================================
# Initial Sync Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestInitialSync:
    """Initial Sync Tests"""

    @pytest.mark.asyncio
    async def test_run_initial_sync_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Successfully Execute Initial Sync"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH Sync succeeded"},
            "claude_code": {"success": True, "message": "Claude Code Sync succeeded"},
            "git": {"success": True, "message": "Git Sync succeeded"},
        }

        with patch(
            "app.modules.workspace.setup.RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime",
            new_callable=AsyncMock,
            return_value=mock_sync_result,
        ):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert isinstance(result, WorkspaceSetupStatus)
            assert result.workspace_id == "workspace-123"
            assert result.completed is True
            assert len(result.tasks) == 3

            # Verify all tasks succeeded
            for task in result.tasks:
                assert task.status == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """Test: Throw Error When Runtime Not Ready"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime not ready"):
            await setup_service.run_initial_sync("workspace-456")

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_user_settings(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Skip Sync When User Has No Settings"""
        # Arrange
        sample_workspace.owner.settings = None
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = await setup_service.run_initial_sync("workspace-123")

        # Assert
        assert result.completed is True
        # All tasks should be marked as skipped
        for task in result.tasks:
            assert task.status == "skipped"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_partial_failure(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Handle Partial Task Failures"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH Sync succeeded"},
            "claude_code": {"success": False, "message": "Claude Code sync failed"},
            "git": {"success": True, "message": "Git Sync succeeded"},
        }

        with patch(
            "app.modules.workspace.setup.RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime",
            new_callable=AsyncMock,
            return_value=mock_sync_result,
        ):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is False  # Has failed tasks

            # Verify each task status
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "failed"
            assert task_statuses["git"] == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_skipped_tasks(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Skipped Tasks (success=False but contains skip message) Count as Complete"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": False, "message": "No SSH settings"},
            "claude_code": {"success": True, "message": "Claude Code Sync succeeded"},
            "git": {"success": False, "message": "No Git settings"},
        }

        with patch(
            "app.modules.workspace.setup.RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime",
            new_callable=AsyncMock,
            return_value=mock_sync_result,
        ):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is True  # Skipped tasks count as complete

            # Verify tasks with skip message are marked as skipped
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "skipped"
            assert task_statuses["claudeCode"] == "success"
            assert task_statuses["git"] == "skipped"

    @pytest.mark.asyncio
    async def test_run_initial_sync_uses_codex_task_for_codex_workspace(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Codex workspace uses Codex setup task"""
        sample_workspace.agentic_tools = ["codex"]
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH Sync succeeded"},
            "codex": {"success": True, "message": "Codex Sync succeeded"},
            "git": {"success": True, "message": "Git Sync succeeded"},
        }

        with patch(
            "app.modules.workspace.setup.RuntimeSettingsSnapshotSyncService.sync_settings_to_runtime",
            new_callable=AsyncMock,
            return_value=mock_sync_result,
        ):
            result = await setup_service.run_initial_sync("workspace-123")

        task_names = {task.task_key: task.task_name for task in result.tasks}
        task_statuses = {task.task_key: task.status for task in result.tasks}
        assert "claudeCode" not in task_statuses
        assert task_names["codex"] == "Codex"
        assert task_statuses["codex"] == "success"


# ============================================================================
# Fetch Runtime Status Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestFetchRuntimeStatus:
    """Runtime Status Retrieval Tests"""

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Successfully Get Runtime Status"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH configured"},
                "claudeCode": {
                    "status": "success",
                    "message": "Claude Code configured",
                },
                "git": {
                    "status": "pending",
                    "message": "Waiting for Git configuration",
                },
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act
            result = await setup_service.fetch_runtime_status("workspace-123")

            # Assert
            assert isinstance(result, WorkspaceSetupStatus)
            assert result.workspace_id == "workspace-123"
            assert result.completed is False  # git is still pending

            # Verify each task status
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "success"
            assert task_statuses["git"] == "pending"
            mock_client.get.assert_awaited_once_with(
                "http://localhost:3002/api/v1/internal/setup/status"
            )

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """Test: Throw Error When Runtime Not Ready"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime not ready"):
            await setup_service.fetch_runtime_status("workspace-456")

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_all_completed(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: All Tasks Completed"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH configured"},
                "claudeCode": {
                    "status": "success",
                    "message": "Claude Code configured",
                },
                "git": {"status": "success", "message": "Git configured"},
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act
            result = await setup_service.fetch_runtime_status("workspace-123")

            # Assert
            assert result.completed is True

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_with_http_error(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: HTTP Error Handling"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock()
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act & Assert
            with pytest.raises(httpx.HTTPStatusError):
                await setup_service.fetch_runtime_status("workspace-123")

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_with_missing_checks(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Use Default Values When Check Items Missing"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {"checks": {}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            # Act
            result = await setup_service.fetch_runtime_status("workspace-123")

            # Assert
            # All tasks should be in pending status
            for task in result.tasks:
                assert task.status == "pending"
                assert task.message == "Waiting for synchronization result"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_normalizes_unknown_status(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Unknown Status Normalized to Pending"""
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "mystery", "message": "Unknown status"},
                "claudeCode": {
                    "status": "success",
                    "message": "Claude Code configured",
                },
                "git": {"status": "failed", "message": "Git failed"},
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await setup_service.fetch_runtime_status("workspace-123")

        task_statuses = {task.task_key: task.status for task in result.tasks}
        assert task_statuses["ssh"] == "pending"
        assert task_statuses["claudeCode"] == "success"
        assert task_statuses["git"] == "failed"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_uses_codex_check_for_codex_workspace(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Codex workspace reads Codex runtime status"""
        sample_workspace.agentic_tools = ["codex"]
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH configured"},
                "codex": {"status": "success", "message": "Codex configured"},
                "git": {"status": "success", "message": "Git configured"},
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await setup_service.fetch_runtime_status("workspace-123")

        task_names = {task.task_key: task.task_name for task in result.tasks}
        task_statuses = {task.task_key: task.status for task in result.tasks}
        assert "claudeCode" not in task_statuses
        assert task_names["codex"] == "Codex"
        assert task_statuses["codex"] == "success"


# ============================================================================
# Workspace Retrieval Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceRetrieval:
    """Workspace Retrieval Tests"""

    def test_get_workspace_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Test: Successfully Retrieve Workspace"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = setup_service._get_workspace("workspace-123")

        # Assert
        assert result == sample_workspace

    def test_get_workspace_not_found(self, setup_service, mock_db_session):
        """Test: Throw Error When Workspace Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="does not exist"):
            setup_service._get_workspace("nonexistent-workspace")


# ============================================================================
# Task Status Creation Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestTaskStatusCreation:
    """Task Status Creation Tests"""

    def test_create_task_status(self, setup_service):
        """Test: Create Task Status"""
        # Act
        task = setup_service._create_task_status(
            key="ssh",
            display_name="SSH Keys",
            status="success",
            message="SSH configured",
        )

        # Assert
        assert isinstance(task, WorkspaceSetupTaskStatus)
        assert task.task_key == "ssh"
        assert task.task_name == "SSH Keys"
        assert task.status == "success"
        assert task.message == "SSH configured"


# ============================================================================
# Message Analysis Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.workspace
class TestMessageAnalysis:
    """Message Analysis Tests"""

    def test_is_skipped_message_with_keyword_no(self, setup_service):
        """Test: Message Containing 'No' Keyword"""
        assert setup_service._is_skipped_message("No settings") is True

    def test_is_skipped_message_with_keyword_none(self, setup_service):
        """Test: Message Containing 'None' Keyword"""
        assert setup_service._is_skipped_message("No related settings") is True

    def test_is_skipped_message_with_keyword_not_set(self, setup_service):
        """Test: Message Containing 'Not Configured' Keyword"""
        assert setup_service._is_skipped_message("SSH not configured") is True

    def test_is_skipped_message_without_keywords(self, setup_service):
        """Test: Message Without Skip Keywords"""
        assert setup_service._is_skipped_message("Sync succeeded") is False

    def test_is_skipped_message_empty(self, setup_service):
        """Test: Empty Message"""
        assert setup_service._is_skipped_message("") is False
        assert setup_service._is_skipped_message(None) is False
