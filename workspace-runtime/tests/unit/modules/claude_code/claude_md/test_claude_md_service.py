"""Claude.md Service unit tests"""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from fastapi import HTTPException, status

from app.modules.claude_code.claude_md.service import ClaudeMdService
from app.modules.claude_code.claude_md.models import (
    ClaudeMdDocument,
    ClaudeMdScope,
    ClaudeMdUpdateRequest,
)
from app.modules.claude_code.common import DocumentScope


class TestClaudeMdService:
    """Test ClaudeMdService class."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return ClaudeMdService()

    @pytest.fixture
    def workspace_id(self):
        """Test workspace ID."""
        return "test-workspace-123"

    def test_file_name_constant(self, service):
        """Test file name constant."""
        assert service._FILE_NAME == "CLAUDE.md"

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_success_project_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """Test getting document - success (PROJECT scope)."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        content = "# Project CLAUDE.md\n\nProject instructions here."
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # Execute
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # Verify
        assert isinstance(result, ClaudeMdDocument)
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.PROJECT
        assert result.content == content
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_success_user_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """Test getting document - success (USER scope)."""
        # Setup mock
        user_dir = tmp_path / ".claude"
        user_dir.mkdir()
        claude_md_file = user_dir / "CLAUDE.md"
        content = "# User CLAUDE.md\n\nUser preferences here."
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = user_dir

        # Execute
        result = service.get_document(workspace_id, ClaudeMdScope.USER)

        # Verify
        assert isinstance(result, ClaudeMdDocument)
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.USER
        assert result.content == content
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_not_found(self, mock_resolve, service, workspace_id, tmp_path):
        """Test getting document - file not found."""
        # Setup mock - directory exists but file doesn't
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # Execute and verify exception is thrown
        with pytest.raises(HTTPException) as exc_info:
            service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["error"] == "404_NOT_FOUND"
        assert "not found" in exc_info.value.detail["message"].lower()

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_with_utf8_content(self, mock_resolve, service, workspace_id, tmp_path):
        """Test getting document - UTF-8 content."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        content = "# 中文標題\n\n這是中文內容 with émojis 🎉"
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # Execute
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # Verify
        assert result.content == content

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_success_project_scope(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - success (PROJECT scope)."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # Prepare request
        new_content = "# Updated CLAUDE.md\n\nNew instructions."
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # Execute
        result = service.update_document(workspace_id, request)

        # Verify
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.PROJECT

        # Verify file was written
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.exists()
        assert claude_md_file.read_text(encoding="utf-8") == new_content

        # Verify calls
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)
        mock_ensure_dir.assert_called_once_with(claude_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_success_user_scope(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - success (USER scope)."""
        # Setup mock
        user_dir = tmp_path / ".claude"
        user_dir.mkdir()
        mock_resolve.return_value = user_dir

        # Prepare request
        new_content = "# User CLAUDE.md\n\nUser settings."
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.USER, content=new_content)

        # Execute
        result = service.update_document(workspace_id, request)

        # Verify
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.USER

        # Verify file was written
        claude_md_file = user_dir / "CLAUDE.md"
        assert claude_md_file.exists()
        assert claude_md_file.read_text(encoding="utf-8") == new_content

        # Verify calls
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)
        mock_ensure_dir.assert_called_once_with(user_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_creates_directory(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - auto-create directory。"""
        # Setup mock - directory doesn't exist
        claude_dir = tmp_path / ".claude"
        mock_resolve.return_value = claude_dir

        # Let ensure_directory mock actually create directory
        mock_ensure_dir.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)

        # Prepare request
        request = ClaudeMdUpdateRequest(
            scope=ClaudeMdScope.PROJECT,
            content="# New content"
        )

        # Execute
        service.update_document(workspace_id, request)

        # Verify ensure_directory was called
        mock_ensure_dir.assert_called_once_with(claude_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_overwrites_existing(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - overwrite existing file."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        claude_md_file.write_text("# Old content", encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # Prepare request
        new_content = "# New content"
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # Execute
        service.update_document(workspace_id, request)

        # Verify file was overwritten
        assert claude_md_file.read_text(encoding="utf-8") == new_content

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_with_utf8_content(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - UTF-8 content."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # Prepare request - includes Chinese and emojis
        new_content = "# 測試標題 🚀\n\n中文內容測試 with émojis 🎉"
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # Execute
        service.update_document(workspace_id, request)

        # Verify UTF-8 encoding is correct
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.read_text(encoding="utf-8") == new_content

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_resolve_path_project_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """Test resolving path - PROJECT scope."""
        claude_dir = tmp_path / ".claude"
        mock_resolve.return_value = claude_dir

        result = service._resolve_path(workspace_id, ClaudeMdScope.PROJECT)

        assert result == claude_dir / "CLAUDE.md"
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_resolve_path_user_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """Test resolving path - USER scope."""
        user_dir = tmp_path / ".claude"
        mock_resolve.return_value = user_dir

        result = service._resolve_path(workspace_id, ClaudeMdScope.USER)

        assert result == user_dir / "CLAUDE.md"
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)

    def test_resolve_path_unsupported_scope(self, service, workspace_id):
        """Test resolving path - unsupported scope."""
        # Use an invalid scope (simulating scope that might be added in future)
        with pytest.raises(HTTPException) as exc_info:
            # Pass string directly to simulate unsupported scope
            service._resolve_path(workspace_id, "unsupported")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_empty_file(self, mock_resolve, service, workspace_id, tmp_path):
        """Test getting document - empty file."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        claude_md_file.write_text("", encoding="utf-8")  # Empty file

        mock_resolve.return_value = claude_dir

        # Execute
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # Verify - should be able to read empty file
        assert result.content == ""

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_empty_content(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """Test updating document - empty content."""
        # Setup mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # Prepare request - empty content
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content="")

        # Execute
        result = service.update_document(workspace_id, request)

        # Verify
        assert result.workspace_id == workspace_id
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.read_text(encoding="utf-8") == ""
