"""Claude Code Common module unit tests."""

from __future__ import annotations

import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, mock_open

from app.modules.claude_code.common import (
    DocumentScope,
    DocumentNotFoundError,
    DuplicateDocumentError,
    AmbiguousDocumentError,
    utcnow,
    humanize_size,
    format_file_size,
    parse_front_matter,
    workspace_root,
    ensure_directory,
    resolve_scope_root,
    read_json_file,
    write_json_file,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
)


class TestDocumentScope:
    """Test DocumentScope enum."""

    def test_document_scope_values(self):
        """Test scope values."""
        assert DocumentScope.PROJECT == "project"
        assert DocumentScope.USER == "user"
        assert DocumentScope.LOCAL == "local"
        assert DocumentScope.PLUGIN == "plugin"

    def test_document_scope_iteration(self):
        """Test iterating all scopes."""
        scopes = list(DocumentScope)
        assert len(scopes) == 4


class TestExceptions:
    """Test custom exceptions."""

    def test_document_not_found_error(self):
        """Test DocumentNotFoundError."""
        with pytest.raises(DocumentNotFoundError):
            raise DocumentNotFoundError("File not found")

    def test_duplicate_document_error(self):
        """Test DuplicateDocumentError."""
        with pytest.raises(DuplicateDocumentError):
            raise DuplicateDocumentError("File exists")

    def test_ambiguous_document_error(self):
        """Test AmbiguousDocumentError."""
        with pytest.raises(AmbiguousDocumentError):
            raise AmbiguousDocumentError("Multiple files found")


class TestUTCNow:
    """Test utcnow function."""

    def test_utcnow_returns_aware_datetime(self):
        """Test returning timezone-aware datetime."""
        now = utcnow()
        assert now.tzinfo == timezone.utc

    def test_utcnow_is_current_time(self):
        """Test returning current time."""
        before = datetime.now(timezone.utc)
        now = utcnow()
        after = datetime.now(timezone.utc)

        assert before <= now <= after


class TestHumanizeSize:
    """Test humanize_size function."""

    def test_humanize_size_bytes(self):
        """Test bytes."""
        assert humanize_size(500) == "500B"
        assert humanize_size(1023) == "1023B"

    def test_humanize_size_kilobytes(self):
        """Test KB."""
        assert humanize_size(1024) == "1KB"
        assert humanize_size(2048) == "2KB"
        assert humanize_size(1536) == "2KB"  # 1.5KB rounded

    def test_humanize_size_megabytes(self):
        """Test MB."""
        assert humanize_size(1024 * 1024) == "1.0MB"
        assert humanize_size(1024 * 1024 * 2) == "2.0MB"
        assert humanize_size(1024 * 1024 * 2.5) == "2.5MB"

    def test_humanize_size_zero(self):
        """Test zero."""
        assert humanize_size(0) == "0B"


class TestFormatFileSize:
    """Test format_file_size function."""

    def test_format_file_size_bytes(self):
        """Test bytes."""
        assert format_file_size(500) == "500.0B"
        assert format_file_size(1023) == "1023.0B"

    def test_format_file_size_kilobytes(self):
        """Test KB."""
        assert format_file_size(1024) == "1.0KB"
        assert format_file_size(2048) == "2.0KB"

    def test_format_file_size_megabytes(self):
        """Test MB."""
        assert format_file_size(1024 * 1024) == "1.0MB"
        assert format_file_size(1024 * 1024 * 2.5) == "2.5MB"

    def test_format_file_size_gigabytes(self):
        """Test GB."""
        assert format_file_size(1024 * 1024 * 1024) == "1.0GB"
        assert format_file_size(1024 * 1024 * 1024 * 2) == "2.0GB"

    def test_format_file_size_terabytes(self):
        """Test TB."""
        assert format_file_size(1024 * 1024 * 1024 * 1024) == "1.0TB"

    def test_format_file_size_zero(self):
        """Test zero."""
        assert format_file_size(0) == "0.0B"


