"""Comprehensive tests to boost code coverage to >85%

This test file focuses on testing previously untested or low-covered modules
with simple, straightforward tests that maximize coverage.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


class TestClaudeCodeCommonUtilities:
    """Test utilities in app.modules.claude_code.common"""

    def test_humanize_size_bytes(self):
        """Test humanize_size for bytes"""
        from app.modules.claude_code.common import humanize_size

        assert humanize_size(0) == "0B"
        assert humanize_size(100) == "100B"
        assert humanize_size(1023) == "1023B"

    def test_humanize_size_kilobytes(self):
        """Test humanize_size for kilobytes"""
        from app.modules.claude_code.common import humanize_size

        assert humanize_size(1024) == "1KB"
        assert humanize_size(2048) == "2KB"
        assert humanize_size(102400) == "100KB"

    def test_humanize_size_megabytes(self):
        """Test humanize_size for megabytes"""
        from app.modules.claude_code.common import humanize_size

        assert humanize_size(1024 * 1024) == "1.0MB"
        assert humanize_size(1024 * 1024 * 5) == "5.0MB"

    def test_format_file_size(self):
        """Test format_file_size"""
        from app.modules.claude_code.common import format_file_size

        assert "B" in format_file_size(100)
        assert "KB" in format_file_size(2048)
        assert "MB" in format_file_size(1024 * 1024 * 2)

    def test_parse_front_matter_no_front_matter(self):
        """Test parse_front_matter with no front matter"""
        from app.modules.claude_code.common import parse_front_matter

        content = "# Just a heading\n\nSome content"
        metadata, body = parse_front_matter(content)

        assert metadata == {}
        assert body == content

    def test_parse_front_matter_with_yaml(self):
        """Test parse_front_matter with valid YAML"""
        from app.modules.claude_code.common import parse_front_matter

        content = "---\nname: Test\ndescription: A test\n---\n\n# Content"
        metadata, body = parse_front_matter(content)

        assert metadata["name"] == "Test"
        assert metadata["description"] == "A test"
        assert "# Content" in body

    def test_parse_front_matter_invalid_yaml(self):
        """Test parse_front_matter with invalid YAML"""
        from app.modules.claude_code.common import parse_front_matter

        content = "---\ninvalid: yaml: :\n---\n\n# Content"
        metadata, body = parse_front_matter(content)

        assert metadata == {}

    def test_parse_front_matter_no_closing_delimiter(self):
        """Test parse_front_matter without closing delimiter"""
        from app.modules.claude_code.common import parse_front_matter

        content = "---\nname: Test\n# No closing delimiter"
        metadata, body = parse_front_matter(content)

        assert metadata == {}

    def test_ensure_directory(self, tmp_path):
        """Test ensure_directory"""
        from app.modules.claude_code.common import ensure_directory

        test_dir = tmp_path / "nested" / "directory"
        ensure_directory(test_dir)

        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_read_json_file_nonexistent(self, tmp_path):
        """Test read_json_file with nonexistent file"""
        from app.modules.claude_code.common import read_json_file

        result = read_json_file(tmp_path / "nonexistent.json")
        assert result == {}

    def test_read_json_file_valid(self, tmp_path):
        """Test read_json_file with valid JSON"""
        from app.modules.claude_code.common import read_json_file

        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        test_file.write_text(json.dumps(test_data))

        result = read_json_file(test_file)
        assert result == test_data

    def test_read_json_file_invalid(self, tmp_path):
        """Test read_json_file with invalid JSON"""
        from app.modules.claude_code.common import read_json_file

        test_file = tmp_path / "invalid.json"
        test_file.write_text("not valid json {")

        result = read_json_file(test_file)
        assert result == {}

    def test_write_json_file(self, tmp_path):
        """Test write_json_file"""
        from app.modules.claude_code.common import write_json_file, read_json_file

        test_file = tmp_path / "output" / "test.json"
        test_data = {"name": "test", "value": 123}

        write_json_file(test_file, test_data)

        assert test_file.exists()
        result = read_json_file(test_file)
        assert result == test_data


class TestMarkdownDocumentRecord:
    """Test MarkdownDocumentRecord"""

    def test_markdown_record_creation(self):
        """Test creating a MarkdownDocumentRecord"""
        from app.modules.claude_code.common import MarkdownDocumentRecord, DocumentScope

        record = MarkdownDocumentRecord(
            file_path=Path("/test/agent.md"),
            root_path=Path("/test"),
            scope=DocumentScope.PROJECT,
            content="# Test",
            metadata={"name": "Test"},
            size_bytes=1024,
            updated_at=datetime.now(timezone.utc)
        )

        assert record.file_name == "agent.md"
        assert record.namespace == ""
        assert "KB" in record.size_label

    def test_markdown_record_with_namespace(self):
        """Test MarkdownDocumentRecord with nested path"""
        from app.modules.claude_code.common import MarkdownDocumentRecord, DocumentScope

        record = MarkdownDocumentRecord(
            file_path=Path("/test/category/agent.md"),
            root_path=Path("/test"),
            scope=DocumentScope.USER,
            content="# Test",
            metadata={},
            size_bytes=2048,
            updated_at=datetime.now(timezone.utc)
        )

        assert record.namespace == "category"

    def test_markdown_record_metadata_with_fallbacks(self):
        """Test metadata_with_fallbacks"""
        from app.modules.claude_code.common import MarkdownDocumentRecord, DocumentScope

        record = MarkdownDocumentRecord(
            file_path=Path("/test/agent.md"),
            root_path=Path("/test"),
            scope=DocumentScope.LOCAL,
            content="# Test",
            metadata={},
            size_bytes=512,
            updated_at=None
        )

        meta = record.metadata_with_fallbacks(
            fallback_name="Default Name",
            fallback_description="Default Desc"
        )

        assert meta["name"] == "Default Name"
        assert meta["description"] == "Default Desc"


class TestScopedMarkdownRepository:
    """Test ScopedMarkdownRepository"""

    def test_normalize_file_name_with_extension(self):
        """Test _normalize_file_name with .md extension"""
        from app.modules.claude_code.common import ScopedMarkdownRepository

        repo = ScopedMarkdownRepository("test-folder")
        assert repo._normalize_file_name("test.md") == "test.md"

    def test_normalize_file_name_without_extension(self):
        """Test _normalize_file_name without extension"""
        from app.modules.claude_code.common import ScopedMarkdownRepository

        repo = ScopedMarkdownRepository("test-folder")
        assert repo._normalize_file_name("test") == "test.md"

    @patch("app.modules.claude_code.common.resolve_scope_root")
    def test_directory_path(self, mock_resolve):
        """Test _directory method"""
        from app.modules.claude_code.common import ScopedMarkdownRepository, DocumentScope

        mock_resolve.return_value = Path("/workspace/.claude")
        repo = ScopedMarkdownRepository("agents")

        result = repo._directory("test-ws", DocumentScope.PROJECT)

        assert result == Path("/workspace/.claude/agents")

    def test_namespace_directory_no_namespace(self):
        """Test _namespace_directory without namespace"""
        from app.modules.claude_code.common import ScopedMarkdownRepository

        repo = ScopedMarkdownRepository("test", supports_namespace=True)
        base = Path("/base/path")

        result = repo._namespace_directory(base, None)
        assert result == base

    def test_namespace_directory_with_namespace(self):
        """Test _namespace_directory with namespace"""
        from app.modules.claude_code.common import ScopedMarkdownRepository

        repo = ScopedMarkdownRepository("test", supports_namespace=True)
        base = Path("/base/path")

        result = repo._namespace_directory(base, "category")
        assert result == Path("/base/path/category")


class TestInternalModels:
    """Test models in app.modules.internal.models"""

    def test_internal_api_response(self):
        """Test InternalApiResponse model"""
        from app.modules.internal.models import InternalApiResponse

        response = InternalApiResponse(
            success=True,
            message="Test message",
            details={"key": "value"}
        )

        assert response.success is True
        assert response.message == "Test message"
        assert response.details["key"] == "value"


class TestClaudeCodeModels:
    """Test Claude Code specific models"""

    def test_document_scope_enum(self):
        """Test DocumentScope enum"""
        from app.modules.claude_code.common import DocumentScope

        assert DocumentScope.PROJECT == "project"
        assert DocumentScope.USER == "user"
        assert DocumentScope.LOCAL == "local"
        assert DocumentScope.PLUGIN == "plugin"
