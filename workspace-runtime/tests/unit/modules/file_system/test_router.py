from __future__ import annotations

from datetime import datetime, timezone
import importlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import zipfile

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import Response

from app.modules.file_system.exceptions import (
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileManagementException,
    FileNotFoundException,
    ReadonlyScopeException,
)
from app.modules.file_system.models import (
    BatchDeleteRequest,
    BatchWriteRequest,
    ExtractArchiveRequest,
    FileContentResponse,
    FileCopyRequest,
    FileCreateRequest,
    FileMoveRequest,
    FileOperationResponse,
    FileTreeResponse,
    FileWriteRequest,
    UploadResponse,
)
from app.modules.file_system.router import (
    _resolve_file_service_root,
    batch_delete_entries,
    batch_write_files,
    copy_entry,
    create_entry,
    delete_entry,
    extract_archive,
    get_directory_children,
    get_extract_archive_status,
    get_file_tree,
    move_entry,
    read_file,
    upload_files,
    write_file,
)
from app.modules.version_control.service import VersionControlError

file_system_router_module = importlib.import_module("app.modules.file_system.router")


class DummyFileService:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path

    def get_tree(self, **kwargs):
        return {"path": kwargs["path"], "scope": kwargs.get("scope"), "nodes": [], "total": 0}

    def read_file(self, path: str, scope=None):
        if path.endswith("missing.txt"):
            raise FileNotFoundException(path)
        if path.startswith("/uploads/"):
            fs_path = self.resolve_scope_path(scope, path)
            if not fs_path.exists():
                raise FileNotFoundException(path)
        return {
            "path": path,
            "scope": scope,
            "content": "hello",
            "size": 5,
            "updatedAt": "2024-01-01T00:00:00Z",
        }

    def read_file_binary(self, path: str, scope=None):
        return b"\x89PNG"

    def write_file(self, **kwargs):
        return {"path": kwargs["path"]}

    def batch_write(self, files, scope=None):
        return {"total": len(files), "succeeded": len(files), "failed": 0, "results": [{"success": True} for _ in files]}

    def create_entry(self, **kwargs):
        return {"path": kwargs["path"]}

    def delete_entry(self, **kwargs):
        return {"path": kwargs["path"]}

    def batch_delete(self, **kwargs):
        return {"total": len(kwargs["paths"]), "succeeded": len(kwargs["paths"]), "failed": 0, "results": [{"success": True} for _ in kwargs["paths"]]}

    def copy_entry(self, **kwargs):
        return {"path": kwargs["dest_path"]}

    def move_entry(self, **kwargs):
        return {"path": kwargs["dest_path"]}

    def resolve_scope_path(self, scope, full_path: str) -> Path:
        return self.tmp_path / full_path.lstrip("/")


