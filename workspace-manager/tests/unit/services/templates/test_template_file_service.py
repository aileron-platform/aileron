"""TemplateFileService 單元Testing"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.file_management import (
    FileNotFoundException,
    FileAlreadyExistsException,
    InvalidScopeException,
    InvalidPathException,
    FileTooLargeException,
    DirectoryNotEmptyException,
)
from app.core.file_management import FileSearchRequest
from app.db.models import Template as TemplateDB
from app.services.template_file_service import TemplateFileService


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
def file_service(mock_db_session, tmp_path):
    """TemplateFileService Instance"""
    with patch('app.config.settings.get_settings') as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateFileService(mock_db_session)
        service.storage_path = tmp_path
        return service


# ============================================================================
# Scope Validation Tests
# ============================================================================

@pytest.mark.unit
class TestScopeValidation:
    """Scope VerifyingTesting"""

    def test_validate_scope_scripts_default(self, file_service):
        """Testing：Default scope 為 scripts"""
        # Act
        result = file_service._validate_scope(None)

        # Assert
        assert result == "scripts"

    def test_validate_scope_valid_skills(self, file_service):
        """Testing：Valid scope - skills"""
        # Act
        result = file_service._validate_scope("skills")

        # Assert
        assert result == "skills"

    def test_validate_scope_valid_scripts(self, file_service):
        """Testing：Valid scope - scripts"""
        # Act
        result = file_service._validate_scope("scripts")

        # Assert
        assert result == "scripts"

    def test_validate_scope_invalid(self, file_service):
        """Testing：Invalid scope 拋OutAbnormal"""
        # Act & Assert
        with pytest.raises(InvalidScopeException):
            file_service._validate_scope("invalid")


# ============================================================================
# Path Validation Tests
# ============================================================================

@pytest.mark.unit
class TestPathValidation:
    """Road徑VerifyingTesting"""

    def test_validate_path_empty(self, file_service):
        """Testing：空Road徑返Back空String"""
        # Act
        result = file_service._validate_path("")

        # Assert
        assert result == ""

    def test_validate_path_with_leading_slash(self, file_service):
        """Testing：RemoveOn頭斜Line"""
        # Act
        result = file_service._validate_path("/path/to/file")

        # Assert
        assert result == "path/to/file"

    def test_validate_path_traversal(self, file_service):
        """Testing：檢測Road徑穿越Attacking"""
        # Act & Assert
        with pytest.raises(InvalidPathException):
            file_service._validate_path("../../../etc/passwd")

    def test_validate_path_normal(self, file_service):
        """Testing：NormalRoad徑VerifyingSuccessfully"""
        # Act
        result = file_service._validate_path("path/to/file.txt")

        # Assert
        assert result == "path/to/file.txt"


# ============================================================================
# Path Resolution Tests
# ============================================================================

@pytest.mark.unit
class TestPathResolution:
    """Road徑解析Testing"""

    def test_resolve_path_root(self, file_service, tmp_path):
        """Testing：解析根Road徑"""
        # Act
        result = file_service._resolve_path("test-template", "scripts", "/")

        # Assert
        expected = tmp_path / "templates" / "test-template" / "scripts"
        assert result == expected

    def test_resolve_path_with_subdirectory(self, file_service, tmp_path):
        """Testing：解析子CatalogRoad徑"""
        # Act
        result = file_service._resolve_path("test-template", "scripts", "subdir/file.txt")

        # Assert
        expected = tmp_path / "templates" / "test-template" / "scripts" / "subdir" / "file.txt"
        assert result == expected


# ============================================================================
# File Tree Tests
# ============================================================================

@pytest.mark.unit
class TestFileTree:
    """FileTreeTesting"""

    def test_get_tree_empty_directory(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Get空CatalogTree"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Act
        result = file_service.get_tree("test-template", "/", "scripts")

        # Assert
        assert result.scope == "scripts"
        assert result.path == "/"
        assert result.total == 0
        assert len(result.nodes) == 0

    def test_get_tree_with_files(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Get含File的CatalogTree"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # BuildingTestingFile
        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "file1.py").write_text("content1")
        (scripts_dir / "file2.js").write_text("content2")

        # Act
        result = file_service.get_tree("test-template", "/", "scripts")

        # Assert
        assert result.total == 2
        assert len(result.nodes) == 2

    def test_get_tree_template_not_found(self, file_service, mock_db_session):
        """Testing：Template不存At拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(FileNotFoundException):
            file_service.get_tree("nonexistent-template", "/", "scripts")


