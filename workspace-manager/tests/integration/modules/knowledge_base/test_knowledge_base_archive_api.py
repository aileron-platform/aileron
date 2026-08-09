from __future__ import annotations

import time
import zipfile
from io import BytesIO

import pytest

from app.db import models as db_models
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


def _create_kb_with_file(client) -> str:
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Archive Files", "slug": "archive-files"},
    )
    kb_id = create_kb_response.json()["id"]
    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/docs/a.txt", "type": "file", "content": "old"},
    )
    assert create_kb_response.status_code == 201
    assert create_file_response.status_code == 200
    return kb_id


def _wait_operation(
    client, kb_id: str, operation_id: str, timeout: float = 10.0
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(
            f"/api/v1/knowledge-bases/{kb_id}/files/archive/{operation_id}"
        )
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"completed", "failed"}:
            return body
        time.sleep(0.1)
    raise AssertionError("archive operation did not finish in time")


def _zip_bytes(filename: str, content: bytes) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filename, content)
    return buffer.getvalue()


@pytest.mark.integration
def test_archive_download_flow(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-archive-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = _create_kb_with_file(client)

    accepted = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/archive",
        json={"paths": ["docs"], "archiveName": "docs.zip", "archiveFormat": "zip"},
    )
    assert accepted.status_code == 202
    operation_id = accepted.json()["operationId"]

    status_body = _wait_operation(client, kb_id, operation_id)
    assert status_body["status"] == "completed"
    assert status_body["result"]["archiveName"] == "docs.zip"

    download = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/archive/{operation_id}/download"
    )
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"


@pytest.mark.integration
def test_archive_status_not_found(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-archive-missing-owner",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = _create_kb_with_file(client)

    response = client.get(f"/api/v1/knowledge-bases/{kb_id}/files/archive/nope")

    assert response.status_code == 404


@pytest.mark.integration
def test_extract_archive_flow(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-extract-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = _create_kb_with_file(client)
    upload = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload",
        data={
            "targetPath": "docs",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[
            (
                "files",
                ("sample.zip", _zip_bytes("inner.txt", b"inside"), "application/zip"),
            )
        ],
    )
    assert upload.status_code == 200

    extracted = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/extract",
        json={
            "archivePath": "docs/sample.zip",
            "targetPath": "docs",
            "defaultStrategy": "keep-both",
            "resolutions": [],
        },
    )
    assert extracted.status_code == 200
    assert extracted.json()["items"] == [
        {
            "sourcePath": "inner.txt",
            "finalPath": "docs/inner.txt",
            "status": "created",
            "size": len(b"inside"),
            "type": "file",
            "error": None,
        }
    ]


@pytest.mark.integration
def test_extract_rejects_non_zip(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-extract-non-zip-owner",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = _create_kb_with_file(client)

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/extract",
        json={
            "archivePath": "docs/a.txt",
            "targetPath": "docs",
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    assert response.status_code == 400