class TestParseFrontMatter:
    """Test parse_front_matter function."""

    def test_parse_front_matter_with_metadata(self):
        """Test parsing with metadata."""
        content = """---
title: Test Document
author: John Doe
---

# Content here"""

        metadata, body = parse_front_matter(content)

        assert metadata["title"] == "Test Document"
        assert metadata["author"] == "John Doe"
        assert body == "# Content here"

    def test_parse_front_matter_without_metadata(self):
        """Test without metadata."""
        content = "# Just content"

        metadata, body = parse_front_matter(content)

        assert metadata == {}
        assert body == content

    def test_parse_front_matter_empty(self):
        """Test empty content."""
        content = ""

        metadata, body = parse_front_matter(content)

        assert metadata == {}
        assert body == ""

    def test_parse_front_matter_invalid_yaml(self):
        """Test invalid YAML."""
        content = """---
invalid: yaml: syntax:
---

# Content"""

        metadata, body = parse_front_matter(content)

        assert metadata == {}

    def test_parse_front_matter_no_closing(self):
        """Test without closing marker."""
        content = """---
title: Test
This is not closed"""

        metadata, body = parse_front_matter(content)

        assert metadata == {}

    def test_parse_front_matter_complex_metadata(self):
        """Test complex metadata."""
        content = """---
title: Complex
tags:
  - python
  - testing
config:
  enabled: true
  count: 42
---

# Content"""

        metadata, body = parse_front_matter(content)

        assert metadata["title"] == "Complex"
        assert metadata["tags"] == ["python", "testing"]
        assert metadata["config"]["enabled"] is True
        assert metadata["config"]["count"] == 42


class TestWorkspaceRoot:
    """Test workspace_root function."""

    @patch('app.modules.claude_code.common.get_workspace_path')
    def test_workspace_root(self, mock_get_path):
        """Test getting workspace root directory."""
        mock_get_path.return_value = "/test/workspace"

        result = workspace_root()

        assert result == Path("/test/workspace")


