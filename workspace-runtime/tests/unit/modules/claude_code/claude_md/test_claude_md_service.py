"""Claude.md Service 單元測試"""

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
    """測試 ClaudeMdService 類別."""

    @pytest.fixture
    def service(self):
        """創建服務實例."""
        return ClaudeMdService()

    @pytest.fixture
    def workspace_id(self):
        """測試工作區 ID."""
        return "test-workspace-123"

    def test_file_name_constant(self, service):
        """測試文件名常量."""
        assert service._FILE_NAME == "CLAUDE.md"

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_success_project_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """測試獲取文檔 - 成功 (PROJECT scope)."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        content = "# Project CLAUDE.md\n\nProject instructions here."
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # 執行
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # 驗證
        assert isinstance(result, ClaudeMdDocument)
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.PROJECT
        assert result.content == content
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_success_user_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """測試獲取文檔 - 成功 (USER scope)."""
        # 設置 mock
        user_dir = tmp_path / ".claude"
        user_dir.mkdir()
        claude_md_file = user_dir / "CLAUDE.md"
        content = "# User CLAUDE.md\n\nUser preferences here."
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = user_dir

        # 執行
        result = service.get_document(workspace_id, ClaudeMdScope.USER)

        # 驗證
        assert isinstance(result, ClaudeMdDocument)
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.USER
        assert result.content == content
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_not_found(self, mock_resolve, service, workspace_id, tmp_path):
        """測試獲取文檔 - 找不到文件."""
        # 設置 mock - 目錄存在但文件不存在
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # 執行並驗證拋出異常
        with pytest.raises(HTTPException) as exc_info:
            service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert exc_info.value.detail["error"] == "404_NOT_FOUND"
        assert "not found" in exc_info.value.detail["message"].lower()

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_with_utf8_content(self, mock_resolve, service, workspace_id, tmp_path):
        """測試獲取文檔 - UTF-8 內容."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        content = "# 中文標題\n\n這是中文內容 with émojis 🎉"
        claude_md_file.write_text(content, encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # 執行
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # 驗證
        assert result.content == content

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_success_project_scope(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - 成功 (PROJECT scope)."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # 準備請求
        new_content = "# Updated CLAUDE.md\n\nNew instructions."
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # 執行
        result = service.update_document(workspace_id, request)

        # 驗證
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.PROJECT

        # 驗證文件已寫入
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.exists()
        assert claude_md_file.read_text(encoding="utf-8") == new_content

        # 驗證調用
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)
        mock_ensure_dir.assert_called_once_with(claude_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_success_user_scope(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - 成功 (USER scope)."""
        # 設置 mock
        user_dir = tmp_path / ".claude"
        user_dir.mkdir()
        mock_resolve.return_value = user_dir

        # 準備請求
        new_content = "# User CLAUDE.md\n\nUser settings."
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.USER, content=new_content)

        # 執行
        result = service.update_document(workspace_id, request)

        # 驗證
        assert result.workspace_id == workspace_id
        assert result.scope == ClaudeMdScope.USER

        # 驗證文件已寫入
        claude_md_file = user_dir / "CLAUDE.md"
        assert claude_md_file.exists()
        assert claude_md_file.read_text(encoding="utf-8") == new_content

        # 驗證調用
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)
        mock_ensure_dir.assert_called_once_with(user_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_creates_directory(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - 自動創建目錄."""
        # 設置 mock - 目錄不存在
        claude_dir = tmp_path / ".claude"
        mock_resolve.return_value = claude_dir

        # 讓 ensure_directory mock 實際創建目錄
        mock_ensure_dir.side_effect = lambda p: p.mkdir(parents=True, exist_ok=True)

        # 準備請求
        request = ClaudeMdUpdateRequest(
            scope=ClaudeMdScope.PROJECT,
            content="# New content"
        )

        # 執行
        service.update_document(workspace_id, request)

        # 驗證 ensure_directory 被調用
        mock_ensure_dir.assert_called_once_with(claude_dir)

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_overwrites_existing(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - 覆蓋現有文件."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        claude_md_file.write_text("# Old content", encoding="utf-8")

        mock_resolve.return_value = claude_dir

        # 準備請求
        new_content = "# New content"
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # 執行
        service.update_document(workspace_id, request)

        # 驗證文件已被覆蓋
        assert claude_md_file.read_text(encoding="utf-8") == new_content

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_with_utf8_content(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - UTF-8 內容."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # 準備請求 - 包含中文和表情符號
        new_content = "# 測試標題 🚀\n\n中文內容測試 with émojis 🎉"
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content=new_content)

        # 執行
        service.update_document(workspace_id, request)

        # 驗證 UTF-8 編碼正確
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.read_text(encoding="utf-8") == new_content

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_resolve_path_project_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """測試解析路徑 - PROJECT scope."""
        claude_dir = tmp_path / ".claude"
        mock_resolve.return_value = claude_dir

        result = service._resolve_path(workspace_id, ClaudeMdScope.PROJECT)

        assert result == claude_dir / "CLAUDE.md"
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.PROJECT)

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_resolve_path_user_scope(self, mock_resolve, service, workspace_id, tmp_path):
        """測試解析路徑 - USER scope."""
        user_dir = tmp_path / ".claude"
        mock_resolve.return_value = user_dir

        result = service._resolve_path(workspace_id, ClaudeMdScope.USER)

        assert result == user_dir / "CLAUDE.md"
        mock_resolve.assert_called_once_with(workspace_id, DocumentScope.USER)

    def test_resolve_path_unsupported_scope(self, service, workspace_id):
        """測試解析路徑 - 不支持的 scope."""
        # 使用一個無效的 scope（模擬未來可能添加的 scope）
        with pytest.raises(HTTPException) as exc_info:
            # 直接傳入字串來模擬不支持的 scope
            service._resolve_path(workspace_id, "unsupported")

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_get_document_empty_file(self, mock_resolve, service, workspace_id, tmp_path):
        """測試獲取文檔 - 空文件."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        claude_md_file = claude_dir / "CLAUDE.md"
        claude_md_file.write_text("", encoding="utf-8")  # 空文件

        mock_resolve.return_value = claude_dir

        # 執行
        result = service.get_document(workspace_id, ClaudeMdScope.PROJECT)

        # 驗證 - 應該能夠讀取空文件
        assert result.content == ""

    @patch("app.modules.claude_code.claude_md.service.ensure_directory")
    @patch("app.modules.claude_code.claude_md.service.resolve_scope_root")
    def test_update_document_empty_content(
        self, mock_resolve, mock_ensure_dir, service, workspace_id, tmp_path
    ):
        """測試更新文檔 - 空內容."""
        # 設置 mock
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        mock_resolve.return_value = claude_dir

        # 準備請求 - 空內容
        request = ClaudeMdUpdateRequest(scope=ClaudeMdScope.PROJECT, content="")

        # 執行
        result = service.update_document(workspace_id, request)

        # 驗證
        assert result.workspace_id == workspace_id
        claude_md_file = claude_dir / "CLAUDE.md"
        assert claude_md_file.read_text(encoding="utf-8") == ""
