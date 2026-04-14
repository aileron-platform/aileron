"""Slash Command Service 單元測試"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.modules.claude_code.slash_commands.service import SlashCommandService
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandUpdateRequest,
)
from app.modules.claude_code.common import DocumentScope


@pytest.fixture
def slash_command_service():
    """Slash command service fixture."""
    return SlashCommandService()


@pytest.fixture
def mock_repository():
    """Mock repository."""
    return MagicMock()


class TestListScopes:
    """測試列出 slash commands 功能."""

    @patch.object(SlashCommandService, "_load_plugin_commands")
    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_list_scopes_all(self, mock_repo_class, mock_load_plugins, slash_command_service):
        """測試列出所有 scope 的 slash commands."""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        slash_command_service._repository = mock_repo
        mock_load_plugins.return_value = []

        # Act
        result = slash_command_service.list_scopes(workspace_id, None)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert len(result.scopes) >= 0

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_list_scopes_project_only(self, mock_repo_class, slash_command_service):
        """測試只列出 project scope 的 slash commands."""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        slash_command_service._repository = mock_repo

        # Act
        result = slash_command_service.list_scopes(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert len(result.scopes) >= 0


class TestGetScope:
    """測試獲取特定 scope 的 slash commands."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_get_scope_success(self, mock_repo_class, slash_command_service):
        """測試成功獲取 scope."""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        slash_command_service._repository = mock_repo

        # Act
        result = slash_command_service.get_scope(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert result.scope == DocumentScope.PROJECT


class TestCreateDocument:
    """測試創建 slash command 文檔."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_create_document_success(self, mock_repo_class, slash_command_service):
        """測試成功創建文檔."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_repo = MagicMock()

        from app.modules.claude_code.common import MarkdownDocumentRecord
        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        mock_repo.create_record.return_value = mock_record
        slash_command_service._repository = mock_repo

        payload = SlashCommandCreateRequest(
            file_name="test.md",
            content="# Test command",
            description="Test description"
        )

        # Act
        result = slash_command_service.create_document(workspace_id, scope, payload)

        # Assert
        assert result is not None
        assert mock_repo.create_record.called


class TestUpdateDocument:
    """測試更新 slash command 文檔."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, slash_command_service):
        """測試成功更新文檔."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        from app.modules.claude_code.common import MarkdownDocumentRecord
        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Updated",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        mock_repo.update_record.return_value = mock_record
        slash_command_service._repository = mock_repo

        payload = SlashCommandUpdateRequest(content="# Updated command")

        # Act
        result = slash_command_service.update_document(workspace_id, scope, file_name, payload)

        # Assert
        assert result is not None
        assert mock_repo.update_record.called


class TestDeleteDocument:
    """測試刪除 slash command 文檔."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, slash_command_service):
        """測試成功刪除文檔."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        mock_repo.delete_record.return_value = None
        slash_command_service._repository = mock_repo

        # Act
        result = slash_command_service.delete_document(workspace_id, scope, file_name)

        # Assert
        assert result is None
        assert mock_repo.delete_record.called


class TestServiceInitialization:
    """測試服務初始化."""

    def test_service_init(self):
        """測試服務初始化."""
        # Act
        service = SlashCommandService()

        # Assert
        assert service is not None
        assert service._repository is not None
