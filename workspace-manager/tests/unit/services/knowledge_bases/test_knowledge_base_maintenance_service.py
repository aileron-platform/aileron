"""Knowledge base maintenance service unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.services.knowledge_base_maintenance_service import KnowledgeBaseMaintenanceService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.scalars = MagicMock()
    session.commit = MagicMock()
    session.delete = MagicMock()
    return session


@pytest.fixture
def maintenance_service(mock_db_session, tmp_path):
    service = KnowledgeBaseMaintenanceService(mock_db_session)
    service.storage_root = tmp_path
    service.settings.KB_TOMBSTONE_RETENTION_HOURS = 24
    return service


@pytest.mark.unit
def test_reconcile_kb_quota_updates_cached_sizes_and_detects_drift(
    maintenance_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=4,
        quota_bytes=None,
    )
    kb_dir = maintenance_service.storage_root / kb.id
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "readme.md").write_text("hello world", encoding="utf-8")

    mock_db_session.scalars.return_value.all.return_value = [kb]

    with patch("app.services.knowledge_base_maintenance_service.logger") as mock_logger:
        result = maintenance_service.reconcile_kb_quota()

    assert result == {"processed": 1, "updated": 1, "drifted": 1}
    assert kb.current_size_bytes == 11
    mock_db_session.commit.assert_called_once()
    mock_logger.warning.assert_called_once()


@pytest.mark.unit
def test_reconcile_kb_quota_skips_commit_when_no_changes(
    maintenance_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=5,
        quota_bytes=None,
    )
    kb_dir = maintenance_service.storage_root / kb.id
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "readme.md").write_text("hello", encoding="utf-8")

    mock_db_session.scalars.return_value.all.return_value = [kb]

    result = maintenance_service.reconcile_kb_quota()

    assert result == {"processed": 1, "updated": 0, "drifted": 0}
    mock_db_session.commit.assert_not_called()


@pytest.mark.unit
def test_reconcile_kb_quota_includes_git_and_lfs_objects(
    maintenance_service,
    mock_db_session,
):
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        quota_bytes=None,
    )
    kb_dir = maintenance_service.storage_root / kb.id
    lfs_dir = kb_dir / ".git" / "lfs" / "objects" / "aa" / "bb"
    lfs_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "wiki.md").write_text("wiki", encoding="utf-8")
    (kb_dir / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (lfs_dir / "large-object").write_text("large", encoding="utf-8")

    mock_db_session.scalars.return_value.all.return_value = [kb]

    result = maintenance_service.reconcile_kb_quota()

    assert result == {"processed": 1, "updated": 1, "drifted": 1}
    assert kb.current_size_bytes == 30
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_cleanup_tombstoned_knowledge_bases_removes_dirs_attachments_and_records(
    maintenance_service,
    mock_db_session,
):
    attachment = MagicMock()
    kb = db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        quota_bytes=None,
        tombstoned_at=datetime.utcnow() - timedelta(hours=48),
    )
    kb.attachments = [attachment]
    kb_dir = maintenance_service.storage_root / kb.id
    kb_dir.mkdir(parents=True, exist_ok=True)
    (kb_dir / "readme.md").write_text("hello", encoding="utf-8")

    mock_db_session.scalars.return_value.all.return_value = [kb]

    result = maintenance_service.cleanup_tombstoned_knowledge_bases()

    assert result == {"deleted": 1, "attachmentsDeleted": 1, "bytesFreed": 5}
    assert not kb_dir.exists()
    mock_db_session.delete.assert_any_call(attachment)
    mock_db_session.delete.assert_any_call(kb)
    mock_db_session.commit.assert_called_once()


@pytest.mark.unit
def test_cleanup_tombstoned_knowledge_bases_skips_recent_tombstones(
    maintenance_service,
    mock_db_session,
):
    mock_db_session.scalars.return_value.all.return_value = []

    result = maintenance_service.cleanup_tombstoned_knowledge_bases()

    assert result == {"deleted": 0, "attachmentsDeleted": 0, "bytesFreed": 0}
    mock_db_session.commit.assert_not_called()