# ============================================================================
# File Read Tests
# ============================================================================

@pytest.mark.unit
class TestFileRead:
    """FileReadTesting"""

    def test_read_file_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：ReadFileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # BuildingTestingFile
        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        test_file = scripts_dir / "test.py"
        test_content = "print('Hello World')"
        test_file.write_text(test_content, encoding="utf-8")

        # Act
        result = file_service.read_file("test-template", "/test.py", "scripts")

        # Assert
        assert result.path == "/test.py"
        assert result.scope == "scripts"
        assert result.content == test_content
        assert result.size == len(test_content.encode("utf-8"))

    def test_read_file_not_found(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Read不存At的File拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Act & Assert
        with pytest.raises(FileNotFoundException):
            file_service.read_file("test-template", "/nonexistent.py", "scripts")

    def test_read_file_too_large(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Read過BigFile拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        test_file = scripts_dir / "large.txt"
        # BuildingExceedLimitation的File
        test_file.write_bytes(b"x" * (file_service.MAX_FILE_SIZE + 1))

        # Act & Assert
        with pytest.raises(FileTooLargeException):
            file_service.read_file("test-template", "/large.txt", "scripts")


# ============================================================================
# File Write Tests
# ============================================================================

@pytest.mark.unit
class TestFileWrite:
    """FileWriteTesting"""

    def test_write_file_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：WriteFileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        content = "print('Hello World')"

        # Act
        result = file_service.write_file("test-template", "/test.py", content, "scripts")

        # Assert
        assert "updatedAt" in result
        assert "versionId" in result
        assert "size" in result
        assert result["size"] == len(content.encode("utf-8"))

        # VerifyingFileActuallyWrite
        test_file = scripts_dir / "test.py"
        assert test_file.exists()
        assert test_file.read_text() == content

    def test_write_file_too_large(self, file_service, mock_db_session, mock_template_db):
        """Testing：Write過BigFile拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        content = "x" * (file_service.MAX_FILE_SIZE + 1)

        # Act & Assert
        with pytest.raises(FileTooLargeException):
            file_service.write_file("test-template", "/large.txt", content, "scripts")

    def test_write_file_with_version_check(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Bringing版本CheckWriteFile"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # 先Write初始Within容
        initial_content = "initial content"
        test_file = scripts_dir / "test.py"
        test_file.write_text(initial_content, encoding="utf-8")

        # 計算Correctly的版本 ID
        content_hash = hashlib.sha256(initial_content.encode("utf-8")).hexdigest()
        version_id = content_hash[:16]

        new_content = "updated content"

        # Act
        result = file_service.write_file(
            "test-template",
            "/test.py",
            new_content,
            "scripts",
            expected_version_id=version_id
        )

        # Assert
        assert result is not None
        assert test_file.read_text() == new_content


# ============================================================================
# File Create/Delete Tests
# ============================================================================

@pytest.mark.unit
class TestFileCreateDelete:
    """FileBuildingDeleteTesting"""

    def test_create_file_entry(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：BuildingFileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Act
        result = file_service.create_entry(
            "test-template",
            "/newfile.py",
            "file",
            "scripts",
            "print('new file')"
        )

        # Assert
        assert result["type"] == "file"
        assert "createdAt" in result
        test_file = scripts_dir / "newfile.py"
        assert test_file.exists()

    def test_create_directory_entry(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：BuildingCatalogSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Act
        result = file_service.create_entry(
            "test-template",
            "/newdir",
            "directory",
            "scripts"
        )

        # Assert
        assert result["type"] == "directory"
        test_dir = scripts_dir / "newdir"
        assert test_dir.exists()
        assert test_dir.is_dir()

    def test_create_entry_already_exists(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Building已存At的條目拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "existing.py").write_text("exists")

        # Act & Assert
        with pytest.raises(FileAlreadyExistsException):
            file_service.create_entry(
                "test-template",
                "/existing.py",
                "file",
                "scripts"
            )

    def test_delete_file_entry(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：DeleteFileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        test_file = scripts_dir / "test.py"
        test_file.write_text("content")

        # Act
        result = file_service.delete_entry("test-template", "/test.py", "scripts")

        # Assert
        assert result["type"] == "file"
        assert not test_file.exists()

    def test_delete_directory_not_empty(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Delete非空Catalog（不遞迴）拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        test_dir = scripts_dir / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        # Act & Assert
        with pytest.raises(DirectoryNotEmptyException):
            file_service.delete_entry("test-template", "/testdir", "scripts", recursive=False)

    def test_delete_directory_recursive(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：遞迴DeleteCatalogSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        test_dir = scripts_dir / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content")

        # Act
        result = file_service.delete_entry("test-template", "/testdir", "scripts", recursive=True)

        # Assert
        assert result["type"] == "directory"
        assert not test_dir.exists()


# ============================================================================
# File Copy/Move Tests
# ============================================================================

@pytest.mark.unit
class TestFileCopyMove:
    """FileCopy移動Testing"""

    def test_copy_file_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：CopyFileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        source_file = scripts_dir / "source.py"
        source_file.write_text("source content")

        # Act
        result = file_service.copy_entry(
            "test-template",
            "/source.py",
            "/dest.py",
            "scripts"
        )

        # Assert
        assert result["type"] == "file"
        dest_file = scripts_dir / "dest.py"
        assert dest_file.exists()
        assert dest_file.read_text() == "source content"
        assert source_file.exists()  # 原File仍存At

    def test_move_file_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：移動FileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        source_file = scripts_dir / "source.py"
        source_file.write_text("source content")

        # Act
        result = file_service.move_entry(
            "test-template",
            "/source.py",
            "/dest.py",
            "scripts"
        )

        # Assert
        assert result["type"] == "file"
        dest_file = scripts_dir / "dest.py"
        assert dest_file.exists()
        assert dest_file.read_text() == "source content"
        assert not source_file.exists()  # 原File已Remove

    def test_copy_file_already_exists(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：CopyTo已存At的Goal拋OutAbnormal"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "source.py").write_text("source")
        (scripts_dir / "dest.py").write_text("dest")

        # Act & Assert
        with pytest.raises(FileAlreadyExistsException):
            file_service.copy_entry(
                "test-template",
                "/source.py",
                "/dest.py",
                "scripts",
                overwrite=False
            )


# ============================================================================
# Batch Operations Tests
# ============================================================================

@pytest.mark.unit
class TestBatchOperations:
    """批次OperationTesting"""

    def test_batch_delete_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：批次DeleteSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "file1.py").write_text("content1")
        (scripts_dir / "file2.py").write_text("content2")
        (scripts_dir / "file3.py").write_text("content3")

        # Act
        result = file_service.batch_delete(
            "test-template",
            ["/file1.py", "/file2.py", "/file3.py"],
            "scripts"
        )

        # Assert
        assert result.failed == 0
        assert result.total == 3
        assert result.succeeded == 3

    def test_batch_delete_partial_failure(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：批次DeletePartUnsuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "file1.py").write_text("content1")
        # file2.py 不存At

        # Act
        result = file_service.batch_delete(
            "test-template",
            ["/file1.py", "/file2.py"],
            "scripts"
        )

        # Assert
        assert result.failed > 0
        assert result.total == 2
        assert result.succeeded == 1
        assert result.failed == 1


# ============================================================================
# File Upload Tests
# ============================================================================

@pytest.mark.unit
class TestFileUpload:
    """FileAbove傳Testing"""

    @pytest.mark.asyncio
    async def test_upload_files_success(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Above傳FileSuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Building mock UploadFile
        mock_file = AsyncMock()
        mock_file.filename = "test.py"
        mock_file.read = AsyncMock(return_value=b"print('test')")

        # Act
        result = await file_service.upload_files(
            "test-template",
            "/",
            [mock_file],
            overwrite=False,
            scope="scripts"
        )

        # Assert
        assert result.failed == 0
        assert result.succeeded == 1

    @pytest.mark.asyncio
    async def test_upload_files_too_many(self, file_service, mock_db_session, mock_template_db):
        """Testing：Above傳過ManyFileUnsuccessfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # BuildingExceedLimitationQuantity的 mock File
        mock_files = [AsyncMock() for _ in range(file_service.MAX_UPLOAD_FILES + 1)]

        # Act
        result = await file_service.upload_files(
            "test-template",
            "/",
            mock_files,
            scope="scripts"
        )

        # Assert
        assert result.success is False
        assert "Too many files" in result.message


# ============================================================================
# File Search Tests
# ============================================================================

@pytest.mark.unit
class TestFileSearch:
    """FileSearchTesting"""

    def test_search_files_by_name(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：按檔名Search"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "test.py").write_text("content")
        (scripts_dir / "example.js").write_text("content")
        (scripts_dir / "test-file.md").write_text("content")

        search_request = FileSearchRequest(
            query="test",
            searchContent=False,
            maxResults=10
        )

        # Act
        result = file_service.search_files("test-template", search_request, "scripts")

        # Assert
        assert result.total >= 2
        file_names = [r.name for r in result.results]
        assert "test.py" in file_names
        assert "test-file.md" in file_names

    def test_search_files_by_content(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：按Within容Search"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "file1.py").write_text("This contains the search term")
        (scripts_dir / "file2.py").write_text("No match here")

        search_request = FileSearchRequest(
            query="search term",
            searchContent=True,
            maxResults=10
        )

        # Act
        result = file_service.search_files("test-template", search_request, "scripts")

        # Assert
        assert result.total >= 1
        found = any(r.name == "file1.py" for r in result.results)
        assert found

    def test_search_files_empty_result(self, file_service, mock_db_session, mock_template_db, tmp_path):
        """Testing：Search無Result"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        scripts_dir = tmp_path / "templates" / "test-template" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)

        search_request = FileSearchRequest(
            query="nonexistent",
            searchContent=False,
            maxResults=10
        )

        # Act
        result = file_service.search_files("test-template", search_request, "scripts")

        # Assert
        assert result.total == 0
        assert len(result.results) == 0


# ============================================================================
# Validation Tests
# ============================================================================

@pytest.mark.unit
class TestValidation:
    """VerifyingTesting"""

    def test_validate_filename_valid(self, file_service):
        """Testing：Valid檔名Verifying"""
        # Arrange
        valid_names = ["test.py", "example.js", "data.json"]

        # Act & Assert
        for name in valid_names:
            assert file_service._validate_filename(name) is True

    def test_validate_filename_invalid_path_separators(self, file_service):
        """Testing：包含Road徑Minute隔符的檔名Invalid"""
        # Arrange
        invalid_names = ["path/file.py", "path\\file.py"]

        # Act & Assert
        for name in invalid_names:
            assert file_service._validate_filename(name) is False

    def test_validate_filename_hidden_files(self, file_service):
        """Testing：HideFileInvalid"""
        # Act & Assert
        assert file_service._validate_filename(".hidden") is False

    def test_validate_filename_special_characters(self, file_service):
        """Testing：Special字符Invalid"""
        # Arrange
        invalid_names = ['file<>.py', 'file:name.py', 'file|name.py']

        # Act & Assert
        for name in invalid_names:
            assert file_service._validate_filename(name) is False
