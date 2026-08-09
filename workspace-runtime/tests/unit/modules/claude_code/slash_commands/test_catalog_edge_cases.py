"""Slash Command Service unit tests"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.modules.claude_code.slash_commands.catalog import SlashCommandService
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandUpdateRequest,
)
from app.modules.claude_code.documents import DocumentScope
from app.core.revision import compute_revision


EMPTY_REVISION = compute_revision("{}")


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
    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
    def test_list_scopes_all(
        self, mock_repo_class, mock_load_plugins, slash_command_service
    ):
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
        assert result.items == []
        assert [scope.scope for scope in result.available_scopes] == [
            DocumentScope.PROJECT,
            DocumentScope.USER,
            DocumentScope.PLUGIN,
        ]

    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
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
        assert result.items == []
        assert [scope.scope for scope in result.available_scopes] == [
            DocumentScope.PROJECT
        ]


class TestGetScope:
    """Test getting specific scope slash commands."""

    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
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

    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
    def test_create_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document creation."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_repo = MagicMock()

        from app.modules.claude_code.documents import MarkdownDocumentRecord

        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        mock_repo.list_records.return_value = []
        slash_command_service._repository = mock_repo

        payload = SlashCommandCreateRequest(
            path="test.md",
            content="# Test command",
            revision=EMPTY_REVISION,
            description="Test description",
        )

        # Act
        with patch.object(
            slash_command_service, "_create_record_by_path", return_value=mock_record
        ):
            result = slash_command_service.create_document(workspace_id, scope, payload)

        # Assert
        assert result is not None


class TestUpdateDocument:
    """Test updating slash command document."""

    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document update."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT

        mock_repo = MagicMock()
        from app.modules.claude_code.documents import MarkdownDocumentRecord

        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Updated",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        slash_command_service._repository = mock_repo

        payload = SlashCommandUpdateRequest(
            path="test.md",
            content="# Updated command",
            revision=compute_revision("# Updated"),
        )

        # Act
        with (
            patch.object(
                slash_command_service, "_load_record_by_path", return_value=mock_record
            ),
            patch.object(
                slash_command_service,
                "_update_record_by_path",
                return_value=mock_record,
            ),
        ):
            result = slash_command_service.update_document(workspace_id, scope, payload)

        # Assert
        assert result is not None


class TestDeleteDocument:
    """Test deleting slash command document."""

    @patch("app.modules.claude_code.slash_commands.catalog.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, slash_command_service):
        """Test successful document deletion."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT

        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        slash_command_service._repository = mock_repo

        # Act
        with (
            patch.object(slash_command_service, "_load_record_by_path") as load_record,
            patch.object(slash_command_service, "_delete_record_by_path"),
        ):
            load_record.return_value = type("Record", (), {"content": "# Test"})()
            result = slash_command_service.delete_document(
                workspace_id, scope, "test.md", compute_revision("# Test")
            )

        # Assert
        assert result is not None


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = SlashCommandService()

        # Assert
        assert service is not None
        assert service._repository is not None
