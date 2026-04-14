"""WorkspaceSetupService 單元測試"""

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
    """Mock 資料庫 Session"""
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
    """沒有 runtime 的 workspace"""
    workspace = MagicMock()
    workspace.id = "workspace-456"
    workspace.owner_id = "user-456"
    workspace.runtime_internal_url = None
    return workspace


@pytest.fixture
def setup_service(mock_db_session):
    """WorkspaceSetupService 實例"""
    return WorkspaceSetupService(mock_db_session)


# ============================================================================
# Initial Sync Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestInitialSync:
    """初始同步測試"""

    @pytest.mark.asyncio
    async def test_run_initial_sync_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：成功執行初始同步"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH 同步成功"},
            "claude_code": {"success": True, "message": "Claude Code 同步成功"},
            "git": {"success": True, "message": "Git 同步成功"}
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

            # 驗證所有任務都成功
            for task in result.tasks:
                assert task.status == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """測試：runtime 未就緒時拋出錯誤"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime 尚未就緒"):
            await setup_service.run_initial_sync("workspace-456")

    @pytest.mark.asyncio
    async def test_run_initial_sync_without_user_settings(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：用戶沒有設定時跳過同步"""
        # Arrange
        sample_workspace.owner.settings = None
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = await setup_service.run_initial_sync("workspace-123")

        # Assert
        assert result.completed is True
        # 所有任務應該被標記為 skipped
        for task in result.tasks:
            assert task.status == "skipped"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_partial_failure(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：部分任務失敗時的處理"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": True, "message": "SSH 同步成功"},
            "claude_code": {"success": False, "message": "Claude Code 同步失敗"},
            "git": {"success": True, "message": "Git 同步成功"}
        }

        with patch("app.services.workspace_setup_service.SyncService.sync_settings_to_runtime",
                   new_callable=AsyncMock, return_value=mock_sync_result):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is False  # 有失敗的任務

            # 驗證各任務狀態
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "failed"
            assert task_statuses["git"] == "success"

    @pytest.mark.asyncio
    async def test_run_initial_sync_with_skipped_tasks(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：跳過的任務(success=False但包含跳過訊息)也算完成"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_sync_result = {
            "ssh": {"success": False, "message": "沒有 SSH 設定"},
            "claude_code": {"success": True, "message": "Claude Code 同步成功"},
            "git": {"success": False, "message": "無 Git 設定"}
        }

        with patch("app.services.workspace_setup_service.SyncService.sync_settings_to_runtime",
                   new_callable=AsyncMock, return_value=mock_sync_result):
            # Act
            result = await setup_service.run_initial_sync("workspace-123")

            # Assert
            assert result.completed is True  # skipped 也算完成

            # 驗證包含跳過訊息的任務被標記為 skipped
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
    """獲取 runtime 狀態測試"""

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：成功獲取 runtime 狀態"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH 已設定"},
                "claudeCode": {"status": "success", "message": "Claude Code 已設定"},
                "git": {"status": "pending", "message": "等待 Git 設定"}
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
            assert result.completed is False  # git 還在 pending

            # 驗證各任務狀態
            task_statuses = {task.task_key: task.status for task in result.tasks}
            assert task_statuses["ssh"] == "success"
            assert task_statuses["claudeCode"] == "success"
            assert task_statuses["git"] == "pending"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_without_runtime(
        self, setup_service, mock_db_session, sample_workspace_without_runtime
    ):
        """測試：runtime 未就緒時拋出錯誤"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace_without_runtime

        # Act & Assert
        with pytest.raises(ValueError, match="runtime 尚未就緒"):
            await setup_service.fetch_runtime_status("workspace-456")

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_all_completed(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：所有任務都完成"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "success", "message": "SSH 已設定"},
                "claudeCode": {"status": "success", "message": "Claude Code 已設定"},
                "git": {"status": "success", "message": "Git 已設定"}
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
        """測試：HTTP 錯誤處理"""
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
        """測試：檢查項缺失時使用默認值"""
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
            # 所有任務應該是 pending 狀態
            for task in result.tasks:
                assert task.status == "pending"
                assert task.message == "等待同步結果"

    @pytest.mark.asyncio
    async def test_fetch_runtime_status_normalizes_unknown_status(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：未知狀態會被正規化為 pending"""
        mock_db_session.get.return_value = sample_workspace

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "checks": {
                "ssh": {"status": "mystery", "message": "未知狀態"},
                "claudeCode": {"status": "success", "message": "Claude Code 已設定"},
                "git": {"status": "failed", "message": "Git 失敗"},
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
    """workspace 獲取測試"""

    def test_get_workspace_success(
        self, setup_service, mock_db_session, sample_workspace
    ):
        """測試：成功獲取 workspace"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace

        # Act
        result = setup_service._get_workspace("workspace-123")

        # Assert
        assert result == sample_workspace

    def test_get_workspace_not_found(
        self, setup_service, mock_db_session
    ):
        """測試：workspace 不存在時拋出錯誤"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="不存在"):
            setup_service._get_workspace("nonexistent-workspace")


# ============================================================================
# Task Status Creation Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestTaskStatusCreation:
    """任務狀態創建測試"""

    def test_create_task_status(self, setup_service):
        """測試：創建任務狀態"""
        # Act
        task = setup_service._create_task_status(
            key="ssh",
            status="success",
            message="SSH 已設定"
        )

        # Assert
        assert isinstance(task, WorkspaceSetupTaskStatus)
        assert task.task_key == "ssh"
        assert task.task_name == "SSH Keys"
        assert task.status == "success"
        assert task.message == "SSH 已設定"


# ============================================================================
# Message Analysis Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestMessageAnalysis:
    """訊息分析測試"""

    def test_is_skipped_message_with_keyword_no(self, setup_service):
        """測試：包含'沒有'關鍵字的訊息"""
        assert setup_service._is_skipped_message("沒有設定") is True

    def test_is_skipped_message_with_keyword_none(self, setup_service):
        """測試：包含'無'關鍵字的訊息"""
        assert setup_service._is_skipped_message("無相關設定") is True

    def test_is_skipped_message_with_keyword_not_set(self, setup_service):
        """測試：包含'未設定'關鍵字的訊息"""
        assert setup_service._is_skipped_message("未設定 SSH") is True

    def test_is_skipped_message_without_keywords(self, setup_service):
        """測試：不包含跳過關鍵字的訊息"""
        assert setup_service._is_skipped_message("同步成功") is False

    def test_is_skipped_message_empty(self, setup_service):
        """測試：空訊息"""
        assert setup_service._is_skipped_message("") is False
        assert setup_service._is_skipped_message(None) is False
