from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from aileron_file_core import (
    CopyEntriesRequest,
    ExtractArchiveRequest,
    FileConflictResolution,
    FileCoreError,
    FileLocator,
    FileOperationEngine,
    FilePolicy,
    RootedFileAdapter,
    StaticRootResolver,
    UploadFilesRequest,
    UploadItem,
)


def _engine(root: Path) -> FileOperationEngine:
    return FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(root)),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024 * 1024),
    )


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def test_upload_preflight_reports_replace_capability_for_each_conflict(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "target").mkdir()
    (tmp_path / "target/same.txt").write_text("old", encoding="utf-8")
    (tmp_path / "target/folder.txt").mkdir()

    result = engine.preflight_upload_files(
        UploadFilesRequest(
            locator=locator,
            target_path="target",
            files=[
                UploadItem(filename="same.txt", content=b"new"),
                UploadItem(filename="folder.txt", content=b"file"),
            ],
        )
    )

    assert [(item.source_path, item.target_type, item.can_replace) for item in result.conflicts] == [
        ("same.txt", "file", True),
        ("folder.txt", "directory", False),
    ]


def test_cancel_aborts_the_whole_upload_batch(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "target").mkdir()
    (tmp_path / "target/same.txt").write_text("old", encoding="utf-8")

    result = engine.upload_files(
        UploadFilesRequest(
            locator=locator,
            target_path="target",
            files=[
                UploadItem(filename="new.txt", content=b"new"),
                UploadItem(filename="same.txt", content=b"replacement"),
            ],
        )
    )

    assert [item.status for item in result.items] == ["cancelled", "cancelled"]
    assert not (tmp_path / "target/new.txt").exists()
    assert (tmp_path / "target/same.txt").read_text(encoding="utf-8") == "old"


def test_upload_supports_batch_default_and_per_item_override(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "target").mkdir()
    (tmp_path / "target/keep.txt").write_text("old", encoding="utf-8")
    (tmp_path / "target/skip.txt").write_text("old", encoding="utf-8")

    result = engine.upload_files(
        UploadFilesRequest(
            locator=locator,
            target_path="target",
            files=[
                UploadItem(filename="keep.txt", content=b"new"),
                UploadItem(filename="skip.txt", content=b"new"),
            ],
            default_strategy="keep-both",
            resolutions=(
                FileConflictResolution(source_path="skip.txt", strategy="skip"),
            ),
        )
    )

    assert [(item.source_path, item.final_path, item.status) for item in result.items] == [
        ("keep.txt", "target/keep_1.txt", "kept-both"),
        ("skip.txt", None, "skipped"),
    ]
    assert (tmp_path / "target/keep.txt").read_text(encoding="utf-8") == "old"
    assert (tmp_path / "target/keep_1.txt").read_text(encoding="utf-8") == "new"


def test_keep_both_allocates_unique_paths_atomically(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "target").mkdir()
    (tmp_path / "target/item.txt").write_text("old", encoding="utf-8")

    def upload(content: bytes) -> str | None:
        result = engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path="target",
                files=[UploadItem(filename="item.txt", content=content)],
                default_strategy="keep-both",
            )
        )
        return result.items[0].final_path

    with ThreadPoolExecutor(max_workers=2) as pool:
        paths = set(pool.map(upload, (b"one", b"two")))

    assert paths == {"target/item_1.txt", "target/item_2.txt"}


def test_copy_replace_merges_directories_without_deleting_existing_entries(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "source/docs").mkdir(parents=True)
    (tmp_path / "source/docs/new.md").write_text("new", encoding="utf-8")
    (tmp_path / "target/docs").mkdir(parents=True)
    (tmp_path / "target/docs/existing.md").write_text("existing", encoding="utf-8")

    result = engine.copy_entries(
        CopyEntriesRequest(
            locator=locator,
            source_paths=("source/docs",),
            target_path="target",
            default_strategy="replace",
        )
    )

    assert result.items[0].status == "merged"
    assert (tmp_path / "target/docs/existing.md").read_text(encoding="utf-8") == "existing"
    assert (tmp_path / "target/docs/new.md").read_text(encoding="utf-8") == "new"


def test_replace_rejects_file_directory_type_conflict(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "source").mkdir()
    (tmp_path / "source/item").write_text("file", encoding="utf-8")
    (tmp_path / "target/item").mkdir(parents=True)

    with pytest.raises(FileCoreError) as error:
        engine.copy_entries(
            CopyEntriesRequest(
                locator=locator,
                source_paths=("source/item",),
                target_path="target",
                default_strategy="replace",
            )
        )

    assert error.value.code == "FILE_TYPE_CONFLICT"


def test_invalid_strategy_error_uses_current_execution_field_name(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    with pytest.raises(FileCoreError) as error:
        engine.upload_files(
            UploadFilesRequest(
                locator=locator,
                target_path="target",
                files=(UploadItem(filename="item.txt", content=b"item"),),
                default_strategy="overwrite",
            )
        )

    assert error.value.code == "INVALID_CONFLICT_STRATEGY"
    assert error.value.details == {"defaultStrategy": "overwrite"}


def test_extract_preflight_detects_ancestor_file_type_conflict_and_keep_both(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "target").mkdir()
    (tmp_path / "target/docs").write_text("blocking file", encoding="utf-8")
    request = ExtractArchiveRequest(
        locator=locator,
        target_path="target",
        archive_name="docs.zip",
        archive_bytes=_zip_bytes({"docs/readme.md": "content"}),
        default_strategy="keep-both",
    )

    preflight = engine.preflight_extract_archive(request)
    result = engine.extract_archive(request)

    assert [(item.target_path, item.can_replace) for item in preflight.conflicts] == [
        ("target/docs", False)
    ]
    assert result.items[0].final_path == "target/docs_1/readme.md"
    assert (tmp_path / "target/docs").read_text(encoding="utf-8") == "blocking file"
    assert (tmp_path / "target/docs_1/readme.md").read_text(encoding="utf-8") == "content"
