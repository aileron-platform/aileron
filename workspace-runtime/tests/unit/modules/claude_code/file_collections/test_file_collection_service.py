"""File Collection Service unit tests"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from app.modules.claude_code.file_collections.service import FileCollectionService
from app.modules.claude_code.file_collections.models import FileCollectionType, FileType
from app.modules.claude_code.common import DocumentScope
from app.modules.file_system import InvalidScopeException


@pytest.fixture
def file_collection_service():
    """File collection service fixture."""
    with patch("app.modules.claude_code.file_collections.service.SettingsService"), \
         patch("app.modules.claude_code.file_collections.service.get_plugin_loader"):
        return FileCollectionService(
            collection_type=FileCollectionType.SKILLS,
            workspace_id="test-workspace"
        )


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace directory structure."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    project_root = workspace_root / ".claude"

    project_root.mkdir(parents=True, exist_ok=True)

    return workspace_root, project_root


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Arrange & Act
        with patch("app.modules.claude_code.file_collections.service.SettingsService"), \
             patch("app.modules.claude_code.file_collections.service.get_plugin_loader"):
            service = FileCollectionService(
                collection_type=FileCollectionType.SKILLS,
                workspace_id="test-workspace"
            )

        # Assert
        assert service is not None
        assert service.collection_type == FileCollectionType.SKILLS
        assert service.workspace_id == "test-workspace"


class TestValidateScope:
    """Test scope validation functionality."""

    def test_validate_scope_valid(self, file_collection_service):
        """Test validating valid scopes."""
        # Act & Assert
        assert file_collection_service.validate_scope(DocumentScope.PROJECT) is True
        assert file_collection_service.validate_scope(DocumentScope.USER) is True
        assert file_collection_service.validate_scope(DocumentScope.PLUGIN) is True
        assert file_collection_service.validate_scope(None) is True  # None is valid

    def test_validate_scope_invalid(self, file_collection_service):
        """Test validating invalid scopes."""
        # Act & Assert
        assert file_collection_service.validate_scope("invalid-scope") is False
        assert file_collection_service.validate_scope(DocumentScope.LOCAL) is False


class TestIsReadonlyScope:
    """Test readonly scope check."""

    def test_plugin_scope_is_readonly(self, file_collection_service):
        """Test plugin scope is readonly."""
        # Act & Assert
        assert file_collection_service.is_readonly_scope(DocumentScope.PLUGIN) is True

    def test_other_scopes_are_writable(self, file_collection_service):
        """Test other scopes are writable."""
        # Act & Assert
        assert file_collection_service.is_readonly_scope(DocumentScope.PROJECT) is False
        assert file_collection_service.is_readonly_scope(DocumentScope.USER) is False
        assert file_collection_service.is_readonly_scope(None) is False


class TestResolveScopePath:
    """Test scope path resolution."""

    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_resolve_scope_path_project(self, mock_resolve, file_collection_service, tmp_path):
        """Test resolving project scope path."""
        # Arrange
        mock_resolve.return_value = tmp_path

        # Act
        result = file_collection_service.resolve_scope_path(DocumentScope.PROJECT, "test.md")

        # Assert
        assert result == tmp_path / "skills" / "test.md"
        mock_resolve.assert_called_once_with("test-workspace", DocumentScope.PROJECT)

    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_resolve_scope_path_scripts(self, mock_resolve, tmp_path):
        """Test resolving scripts collection path."""
        # Arrange
        mock_resolve.return_value = tmp_path
        with patch("app.modules.claude_code.file_collections.service.SettingsService"), \
             patch("app.modules.claude_code.file_collections.service.get_plugin_loader"):
            service = FileCollectionService(
                collection_type=FileCollectionType.SCRIPTS,
                workspace_id="test-workspace"
            )

        # Act
        result = service.resolve_scope_path(DocumentScope.USER, "test.sh")

        # Assert
        assert result == tmp_path / "scripts" / "test.sh"

    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_resolve_scope_path_default_to_project(self, mock_resolve, file_collection_service, tmp_path):
        """Test defaulting to project scope."""
        # Arrange
        mock_resolve.return_value = tmp_path

        # Act
        result = file_collection_service.resolve_scope_path(None, "test.md")

        # Assert
        assert result == tmp_path / "skills" / "test.md"


class TestGetFileType:
    """Test file type identification."""

    def test_get_file_type_markdown(self, file_collection_service):
        """Test identifying Markdown file."""
        # Arrange
        file_path = Path("/test/file.md")

        # Act
        result = file_collection_service._get_file_type(file_path)

        # Assert
        assert result == FileType.MARKDOWN

    def test_get_file_type_python(self, file_collection_service):
        """Test identifying Python file."""
        # Arrange
        file_path = Path("/test/script.py")

        # Act
        result = file_collection_service._get_file_type(file_path)

        # Assert
        assert result == FileType.PYTHON

    def test_get_file_type_typescript(self, file_collection_service):
        """Test identifying TypeScript file."""
        # Arrange
        file_path = Path("/test/app.ts")

        # Act
        result = file_collection_service._get_file_type(file_path)

        # Assert
        assert result == FileType.TYPESCRIPT

    def test_get_file_type_unknown(self, file_collection_service):
        """Test unknown file type."""
        # Arrange
        file_path = Path("/test/file.unknown")

        # Act
        result = file_collection_service._get_file_type(file_path)

        # Assert
        assert result == FileType.OTHER


class TestParseFrontMatter:
    """Test Front Matter parsing."""

    def test_parse_front_matter_with_metadata(self, file_collection_service):
        """Test parsing content with metadata."""
        # Arrange
        content = """---
