"""Knowledge base source service unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.core.file_management import FileManagementException, InvalidPathException
from app.db import models as db_models
from app.services.knowledge_base_source_service import KnowledgeBaseSourceService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.scalar = MagicMock(return_value=0)
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.get = MagicMock(return_value=None)
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
        version_control_enabled=False,
        git_lfs_enabled=False,
        git_default_branch="main",
    )


@pytest.fixture
def source_service(mock_db_session, kb, tmp_path):
    service = KnowledgeBaseSourceService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.kb_service.get_kb = MagicMock(return_value=(kb, type("Access", (), {"access_role": "editor"})()))
    service.settings.KB_ALLOWED_EXTENSIONS = [".md", ".txt", ".csv", ".pdf", ".docx", ".png"]
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100_000
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100_000
    mock_db_session.get.return_value = kb
    return service


@pytest.mark.unit
def test_import_file_copies_into_allowed_raw_directory(source_service, kb, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n", encoding="utf-8")

    result = source_service.import_file(
        user_id="owner-1",
        kb_id=kb.id,
        source_file=source,
        target_subdir="sources",
    )

    target = source_service.storage_root / kb.id / "raw/sources/notes.md"
    assert target.read_text(encoding="utf-8") == "# Notes\n"
    assert result.path == "/raw/sources/notes.md"
    assert result.size == len("# Notes\n")
    assert len(result.source_hash) == 64
    assert kb.current_size_bytes > result.size


@pytest.mark.unit
def test_import_file_rejects_invalid_raw_directory(source_service, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidPathException):
        source_service.import_file(
            user_id="owner-1",
            kb_id="kb-1",
            source_file=source,
            target_subdir="../sources",
        )


@pytest.mark.unit
def test_import_file_rejects_disallowed_extension(source_service, tmp_path):
    source = tmp_path / "archive.exe"
    source.write_text("x", encoding="utf-8")

    with pytest.raises(FileManagementException, match="Unsupported source extension"):
        source_service.import_file(
            user_id="owner-1",
            kb_id="kb-1",
            source_file=source,
            target_subdir="uploads",
        )


@pytest.mark.unit
def test_import_web_clip_writes_markdown_and_assets(source_service, kb):
    result = source_service.import_web_clip(
        user_id="owner-1",
        kb_id=kb.id,
        title="Example Page",
        markdown="# Example\n\n![Diagram](diagram.png)\n",
        assets={"diagram.png": b"fake-image"},
    )

    clip_file = source_service.storage_root / kb.id / "raw/clipped/example-page.md"
    asset_file = source_service.storage_root / kb.id / "raw/assets/example-page/diagram.png"

    assert result.path == "/raw/clipped/example-page.md"
    assert result.asset_paths == ["/raw/assets/example-page/diagram.png"]
    assert len(result.source_hash) == 64
    assert clip_file.is_file()
    assert asset_file.read_bytes() == b"fake-image"
    clip_content = clip_file.read_text(encoding="utf-8")
    assert "type: \"web-clip\"" in clip_content
    assert "/raw/assets/example-page/diagram.png" in clip_content
    assert "# Example" in clip_content


@pytest.mark.unit
def test_import_web_clip_rejects_asset_path_traversal(source_service, kb):
    with pytest.raises(InvalidPathException):
        source_service.import_web_clip(
            user_id="owner-1",
            kb_id=kb.id,
            title="Example Page",
            markdown="# Example\n",
            assets={"../diagram.png": b"fake-image"},
        )


@pytest.mark.unit
def test_import_web_clip_checks_quota_before_writing(source_service, kb):
    source_service.wiki_service.storage_root = source_service.storage_root
    source_service.wiki_service.initialize(kb)
    kb.current_size_bytes = 99_990
    kb.quota_bytes = 100_000

    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        source_service.import_web_clip(
            user_id="owner-1",
            kb_id=kb.id,
            title="Large Clip",
            markdown="x" * 200,
        )

    assert not (source_service.storage_root / kb.id / "raw/clipped/large-clip.md").exists()


@pytest.mark.unit
def test_normalize_markdown_writes_text_metadata_and_cache(source_service, kb):
    raw_file = source_service.storage_root / kb.id / "raw/uploads/research.md"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("# Research\n\nBody\n", encoding="utf-8")

    result = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/uploads/research.md",
    )

    text_file = source_service.storage_root / kb.id / result.normalized_text_path.lstrip("/")
    metadata_file = source_service.storage_root / kb.id / result.metadata_path.lstrip("/")
    cache_file = source_service.storage_root / kb.id / ".aileron-kb/ingest-cache.json"

    assert result.skipped is False
    assert result.extractor == "text"
    assert text_file.read_text(encoding="utf-8") == "# Research\n\nBody\n"
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["sourcePath"] == "/raw/uploads/research.md"
    assert metadata["extractor"] == "text"
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    assert cache["raw/uploads/research.md"]["sourceHash"] == result.source_hash


@pytest.mark.unit
def test_normalize_csv_converts_rows_to_markdown_like_text(source_service, kb):
    raw_file = source_service.storage_root / kb.id / "raw/uploads/table.csv"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("name,value\nalpha,1\n", encoding="utf-8")

    result = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/uploads/table.csv",
    )

    text_file = source_service.storage_root / kb.id / result.normalized_text_path.lstrip("/")
    assert text_file.read_text(encoding="utf-8") == "name | value\nalpha | 1\n"
    assert result.extractor == "csv"


@pytest.mark.unit
def test_normalize_image_writes_metadata_placeholder(source_service, kb):
    raw_file = source_service.storage_root / kb.id / "raw/assets/diagram.png"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_bytes(b"fake-png")

    result = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/assets/diagram.png",
    )

    text_file = source_service.storage_root / kb.id / result.normalized_text_path.lstrip("/")
    metadata_file = source_service.storage_root / kb.id / result.metadata_path.lstrip("/")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

    assert text_file.read_text(encoding="utf-8") == ""
    assert metadata["status"] == "metadata-only"
    assert result.extractor == "image-placeholder"


@pytest.mark.unit
def test_normalize_office_writes_explicit_fallback(source_service, kb):
    raw_file = source_service.storage_root / kb.id / "raw/uploads/deck.docx"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_bytes(b"fake-docx")

    result = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/uploads/deck.docx",
    )

    metadata_file = source_service.storage_root / kb.id / result.metadata_path.lstrip("/")
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    assert metadata["status"] == "unsupported"
    assert result.extractor == "office-placeholder"


@pytest.mark.unit
def test_normalize_skips_unchanged_source_by_hash_cache(source_service, kb):
    raw_file = source_service.storage_root / kb.id / "raw/uploads/research.txt"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("stable", encoding="utf-8")

    first = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/uploads/research.txt",
    )
    second = source_service.normalize_source(
        user_id="owner-1",
        kb_id=kb.id,
        source_path="/raw/uploads/research.txt",
    )

    assert first.skipped is False
    assert second.skipped is True
    assert second.normalized_hash == first.normalized_hash


@pytest.mark.unit
def test_normalize_rejects_path_outside_raw(source_service):
    with pytest.raises(InvalidPathException):
        source_service.normalize_source(
            user_id="owner-1",
            kb_id="kb-1",
            source_path="/wiki/index.md",
        )


@pytest.mark.unit
def test_normalize_checks_quota_before_writing(source_service, kb):
    source_service.wiki_service.storage_root = source_service.storage_root
    source_service.wiki_service.initialize(kb)
    kb.current_size_bytes = 99_990
    kb.quota_bytes = 100_000
    raw_file = source_service.storage_root / kb.id / "raw/uploads/large.md"
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("x" * 200, encoding="utf-8")

    with pytest.raises(FileManagementException, match="Knowledge base storage quota exceeded"):
        source_service.normalize_source(
            user_id="owner-1",
            kb_id=kb.id,
            source_path="/raw/uploads/large.md",
        )

    normalized_files = list((source_service.storage_root / kb.id / "normalized").rglob("*"))
    assert all(path.is_dir() for path in normalized_files)
