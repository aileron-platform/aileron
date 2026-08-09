from pathlib import Path
from os import utime

import pytest

from aileron_file_core import FileCoreError, VersionConflictError
from aileron_file_core.adapters import RootedFileAdapter, StaticRootResolver
from aileron_file_core.engine import FileOperationEngine
from aileron_file_core.models import (
    CopyEntryRequest,
    CreateEntryRequest,
    DeleteEntryRequest,
    FileLocator,
    MoveEntryRequest,
    WriteBytesRequest,
    WriteTextRequest,
)
from aileron_file_core.policies import FilePolicy


def _engine(root: Path) -> FileOperationEngine:
    return FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(root)),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024),
    )


def test_write_text_uses_compare_and_write_text_and_returns_result(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    result = engine.write_text(
        WriteTextRequest(locator=locator, path="notes.md", content="hello")
    )

    assert (tmp_path / "notes.md").read_text() == "hello"
    assert result.operation == "write"
    assert result.entry_type == "file"
    assert result.size == 5
    assert result.version_id


def test_write_bytes_preserves_custom_operation(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "notes.bin").write_bytes(b"old")

    result = engine.write_bytes(
        WriteBytesRequest(
            locator=locator,
            path="notes.bin",
            content=b"new",
            operation="restore",
        )
    )

    assert (tmp_path / "notes.bin").read_bytes() == b"new"
    assert result.operation == "restore"
    assert result.entry_type == "file"
    assert result.size == 3


def test_write_text_detects_expected_version_conflict(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    path = tmp_path / "notes.md"
    path.write_text("current")

    with pytest.raises(VersionConflictError):
        engine.write_text(
            WriteTextRequest(
                locator=locator,
                path="notes.md",
                content="next",
                expected_version_id="stale",
            )
        )


def test_write_text_rejects_content_larger_than_policy(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    with pytest.raises(FileCoreError) as exc:
        engine.write_text(
            WriteTextRequest(locator=locator, path="large.txt", content="x" * 1025)
        )

    assert exc.value.code == "FILE_TOO_LARGE"


def test_write_text_rejects_directory_target_with_structured_error(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "notes.md").mkdir()

    with pytest.raises(FileCoreError) as exc:
        engine.write_text(
            WriteTextRequest(locator=locator, path="notes.md", content="hello")
        )

    assert exc.value.code == "NOT_A_FILE"
    assert exc.value.details["path"] == "notes.md"


def test_write_text_file_ancestor_raises_structured_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "src").write_text("not a directory")

    with pytest.raises(FileCoreError) as exc:
        engine.write_text(
            WriteTextRequest(locator=locator, path="src/pkg/app.py", content="hello")
        )

    assert exc.value.code == "FILE_ALREADY_EXISTS"
    assert exc.value.details["path"] == "src/pkg/app.py"


def test_create_entry_creates_file_and_directory(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    file_result = engine.create_entry(
        CreateEntryRequest(
            locator=locator,
            path="src/app.py",
            entry_type="file",
            content="print('ok')",
        )
    )
    directory_result = engine.create_entry(
        CreateEntryRequest(locator=locator, path="docs", entry_type="directory")
    )

    assert file_result.operation == "create"
    assert file_result.entry_type == "file"
    assert (tmp_path / "src/app.py").is_file()
    assert directory_result.operation == "create"
    assert directory_result.entry_type == "directory"
    assert (tmp_path / "docs").is_dir()


def test_create_entry_parent_file_raises_structured_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "src").write_text("not a directory")

    with pytest.raises(FileCoreError) as exc:
        engine.create_entry(
            CreateEntryRequest(
                locator=locator,
                path="src/app.py",
                entry_type="file",
                content="print('ok')",
            )
        )

    assert exc.value.code == "FILE_ALREADY_EXISTS"
    assert exc.value.details["path"] == "src/app.py"


def test_create_entry_file_ancestor_raises_structured_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "src").write_text("not a directory")

    with pytest.raises(FileCoreError) as exc:
        engine.create_entry(
            CreateEntryRequest(
                locator=locator,
                path="src/pkg/app.py",
                entry_type="file",
                content="print('ok')",
            )
        )

    assert exc.value.code == "FILE_ALREADY_EXISTS"
    assert exc.value.details["path"] == "src/pkg/app.py"


def test_delete_entry_rejects_non_empty_directory_without_recursive(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/readme.md").write_text("readme")

    with pytest.raises(FileCoreError) as exc:
        engine.delete_entry(DeleteEntryRequest(locator=locator, path="docs"))

    assert exc.value.code == "DIRECTORY_NOT_EMPTY"


def test_delete_entry_cleans_empty_parent_directories_when_policy_allows(
    tmp_path: Path,
) -> None:
    engine = FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path)),
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024,
            cleanup_empty_parents=True,
        ),
    )
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "src/pkg").mkdir(parents=True)
    (tmp_path / "src/pkg/notes.md").write_text("readme")

    engine.delete_entry(DeleteEntryRequest(locator=locator, path="src/pkg/notes.md"))

    assert not (tmp_path / "src").exists()
    assert tmp_path.exists()