@pytest.mark.asyncio
async def test_file_tree_routes_success(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    result = await get_file_tree("/", None, False, 2, service)
    children = await get_directory_children("/src", None, False, 1, service)
    assert isinstance(result, FileTreeResponse)
    assert children.path == "/src"


@pytest.mark.asyncio
async def test_read_file_raw_and_text(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    text_result = await read_file("/a.txt", None, False, service)
    raw_result = await read_file("/image.png", None, True, service)
    assert isinstance(text_result, FileContentResponse)
    assert isinstance(raw_result, Response)


@pytest.mark.asyncio
async def test_file_operations_success(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    assert isinstance(await write_file(FileWriteRequest(path="/a.txt", content="x"), service), FileOperationResponse)
    assert (await batch_write_files(BatchWriteRequest(files=[{"path": "/a.txt", "content": "x"}]), service)).succeeded == 1
    assert (await create_entry(FileCreateRequest(path="/dir", type="directory"), service)).success is True
    assert (await delete_entry("/dir", None, False, service)).success is True
    assert (await batch_delete_entries(BatchDeleteRequest(paths=["/a", "/b"]), service)).total == 2
    assert (await copy_entry(FileCopyRequest(sourcePath="/a", destPath="/b"), service)).success is True
    assert (await move_entry(FileMoveRequest(sourcePath="/a", destPath="/b"), service)).success is True


@pytest.mark.asyncio
async def test_file_operations_error_mapping(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    service.read_file = Mock(side_effect=FileNotFoundException("missing"))
    with pytest.raises(HTTPException) as exc_info:
        await read_file("/missing.txt", None, False, service)
    assert exc_info.value.status_code == 404

    service.copy_entry = Mock(side_effect=FileAlreadyExistsException("/b"))
    with pytest.raises(HTTPException) as exc_copy:
        await copy_entry(FileCopyRequest(sourcePath="/a", destPath="/b"), service)
    assert exc_copy.value.status_code == 409

    service.move_entry = Mock(side_effect=FileManagementException("FILE_ERROR", "bad"))
    with pytest.raises(HTTPException) as exc_move:
        await move_entry(FileMoveRequest(sourcePath="/a", destPath="/b"), service)
    assert exc_move.value.status_code == 400


@pytest.mark.asyncio
async def test_file_tree_routes_error_mapping(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    service.get_tree = Mock(side_effect=FileNotFoundException("/missing"))
    with pytest.raises(HTTPException) as exc_tree:
        await get_file_tree("/missing", None, False, 2, service)
    assert exc_tree.value.status_code == 404

    service.get_tree = Mock(side_effect=FileManagementException("TREE_ERROR", "bad tree"))
    with pytest.raises(HTTPException) as exc_children:
        await get_directory_children("/bad", None, False, 2, service)
    assert exc_children.value.status_code == 400


@pytest.mark.asyncio
async def test_write_create_delete_map_specific_errors(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    service.write_file = Mock(side_effect=ReadonlyScopeException("readonly"))
    with pytest.raises(HTTPException) as exc_write:
        await write_file(FileWriteRequest(path="/a.txt", content="x"), service)
    assert exc_write.value.status_code == 403

    service.create_entry = Mock(side_effect=FileAlreadyExistsException("/dir"))
    with pytest.raises(HTTPException) as exc_create:
        await create_entry(FileCreateRequest(path="/dir", type="directory"), service)
    assert exc_create.value.status_code == 409

    service.delete_entry = Mock(side_effect=DirectoryNotEmptyException("/dir"))
    with pytest.raises(HTTPException) as exc_delete:
        await delete_entry("/dir", None, False, service)
    assert exc_delete.value.status_code == 400


@pytest.mark.asyncio
async def test_read_file_raw_uses_default_binary_mime_for_unknown_extension(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    raw_result = await read_file("/blob.unknownext", None, True, service)

    assert isinstance(raw_result, Response)
    assert raw_result.media_type == "application/octet-stream"
    assert raw_result.headers["content-disposition"] == 'inline; filename="blob.unknownext"'


@pytest.mark.asyncio
async def test_upload_files_supports_rename_and_skip(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)

    existing = service.resolve_scope_path(None, "/uploads/test.txt")
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("old", encoding="utf-8")

    file1 = SimpleNamespace(filename="test.txt", read=AsyncMock(return_value=b"new"))
    file2 = SimpleNamespace(filename="bad.txt", read=AsyncMock(side_effect=RuntimeError("boom")))

    result = await upload_files("/uploads", "rename", "store", False, [file1, file2], service)

    assert isinstance(result, UploadResponse)
    assert len(result.uploaded) == 1
    assert result.extracted == []
    assert result.uploaded[0].path.endswith("test_1.txt")
    assert len(result.skipped) == 1


@pytest.mark.asyncio
async def test_upload_files_supports_overwrite_strategy(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    existing = service.resolve_scope_path(None, "/uploads/test.txt")
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text("old", encoding="utf-8")

    file1 = SimpleNamespace(filename="test.txt", read=AsyncMock(return_value=b"new-content"))
    result = await upload_files("/uploads", "overwrite", "store", False, [file1], service)

    assert result.skipped == []
    assert result.uploaded[0].path == "/uploads/test.txt"
    assert existing.read_bytes() == b"new-content"


@pytest.mark.asyncio
async def test_upload_files_extracts_zip_when_requested(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/src/index.ts", "console.log('ok');")

    zip_file = SimpleNamespace(filename="demo.zip", read=AsyncMock(return_value=archive_buffer.getvalue()))
    result = await upload_files("/uploads", "rename", "extract", False, [zip_file], service)

    assert result.uploaded == []
    assert len(result.extracted) == 1
    assert result.extracted[0].path == "/uploads/demo/src/index.ts"
    assert (tmp_path / "uploads" / "demo" / "src" / "index.ts").read_text(encoding="utf-8") == "console.log('ok');"


@pytest.mark.asyncio
async def test_upload_files_rejects_zip_with_unsafe_entry(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    zip_file = SimpleNamespace(filename="unsafe.zip", read=AsyncMock(return_value=archive_buffer.getvalue()))

    with pytest.raises(HTTPException) as exc_info:
        await upload_files("/uploads", "rename", "extract", False, [zip_file], service)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "INVALID_ARCHIVE_ENTRY"


def test_resolve_file_service_root_uses_git_context(monkeypatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    resolved_context_path = workspace_root / ".worktrees" / "feature-auth"
    resolved_context_path.mkdir(parents=True)

    class StubGitUtils:
        def __init__(self, base_path: Path, worktree_subdir: str = ".worktrees") -> None:
            assert base_path == workspace_root.parent
            assert worktree_subdir == ".worktrees"

        def resolve_context_path(self, workspace_id: str, context_id: str) -> Path:
            assert workspace_id == workspace_root.name
            assert context_id == "worktree:feature-auth"
            return resolved_context_path

    monkeypatch.setattr(file_system_router_module, "get_settings", lambda: SimpleNamespace(WORKSPACE_PATH=str(workspace_root)))
    monkeypatch.setattr(file_system_router_module, "GitUtils", StubGitUtils)

    assert _resolve_file_service_root("worktree:feature-auth") == resolved_context_path


def test_resolve_file_service_root_uses_workspace_root_for_primary_context(
    monkeypatch, tmp_path: Path
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    monkeypatch.setattr(
        file_system_router_module,
        "get_settings",
        lambda: SimpleNamespace(WORKSPACE_PATH=str(workspace_root)),
    )

    assert _resolve_file_service_root("primary") == workspace_root


def test_resolve_file_service_root_maps_invalid_context_to_http_error(monkeypatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    class StubGitUtils:
        def __init__(self, base_path: Path, worktree_subdir: str = ".worktrees") -> None:
            assert base_path == workspace_root.parent
            assert worktree_subdir == ".worktrees"

        def resolve_context_path(self, workspace_id: str, context_id: str) -> Path:
            raise VersionControlError(
                f"Unknown Git context: {context_id}",
                404,
                "VC_CONTEXT_NOT_FOUND",
            )

    monkeypatch.setattr(file_system_router_module, "get_settings", lambda: SimpleNamespace(WORKSPACE_PATH=str(workspace_root)))
    monkeypatch.setattr(file_system_router_module, "GitUtils", StubGitUtils)

    with pytest.raises(HTTPException) as exc_info:
        _resolve_file_service_root("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "VC_CONTEXT_NOT_FOUND"


@pytest.mark.asyncio
async def test_upload_files_supports_extract_keep_archive(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/app.py", "print('ok')")

    zip_file = SimpleNamespace(filename="demo.zip", read=AsyncMock(return_value=archive_buffer.getvalue()))
    result = await upload_files("/uploads", "rename", "extract", True, [zip_file], service)

    assert len(result.uploaded) == 1
    assert result.uploaded[0].path == "/uploads/demo.zip"
    assert len(result.extracted) == 1
    assert (tmp_path / "uploads" / "demo.zip").exists()


@pytest.mark.asyncio
async def test_extract_archive_runs_in_background_and_reports_status(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    archive_path = service.resolve_scope_path(None, "/uploads/demo.zip")
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/app.py", "print('ok')")

    archive_path.write_bytes(archive_buffer.getvalue())
    background_tasks = BackgroundTasks()

    accepted = await extract_archive(
        ExtractArchiveRequest(archivePath="/uploads/demo.zip"),
        background_tasks,
        service,
    )

    assert accepted.status == "pending"
    for task in background_tasks.tasks:
        task.func(*task.args, **task.kwargs)

    status = await get_extract_archive_status(accepted.operationId)
    assert status.status == "completed"
    assert status.progress == 1.0
    assert status.result is not None
    assert status.result.extractedPaths == ["/uploads/demo/app.py"]
    assert (tmp_path / "uploads" / "demo" / "app.py").read_text(encoding="utf-8") == "print('ok')"


@pytest.mark.asyncio
async def test_extract_archive_status_reports_failure_for_missing_file(tmp_path: Path) -> None:
    service = DummyFileService(tmp_path)
    background_tasks = BackgroundTasks()

    accepted = await extract_archive(
        ExtractArchiveRequest(archivePath="/uploads/missing.zip"),
        background_tasks,
        service,
    )

    for task in background_tasks.tasks:
        task.func(*task.args, **task.kwargs)

    status = await get_extract_archive_status(accepted.operationId)
    assert status.status == "failed"
    assert status.error is not None
    assert "File not found" in status.error
