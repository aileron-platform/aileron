"""Slash Command Service tests."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.claude_code.documents import (
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    InvalidDocumentFileNameError,
    MarkdownDocumentRecord,
)
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandUpdateRequest,
)
from app.modules.claude_code.slash_commands.catalog import SlashCommandService

EMPTY_REVISION = compute_revision("{}")


@pytest.fixture
def service():
    return SlashCommandService()


@pytest.fixture
def sample_record():
    return MarkdownDocumentRecord(
        file_path="/path/test/test-command.md",
        root_path="/path",
        scope=DocumentScope.PROJECT,
        content="# Test Command",
        size_bytes=100,
        size_label="100 B",
        metadata={"description": "Test command"},
    )


class TestSlashCommandService:
    def test_list_scopes_project(self, service, sample_record):
        service._repository.list_records = Mock(return_value=[sample_record])

        result = service.list_scopes("workspace-1", DocumentScope.PROJECT)

        assert result.workspace_id == "workspace-1"
        assert [item.path for item in result.items] == ["test/test-command.md"]
        assert [
            (scope.scope, scope.read_only) for scope in result.available_scopes
        ] == [
            (DocumentScope.PROJECT, False),
        ]

    def test_get_scope(self, service, sample_record):
        service._repository.list_records = Mock(return_value=[sample_record])

        result = service.get_scope("workspace-1", DocumentScope.PROJECT)

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert result.revision
        assert len(result.documents) == 1
        assert result.documents[0].path == "test/test-command.md"

    def test_get_document_success(self, service, sample_record):
        with patch.object(service, "_load_record_by_path", return_value=sample_record):
            result = service.get_document(
                "workspace-1", DocumentScope.PROJECT, "test.md"
            )

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert result.revision == compute_revision("# Test Command")
        assert result.document.path == "test/test-command.md"
        assert result.document.content == "# Test Command"

    def test_create_document_success(self, service, sample_record):
        service._repository.list_records = Mock(return_value=[])

        payload = SlashCommandCreateRequest(
            path="new-command.md",
            content="# New Command",
            revision=EMPTY_REVISION,
        )

        with patch.object(
            service, "_create_record_by_path", return_value=sample_record
        ):
            result = service.create_document(
                "workspace-1", DocumentScope.PROJECT, payload
            )

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert result.revision == compute_revision("# Test Command")
        assert result.document.content == "# Test Command"

    def test_update_document_success(self, service, sample_record):
        with (
            patch.object(service, "_load_record_by_path", return_value=sample_record),
            patch.object(service, "_update_record_by_path", return_value=sample_record),
        ):
            result = service.update_document(
                "workspace-1",
                DocumentScope.PROJECT,
                SlashCommandUpdateRequest(
                    path="test.md",
                    content="# Updated Command",
                    revision=compute_revision("# Test Command"),
                ),
            )

        assert result.workspace_id == "workspace-1"
        assert result.document.path == "test/test-command.md"

    def test_update_document_rejects_stale_revision(self, service, sample_record):
        with patch.object(service, "_load_record_by_path", return_value=sample_record):
            with pytest.raises(HTTPException) as exc_info:
                service.update_document(
                    "workspace-1",
                    DocumentScope.PROJECT,
                    SlashCommandUpdateRequest(
                        path="test.md",
                        content="# Updated Command",
                        revision=compute_revision("stale"),
                    ),
                )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"

    def test_document_errors(self, service):
        with patch.object(
            service,
            "_load_record_by_path",
            side_effect=DocumentNotFoundError("Not found"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                service.get_document("workspace-1", DocumentScope.PROJECT, "test.md")
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["errorCode"] == "404_NOT_FOUND"

    def test_create_duplicate_document(self, service):
        service._repository.list_records = Mock(return_value=[])

        with patch.object(
            service, "_create_record_by_path", side_effect=DuplicateDocumentError("dup")
        ):
            with pytest.raises(HTTPException) as exc_info:
                service.create_document(
                    "workspace-1",
                    DocumentScope.PROJECT,
                    SlashCommandCreateRequest(
                        path="dup.md",
                        content="# Dup",
                        revision=EMPTY_REVISION,
                    ),
                )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "DUPLICATE_PATH"

    def test_create_invalid_path_uses_error_envelope(self, service):
        service._repository.list_records = Mock(return_value=[])

        with patch.object(
            service,
            "_create_record_by_path",
            side_effect=InvalidDocumentFileNameError("../bad.md"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                service.create_document(
                    "workspace-1",
                    DocumentScope.PROJECT,
                    SlashCommandCreateRequest(
                        path="../bad.md",
                        content="# Bad",
                        revision=EMPTY_REVISION,
                    ),
                )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["errorCode"] == "INVALID_SLASH_COMMAND_PATH"
        assert exc_info.value.detail["message"]

    def test_path_identity_allows_same_name_across_directories(self, service, tmp_path):
        from app.modules.claude_code import documents as documents_module

        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        with patch.object(
            documents_module, "get_workspace_path", return_value=str(workspace_root)
        ):
            git = service.create_document(
                "ws-1",
                DocumentScope.PROJECT,
                SlashCommandCreateRequest(
                    path="git/commit.md",
                    content="# Git commit",
                    revision=service.get_scope("ws-1", DocumentScope.PROJECT).revision,
                ),
            )
            hg = service.create_document(
                "ws-1",
                DocumentScope.PROJECT,
                SlashCommandCreateRequest(
                    path="hg/commit.md",
                    content="# Hg commit",
                    revision=service.get_scope("ws-1", DocumentScope.PROJECT).revision,
                ),
            )

            assert (
                service.get_document(
                    "ws-1", DocumentScope.PROJECT, "git/commit.md"
                ).document.content
                == git.document.content
            )
            assert (
                service.get_document(
                    "ws-1", DocumentScope.PROJECT, "hg/commit.md"
                ).document.content
                == hg.document.content
            )

    def test_delete_document_success(self, service, sample_record):
        service._repository.list_records = Mock(return_value=[])

        with (
            patch.object(service, "_load_record_by_path", return_value=sample_record),
            patch.object(service, "_delete_record_by_path"),
        ):
            result = service.delete_document(
                "workspace-1",
                DocumentScope.PROJECT,
                "test.md",
                compute_revision("# Test Command"),
            )

        assert result.revision == EMPTY_REVISION

    def test_load_plugin_commands_success(self, service):
        mock_cmd = MagicMock()
        mock_cmd.file_name = "plugin-cmd.md"
        mock_cmd.file_path = "/tmp/test-plugin-cmd.md"
        mock_cmd.description = "Plugin command"
        mock_cmd.plugin_name = "test-plugin"
        mock_cmd.marketplace_name = "Test Plugin"

        with (
            patch("pathlib.Path.stat") as mock_stat,
            patch(
                "app.modules.claude_code.plugins.loader.get_plugin_loader"
            ) as mock_get_loader,
            patch("app.modules.claude_code.settings.dependencies.get_settings_service"),
        ):
            mock_stat.return_value.st_size = 100
            mock_loader = MagicMock()
            mock_loader.load_plugin_commands.return_value = [mock_cmd]
            mock_get_loader.return_value = mock_loader

            result = service._load_plugin_commands("workspace-1")

        assert len(result) == 1
        assert result[0].path == "plugin-cmd.md"
        assert result[0].plugin_name == "test-plugin"

    def test_load_plugin_commands_propagates_file_errors_in_strict_mode(self, service):
        mock_cmd = MagicMock()
        mock_cmd.file_path = "/missing/plugin-cmd.md"

        with (
            patch(
                "app.modules.claude_code.plugins.loader.get_plugin_loader"
            ) as mock_get_loader,
            patch("app.modules.claude_code.settings.dependencies.get_settings_service"),
        ):
            mock_loader = MagicMock()
            mock_loader.load_plugin_commands.return_value = [mock_cmd]
            mock_get_loader.return_value = mock_loader

            with pytest.raises(OSError):
                service._load_plugin_commands("workspace-1", strict_errors=True)

    def test_get_plugin_document_success(self, service, tmp_path):
        command_path = tmp_path / "test-plugin-cmd.md"
        command_path.write_text("# Plugin Command", encoding="utf-8")
        mock_cmd = MagicMock()
        mock_cmd.file_name = "plugin-cmd.md"
        mock_cmd.file_path = str(command_path)
        mock_cmd.description = "Plugin command"
        mock_cmd.plugin_name = "test-plugin"
        mock_cmd.marketplace_name = "Test Plugin"

        with (
            patch(
                "app.modules.claude_code.plugins.loader.get_plugin_loader"
            ) as mock_get_loader,
            patch("app.modules.claude_code.settings.dependencies.get_settings_service"),
        ):
            mock_loader = MagicMock()
            mock_loader.load_plugin_commands.return_value = [mock_cmd]
            mock_get_loader.return_value = mock_loader

            result = service._get_plugin_document("workspace-1", "plugin-cmd.md")

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PLUGIN
        assert result.revision == compute_revision("# Plugin Command")
        assert result.document.path == "plugin-cmd.md"

    def test_to_summary(self, service, sample_record):
        result = service._to_summary(sample_record)

        assert result.path == "test/test-command.md"
        assert result.scope == DocumentScope.PROJECT
