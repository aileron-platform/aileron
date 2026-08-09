"""Output Style Service unit tests"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.revision import compute_revision
from app.modules.claude_code.documents import DocumentScope, MarkdownDocumentRecord
from app.modules.claude_code.output_styles.models import (
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleUpdateRequest,
)
from app.modules.claude_code.output_styles.catalog import OutputStyleService
from app.modules.claude_code.plugins.loader import ComponentFileInfo


def scope_revision_for(*records: MarkdownDocumentRecord) -> str:
    content_by_path = {
        record.file_path.relative_to(record.root_path).as_posix(): record.content
        for record in records
    }
    return compute_revision(
        json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
    )


@pytest.fixture
def output_style_service():
    """Output style service fixture."""
    return OutputStyleService()


class TestListScopes:
    """Test listing output styles functionality."""

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_list_scopes_all(self, mock_repo_class, output_style_service):
        """Test listing all scope output styles."""
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
        assert result.scopes[0].revision == compute_revision("{}")

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_list_scopes_project_only(self, mock_repo_class, output_style_service):
        """Test listing only project scope output styles."""
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
        assert result.scopes[0].revision == compute_revision("{}")


class TestGetScope:
    """Test getting specific scope output styles."""

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_get_scope_success(self, mock_repo_class, output_style_service):
        """Test successfully getting scope."""
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
        assert result.revision == compute_revision("{}")

    def test_get_plugin_scope_uses_installed_root_projection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        style_path = tmp_path / "installed" / "output-styles" / "calm.md"
        style_path.parent.mkdir(parents=True)
        style_path.write_text(
            "---\nname: Calm\ndescription: Quiet output\n---\n# Calm\n",
            encoding="utf-8",
        )
        loader = MagicMock()
        loader.load_plugin_output_styles.return_value = [
            ComponentFileInfo(
                file_path=str(style_path),
                file_name="calm.md",
                plugin_name="demo",
                marketplace_name="registry",
                plugin_id="demo@registry",
                relative_source_path="output-styles/calm.md",
            )
        ]
        gate = MagicMock()
        gate.generation.return_value = 9
        monkeypatch.setattr(
            "app.modules.claude_code.output_styles.catalog."
            "get_marketplace_provider_gate",
            lambda: gate,
        )
        service = OutputStyleService(plugin_loader=loader)

        result = service.get_scope(
            "workspace-1",
            DocumentScope.PLUGIN,
            plugin_id="demo@registry",
        )
        detail = service.get_document(
            "workspace-1",
            DocumentScope.PLUGIN,
            "output-styles/calm.md",
            plugin_id="demo@registry",
        )

        assert result.provider_resource_generation == 9
        assert result.documents[0].scope is DocumentScope.PLUGIN
        assert result.documents[0].read_only is True
        assert result.documents[0].editable is False
        assert result.documents[0].plugin_id == "demo@registry"
        assert result.documents[0].generation == 9
        assert result.documents[0].provenance is not None
        assert result.documents[0].provenance.provider == "claude-code"
        assert result.documents[0].relative_source_path == ("output-styles/calm.md")
        assert result.documents[0].file_name == "output-styles/calm.md"
        assert detail.document.content.endswith("# Calm\n")
        assert detail.document.generation == 9

    def test_plugin_styles_use_package_relative_identity_for_nested_same_names(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        first_path = tmp_path / "installed" / "output-styles" / "a" / "style.md"
        second_path = tmp_path / "installed" / "output-styles" / "b" / "style.md"
        first_path.parent.mkdir(parents=True)
        second_path.parent.mkdir(parents=True)
        first_path.write_text("# First\n", encoding="utf-8")
        second_path.write_text("# Second\n", encoding="utf-8")
        loader = MagicMock()
        loader.load_plugin_output_styles.return_value = [
            ComponentFileInfo(
                file_path=str(first_path),
                file_name="style.md",
                plugin_name="demo",
                marketplace_name="registry",
                plugin_id="demo@registry",
                relative_source_path="output-styles/a/style.md",
            ),
            ComponentFileInfo(
                file_path=str(second_path),
                file_name="style.md",
                plugin_name="demo",
                marketplace_name="registry",
                plugin_id="demo@registry",
                relative_source_path="output-styles/b/style.md",
            ),
        ]
        gate = MagicMock()
        gate.generation.return_value = 11
        monkeypatch.setattr(
            "app.modules.claude_code.output_styles.catalog."
            "get_marketplace_provider_gate",
            lambda: gate,
        )
        service = OutputStyleService(plugin_loader=loader)

        listed = service.get_scope(
            "workspace-1",
            DocumentScope.PLUGIN,
            plugin_id="demo@registry",
        )
        first = service.get_document(
            "workspace-1",
            DocumentScope.PLUGIN,
            "output-styles/a/style.md",
            plugin_id="demo@registry",
        )
        second = service.get_document(
            "workspace-1",
            DocumentScope.PLUGIN,
            "output-styles/b/style.md",
            plugin_id="demo@registry",
        )

        assert [item.file_name for item in listed.documents] == [
            "output-styles/a/style.md",
            "output-styles/b/style.md",
        ]
        assert first.document.content == "# First\n"
        assert second.document.content == "# Second\n"
        serialized = json.dumps(
            listed.model_dump(by_alias=True),
            sort_keys=True,
        )
        assert str(tmp_path / "installed") not in serialized

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            service.get_document(
                "workspace-1",
                DocumentScope.PLUGIN,
                "style.md",
                plugin_id="demo@registry",
            )
        assert exc.value.status_code == 404

    @pytest.mark.parametrize(
        "relative_source_path",
        ["../style.md", "/installed/output-styles/style.md", r"output-styles\style.md"],
    )
    def test_plugin_styles_reject_unsafe_public_locator(
        self,
        relative_source_path: str,
    ) -> None:
        loader = MagicMock()
        loader.load_plugin_output_styles.return_value = [
            ComponentFileInfo(
                file_path="/installed/output-styles/style.md",
                file_name="style.md",
                plugin_name="demo",
                marketplace_name="registry",
                plugin_id="demo@registry",
                relative_source_path=relative_source_path,
            )
        ]
        service = OutputStyleService(plugin_loader=loader)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            service.get_scope(
                "workspace-1",
                DocumentScope.PLUGIN,
                plugin_id="demo@registry",
            )

        assert exc.value.status_code == 409
        assert exc.value.detail == {
            "errorCode": "marketplace.settings.plugin_resource_parse_failed"
        }


class TestCreateDocument:
    """Test creating output style document."""

    @patch.object(OutputStyleService, "_ensure_default_selection")
    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_create_document_success(
        self, mock_repo_class, mock_ensure_default_selection, output_style_service
    ):
        """Test successfully creating document."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_repo = MagicMock()

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
        mock_repo.create_record.return_value = mock_record
        output_style_service._repository = mock_repo

        payload = OutputStyleCreateRequest(
            file_name="test.md",
            content="# Test style",
            description="Test description",
            revision=compute_revision("{}"),
        )

        # Act
        result = output_style_service.create_document(workspace_id, scope, payload)

        # Assert
        assert result is not None
        assert result.revision == compute_revision("# Test")
        assert mock_repo.create_record.called
        mock_ensure_default_selection.assert_called_once_with(
            workspace_id, scope, "test.md"
        )

    def test_create_document_rejects_stale_scope_revision(self, output_style_service):
        """Test creating with stale scope revision."""
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_repo = MagicMock()
        mock_repo.list_records.return_value = [
            MarkdownDocumentRecord(
                file_path=Path("/test/path/existing.md"),
                root_path=Path("/test/path"),
                scope=scope,
                content="# Existing",
                metadata={},
                size_bytes=10,
                updated_at=None,
            )
        ]
        output_style_service._repository = mock_repo
        payload = OutputStyleCreateRequest(
            file_name="test.md",
            content="# Test style",
            revision="stale",
        )

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.create_document(workspace_id, scope, payload)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repo.create_record.assert_not_called()


