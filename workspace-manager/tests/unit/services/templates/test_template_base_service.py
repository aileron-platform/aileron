"""TemplateBaseService 單元Testing"""

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
    """Mock Data庫 Session"""
    session = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_template_db():
    """範例TemplateData庫Model"""
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
    """TemplateBaseService Instance"""
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
    """Road徑ManagingTesting"""

    def test_get_template_dir(self, base_service, tmp_path):
        """Testing：GetTemplateCatalogRoad徑"""
        # Act
        result = base_service._get_template_dir("test-template")

        # Assert
        expected = tmp_path / "templates" / "test-template"
        assert result == expected

    def test_get_registry_template_dir(self, base_service, tmp_path):
        """Testing：Get canonical registry TemplateCatalogRoad徑"""
        result = base_service._get_registry_template_dir("test-template")

        expected = tmp_path / "templates" / "test-template"
        assert result == expected

    def test_resolve_template_dir_prefers_registry_template(self, base_service, tmp_path):
        """Testing：解析TemplateCatalog時優先Use registry templates Catalog"""
        registry_dir = tmp_path / "templates" / "test-template"
        legacy_dir = tmp_path / "plugins" / "test-template"
        registry_dir.mkdir(parents=True, exist_ok=True)
        legacy_dir.mkdir(parents=True, exist_ok=True)

        result = base_service._resolve_template_dir("test-template")

        assert result == registry_dir

    def test_get_plugin_json_path(self, base_service, tmp_path):
        """Testing：Get plugin.json Road徑"""
        # Act
        result = base_service._get_plugin_json_path("test-template")

        # Assert
        expected = tmp_path / "templates" / "test-template" / ".claude-plugin" / "plugin.json"
        assert result == expected

    def test_ensure_directory_creates_new(self, base_service, tmp_path):
        """Testing：確保Catalog存At會BuildingNewCatalog"""
        # Act
        directory, created = base_service._ensure_directory("test-template", "commands")

        # Assert
        expected = tmp_path / "templates" / "test-template" / "commands"
        assert directory == expected
        assert directory.exists()
        assert created is True

    def test_ensure_directory_existing(self, base_service, tmp_path):
        """Testing：確保Catalog存At不會RepeatBuilding"""
        # Arrange
        existing_dir = tmp_path / "templates" / "test-template" / "commands"
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
    """FileVerifyingTesting"""

    def test_validate_filename_valid(self, base_service):
        """Testing：ValidFileNameVerifyingSuccessfully"""
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
        """Testing：Invalid字符FileNameVerifyingUnsuccessfully"""
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
        """Testing：不Allowing的副檔名VerifyingUnsuccessfully"""
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
        """Testing：空檔名或PointNumberVerifyingUnsuccessfully"""
        # Arrange
        invalid_names = ["", ".", ".."]

        # Act & Assert
        for name in invalid_names:
            assert base_service._validate_filename(name) is False

    def test_validate_file_path_valid(self, base_service):
        """Testing：ValidFileRoad徑VerifyingSuccessfully"""
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
        """Testing：InvalidFileRoad徑VerifyingUnsuccessfully"""
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
        """Testing：SafeRoad徑Check（AtBasisRoad徑Within）"""
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
        """Testing：SafeRoad徑Check（AtBasisRoad徑Outside）"""
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
    """Template ID VerifyingTesting"""

    def test_validate_template_id_valid(self, base_service):
        """Testing：ValidTemplate ID VerifyingSuccessfully"""
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
        """Testing：InvalidTemplate ID VerifyingUnsuccessfully"""
        # Arrange
        invalid_ids = [
            "Template",  # Big寫
            "test_template",  # 底Line
            "123-template",  # NumberOn頭
            "-test",  # 連字NumberOn頭
            "test-",  # 連字Number結尾
            "test--template",  # 連續連字Number
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
    """FileOperationTesting"""

    def test_normalize_file_name_with_extension(self, base_service):
        """Testing：Standard化已有副檔名的FileName"""
        # Act
        result = base_service._normalize_file_name("command.md")

        # Assert
        assert result == "command.md"

    def test_normalize_file_name_without_extension(self, base_service):
        """Testing：Standard化無副檔名的FileName"""
        # Act
        result = base_service._normalize_file_name("command")

        # Assert
        assert result == "command.md"

    def test_list_markdown_files(self, base_service, tmp_path):
        """Testing：ListingOut Markdown File"""
        # Arrange
        test_dir = tmp_path / "test-dir"
        test_dir.mkdir(parents=True, exist_ok=True)

        (test_dir / "file1.md").write_text("content1")
        (test_dir / "file2.md").write_text("content2")
        (test_dir / "file3.txt").write_text("not included")

        # 定義Simple的FileModelClass
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
        """Testing：ReadFileWithin容"""
        # Arrange
        test_file = tmp_path / "test.md"
        test_content = "Test content\nLine 2"
        test_file.write_text(test_content, encoding="utf-8")

        # 定義Simple的Within容ModelClass
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
        """Testing：WriteFile並返BackStatisticsInformation"""
        # Arrange
        test_file = tmp_path / "test.md"
        content = "Test content"

        # 定義Simple的Within容ModelClass
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
        """Testing：Write過BigFileUnsuccessfully"""
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
    """YAML front matter LiftingGettingTesting"""

    def test_extract_yaml_description_with_frontmatter(self, base_service):
        """Testing：From YAML front matter LiftingGetting description"""
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
        """Testing：FromBringing引Number的 YAML front matter LiftingGetting description"""
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
        """Testing：無 YAML front matter 返Back空String"""
        # Arrange
        content = "# Just content\nNo frontmatter"

        # Act
        result = base_service._extract_yaml_description(content)

        # Assert
        assert result == ""

    def test_extract_yaml_description_no_description_field(self, base_service):
        """Testing：無 description 欄位返Back空String"""
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
    """Plugin JSON MoreNewTesting"""

    def test_update_plugin_json_success(self, base_service, tmp_path):
        """Testing：MoreNew plugin.json Successfully"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)

        # Building commands 和 agents Catalog
        commands_dir = template_dir / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        (commands_dir / "cmd1.md").write_text("command 1")
        (commands_dir / "cmd2.md").write_text("command 2")

        agents_dir = template_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        (agents_dir / "agent1.md").write_text("agent 1")

        # Building plugin.json
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
        """Testing：plugin.json 不存At時不會拋OutAbnormal"""
        # Act
        base_service._update_plugin_json("nonexistent-template")

        # Assert
        # 應該Normal執行，不拋OutAbnormal
        # 只會RecordWarnLog


# ============================================================================
# Template Retrieval Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateRetrieval:
    """Template檢索Testing"""

    def test_get_template_success(self, base_service, mock_db_session, mock_template_db):
        """Testing：GetTemplateSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Act
        result = base_service._get_template("test-template")

        # Assert
        assert result == mock_template_db

    def test_get_template_not_found(self, base_service, mock_db_session):
        """Testing：Get不存At的Template返Back None"""
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
    """Back應ConstructingTesting"""

    def test_response_template_not_found(self, base_service):
        """Testing：BuildingTemplate不存At的Back應"""
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
        """Testing：BuildingTemplate不存At的Back應（含Listing表Data）"""
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
        """Testing：Template與檔名VerifyingSuccessfully"""
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
        """Testing：Template不存At時返BackIncorrectlyBack應"""
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
        """Testing：Invalid檔名時返BackIncorrectlyBack應"""
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
    """ConstantTesting"""

    def test_max_file_size_bytes(self, base_service):
        """Testing：FileSizeLimitationConstant"""
        assert base_service.MAX_FILE_SIZE_BYTES == 1024 * 1024

    def test_max_template_file_size_bytes(self, base_service):
        """Testing：TemplateFileSizeLimitationConstant"""
        assert base_service.MAX_TEMPLATE_FILE_SIZE_BYTES == 10 * 1024 * 1024

    def test_max_upload_files(self, base_service):
        """Testing：MostBigAbove傳File數Constant"""
        assert base_service.MAX_UPLOAD_FILES == 50

    def test_allowed_extensions(self, base_service):
        """Testing：Allowing的副檔名Set"""
        assert '.md' in base_service.ALLOWED_EXTENSIONS
        assert '.txt' in base_service.ALLOWED_EXTENSIONS
        assert '.py' in base_service.ALLOWED_EXTENSIONS
        assert '.json' in base_service.ALLOWED_EXTENSIONS
        assert '.yaml' in base_service.ALLOWED_EXTENSIONS
