"""Core file content related API tests"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import zipfile

from app.modules.file_system.exceptions import ReadonlyScopeException
from app.modules.file_system.router import get_new_file_service
from app.modules.file_system.operations import FileService

from .dependency_overrides import override_dependency

file_router = importlib.import_module("app.modules.file_system.router")
base_service_module = importlib.import_module("app.modules.file_system.base_operations")


class ReadonlyFileServiceStub:
    """File service that only raises readonly errors"""

    def write_file(self, *args, **kwargs):  # pragma: no cover - simple stub
        raise ReadonlyScopeException("project")


def _prepare_workspace(base: Path) -> Path:
    workspace = base / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "guide.md").write_text("Initial content\n", encoding="utf-8")
    (workspace / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return workspace


def test_fl_004_read_text_file(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/content",
            params={"path": "docs/guide.md"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "Initial content\n"
    assert len(payload["revision"]) == 64


def test_file_content_uses_revision_field(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        client.put(
            "/api/v1/files/content",
            json={"path": "a.txt", "content": "hi"},
        )
        body = client.get(
            "/api/v1/files/content",
            params={"path": "a.txt"},
        ).json()

    assert "revision" in body
    assert "versionId" not in body and "contentHash" not in body


def test_file_write_revision_conflict(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        client.put(
            "/api/v1/files/content",
            json={"path": "a.txt", "content": "hi"},
        )
        response = client.put(
            "/api/v1/files/content",
            json={"path": "a.txt", "content": "x", "revision": "stale"},
        )

    assert response.status_code == 409


def test_fl_005_download_binary_raw_mode(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/content",
            params={"path": "sample.png", "raw": "true"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    assert response.headers["Content-Disposition"] == 'inline; filename="sample.png"'
    assert response.content == b"\x89PNG\r\n\x1a\n"


def test_read_binary_raw_mode_supports_non_ascii_filename(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    filename = "ChatGPT Image 2026年7月27日 上午11_26_27.png"
    image_content = b"\x89PNG\r\n\x1a\n"
    (workspace / filename).write_bytes(image_content)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/content",
            params={"path": filename, "raw": "true"},
        )

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "image/png"
    assert response.headers["Content-Disposition"].startswith(
        "inline; filename*=utf-8''"
    )
    assert response.content == image_content


def test_fl_006_read_missing_file_returns_404(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get(
            "/api/v1/files/content",
            params={"path": "missing.txt"},
        )

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "FILE_NOT_FOUND"


def test_fl_007_write_file_updates_content(client, tmp_path):
    workspace = _prepare_workspace(tmp_path)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.put(
            "/api/v1/files/content",
            json={"path": "docs/guide.md", "content": "Updated!"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert "data" in payload
    assert "revision" in payload["data"]
    assert (workspace / "docs" / "guide.md").read_text(encoding="utf-8") == "Updated!"


def test_fl_008_write_file_readonly_scope(client):
    service = ReadonlyFileServiceStub()

    with override_dependency(get_new_file_service, lambda: service):
        response = client.put(
            "/api/v1/files/content",
            json={"path": "docs/guide.md", "content": "fail"},
        )

    assert response.status_code == 403
    detail = response.json()["detail"]
    assert detail["code"] == "READONLY_SCOPE"


def test_fl_009_batch_write_multiple_files(client, tmp_path):
    """FL-009 Multi-file single write"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.txt").write_text("original 1", encoding="utf-8")
    (workspace / "file2.txt").write_text("original 2", encoding="utf-8")
    (workspace / "file3.txt").write_text("original 3", encoding="utf-8")

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/content/batch",
            json={
                "files": [
                    {"path": "file1.txt", "content": "updated 1"},
                    {"path": "file2.txt", "content": "updated 2"},
                    {"path": "file3.txt", "content": "updated 3"},
                ]
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["succeeded"] == 3
    assert payload["total"] == 3
    assert payload["failed"] == 0
    assert (workspace / "file1.txt").read_text(encoding="utf-8") == "updated 1"
    assert (workspace / "file2.txt").read_text(encoding="utf-8") == "updated 2"
    assert (workspace / "file3.txt").read_text(encoding="utf-8") == "updated 3"


def test_fl_010_create_file_and_directory(client, tmp_path):
    """FL-010 Create new file and folder"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # Create file
        response1 = client.post(
            "/api/v1/files",
            json={"path": "newfile.txt", "type": "file", "content": "hello"},
        )
        assert response1.status_code == 201
        assert (workspace / "newfile.txt").exists()

        # Create directory
        response2 = client.post(
            "/api/v1/files",
            json={"path": "newfolder", "type": "directory"},
        )
        assert response2.status_code == 201
        assert (workspace / "newfolder").is_dir()


def test_fl_011_create_duplicate_file_conflict(client, tmp_path):
    """FL-011 Duplicate creation triggers conflict"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "existing.txt").write_text("already here", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files",
            json={"path": "existing.txt", "type": "file"},
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "FILE_ALREADY_EXISTS"


def test_fl_012_delete_file_success(client, tmp_path):
    """FL-012 Delete file success"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "temp.txt").write_text("to be deleted", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.delete("/api/v1/files", params={"path": "temp.txt"})

    assert response.status_code == 200
    assert not (workspace / "temp.txt").exists()


def test_fl_013_delete_non_empty_directory_without_recursive(client, tmp_path):
    """FL-013 Delete non-empty folder without recursive"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "dir").mkdir()
    (workspace / "dir" / "file.txt").write_text("content", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.delete(
            "/api/v1/files", params={"path": "dir", "recursive": False}
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "DIRECTORY_NOT_EMPTY"


def test_fl_014_batch_delete_mixed_results(client, tmp_path):
    """FL-014 Batch delete mixed status"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.txt").write_text("content 1", encoding="utf-8")
    (workspace / "file2.txt").write_text("content 2", encoding="utf-8")
    # file3.txt does not exist

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/batch-delete",
            json={"paths": ["file1.txt", "file2.txt", "file3.txt"]},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["succeeded"] == 2
    assert payload["total"] == 3
    assert payload["failed"] == 1
    # Check results contain successful and failed files
    results = payload["results"]
    success_results = [r for r in results if r["status"] == "success"]
    failed_results = [r for r in results if r["status"] == "failed"]
    assert len(success_results) == 2
    assert len(failed_results) == 1


def test_fl_016_move_file_success_and_conflict(client, tmp_path):
    """FL-016 Move file"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("content to move", encoding="utf-8")
    (workspace / "tmp").mkdir()

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # Move success
        response1 = client.post(
            "/api/v1/files/move",
            json={"sourcePath": "a.txt", "destPath": "tmp/a.txt"},
        )
        assert response1.status_code == 200
        assert not (workspace / "a.txt").exists()
        assert (workspace / "tmp" / "a.txt").exists()

        # Attempt to move to existing location (conflict)
        (workspace / "b.txt").write_text("another file", encoding="utf-8")
        response2 = client.post(
            "/api/v1/files/move",
            json={"sourcePath": "b.txt", "destPath": "tmp/a.txt"},
        )
        assert response2.status_code == 409
        assert response2.json()["detail"]["code"] == "FILE_ALREADY_EXISTS"


def test_fl_017_upload_preflight_and_keep_both_batch(client, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()
    (workspace / "uploads" / "test.txt").write_text("existing", encoding="utf-8")

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        preflight = client.post(
            "/api/v1/files/conflicts/preflight",
            json={
                "operation": "upload",
                "targetPath": "uploads",
                "sources": [{"sourcePath": "test.txt", "entryType": "file"}],
            },
        )
        response = client.post(
            "/api/v1/files/upload",
            data={
                "targetPath": "uploads",
                "defaultStrategy": "keep-both",
                "resolutions": "[]",
            },
            files={"files": ("test.txt", b"new", "text/plain")},
        )

    assert preflight.status_code == 200
    assert preflight.json()["conflicts"][0] == {
        "sourcePath": "test.txt",
        "targetPath": "uploads/test.txt",
        "sourceType": "file",
        "targetType": "file",
        "canReplace": True,
    }
    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"items", "total", "succeeded", "skipped", "failed"}
    assert payload["items"][0]["status"] == "kept-both"
    assert payload["items"][0]["finalPath"] == "uploads/test_1.txt"
    assert (workspace / "uploads" / "test.txt").read_text(encoding="utf-8") == "existing"
    assert (workspace / "uploads" / "test_1.txt").read_text(encoding="utf-8") == "new"


def test_fl_018_paste_directory_replace_merges_and_type_conflict_is_forbidden(
    client, tmp_path
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "source" / "docs").mkdir(parents=True)
    (workspace / "source" / "docs" / "new.md").write_text("new", encoding="utf-8")
    (workspace / "target" / "docs").mkdir(parents=True)
    (workspace / "target" / "docs" / "old.md").write_text("old", encoding="utf-8")
    (workspace / "source.txt").write_text("file", encoding="utf-8")
    (workspace / "target" / "source.txt").mkdir()
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        merged = client.post(
            "/api/v1/files/paste",
            json={
                "targetPath": "target",
                "sources": [{"sourcePath": "source/docs", "entryType": "directory"}],
                "defaultStrategy": "replace",
                "resolutions": [],
            },
        )
        conflict = client.post(
            "/api/v1/files/paste",
            json={
                "targetPath": "target",
                "sources": [{"sourcePath": "source.txt", "entryType": "file"}],
                "defaultStrategy": "replace",
                "resolutions": [],
            },
        )

    assert merged.status_code == 200
    assert merged.json()["items"][0]["status"] == "merged"
    assert (workspace / "target" / "docs" / "old.md").exists()
    assert (workspace / "target" / "docs" / "new.md").exists()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "FILE_TYPE_CONFLICT"


def test_fl_019_extract_preflight_and_execution_use_batch_contract(client, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/hello.txt", "hi")

    with override_dependency(get_new_file_service, lambda: service):
        (workspace / "uploads").mkdir()
        (workspace / "uploads" / "demo.zip").write_bytes(archive_buffer.getvalue())
        preflight = client.post(
            "/api/v1/files/conflicts/preflight",
            json={
                "operation": "extract",
                "archivePath": "uploads/demo.zip",
                "targetPath": "uploads",
            },
        )
        response = client.post(
            "/api/v1/files/extract",
            json={
                "archivePath": "uploads/demo.zip",
                "targetPath": "uploads",
                "defaultStrategy": "cancel",
                "resolutions": [],
            },
        )

    assert preflight.status_code == 200
    assert preflight.json() == {"conflicts": [], "total": 1}
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["sourcePath"] == "demo/hello.txt"
    assert payload["items"][0]["finalPath"] == "uploads/demo/hello.txt"
    assert (workspace / "uploads" / "demo" / "hello.txt").read_text(
        encoding="utf-8"
    ) == "hi"


def test_fl_020_extract_rejects_path_traversal(client, tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("../escape.txt", "boom")

    with override_dependency(get_new_file_service, lambda: service):
        (workspace / "unsafe.zip").write_bytes(archive_buffer.getvalue())
        response = client.post(
            "/api/v1/files/extract",
            json={
                "archivePath": "unsafe.zip",
                "targetPath": "uploads",
                "defaultStrategy": "cancel",
                "resolutions": [],
            },
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_ARCHIVE_ENTRY"
    assert not (workspace / "uploads").exists()


def test_fl_024_download_single_file(client, tmp_path):
    """FL-024 Single file download returns an attachment"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "report.txt").write_text("hello", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.get("/api/v1/files/download", params={"path": "/report.txt"})

    assert response.status_code == 200
    assert response.content == b"hello"
    assert "attachment" in response.headers["content-disposition"]
    assert "report.txt" in response.headers["content-disposition"]


def test_fl_025_archive_download_runs_as_background_operation(client, tmp_path):
    """FL-025 Directory archive download can be created, polled, and downloaded"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "docs").mkdir()
    (workspace / "docs" / "guide.md").write_text("guide", encoding="utf-8")
    (workspace / "docs" / "notes.md").write_text("notes", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/archive",
            json={"paths": ["/docs"], "archiveName": "docs.zip"},
        )
        assert response.status_code == 202
        operation_id = response.json()["operationId"]

        status_response = client.get(f"/api/v1/files/archive/{operation_id}")
        download_response = client.get(f"/api/v1/files/archive/{operation_id}/download")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["result"]["archiveName"] == "docs.zip"
    assert status_payload["result"]["downloadUrl"].endswith(
        f"/archive/{operation_id}/download"
    )
    assert download_response.status_code == 200

    archive_buffer = BytesIO(download_response.content)
    with zipfile.ZipFile(archive_buffer, "r") as archive:
        assert sorted(archive.namelist()) == ["docs/guide.md", "docs/notes.md"]
        assert archive.read("docs/guide.md") == b"guide"


def test_fl_026_archive_download_removes_redundant_child_selection(client, tmp_path):
    """FL-026 Archive download does not duplicate child paths selected under a parent"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "src" / "app.ts").write_text("app", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/archive",
            json={"paths": ["/src", "/src/app.ts"], "archiveName": "src.zip"},
        )
        operation_id = response.json()["operationId"]
        download_response = client.get(f"/api/v1/files/archive/{operation_id}/download")

    assert response.status_code == 202
    assert download_response.status_code == 200
    with zipfile.ZipFile(BytesIO(download_response.content), "r") as archive:
        assert archive.namelist() == ["src/app.ts"]


def test_fl_027_archive_download_rejects_missing_path(client, tmp_path):
    """FL-027 Archive download status reports missing path failure"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/archive",
            json={"paths": ["/missing"], "archiveName": "missing.zip"},
        )
        assert response.status_code == 202
        operation_id = response.json()["operationId"]
        status_response = client.get(f"/api/v1/files/archive/{operation_id}")

    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert "File not found" in payload["error"]


def test_fl_028_archive_download_expired_operation_is_not_found(client, tmp_path):
    """FL-028 Expired archive operations are cleaned up"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file.txt").write_text("hello", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/archive",
            json={"paths": ["/file.txt"], "archiveName": "file.zip"},
        )
        operation_id = response.json()["operationId"]

        file_router._archive_operation_store.update(
            scope_key=file_router.WORKSPACE_OPERATION_SCOPE,
            operation_id=operation_id,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
        status_response = client.get(f"/api/v1/files/archive/{operation_id}")

    assert response.status_code == 202
    assert status_response.status_code == 404


def test_fl_029_archive_download_reports_limit_failure(client, tmp_path, monkeypatch):
    """FL-029 Archive download fails when configured entry limit is exceeded"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "one.txt").write_text("one", encoding="utf-8")
    (workspace / "two.txt").write_text("two", encoding="utf-8")
    test_settings = SimpleNamespace(
        ARCHIVE_MAX_ENTRY_COUNT=1000,
        ARCHIVE_MAX_ENTRY_SIZE_BYTES=20 * 1024 * 1024,
        ARCHIVE_MAX_TOTAL_SIZE_BYTES=100 * 1024 * 1024,
        ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS=10,
        ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT=1,
        ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES=1024,
        ARCHIVE_DOWNLOAD_TTL_SECONDS=1800,
    )

    monkeypatch.setattr(file_router, "get_settings", lambda: test_settings)
    monkeypatch.setattr(base_service_module, "get_settings", lambda: test_settings)
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/archive",
            json={"paths": ["/one.txt", "/two.txt"], "archiveName": "files.zip"},
        )
        operation_id = response.json()["operationId"]
        status_response = client.get(f"/api/v1/files/archive/{operation_id}")

    assert response.status_code == 202
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert "entry count exceeds limit" in payload["error"]
