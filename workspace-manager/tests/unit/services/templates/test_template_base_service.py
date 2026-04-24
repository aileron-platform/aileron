"""TemplateBaseService 單元測試"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.db.models import Template as TemplateDB
from app.services.template_base_service import TemplateBaseService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock 資料庫 Session"""
    session = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_template_db():
    """範例模板資料庫模型"""
    return TemplateDB(
        id="test-template",
        name="Test Template",
        description="A test template",
        author_name="Test Author",
        author_email="test@example.com",
        author_url="https://example.com",
        category="general",
        version="1.0.0",
        cli_type="claude-code",
        status="active",
        keywords=["test"],
        init_commands=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def base_service(mock_db_session, tmp_path):
    """TemplateBaseService 實例"""
    with patch('app.services.template_base_service.get_settings') as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateBaseService(mock_db_session)
        service.storage_path = tmp_path
        return service


# ============================================================================
# Path Management Tests
# ============================================================================

@pytest.mark.unit
class TestPathManagement:
    """路徑管理測試"""

    def test_get_template_dir(self, base_service, tmp_path):
        """測試：取得模板目錄路徑"""
        # Act
        result = base_service._get_template_dir("test-template")

        # Assert
        expected = tmp_path / "plugins" / "test-template"
        assert result == expected

    def test_get_registry_template_dir(self, base_service, tmp_path):
        """測試：取得 canonical registry 模板目錄路徑"""
        result = base_service._get_registry_template_dir("test-template")

        expected = tmp_path / "templates" / "test-template"
        assert result == expected

    def test_resolve_template_dir_prefers_registry_template(self, base_service, tmp_path):
        """測試：解析模板目錄時優先使用 registry templates 目錄"""
        registry_dir = tmp_path / "templates" / "test-template"
        legacy_dir = tmp_path / "plugins" / "test-template"
        registry_dir.mkdir(parents=True, exist_ok=True)
        legacy_dir.mkdir(parents=True, exist_ok=True)

        result = base_service._resolve_template_dir("test-template")

        assert result == registry_dir

    def test_get_plugin_json_path(self, base_service, tmp_path):
        """測試：取得 plugin.json 路徑"""
        # Act
        result = base_service._get_plugin_json_path("test-template")

        # Assert
        expected = tmp_path / "plugins" / "test-template" / ".claude-plugin" / "plugin.json"
        assert result == expected

    def test_ensure_directory_creates_new(self, base_service, tmp_path):
        """測試：確保目錄存在會建立新目錄"""
        # Act
        directory, created = base_service._ensure_directory("test-template", "commands")

        # Assert
        expected = tmp_path / "plugins" / "test-template" / "commands"
        assert directory == expected
        assert directory.exists()
        assert created is True

    def test_ensure_directory_existing(self, base_service, tmp_path):
        """測試：確保目錄存在不會重複建立"""
        # Arrange
        existing_dir = tmp_path / "plugins" / "test-template" / "commands"
        existing_dir.mkdir(parents=True, exist_ok=True)

        # Act
        directory, created = base_service._ensure_directory("test-template", "commands")

        # Assert
        assert directory == existing_dir
        assert created is False


# ============================================================================
# File Validation Tests
# ============================================================================

@pytest.mark.unit
class TestFileValidation:
    """檔案驗證測試"""

    def test_validate_filename_valid(self, base_service):
        """測試：有效檔案名稱驗證成功"""
        # Arrange
        valid_names = [
            "command.md",
            "test-file.txt",
            "script.py",
            "config.yaml",
            "data.json"
        ]

        # Act & Assert
        for name in valid_names:
            assert base_service._validate_filename(name) is True

    def test_validate_filename_invalid_characters(self, base_service):
        """測試：無效字符檔案名稱驗證失敗"""
        # Arrange
        invalid_names = [
            "file<>.md",
            'file".txt',
            "file|.py",
            "file?.yaml",
            "file*.json"
        ]

        # Act & Assert
        for name in invalid_names:
            assert base_service._validate_filename(name) is False

    def test_validate_filename_invalid_extension(self, base_service):
        """測試：不允許的副檔名驗證失敗"""
        # Arrange
        invalid_names = [
            "file.exe",
            "file.bat",
            "file.com"
        ]

        # Act & Assert
        for name in invalid_names:
            assert base_service._validate_filename(name) is False

    def test_validate_filename_empty_or_dots(self, base_service):
        """測試：空檔名或點號驗證失敗"""
        # Arrange
        invalid_names = ["", ".", ".."]

        # Act & Assert
        for name in invalid_names:
            assert base_service._validate_filename(name) is False

    def test_validate_file_path_valid(self, base_service):
        """測試：有效檔案路徑驗證成功"""
        # Arrange
        valid_paths = [
            "commands/test.md",
            "scripts/sub/file.py",
            "agents/agent1.md"
        ]

        # Act & Assert
        for path in valid_paths:
            assert base_service._validate_file_path(path) is True

    def test_validate_file_path_invalid(self, base_service):
        """測試：無效檔案路徑驗證失敗"""
        # Arrange
        invalid_paths = [
            "/absolute/path",
            "../parent/file",
            "",
            'path<>file',
            'path|file'
        ]

        # Act & Assert
        for path in invalid_paths:
            assert base_service._validate_file_path(path) is False

    def test_is_safe_path_within_base(self, base_service, tmp_path):
        """測試：安全路徑檢查（在基礎路徑內）"""
        # Arrange
        base_path = tmp_path / "base"
        base_path.mkdir(parents=True, exist_ok=True)
        safe_path = base_path / "subdir" / "file.txt"
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.touch()

        # Act
        result = base_service._is_safe_path(safe_path, base_path)

        # Assert
        assert result is True

    def test_is_safe_path_outside_base(self, base_service, tmp_path):
        """測試：安全路徑檢查（在基礎路徑外）"""
        # Arrange
        base_path = tmp_path / "base"
        base_path.mkdir(parents=True, exist_ok=True)
        unsafe_path = tmp_path / "outside" / "file.txt"
        unsafe_path.parent.mkdir(parents=True, exist_ok=True)
        unsafe_path.touch()

        # Act
        result = base_service._is_safe_path(unsafe_path, base_path)

        # Assert
        assert result is False


# ============================================================================
# Template ID Validation Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateIdValidation:
    """模板 ID 驗證測試"""

    def test_validate_template_id_valid(self, base_service):
        """測試：有效模板 ID 驗證成功"""
        # Arrange
        valid_ids = [
            "test-template",
            "my-template-123",
            "simple",
            "complex-template-with-numbers-456"
        ]

        # Act & Assert
        for template_id in valid_ids:
            assert base_service._validate_template_id(template_id) is True

    def test_validate_template_id_invalid(self, base_service):
        """測試：無效模板 ID 驗證失敗"""
        # Arrange
        invalid_ids = [
            "Template",  # 大寫
            "test_template",  # 底線
            "123-template",  # 數字開頭
            "-test",  # 連字號開頭
            "test-",  # 連字號結尾
            "test--template",  # 連續連字號
            "test template",  # 空格
        ]

        # Act & Assert
        for template_id in invalid_ids:
            assert base_service._validate_template_id(template_id) is False


# ============================================================================
# File Operations Tests
# ============================================================================

@pytest.mark.unit
class TestFileOperations:
    """檔案操作測試"""

    def test_normalize_file_name_with_extension(self, base_service):
        """測試：標準化已有副檔名的檔案名稱"""
        # Act
        result = base_service._normalize_file_name("command.md")

        # Assert
        assert result == "command.md"

    def test_normalize_file_name_without_extension(self, base_service):
        """測試：標準化無副檔名的檔案名稱"""
        # Act
        result = base_service._normalize_file_name("command")

        # Assert
        assert result == "command.md"

    def test_list_markdown_files(self, base_service, tmp_path):
        """測試：列出 Markdown 檔案"""
        # Arrange
        test_dir = tmp_path / "test-dir"
        test_dir.mkdir(parents=True, exist_ok=True)

        (test_dir / "file1.md").write_text("content1")
        (test_dir / "file2.md").write_text("content2")
        (test_dir / "file3.txt").write_text("not included")

        # 定義簡單的檔案模型類別
        class FileModel:
            def __init__(self, file_name, size, last_modified):
                self.file_name = file_name
                self.size = size
                self.last_modified = last_modified

        # Act
        files = base_service._list_markdown_files(test_dir, FileModel)

        # Assert
        assert len(files) == 2
        file_names = [f.file_name for f in files]
        assert "file1.md" in file_names
        assert "file2.md" in file_names
        assert "file3.txt" not in file_names

    def test_read_file_content(self, base_service, tmp_path):
        """測試：讀取檔案內容"""
        # Arrange
        test_file = tmp_path / "test.md"
        test_content = "Test content\nLine 2"
        test_file.write_text(test_content, encoding="utf-8")

        # 定義簡單的內容模型類別
        class ContentModel:
            def __init__(self, file_name, content, size, last_modified):
                self.file_name = file_name
                self.content = content
                self.size = size
                self.last_modified = last_modified

        # Act
        result = base_service._read_file_content(test_file, ContentModel)

        # Assert
        assert result.file_name == "test.md"
        assert result.content == test_content
        assert result.size > 0

    def test_write_file_with_stats_success(self, base_service, tmp_path):
        """測試：寫入檔案並返回統計資訊"""
        # Arrange
        test_file = tmp_path / "test.md"
        content = "Test content"

        # 定義簡單的內容模型類別
        class ContentModel:
            def __init__(self, file_name, content, size, last_modified):
                self.file_name = file_name
                self.content = content
                self.size = size
                self.last_modified = last_modified

        # Act
        result, error = base_service._write_file_with_stats(test_file, content, ContentModel)

        # Assert
        assert error is None
        assert result is not None
        assert result.content == content
        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_file_with_stats_too_large(self, base_service, tmp_path):
        """測試：寫入過大檔案失敗"""
        # Arrange
        test_file = tmp_path / "test.md"
        content = "x" * (base_service.MAX_FILE_SIZE_BYTES + 1)

        class ContentModel:
            def __init__(self, file_name, content, size, last_modified):
                pass

        # Act
        result, error = base_service._write_file_with_stats(test_file, content, ContentModel)

        # Assert
        assert result is None
        assert error is not None
        assert "too large" in error.lower()


# ============================================================================
# YAML Extraction Tests
# ============================================================================

@pytest.mark.unit
class TestYAMLExtraction:
    """YAML front matter 提取測試"""

    def test_extract_yaml_description_with_frontmatter(self, base_service):
        """測試：從 YAML front matter 提取 description"""
        # Arrange
        content = """---
description: Test description
author: Test Author
---

# Content
"""

        # Act
        result = base_service._extract_yaml_description(content)

        # Assert
        assert result == "Test description"

    def test_extract_yaml_description_with_quotes(self, base_service):
        """測試：從帶引號的 YAML front matter 提取 description"""
        # Arrange
        content = """---
description: "Test description with quotes"
---

# Content
"""

        # Act
        result = base_service._extract_yaml_description(content)

        # Assert
        assert result == "Test description with quotes"

    def test_extract_yaml_description_no_frontmatter(self, base_service):
        """測試：無 YAML front matter 返回空字串"""
        # Arrange
        content = "# Just content\nNo frontmatter"

        # Act
        result = base_service._extract_yaml_description(content)

        # Assert
        assert result == ""

    def test_extract_yaml_description_no_description_field(self, base_service):
        """測試：無 description 欄位返回空字串"""
        # Arrange
        content = """---
author: Test Author
title: Test Title
---

# Content
"""

        # Act
        result = base_service._extract_yaml_description(content)

        # Assert
        assert result == ""


# ============================================================================
# Plugin JSON Update Tests
# ============================================================================

@pytest.mark.unit
class TestPluginJsonUpdate:
    """Plugin JSON 更新測試"""

    def test_update_plugin_json_success(self, base_service, tmp_path):
        """測試：更新 plugin.json 成功"""
        # Arrange
        template_dir = tmp_path / "plugins" / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)

        # 建立 commands 和 agents 目錄
        commands_dir = template_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        (commands_dir / "cmd1.md").write_text("command 1")
        (commands_dir / "cmd2.md").write_text("command 2")

        agents_dir = template_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "agent1.md").write_text("agent 1")

        # 建立 plugin.json
        plugin_dir = template_dir / ".claude-plugin"
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_file = plugin_dir / "plugin.json"

        initial_data = {
            "id": "test-template",
            "name": "Test",
            "commands": [],
            "agents": []
        }
        plugin_file.write_text(json.dumps(initial_data), encoding="utf-8")

        # Act
        base_service._update_plugin_json("test-template")

        # Assert
        updated_data = json.loads(plugin_file.read_text(encoding="utf-8"))
        assert len(updated_data["commands"]) == 2
        assert len(updated_data["agents"]) == 1
        assert any("cmd1.md" in cmd for cmd in updated_data["commands"])
        assert any("agent1.md" in agent for agent in updated_data["agents"])

    def test_update_plugin_json_not_found(self, base_service, tmp_path):
        """測試：plugin.json 不存在時不會拋出異常"""
        # Act
        base_service._update_plugin_json("nonexistent-template")

        # Assert
        # 應該正常執行，不拋出異常
        # 只會記錄警告日誌


