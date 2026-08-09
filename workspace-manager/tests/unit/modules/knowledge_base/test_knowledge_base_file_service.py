"""Knowledge base file service unit tests."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest
from aileron_file_core.conformance import assert_engine_conformance
from fastapi import UploadFile

from app.core.file_management import (
    FileConflictExecutionRequest,
    FileConflictSource,
    FileExtractExecutionRequest,
    FileManagementException,
    FileNotFoundException,
    FileTooLargeException,
)
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base import files as kb_file_service_module
from app.modules.knowledge_base.access import KnowledgeBaseAccessDeniedError
from app.modules.knowledge_base.files import KnowledgeBaseFileService

OWNER_ACTOR = AuthorizationActor(user_id="owner-1", platform_role="member")
READER_ACTOR = AuthorizationActor(user_id="reader-1", platform_role="member")


class _AuthorizationProbe(Exception):
    """Stop a file consumer after its operation authorization call."""


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
    service.kb_service.get_kb_for_operation = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "manager"})())
    )
    service.settings.KB_ALLOWED_EXTENSIONS = [".md", ".txt", ".json"]
    service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 10
    service.settings.DEFAULT_KB_QUOTA_BYTES = 20
    service.settings.DEFAULT_USER_KB_QUOTA_BYTES = 100
    return service


@pytest.mark.unit
@pytest.mark.parametrize(
    ("method_name", "kwargs", "operation"),
    [
        ("get_tree", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "read_file",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "read_file_bytes",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "resolve_download_path",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        (
            "write_file",
            {"path": "notes.md", "content": "notes"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "create_entry",
            {"path": "notes.md", "entry_type": "file"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "delete_entry",
            {"path": "notes.md"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "move_entry",
            {"source_path": "notes.md", "dest_path": "moved.md"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
        (
            "search_entries",
            {"query": "notes"},
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        ),
        ("list_history", {}, OperationId.KNOWLEDGE_BASE_DETAIL_READ),
        (
            "restore_history",
            {"entry_id": "history-1"},
            OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        ),
    ],
)
def test_file_callers_use_explicit_operation_ids(
    file_service,
    method_name,
    kwargs,
    operation,
):
    def stop_after_authorization(**call):
        raise _AuthorizationProbe(call)

    file_service.kb_service.get_kb_for_operation.side_effect = stop_after_authorization

    with pytest.raises(_AuthorizationProbe) as probe:
        getattr(file_service, method_name)(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            **kwargs,
        )

    assert probe.value.args[0] == {
        "actor": OWNER_ACTOR,
        "kb_id": "kb-1",
        "operation": operation,
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_caller_uses_content_write_operation(file_service):
    def stop_after_authorization(**call):
        raise _AuthorizationProbe(call)

    file_service.kb_service.get_kb_for_operation.side_effect = stop_after_authorization

    with pytest.raises(_AuthorizationProbe) as probe:
        await file_service.upload_files(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            target_path="/",
            files=[],
            default_strategy="cancel",
            resolutions=[],
        )

    assert probe.value.args[0] == {
        "actor": OWNER_ACTOR,
        "kb_id": "kb-1",
        "operation": OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
    }


@pytest.mark.unit
def test_any_extension_accepted(file_service, kb):
    result = file_service.write_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="bin/tool.exe",
        content="x",
    )

    assert result["size"] == 1
    assert (file_service.storage_root / kb.id / "bin/tool.exe").read_text(
        encoding="utf-8"
    ) == "x"
    activity = [
        call.args[0]
        for call in file_service.db.add.call_args_list
        if isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
    ]
    assert [event.event_type for event in activity] == ["file_written"]


@pytest.mark.unit
def test_write_file_rejects_kb_quota(file_service, kb):
    kb.current_size_bytes = 18
    with pytest.raises(
        FileManagementException, match="Knowledge base storage quota exceeded"
    ):
        file_service.write_file(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            path="/raw/sources/notes.md",
            content="abcd",
        )
    assert not any(
        isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
        for call in file_service.db.add.call_args_list
    )
    file_service.db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_and_delete_record_only_low_sensitivity_activity(file_service, kb):
    upload = UploadFile(filename="notes.md", file=BytesIO(b"notes"))
    await file_service.upload_files(
        actor=OWNER_ACTOR,
        kb_id=kb.id,
        target_path="/",
        files=[upload],
        default_strategy="cancel",
        resolutions=[],
    )
    file_service.delete_entry(
        actor=OWNER_ACTOR,
        kb_id=kb.id,
        path="notes.md",
    )

    activity = [
        call.args[0]
        for call in file_service.db.add.call_args_list
        if isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
    ]
    assert [event.event_type for event in activity] == [
        "file_uploaded",
        "file_deleted",
    ]
    assert all(event.resource_id == kb.id for event in activity)


@pytest.mark.unit
def test_kb_quota_threshold_crossings_and_recovery_are_recorded(file_service, kb):
    for size in (15, 17, 20, 18, 10):
        file_service.write_file(
            actor=OWNER_ACTOR,
            kb_id=kb.id,
            path="notes.md",
            content="x" * size,
        )

    threshold_events = [
        call.args[0].event_type
        for call in file_service.db.add.call_args_list
        if isinstance(call.args[0], db_models.PlatformResourceActivityEvent)
        and call.args[0].event_type.startswith("capacity_threshold_")
    ]
    assert threshold_events == [
        "capacity_threshold_warning",
        "capacity_threshold_critical",
        "capacity_threshold_recovered",
        "capacity_threshold_recovered",
    ]


@pytest.mark.unit
def test_write_file_with_stale_expected_version_does_not_overwrite(file_service, kb):
    target = file_service.storage_root / kb.id / "raw/sources/notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("current", encoding="utf-8")
    stale_version = hashlib.sha256("stale".encode("utf-8")).hexdigest()

    with pytest.raises(FileManagementException) as exc_info:
        file_service.write_file(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            path="/raw/sources/notes.md",
            content="new",
            revision=stale_version,
        )

    assert exc_info.value.code == "CONTENT_CONFLICT"
    assert exc_info.value.status_code == 409
    assert target.read_text(encoding="utf-8") == "current"


@pytest.mark.unit
def test_search_entries_uses_core_search_result_total_and_checks_access(
    file_service, kb
):
    target = file_service.storage_root / kb.id / "raw/sources/notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("Alpha topic", encoding="utf-8")

    result = file_service.search_entries(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        query="alpha",
        path="/raw",
    )

    file_service.kb_service.get_kb_for_operation.assert_called_with(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
    )
    assert result["total"] == 1
    assert result["results"][0]["path"] == "/raw/sources/notes.md"


@pytest.mark.unit
def test_write_file_quota_version_write_and_size_update_happen_inside_resource_lock(
    file_service,
    kb,
    monkeypatch,
):
    target = file_service.storage_root / kb.id / "raw/sources/notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("old", encoding="utf-8")
    kb.current_size_bytes = 3
    locked_content = "locked content"
    new_content = "new content"
    expected_version = hashlib.sha256(locked_content.encode("utf-8")).hexdigest()
    events: list[str] = []

    class RecordingResourceWriteLocks:
        in_lock = False

        @contextmanager
        def lock(self, key):
            assert key == ("knowledge-base", kb.id, "raw/sources/notes.md")
            events.append("enter")
            self.in_lock = True
            target.write_text(locked_content, encoding="utf-8")
            kb.current_size_bytes = len(locked_content)
            try:
                yield
                assert target.read_text(encoding="utf-8") == new_content
                assert kb.current_size_bytes == len(new_content)
                events.append("verified_before_release")
            finally:
                self.in_lock = False
                events.append("exit")

    locks = RecordingResourceWriteLocks()

    def assert_quota_checked_inside_lock(checked_kb, delta_bytes):
        assert locks.in_lock
        assert checked_kb is kb
        assert delta_bytes == len(new_content) - len(locked_content)
        events.append("quota")

    def assert_size_updated_inside_lock(updated_kb, delta_bytes):
        assert locks.in_lock
        assert updated_kb is kb
        assert target.read_text(encoding="utf-8") == new_content
        events.append("update_size")
        updated_kb.current_size_bytes += delta_bytes

    monkeypatch.setattr(kb_file_service_module, "_resource_write_locks", locks)
    monkeypatch.setattr(file_service, "_check_quota", assert_quota_checked_inside_lock)
    monkeypatch.setattr(
        file_service, "_update_kb_size", assert_size_updated_inside_lock
    )

    result = file_service.write_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/raw/sources/notes.md",
        content=new_content,
        revision=expected_version,
    )

    assert result["size"] == len(new_content)
    assert result["revision"] == hashlib.sha256(new_content.encode("utf-8")).hexdigest()
    assert events == [
        "enter",
        "quota",
        "update_size",
        "verified_before_release",
        "exit",
    ]


@pytest.mark.unit
def test_write_file_path_aliases_use_same_resource_lock_key(
    file_service, kb, monkeypatch
):
    captured_keys = []

    class RecordingResourceWriteLocks:
        @contextmanager
        def lock(self, key):
            captured_keys.append(key)
            yield

    monkeypatch.setattr(
        kb_file_service_module, "_resource_write_locks", RecordingResourceWriteLocks()
    )

    for path in ("/doc.md", "doc.md", "./doc.md", "a//b.md", "a/./b.md"):
        file_service.write_file(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            path=path,
            content=path,
        )

    assert captured_keys == [
        ("knowledge-base", kb.id, "doc.md"),
        ("knowledge-base", kb.id, "doc.md"),
        ("knowledge-base", kb.id, "doc.md"),
        ("knowledge-base", kb.id, "a/b.md"),
        ("knowledge-base", kb.id, "a/b.md"),
    ]


@pytest.mark.unit
def test_reader_cannot_write(file_service, kb):
    file_service.kb_service.get_kb_for_operation = MagicMock(
        side_effect=KnowledgeBaseAccessDeniedError(
            "Knowledge base permission denied",
            code="KB_OPERATION_DENIED",
        )
    )

    with pytest.raises(KnowledgeBaseAccessDeniedError) as exc_info:
        file_service.write_file(
            actor=READER_ACTOR,
            kb_id="kb-1",
            path="notes/a.txt",
            content="x",
        )

    assert exc_info.value.code == "KB_OPERATION_DENIED"
    assert not (file_service.storage_root / kb.id / "notes/a.txt").exists()


@pytest.mark.unit
def test_create_and_read_file_updates_cached_size(file_service, kb):
    result = file_service.create_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/raw/sources/notes.md",
        entry_type="file",
        content="hello",
    )

    assert result["size"] == 5
    assert kb.current_size_bytes == 5

    content = file_service.read_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/raw/sources/notes.md",
    )
    assert content.content == "hello"
    assert content.size == 5


@pytest.mark.unit
def test_read_file_bytes_allows_reader_and_enforces_size_limit(file_service, kb):
    file_service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "reader"})())
    )
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "image.png"
    target.write_bytes(b"png-bytes")

    content, size = file_service.read_file_bytes(
        actor=READER_ACTOR,
        kb_id="kb-1",
        path="/image.png",
    )

    assert content == b"png-bytes"
    assert size == len(b"png-bytes")

    target.write_bytes(b"01234567890")
    with pytest.raises(FileTooLargeException):
        file_service.read_file_bytes(
            actor=READER_ACTOR,
            kb_id="kb-1",
            path="/image.png",
        )


@pytest.mark.unit
def test_read_file_returns_binary_metadata_for_zip_path_with_spaces(file_service, kb):
    file_service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 1024 * 1024
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "cube-web-design-style (1).zip"
    target.write_bytes(_zip_bytes({"style.css": b"body {}"}))

    content = file_service.read_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/cube-web-design-style (1).zip",
    )

    assert content.content == ""
    assert content.readable is False
    assert content.unreadableReason == "binary"


@pytest.mark.unit
def test_get_tree_reads_existing_root_and_reports_writable_raw_tree(file_service, kb):
    raw_sources = file_service.storage_root / kb.id / "raw/sources"
    raw_sources.mkdir(parents=True, exist_ok=True)

    tree = file_service.get_tree(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/",
        max_depth=2,
    )

    root = file_service.storage_root / kb.id
    assert (root / "raw/sources").is_dir()
    assert not (root / "AGENTS.md").exists()
    assert {node.name for node in tree.nodes} >= {"raw"}
    nodes_by_name = {node.name: node for node in tree.nodes}
    assert nodes_by_name["raw"].writable is True
    raw_children_by_name = {node.name: node for node in nodes_by_name["raw"].children}
    assert raw_children_by_name["sources"].writable is True
    assert "normalized" not in {node.name for node in tree.nodes}
    assert "reports" not in {node.name for node in tree.nodes}


@pytest.mark.unit
def test_get_tree_missing_path_does_not_create_directory(file_service, kb):
    missing = file_service.storage_root / kb.id / "missing"

    with pytest.raises(FileNotFoundException):
        file_service.get_tree(
            actor=OWNER_ACTOR,
            kb_id="kb-1",
            path="/missing",
        )

    assert not missing.exists()


@pytest.mark.unit
def test_write_file_allows_raw_path(file_service, kb):
    result = file_service.write_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="raw/sources/a.md",
        content="hello",
    )

    assert result["size"] == 5
    assert (file_service.storage_root / kb.id / "raw/sources/a.md").read_text(
        encoding="utf-8"
    ) == "hello"


@pytest.mark.unit
def test_write_file_outside_raw_succeeds(file_service, kb):
    result = file_service.write_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="notes/custom-note.md",
        content="hello",
    )

    assert result["size"] == 5
    assert (file_service.storage_root / kb.id / "notes/custom-note.md").read_text(
        encoding="utf-8"
    ) == "hello"


@pytest.mark.unit
def test_write_file_internal_state_path_succeeds(file_service, kb):
    result = file_service.write_file(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path=".aileron-kb/metadata.json",
        content="{}",
    )

    assert result["size"] == 2
    assert (file_service.storage_root / kb.id / ".aileron-kb/metadata.json").read_text(
        encoding="utf-8"
    ) == "{}"


@pytest.mark.unit
def test_delete_entry_reduces_cached_size(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    target = kb_root / "raw/sources/notes.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5

    file_service.delete_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/raw/sources/notes.md",
    )

    assert not target.exists()
    assert kb.current_size_bytes == 0


@pytest.mark.unit
def test_delete_entry_allows_raw_root(file_service, kb):
    raw_root = file_service.storage_root / kb.id / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)

    result = file_service.delete_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="/raw",
        recursive=True,
    )

    assert result["type"] == "directory"
    assert not raw_root.exists()


@pytest.mark.unit
def test_move_entry_allows_destination_outside_raw(file_service, kb):
    source = file_service.storage_root / kb.id / "raw/sources/a.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")

    result = file_service.move_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        source_path="raw/sources/a.md",
        dest_path="notes/sources/a.md",
    )

    assert result == {"type": "file", "size": 5}
    assert not source.exists()
    assert (file_service.storage_root / kb.id / "notes/sources/a.md").read_text(
        encoding="utf-8"
    ) == "hello"


@pytest.mark.unit
def test_move_entry_allows_source_outside_raw(file_service, kb):
    source = file_service.storage_root / kb.id / "notes/index.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello", encoding="utf-8")

    result = file_service.move_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        source_path="notes/index.md",
        dest_path="raw/sources/index.md",
    )

    assert result == {"type": "file", "size": 5}
    assert not source.exists()
    assert (file_service.storage_root / kb.id / "raw/sources/index.md").read_text(
        encoding="utf-8"
    ) == "hello"


@pytest.mark.unit
def test_reader_cannot_paste_entry(file_service, kb):
    kb_root = file_service.storage_root / kb.id
    kb_root.mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources").mkdir(parents=True, exist_ok=True)
    (kb_root / "raw/sources/source.md").write_text("hello", encoding="utf-8")
    kb.current_size_bytes = 5
    file_service.kb_service.get_kb_for_operation = MagicMock(
        side_effect=KnowledgeBaseAccessDeniedError(
            "Knowledge base permission denied",
            code="KB_OPERATION_DENIED",
        )
    )

    with pytest.raises(KnowledgeBaseAccessDeniedError) as exc_info:
        file_service.paste_entries(
            actor=READER_ACTOR,
            kb_id="kb-1",
            payload=FileConflictExecutionRequest(
                targetPath="/notes",
                sources=[
                    FileConflictSource(
                        sourcePath="/raw/sources/source.md", entryType="file"
                    )
                ],
                defaultStrategy="cancel",
                resolutions=[],
            ),
        )

    assert exc_info.value.code == "KB_OPERATION_DENIED"
    assert not (kb_root / "notes/copy.md").exists()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upload_files_allows_target_outside_raw(file_service, kb):
    upload = UploadFile(filename="a.md", file=BytesIO(b"hello"))

    result = await file_service.upload_files(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        target_path="sources/imports",
        files=[upload],
        default_strategy="cancel",
        resolutions=[],
    )

    assert result.succeeded == 1
    assert result.items[0].finalPath == "sources/imports/a.md"
    assert (file_service.storage_root / kb.id / "sources/imports/a.md").read_text(
        encoding="utf-8"
    ) == "hello"


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_kb_facade_uses_core_for_upload_extract_and_search(file_service, kb):
    file_service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 1000
    upload = UploadFile(filename="notes.md", file=BytesIO(b"alpha"))
    upload_result = await file_service.upload_files(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        target_path="imports",
        files=[upload],
        default_strategy="replace",
        resolutions=[],
    )
    archive_path = file_service.storage_root / kb.id / "imports/docs.zip"
    archive_path.write_bytes(_zip_bytes({"guide.md": b"beta topic"}))
    extract_result = file_service.extract_archive(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        payload=FileExtractExecutionRequest(
            archivePath="imports/docs.zip",
            targetPath="imports",
            defaultStrategy="replace",
            resolutions=[],
        ),
    )
    search_result = file_service.search_entries(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        query="beta",
    )

    assert upload_result.items[0].finalPath == "imports/notes.md"
    assert extract_result.items[0].finalPath == "imports/guide.md"
    assert search_result["results"][0]["path"] == "/imports/guide.md"


@pytest.mark.unit
def test_kb_engine_satisfies_shared_file_core_conformance(file_service, kb):
    kb.quota_bytes = 1000
    file_service.settings.KB_SINGLE_FILE_SIZE_LIMIT = 1000
    with file_service._kb_context(kb, "manager"):
        assert_engine_conformance(
            engine=file_service._engine(),
            locator=file_service._locator(kb.id),
        )


@pytest.mark.unit
def test_create_entry_allows_new_raw_directory(file_service, kb):
    result = file_service.create_entry(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        path="raw/sources/2026Q2",
        entry_type="directory",
    )

    assert result["type"] == "directory"
    assert (file_service.storage_root / kb.id / "raw/sources/2026Q2").is_dir()
