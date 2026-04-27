"""Subagent Service unit tests"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from fastapi import HTTPException

from app.modules.claude_code.subagents.service import SubagentService
from app.modules.claude_code.subagents.models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDocument,
    SubagentDocumentResponse,
    SubagentScopeGroup,
    SubagentScopeResponse,
    SubagentSummary,
    SubagentUpdateRequest,
)
from app.modules.claude_code.common import (
    DocumentScope,
    MarkdownDocumentRecord,
    DocumentNotFoundError,
    AmbiguousDocumentError,
    DuplicateDocumentError,
)


@pytest.fixture
def subagent_service():
    """Subagent service fixture."""
    return SubagentService()


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
        updated_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_plugin_agent_info(tmp_path):
    """Sample plugin agent info."""
    from app.modules.claude_code.plugins.loader import ComponentFileInfo
    # Create a temporary file for the plugin agent
    agent_file = tmp_path / "plugin-agent.md"
    agent_file.write_text("---\nname: Plugin Agent\ndescription: Test agent\n---\n\n# Content")
    return ComponentFileInfo(
        file_path=str(agent_file),
        file_name="plugin-agent.md",
        plugin_name="test-plugin",
        marketplace_name="test-marketplace",
        description="Plugin agent description"
    )


class TestSubagentServiceInitialization:
    """Test Subagent Service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = SubagentService()

        # Assert
        assert service is not None
        assert service._repository is not None


class TestToSummary:
    """Test _to_summary method."""

    def test_to_summary_with_metadata(self, subagent_service, sample_markdown_record):
        """Test converting record with metadata."""
        # Act
        result = subagent_service._to_summary(sample_markdown_record)

        # Assert
        assert isinstance(result, SubagentSummary)
        assert result.file_name == "test-agent.md"
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
            updated_at=datetime.now(timezone.utc)
        )

        # Act
        result = subagent_service._to_summary(
            record,
            fallback_name="Fallback Agent"
        )

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
            updated_at=datetime.now(timezone.utc)
        )

        # Act
        result = subagent_service._to_summary(
            record,
            fallback_description="Fallback description"
        )

        # Assert
        assert result.description == "Fallback description"


class TestListScopes:
    """Test list_scopes method."""

    def test_list_scopes_all_scopes(
        self, subagent_service, sample_markdown_record
    ):
        """Test listing all scopes."""
        from unittest.mock import MagicMock
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository

        with patch.object(subagent_service, '_load_plugin_agents', return_value=[]):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

            # Assert
            assert isinstance(result, SubagentCollectionResponse)
            assert result.workspace_id == "test-workspace"
            assert len(result.scopes) >= 1

    def test_list_scopes_with_plugin_agents(
        self, subagent_service
    ):
        """Test listing including plugin agents."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = []
        subagent_service._repository = mock_repository
        plugin_summaries = [
            SubagentSummary(
                fileName="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                pluginName="test-plugin",
                marketplaceName="test-marketplace"
            )
        ]

        with patch.object(subagent_service, "_load_plugin_agents", return_value=plugin_summaries):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

        # Assert
        plugin_scope = next((s for s in result.scopes if s.scope == DocumentScope.PLUGIN), None)
        assert plugin_scope is not None
        assert len(plugin_scope.documents) == 1
        assert plugin_scope.documents[0].plugin_name == "test-plugin"

    def test_list_scopes_filtered(self, subagent_service, sample_markdown_record):
        """Test filtering specific scope."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.list_records.return_value = [sample_markdown_record]
        subagent_service._repository = mock_repository

        # Act
        result = subagent_service.list_scopes("test-workspace", DocumentScope.PROJECT)

        # Assert
        assert len(result.scopes) == 1
        assert result.scopes[0].scope == DocumentScope.PROJECT


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
        assert len(result.documents) == 1
        assert result.documents[0].file_name == "test-agent.md"