class TestEnsureDirectory:
    """Test ensure_directory function."""

    def test_ensure_directory_creates_dir(self, tmp_path):
        """Test creating directory."""
        test_dir = tmp_path / "new_dir"

        ensure_directory(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_parents(self, tmp_path):
        """Test creating nested directories."""
        test_dir = tmp_path / "parent" / "child" / "grandchild"

        ensure_directory(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_ensure_directory_exists(self, tmp_path):
        """Test directory already exists."""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()

        # Should not raise error
        ensure_directory(test_dir)

        assert test_dir.exists()


class TestResolveScopeRoot:
    """Test resolve_scope_root function."""

    @patch('app.modules.claude_code.common.workspace_root')
    def test_resolve_scope_root_user(self, mock_root):
        """Test USER scope."""
        result = resolve_scope_root("workspace-1", DocumentScope.USER)

        assert result == Path("/home/developer/.claude")

    @patch('app.modules.claude_code.common.workspace_root')
    def test_resolve_scope_root_project(self, mock_root):
        """Test PROJECT scope."""
        mock_root.return_value = Path("/workspace")

        result = resolve_scope_root("workspace-1", DocumentScope.PROJECT)

        assert result == Path("/workspace/.claude")

    @patch('app.modules.claude_code.common.workspace_root')
    def test_resolve_scope_root_local(self, mock_root):
        """Test LOCAL scope."""
        mock_root.return_value = Path("/workspace")

        result = resolve_scope_root("workspace-1", DocumentScope.LOCAL)

        assert result == Path("/workspace/.claude")


class TestReadJsonFile:
    """Test read_json_file function."""

    def test_read_json_file_success(self, tmp_path):
        """Test successfully reading JSON."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        result = read_json_file(json_file)

        assert result == {"key": "value"}

    def test_read_json_file_not_exists(self, tmp_path):
        """Test file not exists."""
        json_file = tmp_path / "nonexistent.json"

        result = read_json_file(json_file)

        assert result == {}

    def test_read_json_file_invalid_json(self, tmp_path):
        """Test invalid JSON."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        result = read_json_file(json_file)

        assert result == {}

    def test_read_json_file_empty(self, tmp_path):
        """Test empty file."""
        json_file = tmp_path / "empty.json"
        json_file.write_text("")

        result = read_json_file(json_file)

        assert result == {}


class TestWriteJsonFile:
    """Test write_json_file function."""

    def test_write_json_file_success(self, tmp_path):
        """Test successfully writing JSON."""
        json_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42}

        write_json_file(json_file, data)

        assert json_file.exists()
        content = json_file.read_text()
        assert "key" in content
        assert "value" in content

    def test_write_json_file_creates_directory(self, tmp_path):
        """Test creating directory."""
        json_file = tmp_path / "subdir" / "test.json"
        data = {"key": "value"}

        write_json_file(json_file, data)

        assert json_file.exists()
        assert json_file.parent.exists()

    def test_write_json_file_overwrites(self, tmp_path):
        """Test overwriting file."""
        json_file = tmp_path / "test.json"

        write_json_file(json_file, {"old": "data"})
        write_json_file(json_file, {"new": "data"})

        content = json_file.read_text()
        assert "new" in content
        assert "old" not in content

    def test_write_json_file_unicode(self, tmp_path):
        """Test Unicode characters."""
        json_file = tmp_path / "test.json"
        data = {"greeting": "hello 🎉", "emoji": "😀"}

        write_json_file(json_file, data)

        result = read_json_file(json_file)
        assert result["greeting"] == "hello 🎉"
        assert result["emoji"] == "😀"


class TestMarkdownDocumentRecord:
    """Test MarkdownDocumentRecord dataclass."""

    def test_markdown_document_record_creation(self):
        """Test creating record."""
        record = MarkdownDocumentRecord(
            file_path=Path("/test/doc.md"),
            root_path=Path("/test"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={"title": "Test"},
            size_bytes=100,
            updated_at=utcnow()
        )

        assert record.file_path == Path("/test/doc.md")
        assert record.scope == DocumentScope.PROJECT
        assert record.content == "# Test"
        assert record.size_bytes == 100

    def test_markdown_document_record_none_updated_at(self):
        """Test None updated_at."""
        record = MarkdownDocumentRecord(
            file_path=Path("/test/doc.md"),
            root_path=Path("/test"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={},
            size_bytes=100,
            updated_at=None
        )

        assert record.updated_at is None


class TestEdgeCases:
    """Test edge cases."""

    def test_humanize_size_large_numbers(self):
        """Test large numbers."""
        # Numbers over MB
        result = humanize_size(10 * 1024 * 1024)
        assert "MB" in result

    def test_parse_front_matter_special_characters(self):
        """Test special characters."""
        content = """---
title: Test @ #$%
special: "quotes: and: colons"
---

Content"""

        metadata, body = parse_front_matter(content)
        assert metadata["title"] == "Test @"


class TestScopedMarkdownRepository:
    """Test ScopedMarkdownRepository class."""

    @pytest.fixture
    def temp_workspace(self, tmp_path):
        """Create temporary workspace."""
        workspace_id = "test-workspace"
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        return workspace_id, workspace_path

    @pytest.fixture
    def repository(self):
        """Create test repository instance."""
        return ScopedMarkdownRepository("test-docs", supports_namespace=True)

    def test_init(self):
        """Test initialization."""
        repo = ScopedMarkdownRepository("my-folder")
        assert repo.folder_name == "my-folder"
        assert repo.supports_namespace is False

        repo_with_ns = ScopedMarkdownRepository("my-folder", supports_namespace=True)
        assert repo_with_ns.supports_namespace is True

    def test_normalize_file_name(self, repository):
        """Test file name normalization."""
        assert repository._normalize_file_name("test") == "test.md"
        assert repository._normalize_file_name("test.md") == "test.md"
        assert repository._normalize_file_name("my-file") == "my-file.md"

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_directory(self, mock_resolve, repository, temp_workspace):
        """Test directory resolution."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        directory = repository._directory(workspace_id, DocumentScope.PROJECT)
        assert directory == workspace_path / ".claude" / "test-docs"
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)

    def test_namespace_directory(self, repository, tmp_path):
        """Test namespace directory."""
        base_dir = tmp_path / "base"

        # No namespace
        result = repository._namespace_directory(base_dir, None)
        assert result == base_dir

        # With namespace
        result = repository._namespace_directory(base_dir, "subdir")
        assert result == base_dir / "subdir"

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_list_records_empty(self, mock_resolve, repository, temp_workspace):
        """Test listing records - empty directory."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        records = repository.list_records(workspace_id, DocumentScope.PROJECT)
        assert records == []

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_list_records_with_files(self, mock_resolve, repository, temp_workspace):
        """Test listing records - with files."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)

        # Create test files
        (docs_dir / "doc1.md").write_text("# Doc 1", encoding="utf-8")
        (docs_dir / "doc2.md").write_text("# Doc 2", encoding="utf-8")

        records = repository.list_records(workspace_id, DocumentScope.PROJECT)
        assert len(records) == 2
        assert all(isinstance(r, MarkdownDocumentRecord) for r in records)
        assert records[0].content in ["# Doc 1", "# Doc 2"]

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_get_record_success(self, mock_resolve, repository, temp_workspace):
        """Test getting record - success."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)

        content = """---
title: Test Doc
---

# Content"""
        (docs_dir / "test.md").write_text(content, encoding="utf-8")

        record = repository.get_record(workspace_id, DocumentScope.PROJECT, "test")
        assert record.file_name == "test.md"
        assert record.content == content
        assert record.metadata["title"] == "Test Doc"
        assert record.scope == DocumentScope.PROJECT

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_get_record_not_found(self, mock_resolve, repository, temp_workspace):
        """Test getting record - not found."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        with pytest.raises(DocumentNotFoundError):
            repository.get_record(workspace_id, DocumentScope.PROJECT, "nonexistent")

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_create_record_success(self, mock_resolve, repository, temp_workspace):
        """Test creating record - success."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        content = "# New Document"
        record = repository.create_record(
            workspace_id, DocumentScope.PROJECT, "new-doc", content
        )

        assert record.file_name == "new-doc.md"
        assert record.content == content
        assert record.scope == DocumentScope.PROJECT

        # Verify file created
        expected_path = workspace_path / ".claude" / "test-docs" / "new-doc.md"
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == content

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_create_record_with_namespace(self, mock_resolve, repository, temp_workspace):
        """Test creating record - with namespace."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        content = "# Namespaced Document"
        record = repository.create_record(
            workspace_id, DocumentScope.PROJECT, "doc", content, namespace="subdir"
        )

        assert record.file_name == "doc.md"
        assert record.namespace == "subdir"

        # Verify file in correct namespace directory
        expected_path = workspace_path / ".claude" / "test-docs" / "subdir" / "doc.md"
        assert expected_path.exists()

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_create_record_duplicate(self, mock_resolve, repository, temp_workspace):
        """Test creating record - duplicate."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "existing.md").write_text("# Existing", encoding="utf-8")

        with pytest.raises(DuplicateDocumentError):
            repository.create_record(workspace_id, DocumentScope.PROJECT, "existing", "# New")

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_update_record_success(self, mock_resolve, repository, temp_workspace):
        """Test updating record - success."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "update.md").write_text("# Original", encoding="utf-8")

        new_content = "# Updated"
        record = repository.update_record(
            workspace_id, DocumentScope.PROJECT, "update", new_content
        )

        assert record.content == new_content
        assert (docs_dir / "update.md").read_text(encoding="utf-8") == new_content

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_update_record_not_found(self, mock_resolve, repository, temp_workspace):
        """Test updating record - not found."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        with pytest.raises(DocumentNotFoundError):
            repository.update_record(
                workspace_id, DocumentScope.PROJECT, "nonexistent", "# Content"
            )

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_delete_record_success(self, mock_resolve, repository, temp_workspace):
        """Test deleting record - success."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)
        file_path = docs_dir / "delete.md"
        file_path.write_text("# To Delete", encoding="utf-8")

        assert file_path.exists()
        repository.delete_record(workspace_id, DocumentScope.PROJECT, "delete")
        assert not file_path.exists()

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_delete_record_not_found(self, mock_resolve, repository, temp_workspace):
        """Test deleting record - not found."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        with pytest.raises(DocumentNotFoundError):
            repository.delete_record(workspace_id, DocumentScope.PROJECT, "nonexistent")

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_resolve_file_path_with_namespace(self, mock_resolve, repository, temp_workspace):
        """Test resolving file path - with namespace."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        ns_dir = docs_dir / "namespace"
        ns_dir.mkdir(parents=True)
        (ns_dir / "doc.md").write_text("# Doc", encoding="utf-8")

        result = repository._resolve_file_path(docs_dir, "doc", namespace="namespace")
        assert result == ns_dir / "doc.md"

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_resolve_file_path_without_namespace(self, mock_resolve, repository, temp_workspace):
        """Test resolving file path - without namespace."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "doc.md").write_text("# Doc", encoding="utf-8")

        result = repository._resolve_file_path(docs_dir, "doc", namespace=None)
        assert result == docs_dir / "doc.md"

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_resolve_file_path_ambiguous(self, mock_resolve, repository, temp_workspace):
        """Test resolving file path - ambiguous."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)
        (docs_dir / "doc.md").write_text("# Doc 1", encoding="utf-8")

        subdir = docs_dir / "subdir"
        subdir.mkdir()
        (subdir / "doc.md").write_text("# Doc 2", encoding="utf-8")

        with pytest.raises(AmbiguousDocumentError):
            repository._resolve_file_path(docs_dir, "doc", namespace=None)

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_resolve_file_path_not_found(self, mock_resolve, repository, temp_workspace):
        """Test resolving file path - not found."""
        workspace_id, workspace_path = temp_workspace
        mock_resolve.return_value = workspace_path / ".claude"

        docs_dir = workspace_path / ".claude" / "test-docs"
        docs_dir.mkdir(parents=True)

        result = repository._resolve_file_path(docs_dir, "nonexistent", namespace=None)
        assert result is None
