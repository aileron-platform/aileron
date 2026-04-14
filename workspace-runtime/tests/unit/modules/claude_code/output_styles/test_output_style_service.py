"""Output Style Service 單元測試"""

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
    """測試列出 output styles 功能."""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_list_scopes_all(self, mock_repo_class, output_style_service):
        """測試列出所有 scope 的 output styles."""
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
        """測試只列出 project scope 的 output styles."""
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
    """測試獲取特定 scope 的 output styles."""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_get_scope_success(self, mock_repo_class, output_style_service):
        """測試成功獲取 scope."""
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
    """測試創建 output style 文檔."""

    @patch.object(OutputStyleService, "_ensure_default_selection")
    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_create_document_success(self, mock_repo_class, mock_ensure_default_selection, output_style_service):
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
    """測試更新 output style 文檔."""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, output_style_service):
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
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated style")

        # Act
        result = output_style_service.update_document(workspace_id, scope, file_name, payload)

        # Assert
        assert result is not None
        assert mock_repo.update_record.called


class TestDeleteDocument:
    """測試刪除 output style 文檔."""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, output_style_service):
        """測試成功刪除文檔."""
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
    """測試 output style 預設選擇 helper。"""

    @patch("app.modules.claude_code.output_styles.service.write_json_file")
    @patch("app.modules.claude_code.output_styles.service.read_json_file")
    def test_ensure_default_selection_sets_full_file_name(
        self, mock_read_json_file, mock_write_json_file, output_style_service, tmp_path
    ):
        """當 settings 尚未設定 outputStyle 時，應寫入完整檔名。"""
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
        """已有 outputStyle 時，不應覆寫。"""
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
        """刪除最後一個 outputStyle 時，應移除空的 settings 檔案。"""
        settings_path = tmp_path / "settings.local.json"
        settings_path.write_text("{}")
        mock_read_json_file.return_value = {"outputStyle": "Learning.md"}

        with patch.object(output_style_service, "_settings_file", return_value=settings_path):
            output_style_service._clear_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        assert not settings_path.exists()


class TestServiceInitialization:
    """測試服務初始化."""

    def test_service_init(self):
        """測試服務初始化."""
        # Act
        service = OutputStyleService()

        # Assert
        assert service is not None
        assert service._repository is not None


class TestGetDocument:
    """測試獲取文檔."""

    @patch("app.modules.claude_code.output_styles.service.ScopedMarkdownRepository")
    def test_get_document_success(self, mock_repo_class, output_style_service):
        """測試成功獲取文檔."""
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
        """測試獲取不存在的文檔."""
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
        """測試獲取歧義文檔."""
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
    """測試更新文檔錯誤處理."""

    def test_update_document_ambiguous(self, output_style_service):
        """測試更新歧義文檔."""
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
        """測試更新不存在的文檔."""
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
    """測試刪除文檔錯誤處理."""

    def test_delete_document_ambiguous(self, output_style_service):
        """測試刪除歧義文檔."""
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
        """測試刪除不存在的文檔."""
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
    """測試創建文檔錯誤處理."""

    def test_create_document_duplicate(self, output_style_service):
        """測試創建重複文檔."""
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
