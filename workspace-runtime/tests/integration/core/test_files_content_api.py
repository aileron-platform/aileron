"""核心檔案內容相關 API 測試"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from app.modules.file_system.exceptions import ReadonlyScopeException
from app.modules.file_system.router import get_new_file_service
from app.modules.file_system.service import FileService

from .helpers import override_dependency


class ReadonlyFileServiceStub:
    """只會拋出唯讀錯誤的檔案服務"""

    def write_file(self, *args, **kwargs):  # pragma: no cover - 簡單 stub
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
    """FL-009 多檔案一次寫入"""
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
    """FL-010 建立新檔與資料夾"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # 建立檔案
        response1 = client.post(
            "/api/v1/files",
            json={"path": "newfile.txt", "type": "file", "content": "hello"},
        )
        assert response1.status_code == 201
        assert (workspace / "newfile.txt").exists()

        # 建立資料夾
        response2 = client.post(
            "/api/v1/files",
            json={"path": "newfolder", "type": "directory"},
        )
        assert response2.status_code == 201
        assert (workspace / "newfolder").is_dir()


def test_fl_011_create_duplicate_file_conflict(client, tmp_path):
    """FL-011 重複建立觸發衝突"""
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
    """FL-012 刪除檔案成功"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "temp.txt").write_text("to be deleted", encoding="utf-8")
    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        response = client.delete("/api/v1/files", params={"path": "temp.txt"})

    assert response.status_code == 200
    assert not (workspace / "temp.txt").exists()


def test_fl_013_delete_non_empty_directory_without_recursive(client, tmp_path):
    """FL-013 未遞迴刪除非空資料夾"""
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
    """FL-014 批次刪除混合狀態"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.txt").write_text("content 1", encoding="utf-8")
    (workspace / "file2.txt").write_text("content 2", encoding="utf-8")
    # file3.txt 不存在

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
    # 檢查結果中包含成功和失敗的檔案
    results = payload["results"]
    success_results = [r for r in results if r["status"] == "success"]
    failed_results = [r for r in results if r["status"] == "failed"]
    assert len(success_results) == 2
    assert len(failed_results) == 1


def test_fl_015_copy_file_with_overwrite_protection(client, tmp_path):
    """FL-015 複製檔案與覆寫保護"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("source content", encoding="utf-8")
    (workspace / "backup").mkdir()

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # 第一次複製：成功
        response1 = client.post(
            "/api/v1/files/copy",
            json={"sourcePath": "a.txt", "destPath": "backup/a.txt", "overwrite": False},
        )
        assert response1.status_code == 200
        assert (workspace / "backup" / "a.txt").read_text(encoding="utf-8") == "source content"

        # 第二次複製：衝突
        response2 = client.post(
            "/api/v1/files/copy",
            json={"sourcePath": "a.txt", "destPath": "backup/a.txt", "overwrite": False},
        )
        assert response2.status_code == 409


def test_fl_016_move_file_success_and_conflict(client, tmp_path):
    """FL-016 移動檔案"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "a.txt").write_text("content to move", encoding="utf-8")
    (workspace / "tmp").mkdir()

    service = FileService(root_path=workspace)

    with override_dependency(get_new_file_service, lambda: service):
        # 移動成功
        response1 = client.post(
            "/api/v1/files/move",
            json={"sourcePath": "a.txt", "destPath": "tmp/a.txt", "overwrite": False},
        )
        assert response1.status_code == 200
        assert not (workspace / "a.txt").exists()
        assert (workspace / "tmp" / "a.txt").exists()

        # 嘗試移動到已存在的位置（衝突）
        (workspace / "b.txt").write_text("another file", encoding="utf-8")
        response2 = client.post(
            "/api/v1/files/move",
            json={"sourcePath": "b.txt", "destPath": "tmp/a.txt", "overwrite": False},
        )
        assert response2.status_code == 409


def test_fl_017_upload_multiple_files_with_rename_strategy(client, tmp_path):
    """FL-017 多檔案上傳與自動改名"""
    from io import BytesIO

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "uploads").mkdir()

    service = FileService(root_path=workspace)

    # 建立兩個同名的上傳檔案
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
    # 驗證檔名
    uploaded_paths = [item["path"] for item in payload["uploaded"]]
    assert "uploads/test.txt" in uploaded_paths
    assert "uploads/test_1.txt" in uploaded_paths


def test_fl_018_upload_zip_without_extract_stores_archive(client, tmp_path):
    """FL-018 ZIP 預設僅保存，不自動解壓"""
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
    """FL-019 ZIP 解壓並保留原始壓縮檔"""
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
    """FL-020 ZIP 路徑穿越必須被拒絕"""
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
    """FL-021 ZIP 在 reject 策略下遇到衝突必須失敗"""
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
    """FL-022 既有 ZIP 可透過背景任務解壓並查詢狀態"""
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
    """FL-023 背景解壓失敗時狀態查詢應回傳 failed"""
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
