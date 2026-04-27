"""Slash Command Service tests."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.modules.claude_code.common import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    MarkdownDocumentRecord,
)
from app.modules.claude_code.slash_commands.models import (
    SlashCommandCreateRequest,
    SlashCommandUpdateRequest,
)
from app.modules.claude_code.slash_commands.service import SlashCommandService


@pytest.fixture
def service():
    return SlashCommandService()


@pytest.fixture
def sample_record():
    return MarkdownDocumentRecord(
        file_path="/path/test/test-command.md",
        root_path="/path",
        scope=DocumentScope.PROJECT,
        namespace="test",
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
        assert len(result.scopes) == 1
        assert result.scopes[0].scope == DocumentScope.PROJECT

    def test_get_scope(self, service, sample_record):
        service._repository.list_records = Mock(return_value=[sample_record])

        result = service.get_scope("workspace-1", DocumentScope.PROJECT)

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert len(result.documents) == 1
        assert result.documents[0].file_name == "test-command.md"

    def test_get_document_success(self, service, sample_record):
        service._repository.get_record = Mock(return_value=sample_record)

        result = service.get_document("workspace-1", DocumentScope.PROJECT, "test.md")

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert result.document.file_name == "test-command.md"
        assert result.document.content == "# Test Command"

    def test_create_document_success(self, service, sample_record):
        service._repository.create_record = Mock(return_value=sample_record)

        payload = SlashCommandCreateRequest(
            fileName="new-command.md",
            content="# New Command",
            namespace="test",
        )

        result = service.create_document("workspace-1", DocumentScope.PROJECT, payload)

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PROJECT
        assert result.document.content == "# Test Command"

    def test_update_document_success(self, service, sample_record):
        service._repository.update_record = Mock(return_value=sample_record)

        result = service.update_document(
            "workspace-1",
            DocumentScope.PROJECT,
            "test.md",
            SlashCommandUpdateRequest(content="# Updated Command"),
        )

        assert result.workspace_id == "workspace-1"
        assert result.document.file_name == "test-command.md"

    def test_document_errors(self, service):
        service._repository.get_record = Mock(side_effect=DocumentNotFoundError("Not found"))
        with pytest.raises(HTTPException) as exc_info:
            service.get_document("workspace-1", DocumentScope.PROJECT, "test.md")
        assert exc_info.value.status_code == 404

        service._repository.get_record = Mock(side_effect=AmbiguousDocumentError("Ambiguous"))
        with pytest.raises(HTTPException) as exc_info:
            service.get_document("workspace-1", DocumentScope.PROJECT, "test.md")
        assert exc_info.value.status_code == 409

    def test_create_duplicate_document(self, service):
        service._repository.create_record = Mock(side_effect=DuplicateDocumentError("dup"))

        with pytest.raises(HTTPException) as exc_info:
            service.create_document(
                "workspace-1",
                DocumentScope.PROJECT,
                SlashCommandCreateRequest(fileName="dup.md", content="# Dup"),
            )

        assert exc_info.value.status_code == 409

    def test_delete_document_success(self, service):
        service._repository.delete_record = Mock()

        service.delete_document("workspace-1", DocumentScope.PROJECT, "test.md")

        service._repository.delete_record.assert_called_once()

    def test_load_plugin_commands_success(self, service):
        mock_cmd = MagicMock()
        mock_cmd.file_name = "plugin-cmd.md"
        mock_cmd.file_path = "/tmp/test-plugin-cmd.md"
        mock_cmd.description = "Plugin command"
        mock_cmd.plugin_name = "test-plugin"
        mock_cmd.marketplace_name = "Test Plugin"

        with patch("pathlib.Path.stat") as mock_stat, patch(
            "app.modules.claude_code.plugins.loader.get_plugin_loader"
        ) as mock_get_loader, patch(
            "app.modules.claude_code.settings.dependencies.get_settings_service"
        ):
            mock_stat.return_value.st_size = 100
            mock_loader = MagicMock()
            mock_loader.load_plugin_commands.return_value = [mock_cmd]
            mock_get_loader.return_value = mock_loader

            result = service._load_plugin_commands("workspace-1")

        assert len(result) == 1
        assert result[0].file_name == "plugin-cmd.md"
        assert result[0].plugin_name == "test-plugin"

    def test_get_plugin_document_success(self, service):
        mock_cmd = MagicMock()
        mock_cmd.file_name = "plugin-cmd.md"
        mock_cmd.file_path = "/tmp/test-plugin-cmd.md"
        mock_cmd.description = "Plugin command"
        mock_cmd.plugin_name = "test-plugin"
        mock_cmd.marketplace_name = "Test Plugin"

        with patch("pathlib.Path.read_text", return_value="# Plugin Command"), patch(
            "pathlib.Path.stat"
        ) as mock_stat, patch(
            "app.modules.claude_code.plugins.loader.get_plugin_loader"
        ) as mock_get_loader, patch(
            "app.modules.claude_code.settings.dependencies.get_settings_service"
        ):
            mock_stat.return_value.st_size = 100
            mock_loader = MagicMock()
            mock_loader.load_plugin_commands.return_value = [mock_cmd]
            mock_get_loader.return_value = mock_loader

            result = service._get_plugin_document("workspace-1", "plugin-cmd.md")

        assert result.workspace_id == "workspace-1"
        assert result.scope == DocumentScope.PLUGIN
        assert result.document.file_name == "plugin-cmd.md"

    def test_to_summary(self, service, sample_record):
        result = service._to_summary(sample_record)

        assert result.file_name == "test-command.md"
        assert result.scope == DocumentScope.PROJECT
        assert result.namespace == "test"
