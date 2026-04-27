"""Core file content related API tests"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from app.modules.file_system.exceptions import ReadonlyScopeException
from app.modules.file_system.router import get_new_file_service
from app.modules.file_system.service import FileService

from .helpers import override_dependency


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
    assert payload["contentHash"].startswith("sha256:")


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
    assert "versionId" in payload["data"]
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
        response = client.delete("/api/v1/files", params={"path": "dir", "recursive": False})

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


def test_fl_015_copy_file_with_overwrite_protection(client, tmp_path):
    """FL-015 Copy file with overwrite protection"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("source content", encoding="utf-8")
    (workspace / "backup").mkdir()

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # First copy: success
        response1 = client.post(
            "/api/v1/files/copy",
            json={"sourcePath": "a.txt", "destPath": "backup/a.txt", "overwrite": False},
        )
        assert response1.status_code == 200
        assert (workspace / "backup" / "a.txt").read_text(encoding="utf-8") == "source content"

        # Second copy: conflict
        response2 = client.post(
            "/api/v1/files/copy",
            json={"sourcePath": "a.txt", "destPath": "backup/a.txt", "overwrite": False},
        )
        assert response2.status_code == 409


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
            json={"sourcePath": "a.txt", "destPath": "tmp/a.txt", "overwrite": False},
        )
        assert response1.status_code == 200
        assert not (workspace / "a.txt").exists()
        assert (workspace / "tmp" / "a.txt").exists()

        # Attempt to move to existing location (conflict)
        (workspace / "b.txt").write_text("another file", encoding="utf-8")
        response2 = client.post(
            "/api/v1/files/move",
            json={"sourcePath": "b.txt", "destPath": "tmp/a.txt", "overwrite": False},
        )
        assert response2.status_code == 409


def test_fl_017_upload_multiple_files_with_rename_strategy(client, tmp_path):
    """FL-017 Multi-file upload with auto rename"""
    from io import BytesIO

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()

    service = FileService(root_path=workspace)

    # Create two upload files with same name
    file1 = BytesIO(b"file content 1")
    file2 = BytesIO(b"file content 2")

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/upload",
            data={"targetPath": "uploads", "conflictStrategy": "rename"},
            files=[
                ("files", ("test.txt", file1, "text/plain")),
                ("files", ("test.txt", file2, "text/plain")),
            ],
        )

    assert response.status_code == 201
    payload = response.json()
    assert len(payload["uploaded"]) == 2
    assert len(payload["skipped"]) == 0
    # Verify filenames
    uploaded_paths = [item["path"] for item in payload["uploaded"]]
    assert "uploads/test.txt" in uploaded_paths
    assert "uploads/test_1.txt" in uploaded_paths


def test_fl_018_upload_zip_without_extract_stores_archive(client, tmp_path):
    """FL-018 ZIP default storage only, no auto extract"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/hello.txt", "hi")

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/upload",
            data={"targetPath": "uploads", "conflictStrategy": "rename"},
            files=[("files", ("demo.zip", BytesIO(archive_buffer.getvalue()), "application/zip"))],
        )

    assert response.status_code == 201
    payload = response.json()
    assert [item["path"] for item in payload["uploaded"]] == ["uploads/demo.zip"]
    assert payload["extracted"] == []
    assert (workspace / "uploads" / "demo.zip").exists()
    assert not (workspace / "uploads" / "demo").exists()


def test_fl_019_upload_zip_with_extract_and_keep_archive(client, tmp_path):
    """FL-019 ZIP extract and keep original archive"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/hello.txt", "hi")

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/upload",
            data={
                "targetPath": "uploads",
                "archiveAction": "extract",
                "keepArchive": "true",
                "conflictStrategy": "rename",
            },
            files=[("files", ("demo.zip", BytesIO(archive_buffer.getvalue()), "application/zip"))],
        )

    assert response.status_code == 201
    payload = response.json()
    assert [item["path"] for item in payload["uploaded"]] == ["uploads/demo.zip"]
    assert [item["path"] for item in payload["extracted"]] == ["uploads/demo/hello.txt"]
    assert (workspace / "uploads" / "demo.zip").exists()
    assert (workspace / "uploads" / "demo" / "hello.txt").read_text(encoding="utf-8") == "hi"


def test_fl_020_upload_zip_rejects_path_traversal(client, tmp_path):
    """FL-020 ZIP path traversal must be rejected"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("../escape.txt", "boom")

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/upload",
            data={"targetPath": "uploads", "archiveAction": "extract", "conflictStrategy": "rename"},
            files=[("files", ("unsafe.zip", BytesIO(archive_buffer.getvalue()), "application/zip"))],
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "INVALID_ARCHIVE_ENTRY"
    assert not (workspace / "uploads").exists()


def test_fl_021_upload_zip_reject_strategy_aborts_on_conflict(client, tmp_path):
    """FL-021 ZIP must fail on conflict under reject strategy"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()
    (workspace / "uploads" / "demo").mkdir()
    (workspace / "uploads" / "demo" / "hello.txt").write_text("old", encoding="utf-8")
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/hello.txt", "new")

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/upload",
            data={"targetPath": "uploads", "archiveAction": "extract", "conflictStrategy": "reject"},
            files=[("files", ("demo.zip", BytesIO(archive_buffer.getvalue()), "application/zip"))],
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "FILE_ALREADY_EXISTS"
    assert (workspace / "uploads" / "demo" / "hello.txt").read_text(encoding="utf-8") == "old"


def test_fl_022_extract_zip_runs_as_background_operation(client, tmp_path):
    """FL-022 Existing ZIP can extract via background task and query status"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    archive_buffer = BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("demo/hello.txt", "hi")

    (workspace / "uploads").mkdir()
    (workspace / "uploads" / "demo.zip").write_bytes(archive_buffer.getvalue())

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/extract",
            json={"archivePath": "/uploads/demo.zip", "conflictStrategy": "rename"},
        )

        assert response.status_code == 202
        payload = response.json()
        status_response = client.get(f"/api/v1/files/extract/{payload['operationId']}")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["result"]["extractedPaths"] == ["/uploads/demo/hello.txt"]
    assert (workspace / "uploads" / "demo.zip").exists()
    assert (workspace / "uploads" / "demo" / "hello.txt").read_text(encoding="utf-8") == "hi"


def test_fl_023_extract_zip_status_reports_failure(client, tmp_path):
    """FL-023 Background extract failure status query should return failed"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.post(
            "/api/v1/files/extract",
            json={"archivePath": "/uploads/missing.zip", "conflictStrategy": "rename"},
        )

        assert response.status_code == 202
        payload = response.json()
        status_response = client.get(f"/api/v1/files/extract/{payload['operationId']}")

    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "failed"
    assert "File not found" in status_payload["error"]