def test_move_entry_and_copy_entry_work_for_files(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "notes.md").write_text("hello")

    copy_result = engine.copy_entry(
        CopyEntryRequest(locator=locator, source_path="notes.md", dest_path="copy.md")
    )
    move_result = engine.move_entry(
        MoveEntryRequest(locator=locator, source_path="notes.md", dest_path="moved.md")
    )

    assert copy_result.operation == "copy"
    assert copy_result.entry_type == "file"
    assert (tmp_path / "copy.md").read_text() == "hello"
    assert (tmp_path / "moved.md").read_text() == "hello"
    assert (tmp_path / "notes.md").exists() is False
    assert move_result.operation == "move"
    assert move_result.entry_type == "file"


def test_copy_and_move_file_ancestor_raise_structured_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "source.txt").write_text("hello")
    (tmp_path / "dest").write_text("not a directory")

    with pytest.raises(FileCoreError) as copy_exc:
        engine.copy_entry(
            CopyEntryRequest(
                locator=locator,
                source_path="source.txt",
                dest_path="dest/nested/copy.txt",
            )
        )
    with pytest.raises(FileCoreError) as move_exc:
        engine.move_entry(
            MoveEntryRequest(
                locator=locator,
                source_path="source.txt",
                dest_path="dest/nested/moved.txt",
            )
        )

    assert copy_exc.value.code == "FILE_ALREADY_EXISTS"
    assert copy_exc.value.details["path"] == "dest/nested/copy.txt"
    assert move_exc.value.code == "FILE_ALREADY_EXISTS"
    assert move_exc.value.details["path"] == "dest/nested/moved.txt"


def test_copy_and_move_reject_same_or_nested_paths(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "source.txt").write_text("hello")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.md").write_text("hello")

    with pytest.raises(FileCoreError) as same_exc:
        engine.copy_entry(
            CopyEntryRequest(
                locator=locator,
                source_path="source.txt",
                dest_path="source.txt",
            )
        )
    with pytest.raises(FileCoreError) as nested_copy_exc:
        engine.copy_entry(
            CopyEntryRequest(
                locator=locator,
                source_path="docs",
                dest_path="docs/nested",
            )
        )
    with pytest.raises(FileCoreError) as nested_move_exc:
        engine.move_entry(
            MoveEntryRequest(
                locator=locator,
                source_path="docs",
                dest_path="docs/nested",
            )
        )

    assert same_exc.value.code == "FILE_ALREADY_EXISTS"
    assert nested_copy_exc.value.code == "INVALID_OPERATION"
    assert nested_move_exc.value.code == "INVALID_OPERATION"


def test_copy_directory_rejects_symlink_descendant(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("hidden")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "escape").symlink_to(outside, target_is_directory=True)

    with pytest.raises(FileCoreError) as exc:
        _engine(tmp_path).copy_entry(
            CopyEntryRequest(
                locator=FileLocator(domain="test", resource_id="workspace"),
                source_path="docs",
                dest_path="copy",
            )
        )

    assert exc.value.code == "UNSUPPORTED_SYMLINK"
    assert not (tmp_path / "copy").exists()


def test_copy_and_move_reject_symlink_source(tmp_path: Path) -> None:
    (tmp_path / "target.txt").write_text("hello")
    (tmp_path / "link.txt").symlink_to(tmp_path / "target.txt")
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    with pytest.raises(FileCoreError) as copy_exc:
        engine.copy_entry(
            CopyEntryRequest(
                locator=locator,
                source_path="link.txt",
                dest_path="copy.txt",
            )
        )
    with pytest.raises(FileCoreError) as move_exc:
        engine.move_entry(
            MoveEntryRequest(
                locator=locator,
                source_path="link.txt",
                dest_path="moved.txt",
            )
        )

    assert copy_exc.value.code == "UNSUPPORTED_SYMLINK"
    assert copy_exc.value.details["path"] == "link.txt"
    assert move_exc.value.code == "UNSUPPORTED_SYMLINK"
    assert move_exc.value.details["path"] == "link.txt"


def test_copy_entry_preserves_metadata_only_when_policy_allows(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello")
    old_timestamp = 1_600_000_000
    utime(source, (old_timestamp, old_timestamp))
    locator = FileLocator(domain="test", resource_id="workspace")

    _engine(tmp_path).copy_entry(
        CopyEntryRequest(locator=locator, source_path="source.txt", dest_path="plain.txt")
    )
    preserving_engine = FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(tmp_path)),
        policy=FilePolicy(
            max_read_bytes=1024,
            max_write_bytes=1024,
            preserve_copy_metadata=True,
        ),
    )
    preserving_engine.copy_entry(
        CopyEntryRequest(
            locator=locator,
            source_path="source.txt",
            dest_path="preserved.txt",
        )
    )

    assert int((tmp_path / "plain.txt").stat().st_mtime) != old_timestamp
    assert int((tmp_path / "preserved.txt").stat().st_mtime) == old_timestamp


def test_move_entry_does_not_preserve_metadata_by_default(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("hello")
    old_timestamp = 1_600_000_000
    utime(source, (old_timestamp, old_timestamp))

    _engine(tmp_path).move_entry(
        MoveEntryRequest(
            locator=FileLocator(domain="test", resource_id="workspace"),
            source_path="source.txt",
            dest_path="moved.txt",
        )
    )

    assert int((tmp_path / "moved.txt").stat().st_mtime) != old_timestamp
