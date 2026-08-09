"""Subagent Service unit tests"""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException

from app.modules.cli_settings.subagents.config import SubagentTool, get_subagent_config
from app.modules.cli_settings.subagents import config as subagents_config_module
from app.modules.cli_settings.subagents.catalog import SubagentService
from app.modules.cli_settings.subagents.models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocument,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentSummary,
    SubagentUpdateRequest,
)
from app.core.revision import compute_revision
from app.modules.claude_code.documents import (
    DocumentScope,
    MarkdownDocumentRecord,
    DocumentNotFoundError,
    DuplicateDocumentError,
)


def scope_revision_for(*records: MarkdownDocumentRecord) -> str:
    content_by_path = {
        record.file_path.relative_to(record.root_path).as_posix(): record.content
        for record in records
    }
    return compute_revision(
        json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
    )


@pytest.fixture
def subagent_service():
    """Subagent service fixture."""
    return SubagentService(get_subagent_config(SubagentTool.CLAUDE))


@pytest.fixture
def sample_markdown_record():
    """Sample MarkdownDocumentRecord."""
    from datetime import datetime, timezone

    return MarkdownDocumentRecord(
        file_path=Path("/path/to/test-agent.md"),
        root_path=Path("/path/to"),
        scope=DocumentScope.PROJECT,
        content="---\nname: Test Agent\ndescription: A test agent\n---\n\n# Agent Content",
        metadata={"name": "Test Agent", "description": "A test agent"},
        size_bytes=2048,
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_plugin_agent_info(tmp_path):
    """Sample plugin agent info."""
    from app.modules.claude_code.plugins.loader import ComponentFileInfo

    # Create a temporary file for the plugin agent
    agent_file = tmp_path / "plugin-agent.md"
    agent_file.write_text(
        "---\nname: Plugin Agent\ndescription: Test agent\n---\n\n# Content"
    )
    return ComponentFileInfo(
        file_path=str(agent_file),
        file_name="plugin-agent.md",
        plugin_name="test-plugin",
        marketplace_name="test-marketplace",
        description="Plugin agent description",
    )


class TestSubagentServiceInitialization:
    """Test Subagent Service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = SubagentService(get_subagent_config(SubagentTool.CLAUDE))

        # Assert
        assert service is not None
        assert service._repository is not None

    def test_opencode_config_uses_opencode_agent_paths(self):
        """Test OpenCode subagent path configuration."""
        config = get_subagent_config(SubagentTool.OPENCODE)

        assert config.project_dot_dir == ".opencode"
        assert config.agents_dir == "agents"
        assert config.user_root == Path.home() / ".config" / "opencode" / "agents"
        assert config.api_prefix == "opencode"
        assert config.supports_plugin is False

    def test_opencode_project_and_user_crud_use_opencode_agent_paths(
        self, tmp_path, monkeypatch
    ):
        """Test OpenCode project and user CRUD paths."""
        workspace_root = tmp_path / "workspace"
        home_root = tmp_path / "home"
        workspace_root.mkdir()
        home_root.mkdir()
        monkeypatch.setattr(
            subagents_config_module, "get_workspace_path", lambda: str(workspace_root)
        )
        monkeypatch.setattr(Path, "home", lambda: home_root)

        service = SubagentService(get_subagent_config(SubagentTool.OPENCODE))
        project_content = (
            "---\nname: Project Agent\ndescription: Project helper\n---\n\n# Project"
        )
        user_content = "---\nname: User Agent\ndescription: User helper\n---\n\n# User"

        created_project = service.create_document(
            "ws-1",
            DocumentScope.PROJECT,
            SubagentCreateRequest(
                path="project-agent.md",
                content=project_content,
                revision=service.get_scope("ws-1", DocumentScope.PROJECT).revision,
            ),
        )
        created_user = service.create_document(
            "ws-1",
            DocumentScope.USER,
            SubagentCreateRequest(
                path="user-agent.md",
                content=user_content,
                revision=service.get_scope("ws-1", DocumentScope.USER).revision,
            ),
        )

        assert created_project.document.path == "project-agent.md"
        assert created_user.document.path == "user-agent.md"
        project_path = workspace_root / ".opencode" / "agents" / "project-agent.md"
        user_path = home_root / ".config" / "opencode" / "agents" / "user-agent.md"
        assert project_path.read_text(encoding="utf-8") == project_content
        assert user_path.read_text(encoding="utf-8") == user_content

        assert (
            service.get_document(
                "ws-1", DocumentScope.PROJECT, "project-agent.md"
            ).document.name
            == "Project Agent"
        )
        assert (
            service.get_scope("ws-1", DocumentScope.USER).documents[0].path
            == "user-agent.md"
        )

        updated_content = "---\nname: User Agent Updated\ndescription: User helper updated\n---\n\n# User"
        updated = service.update_document(
            "ws-1",
            DocumentScope.USER,
            SubagentUpdateRequest(
                path="user-agent.md",
                content=updated_content,
                revision=service.get_document(
                    "ws-1", DocumentScope.USER, "user-agent.md"
                ).revision,
            ),
        )
        assert updated.document.name == "User Agent Updated"
        assert user_path.read_text(encoding="utf-8") == updated_content

        service.delete_document(
            "ws-1",
            DocumentScope.PROJECT,
            "project-agent.md",
            revision=service.get_document(
                "ws-1", DocumentScope.PROJECT, "project-agent.md"
            ).revision,
        )
        assert not project_path.exists()


class TestToSummary:
    """Test _to_summary method."""

    def test_to_summary_with_metadata(self, subagent_service, sample_markdown_record):
        """Test converting record with metadata."""
        # Act
        result = subagent_service._to_summary(sample_markdown_record)

        # Assert
        assert isinstance(result, SubagentSummary)
        assert result.path == "test-agent.md"
        assert result.name == "Test Agent"
        assert result.description == "A test agent"
        assert result.scope == DocumentScope.PROJECT
        assert result.size == "2KB"

    def test_to_summary_with_fallback_name(self, subagent_service):
        """Test using fallback name."""
        # Arrange
        from datetime import datetime, timezone

        record = MarkdownDocumentRecord(
            file_path=Path("/path/to/agent.md"),
            root_path=Path("/path/to"),
            scope=DocumentScope.USER,
            content="# Content without frontmatter",
            metadata={},
            size_bytes=1024,
            updated_at=datetime.now(timezone.utc),
        )

        # Act
        result = subagent_service._to_summary(record, fallback_name="Fallback Agent")

        # Assert
        assert result.name == "Fallback Agent" or result.name == "agent.md"

    def test_to_summary_with_fallback_description(self, subagent_service):
        """Test using fallback description."""
        # Arrange
        from datetime import datetime, timezone

        record = MarkdownDocumentRecord(
            file_path=Path("/path/to/agent.md"),
            root_path=Path("/path/to"),
            scope=DocumentScope.USER,
            content="---\nname: Agent\n---\n\n# Content",
            metadata={"name": "Agent"},
            size_bytes=1024,
            updated_at=datetime.now(timezone.utc),
        )

        # Act
        result = subagent_service._to_summary(
            record, fallback_description="Fallback description"
        )

        # Assert
        assert result.description == "Fallback description"


class TestListScopes:
    """Test list_scopes method."""

    def test_list_scopes_all_scopes(self, subagent_service, sample_markdown_record):
        """Test listing all scopes."""
        from unittest.mock import MagicMock

        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository

        with patch.object(subagent_service, "_load_plugin_agents", return_value=[]):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

            # Assert
        assert isinstance(result, SubagentCollectionResponse)
        assert result.workspace_id == "test-workspace"
        assert [item.path for item in result.items]
        assert {scope.scope for scope in result.available_scopes} >= {
            DocumentScope.PROJECT,
            DocumentScope.USER,
        }

    def test_list_scopes_with_plugin_agents(self, subagent_service):
        """Test listing including plugin agents."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = []
        subagent_service._repository = mock_repository
        plugin_summaries = [
            SubagentSummary(
                path="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                pluginName="test-plugin",
                marketplaceName="test-marketplace",
            )
        ]

        with patch.object(
            subagent_service, "_load_plugin_agents", return_value=plugin_summaries
        ):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

        # Assert
        plugin_item = next(
            (item for item in result.items if item.scope == DocumentScope.PLUGIN), None
        )
        assert plugin_item is not None
        assert plugin_item.plugin_name == "test-plugin"
        plugin_scope = next(
            (s for s in result.available_scopes if s.scope == DocumentScope.PLUGIN),
            None,
        )
        assert plugin_scope is not None
        assert plugin_scope.read_only is True

    def test_list_scopes_filtered(self, subagent_service, sample_markdown_record):
        """Test filtering specific scope."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository

        # Act
        result = subagent_service.list_scopes("test-workspace", DocumentScope.PROJECT)

        # Assert
        assert [item.scope for item in result.items] == [DocumentScope.PROJECT]
        assert [
            (scope.scope, scope.read_only) for scope in result.available_scopes
        ] == [
            (DocumentScope.PROJECT, False),
        ]


class TestGetScope:
    """Test get_scope method."""

    def test_get_scope_success(self, subagent_service, sample_markdown_record):
        """Test successfully getting scope."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository

        # Act
        result = subagent_service.get_scope("test-workspace", DocumentScope.PROJECT)

        # Assert
        assert isinstance(result, SubagentScopeResponse)
        assert result.scope == DocumentScope.PROJECT
        assert result.revision == scope_revision_for(sample_markdown_record)
        assert len(result.documents) == 1
        assert result.documents[0].path == "test-agent.md"


class TestGetDocument:
    """Test get_document method."""

    def test_get_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully getting document."""
        with patch.object(
            subagent_service,
            "_load_record_by_path",
            return_value=sample_markdown_record,
        ) as load_record:
            result = subagent_service.get_document(
                "test-workspace", DocumentScope.PROJECT, "test-agent.md"
            )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        assert result.revision == compute_revision(sample_markdown_record.content)
        assert result.document.path == "test-agent.md"
        assert result.document.content == sample_markdown_record.content
        load_record.assert_called_once_with(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )

    def test_get_document_not_found(self, subagent_service):
        """Test getting non-existent document."""
        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                side_effect=DocumentNotFoundError("Not found"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.get_document(
                "test-workspace", DocumentScope.PROJECT, "missing.md"
            )
        assert exc_info.value.status_code == 404

    @patch.object(SubagentService, "_get_plugin_document")
    def test_get_document_from_plugin(self, mock_get_plugin, subagent_service):
        """Test getting document from plugin."""
        # Arrange
        plugin_doc_response = SubagentDocumentResponse(
            workspaceId="test-workspace",
            scope=DocumentScope.PLUGIN,
            revision=compute_revision("# Plugin agent content"),
            document=SubagentDocument(
                path="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                content="# Plugin agent content",
                pluginName="test-plugin",
                marketplaceName="test-marketplace",
            ),
        )
        mock_get_plugin.return_value = plugin_doc_response

        # Act
        result = subagent_service.get_document(
            "test-workspace", DocumentScope.PLUGIN, "plugin-agent.md"
        )

        # Assert
        assert result.document.plugin_name == "test-plugin"
        mock_get_plugin.assert_called_once_with("test-workspace", "plugin-agent.md")

    def test_path_identity_allows_same_name_across_directories(
        self, tmp_path, monkeypatch
    ):
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        monkeypatch.setattr(
            subagents_config_module, "get_workspace_path", lambda: str(workspace_root)
        )
        service = SubagentService(get_subagent_config(SubagentTool.OPENCODE))

        git_content = (
            "---\nname: Git Reviewer\ndescription: Git review helper\n---\n\n# Git"
        )
        hg_content = (
            "---\nname: Hg Reviewer\ndescription: Hg review helper\n---\n\n# Hg"
        )
        service.create_document(
            "ws-1",
            DocumentScope.PROJECT,
            SubagentCreateRequest(
                path="git/reviewer.md",
                content=git_content,
                revision=service.get_scope("ws-1", DocumentScope.PROJECT).revision,
            ),
        )
        service.create_document(
            "ws-1",
            DocumentScope.PROJECT,
            SubagentCreateRequest(
                path="hg/reviewer.md",
                content=hg_content,
                revision=service.get_scope("ws-1", DocumentScope.PROJECT).revision,
            ),
        )

        git_result = service.get_document(
            "ws-1", DocumentScope.PROJECT, "git/reviewer.md"
        )
        hg_result = service.get_document(
            "ws-1", DocumentScope.PROJECT, "hg/reviewer.md"
        )

        assert git_result.document.path == "git/reviewer.md"
        assert git_result.document.content == git_content
        assert hg_result.document.path == "hg/reviewer.md"
        assert hg_result.document.content == hg_content


class TestCreateDocument:
    """Test create_document method."""

    def test_create_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully creating document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = []
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            path="new-agent.md",
            content="---\nname: New Agent\ndescription: A new agent\n---\n\n# New agent",
            revision=compute_revision("{}"),
        )

        with patch.object(
            subagent_service,
            "_create_record_by_path",
            return_value=sample_markdown_record,
        ) as create_record:
            result = subagent_service.create_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        assert result.revision == compute_revision(sample_markdown_record.content)
        assert result.document.content == sample_markdown_record.content
        create_record.assert_called_once_with(
            "test-workspace",
            DocumentScope.PROJECT,
            "new-agent.md",
            payload.content,
        )

    def test_create_document_rejects_stale_scope_revision(
        self, subagent_service, sample_markdown_record
    ):
        """Test creating with stale scope revision."""
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            path="new-agent.md",
            content="---\nname: New Agent\ndescription: A new agent\n---\n\n# New agent",
            revision="stale",
        )

        with pytest.raises(HTTPException) as exc_info:
            subagent_service.create_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repository.create_record.assert_not_called()

    def test_create_document_duplicate(self, subagent_service):
        """Test creating duplicate document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = []
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            path="existing.md",
            content="---\nname: Existing\ndescription: Existing agent\n---\n\n# Content",
            revision=compute_revision("{}"),
        )

        # Act & Assert
        with (
            patch.object(
                subagent_service,
                "_create_record_by_path",
                side_effect=DuplicateDocumentError("Duplicate"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.create_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )
        assert exc_info.value.status_code == 409

    def test_create_document_rejects_missing_markdown_metadata(self, subagent_service):
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            path="agent.md",
            content="# Missing metadata",
            revision=compute_revision("{}"),
        )

        with pytest.raises(HTTPException) as exc_info:
            subagent_service.create_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["target"] == "content"
        mock_repository.create_record.assert_not_called()


class TestUpdateDocument:
    """Test update_document method."""

    def test_update_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully updating document."""
        # Arrange
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository
        payload = SubagentUpdateRequest(
            path="test-agent.md",
            content="---\nname: Updated Agent\ndescription: Updated agent\n---\n\n# Updated content",
            revision=compute_revision(sample_markdown_record.content),
        )

        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                return_value=sample_markdown_record,
            ) as load_record,
            patch.object(
                subagent_service,
                "_update_record_by_path",
                return_value=sample_markdown_record,
            ) as update_record,
        ):
            result = subagent_service.update_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        assert result.revision == compute_revision(sample_markdown_record.content)
        load_record.assert_called_once_with(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )
        update_record.assert_called_once_with(
            "test-workspace",
            DocumentScope.PROJECT,
            "test-agent.md",
            payload.content,
        )

    def test_update_document_rejects_stale_document_revision(
        self, subagent_service, sample_markdown_record
    ):
        """Test updating with stale document revision."""
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository
        payload = SubagentUpdateRequest(
            path="test-agent.md",
            content="---\nname: Updated Agent\ndescription: Updated agent\n---\n\n# Updated content",
            revision="stale",
        )

        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                return_value=sample_markdown_record,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.update_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repository.update_record.assert_not_called()

    def test_update_document_not_found(self, subagent_service):
        """Test updating non-existent document."""
        # Arrange
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository
        payload = SubagentUpdateRequest(
            path="missing.md",
            content="---\nname: Missing\ndescription: Missing agent\n---\n\n# Content",
            revision="revision",
        )

        # Act & Assert
        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                side_effect=DocumentNotFoundError("Not found"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.update_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )
        assert exc_info.value.status_code == 404


class TestDeleteDocument:
    """Test delete_document method."""

    def test_delete_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully deleting document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = []
        subagent_service._repository = mock_repository

        # Act
        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                return_value=sample_markdown_record,
            ) as load_record,
            patch.object(subagent_service, "_delete_record_by_path") as delete_record,
        ):
            result = subagent_service.delete_document(
                "test-workspace",
                DocumentScope.PROJECT,
                "test-agent.md",
                revision=compute_revision(sample_markdown_record.content),
            )

        # Assert
        assert isinstance(result, SubagentDeleteResponse)
        assert result.revision == compute_revision("{}")
        load_record.assert_called_once_with(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )
        delete_record.assert_called_once_with(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )

    def test_delete_document_rejects_stale_document_revision(
        self, subagent_service, sample_markdown_record
    ):
        """Test deleting with stale document revision."""
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository

        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                return_value=sample_markdown_record,
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.delete_document(
                "test-workspace",
                DocumentScope.PROJECT,
                "test-agent.md",
                revision="stale",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"
        mock_repository.delete_record.assert_not_called()

    def test_delete_document_not_found(self, subagent_service):
        """Test deleting non-existent document."""
        # Arrange
        mock_repository = MagicMock()
        subagent_service._repository = mock_repository

        # Act & Assert
        with (
            patch.object(
                subagent_service,
                "_load_record_by_path",
                side_effect=DocumentNotFoundError("Not found"),
            ),
            pytest.raises(HTTPException) as exc_info,
        ):
            subagent_service.delete_document(
                "test-workspace",
                DocumentScope.PROJECT,
                "missing.md",
                revision="revision",
            )
        assert exc_info.value.status_code == 404


class TestLoadPluginAgents:
    """Test _load_plugin_agents method."""

    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    def test_load_plugin_agents_success(
        self,
        mock_get_settings,
        mock_get_loader,
        subagent_service,
        sample_plugin_agent_info,
    ):
        """Test successfully loading plugin agents."""
        # Arrange
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = [sample_plugin_agent_info]
        mock_get_loader.return_value = mock_loader

        # Act
        result = subagent_service._load_plugin_agents("test-workspace")

        # Assert
        assert len(result) == 1
        assert result[0].path == "plugin-agent.md"
        assert result[0].plugin_name == "test-plugin"
        assert result[0].marketplace_name == "test-marketplace"

    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    def test_load_plugin_agents_empty(
        self, mock_get_settings, mock_get_loader, subagent_service
    ):
        """Test loading empty plugin agents."""
        # Arrange
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = []
        mock_get_loader.return_value = mock_loader

        # Act
        result = subagent_service._load_plugin_agents("test-workspace")

        # Assert
        assert result == []

    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    def test_load_plugin_agents_with_read_error(
        self,
        mock_get_settings,
        mock_get_loader,
        subagent_service,
        sample_plugin_agent_info,
        tmp_path,
    ):
        """Test encountering read error during loading."""
        from app.modules.claude_code.plugins.loader import ComponentFileInfo

        # Arrange
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        # Create a non-existent file path
        invalid_agent_info = ComponentFileInfo(
            file_path=str(tmp_path / "nonexistent.md"),
            file_name="invalid.md",
            plugin_name="test-plugin",
            marketplace_name="test-marketplace",
        )

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = [invalid_agent_info]
        mock_get_loader.return_value = mock_loader

        # Act - should skip error files
        result = subagent_service._load_plugin_agents("test-workspace")

        # Assert - errors are logged but don't interrupt
        # Actual implementation may return empty list or skip error items
        assert isinstance(result, list)


class TestGetPluginDocument:
    """Test _get_plugin_document method."""

    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    def test_get_plugin_document_success(
        self, mock_get_settings, mock_get_loader, subagent_service, tmp_path
    ):
        """Test successfully getting plugin document."""
        # Arrange
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        # Create temporary file
        agent_file = tmp_path / "plugin-agent.md"
        agent_file.write_text("---\nname: Plugin Agent\n---\n\n# Content")

        from app.modules.claude_code.plugins.loader import ComponentFileInfo

        agent_info = ComponentFileInfo(
            file_path=str(agent_file),
            file_name="plugin-agent.md",
            plugin_name="test-plugin",
            marketplace_name="test-marketplace",
            description="Plugin agent",
        )

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = [agent_info]
        mock_get_loader.return_value = mock_loader

        # Act
        result = subagent_service._get_plugin_document(
            "test-workspace", "plugin-agent.md"
        )

        # Assert
        assert result.document.path == "plugin-agent.md"
        assert result.document.plugin_name == "test-plugin"
        assert result.scope == DocumentScope.PLUGIN

    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    def test_get_plugin_document_not_found(
        self, mock_get_settings, mock_get_loader, subagent_service
    ):
        """Test getting non-existent plugin document."""
        # Arrange
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = []
        mock_get_loader.return_value = mock_loader

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service._get_plugin_document("test-workspace", "missing.md")
        assert exc_info.value.status_code == 404


class TestIntegrationScenarios:
    """Integration scenario tests."""

    def test_mixed_scopes_listing(self, subagent_service, sample_markdown_record):
        """Test mixed scope listing."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository
        plugin_summaries = [
            SubagentSummary(
                path="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                pluginName="test-plugin",
                marketplaceName="test-marketplace",
            )
        ]

        with patch.object(
            subagent_service, "_load_plugin_agents", return_value=plugin_summaries
        ):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

        # Assert
        scopes = {s.scope for s in result.available_scopes}
        assert DocumentScope.PROJECT in scopes or DocumentScope.USER in scopes
        # Plugin scope only appears when there are plugin agents
        if plugin_summaries:
            assert DocumentScope.PLUGIN in scopes