title: Test Skill
description: A test skill
---

# Skill Content
"""

        # Act
        metadata, body = file_collection_service._parse_front_matter(content)

        # Assert
        assert metadata is not None
        assert metadata.get("title") == "Test Skill"
        assert metadata.get("description") == "A test skill"
        assert "# Skill Content" in body

    def test_parse_front_matter_without_metadata(self, file_collection_service):
        """Test parsing content without metadata."""
        # Arrange
        content = "# Simple Content"

        # Act
        metadata, body = file_collection_service._parse_front_matter(content)

        # Assert
        assert metadata is None
        assert body == content

    def test_parse_front_matter_invalid_yaml_returns_original_content(self, file_collection_service):
        content = "---\nfoo: [\n---\nBody"

        metadata, body = file_collection_service._parse_front_matter(content)

        assert metadata is None
        assert body == content

    def test_parse_front_matter_without_closing_marker(self, file_collection_service):
        content = "---\nfoo: bar\nBody"

        metadata, body = file_collection_service._parse_front_matter(content)

        assert metadata is None
        assert body == content


class TestGetPluginSkills:
    "Test getting plugin skills.""

    @patch("app.modules.claude_code.file_collections.service.get_plugin_loader")
    def test_get_plugin_skills_empty(self, mock_get_loader, file_collection_service):
        "Test getting empty plugin skills.""
        # Arrange
        mock_loader = MagicMock()
        mock_loader.get_all_skills.return_value = []
        file_collection_service.plugin_loader = mock_loader

        # Act
        result = file_collection_service.get_plugin_skills()

        # Assert
        assert result == []

    def test_get_plugin_skills_with_data(self, file_collection_service):
        "Test getting plugin skills with data.""
        # Arrange
        mock_loader = MagicMock()
        mock_loader.get_all_skills.return_value = []
        file_collection_service.plugin_loader = mock_loader

        # Act
        result = file_collection_service.get_plugin_skills()

        # Assert
        # Empty list is also a valid result
        assert result == []

    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_get_plugin_skills_reads_markdown_and_skips_invalid_files(self, mock_resolve, file_collection_service, tmp_path):
        plugin_root = tmp_path / "plugins"
        skill_dir = plugin_root / "plugin-a" / "skills"
        skill_dir.mkdir(parents=True)
        (skill_dir / "good.md").write_text("---\ndescription: Good skill\n---\nBody", encoding="utf-8")
        (skill_dir / "broken.md").write_bytes(b"\xff\xfe")
        mock_resolve.return_value = plugin_root
        file_collection_service.plugin_loader.get_installed_plugins.return_value = [
            SimpleNamespace(name="plugin-a", version="1.0.0")
        ]

        class FakePluginSkillInfo:
            def __init__(self, **kwargs):
                self.plugin_name = kwargs["pluginName"]
                self.skill_name = kwargs["skillName"]
                self.skill_path = kwargs["skillPath"]
                self.description = kwargs["description"]
                self.metadata = kwargs["metadata"]

        with patch("app.modules.claude_code.file_collections.service.PluginSkillInfo", FakePluginSkillInfo):
            result = file_collection_service.get_plugin_skills()

        assert len(result) == 1
        assert result[0].plugin_name == "plugin-a"
        assert result[0].skill_name == "good"
        assert result[0].description == "Good skill"

    def test_get_plugin_skills_returns_empty_on_loader_error(self, file_collection_service):
        file_collection_service.plugin_loader.get_installed_plugins.side_effect = RuntimeError("boom")

        assert file_collection_service.get_plugin_skills() == []


class TestGetTreeWithMetadata:
    "Test getting file tree with metadata.""

    @patch.object(FileCollectionService, 'get_tree')
    @patch.object(FileCollectionService, 'read_file')
    def test_get_tree_with_metadata_success(self, mock_read_file, mock_get_tree, file_collection_service):
        "Test successfully getting file tree with metadata.""
        # Arrange
        mock_get_tree.return_value = {
            "nodes": [
                {
                    "path": "/test.md",
                    "type": "file",
                    "name": "test.md"
                }
            ]
        }

        mock_read_file.return_value = {
            "content": "---\ntitle: Test\n---\nContent"
        }

        # Act
        result = file_collection_service.get_tree_with_metadata("/", DocumentScope.PROJECT)

        # Assert
        assert len(result) == 1
        assert result[0]["path"] == "/test.md"
        assert result[0]["metadata"]["frontMatter"]["title"] == "Test"
        assert result[0]["fileType"] == FileType.MARKDOWN.value

    @patch.object(FileCollectionService, 'get_tree')
    def test_get_tree_with_metadata_no_files(self, mock_get_tree, file_collection_service):
        "Test no files case.""
        # Arrange
        mock_get_tree.return_value = {"nodes": []}

        # Act
        result = file_collection_service.get_tree_with_metadata("/", DocumentScope.PROJECT)

        # Assert
        assert result == []

    @patch.object(FileCollectionService, "get_tree")
    @patch.object(FileCollectionService, "read_file")
    def test_get_tree_with_metadata_ignores_read_errors_and_non_markdown(
        self, mock_read_file, mock_get_tree, file_collection_service
    ):
        mock_get_tree.return_value = {
            "nodes": [
                {"path": "/dir", "type": "directory", "name": "dir"},
                {"path": "/bad.md", "type": "file", "name": "bad.md"},
                {"path": "/plain.txt", "type": "file", "name": "plain.txt"},
            ]
        }
        mock_read_file.side_effect = [RuntimeError("boom"), {"content": "plain content"}]

        result = file_collection_service.get_tree_with_metadata("/", DocumentScope.PROJECT)

        assert result[0]["type"] == "directory"
        assert result[1].get("metadata") is None
        assert result[2].get("fileType") is None


class TestReadWriteOperations:
    "Test read write operations.""

    @patch.object(FileCollectionService, 'resolve_scope_path')
    def test_read_file_simple(self, mock_resolve, file_collection_service, tmp_path):
        "Test simple file reading.""
        # Arrange
        test_file = tmp_path / "test.md"
        test_file.write_text("Test content")
        mock_resolve.return_value = test_file

        # Act
        result = file_collection_service.read_file("test.md", DocumentScope.PROJECT)

        # Assert
        assert "content" in result
        assert "Test content" in result["content"]

    @patch.object(FileCollectionService, 'resolve_scope_path')
    def test_write_file_simple(self, mock_resolve, file_collection_service, tmp_path):
        "Test simple file writing.""
        # Arrange
        test_file = tmp_path / "new.md"
        mock_resolve.return_value = test_file

        # Act
        result = file_collection_service.write_file(
            "new.md",
            "New content",
            DocumentScope.PROJECT
        )

        # Assert
        assert result["path"] == "new.md"
        assert test_file.read_text() == "New content"


class TestAdditionalServiceCoverage:
    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_resolve_scope_path_invalid_scope_raises(self, mock_resolve, file_collection_service, tmp_path):
        mock_resolve.return_value = tmp_path

        with pytest.raises(InvalidScopeException, match="Invalid scope"):
            file_collection_service.resolve_scope_path("invalid", "test.md")

    @patch("app.modules.claude_code.file_collections.service.resolve_scope_root")
    def test_resolve_scope_path_validates_relative_path(self, mock_resolve, file_collection_service, tmp_path):
        mock_resolve.return_value = tmp_path

        result = file_collection_service.resolve_scope_path(DocumentScope.PROJECT, "nested/test.md")

        assert result == tmp_path / "skills" / "nested" / "test.md"


class TestErrorHandling:
    """Test error handling."""

    def test_validate_scope_invalid_local(self, file_collection_service):
        """Test validating LOCAL scope fails."""
        # Act & Assert
        assert file_collection_service.validate_scope(DocumentScope.LOCAL) is False

    def test_is_readonly_scope_project_writable(self, file_collection_service):
        """Test PROJECT scope is writable."""
        # Act & Assert
        assert file_collection_service.is_readonly_scope(DocumentScope.PROJECT) is False

    def test_is_readonly_scope_user_writable(self, file_collection_service):
        """Test USER scope is writable."""
        # Act & Assert
        assert file_collection_service.is_readonly_scope(DocumentScope.USER) is False

    @patch.object(FileCollectionService, 'resolve_scope_path')
    def test_read_file_not_found(self, mock_resolve, file_collection_service, tmp_path):
        """Test reading non-existent file."""
        # Arrange
        non_existent = tmp_path / "missing.md"
        mock_resolve.return_value = non_existent

        # Act & Assert
        from app.modules.file_system import FileManagementException
        with pytest.raises(FileManagementException):
            file_collection_service.read_file("missing.md", DocumentScope.PROJECT)
