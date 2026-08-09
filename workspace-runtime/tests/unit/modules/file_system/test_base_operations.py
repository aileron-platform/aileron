from __future__ import annotations

import base64
from datetime import datetime, timezone
from io import BytesIO
import os
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from aileron_file_core import resolve_safe_path
from aileron_file_core.conformance import assert_engine_conformance
from app.modules.file_system.base_operations import BaseFileService
from app.modules.file_system.exceptions import (
    ContentConflictException,
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileManagementException,
    FileNotFoundException,
    FileTooLargeException,
    InvalidPathException,
    ReadonlyScopeException,
)


class DummyFileService(BaseFileService):
    def __init__(self, root_path: Path, readonly_scopes: set[str] | None = None):
        super().__init__(root_path)
        self.readonly_scopes = readonly_scopes or set()

    def resolve_scope_path(self, scope: str | None, relative_path: str) -> Path:
        root = self._root_path / scope if scope else self._root_path
        return resolve_safe_path(root, relative_path.lstrip("/") or ".").absolute_path

    def validate_scope(self, scope: str | None) -> bool:
        return True

    def is_readonly_scope(self, scope: str | None) -> bool:
        return bool(scope and scope in self.readonly_scopes)


@pytest.fixture
def service(tmp_path: Path) -> DummyFileService:
    return DummyFileService(tmp_path)


def test_get_tree_creates_missing_root_directory(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=2),
    )

    result = service.get_tree("/")

    assert result == {"path": "/", "scope": None, "nodes": [], "total": 0}


def test_get_tree_raises_for_missing_non_root_path(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=3),
    )

    with pytest.raises(FileNotFoundException):
        service.get_tree("/missing")


def test_get_tree_filters_hidden_and_skip_directories(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    (service._root_path / "src").mkdir()
    (service._root_path / "src" / "main.py").write_text("print('ok')", encoding="utf-8")
    (service._root_path / ".env").write_text("SECRET=1", encoding="utf-8")
    (service._root_path / "node_modules").mkdir()
    (service._root_path / "docs").mkdir()

    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=5),
    )

    result = service.get_tree("/", include_hidden=False, max_depth=99)

    assert result["total"] == 2
    assert [node["name"] for node in result["nodes"]] == ["docs", "src"]
    src_node = result["nodes"][1]
    assert src_node["type"] == "directory"
    assert src_node["hasChildren"] is True
    assert src_node["children"][0]["path"] == "/src/main.py"


def test_get_tree_respects_include_hidden_and_max_depth(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = service._root_path / ".config" / "deep"
    nested.mkdir(parents=True)
    (nested / "app.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=1),
    )

    result = service.get_tree("/", include_hidden=True, max_depth=10)

    assert result["nodes"][0]["name"] == ".config"
    assert result["nodes"][0]["children"][0]["name"] == "deep"
    assert result["nodes"][0]["children"][0]["children"] == []
    assert result["nodes"][0]["children"][0]["hasChildren"] is True


def test_file_tree_excludes_runtime_local_history(tmp_path: Path) -> None:
    service = DummyFileService(root_path=tmp_path / "workspace")
    history_file = service._root_path / ".aileron" / "local-history" / "entries.jsonl"
    history_file.parent.mkdir(parents=True)
    history_file.write_text("{}", encoding="utf-8")
    visible_file = service._root_path / ".aileron" / "generated-images" / "image.txt"
    visible_file.parent.mkdir(parents=True)
    visible_file.write_text("visible", encoding="utf-8")

    tree = service.get_tree("", include_hidden=True)

    def collect_paths(nodes: list[dict]) -> set[str]:
        paths = set()
        for node in nodes:
            paths.add(node["path"])
            paths.update(collect_paths(node.get("children", [])))
        return paths

    paths = collect_paths(tree["nodes"])
    assert "/.aileron/local-history" not in paths
    assert "/.aileron/local-history/entries.jsonl" not in paths
    assert "/.aileron/generated-images" in paths


def test_file_api_rejects_runtime_local_history_path(tmp_path: Path) -> None:
    service = DummyFileService(root_path=tmp_path / "workspace")
    target = service._root_path / ".aileron" / "local-history" / "entries.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")

    with pytest.raises(FileManagementException) as exc:
        service.read_file(".aileron/local-history/entries.jsonl")

    assert exc.value.status_code == 400


