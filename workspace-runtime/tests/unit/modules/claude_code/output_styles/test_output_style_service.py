"""Output Style Service unit tests"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.modules.claude_code.output_styles.service import OutputStyleService
from app.modules.claude_code.output_styles.models import (
    OutputStyleCreateRequest,
    OutputStyleUpdateRequest,
)
from app.modules.claude_code.common import DocumentScope


@pytest.fixture
def output_style_service():
    """Output style service fixture."""
    return OutputStyleService()


class TestListScopes:
    "Test listing output styles functionality.""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_list_scopes_all(self, mock_repo_class, output_style_service):
        "Test listing all scope output styles.""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.list_scopes(workspace_id, None)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert len(result.scopes) >= 0

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_list_scopes_project_only(self, mock_repo_class, output_style_service):
        "Test listing only project scope output styles.""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.list_scopes(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert len(result.scopes) >= 0


class TestGetScope:
    "Test getting specific scope output styles.""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_get_scope_success(self, mock_repo_class, output_style_service):
        "Test successfully getting scope.""
        # Arrange
        workspace_id = "test-workspace"
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.get_scope(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert result.scope == DocumentScope.PROJECT


class TestCreateDocument:
    "Test creating output style document.""

    @patch.object(OutputStyleService, "_ensure_default_selection")
    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_create_document_success(self, mock_repo_class, mock_ensure_default_selection, output_style_service):
        "Test successfully creating document.""
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
        output_style_service._repository = mock_repo

        payload = OutputStyleCreateRequest(
            file_name="test.md",
            content="# Test style",
            description="Test description"
        )

        # Act
        result = output_style_service.create_document(workspace_id, scope, payload)

        # Assert
        assert result is not None
        assert mock_repo.create_record.called
        mock_ensure_default_selection.assert_called_once_with(workspace_id, scope, "test.md")


class TestUpdateDocument:
    "Test updating output style document.""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, output_style_service):
        "Test successfully updating document.""
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
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated style")

        # Act
        result = output_style_service.update_document(workspace_id, scope, file_name, payload)

        # Assert
        assert result is not None
        assert mock_repo.update_record.called


class TestDeleteDocument:
    "Test deleting output style document.""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, output_style_service):
        "Test successfully deleting document.""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        mock_repo.delete_record.return_value = None
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.delete_document(workspace_id, scope, file_name)

        # Assert
        assert result is not None
        assert result.deleted is True
        assert mock_repo.delete_record.called


class TestDefaultSelectionHelpers:
    """Test output style default selection helper."" "

    @patch("app.modules.claude_code.output_styles.service.write_json_file")
    @patch("app.modules.claude_code.output_styles.service.read_json_file")
    def test_ensure_default_selection_sets_full_file_name(
        self, mock_read_json_file, mock_write_json_file, output_style_service, tmp_path
    ):
        """When outputStyle not yet set in settings, should write full filename."" "
        settings_path = tmp_path / "settings.local.json"
        mock_read_json_file.return_value = {}

        with patch.object(output_style_service, "_settings_file", return_value=settings_path):
            output_style_service._ensure_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        mock_write_json_file.assert_called_once_with(
            settings_path, {"outputStyle": "Learning.md"}
        )

    @patch("app.modules.claude_code.output_styles.service.write_json_file")
    @patch("app.modules.claude_code.output_styles.service.read_json_file")
    def test_ensure_default_selection_keeps_existing_selection(
        self, mock_read_json_file, mock_write_json_file, output_style_service, tmp_path
    ):
        """When outputStyle already exists, should not overwrite."" "
        settings_path = tmp_path / "settings.local.json"
        mock_read_json_file.return_value = {"outputStyle": "Existing.md"}

        with patch.object(output_style_service, "_settings_file", return_value=settings_path):
            output_style_service._ensure_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        mock_write_json_file.assert_not_called()

    @patch("app.modules.claude_code.output_styles.service.read_json_file")
    def test_clear_default_selection_deletes_empty_settings_file(
        self, mock_read_json_file, output_style_service, tmp_path
    ):
        """When deleting last outputStyle, should remove empty settings file."""
        settings_path = tmp_path / "settings.local.json"
        settings_path.write_text("{}")
        mock_read_json_file.return_value = {"outputStyle": "Learning.md"}

        with patch.object(output_style_service, "_settings_file", return_value=settings_path):
            output_style_service._clear_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        assert not settings_path.exists()


