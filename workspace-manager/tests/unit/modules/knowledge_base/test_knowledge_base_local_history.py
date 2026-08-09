"""Knowledge base local history unit tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from aileron_git_core.testkit import Repo

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.version_control.models import DiscardRequest
from app.modules.knowledge_base.files import KnowledgeBaseFileService
from app.modules.knowledge_base.git import KnowledgeBaseGitService
from app.modules.version_control.local_history import ManagerLocalHistoryService

ACTOR = AuthorizationActor(user_id="owner-1", platform_role="member")


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


def test_manager_local_history_records_kb_snapshot(tmp_path: Path) -> None:
    source = tmp_path / "kb" / "doc.md"
    source.parent.mkdir(parents=True)
    source.write_text("before", encoding="utf-8")
    history = ManagerLocalHistoryService(history_root=tmp_path / "history")

    entry = history.snapshot_file(
        domain="knowledge-base",
        resource_id="kb-1",
        source_path=source,
        relative_path="doc.md",
        operation="write",
    )

    assert entry is not None
    assert entry["domain"] == "knowledge-base"
    assert Path(entry["snapshotPath"]).read_text(encoding="utf-8") == "before"


def test_manager_local_history_uses_revision_fields(tmp_path: Path) -> None:
    source = tmp_path / "kb" / "doc.md"
    source.parent.mkdir(parents=True)
    source.write_text("before", encoding="utf-8")
    history = ManagerLocalHistoryService(history_root=tmp_path / "history")

    entry = history.snapshot_file(
        domain="knowledge-base",
        resource_id="kb-1",
        source_path=source,
        relative_path="doc.md",
        operation="write",
        version_id_before="before-revision",
    )

    assert entry is not None
    assert entry["revisionBefore"] == "before-revision"
    assert entry["revisionAfter"] is None
    assert "versionIdBefore" not in entry
    assert "versionIdAfter" not in entry
    assert "contentHashBefore" not in entry
    assert "contentHashAfter" not in entry


def test_knowledge_base_write_snapshots_existing_file(
    mock_db_session,
    kb,
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.local_history = ManagerLocalHistoryService(
        history_root=tmp_path / "history"
    )
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 100
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100

    target = service.storage_root / kb.id / "doc.md"
    target.parent.mkdir(parents=True)
    target.write_text("before", encoding="utf-8")
    kb.current_size_bytes = len("before")

    service.write_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
        content="after",
    )

    history = service.list_history(actor=ACTOR, kb_id=kb.id, path="doc.md")
    assert len(history["items"]) == 1
    snapshot_path = Path(history["items"][0]["snapshotPath"])
    assert snapshot_path.read_text(encoding="utf-8") == "before"


def test_knowledge_base_restore_writes_snapshot_content(
    mock_db_session,
    kb,
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.local_history = ManagerLocalHistoryService(
        history_root=tmp_path / "history"
    )
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 100
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100

    service.write_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
        content="before",
    )
    service.write_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
        content="after",
    )
    entry_id = service.list_history(actor=ACTOR, kb_id=kb.id)["items"][0]["id"]
    current_revision = service.read_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
    ).revision

    result = service.restore_history(
        actor=ACTOR,
        kb_id=kb.id,
        entry_id=entry_id,
        revision=current_revision,
    )

    assert result["path"] == "doc.md"
    assert "revision" in result
    assert "versionId" not in result
    assert (service.storage_root / kb.id / "doc.md").read_text(
        encoding="utf-8"
    ) == "before"


def test_knowledge_base_restore_preserves_binary_snapshot(
    mock_db_session,
    kb,
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.local_history = ManagerLocalHistoryService(
        history_root=tmp_path / "history"
    )
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 100
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100
    target = service.storage_root / kb.id / "asset.bin"
    target.parent.mkdir(parents=True)
    payload_before = b"\xff\x00before"
    payload_after = b"\x00after"
    target.write_bytes(payload_before)
    kb.current_size_bytes = len(payload_before)

    version_id = service._file_policy().version_strategy.read_version(target)
    service.local_history.snapshot_file(
        domain="knowledge-base",
        resource_id=kb.id,
        source_path=target,
        relative_path="asset.bin",
        operation="write",
        version_id_before=version_id,
    )
    target.write_bytes(payload_after)
    entry_id = service.list_history(actor=ACTOR, kb_id=kb.id)["items"][0]["id"]
    current_version = service._file_policy().version_strategy.read_version(target)

    result = service.restore_history(
        actor=ACTOR,
        kb_id=kb.id,
        entry_id=entry_id,
        revision=current_version,
    )

    assert result["path"] == "asset.bin"
    assert "revision" in result
    assert "versionId" not in result
    assert target.read_bytes() == payload_before


def test_knowledge_base_restore_existing_file_requires_expected_version(
    mock_db_session,
    kb,
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseFileService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.local_history = ManagerLocalHistoryService(
        history_root=tmp_path / "history"
    )
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 100
    service.settings.DEFAULT_KB_QUOTA_BYTES = 100
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100

    service.write_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
        content="before",
    )
    service.write_file(
        actor=ACTOR,
        kb_id=kb.id,
        path="doc.md",
        content="after",
    )
    entry_id = service.list_history(actor=ACTOR, kb_id=kb.id)["items"][0]["id"]

    with pytest.raises(Exception) as exc_info:
        service.restore_history(
            actor=ACTOR,
            kb_id=kb.id,
            entry_id=entry_id,
        )

    assert getattr(exc_info.value, "code", None) == "CONTENT_CONFLICT"
    assert (service.storage_root / kb.id / "doc.md").read_text(
        encoding="utf-8"
    ) == "after"


def _enable_existing_repo(
    service: KnowledgeBaseGitService, kb: db_models.KnowledgeBase
) -> Repo:
    kb.version_control_enabled = True
    root = service.storage_root / kb.id
    root.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(root, initial_branch="main")
    with repo.config_writer() as config:
        config.set_value("user", "name", "KB Tester")
        config.set_value("user", "email", "kb@example.com")
    (root / "notes").mkdir()
    (root / "notes" / "index.md").write_text("# Index\n", encoding="utf-8")
    repo.index.add(["notes/index.md"])
    repo.index.commit("initial")
    return repo


def test_knowledge_base_discard_snapshots_modified_file(
    mock_db_session,
    kb,
    tmp_path: Path,
) -> None:
    service = KnowledgeBaseGitService(mock_db_session)
    service.storage_root = tmp_path / "kb"
    service.local_history = ManagerLocalHistoryService(
        history_root=tmp_path / "history"
    )
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    _enable_existing_repo(service, kb)
    target = service.storage_root / kb.id / "notes" / "index.md"
    target.write_text("# Index\n\nChanged\n", encoding="utf-8")

    service.discard(
        actor=ACTOR,
        kb_id=kb.id,
        payload=DiscardRequest(paths=["notes/index.md"]),
    )

    entries = service.local_history.list_entries(
        domain="knowledge-base",
        resource_id=kb.id,
        path="notes/index.md",
    )
    assert len(entries) == 1
    assert entries[0]["operation"] == "discard"
    assert (
        Path(entries[0]["snapshotPath"]).read_text(encoding="utf-8")
        == "# Index\n\nChanged\n"
    )
