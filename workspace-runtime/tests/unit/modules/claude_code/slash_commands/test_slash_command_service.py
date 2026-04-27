"""Slash Command Service unit tests"""

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
    """Test listing slash commands functionality."""

    @patch.object(SlashCommandService, "_load_plugin_commands")
    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_list_scopes_all(self, mock_repo_class, mock_load_plugins, slash_command_service):
        """Test listing all scopes slash commands."""
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
        """Test listing only project scope slash commands."""
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
    """Test getting specific scope slash commands."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_get_scope_success(self, mock_repo_class, slash_command_service):
        """Test successful scope retrieval."""
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
    """Test creating slash command document."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_create_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document creation."""
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
    """Test updating slash command document."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document update."""
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
    """Test deleting slash command document."""

    @patch("app.modules.claude_code.slash_commands.service.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document deletion."""
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
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = SlashCommandService()

        # Assert
        assert service is not None
        assert service._repository is not None