# ============================================================================
# Template Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateRetrieval:
    """模板檢索測試"""

    def test_get_template_success(self, base_service, mock_db_session, mock_template_db):
        """測試：取得模板成功"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Act
        result = base_service._get_template("test-template")

        # Assert
        assert result == mock_template_db

    def test_get_template_not_found(self, base_service, mock_db_session):
        """測試：取得不存在的模板返回 None"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act
        result = base_service._get_template("nonexistent-template")

        # Assert
        assert result is None


# ============================================================================
# Response Builder Tests
# ============================================================================

@pytest.mark.unit
class TestResponseBuilder:
    """回應建構測試"""

    def test_response_template_not_found(self, base_service):
        """測試：建立模板不存在的回應"""
        # Arrange
        class MockResponse:
            def __init__(self, **kwargs):
                self.success = kwargs.get("success")
                self.error = kwargs.get("error")
                self.data = kwargs.get("data")

        # Act
        result = base_service._response_template_not_found(MockResponse)

        # Assert
        assert result.success is False
        assert result.error == "Template not found"

    def test_response_template_not_found_with_list_data(self, base_service):
        """測試：建立模板不存在的回應（含列表資料）"""
        # Arrange
        class MockResponse:
            def __init__(self, **kwargs):
                self.success = kwargs.get("success")
                self.error = kwargs.get("error")
                self.data = kwargs.get("data")

        # Act
        result = base_service._response_template_not_found(MockResponse, include_list_data=True)

        # Assert
        assert result.success is False
        assert result.error == "Template not found"
        assert result.data == []

    def test_validate_template_and_filename_success(self, base_service, mock_db_session, mock_template_db):
        """測試：模板與檔名驗證成功"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        class MockResponse:
            def __init__(self, **kwargs):
                pass

        # Act
        db_template, error_response = base_service._validate_template_and_filename(
            "test-template",
            MockResponse,
            file_name="test.md"
        )

        # Assert
        assert db_template == mock_template_db
        assert error_response is None

    def test_validate_template_and_filename_invalid_template(self, base_service, mock_db_session):
        """測試：模板不存在時返回錯誤回應"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        class MockResponse:
            def __init__(self, **kwargs):
                self.success = kwargs.get("success")
                self.error = kwargs.get("error")

        # Act
        db_template, error_response = base_service._validate_template_and_filename(
            "nonexistent-template",
            MockResponse
        )

        # Assert
        assert db_template is None
        assert error_response is not None
        assert error_response.success is False

    def test_validate_template_and_filename_invalid_filename(self, base_service, mock_db_session, mock_template_db):
        """測試：無效檔名時返回錯誤回應"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        class MockResponse:
            def __init__(self, **kwargs):
                self.success = kwargs.get("success")
                self.error = kwargs.get("error")

        # Act
        db_template, error_response = base_service._validate_template_and_filename(
            "test-template",
            MockResponse,
            file_name="invalid<>.md"
        )

        # Assert
        assert db_template is None
        assert error_response is not None
        assert error_response.error == "Invalid filename"


# ============================================================================
# Constants Tests
# ============================================================================

@pytest.mark.unit
class TestConstants:
    """常數測試"""

    def test_max_file_size_bytes(self, base_service):
        """測試：檔案大小限制常數"""
        assert base_service.MAX_FILE_SIZE_BYTES == 1024 * 1024

    def test_max_template_file_size_bytes(self, base_service):
        """測試：模板檔案大小限制常數"""
        assert base_service.MAX_TEMPLATE_FILE_SIZE_BYTES == 10 * 1024 * 1024

    def test_max_upload_files(self, base_service):
        """測試：最大上傳檔案數常數"""
        assert base_service.MAX_UPLOAD_FILES == 50

    def test_allowed_extensions(self, base_service):
        """測試：允許的副檔名集合"""
        assert '.md' in base_service.ALLOWED_EXTENSIONS
        assert '.txt' in base_service.ALLOWED_EXTENSIONS
        assert '.py' in base_service.ALLOWED_EXTENSIONS
        assert '.json' in base_service.ALLOWED_EXTENSIONS
        assert '.yaml' in base_service.ALLOWED_EXTENSIONS
