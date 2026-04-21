"""Knowledge base file service 單元測試。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.file_management import FileManagementException, FileTooLargeException
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
    with pytest.raises(FileManagementException, match="不支援的檔案副檔名"):
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
    with pytest.raises(FileManagementException, match="知識庫容量配額不足"):
        file_service.write_file(
            user_id="owner-1",
            kb_id="kb-1",
            path="/notes.md",
            content="abcd",
        )


@pytest.mark.unit
def test_write_file_rejects_user_quota(file_service, mock_db_session):
    mock_db_session.scalar.return_value = 98

    with pytest.raises(FileManagementException, match="使用者知識庫總容量配額不足"):
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

    with pytest.raises(KnowledgeBaseAccessDeniedError, match="知識庫無寫入權限"):
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
