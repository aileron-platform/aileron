from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

import pytest

from aileron_file_core import (
    ArchiveMemoryEntry,
    BatchDeleteRequest,
    BatchWriteItem,
    BatchWriteRequest,
    BuildArchiveRequest,
    ExtractArchiveRequest,
    ExtractArchiveStreamRequest,
    FileCoreError,
    ListFilesRequest,
    FileLocator,
    FileOperationEngine,
    FilePolicy,
    RootedFileAdapter,
    SearchRequest,
    StaticRootResolver,
    SyncTreeItem,
    SyncTreeRequest,
    UploadFilesRequest,
    UploadItem,
    UploadStreamItem,
)


def _engine(root: Path) -> FileOperationEngine:
    return FileOperationEngine(
        adapter=RootedFileAdapter(root_resolver=StaticRootResolver(root)),
        policy=FilePolicy(max_read_bytes=1024, max_write_bytes=1024 * 1024),
    )


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_upload_files_keeps_both_conflicting_paths(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads/test.txt").write_text("old", encoding="utf-8")

    result = engine.upload_files(
        UploadFilesRequest(
            locator=locator,
            target_path="/uploads",
            files=[UploadItem(filename="test.txt", content=b"new")],
            default_strategy="keep-both",
        )
    )

    assert result.succeeded == 1
    assert result.items[0].final_path == "uploads/test_1.txt"
    assert result.items[0].status == "kept-both"
    assert (tmp_path / "uploads/test_1.txt").read_bytes() == b"new"


def test_sync_tree_writes_binary_files_and_deletes_missing_files(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="package")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/old.png").write_bytes(b"old")
    (tmp_path / "empty").mkdir()
    (tmp_path / "empty/remove.txt").write_text("remove", encoding="utf-8")

    result = engine.sync_tree(
        SyncTreeRequest(
            locator=locator,
            files=[
                SyncTreeItem(path="assets/logo.png", content=b"\x89PNG\r\n\x1a\n\x00")
            ],
        )
    )

    assert result.failed == 0
    assert (tmp_path / "assets/logo.png").read_bytes() == b"\x89PNG\r\n\x1a\n\x00"
    assert not (tmp_path / "assets/old.png").exists()
    assert not (tmp_path / "empty").exists()


def test_list_files_returns_text_and_binary_content_with_exclusions(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="package")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/readme.md").write_text("hello", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/logo.bin").write_bytes(b"abc\x00def")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/config").write_text("hidden", encoding="utf-8")

    result = engine.list_files(
        ListFilesRequest(locator=locator, path="/", include_content=True)
    )

    assert [item.path for item in result.items] == [
        "assets/logo.bin",
        "docs/readme.md",
    ]
    binary_item = result.items[0]
    text_item = result.items[1]
    assert binary_item.binary is True
    assert binary_item.content == "YWJjAGRlZg=="
    assert binary_item.content_encoding == "base64"
    assert text_item.binary is False
    assert text_item.content == "hello"
    assert text_item.content_encoding == "utf-8"


