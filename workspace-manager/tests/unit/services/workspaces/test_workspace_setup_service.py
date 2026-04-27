"""WorkspaceSetupService 單元Testing"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models import WorkspaceSetupStatus, WorkspaceSetupTaskStatus
from app.services.workspace_setup_service import WorkspaceSetupService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Data庫 Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    return session


@pytest.fixture
def sample_workspace():
    """範例 workspace"""
    workspace = MagicMock()
    workspace.id = "workspace-123"
    workspace.owner_id = "user-123"
    workspace.runtime_internal_url = "http://localhost:3002"

    # Mock owner and settings
    owner = MagicMock()
    owner.settings = MagicMock()
    owner.settings.additional_settings = {"ssh": {"publicKey": "key123"}}
    workspace.owner = owner

    return workspace


@pytest.fixture
def sample_workspace_without_runtime():
    """None runtime 的 workspace"""
    workspace = MagicMock()
    workspace.id = "workspace-456"
    workspace.owner_id = "user-456"
    workspace.runtime_internal_url = None
    return workspace


@pytest.fixture
def setup_service(mock_db_session):
    """WorkspaceSetupService Instance"""
    return WorkspaceSetupService(mock_db_session)


# ============================================================================
# Initial Sync Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestInitialSync:
    """初始同步Testing"""

    @pytest.mark.asyncio
    async def test_run_initial_sync_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：Successfully執行初始同步"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH Sync succeeded"},
            "claude_code": {"success": True, "message": "Claude Code Sync succeeded"},
            "git": {"success": True, "message": "Git Sync succeeded"}
        }

        with patch("app.services.workspace_setup_service.SyncService.sync_settings_to_runtime",
                   new_callable=AsyncMock, return_value=mock_sync_result):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert isinstance(result, WorkspaceSetupStatus)
            assert result.workspace_id == "workspace-123"
            assert result.completed is True
            assert len(result.tasks) == 3

            # VerifyingAllTask都Successfully
            for task in result.tasks:
                assert task.status == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """Testing：runtime 未就緒時拋OutIncorrectly"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime not ready"):
            await setup_service.run_initial_sync("workspace-456")

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_user_settings(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：用HouseholdNo settings時跳過同步"""
        # Arrange
        sample_workspace.owner.settings = None
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = await setup_service.run_initial_sync("workspace-123")

        # Assert
        assert result.completed is True
        # AllTask應該被Mark為 skipped
        for task in result.tasks:
            assert task.status == "skipped"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_partial_failure(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：PartTaskUnsuccessfully時的Handle"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH Sync succeeded"},
            "claude_code": {"success": False, "message": "Claude Code 同步Unsuccessfully"},
            "git": {"success": True, "message": "Git Sync succeeded"}
        }

        with patch("app.services.workspace_setup_service.SyncService.sync_settings_to_runtime",
                   new_callable=AsyncMock, return_value=mock_sync_result):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is False  # 有Unsuccessfully的Task

            # Verifying各Task狀態
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "failed"
            assert task_statuses["git"] == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_skipped_tasks(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：跳過的Task(success=False但包含跳過訊息)也算Complete"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": False, "message": "No SSH settings"},
            "claude_code": {"success": True, "message": "Claude Code Sync succeeded"},
            "git": {"success": False, "message": "No Git settings"}
        }

        with patch("app.services.workspace_setup_service.SyncService.sync_settings_to_runtime",
                   new_callable=AsyncMock, return_value=mock_sync_result):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is True  # skipped 也算Complete

            # Verifying包含跳過訊息的Task被Mark為 skipped
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "skipped"
            assert task_statuses["claudeCode"] == "success"
            assert task_statuses["git"] == "skipped"


# ============================================================================
# Fetch Runtime Status Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestFetchRuntimeStatus:
    """獲Getting runtime 狀態Testing"""

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：Successfully獲Getting runtime 狀態"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH configured"},
                "claudeCode": {"status": "success", "message": "Claude Code 已Configure"},
                "git": {"status": "pending", "message": "Waiting Git Configure"}
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
            assert result.completed is False  # git 還At pending

            # Verifying各Task狀態
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "success"
            assert task_statuses["git"] == "pending"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """Testing：runtime 未就緒時拋OutIncorrectly"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime not ready"):
            await setup_service.fetch_runtime_status("workspace-456")

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_all_completed(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：AllTask都Complete"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH configured"},
                "claudeCode": {"status": "success", "message": "Claude Code 已Configure"},
                "git": {"status": "success", "message": "Git 已Configure"}
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
        """Testing：HTTP IncorrectlyHandle"""
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
        """Testing：Check項缺失時Use默認Value"""
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
            # AllTask應該Yes pending 狀態
            for task in result.tasks:
                assert task.status == "pending"
                assert task.message == "Waiting for synchronization result"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_normalizes_unknown_status(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：未知狀態會被正規化為 pending"""
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "mystery", "message": "未知狀態"},
                "claudeCode": {"status": "success", "message": "Claude Code 已Configure"},
                "git": {"status": "failed", "message": "Git Unsuccessfully"},
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


# ============================================================================
# Workspace Retrieval Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestWorkspaceRetrieval:
    """workspace 獲GettingTesting"""

    def test_get_workspace_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """Testing：Successfully獲Getting workspace"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = setup_service._get_workspace("workspace-123")

        # Assert
        assert result == sample_workspace

    def test_get_workspace_not_found(
        self, setup_service, mock_db_session
    ):
        """Testing：workspace does not exist時拋OutIncorrectly"""
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
    """Task狀態創建Testing"""

    def test_create_task_status(self, setup_service):
        """Testing：創建Task狀態"""
        # Act
        task = setup_service._create_task_status(
            key="ssh",
            status="success",
            message="SSH configured"
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
    """訊息AnalysisTesting"""

    def test_is_skipped_message_with_keyword_no(self, setup_service):
        """Testing：包含'None'Key字的訊息"""
        assert setup_service._is_skipped_message("No settings") is True

    def test_is_skipped_message_with_keyword_none(self, setup_service):
        """Testing：包含'無'Key字的訊息"""
        assert setup_service._is_skipped_message("No related settings") is True

    def test_is_skipped_message_with_keyword_not_set(self, setup_service):
        """Testing：包含'未Configure'Key字的訊息"""
        assert setup_service._is_skipped_message("SSH not configured") is True

    def test_is_skipped_message_without_keywords(self, setup_service):
        """Testing：不包含跳過Key字的訊息"""
        assert setup_service._is_skipped_message("Sync succeeded") is False

    def test_is_skipped_message_empty(self, setup_service):
        """Testing：空訊息"""
        assert setup_service._is_skipped_message("") is False
        assert setup_service._is_skipped_message(None) is False
