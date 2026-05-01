"""Knowledge base Team Wiki service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.db import models as db_models
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
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
        version_control_enabled=False,
        git_lfs_enabled=False,
        git_default_branch="main",
    )


@pytest.fixture
def wiki_service(mock_db_session, tmp_path):
    service = KnowledgeBaseWikiService(mock_db_session)
    service.storage_root = tmp_path
    return service


@pytest.mark.unit
def test_initialize_creates_team_wiki_layout(wiki_service, mock_db_session, kb):
    wiki_service.initialize(kb)

    root = wiki_service.storage_root / kb.id
    expected_directories = [
        "raw/sources",
        "raw/assets",
        "wiki/entities",
        "wiki/concepts",
        "wiki/sources",
        "wiki/queries",
        "wiki/synthesis",
        "wiki/comparisons",
        ".aileron-kb/vector",
    ]
    for relative_path in expected_directories:
        assert (root / relative_path).is_dir()

    expected_files = [
        "AGENTS.md",
        "purpose.md",
        "schema.md",
        "wiki/index.md",
        "wiki/log.md",
        "wiki/overview.md",
        ".aileron-kb/ingest-queue.json",
        ".aileron-kb/ingest-cache.json",
        ".aileron-kb/reviews.json",
        ".aileron-kb/graph-cache.json",
        ".aileron-kb/sources-metadata.json",
    ]
    for relative_path in expected_files:
        assert (root / relative_path).is_file()

    assert "[[overview]]" in (root / "wiki/index.md").read_text(encoding="utf-8")
    assert kb.current_size_bytes > 0
    assert kb.wiki_initialized_at is not None
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once_with(kb)


@pytest.mark.unit
def test_initialize_is_idempotent_and_preserves_user_files(wiki_service, kb):
    root = wiki_service.storage_root / kb.id
    root.mkdir(parents=True)
    custom_file = root / "wiki/index.md"
    custom_file.parent.mkdir(parents=True)
    custom_file.write_text("# Custom Index\n", encoding="utf-8")

    wiki_service.initialize(kb)
    first_size = kb.current_size_bytes
    wiki_service.initialize(kb)

    assert custom_file.read_text(encoding="utf-8") == "# Custom Index\n"
    assert kb.current_size_bytes == first_size
