from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.file_system.router import get_new_file_service, router


def _batch(command: str) -> dict:
    return {
        "items": [
            {
                "sourcePath": "source.txt",
                "finalPath": "/target/source.txt",
                "status": "created",
                "size": 4,
                "type": "file",
                "error": None,
            }
        ],
        "total": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
        "_command": command,
    }


class ContractFileService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def preflight_upload_files(self, **kwargs):
        self.calls.append(("upload-preflight", kwargs))
        return {"conflicts": [], "total": 0}

    def preflight_copy_entries(self, **kwargs):
        self.calls.append(("paste-preflight", kwargs))
        return {
            "conflicts": [
                {
                    "sourcePath": "/source.txt",
                    "targetPath": "/target/source.txt",
                    "sourceType": "file",
                    "targetType": "directory",
                    "canReplace": False,
                }
            ],
            "total": 1,
        }

    def preflight_extract_archive(self, **kwargs):
        self.calls.append(("extract-preflight", kwargs))
        return {"conflicts": [], "total": 0}

    def paste_entries(self, **kwargs):
        self.calls.append(("paste", kwargs))
        result = _batch("paste")
        result.pop("_command")
        return result

    def upload_file_streams(self, **kwargs):
        self.calls.append(("upload", kwargs))
        result = _batch("upload")
        result.pop("_command")
        return result

    def extract_archive_path(self, **kwargs):
        self.calls.append(("extract", kwargs))
        result = _batch("extract")
        result.pop("_command")
        return result


def _client(service: ContractFileService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_new_file_service] = lambda: service
    return TestClient(app)


def test_conflict_preflight_supports_upload_paste_and_extract() -> None:
    service = ContractFileService()
    client = _client(service)

    upload = client.post(
        "/files/conflicts/preflight",
        json={
            "operation": "upload",
            "targetPath": "/target",
            "sources": [{"sourcePath": "source.txt", "entryType": "file"}],
        },
    )
    paste = client.post(
        "/files/conflicts/preflight",
        json={
            "operation": "paste",
            "targetPath": "/target",
            "sources": [{"sourcePath": "/source.txt", "entryType": "file"}],
        },
    )
    extract = client.post(
        "/files/conflicts/preflight",
        json={
            "operation": "extract",
            "targetPath": "/target",
            "archivePath": "/archive.zip",
        },
    )

    assert upload.json() == {"conflicts": [], "total": 0}
    assert paste.json()["conflicts"][0]["canReplace"] is False
    assert extract.json() == {"conflicts": [], "total": 0}
    assert [call[0] for call in service.calls] == [
        "upload-preflight",
        "paste-preflight",
        "extract-preflight",
    ]


def test_execution_routes_require_strategy_and_resolutions_and_return_batch() -> None:
    service = ContractFileService()
    client = _client(service)
    resolution_json = '[{"sourcePath":"source.txt","strategy":"replace"}]'

    upload = client.post(
        "/files/upload",
        data={
            "targetPath": "/target",
            "defaultStrategy": "cancel",
            "resolutions": resolution_json,
        },
        files={"files": ("source.txt", b"data", "text/plain")},
    )
    paste = client.post(
        "/files/paste",
        json={
            "targetPath": "/target",
            "sources": [{"sourcePath": "/source.txt", "entryType": "file"}],
            "defaultStrategy": "replace",
            "resolutions": [],
        },
    )
    extract = client.post(
        "/files/extract",
        json={
            "archivePath": "/archive.zip",
            "targetPath": "/target",
            "defaultStrategy": "keep-both",
            "resolutions": [],
        },
    )

    expected_fields = {"items", "total", "succeeded", "skipped", "failed"}
    assert upload.status_code == 200
    assert paste.status_code == 200
    assert extract.status_code == 200
    assert set(upload.json()) == expected_fields
    assert set(upload.json()["items"][0]) == {
        "sourcePath",
        "finalPath",
        "status",
        "size",
        "type",
        "error",
    }
    assert client.post(
        "/files/paste",
        json={
            "targetPath": "/target",
            "sources": [{"sourcePath": "/source.txt", "entryType": "file"}],
        },
    ).status_code == 422
    assert client.post(
        "/files/upload",
        data={"targetPath": "/target", "conflictStrategy": "rename"},
        files={"files": ("source.txt", b"data", "text/plain")},
    ).status_code == 422


def test_extract_preflight_requires_archive_path() -> None:
    response = _client(ContractFileService()).post(
        "/files/conflicts/preflight",
        json={"operation": "extract", "targetPath": "/target"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_ARCHIVE"
