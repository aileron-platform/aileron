"""Unit Tests for TemplateService"""

from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import yaml

from app.db.models import Template as TemplateDB
from app.models import (
    Template,
    TemplateAuthor,
    TemplateCreate,
    TemplateUpdate,
    TemplateListResponse,
)
from app.services.template_service import TemplateService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.query = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.delete = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def mock_template_db():
    """Sample Template Database Model"""
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
        status="released",
        keywords=["test", "example"],
        init_commands="echo 'Hello'",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_template_create():
    """Sample Template Create Request"""
    return TemplateCreate(
        template_id="new-template",
        name="New Template",
        description="A new template",
        author=TemplateAuthor(
            name="Author Name",
            email="author@example.com",
            url="https://example.com"
        ),
        version="1.0.0",
        cli_type="claude-code",
        status="draft",
        keywords=["new", "template"],
        init_commands="echo 'Init'"
    )


@pytest.fixture
def template_service(mock_db_session, tmp_path):
    """TemplateService Instance"""
    with patch('app.services.template_service.get_settings') as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateService(mock_db_session)
        service.storage_path = tmp_path
        return service


# ============================================================================
# Template CRUD Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateCRUD:
    """Template CRUD Operations Tests"""

    def test_list_templates_success(self, template_service, mock_db_session, mock_template_db):
        """Test: List all templates successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_template_db]
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_db_to_pydantic') as mock_convert:
            mock_convert.return_value = Template(
                id="test-template",
                name="Test Template",
                description="A test template",
                author=TemplateAuthor(name="Test Author", email="test@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )

            # Act
            result = template_service.list(page=1, limit=20)

            # Assert
            assert isinstance(result, TemplateListResponse)
            assert result.total == 1
            assert result.page == 1
            assert result.limit == 20
            assert len(result.items) == 1

    def test_list_templates_with_filters(self, template_service, mock_db_session, mock_template_db):
        """Test: List templates with filters"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_template_db]
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_db_to_pydantic') as mock_convert:
            mock_convert.return_value = Template(
                id="test-template",
                name="Test Template",
                description="A test template",
                author=TemplateAuthor(name="Test Author", email="test@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )

            # Act
            result = template_service.list(
                category="general",
                cli_type="claude-code",
                search="test",
                page=1,
                limit=10
            )

            # Assert
            assert result.total == 1
            assert len(result.items) == 1
            assert mock_query.filter.called

    def test_get_template_success(self, template_service, mock_db_session, mock_template_db):
        """Test: Get single template successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_db_to_pydantic') as mock_convert:
            expected_template = Template(
                id="test-template",
                name="Test Template",
                description="A test template",
                author=TemplateAuthor(name="Test Author", email="test@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )
            mock_convert.return_value = expected_template

            # Act
            result = template_service.get("test-template")

            # Assert
            assert result == expected_template
            mock_db_session.query.assert_called_once()

    def test_get_template_not_found(self, template_service, mock_db_session):
        """Test: Get nonexistent template returns None"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act
        result = template_service.get("nonexistent-template")

        # Assert
        assert result is None

    def test_create_template_success(self, template_service, mock_db_session, mock_template_create, tmp_path):
        """Test: Create new template successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_create_template_structure'), \
             patch.object(template_service, '_db_to_pydantic') as mock_convert:

            expected_template = Template(
                id="new-template",
                name="New Template",
                description="A new template",
                author=TemplateAuthor(name="Author Name", email="author@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )
            mock_convert.return_value = expected_template

            # Act
            result = template_service.create(mock_template_create)

            # Assert
            assert result == expected_template
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called()

    def test_create_template_duplicate_id(self, template_service, mock_db_session, mock_template_create, mock_template_db):
        """Test: Create template with duplicate ID unsuccessful"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(ValueError, match="already exists"):
            template_service.create(mock_template_create)

    def test_create_template_invalid_id_format(self, template_service, mock_db_session):
        """Test: Create template with invalid ID format unsuccessful"""
        # Arrange
        invalid_template = TemplateCreate(
            template_id="Invalid_Template_123",  # Invalid kebab-case
            name="Invalid Template",
            description="Invalid",
            author=TemplateAuthor(name="Author", email="author@example.com"),
            version="1.0.0",
            cli_type="claude-code",
            status="released"
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act & Assert
        with pytest.raises(ValueError, match="kebab-case"):
            template_service.create(invalid_template)

    def test_update_template_success(self, template_service, mock_db_session, mock_template_db):
        """Test: Update template successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        update_data = TemplateUpdate(
            name="Updated Template",
            description="Updated description"
        )

        with patch.object(template_service, '_db_to_pydantic') as mock_convert:
            expected_template = Template(
                id="test-template",
                name="Updated Template",
                description="Updated description",
                author=TemplateAuthor(name="Test Author", email="test@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )
            mock_convert.return_value = expected_template

            # Act
            result = template_service.update("test-template", update_data)

            # Assert
            assert result == expected_template
            assert mock_template_db.name == "Updated Template"
            assert mock_template_db.description == "Updated description"
            assert mock_db_session.commit.call_count >= 1

    def test_update_template_not_found(self, template_service, mock_db_session):
        """Test: Update nonexistent template returns None"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        update_data = TemplateUpdate(name="Updated")

        # Act
        result = template_service.update("nonexistent-template", update_data)

        # Assert
        assert result is None

    def test_delete_template_success(self, template_service, mock_db_session, mock_template_db, tmp_path):
        """Test: Delete template successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Create template directory
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)

        with patch.object(template_service, '_delete_template_structure'):
            # Act
            result = template_service.delete("test-template")

            # Assert
            assert result is True
            mock_db_session.delete.assert_called_once_with(mock_template_db)
            mock_db_session.commit.assert_called_once()

    def test_delete_template_not_found(self, template_service, mock_db_session):
        """Test: Delete nonexistent template returns False"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        # Act
        result = template_service.delete("nonexistent-template")

        # Assert
        assert result is False


# ============================================================================
# Template Import/Export Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateImportExport:
    """Template Import/Export Tests"""

    def test_export_template_success(self, template_service, mock_db_session, mock_template_db, tmp_path):
        """Test: Export template successfully"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        # Create template directory and files
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "test.txt").write_text("test content")

        with patch.object(template_service, '_get_template') as mock_get:
            mock_get.return_value = mock_template_db

            # Act
            result = template_service.export_template("test-template")

            # Assert
            assert result is not None
            assert result.exists()
            assert result.suffix == ".zip"

    def test_export_template_not_found(self, template_service, mock_db_session):
        """Test: Export nonexistent template returns None"""
        # Arrange
        with patch.object(template_service, '_get_template') as mock_get:
            mock_get.return_value = None

            # Act
            result = template_service.export_template("nonexistent-template")

            # Assert
            assert result is None

    @pytest.mark.asyncio
    async def test_import_template_success(
        self, template_service, mock_db_session, tmp_path, upload_file_factory
    ):
        """Test: Import template successfully"""
        # Arrange
        # Create ZIP file
        zip_path = tmp_path / "test-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            manifest_data = {
                "id": "imported-template",
                "name": "Imported Template",
                "description": "An imported template",
                "version": "1.0.0",
                "author": {"name": "Author", "email": "author@example.com"},
                "cli_type": "claude-code",
                "status": "active"
            }
            zipf.writestr(".claude-plugin/manifest.json", json.dumps(manifest_data))

        # Create mock UploadFile
        mock_file = upload_file_factory("test-template.zip", zip_path.read_bytes())

        with patch.object(template_service, '_get_template') as mock_get, \
             patch.object(template_service, '_db_to_pydantic') as mock_convert:

            mock_get.return_value = None
            expected_template = Template(
                id="imported-template",
                name="Imported Template",
                description="An imported template",
                author=TemplateAuthor(name="Author", email="author@example.com"),
                version="1.0.0",
                cliType="claude-code",
                status="released"
            )
            mock_convert.return_value = expected_template

            # Act
            result = await template_service.import_template(mock_file, overwrite=False)

            # Assert
            assert result == expected_template
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_import_template_missing_package_manifest(self, template_service, tmp_path):
        """Test: Import template missing manifest.json unsuccessful"""
        # Arrange
        zip_path = tmp_path / "invalid-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr("test.txt", "test content")

        mock_file = AsyncMock()
        mock_file.filename = "invalid-template.zip"
        mock_file.read = AsyncMock(return_value=zip_path.read_bytes())

        # Act & Assert
        with pytest.raises(ValueError, match="missing .claude-plugin/manifest.json"):
            await template_service.import_template(mock_file)

    @pytest.mark.asyncio
    async def test_import_template_rejects_legacy_marketplace_json_only(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Legacy marketplace.json requires manifest.json"""
        zip_path = tmp_path / "legacy-marketplace-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/marketplace.json",
                json.dumps({"id": "legacy-marketplace-template"}),
            )

        mock_file = upload_file_factory("legacy-marketplace-template.zip", zip_path.read_bytes())

        with pytest.raises(ValueError, match="missing .claude-plugin/manifest.json"):
            await template_service.import_template(mock_file)

    @pytest.mark.asyncio
    async def test_import_template_prefers_manifest_json_when_legacy_file_also_exists(
        self, template_service, mock_db_session, tmp_path, upload_file_factory
    ):
        """Test: Use manifest.json when both manifest.json and marketplace.json exist"""
        zip_path = tmp_path / "dual-manifest-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps({"id": "manifest-template", "name": "Manifest Template"}),
            )
            zipf.writestr(
                ".claude-plugin/marketplace.json",
                json.dumps({"id": "legacy-template", "name": "Legacy Template"}),
            )

        mock_file = upload_file_factory("dual-manifest-template.zip", zip_path.read_bytes())

        created_templates: list[TemplateDB] = []
        mock_db_session.add.side_effect = created_templates.append

        with patch.object(template_service, "_get_template", return_value=None), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.side_effect = lambda db_template: Template(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                author=TemplateAuthor(name=db_template.author_name, email=db_template.author_email),
                version=db_template.version,
                cliType=db_template.cli_type,
                status=db_template.status,
            )

            result = await template_service.import_template(mock_file)

        assert result.id == "manifest-template"
        assert result.name == "Manifest Template"
        assert created_templates[0].id == "manifest-template"

    @pytest.mark.asyncio
    async def test_import_template_missing_id(self, template_service, tmp_path, upload_file_factory):
        """Test: Missing id in manifest.json causes failure"""
        zip_path = tmp_path / "missing-id-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps({"name": "Missing Id Template"}),
            )

        mock_file = upload_file_factory("missing-id-template.zip", zip_path.read_bytes())

        with pytest.raises(ValueError, match="manifest.json missing id field"):
            await template_service.import_template(mock_file)

    @pytest.mark.asyncio
    async def test_import_template_overwrite_updates_existing_template(
        self, template_service, mock_db_session, mock_template_db, tmp_path, upload_file_factory
    ):
        """Test: Overwrite import updates existing template and files"""
        zip_path = tmp_path / "overwrite-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            plugin_data = {
                "id": "test-template",
                "name": "Updated Imported Template",
                "description": "Updated description",
                "author": {"name": "Updated Author", "email": "updated@example.com"},
            }
            zipf.writestr(".claude-plugin/manifest.json", json.dumps(plugin_data))
            zipf.writestr("commands/new-command.md", "content")

        existing_dir = tmp_path / "templates" / "test-template"
        existing_dir.mkdir(parents=True, exist_ok=True)
        (existing_dir / "old.txt").write_text("stale content")

        mock_file = upload_file_factory("overwrite-template.zip", zip_path.read_bytes())

        with patch.object(template_service, "_get_template", return_value=mock_template_db), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.return_value = Template(
                id="test-template",
                name="Updated Imported Template",
                description="Updated description",
                author=TemplateAuthor(name="Updated Author", email="updated@example.com"),
                version=mock_template_db.version,
                cliType=mock_template_db.cli_type,
                status=mock_template_db.status,
            )

            result = await template_service.import_template(mock_file, overwrite=True)

        assert result.name == "Updated Imported Template"
        assert mock_template_db.name == "Updated Imported Template"
        assert mock_template_db.author_name == "Updated Author"
        assert mock_template_db.author_email == "updated@example.com"
        assert mock_template_db.author_url is None
        assert not (existing_dir / "old.txt").exists()
        assert (existing_dir / "commands" / "new-command.md").exists()
        mock_db_session.commit.assert_called()
        mock_db_session.refresh.assert_called_once_with(mock_template_db)

    @pytest.mark.asyncio
    async def test_import_template_new_template_uses_defaults(
        self, template_service, mock_db_session, tmp_path, upload_file_factory
    ):
        """Test: Import new template applies default field values"""
        zip_path = tmp_path / "defaults-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps({"id": "defaulted-template"}),
            )

        mock_file = upload_file_factory("defaults-template.zip", zip_path.read_bytes())

        created_templates: list[TemplateDB] = []

        def capture_add(template: TemplateDB) -> None:
            created_templates.append(template)

        mock_db_session.add.side_effect = capture_add

        with patch.object(template_service, "_get_template", return_value=None), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.side_effect = lambda db_template: Template(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                author=TemplateAuthor(name=db_template.author_name, email=db_template.author_email),
                version=db_template.version,
                cliType=db_template.cli_type,
                status=db_template.status,
            )

            result = await template_service.import_template(mock_file)

        assert result.id == "defaulted-template"
        assert created_templates
        created = created_templates[0]
        assert created.name == "Unnamed Template"
        assert created.author_name == "Unknown"
        assert created.version == "1.0.0"
        assert created.cli_type == "claude-code"
        assert created.status == "draft"

    @pytest.mark.asyncio
    async def test_import_template_normalizes_legacy_status_and_cli_type(
        self, template_service, mock_db_session, tmp_path, upload_file_factory
    ):
        """Test: Import normalizes legacy status/cli_type to database acceptable values"""
        zip_path = tmp_path / "legacy-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps(
                    {
                        "id": "legacy-template",
                        "status": "active",
                        "cli_type": "claude",
                    }
                ),
            )

        mock_file = upload_file_factory("legacy-template.zip", zip_path.read_bytes())

        created_templates: list[TemplateDB] = []

        def capture_add(template: TemplateDB) -> None:
            created_templates.append(template)

        mock_db_session.add.side_effect = capture_add

        with patch.object(template_service, "_get_template", return_value=None), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.side_effect = lambda db_template: Template(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                author=TemplateAuthor(name=db_template.author_name, email=db_template.author_email),
                version=db_template.version,
                cliType=db_template.cli_type,
                status=db_template.status,
            )

            result = await template_service.import_template(mock_file)

        assert result.cliType == "claude-code"
        assert result.status == "released"
        assert created_templates[0].cli_type == "claude-code"
        assert created_templates[0].status == "released"

    @pytest.mark.asyncio
    async def test_import_template_supports_single_root_directory_zip(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Import supports ZIP containing single template root directory"""
        zip_path = tmp_path / "nested-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                "nested-template/.claude-plugin/manifest.json",
                json.dumps({"id": "nested-template"}),
            )

        mock_file = upload_file_factory("nested-template.zip", zip_path.read_bytes())

        with patch.object(template_service, "_get_template", return_value=None), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.side_effect = lambda db_template: Template(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                author=TemplateAuthor(name=db_template.author_name, email=db_template.author_email),
                version=db_template.version,
                cliType=db_template.cli_type,
                status=db_template.status,
            )

            result = await template_service.import_template(mock_file)

        assert result.id == "nested-template"

    @pytest.mark.asyncio
    async def test_import_template_normalizes_claudecode_cli_type(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Import supports legacy ClaudeCode cli_type"""
        zip_path = tmp_path / "claudecode-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps({"id": "claudecode-template", "cli_type": "ClaudeCode"}),
            )

        mock_file = upload_file_factory("claudecode-template.zip", zip_path.read_bytes())

        with patch.object(template_service, "_get_template", return_value=None), \
             patch.object(template_service, "_db_to_pydantic") as mock_convert:
            mock_convert.side_effect = lambda db_template: Template(
                id=db_template.id,
                name=db_template.name,
                description=db_template.description,
                author=TemplateAuthor(name=db_template.author_name, email=db_template.author_email),
                version=db_template.version,
                cliType=db_template.cli_type,
                status=db_template.status,
            )

            result = await template_service.import_template(mock_file)

        assert result.cliType == "claude-code"

    @pytest.mark.asyncio
    async def test_import_template_rejects_invalid_cli_type_with_friendly_message(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Invalid cli_type returns clear error message"""
        zip_path = tmp_path / "invalid-cli-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(
                ".claude-plugin/manifest.json",
                json.dumps({"id": "invalid-cli-template", "cli_type": "foobar"}),
            )

        mock_file = upload_file_factory("invalid-cli-template.zip", zip_path.read_bytes())

        with pytest.raises(ValueError, match="cli_type is invalid"):
            await template_service.import_template(mock_file)

    @pytest.mark.asyncio
    async def test_import_template_rejects_invalid_json_with_friendly_message(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Invalid manifest.json returns clear error message"""
        zip_path = tmp_path / "invalid-json-template.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.writestr(".claude-plugin/manifest.json", "{invalid json")

        mock_file = upload_file_factory("invalid-json-template.zip", zip_path.read_bytes())

        with pytest.raises(ValueError, match="manifest.json is not valid JSON"):
            await template_service.import_template(mock_file)

    @pytest.mark.asyncio
    async def test_import_template_rejects_bad_zip_with_friendly_message(
        self, template_service, tmp_path, upload_file_factory
    ):
        """Test: Corrupted ZIP returns clear error message"""
        bad_zip_path = tmp_path / "broken-template.zip"
        bad_zip_path.write_bytes(b"not a real zip file")

        mock_file = upload_file_factory("broken-template.zip", bad_zip_path.read_bytes())

        with pytest.raises(ValueError, match="ZIP file is corrupted or invalid format"):
            await template_service.import_template(mock_file)


# ============================================================================
# Template Structure Tests
# ============================================================================

@pytest.mark.unit
class TestTemplateStructure:
    """Template Structure Management Tests"""

    def test_create_template_structure(self, template_service, mock_template_create, tmp_path):
        """Test: Create template file structure"""
        # Act
        template_service._create_template_structure("new-template", mock_template_create)

        # Assert
        template_dir = tmp_path / "templates" / "new-template"
        assert template_dir.exists()
        assert (template_dir / "commands").exists()
        assert (template_dir / "agents").exists()
        assert (template_dir / "skills").exists()
        assert (template_dir / "hooks").exists()
        assert (template_dir / "mcp").exists()
        assert (template_dir / "resources" / "scripts").exists()
        assert (template_dir / "template.yaml").exists()

        template_yaml_path = template_dir / "template.yaml"
        assert template_yaml_path.exists()

        # Verify template.yaml content
        template_data = yaml.safe_load(template_yaml_path.read_text())
        assert template_data["id"] == "new-template"
        assert template_data["name"] == "New Template"

    def test_delete_template_structure(self, template_service, tmp_path):
        """Test: Delete template file structure"""
        # Arrange
        template_dir = tmp_path / "templates" / "test-template"
        template_dir.mkdir(parents=True, exist_ok=True)
        (template_dir / "test.txt").write_text("test")

        # Act
        template_service._delete_template_structure("test-template")

        # Assert
        assert not template_dir.exists()


# ============================================================================
# Service Delegation Tests
# ============================================================================

@pytest.mark.unit
class TestServiceDelegation:
    """Service Delegation Tests"""

    def test_get_mcp_config_delegation(self, template_service):
        """Test: MCP config delegation"""
        # Arrange
        with patch.object(template_service.mcp_service, 'get_mcp_config') as mock_method:
            mock_method.return_value = {"servers": {}}

            # Act
            result = template_service.get_mcp_config("test-template")

            # Assert
            mock_method.assert_called_once_with("test-template")
            assert result == {"servers": {}}

    def test_get_hooks_config_delegation(self, template_service):
        """Test: Hooks config delegation"""
        # Arrange
        with patch.object(template_service.hooks_service, 'get_hooks_config') as mock_method:
            mock_method.return_value = {"hooks": {}}

            # Act
            result = template_service.get_hooks_config("test-template")

            # Assert
            mock_method.assert_called_once_with("test-template")
            assert result == {"hooks": {}}

    def test_get_commands_delegation(self, template_service):
        """Test: Slash Commands delegation"""
        # Arrange
        with patch.object(template_service.commands_service, 'get_commands_files') as mock_method:
            mock_method.return_value = []

            # Act
            result = template_service.get_commands_files("test-template")

            # Assert
            mock_method.assert_called_once_with("test-template")
            assert result == []

    @pytest.mark.parametrize(
        ("service_attr", "service_method", "wrapper_name", "args", "expected_result"),
        [
            ("mcp_service", "update_mcp_config", "update_mcp_config", ("test-template", {"servers": []}), {"ok": True}),
            ("hooks_service", "update_hooks_config", "update_hooks_config", ("test-template", {"hooks": []}), {"ok": True}),
            ("commands_service", "get_command_file_content", "get_command_file_content", ("test-template", "cmd.md"), "command"),
            ("commands_service", "create_command_file", "create_command_file", ("test-template", {"name": "cmd"}), {"created": True}),
            ("commands_service", "update_command_file", "update_command_file", ("test-template", "cmd.md", {"content": "new"}), {"updated": True}),
            ("commands_service", "delete_command_file", "delete_command_file", ("test-template", "cmd.md"), {"deleted": True}),
            ("agents_service", "get_agents_files", "get_agents_files", ("test-template",), ["agent.md"]),
            ("agents_service", "get_agent_file_content", "get_agent_file_content", ("test-template", "agent.md"), "agent"),
            ("agents_service", "create_agent_file", "create_agent_file", ("test-template", {"name": "agent"}), {"created": True}),
            ("agents_service", "update_agent_file", "update_agent_file", ("test-template", "agent.md", {"content": "new"}), {"updated": True}),
            ("agents_service", "delete_agent_file", "delete_agent_file", ("test-template", "agent.md"), {"deleted": True}),
            ("output_style_service", "get_output_style_files", "get_output_style_files", ("test-template",), ["style.md"]),
            ("output_style_service", "get_output_style_file_content", "get_output_style_file_content", ("test-template", "style.md"), "style"),
            ("output_style_service", "create_output_style_file", "create_output_style_file", ("test-template", {"name": "style"}), {"created": True}),
            ("output_style_service", "update_output_style_file", "update_output_style_file", ("test-template", "style.md", {"content": "new"}), {"updated": True}),
            ("output_style_service", "delete_output_style_file", "delete_output_style_file", ("test-template", "style.md"), {"deleted": True}),
            ("file_service", "search_files", "search_files", ("test-template", {"query": "test"}), ["match"]),
            ("agents_md_service", "get_agents_md", "get_agents_md", ("test-template",), "# Claude"),
            ("agents_md_service", "update_agents_md", "update_agents_md", ("test-template", "# Updated"), None),
            ("commands_service", "load_commands", "_load_commands", ("test-template",), ["cmd"]),
            ("agents_service", "load_agents", "_load_agents", ("test-template",), ["agent"]),
            ("output_style_service", "load_output_style", "_load_output_style", ("test-template",), ["style"]),
            ("mcp_service", "load_mcp_servers", "_load_mcp_servers", ("test-template",), {"servers": {}}),
            ("hooks_service", "load_hooks", "_load_hooks", ("test-template",), {"hooks": []}),
            ("file_service", "load_files", "_load_files", ("test-template",), ["file"]),
        ],
    )
    def test_wrapper_delegations(
        self, template_service, service_attr, service_method, wrapper_name, args, expected_result
    ):
        """Test: Wrappers correctly delegate to appropriate sub-services"""
        service = getattr(template_service, service_attr)
        with patch.object(service, service_method, return_value=expected_result) as mock_method:
            result = getattr(template_service, wrapper_name)(*args)

        mock_method.assert_called_once_with(*args)
        assert result == expected_result

    def test_file_wrapper_delegations(self, template_service):
        """Test: File wrappers correctly forward to new file_service API"""
        with patch.object(template_service.file_service, "get_tree", return_value={"nodes": []}) as mock_get_tree, \
             patch.object(template_service.file_service, "read_file", return_value={"content": "file"}) as mock_read_file, \
             patch.object(template_service.file_service, "create_entry", return_value={"created": True}) as mock_create_entry, \
             patch.object(template_service.file_service, "write_file", return_value={"updated": True}) as mock_write_file, \
             patch.object(template_service.file_service, "move_entry", return_value={"type": "file"}) as mock_move_entry, \
             patch.object(template_service.file_service, "copy_entry", return_value={"copied": True}) as mock_copy_entry, \
             patch.object(template_service.file_service, "delete_entry", return_value={"deleted": True}) as mock_delete_entry, \
             patch.object(template_service.file_service, "batch_delete", return_value={"deleted": 2}) as mock_batch_delete:
            assert template_service.get_template_files("test-template", "nested", True, 2, "skills") == {"nodes": []}
            assert template_service.get_file_content("test-template", "nested/file.py", "skills") == {"content": "file"}
            assert template_service.create_file_or_directory(
                "test-template",
                {"path": "dir/new.py", "type": "file", "content": "print(1)"},
                "skills",
            ) == {"created": True}
            assert template_service.update_file_content(
                "test-template",
                {"path": "dir/new.py", "content": "print(2)", "expected_version_id": "abc"},
                "skills",
            ) == {"updated": True}
            assert template_service.rename_file(
                "test-template",
                {"old_path": "dir/old.py", "new_name": "renamed.py"},
                "skills",
            ) == {"type": "file"}
            assert template_service.move_file(
                "test-template",
                {"source_path": "dir/a.py", "target_path": "dst/a.py", "overwrite": True},
                "skills",
            ) == {"type": "file"}
            assert template_service.copy_file(
                "test-template",
                {"source_path": "dir/a.py", "target_path": "dst/a.py", "overwrite": True},
                "skills",
            ) == {"copied": True}
            assert template_service.delete_file("test-template", "old.py", True, "skills") == {"deleted": True}
            assert template_service.batch_delete_files(
                "test-template",
                {"paths": ["a", "b"], "recursive": True},
                "skills",
            ) == {"deleted": 2}

        mock_get_tree.assert_called_once_with(
            "test-template",
            path="nested",
            scope="skills",
            include_hidden=True,
            max_depth=2,
        )
        mock_read_file.assert_called_once_with("test-template", "nested/file.py", scope="skills")
        mock_create_entry.assert_called_once_with(
            "test-template",
            "dir/new.py",
            "file",
            scope="skills",
            content="print(1)",
        )
        mock_write_file.assert_called_once_with(
            "test-template",
            "dir/new.py",
            "print(2)",
            scope="skills",
            expected_version_id="abc",
        )
        assert mock_move_entry.call_args_list[0].args == (
            "test-template",
            "dir/old.py",
            "dir/renamed.py",
        )
        assert mock_move_entry.call_args_list[0].kwargs == {
            "scope": "skills",
            "overwrite": False,
        }
        assert mock_move_entry.call_args_list[1].args == (
            "test-template",
            "dir/a.py",
            "dst/a.py",
        )
        assert mock_move_entry.call_args_list[1].kwargs == {
            "scope": "skills",
            "overwrite": True,
        }
        mock_copy_entry.assert_called_once_with(
            "test-template",
            "dir/a.py",
            "dst/a.py",
            scope="skills",
            overwrite=True,
        )
        mock_delete_entry.assert_called_once_with(
            "test-template",
            "old.py",
            scope="skills",
            recursive=True,
        )
        mock_batch_delete.assert_called_once_with(
            "test-template",
            ["a", "b"],
            scope="skills",
            recursive=True,
        )

    @pytest.mark.asyncio
    async def test_upload_files_delegation(self, template_service):
        """Test: upload_files correctly delegates to file_service"""
        files = [Mock(filename="one.txt")]

        with patch.object(template_service.file_service, "upload_files", new=AsyncMock(return_value={"uploaded": 1})) as mock_method:
            result = await template_service.upload_files(
                "test-template",
                "nested",
                files,
                overwrite=True,
                base_path="skills",
            )

        mock_method.assert_awaited_once_with(
            "test-template",
            "nested",
            files,
            True,
            "skills",
        )
        assert result == {"uploaded": 1}


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """Error Handling Tests"""

    def test_create_template_filesystem_error_rollback(self, template_service, mock_db_session, mock_template_create):
        """Test: Template creation filesystem error rolls back database"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_create_template_structure') as mock_create_fs:
            mock_create_fs.side_effect = Exception("Filesystem error")

            # Act & Assert
            with pytest.raises(Exception, match="Filesystem error"):
                template_service.create(mock_template_create)

            # Verify rollback
            mock_db_session.delete.assert_called_once()
            assert mock_db_session.commit.call_count >= 1

    def test_export_template_with_filesystem_error(self, template_service, mock_db_session, mock_template_db, tmp_path):
        """Test: Handle filesystem errors during template export"""
        # Arrange
        with patch.object(template_service, '_get_template') as mock_get:
            mock_get.return_value = mock_template_db

            # Create directory structure that will cause error
            template_dir = tmp_path / "plugins" / "test-template"
            template_dir.mkdir(parents=True, exist_ok=True)

            with patch('zipfile.ZipFile') as mock_zip:
                mock_zip.side_effect = Exception("ZIP error")

                # Act
                result = template_service.export_template("test-template")

                # Assert
                assert result is None

    def test_list_templates_with_keywords_filter(self, template_service, mock_db_session, mock_template_db):
        """Test: List templates with keyword filter"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_template_db]
        mock_db_session.query.return_value = mock_query

        # Act
        result = template_service.list(keywords="test,example")

        # Assert
        assert result is not None
        assert len(result.items) == 1
        # Verify filter was called for keywords
        assert mock_query.filter.call_count >= 2

    def test_list_templates_with_empty_keywords(self, template_service, mock_db_session, mock_template_db):
        """Test: Filter with empty keywords doesn't error"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [mock_template_db]
        mock_db_session.query.return_value = mock_query

        # Act
        result = template_service.list(keywords="  , ,  ")

        # Assert
        assert result is not None

    def test_update_template_with_author(self, template_service, mock_db_session, mock_template_db):
        """Test: Update template author information"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        update_payload = TemplateUpdate(
            name="Updated Template",
            author=TemplateAuthor(
                name="New Author",
                email="new@example.com",
                url="https://newauthor.com"
            )
        )

        # Act
        result = template_service.update("test-template", update_payload)

        # Assert
        assert result is not None
        assert mock_template_db.author_name == "New Author"
        assert mock_template_db.author_email == "new@example.com"
        assert mock_template_db.author_url == "https://newauthor.com"
        mock_db_session.commit.assert_called()

    def test_delete_template_with_filesystem_error(self, template_service, mock_db_session, mock_template_db, tmp_path):
        """Test: Handle filesystem errors during template deletion"""
        # Arrange
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = mock_template_db
        mock_db_session.query.return_value = mock_query

        with patch.object(template_service, '_delete_template_structure') as mock_delete:
            mock_delete.side_effect = Exception("Filesystem error")

            # Act
            result = template_service.delete("test-template")

            # Assert - should return True even if filesystem deletion fails
            assert result is True
            mock_db_session.delete.assert_called_once_with(mock_template_db)
            mock_db_session.commit.assert_called()

    def test_db_to_pydantic_with_all_configs(self, template_service, mock_template_db):
        """Test: _db_to_pydantic loads all configurations"""
        # Arrange
        with patch.object(template_service.mcp_service, 'load_mcp_servers') as mock_mcp:
            with patch.object(template_service.hooks_service, 'load_hooks') as mock_hooks:
                with patch.object(template_service.commands_service, 'load_commands') as mock_commands:
                    with patch.object(template_service.agents_service, 'load_agents') as mock_agents:
                        with patch.object(template_service.output_style_service, 'load_output_style') as mock_styles:
                            with patch.object(template_service.file_service, 'load_files') as mock_files:
                                mock_mcp.return_value = []
                                mock_hooks.return_value = []
                                mock_commands.return_value = []
                                mock_agents.return_value = []
                                mock_styles.return_value = []
                                mock_files.return_value = []

                                # Act
                                result = template_service._db_to_pydantic(mock_template_db)

                                # Assert
                                assert result is not None
                                assert result.id == "test-template"
                                mock_mcp.assert_called_once_with("test-template")
                                mock_hooks.assert_called_once_with("test-template")
                                mock_commands.assert_called_once_with("test-template")
                                mock_agents.assert_called_once_with("test-template")
                                mock_styles.assert_called_once_with("test-template")
                                mock_files.assert_called_once_with("test-template")