def test_get_tree_keeps_directory_expandable_without_extra_empty_probe(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep_dir = service._root_path / "truncated" / "nested"
    deep_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=2),
    )

    result = service.get_tree("/", include_hidden=False, max_depth=1)

    truncated_node = next(
        node for node in result["nodes"] if node["name"] == "truncated"
    )
    assert truncated_node["type"] == "directory"
    nested_node = truncated_node["children"][0]
    assert nested_node["name"] == "nested"
    assert nested_node["children"] == []
    assert nested_node["hasChildren"] is True


def test_get_tree_raises_when_target_is_file(
    service: DummyFileService, monkeypatch: pytest.MonkeyPatch
) -> None:
    (service._root_path / "demo.txt").write_text("demo", encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.file_system.base_operations.get_settings",
        lambda: SimpleNamespace(FILE_TREE_MAX_DEPTH=2),
    )

    with pytest.raises(InvalidPathException):
        service.get_tree("/demo.txt")


def test_read_file_returns_text_content_with_hash(service: DummyFileService) -> None:
    file_path = service._root_path / "notes.txt"
    file_path.write_text("hello", encoding="utf-8")

    result = service.read_file("/notes.txt")

    assert result["content"] == "hello"
    assert result["size"] == 5
    assert len(result["revision"]) == 64


def test_read_file_truncates_large_line_count(service: DummyFileService) -> None:
    lines = "\n".join(f"line-{i}" for i in range(1002))
    (service._root_path / "many-lines.txt").write_text(lines, encoding="utf-8")

    result = service.read_file("/many-lines.txt")

    assert "... (truncated, 2 more lines)" in result["content"]
    assert len(result["revision"]) == 64


def test_read_file_returns_large_file_message_without_loading_content(
    service: DummyFileService,
) -> None:
    file_path = service._root_path / "big.txt"
    file_path.write_bytes(b"a" * (1024 * 1024 + 1))

    result = service.read_file("/big.txt")

    assert "Large text file: /big.txt" in result["content"]
    assert len(result["revision"]) == 64


def test_read_file_returns_binary_message_for_null_bytes(
    service: DummyFileService,
) -> None:
    file_path = service._root_path / "blob.bin"
    file_path.write_bytes(b"abc\x00def")

    result = service.read_file("/blob.bin")

    assert "Binary file: /blob.bin" in result["content"]
    assert len(result["revision"]) == 64


def test_read_file_treats_unicode_decode_error_as_binary(
    service: DummyFileService,
) -> None:
    file_path = service._root_path / "strange.txt"
    file_path.write_bytes(b"\xff\xfe\xfd")

    result = service.read_file("/strange.txt")

    assert (
        result["content"] == "Binary file: /strange.txt\n(File encoding is not UTF-8)"
    )


def test_read_file_binary_reads_bytes(service: DummyFileService) -> None:
    payload = b"\x00\x01demo"
    (service._root_path / "payload.bin").write_bytes(payload)

    assert service.read_file_binary("/payload.bin") == payload


def test_read_file_and_binary_raise_for_missing_or_invalid_paths(
    service: DummyFileService,
) -> None:
    (service._root_path / "folder").mkdir()

    with pytest.raises(FileNotFoundException):
        service.read_file("/missing.txt")

    with pytest.raises(InvalidPathException):
        service.read_file("/folder")

    with pytest.raises(InvalidPathException):
        service.read_file_binary("/folder")


def test_write_file_persists_content(service: DummyFileService) -> None:
    result = service.write_file("/nested/demo.txt", "hello world")

    assert (service._root_path / "nested" / "demo.txt").read_text(
        encoding="utf-8"
    ) == "hello world"
    assert result["size"] == 11


