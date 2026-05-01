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
def test_import_file_writes_to_raw_sources_and_records_metadata(source_service, kb, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("# Notes\n", encoding="utf-8")

    result = source_service.import_file(
        user_id="owner-1",
        kb_id=kb.id,
        source_file=source,
        origin="upload",
    )

    target = source_service.storage_root / kb.id / "raw/sources/notes.md"
    assert target.read_text(encoding="utf-8") == "# Notes\n"
    assert result.path == "/raw/sources/notes.md"
    assert result.size == len("# Notes\n")
    assert len(result.source_hash) == 64

    meta_path = source_service.storage_root / kb.id / ".aileron-kb/sources-metadata.json"
    assert meta_path.is_file()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert "raw/sources/notes.md" in meta
    assert meta["raw/sources/notes.md"]["origin"] == "upload"


@pytest.mark.unit
def test_import_file_rejects_invalid_raw_directory(source_service, tmp_path):
    source = tmp_path / "notes.md"
    source.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidPathException):
        source_service.import_file(
            user_id="owner-1",
            kb_id="kb-1",
            source_file=source,
            target_name="../escape.md",
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
        )


@pytest.mark.unit
def test_import_web_clip_writes_to_raw_sources_and_records_origin(source_service, kb):
    result = source_service.import_web_clip(
        user_id="owner-1",
        kb_id=kb.id,
        title="Example Page",
        markdown="# Example\n\n![Diagram](diagram.png)\n",
        assets={"diagram.png": b"fake-image"},
    )

    clip_file = source_service.storage_root / kb.id / "raw/sources/example-page.md"
    asset_file = source_service.storage_root / kb.id / "raw/assets/example-page/diagram.png"

    assert result.path == "/raw/sources/example-page.md"
    assert result.asset_paths == ["/raw/assets/example-page/diagram.png"]
    assert len(result.source_hash) == 64
    assert clip_file.is_file()
    assert asset_file.read_bytes() == b"fake-image"
    clip_content = clip_file.read_text(encoding="utf-8")
    assert "type: \"web-clip\"" in clip_content
    assert "# Example" in clip_content

    meta_path = source_service.storage_root / kb.id / ".aileron-kb/sources-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["raw/sources/example-page.md"]["origin"] == "clipped"


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

    assert not (source_service.storage_root / kb.id / "raw/sources/large-clip.md").exists()