def test_list_files_excludes_generated_paths_even_when_hidden_files_are_included(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="package")
    (tmp_path / ".config").mkdir()
    (tmp_path / ".config/settings.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git/config").write_text("hidden", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__/module.pyc").write_bytes(b"cache")

    result = engine.list_files(
        ListFilesRequest(locator=locator, path="/", include_hidden=True)
    )

    assert [item.path for item in result.items] == [".config/settings.json"]


def test_extract_archive_rejects_zip_slip(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    with pytest.raises(FileCoreError) as exc_info:
        engine.extract_archive(
            ExtractArchiveRequest(
                locator=locator,
                target_path="/uploads",
                archive_name="unsafe.zip",
                archive_bytes=_zip_bytes({"../escape.txt": "bad"}),
            )
        )

    assert exc_info.value.code == "INVALID_ARCHIVE_ENTRY"


def test_extract_archive_writes_files_and_uses_conflict_strategy(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "uploads/demo").mkdir(parents=True)
    (tmp_path / "uploads/demo/app.py").write_text("old", encoding="utf-8")

    result = engine.extract_archive(
        ExtractArchiveRequest(
            locator=locator,
            target_path="/uploads",
            archive_name="demo.zip",
            archive_bytes=_zip_bytes({"demo/app.py": "new"}),
            default_strategy="keep-both",
        )
    )

    assert result.items[0].final_path == "uploads/demo/app_1.py"
    assert (tmp_path / "uploads/demo/app_1.py").read_text(encoding="utf-8") == "new"


class _BoundedReadStream(BytesIO):
    def read(self, size: int = -1) -> bytes:
        assert 0 < size <= 1024 * 1024
        return super().read(size)


def test_stream_upload_and_extract_do_not_read_the_whole_file_at_once(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    content = b"x" * (512 * 1024)
    upload_stream = _BoundedReadStream(content)

    upload_result = engine.upload_streams(
        locator=locator,
        target_path="/uploads",
        files=[
            UploadStreamItem(
                filename="large.bin",
                stream=upload_stream,
                size=len(content),
            )
        ],
    )

    assert upload_result.succeeded == 1
    assert (tmp_path / "uploads/large.bin").read_bytes() == content

    archive_content = _zip_bytes({"demo/SKILL.md": "# Demo"})
    extract_result = engine.extract_archive_stream(
        ExtractArchiveStreamRequest(
            locator=locator,
            target_path="/uploads",
            archive_name="skills.zip",
            archive_stream=BytesIO(archive_content),
            archive_size=len(archive_content),
        )
    )

    assert extract_result.items[0].final_path == "uploads/demo/SKILL.md"
    assert (tmp_path / "uploads/demo/SKILL.md").read_text() == "# Demo"


def test_stream_upload_rejects_size_mismatch_without_replacing_existing_file(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    existing = tmp_path / "uploads/existing.txt"
    existing.parent.mkdir(parents=True)
    existing.write_text("original", encoding="utf-8")

    result = engine.upload_streams(
        locator=locator,
        target_path="/uploads",
        files=[
            UploadStreamItem(
                filename="existing.txt",
                stream=BytesIO(b"replacement"),
                size=3,
            )
        ],
        default_strategy="replace",
    )

    assert result.failed == 1
    assert existing.read_text(encoding="utf-8") == "original"


def test_build_archive_removes_redundant_roots(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "docs/sub").mkdir(parents=True)
    (tmp_path / "docs/readme.md").write_text("readme", encoding="utf-8")
    (tmp_path / "docs/sub/guide.md").write_text("guide", encoding="utf-8")

    result = engine.build_archive(
        BuildArchiveRequest(locator=locator, paths=["/docs", "/docs/sub"])
    )

    assert sorted(entry.archive_path for entry in result.entries) == [
        "docs/readme.md",
        "docs/sub/guide.md",
    ]


def test_build_archive_excludes_generated_paths_inside_selected_directory(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "project/.git").mkdir(parents=True)
    (tmp_path / "project/.git/config").write_text("hidden", encoding="utf-8")
    (tmp_path / "project/__pycache__").mkdir(parents=True)
    (tmp_path / "project/__pycache__/module.pyc").write_bytes(b"cache")
    (tmp_path / "project/src").mkdir()
    (tmp_path / "project/src/app.py").write_text("print('ok')", encoding="utf-8")

    result = engine.build_archive(BuildArchiveRequest(locator=locator, paths=["project"]))

    assert [entry.archive_path for entry in result.entries] == ["project/src/app.py"]


def test_build_archive_bytes_writes_zip_with_extra_entries_and_root(
    tmp_path: Path,
) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "plugin").mkdir()
    (tmp_path / "plugin/manifest.json").write_text("{}", encoding="utf-8")

    result = engine.build_archive_bytes(
        BuildArchiveRequest(
            locator=locator,
            paths=["/plugin"],
            archive_root="plugins/demo",
            extra_entries=[
                ArchiveMemoryEntry(
                    archive_path="marketplace.json",
                    content=b'{"plugins":[]}\n',
                )
            ],
        )
    )

    with ZipFile(BytesIO(result.content)) as archive:
        assert sorted(archive.namelist()) == [
            "marketplace.json",
            "plugins/demo/plugin/manifest.json",
        ]
        assert archive.read("marketplace.json") == b'{"plugins":[]}\n'


def test_search_matches_filename_and_content(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes/roadmap.md").write_text("plain", encoding="utf-8")
    (tmp_path / "notes/research.md").write_text("Alpha topic", encoding="utf-8")

    name_result = engine.search(SearchRequest(locator=locator, query="road"))
    content_result = engine.search(SearchRequest(locator=locator, query="alpha"))

    assert name_result.matches[0].match_type == "name"
    assert name_result.matches[0].path == "notes/roadmap.md"
    assert content_result.matches[0].match_type == "content"
    assert content_result.matches[0].line == 1


def test_batch_write_and_delete_use_engine_results(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    locator = FileLocator(domain="test", resource_id="workspace")

    write_result = engine.batch_write(
        BatchWriteRequest(
            locator=locator,
            files=[
                BatchWriteItem(path="a.txt", content="a"),
                BatchWriteItem(path="nested/b.txt", content="b"),
            ],
        )
    )
    delete_result = engine.batch_delete(
        BatchDeleteRequest(locator=locator, paths=["a.txt", "missing.txt"])
    )

    assert write_result.succeeded == 2
    assert delete_result.succeeded == 1
    assert delete_result.failed == 1