def test_write_file_rejects_stale_expected_version(service: DummyFileService) -> None:
    service.write_file("/README.md", "first")
    original = service.read_file("/README.md")

    service.write_file("/README.md", "second", revision=original["revision"])

    with pytest.raises(ContentConflictException) as exc_info:
        service.write_file("/README.md", "third", revision=original["revision"])

    current = service.read_file("/README.md")
    assert exc_info.value.status_code == 409
    assert exc_info.value.details["path"] == "/README.md"
    assert exc_info.value.details["expectedRevision"] == original["revision"]
    assert exc_info.value.details["actualRevision"] == current["revision"]
    assert "expectedVersion" not in exc_info.value.details
    assert "actualVersion" not in exc_info.value.details
    assert current["content"] == "second"


def test_write_file_success_returns_new_content_hash_version(
    service: DummyFileService,
) -> None:
    result = service.write_file("/README.md", "first")
    read_result = service.read_file("/README.md")

    assert result["revision"] == read_result["revision"]
    assert len(result["revision"]) == 64


def test_write_file_builds_response_metadata_before_releasing_lock(
    service: DummyFileService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = service._root_path / "README.md"
    external_mtime = 4_102_444_800

    class MutatingLockManager:
        def lock(self, key):  # noqa: ANN001
            class LockContext:
                def __enter__(self):
                    return None

                def __exit__(self, exc_type, exc, traceback):  # noqa: ANN001
                    target.write_text("external overwrite", encoding="utf-8")
                    os.utime(target, (external_mtime, external_mtime))
                    return False

            return LockContext()

    monkeypatch.setattr(
        "app.modules.file_system.base_operations._resource_write_locks",
        MutatingLockManager(),
    )

    result = service.write_file("/README.md", "first")

    assert result["size"] == len("first")
    assert (
        result["updatedAt"]
        != datetime.fromtimestamp(external_mtime, timezone.utc).isoformat()
    )


def test_write_file_rejects_readonly_scope_and_large_content(tmp_path: Path) -> None:
    readonly_service = DummyFileService(tmp_path, readonly_scopes={"readonly"})

    with pytest.raises(ReadonlyScopeException):
        readonly_service.write_file("/demo.txt", "x", scope="readonly")

    with pytest.raises(FileTooLargeException):
        readonly_service.write_file(
            "/big.txt", "a" * (BaseFileService.MAX_FILE_SIZE + 1)
        )


def test_create_entry_supports_text_file_base64_and_directory(
    service: DummyFileService,
) -> None:
    file_result = service.create_entry("/plain.txt", "file", content="hello")
    encoded = base64.b64encode(b"\x00\x01").decode("ascii")
    binary_result = service.create_entry(
        "/bin/data.bin", "file", content=encoded, encoding="base64"
    )
    dir_result = service.create_entry("/new-dir", "directory")

    assert file_result["type"] == "file"
    assert binary_result["size"] == 2
    assert (service._root_path / "bin" / "data.bin").read_bytes() == b"\x00\x01"
    assert dir_result["type"] == "directory"


def test_create_entry_rejects_readonly_duplicate_and_invalid_type(
    tmp_path: Path,
) -> None:
    readonly_service = DummyFileService(tmp_path, readonly_scopes={"readonly"})

    with pytest.raises(ReadonlyScopeException):
        readonly_service.create_entry("/demo.txt", "file", scope="readonly")

    readonly_service.create_entry("/demo.txt", "file")
    with pytest.raises(FileAlreadyExistsException):
        readonly_service.create_entry("/demo.txt", "file")

    with pytest.raises(InvalidPathException):
        readonly_service.create_entry("/invalid", "symlink")


def test_delete_entry_handles_files_directories_and_recursive_cleanup(
    service: DummyFileService,
) -> None:
    deep_file = service._root_path / "a" / "b" / "demo.txt"
    deep_file.parent.mkdir(parents=True)
    deep_file.write_text("x", encoding="utf-8")

    result = service.delete_entry("/a/b/demo.txt")

    assert result["type"] == "file"
    assert not (service._root_path / "a").exists()

    non_empty = service._root_path / "dir"
    (non_empty / "child").mkdir(parents=True)
    with pytest.raises(DirectoryNotEmptyException):
        service.delete_entry("/dir")

    recursive_result = service.delete_entry("/dir", recursive=True)
    assert recursive_result["type"] == "directory"


def test_delete_entry_rejects_readonly_and_missing(tmp_path: Path) -> None:
    readonly_service = DummyFileService(tmp_path, readonly_scopes={"readonly"})

    with pytest.raises(ReadonlyScopeException):
        readonly_service.delete_entry("/demo.txt", scope="readonly")

    with pytest.raises(FileNotFoundException):
        readonly_service.delete_entry("/demo.txt")


def test_copy_entry_supports_file_directory_and_existing_destination_directory(
    service: DummyFileService,
) -> None:
    source_file = service._root_path / "src.txt"
    source_file.write_text("copy me", encoding="utf-8")
    destination_dir = service._root_path / "dest"
    destination_dir.mkdir()

    file_result = service.copy_entry("/src.txt", "/dest")

    assert file_result["destPath"] == "/dest/src.txt"
    assert (destination_dir / "src.txt").read_text(encoding="utf-8") == "copy me"

    source_tree = service._root_path / "folder" / "nested"
    source_tree.mkdir(parents=True)
    (source_tree / "data.txt").write_text("v", encoding="utf-8")
    dir_result = service.copy_entry("/folder", "/folder-copy")

    assert dir_result["type"] == "directory"
    assert (service._root_path / "folder-copy" / "nested" / "data.txt").read_text(
        encoding="utf-8"
    ) == "v"


def test_copy_entry_rejects_readonly_missing_and_duplicate(
    service: DummyFileService, tmp_path: Path
) -> None:
    readonly_service = DummyFileService(tmp_path, readonly_scopes={"readonly"})
    (readonly_service._root_path / "src.txt").write_text("content", encoding="utf-8")
    (readonly_service._root_path / "existing.txt").write_text("old", encoding="utf-8")

    with pytest.raises(ReadonlyScopeException):
        readonly_service.copy_entry("/src.txt", "/target.txt", dest_scope="readonly")

    with pytest.raises(FileNotFoundException):
        readonly_service.copy_entry("/missing.txt", "/target.txt")

    with pytest.raises(FileAlreadyExistsException):
        readonly_service.copy_entry("/src.txt", "/existing.txt")


def test_paste_replace_merges_directory_and_preserves_existing_tree(
    service: DummyFileService,
) -> None:
    (service._root_path / "source" / "v2").mkdir(parents=True)
    (service._root_path / "source" / "v2" / "data.txt").write_text(
        "new", encoding="utf-8"
    )
    (service._root_path / "target" / "source").mkdir(parents=True)
    (service._root_path / "target" / "source" / "old.txt").write_text(
        "old", encoding="utf-8"
    )

    result = service.paste_entries(
        source_paths=["/source"],
        target_path="/target",
        default_strategy="replace",
        resolutions=[],
    )

    assert result["items"][0]["status"] == "merged"
    assert (service._root_path / "target" / "source" / "v2" / "data.txt").read_text(
        encoding="utf-8"
    ) == "new"
    assert (service._root_path / "target" / "source" / "old.txt").read_text(
        encoding="utf-8"
    ) == "old"


def test_paste_replace_rejects_type_conflict(service: DummyFileService) -> None:
    (service._root_path / "source.txt").write_text("source", encoding="utf-8")
    (service._root_path / "target" / "source.txt").mkdir(parents=True)

    with pytest.raises(FileManagementException) as exc_info:
        service.paste_entries(
            source_paths=["/source.txt"],
            target_path="/target",
            default_strategy="replace",
            resolutions=[],
        )

    assert exc_info.value.code == "FILE_TYPE_CONFLICT"


def test_move_entry_supports_rename_directory_target_and_cleanup(
    service: DummyFileService,
) -> None:
    source_file = service._root_path / "from" / "demo.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("move", encoding="utf-8")

    result = service.move_entry("/from/demo.txt", "/renamed/demo.txt")

    assert result["type"] == "file"
    assert not (service._root_path / "from").exists()
    assert (service._root_path / "renamed" / "demo.txt").read_text(
        encoding="utf-8"
    ) == "move"

    (service._root_path / "source-dir").mkdir()
    (service._root_path / "source-dir" / "x.txt").write_text("x", encoding="utf-8")
    (service._root_path / "existing-dir").mkdir()

    moved_into_dir = service.move_entry("/source-dir", "/existing-dir")
    assert moved_into_dir["destPath"] == "/existing-dir/source-dir"
    assert (service._root_path / "existing-dir" / "source-dir" / "x.txt").exists()


def test_move_entry_rejects_readonly_missing_and_duplicate(tmp_path: Path) -> None:
    readonly_service = DummyFileService(tmp_path, readonly_scopes={"source", "dest"})
    (readonly_service._root_path / "demo.txt").write_text("content", encoding="utf-8")
    (readonly_service._root_path / "existing.txt").write_text(
        "existing", encoding="utf-8"
    )

    with pytest.raises(ReadonlyScopeException):
        readonly_service.move_entry("/demo.txt", "/new.txt", source_scope="source")

    with pytest.raises(ReadonlyScopeException):
        readonly_service.move_entry("/demo.txt", "/new.txt", dest_scope="dest")

    with pytest.raises(FileNotFoundException):
        DummyFileService(tmp_path).move_entry("/missing.txt", "/new.txt")

    service = DummyFileService(tmp_path)
    with pytest.raises(FileAlreadyExistsException):
        service.move_entry("/demo.txt", "/existing.txt")


def test_batch_delete_and_batch_write_collect_success_and_failure(
    service: DummyFileService,
) -> None:
    (service._root_path / "keep").mkdir()
    (service._root_path / "delete-me.txt").write_text("bye", encoding="utf-8")

    delete_result = service.batch_delete(["/delete-me.txt", "/missing.txt"])
    write_result = service.batch_write(
        [
            {"path": "/ok.txt", "content": "ok"},
            {
                "path": "/too-large.txt",
                "content": "a" * (BaseFileService.MAX_FILE_SIZE + 1),
            },
        ]
    )

    assert delete_result["succeeded"] == 1
    assert delete_result["failed"] == 1
    assert write_result["succeeded"] == 1
    assert write_result["failed"] == 1


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_workspace_facade_uses_core_for_upload_extract_search_and_batch(
    service: DummyFileService,
) -> None:
    upload_result = service.upload_file_bytes(
        target_path="/imports",
        filename="notes.md",
        content=b"alpha",
        default_strategy="replace",
        resolutions=[],
    )
    extract_result = service.extract_archive_bytes(
        target_path="/imports",
        archive_name="docs.zip",
        archive_bytes=_zip_bytes({"guide.md": b"beta topic"}),
        default_strategy="replace",
        resolutions=[],
    )
    search_result = service.search_entries(query="beta")
    batch_result = service.batch_write([{"path": "/batch/result.txt", "content": "ok"}])

    assert upload_result["items"][0]["finalPath"] == "imports/notes.md"
    assert extract_result["items"][0]["finalPath"] == "imports/guide.md"
    assert search_result["results"][0]["path"] == "/imports/guide.md"
    assert batch_result["succeeded"] == 1


def test_workspace_facade_maps_successful_stream_uploads_before_api_serialization(
    service: DummyFileService,
) -> None:
    result = service.upload_file_streams(
        target_path="/imports",
        files=[("notes.md", BytesIO(b"alpha"), 5)],
        default_strategy="replace",
        resolutions=[],
    )

    assert result == {
        "items": [
            {
                "sourcePath": "notes.md",
                "finalPath": "imports/notes.md",
                "status": "created",
                "size": 5,
                "type": "file",
                "error": None,
            }
        ],
        "total": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
    }


def test_workspace_facade_preflights_upload_streams_with_core(
    service: DummyFileService,
) -> None:
    (service._root_path / "imports").mkdir()
    (service._root_path / "imports" / "notes.md").write_text(
        "existing", encoding="utf-8"
    )

    result = service.preflight_upload_streams(
        target_path="/imports",
        files=[("notes.md", BytesIO(b"new"), 3)],
    )

    assert result == {
        "conflicts": [
            {
                "sourcePath": "notes.md",
                "targetPath": "imports/notes.md",
                "sourceType": "file",
                "targetType": "file",
                "canReplace": True,
            }
        ],
        "total": 1,
    }


def test_workspace_engine_satisfies_shared_file_core_conformance(
    service: DummyFileService,
) -> None:
    assert_engine_conformance(
        engine=service._engine(),
        locator=service._locator(None),
    )
