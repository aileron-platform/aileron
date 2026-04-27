"""Knowledge base file service UnitTest。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.file_management import FileAlreadyExistsException, FileManagementException, FileNotFoundException, FileTooLargeException
from app.db import models as db_models
from app.services.knowledge_base_file_service import KnowledgeBaseFileService
from app.services.knowledge_base_service import KnowledgeBaseAccessDeniedError


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.scalar = MagicMock(return_value=0)
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
    )


@pytest.fixture
def file_service(mock_db_session, kb, tmp_path, monkeypatch):
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path
    service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "editor"})())
    )
    service.settings.KB_ALLOWED_EXTENSIONS = [".md", ".txt", ".json"]
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 10
    service.settings.DEFAULT_KB_QUOTA_BYTES = 20
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100
    return service


@pytest.mark.unit
def test_write_file_rejects_disallowed_extension(file_service):
    with pytest.raises(FileManagementException, match="Unsupported file extension"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/notes.py",
            content="print('x')",
        )


@pytest.mark.unit
def test_write_file_rejects_file_too_large(file_service):
    with pytest.raises(FileTooLargeException):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/notes.md",
            content="01234567890",
        )


@pytest.mark.unit
def test_write_file_rejects_kb_quota(file_service, kb):
    kb.current_size_bytes = 18
    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/notes.md",
            content="abcd",
        )


@pytest.mark.unit
def test_write_file_rejects_user_quota(file_service, mock_db_session):
    mock_db_session.scalar.return_value = 98

    with pytest.raises(FileManagementException, match="User knowledge base total storage quota exceeded"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/notes.md",
            content="abcd",
        )


@pytest.mark.unit
def test_write_file_rejects_viewer_write_access(file_service, kb):
    file_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )

    with pytest.raises(KnowledgeBaseAccessDeniedError, match="Knowledge base does not have write permission"):
        file_service.write_file(
            user_id="viewer-1",
            kb_id="kb-1",
            path="/notes.md",
            content="hello",
        )


@pytest.mark.unit
def test_create_and_read_file_updates_cached_size(file_service, kb):
    result = file_service.create_entry(
        user_id="owner-1",
        kb_id="kb-1",
        path="/notes.md",
        entry_type="file",
        content="hello",
    )

    assert result["size"] == 5
    assert kb.current_size_bytes == 5

    content = file_service.read_file(
        user_id="owner-1",
        kb_id="kb-1",
        path="/notes.md",
    )
    assert content.content == "hello"
    assert content.size == 5


@pytest.mark.unit
def test_delete_entry_reduces_cached_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "notes.md"
    target.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    file_service.delete_entry(
        user_id="owner-1",
        kb_id="kb-1",
        path="/notes.md",
    )

    assert not target.exists()
    assert kb.current_size_bytes == 0


@pytest.mark.unit
def test_copy_entry_copies_file_and_updates_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    source = kb_root / "notes.md"
    source.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/notes.md",
        dest_path="/notes-copy.md",
    )

    assert result == {"type": "file", "size": 5}
    assert (kb_root / "notes-copy.md").read_text(encoding="utf-8") == "hello"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_copies_directory_and_updates_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    source_dir = kb_root / "docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "a.md").write_text("abc", encoding="utf-8")
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "b.txt").write_text("de", encoding="utf-8")
    kb.current_size_bytes = 5

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/docs",
        dest_path="/docs-copy",
    )

    assert result == {"type": "directory", "size": 5}
    assert (kb_root / "docs-copy" / "a.md").read_text(encoding="utf-8") == "abc"
    assert (kb_root / "docs-copy" / "nested" / "b.txt").read_text(encoding="utf-8") == "de"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_rejects_missing_source(file_service):
    with pytest.raises(FileNotFoundException):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/missing.md",
            dest_path="/dest.md",
        )


@pytest.mark.unit
def test_copy_entry_rejects_existing_destination_without_overwrite(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "source.md").write_text("hello", encoding="utf-8")
    (kb_root / "dest.md").write_text("world", encoding="utf-8")
    kb.current_size_bytes = 10

    with pytest.raises(FileAlreadyExistsException):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/source.md",
            dest_path="/dest.md",
            overwrite=False,
        )


@pytest.mark.unit
def test_copy_entry_supports_overwrite_and_updates_delta(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "source.md").write_text("hello", encoding="utf-8")
    (kb_root / "dest.md").write_text("a", encoding="utf-8")
    kb.current_size_bytes = 6

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/source.md",
        dest_path="/dest.md",
        overwrite=True,
    )

    assert result == {"type": "file", "size": 5}
    assert (kb_root / "dest.md").read_text(encoding="utf-8") == "hello"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_rejects_disallowed_extension(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "source.md").write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    with pytest.raises(FileManagementException, match="Unsupported file extension"):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/source.md",
            dest_path="/dest.exe",
        )


@pytest.mark.unit
def test_copy_entry_rejects_kb_quota(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "source.md").write_text("abcd", encoding="utf-8")
    kb.current_size_bytes = 18

    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/source.md",
            dest_path="/copy.md",
        )


@pytest.mark.unit
def test_copy_entry_rejects_viewer_write_access(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "source.md").write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5
    file_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )

    with pytest.raises(KnowledgeBaseAccessDeniedError, match="Knowledge base does not have write permission"):
        file_service.copy_entry(
            user_id="viewer-1",
            kb_id="kb-1",
            source_path="/source.md",
            dest_path="/copy.md",
        )
