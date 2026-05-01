"""Knowledge base file service unit tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import UploadFile

from app.core.file_management import (
    FileAlreadyExistsException,
    FileManagementException,
    FileNotFoundException,
    FileTooLargeException,
    KnowledgeBasePathNotWritableError,
    KnowledgeBaseRawRootCannotBeDeletedError,
)
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
            path="/raw/sources/notes.py",
            content="print('x')",
        )


@pytest.mark.unit
def test_write_file_rejects_file_too_large(file_service):
    with pytest.raises(FileTooLargeException):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/raw/sources/notes.md",
            content="01234567890",
        )


@pytest.mark.unit
def test_write_file_rejects_kb_quota(file_service, kb):
    kb.current_size_bytes = 18
    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/raw/sources/notes.md",
            content="abcd",
        )


@pytest.mark.unit
def test_write_file_rejects_user_quota(file_service, mock_db_session):
    mock_db_session.scalar.return_value = 98

    with pytest.raises(FileManagementException, match="User knowledge base total storage quota exceeded"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/raw/sources/notes.md",
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
            path="/raw/sources/notes.md",
            content="hello",
        )


@pytest.mark.unit
def test_create_and_read_file_updates_cached_size(file_service, kb):
    result = file_service.create_entry(
        user_id="owner-1",
        kb_id="kb-1",
        path="/raw/sources/notes.md",
        entry_type="file",
        content="hello",
    )

    assert result["size"] == 5
    assert kb.current_size_bytes == 5

    content = file_service.read_file(
        user_id="owner-1",
        kb_id="kb-1",
        path="/raw/sources/notes.md",
    )
    assert content.content == "hello"
    assert content.size == 5


@pytest.mark.unit
def test_read_file_bytes_allows_viewer_and_enforces_size_limit(file_service, kb):
    file_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "image.png"
    target.write_bytes(b"png-bytes")

    content, size = file_service.read_file_bytes(
        user_id="viewer-1",
        kb_id="kb-1",
        path="/image.png",
    )

    assert content == b"png-bytes"
    assert size == len(b"png-bytes")

    target.write_bytes(b"01234567890")
    with pytest.raises(FileTooLargeException):
        file_service.read_file_bytes(
            user_id="viewer-1",
            kb_id="kb-1",
            path="/image.png",
        )


@pytest.mark.unit
def test_get_tree_lazily_initializes_team_wiki_layout(file_service, kb):
    tree = file_service.get_tree(
        user_id="owner-1",
        kb_id="kb-1",
        path="/",
        max_depth=2,
    )

    root = file_service.storage_root / kb.id
    assert (root / "AGENTS.md").is_file()
    assert (root / "wiki/index.md").is_file()
    assert (root / "raw/sources").is_dir()
    assert kb.wiki_initialized_at is not None
    assert {node.name for node in tree.nodes} >= {"raw", "wiki", "AGENTS.md"}
    nodes_by_name = {node.name: node for node in tree.nodes}
    assert nodes_by_name["raw"].writable is True
    assert nodes_by_name["wiki"].writable is False
    assert nodes_by_name["AGENTS.md"].writable is False
    raw_children_by_name = {node.name: node for node in nodes_by_name["raw"].children}
    assert raw_children_by_name["sources"].writable is True
    assert "normalized" not in {node.name for node in tree.nodes}
    assert "reports" not in {node.name for node in tree.nodes}


@pytest.mark.unit
def test_write_file_allows_raw_path(file_service, kb):
    result = file_service.write_file(
        user_id="owner-1",
        kb_id="kb-1",
        path="raw/sources/a.md",
        content="hello",
    )

    assert result["size"] == 5
    assert (file_service.storage_root / kb.id / "raw/sources/a.md").read_text(encoding="utf-8") == "hello"


@pytest.mark.unit
def test_write_file_rejects_wiki_path(file_service):
    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="wiki/index.md",
            content="hello",
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"


@pytest.mark.unit
def test_write_file_rejects_internal_state_path(file_service):
    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path=".aileron-kb/reviews.json",
            content="{}",
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"


@pytest.mark.unit
def test_delete_entry_reduces_cached_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "raw/sources/notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    file_service.delete_entry(
        user_id="owner-1",
        kb_id="kb-1",
        path="/raw/sources/notes.md",
    )

    assert not target.exists()
    assert kb.current_size_bytes == 0


@pytest.mark.unit
def test_delete_entry_rejects_raw_root(file_service, kb):
    raw_root = file_service.storage_root / kb.id / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    with pytest.raises(KnowledgeBaseRawRootCannotBeDeletedError) as exc_info:
        file_service.delete_entry(
            user_id="owner-1",
            kb_id="kb-1",
            path="/raw",
            recursive=True,
        )

    assert exc_info.value.code == "RAW_ROOT_CANNOT_BE_DELETED"
    assert raw_root.is_dir()


@pytest.mark.unit
def test_move_entry_rejects_destination_outside_raw(file_service, kb):
    source = file_service.storage_root / kb.id / "raw/sources/a.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        file_service.move_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="raw/sources/a.md",
            dest_path="wiki/sources/a.md",
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"
    assert source.exists()


@pytest.mark.unit
def test_move_entry_rejects_source_outside_raw(file_service, kb):
    source = file_service.storage_root / kb.id / "wiki/index.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        file_service.move_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="wiki/index.md",
            dest_path="raw/sources/index.md",
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"
    assert source.exists()


@pytest.mark.unit
def test_copy_entry_rejects_source_outside_raw(file_service, kb):
    source = file_service.storage_root / kb.id / "wiki/index.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="wiki/index.md",
            dest_path="raw/sources/index-copy.md",
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"
    assert not (file_service.storage_root / kb.id / "raw/sources/index-copy.md").exists()


@pytest.mark.unit
def test_copy_entry_copies_file_and_updates_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    source = kb_root / "raw/sources/notes.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/raw/sources/notes.md",
        dest_path="/raw/sources/notes-copy.md",
    )

    assert result == {"type": "file", "size": 5}
    assert (kb_root / "raw/sources/notes-copy.md").read_text(encoding="utf-8") == "hello"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_copies_file_within_raw(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    source = kb_root / "raw/sources/a.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="raw/sources/a.md",
        dest_path="raw/assets/a.md",
    )

    assert result == {"type": "file", "size": 5}
    assert (kb_root / "raw/assets/a.md").read_text(encoding="utf-8") == "hello"


@pytest.mark.unit
def test_copy_entry_copies_directory_and_updates_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    source_dir = kb_root / "raw/sources/docs"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "a.md").write_text("abc", encoding="utf-8")
    nested_dir = source_dir / "nested"
    nested_dir.mkdir()
    (nested_dir / "b.txt").write_text("de", encoding="utf-8")
    kb.current_size_bytes = 5

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/raw/sources/docs",
        dest_path="/raw/sources/docs-copy",
    )

    assert result == {"type": "directory", "size": 5}
    assert (kb_root / "raw/sources/docs-copy" / "a.md").read_text(encoding="utf-8") == "abc"
    assert (kb_root / "raw/sources/docs-copy" / "nested" / "b.txt").read_text(encoding="utf-8") == "de"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_rejects_missing_source(file_service):
    with pytest.raises(FileNotFoundException):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/raw/sources/missing.md",
            dest_path="/raw/sources/dest.md",
        )


@pytest.mark.unit
def test_copy_entry_rejects_existing_destination_without_overwrite(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("hello", encoding="utf-8")
    (kb_root / "raw/sources/dest.md").write_text("world", encoding="utf-8")
    kb.current_size_bytes = 10

    with pytest.raises(FileAlreadyExistsException):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/raw/sources/source.md",
            dest_path="/raw/sources/dest.md",
            overwrite=False,
        )


@pytest.mark.unit
def test_copy_entry_supports_overwrite_and_updates_delta(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("hello", encoding="utf-8")
    (kb_root / "raw/sources/dest.md").write_text("a", encoding="utf-8")
    kb.current_size_bytes = 6

    result = file_service.copy_entry(
        user_id="owner-1",
        kb_id="kb-1",
        source_path="/raw/sources/source.md",
        dest_path="/raw/sources/dest.md",
        overwrite=True,
    )

    assert result == {"type": "file", "size": 5}
    assert (kb_root / "raw/sources/dest.md").read_text(encoding="utf-8") == "hello"
    assert kb.current_size_bytes == 10


@pytest.mark.unit
def test_copy_entry_rejects_disallowed_extension(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    with pytest.raises(FileManagementException, match="Unsupported file extension"):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/raw/sources/source.md",
            dest_path="/raw/sources/dest.exe",
        )


@pytest.mark.unit
def test_copy_entry_rejects_kb_quota(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("abcd", encoding="utf-8")
    kb.current_size_bytes = 18

    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        file_service.copy_entry(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/raw/sources/source.md",
            dest_path="/raw/sources/copy.md",
        )


@pytest.mark.unit
def test_copy_entry_rejects_viewer_write_access(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5
    file_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )

    with pytest.raises(KnowledgeBaseAccessDeniedError, match="Knowledge base does not have write permission"):
        file_service.copy_entry(
            user_id="viewer-1",
            kb_id="kb-1",
            source_path="/raw/sources/source.md",
            dest_path="/raw/sources/copy.md",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_files_rejects_target_outside_raw(file_service):
    upload = UploadFile(filename="a.md", file=BytesIO(b"hello"))

    with pytest.raises(KnowledgeBasePathNotWritableError) as exc_info:
        await file_service.upload_files(
            user_id="owner-1",
            kb_id="kb-1",
            target_path="wiki/sources",
            files=[upload],
        )

    assert exc_info.value.code == "PATH_NOT_WRITABLE"


@pytest.mark.unit
def test_create_entry_allows_new_raw_directory(file_service, kb):
    result = file_service.create_entry(
        user_id="owner-1",
        kb_id="kb-1",
        path="raw/sources/2026Q2",
        entry_type="directory",
    )

    assert result["type"] == "directory"
    assert (file_service.storage_root / kb.id / "raw/sources/2026Q2").is_dir()
