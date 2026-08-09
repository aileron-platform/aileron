"""CLI Instruction File Service unit tests"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.core.revision import compute_revision
from app.modules.cli_settings.agents_md.models import (
    AgentsMdDocument,
    AgentsMdScope,
    AgentsMdUpdateRequest,
)
from app.modules.cli_settings.agents_md.documents import (
    AgentsMdService,
    AgentsMdTool,
    AgentsMdToolConfig,
    get_agents_md_config,
)


class TestAgentsMdToolConfig:
    """Test tool configuration correctness"""

    def test_codex_config(self):
        config = get_agents_md_config(AgentsMdTool.CODEX)
        assert config.file_name == "AGENTS.md"
        assert config.endpoint_name == "agents-md"
        assert config.user_root == Path.home() / ".codex"

    def test_opencode_config(self):
        config = get_agents_md_config(AgentsMdTool.OPENCODE)
        assert config.file_name == "AGENTS.md"
        assert config.endpoint_name == "agents-md"
        assert config.user_root == Path.home() / ".config" / "opencode"

    def test_unsupported_tool_raises(self):
        with pytest.raises(ValueError, match="Unsupported tool"):
            get_agents_md_config("nonexistent")


class TestAgentsMdService:
    """Test AgentsMdService"""

    @pytest.fixture(
        params=[
            AgentsMdTool.CODEX,
            AgentsMdTool.OPENCODE,
        ]
    )
    def tool(self, request):
        return request.param

    @pytest.fixture
    def config(self, tool):
        return get_agents_md_config(tool)

    @pytest.fixture
    def service(self, config):
        return AgentsMdService(config)

    @pytest.fixture
    def workspace_id(self):
        return "test-workspace-123"

    # ---- get_document ----

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_get_document_project_scope(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        doc_file = tmp_path / config.file_name
        content = f"# {config.file_name} project content"
        doc_file.write_text(content, encoding="utf-8")

        result = service.get_document(workspace_id, AgentsMdScope.PROJECT)

        assert isinstance(result, AgentsMdDocument)
        assert result.workspace_id == workspace_id
        assert result.scope == AgentsMdScope.PROJECT
        assert result.content == content
        assert result.revision == compute_revision(content)

    def test_get_document_user_scope(self, service, config, workspace_id, tmp_path):
        # Use a service with custom user_root
        custom_config = AgentsMdToolConfig(
            tool=config.tool,
            file_name=config.file_name,
            user_root=tmp_path,
            endpoint_name=config.endpoint_name,
        )
        svc = AgentsMdService(custom_config)
        doc_file = tmp_path / config.file_name
        content = f"# {config.file_name} user content"
        doc_file.write_text(content, encoding="utf-8")

        result = svc.get_document(workspace_id, AgentsMdScope.USER)

        assert result.scope == AgentsMdScope.USER
        assert result.content == content
        assert result.revision == compute_revision(content)

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_get_document_missing_returns_empty(
        self, mock_ws_path, service, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)

        result = service.get_document(workspace_id, AgentsMdScope.PROJECT)

        assert result.content == ""
        assert result.revision == compute_revision("")

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_update_document_creates_missing_file_with_empty_revision(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        # Revision returned for a missing document is the empty-content revision.
        empty_revision = service.get_document(
            workspace_id, AgentsMdScope.PROJECT
        ).revision

        new_content = f"# Created {config.file_name}"
        service.update_document(
            workspace_id,
            AgentsMdUpdateRequest(
                scope=AgentsMdScope.PROJECT,
                content=new_content,
                revision=empty_revision,
            ),
        )

        doc_file = tmp_path / config.file_name
        assert doc_file.read_text(encoding="utf-8") == new_content

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_get_document_utf8(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        doc_file = tmp_path / config.file_name
        content = "# Test Heading\n\nContent with multi-byte emojis 🎉"
        doc_file.write_text(content, encoding="utf-8")

        result = service.get_document(workspace_id, AgentsMdScope.PROJECT)
        assert result.content == content

    # ---- update_document ----

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_update_document_project_scope(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        new_content = f"# Updated {config.file_name}"
        current_content = "# Current"
        (tmp_path / config.file_name).write_text(current_content, encoding="utf-8")
        request = AgentsMdUpdateRequest(
            scope=AgentsMdScope.PROJECT,
            content=new_content,
            revision=compute_revision(current_content),
        )

        result = service.update_document(workspace_id, request)

        assert result.workspace_id == workspace_id
        assert result.scope == AgentsMdScope.PROJECT
        assert result.revision == compute_revision(new_content)
        written = (tmp_path / config.file_name).read_text(encoding="utf-8")
        assert written == new_content

    def test_update_document_creates_directory(self, config, workspace_id, tmp_path):
        nested = tmp_path / "nested" / "dir"
        custom_config = AgentsMdToolConfig(
            tool=config.tool,
            file_name=config.file_name,
            user_root=nested,
            endpoint_name=config.endpoint_name,
        )
        svc = AgentsMdService(custom_config)
        request = AgentsMdUpdateRequest(
            scope=AgentsMdScope.USER,
            content="# New",
            revision=compute_revision(""),
        )

        svc.update_document(workspace_id, request)

        assert (nested / config.file_name).exists()

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_update_document_rejects_stale_revision(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        doc_file = tmp_path / config.file_name
        doc_file.write_text("# Current", encoding="utf-8")
        request = AgentsMdUpdateRequest(
            scope=AgentsMdScope.PROJECT,
            content="# Updated",
            revision=compute_revision("# Stale"),
        )

        with pytest.raises(HTTPException) as exc_info:
            service.update_document(workspace_id, request)

        assert exc_info.value.status_code == status.HTTP_409_CONFLICT
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        assert doc_file.read_text(encoding="utf-8") == "# Current"

    def test_update_request_requires_revision(self):
        with pytest.raises(ValidationError):
            AgentsMdUpdateRequest(
                scope=AgentsMdScope.PROJECT, content="# Missing revision"
            )

    # ---- _resolve_path ----

    @patch("app.modules.cli_settings.agents_md.documents.get_workspace_path")
    def test_resolve_path_project(
        self, mock_ws_path, service, config, workspace_id, tmp_path
    ):
        mock_ws_path.return_value = str(tmp_path)
        result = service._resolve_path(workspace_id, AgentsMdScope.PROJECT)
        assert result == tmp_path / config.file_name

    def test_resolve_path_user(self, service, config, workspace_id):
        result = service._resolve_path(workspace_id, AgentsMdScope.USER)
        assert result == config.user_root / config.file_name

    def test_resolve_path_unsupported_scope(self, service, workspace_id):
        with pytest.raises(HTTPException) as exc_info:
            service._resolve_path(workspace_id, "unsupported")
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