class TestUpdateDocument:
    """Test updating output style document."""

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_update_document_success(self, mock_repo_class, output_style_service):
        """Test successfully updating document."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        mock_record = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Updated",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        mock_repo.get_record.return_value = mock_record
        mock_repo.update_record.return_value = mock_record
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(
            content="# Updated style",
            revision=compute_revision("# Updated"),
        )

        # Act
        result = output_style_service.update_document(
            workspace_id, scope, file_name, payload
        )

        # Assert
        assert result is not None
        assert result.revision == compute_revision("# Updated")
        assert mock_repo.update_record.called

    def test_update_document_rejects_stale_document_revision(
        self, output_style_service
    ):
        """Test updating with stale document revision."""
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"
        mock_repo = MagicMock()
        mock_repo.get_record.return_value = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Current",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        output_style_service._repository = mock_repo
        payload = OutputStyleUpdateRequest(content="# Updated style", revision="stale")

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.update_document(
                workspace_id, scope, file_name, payload
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repo.update_record.assert_not_called()


class TestDeleteDocument:
    """Test deleting output style document."""

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_delete_document_success(self, mock_repo_class, output_style_service):
        """Test successfully deleting document."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
        mock_repo.get_record.return_value = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Test",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        mock_repo.delete_record.return_value = None
        mock_repo.list_records.return_value = []
        output_style_service._repository = mock_repo

        # Act
        result = output_style_service.delete_document(
            workspace_id,
            scope,
            file_name,
            revision=compute_revision("# Test"),
        )

        # Assert
        assert isinstance(result, OutputStyleDeleteResponse)
        assert result.revision == compute_revision("{}")
        assert result.deleted is True
        assert mock_repo.delete_record.called

    def test_delete_document_rejects_stale_document_revision(
        self, output_style_service
    ):
        """Test deleting with stale document revision."""
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"
        mock_repo = MagicMock()
        mock_repo.get_record.return_value = MarkdownDocumentRecord(
            file_path=Path("/test/path/test.md"),
            root_path=Path("/test/path"),
            scope=scope,
            content="# Test",
            metadata={},
            size_bytes=10,
            updated_at=None,
        )
        output_style_service._repository = mock_repo

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.delete_document(
                workspace_id, scope, file_name, revision="stale"
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repo.delete_record.assert_not_called()


class TestDefaultSelectionHelpers:
    """Test output style default selection helper."""

    @patch("app.modules.claude_code.output_styles.catalog.write_json_file")
    @patch("app.modules.claude_code.output_styles.catalog.read_json_file")
    def test_ensure_default_selection_sets_full_file_name(
        self, mock_read_json_file, mock_write_json_file, output_style_service, tmp_path
    ):
        """When outputStyle not yet set in settings, should write full filename."""
        settings_path = tmp_path / "settings.local.json"
        mock_read_json_file.return_value = {}

        with patch.object(
            output_style_service, "_settings_file", return_value=settings_path
        ):
            output_style_service._ensure_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        mock_write_json_file.assert_called_once_with(
            settings_path, {"outputStyle": "Learning.md"}
        )

    @patch("app.modules.claude_code.output_styles.catalog.write_json_file")
    @patch("app.modules.claude_code.output_styles.catalog.read_json_file")
    def test_ensure_default_selection_keeps_existing_selection(
        self, mock_read_json_file, mock_write_json_file, output_style_service, tmp_path
    ):
        """When outputStyle already exists, should not overwrite."""
        settings_path = tmp_path / "settings.local.json"
        mock_read_json_file.return_value = {"outputStyle": "Existing.md"}

        with patch.object(
            output_style_service, "_settings_file", return_value=settings_path
        ):
            output_style_service._ensure_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        mock_write_json_file.assert_not_called()

    @patch("app.modules.claude_code.output_styles.catalog.read_json_file")
    def test_clear_default_selection_deletes_empty_settings_file(
        self, mock_read_json_file, output_style_service, tmp_path
    ):
        """When deleting last outputStyle, should remove empty settings file."""
        settings_path = tmp_path / "settings.local.json"
        settings_path.write_text("{}")
        mock_read_json_file.return_value = {"outputStyle": "Learning.md"}

        with patch.object(
            output_style_service, "_settings_file", return_value=settings_path
        ):
            output_style_service._clear_default_selection(
                "workspace-1", DocumentScope.LOCAL, "Learning.md"
            )

        assert not settings_path.exists()


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = OutputStyleService()

        # Assert
        assert service is not None
        assert service._repository is not None


class TestGetDocument:
    """Test getting document."""

    @patch("app.modules.claude_code.output_styles.catalog.ScopedMarkdownRepository")
    def test_get_document_success(self, mock_repo_class, output_style_service):
        """Test successfully getting document."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "test.md"

        mock_repo = MagicMock()
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
        assert result.revision == compute_revision("# Test")
        assert result.document.content == "# Test"
        mock_repo.get_record.assert_called_once()

    def test_get_document_not_found(self, output_style_service):
        """Test getting non-existent document."""
        # Arrange
        from app.modules.claude_code.documents import DocumentNotFoundError

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
        """Test getting ambiguous document."""
        # Arrange
        from app.modules.claude_code.documents import AmbiguousDocumentError

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
    """Test updating document error handling."""

    def test_update_document_ambiguous(self, output_style_service):
        """Test updating ambiguous document."""
        # Arrange
        from app.modules.claude_code.documents import AmbiguousDocumentError

        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "ambiguous.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = AmbiguousDocumentError("Ambiguous")
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated", revision="revision")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.update_document(
                workspace_id, scope, file_name, payload
            )

        assert exc_info.value.status_code == 409

    def test_update_document_not_found_error(self, output_style_service):
        """Test updating non-existent document."""
        # Arrange
        from app.modules.claude_code.documents import DocumentNotFoundError

        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "missing.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = DocumentNotFoundError("Not found")
        output_style_service._repository = mock_repo

        payload = OutputStyleUpdateRequest(content="# Updated", revision="revision")

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.update_document(
                workspace_id, scope, file_name, payload
            )

        assert exc_info.value.status_code == 404


class TestDeleteDocumentErrors:
    """Test deleting document error handling."""

    def test_delete_document_ambiguous(self, output_style_service):
        """Test deleting ambiguous document."""
        # Arrange
        from app.modules.claude_code.documents import AmbiguousDocumentError

        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "ambiguous.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = AmbiguousDocumentError("Ambiguous")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.delete_document(
                workspace_id, scope, file_name, revision="revision"
            )

        assert exc_info.value.status_code == 409

    def test_delete_document_not_found_error(self, output_style_service):
        """Test deleting non-existent document."""
        # Arrange
        from app.modules.claude_code.documents import DocumentNotFoundError

        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        file_name = "missing.md"

        mock_repo = MagicMock()
        mock_repo.get_record.side_effect = DocumentNotFoundError("Not found")
        output_style_service._repository = mock_repo

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.delete_document(
                workspace_id, scope, file_name, revision="revision"
            )

        assert exc_info.value.status_code == 404


class TestCreateDocumentError:
    """Test creating document error handling."""

    def test_create_document_duplicate(self, output_style_service):
        """Test creating duplicate document."""
        # Arrange
        from app.modules.claude_code.documents import DuplicateDocumentError

        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT

        mock_repo = MagicMock()
        mock_repo.list_records.return_value = []
        mock_repo.create_record.side_effect = DuplicateDocumentError("Duplicate")
        output_style_service._repository = mock_repo

        payload = OutputStyleCreateRequest(
            file_name="existing.md",
            content="# Content",
            description="Test",
            revision=compute_revision("{}"),
        )

        # Act & Assert
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            output_style_service.create_document(workspace_id, scope, payload)

        assert exc_info.value.status_code == 409