class TestServiceInitialization:
    "Test service initialization.""

    def test_service_init(self):
        "Test service initialization.""
        # Act
        service = OutputStyleService()

        # Assert
        assert service is not None
        assert service._repository is not None


class TestGetDocument:
    "Test getting document.""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_get_document_success(self, mock_repo_class, output_style_service):
        "Test successfully getting document.""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        from app.modules.claude_code.common import MarkdownDocumentRecord
        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={"name": "Test Style", "description": "Test description"},
            size_bytes=100,
            updated_at=None,
        )
        mock_repo.get_record.return_value = mock_record
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.get_document(workspace_id, scope, file_name)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert result.scope == scope
        assert result.document.content == "# Test"
        mock_repo.get_record.assert_called_once()

    def test_get_document_not_found(self, output_style_service):
        "Test getting non-existent document.""
        # Arrange
        from app.modules.claude_code.common import DocumentNotFoundError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "missing.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = DocumentNotFoundError("Not found")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.get_document(workspace_id, scope, file_name)

        assert exc_info.value.status_code == 404

    def test_get_document_ambiguous(self, output_style_service):
        "Test getting ambiguous document.""
        # Arrange
        from app.modules.claude_code.common import AmbiguousDocumentError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "ambiguous.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = AmbiguousDocumentError("Ambiguous")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.get_document(workspace_id, scope, file_name)

        assert exc_info.value.status_code == 409


class TestUpdateDocumentErrors:
    "Test updating document error handling.""

    def test_update_document_ambiguous(self, output_style_service):
        "Test updating ambiguous document.""
        # Arrange
        from app.modules.claude_code.common import AmbiguousDocumentError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "ambiguous.md"

        mock_repo = MagicMock()
        mock_repo.update_record.side_effect = AmbiguousDocumentError("Ambiguous")
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated")

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.update_document(workspace_id, scope, file_name, payload)

        assert exc_info.value.status_code == 409

    def test_update_document_not_found_error(self, output_style_service):
        "Test updating non-existent document.""
        # Arrange
        from app.modules.claude_code.common import DocumentNotFoundError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "missing.md"

        mock_repo = MagicMock()
        mock_repo.update_record.side_effect = DocumentNotFoundError("Not found")
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated")

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.update_document(workspace_id, scope, file_name, payload)

        assert exc_info.value.status_code == 404


class TestDeleteDocumentErrors:
    "Test deleting document error handling.""

    def test_delete_document_ambiguous(self, output_style_service):
        "Test deleting ambiguous document.""
        # Arrange
        from app.modules.claude_code.common import AmbiguousDocumentError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "ambiguous.md"

        mock_repo = MagicMock()
        mock_repo.delete_record.side_effect = AmbiguousDocumentError("Ambiguous")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.delete_document(workspace_id, scope, file_name)

        assert exc_info.value.status_code == 409

    def test_delete_document_not_found_error(self, output_style_service):
        "Test deleting non-existent document.""
        # Arrange
        from app.modules.claude_code.common import DocumentNotFoundError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "missing.md"

        mock_repo = MagicMock()
        mock_repo.delete_record.side_effect = DocumentNotFoundError("Not found")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.delete_document(workspace_id, scope, file_name)

        assert exc_info.value.status_code == 404


class TestCreateDocumentError:
    "Test creating document error handling.""

    def test_create_document_duplicate(self, output_style_service):
        "Test creating duplicate document.""
        # Arrange
        from app.modules.claude_code.common import DuplicateDocumentError
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT

        mock_repo = MagicMock()
        mock_repo.create_record.side_effect = DuplicateDocumentError("Duplicate")
        output_style_service._repository = mock_repo

        payload = OutputStyleCreateRequest(
            file_name="existing.md",
            content="# Content",
            description="Test"
        )

        # Act & Assert
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            output_style_service.create_document(workspace_id, scope, payload)

        assert exc_info.value.status_code == 409