class TestGetDocument:
    """Test get_document method."""

    def test_get_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully getting document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.get_record.return_value = sample_markdown_record
        subagent_service._repository = mock_repository

        # Act
        result = subagent_service.get_document(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        assert result.document.file_name == "test-agent.md"
        assert result.document.content == sample_markdown_record.content

    def test_get_document_not_found(self, subagent_service):
        """Test getting non-existent document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.get_record.side_effect = DocumentNotFoundError("Not found")
        subagent_service._repository = mock_repository

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service.get_document(
                "test-workspace", DocumentScope.PROJECT, "missing.md"
            )
        assert exc_info.value.status_code == 404

    def test_get_document_ambiguous(self, subagent_service):
        """Test getting ambiguous document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.get_record.side_effect = AmbiguousDocumentError("Ambiguous")
        subagent_service._repository = mock_repository

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service.get_document(
                "test-workspace", DocumentScope.PROJECT, "ambiguous.md"
            )
        assert exc_info.value.status_code == 409

    @patch.object(SubagentService, '_get_plugin_document')
    def test_get_document_from_plugin(self, mock_get_plugin, subagent_service):
        """Test getting document from plugin."""
        # Arrange
        plugin_doc_response = SubagentDocumentResponse(
            workspaceId="test-workspace",
            scope=DocumentScope.PLUGIN,
            document=SubagentDocument(
                fileName="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                content="# Plugin agent content",
                pluginName="test-plugin",
                marketplaceName="test-marketplace"
            )
        )
        mock_get_plugin.return_value = plugin_doc_response

        # Act
        result = subagent_service.get_document(
            "test-workspace", DocumentScope.PLUGIN, "plugin-agent.md"
        )

        # Assert
        assert result.document.plugin_name == "test-plugin"
        mock_get_plugin.assert_called_once_with("test-workspace", "plugin-agent.md")


class TestCreateDocument:
    """Test create_document method."""

    def test_create_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully creating document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.create_record.return_value = sample_markdown_record
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            file_name="new-agent.md",
            content="# New agent",
            name="New Agent",
            description="A new agent"
        )

        # Act
        result = subagent_service.create_document(
            "test-workspace", DocumentScope.PROJECT, payload
        )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        assert result.document.content == sample_markdown_record.content

    def test_create_document_duplicate(self, subagent_service):
        """Test creating duplicate document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.create_record.side_effect = DuplicateDocumentError("Duplicate")
        subagent_service._repository = mock_repository
        payload = SubagentCreateRequest(
            file_name="existing.md",
            content="# Content"
        )

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service.create_document(
                "test-workspace", DocumentScope.PROJECT, payload
            )
        assert exc_info.value.status_code == 409


class TestUpdateDocument:
    """Test update_document method."""

    def test_update_document_success(self, subagent_service, sample_markdown_record):
        """Test successfully updating document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.update_record.return_value = sample_markdown_record
        subagent_service._repository = mock_repository
        payload = SubagentUpdateRequest(
            content="# Updated content",
            name="Updated Agent"
        )

        # Act
        result = subagent_service.update_document(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md", payload
        )

        # Assert
        assert isinstance(result, SubagentDocumentResponse)
        mock_repository.update_record.assert_called_once()

    def test_update_document_not_found(self, subagent_service):
        """Test updating non-existent document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.update_record.side_effect = DocumentNotFoundError("Not found")
        subagent_service._repository = mock_repository
        payload = SubagentUpdateRequest(content="# Content")

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service.update_document(
                "test-workspace", DocumentScope.PROJECT, "missing.md", payload
            )
        assert exc_info.value.status_code == 404


class TestDeleteDocument:
    """Test delete_document method."""

    def test_delete_document_success(self, subagent_service):
        """Test successfully deleting document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.delete_record.return_value = None
        subagent_service._repository = mock_repository

        # Act
        subagent_service.delete_document(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )

        # Assert
        mock_repository.delete_record.assert_called_once_with(
            "test-workspace", DocumentScope.PROJECT, "test-agent.md"
        )

    def test_delete_document_not_found(self, subagent_service):
        """Test deleting non-existent document."""
        # Arrange
        mock_repository = MagicMock()
        mock_repository.delete_record.side_effect = DocumentNotFoundError("Not found")
        subagent_service._repository = mock_repository

        # Act & Assert
        with pytest.raises(HTTPException) as exc_info:
            subagent_service.delete_document(
                "test-workspace", DocumentScope.PROJECT, "missing.md"
            )
        assert exc_info.value.status_code == 404


class TestLoadPluginAgents:
    """Test _load_plugin_agents method."""

    @patch('app.modules.claude_code.plugins.loader.get_plugin_loader')
    @patch('app.modules.claude_code.settings.dependencies.get_settings_service')
    def test_load_plugin_agents_success(
        self, mock_get_settings, mock_get_loader, subagent_service, sample_plugin_agent_info
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
        assert result[0].file_name == "plugin-agent.md"
        assert result[0].plugin_name == "test-plugin"
        assert result[0].marketplace_name == "test-marketplace"

    @patch('app.modules.claude_code.plugins.loader.get_plugin_loader')
    @patch('app.modules.claude_code.settings.dependencies.get_settings_service')
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

    @patch('app.modules.claude_code.plugins.loader.get_plugin_loader')
    @patch('app.modules.claude_code.settings.dependencies.get_settings_service')
    def test_load_plugin_agents_with_read_error(
        self, mock_get_settings, mock_get_loader, subagent_service, sample_plugin_agent_info, tmp_path
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
            marketplace_name="test-marketplace"
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

    @patch('app.modules.claude_code.plugins.loader.get_plugin_loader')
    @patch('app.modules.claude_code.settings.dependencies.get_settings_service')
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
            description="Plugin agent"
        )

        mock_loader = Mock()
        mock_loader.load_plugin_agents.return_value = [agent_info]
        mock_get_loader.return_value = mock_loader

        # Act
        result = subagent_service._get_plugin_document("test-workspace", "plugin-agent.md")

        # Assert
        assert result.document.file_name == "plugin-agent.md"
        assert result.document.plugin_name == "test-plugin"
        assert result.scope == DocumentScope.PLUGIN

    @patch('app.modules.claude_code.plugins.loader.get_plugin_loader')
    @patch('app.modules.claude_code.settings.dependencies.get_settings_service')
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
                fileName="plugin-agent.md",
                name="Plugin Agent",
                description="From plugin",
                scope=DocumentScope.PLUGIN,
                size="1KB",
                pluginName="test-plugin",
                marketplaceName="test-marketplace"
            )
        ]

        with patch.object(subagent_service, "_load_plugin_agents", return_value=plugin_summaries):
            # Act
            result = subagent_service.list_scopes("test-workspace", None)

        # Assert
        scopes = {s.scope for s in result.scopes}
        assert DocumentScope.PROJECT in scopes or DocumentScope.USER in scopes
        # Plugin scope only appears when there are plugin agents
        if plugin_summaries:
            assert DocumentScope.PLUGIN in scopes
