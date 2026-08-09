from pathlib import Path

import pytest

from aileron_file_core import (
    JsonLocalHistoryStore,
    LocalHistoryService,
    PathOutsideRootError,
)


def test_local_history_snapshots_existing_file_and_records_metadata(
    tmp_path: Path,
) -> None:
    root = tmp_path / "history"
    source = tmp_path / "repo" / "docs" / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("before", encoding="utf-8")
    service = LocalHistoryService(
        store=JsonLocalHistoryStore(root),
        snapshot_root=root / "snapshots",
        domain="workspace",
        resource_id="ws-1",
    )

    entry = service.snapshot_existing_file(
        source_path=source,
        relative_path="docs/note.md",
        operation="write",
        version_id_before="sha256:old",
        content_hash_before="sha256:old",
    )

    assert entry is not None
    assert entry.domain == "workspace"
    assert entry.resource_id == "ws-1"
    assert entry.path == "docs/note.md"
    assert entry.operation == "write"
    assert entry.version_id_before == "sha256:old"
    assert entry.content_hash_before == "sha256:old"
    assert entry.snapshot_path is not None
    assert Path(entry.snapshot_path).read_text(encoding="utf-8") == "before"
    assert service.list_entries(path="docs/note.md")[0].id == entry.id


def test_local_history_skips_missing_files(tmp_path: Path) -> None:
    root = tmp_path / "history"
    service = LocalHistoryService(
        store=JsonLocalHistoryStore(root),
        snapshot_root=root / "snapshots",
        domain="workspace",
        resource_id="ws-1",
    )

    assert (
        service.snapshot_existing_file(
            source_path=tmp_path / "missing.md",
            relative_path="missing.md",
            operation="delete",
        )
        is None
    )
    assert service.list_entries() == []


def test_local_history_filters_by_path_and_orders_newest_first(tmp_path: Path) -> None:
    root = tmp_path / "history"
    source = tmp_path / "repo" / "note.md"
    source.parent.mkdir(parents=True)
    source.write_text("one", encoding="utf-8")
    service = LocalHistoryService(
        store=JsonLocalHistoryStore(root),
        snapshot_root=root / "snapshots",
        domain="workspace",
        resource_id="ws-1",
    )

    first = service.snapshot_existing_file(
        source_path=source,
        relative_path="note.md",
        operation="write",
    )
    source.write_text("two", encoding="utf-8")
    second = service.snapshot_existing_file(
        source_path=source,
        relative_path="note.md",
        operation="write",
    )
    source.write_text("other", encoding="utf-8")
    service.snapshot_existing_file(
        source_path=source,
        relative_path="other.md",
        operation="write",
    )

    assert first is not None
    assert second is not None
    assert [entry.id for entry in service.list_entries(path="note.md")] == [
        second.id,
        first.id,
    ]


def test_local_history_rejects_unsafe_resource_id(tmp_path: Path) -> None:
    with pytest.raises(PathOutsideRootError):
        LocalHistoryService(
            store=JsonLocalHistoryStore(tmp_path / "history"),
            snapshot_root=tmp_path / "history" / "snapshots",
            domain="workspace",
            resource_id="../ws",
        ).list_entries()
