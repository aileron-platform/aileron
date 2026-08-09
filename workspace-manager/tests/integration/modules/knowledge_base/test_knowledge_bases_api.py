from __future__ import annotations

import hashlib
import os
import time
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.knowledge_base.access import KnowledgeBaseConflictError
from tests.helpers.manager_session import authenticate_client_as


def _authenticate_as(client, _monkeypatch, user: db_models.User) -> None:
    authenticate_client_as(client, user)


def _create_workspace(
    session_factory,
    *,
    owner_id: str,
    name: str = "KB Workspace",
) -> str:
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=f"workspace-{uuid4().hex[:8]}",
            owner_id=owner_id,
            name=name,
            runtime="universal",
            provisioner="docker",
            runtime_status="stopped",
            runtime_container_id=None,
            env_vars=[],
            workspace_firewall_allowed_domains=[],
            browser_firewall_allowed_domains=[],
            acp_cli_args=[],
        )
        session.add(workspace)
        session.commit()
        return workspace.id


@pytest.mark.integration
def test_knowledge_base_create_list_and_update(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "API Docs", "slug": "api-docs", "description": "shared docs"},
    )
    list_response = client.get("/api/v1/knowledge-bases")
    kb_id = create_response.json()["id"]
    update_response = client.patch(
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"description": "updated docs"},
    )

    assert create_response.status_code == 201
    assert create_response.json()["slug"] == "api-docs"
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert list_response.json()["items"][0]["accessRole"] == "owner"
    assert update_response.status_code == 200
    assert update_response.json()["description"] == "updated docs"


@pytest.mark.integration
def test_knowledge_base_share_flow(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    member = create_user(
        username="kb-member", platform_role="member", role_status="valid"
    )

    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Team Docs", "slug": "team-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    create_share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": member.id, "role": "reader"},
    )
    list_share_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/shares")
    assert create_share_response.status_code == 201
    assert create_share_response.json()["role"] == "reader"
    assert list_share_response.status_code == 200
    assert len(list_share_response.json()["items"]) == 1


@pytest.mark.integration
def test_knowledge_base_file_endpoints_support_create_read_delete(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files"},
    )
    kb_id = create_kb_response.json()["id"]

    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/raw/readme.md", "type": "file", "content": "hello kb"},
    )
    read_file_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/readme.md"},
    )
    delete_file_response = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        params={"path": "/raw/readme.md"},
    )

    assert create_file_response.status_code == 200
    assert read_file_response.status_code == 200
    assert read_file_response.json()["content"] == "hello kb"
    assert delete_file_response.status_code == 200


@pytest.mark.integration
def test_reader_cannot_mutate_canonical_knowledge_base_files(
    test_app,
    create_user,
    monkeypatch,
):
    client, _ = test_app
    owner = create_user(
        username="kb-file-owner",
        platform_role="member",
        role_status="valid",
    )
    reader = create_user(
        username="kb-file-reader",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    create_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Protected Files", "slug": "protected-files"},
    )
    kb_id = create_response.json()["id"]
    share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )
    assert share_response.status_code == 201

    _authenticate_as(client, monkeypatch, reader)
    responses = [
        client.put(
            f"/api/v1/knowledge-bases/{kb_id}/files/content",
            json={
                "path": "/blocked.md",
                "type": "file",
                "content": "blocked",
                "revision": "missing",
            },
        ),
        client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files",
            data={"path": "/blocked", "type": "directory"},
        ),
        client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files/upload",
            data={
                "targetPath": "/",
                "defaultStrategy": "keep-both",
                "resolutions": "[]",
            },
            files={"files": ("blocked.md", b"blocked", "text/markdown")},
        ),
        client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files/move",
            json={
                "sourcePath": "/blocked.md",
                "destinationPath": "/moved.md",
            },
        ),
        client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files/paste",
            json={
                "targetPath": "/",
                "sources": [{"sourcePath": "/blocked.md", "entryType": "file"}],
                "defaultStrategy": "keep-both",
                "resolutions": [],
            },
        ),
        client.delete(
            f"/api/v1/knowledge-bases/{kb_id}/files",
            params={"path": "/blocked.md"},
        ),
        client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files/history/missing/restore",
            json={},
        ),
    ]

    assert [response.status_code for response in responses] == [403] * len(responses)
    assert {response.json()["detail"]["errorCode"] for response in responses} == {
        "KB_PERMISSION_DENIED"
    }


@pytest.mark.integration
def test_knowledge_base_file_content_uses_revision_contract(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-revision-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Revision Files", "slug": "revision-files"},
    )
    kb_id = create_kb_response.json()["id"]

    create_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/revision.md",
            "type": "file",
            "content": "first",
            "revision": "",
        },
    )
    read_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/revision.md"},
    )
    missing_revision_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/revision.md",
            "type": "file",
            "content": "missing revision write",
        },
    )
    legacy_revision_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/revision.md",
            "type": "file",
            "content": "legacy revision write",
            "expectedVersionId": read_response.json()["revision"],
        },
    )
    stale_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/revision.md",
            "type": "file",
            "content": "stale write",
            "revision": "stale",
        },
    )
    update_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/revision.md",
            "type": "file",
            "content": "second",
            "revision": read_response.json()["revision"],
        },
    )

    assert create_response.status_code == 200
    assert read_response.status_code == 200
    read_body = read_response.json()
    assert read_body["revision"] == hashlib.sha256(b"first").hexdigest()
    assert len(read_body["revision"]) == 64
    assert "versionId" not in read_body
    assert "contentHash" not in read_body
    assert missing_revision_response.status_code == 422
    assert legacy_revision_response.status_code == 422
    assert stale_response.status_code == 409
    stale_body = stale_response.json()["detail"]
    assert stale_body["details"]["expectedRevision"] == "stale"
    assert stale_body["details"]["actualRevision"] == read_body["revision"]
    assert "expectedVersion" not in stale_body["details"]
    assert "actualVersion" not in stale_body["details"]
    assert update_response.status_code == 200
    update_body = update_response.json()
    assert update_body["revision"] == hashlib.sha256(b"second").hexdigest()
    assert "versionId" not in update_body
    assert "contentHash" not in update_body

    history_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/history",
        params={"path": "/raw/revision.md"},
    )
    assert history_response.status_code == 200
    history_item = history_response.json()["items"][0]
    assert history_item["revisionBefore"] == hashlib.sha256(b"first").hexdigest()
    assert history_item["revisionAfter"] is None
    assert "versionIdBefore" not in history_item
    assert "versionIdAfter" not in history_item
    assert "contentHashBefore" not in history_item
    assert "contentHashAfter" not in history_item

    restore_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/history/{history_item['id']}/restore",
        json={"revision": update_body["revision"]},
    )
    assert restore_response.status_code == 200
    restore_body = restore_response.json()
    assert restore_body["revision"] == hashlib.sha256(b"first").hexdigest()
    assert "versionId" not in restore_body


@pytest.mark.integration
def test_knowledge_base_file_upload_preflight_and_keep_both(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-upload-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Upload Files", "slug": "upload-files"},
    )
    kb_id = create_kb_response.json()["id"]
    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/docs/a.txt", "type": "file", "content": "old"},
    )

    preflight = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/conflicts/preflight",
        json={
            "operation": "upload",
            "targetPath": "docs",
            "sources": [{"sourcePath": "a.txt", "entryType": "file"}],
            "archivePath": None,
        },
    )
    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload",
        data={
            "targetPath": "docs",
            "defaultStrategy": "keep-both",
            "resolutions": "[]",
        },
        files=[("files", ("a.txt", b"new", "text/plain"))],
    )

    assert create_file_response.status_code == 200
    assert preflight.status_code == 200
    assert preflight.json() == {
        "conflicts": [
            {
                "sourcePath": "a.txt",
                "targetPath": "docs/a.txt",
                "sourceType": "file",
                "targetType": "file",
                "canReplace": True,
            }
        ],
        "total": 1,
    }
    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "sourcePath": "a.txt",
                "finalPath": "docs/a_1.txt",
                "status": "kept-both",
                "size": len(b"new"),
                "type": "file",
                "error": None,
            }
        ],
        "total": 1,
        "succeeded": 1,
        "skipped": 0,
        "failed": 0,
    }


@pytest.mark.integration
def test_knowledge_base_file_upload_cancel_prevents_entire_batch(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-upload-reject-owner",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Reject Upload Files", "slug": "reject-upload-files"},
    )
    kb_id = create_kb_response.json()["id"]
    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/docs/a.txt", "type": "file", "content": "old"},
    )

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/upload",
        data={
            "targetPath": "docs",
            "defaultStrategy": "cancel",
            "resolutions": "[]",
        },
        files=[
            ("files", ("a.txt", b"new", "text/plain")),
            ("files", ("b.txt", b"new", "text/plain")),
        ],
    )

    assert create_file_response.status_code == 200
    assert response.status_code == 200
    assert response.json()["succeeded"] == 0
    assert [item["status"] for item in response.json()["items"]] == [
        "cancelled",
        "cancelled",
    ]
    assert (
        client.get(
            f"/api/v1/knowledge-bases/{kb_id}/files/content",
            params={"path": "/docs/b.txt"},
        ).status_code
        == 404
    )


@pytest.mark.integration
def test_knowledge_base_file_download(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(
        username="kb-download-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Download Files", "slug": "download-files"},
    )
    kb_id = create_kb_response.json()["id"]
    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/docs/a.txt", "type": "file", "content": "old"},
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/download",
        params={"path": "docs/a.txt"},
    )

    assert create_file_response.status_code == 200
    assert response.status_code == 200
    assert response.content == b"old"
    assert "attachment" in response.headers.get("content-disposition", "")


@pytest.mark.integration
def test_knowledge_base_file_download_rejects_directory(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-download-dir-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Download Directory", "slug": "download-directory"},
    )
    kb_id = create_kb_response.json()["id"]
    create_dir_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/docs", "type": "directory"},
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/download",
        params={"path": "docs"},
    )

    assert create_dir_response.status_code == 200
    assert response.status_code == 400


@pytest.mark.integration
def test_knowledge_base_file_content_raw_supports_viewer_and_rejects_bad_paths(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-raw-owner", platform_role="member", role_status="valid"
    )
    reader = create_user(
        username="kb-raw-reader", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Raw Files", "slug": "raw-files"},
    )
    kb_id = create_kb_response.json()["id"]
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/pixel.png",
            "type": "file",
            "content": "png-bytes",
            "revision": "",
        },
    )
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )

    _authenticate_as(client, monkeypatch, reader)
    raw_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/pixel.png", "raw": "true"},
    )
    traversal_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/../raw/pixel.png", "raw": "true"},
    )
    missing_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/missing.png", "raw": "true"},
    )

    assert write_response.status_code == 200
    assert raw_response.status_code == 200
    assert raw_response.headers["content-type"].startswith("image/png")
    assert raw_response.content == b"png-bytes"
    assert traversal_response.status_code == 400
    assert traversal_response.json()["detail"]["errorCode"] == "INVALID_PATH"
    assert missing_response.status_code == 404


@pytest.mark.integration
def test_knowledge_base_source_api_uploads_sources_and_imports_web_clip(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-source-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Sources", "slug": "sources"},
    )
    kb_id = create_kb_response.json()["id"]

    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        files={"file": ("research.md", b"# Research\n\nBody\n", "text/markdown")},
    )
    clip_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources/web-clip",
        json={
            "title": "Example Page",
            "markdown": "# Example\n\nBody\n",
            "assets": {"diagram.txt": "asset text"},
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()
    assert upload_payload["source"]["path"] == "/raw/sources/research.md"
    assert upload_payload["source"]["sourceHash"]
    assert "normalization" not in upload_payload
    assert clip_response.status_code == 200
    assert clip_response.json()["path"] == "/raw/sources/example-page.md"
    assert clip_response.json()["assetPaths"] == [
        "/raw/assets/example-page/diagram.txt"
    ]


@pytest.mark.integration
def test_knowledge_base_source_api_rejects_viewer_upload(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-source-owner-2", platform_role="member", role_status="valid"
    )
    reader = create_user(
        username="kb-source-reader", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Reader Sources", "slug": "reader-sources"},
    )
    kb_id = create_kb_response.json()["id"]
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )

    _authenticate_as(client, monkeypatch, reader)
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        files={"file": ("research.md", b"# Research\n", "text/markdown")},
    )

    assert upload_response.status_code == 403
    assert upload_response.json()["detail"]["errorCode"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_query_api_returns_context_from_raw_sources(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-query-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Query Sources", "slug": "query-sources"},
    )
    kb_id = create_kb_response.json()["id"]
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/sources/python-packaging.md",
            "type": "file",
            "content": (
                "---\n"
                "title: Python Packaging\n"
                "type: source\n"
                "---\n\n"
                "# Python Packaging\n\n"
                "Python packaging uses wheels and indexes for distribution.\n"
            ),
            "revision": "",
        },
    )

    query_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query",
        json={"query": "python wheels", "limit": 4},
    )

    assert write_response.status_code == 200
    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["kbId"] == kb_id
    assert payload["query"] == "python wheels"
    assert payload["status"] == "context_ready"
    assert payload["answer"] == ""
    assert payload["citations"][0]["path"] == "raw/sources/python-packaging.md"
    assert payload["citations"][0]["title"] == "Python Packaging"
    assert payload["citations"][0]["type"] == "source"
    assert "wheels" in payload["citations"][0]["snippet"].lower()
    assert payload["context"][0]["path"] == "raw/sources/python-packaging.md"
    assert payload["context"][0]["type"] == "source"
    assert payload["context"][0]["citationIndex"] == 0
    assert payload["context"][0]["reasons"] == ["lexical_match"]
    assert "Python packaging uses wheels" in payload["context"][0]["content"]


@pytest.mark.integration
def test_knowledge_base_query_api_allows_viewer_with_read_access(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-query-share-owner", platform_role="member", role_status="valid"
    )
    reader = create_user(
        username="kb-query-share-reader", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Shared Query Sources", "slug": "shared-query-sources"},
    )
    kb_id = create_kb_response.json()["id"]
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/sources/roadmap.md",
            "type": "file",
            "content": "# Roadmap\n\nThe product roadmap includes query access for viewers.\n",
            "revision": "",
        },
    )
    share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )

    _authenticate_as(client, monkeypatch, reader)
    query_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query",
        json={"query": "roadmap viewers"},
    )

    assert write_response.status_code == 200
    assert share_response.status_code == 201
    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["status"] == "context_ready"
    assert payload["citations"][0]["path"] == "raw/sources/roadmap.md"
    assert payload["context"][0]["reasons"] == ["lexical_match"]


@pytest.mark.integration
def test_knowledge_base_query_api_returns_no_context_without_matching_documents(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-query-empty-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Empty Query Sources", "slug": "empty-query-sources"},
    )
    kb_id = create_kb_response.json()["id"]

    query_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query",
        json={"query": "missing topic"},
    )

    assert query_response.status_code == 200
    payload = query_response.json()
    assert payload["kbId"] == kb_id
    assert payload["query"] == "missing topic"
    assert payload["status"] == "no_context"
    assert payload["answer"] == ""
    assert payload["citations"] == []
    assert payload["context"] == []


@pytest.mark.integration
def test_knowledge_base_operation_status_reports_inactive_when_idle(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-op-status-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases", json={"name": "Op Docs", "slug": "op-docs"}
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/init",
        json={"defaultBranch": "main"},
    )

    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/operation-status"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["isActive"] is False
    assert body["operation"] is None


@pytest.mark.integration
def test_knowledge_base_git_api_supports_enable_changes_commit_and_history(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="kb-git-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    with session_factory() as session:
        session.add(
            db_models.UserSetting(
                id="kb-git-owner-settings",
                user_id=owner.id,
                git_user_name="Knowledge Base Owner",
                git_user_email="kb-owner@example.local",
            )
        )
        session.commit()
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Git Docs", "slug": "git-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    disabled_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/status"
    )
    initial_status_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/repository"
    )
    enable_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/init",
        json={"defaultBranch": "main"},
    )
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/api.md",
            "type": "file",
            "content": "# API\n",
            "revision": "",
        },
    )
    changes_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/changes"
    )
    stage_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/stage",
        json={"paths": ["raw/api.md"]},
    )
    commit_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/commit",
        json={"message": "Add raw API page"},
    )
    commit_id = commit_response.json()["commit"]["id"]
    commits_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/commits"
    )
    files_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/commits/{commit_id}/files"
    )
    blob_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/blob",
        params={"path": "raw/api.md", "revision": commit_id},
    )

    assert disabled_response.status_code == 400
    assert (
        disabled_response.json()["detail"]["errorCode"] == "KB_VERSION_CONTROL_DISABLED"
    )
    assert initial_status_response.status_code == 200
    assert initial_status_response.json()["isGitRepo"] is False
    assert enable_response.status_code == 200
    assert enable_response.json()["isInitialized"] is True
    assert enable_response.json()["currentBranch"] == "main"
    assert write_response.status_code == 200
    assert changes_response.status_code == 200
    assert [item["path"] for item in changes_response.json()["untracked"]["items"]] == [
        "raw/api.md"
    ]
    assert stage_response.status_code == 200
    assert stage_response.json()["staged"] == ["raw/api.md"]
    assert commit_response.status_code == 200
    assert commit_response.json()["commit"]["message"] == "Add raw API page"
    assert commits_response.status_code == 200
    assert commits_response.json()["total"] == 1
    assert files_response.status_code == 200
    assert [item["path"] for item in files_response.json()["files"]] == ["raw/api.md"]
    assert blob_response.status_code == 200
    assert blob_response.json()["content"] == "# API\n"


@pytest.mark.integration
def test_knowledge_base_clone_rejects_existing_content_without_overwriting(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-clone-content-owner",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Existing Docs", "slug": "existing-docs"},
    ).json()["id"]
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/notes.md",
            "type": "file",
            "content": "# Existing\n",
            "revision": "",
        },
    )

    clone_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/clone",
        json={"remoteUrl": "https://example.invalid/docs.git"},
    )
    read_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/notes.md"},
    )

    assert write_response.status_code == 200
    assert clone_response.status_code == 409
    assert clone_response.json()["detail"]["errorCode"] == "VC_CLONE_TARGET_NOT_EMPTY"
    assert read_response.json()["content"] == "# Existing\n"


@pytest.mark.integration
def test_knowledge_base_clone_ssh_requires_system_user_key(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-clone-ssh-owner",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "SSH Docs", "slug": "ssh-docs"},
    ).json()["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/clone",
        json={"remoteUrl": "git@example.invalid:team/docs.git"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "VC_SSH_KEY_REQUIRED"


def test_knowledge_base_git_force_unlock_clears_stale_on_disk_lock(
    test_app, create_user, monkeypatch
):
    """KB force-unlock returns a target-safe shared mutation result."""
    from pathlib import Path

    client, _ = test_app
    owner = create_user(
        username="kb-force-unlock-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases", json={"name": "Force Docs", "slug": "force-docs"}
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/init",
        json={"defaultBranch": "main"},
    )

    kb_root = Path(get_settings().MANAGER_KNOWLEDGE_BASES_DIR) / kb_id
    stale_lock = kb_root / ".git" / "index.lock"
    stale_lock.write_text("stale", encoding="utf-8")
    stale_time = time.time() - 60
    os.utime(stale_lock, (stale_time, stale_time))
    assert stale_lock.exists()

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/force-unlock"
    )

    assert response.status_code == 200
    assert response.json()["affectedTotal"] == 1
    assert "cleared" not in response.json()
    assert not stale_lock.exists()


def test_knowledge_base_git_force_unlock_refuses_during_active_operation(
    test_app, create_user, monkeypatch
):
    """KB force-unlock during an active in-memory op returns 409 canForceUnlock:false."""
    from pathlib import Path

    from aileron_git_core import LockScope, OperationKind

    from app.modules.knowledge_base import git as kb_git_module
    from app.modules.knowledge_base.git_operations import kb_git_operation_key

    client, _ = test_app
    owner = create_user(
        username="kb-force-unlock-active",
        platform_role="member",
        role_status="valid",
    )
    _authenticate_as(client, monkeypatch, owner)
    kb_id = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Active Docs", "slug": "active-docs"},
    ).json()["id"]
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/init",
        json={"defaultBranch": "main"},
    )

    kb_root = Path(get_settings().MANAGER_KNOWLEDGE_BASES_DIR) / kb_id
    stale_lock = kb_root / ".git" / "index.lock"
    stale_lock.write_text("stale", encoding="utf-8")

    # Hold a real in-memory operation lock on the KB key, then call force-unlock.
    manager = kb_git_module.KB_GIT_OPERATION_MANAGER
    key = kb_git_operation_key(kb_id)
    with manager.acquire(
        key,
        OperationKind.WRITE,
        operation_name="external",
        blocking_scope=LockScope.COMMON_REPOSITORY,
    ):
        response = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/version-control/force-unlock"
        )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["errorCode"] == "operation_locked"
    assert detail["canForceUnlock"] is False
    assert detail["blockingScope"] == "common_repository"
    # The stale lock must NOT have been cleared while an active op held the key.
    assert stale_lock.exists()


@pytest.mark.integration
def test_knowledge_base_git_api_supports_lfs_remote_and_shared_branch_contract(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="kb-git-manager", platform_role="member", role_status="valid"
    )
    reader = create_user(
        username="kb-git-reader", platform_role="member", role_status="valid"
    )
    with session_factory() as session:
        session.add(
            db_models.UserSetting(
                id="kb-git-manager-settings",
                user_id=owner.id,
                git_user_name="Knowledge Base Manager",
                git_user_email="kb-manager@example.local",
            )
        )
        session.commit()
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Managed Git Docs", "slug": "managed-git-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )
    enable_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/init", json={}
    )
    create_lfs_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={
            "path": "/raw/docs/guide.pdf",
            "type": "file",
            "content": "pdf-data",
        },
    )
    lfs_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/lfs",
        json={"patterns": ["raw/**/*.pdf"]},
    )
    remote_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/remote",
        json={"remoteUrl": "https://example.com/team/knowledge.git"},
    )
    lfs_patterns_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/lfs"
    )
    lfs_preview_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/lfs/preview",
        json={},
    )
    monkeypatch.setattr(
        "aileron_git_core.application.convert_snapshot",
        lambda _root, paths, **_kwargs: tuple(paths),
    )
    lfs_convert_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/lfs/convert",
        json={"paths": ["raw/docs/guide.pdf"]},
    )
    remote_settings_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/remote"
    )
    cancel_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/operation/cancel"
    )
    status_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/repository"
    )
    removed_checkout_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/branches/draft/checkout",
        json={"create": True},
    )
    branches_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/branches"
    )
    removed_rollback_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/version-control/rollback",
        json={"revision": "HEAD", "confirm": "wrong"},
    )

    assert enable_response.status_code == 200
    assert create_lfs_file_response.status_code == 200
    assert enable_response.json()["currentBranch"] == "main"
    assert lfs_response.status_code == 200
    assert lfs_response.json()["commandId"] == "lfs.patterns.update"
    assert lfs_patterns_response.status_code == 200
    assert lfs_patterns_response.json() == {"patterns": ["raw/**/*.pdf"]}
    assert lfs_preview_response.status_code == 200
    assert lfs_preview_response.json() == {
        "matchedTotal": 1,
        "totalSize": len("pdf-data"),
        "pathSample": ["raw/docs/guide.pdf"],
    }
    assert lfs_convert_response.status_code == 200
    assert lfs_convert_response.json()["commandId"] == "lfs.snapshot.convert"
    assert lfs_convert_response.json()["affectedTotal"] == 1
    assert remote_response.status_code == 200
    assert remote_response.json()["output"] == "origin"
    assert remote_settings_response.status_code == 200
    assert remote_settings_response.json() == {
        "remoteName": "origin",
        "remoteUrl": "https://example.com/team/knowledge.git",
        "hasOrigin": True,
    }
    assert cancel_response.status_code == 409
    assert cancel_response.json()["detail"]["errorCode"] == "operation_not_cancellable"
    assert status_response.status_code == 200
    assert (
        status_response.json()["remoteUrl"] == "https://example.com/team/knowledge.git"
    )
    assert removed_checkout_response.status_code == 404
    assert {branch["name"] for branch in branches_response.json()["branches"]} == {
        "main"
    }
    assert removed_rollback_response.status_code == 404


@pytest.mark.integration
def test_knowledge_base_file_paste_supports_copy_and_conflict_resolution(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-copy-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Copy Files", "slug": "copy-files"},
    )
    kb_id = create_kb_response.json()["id"]

    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/raw/readme.md", "type": "file", "content": "hello kb"},
    )
    copy_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/paste",
        json={
            "targetPath": "/raw/copies",
            "sources": [{"sourcePath": "/raw/readme.md", "entryType": "file"}],
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    copied_content_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/copies/readme.md"},
    )
    conflict_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/paste",
        json={
            "targetPath": "/raw/copies",
            "sources": [{"sourcePath": "/raw/readme.md", "entryType": "file"}],
            "defaultStrategy": "skip",
            "resolutions": [],
        },
    )

    assert create_file_response.status_code == 200
    assert copy_file_response.status_code == 200
    assert copy_file_response.json()["items"][0]["type"] == "file"
    assert copy_file_response.json()["items"][0]["size"] == len("hello kb")
    assert copied_content_response.status_code == 200
    assert copied_content_response.json()["content"] == "hello kb"
    assert conflict_response.status_code == 200
    assert conflict_response.json()["items"][0]["status"] == "skipped"


@pytest.mark.integration
def test_knowledge_base_file_paste_endpoint_requires_manager(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-copy-owner-2", platform_role="member", role_status="valid"
    )
    reader = create_user(
        username="kb-copy-reader", platform_role="member", role_status="valid"
    )

    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Reader Copy Files", "slug": "reader-copy-files"},
    )
    kb_id = create_kb_response.json()["id"]
    share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"targetType": "user", "targetId": reader.id, "role": "reader"},
    )
    assert share_response.status_code == 201

    owner_missing_source_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/paste",
        json={
            "targetPath": "/raw/copies",
            "sources": [{"sourcePath": "/raw/missing.md", "entryType": "file"}],
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )
    assert owner_missing_source_response.status_code == 404
    assert (
        owner_missing_source_response.json()["detail"]["errorCode"] == "FILE_NOT_FOUND"
    )

    _authenticate_as(client, monkeypatch, reader)
    viewer_copy_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/paste",
        json={
            "targetPath": "/raw/copies",
            "sources": [{"sourcePath": "/raw/missing.md", "entryType": "file"}],
            "defaultStrategy": "cancel",
            "resolutions": [],
        },
    )

    assert viewer_copy_response.status_code == 403
    assert viewer_copy_response.json()["detail"]["errorCode"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_workspace_knowledge_base_canonical_mutations_persist_latest_durable_intent(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="workspace-runtime-owner",
        platform_role="member",
        role_status="valid",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Runtime Docs", "slug": "runtime-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    attach_correlation_id = str(uuid4())
    update_correlation_id = str(uuid4())
    detach_correlation_id = str(uuid4())

    attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "runtime-docs"},
        headers={"X-Correlation-ID": attach_correlation_id},
    )
    attachment_id = attach_response.json()["attachment"]["id"]
    pending_attach_list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases"
    )

    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        attach_job = session.scalar(
            select(db_models.WorkspaceRuntimeJob).where(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.target_revision == 1,
            )
        )
        active_snapshot = list(workspace.knowledge_base_mount_candidate_snapshot)
        workspace.knowledge_base_mount_active_snapshot = active_snapshot
        workspace.knowledge_base_mount_active_revision = 1
        workspace.knowledge_base_mount_observed_revision = 1
        workspace.knowledge_base_mount_candidate_snapshot = None
        workspace.knowledge_base_mount_sync_status = "ready"
        attach_job.status = "succeeded"
        attach_job.finished_at = datetime.utcnow()
        session.add(
            db_models.WorkspaceKnowledgeBaseAttachment(
                id=attachment_id,
                workspace_id=workspace_id,
                kb_id=kb_id,
                mount_alias="runtime-docs",
                attached_by_id=owner.id,
            )
        )
        session.commit()

    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}")
    update_response = client.patch(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}",
        json={"mountAlias": "runtime-docs-v2"},
        headers={"X-Correlation-ID": update_correlation_id},
    )
    pending_rename_list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases"
    )
    detach_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}",
        headers={"X-Correlation-ID": detach_correlation_id},
    )
    pending_removal_list_response = client.get(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases"
    )
    delete_mounted_kb_response = client.request(
        "DELETE",
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"confirmationName": "Runtime Docs"},
    )

    assert attach_response.status_code == 202
    assert attach_response.headers["X-Correlation-ID"] == attach_correlation_id
    assert attach_response.json()["attachment"]["kbId"] == kb_id
    assert attach_response.json()["attachment"]["mountAlias"] == "runtime-docs"
    assert attach_response.json()["attachment"]["status"] == "pending"
    assert attach_response.json()["knowledgeBaseMountSync"] == {
        "status": "syncing",
        "desiredRevision": 1,
        "observedRevision": 0,
        "lastKnownGoodRevision": 0,
        "errorCode": None,
        "compensating": False,
    }
    assert pending_attach_list_response.status_code == 200
    assert pending_attach_list_response.json()["items"] == [
        attach_response.json()["attachment"]
    ]
    assert (
        pending_attach_list_response.json()["knowledgeBaseMountSync"]["desiredRevision"]
        == 1
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["attachedKnowledgeBases"][0]["kbId"] == kb_id
    assert "role" not in detail_response.json()["attachedKnowledgeBases"][0]
    assert detail_response.json()["knowledgeBaseMountActiveRevision"] == 1
    assert detail_response.json()["knowledgeBaseMountDesiredRevision"] == 1
    assert detail_response.json()["knowledgeBaseMountObservedRevision"] == 1
    assert detail_response.json()["knowledgeBaseMountSyncStatus"] == "ready"

    assert update_response.status_code == 202
    assert update_response.json()["attachment"]["mountAlias"] == "runtime-docs-v2"
    assert update_response.json()["attachment"]["status"] == "pending"
    assert update_response.json()["knowledgeBaseMountSync"]["desiredRevision"] == 2
    assert (
        pending_rename_list_response.json()["items"][0]["mountAlias"]
        == "runtime-docs-v2"
    )
    assert pending_rename_list_response.json()["items"][0]["status"] == "pending"
    assert detach_response.status_code == 202
    assert detach_response.json()["attachment"]["status"] == "pending_removal"
    assert detach_response.json()["knowledgeBaseMountSync"]["desiredRevision"] == 3
    assert (
        pending_removal_list_response.json()["items"][0]["status"] == "pending_removal"
    )
    assert delete_mounted_kb_response.status_code == 409
    assert (
        delete_mounted_kb_response.json()["detail"]["errorCode"]
        == "KB_DELETE_ATTACHMENT_CONFLICT"
    )
    assert delete_mounted_kb_response.json()["detail"]["details"] == {
        "attachmentCount": 1,
        "visibleWorkspaces": [
            {
                "attachmentId": attachment_id,
                "workspaceId": workspace_id,
                "workspaceName": "KB Workspace",
                "mountAlias": "runtime-docs",
                "attachmentStatus": "active",
            }
        ],
        "hiddenWorkspaceCount": 0,
    }

    with session_factory() as session:
        jobs = (
            session.query(db_models.WorkspaceRuntimeJob)
            .filter(
                db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                db_models.WorkspaceRuntimeJob.operation
                == "knowledge_base_mount_reconcile",
            )
            .order_by(db_models.WorkspaceRuntimeJob.target_revision)
            .all()
        )

    assert [job.target_revision for job in jobs] == [1, 2, 3]
    assert [job.status for job in jobs] == ["succeeded", "superseded", "queued"]
    assert [job.correlation_id for job in jobs] == [
        attach_correlation_id,
        update_correlation_id,
        detach_correlation_id,
    ]
    assert [job.job_metadata["mutation_action"] for job in jobs] == [
        "attach",
        "update_alias",
        "detach",
    ]


@pytest.mark.integration
def test_knowledge_base_content_update_does_not_reconcile_existing_mount(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="workspace-mounted-kb-owner",
        platform_role="member",
        role_status="valid",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Mounted Content", "slug": "mounted-content"},
    )
    kb_id = create_kb_response.json()["id"]
    attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "mounted-content"},
    )
    assert attach_response.status_code == 202

    content_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/raw/live.md",
            "type": "file",
            "content": "visible through the existing read-only mount",
            "revision": "",
        },
    )

    assert content_response.status_code == 200
    with session_factory() as session:
        workspace = session.get(db_models.Workspace, workspace_id)
        jobs = list(
            session.scalars(
                select(db_models.WorkspaceRuntimeJob).where(
                    db_models.WorkspaceRuntimeJob.workspace_id == workspace_id,
                    db_models.WorkspaceRuntimeJob.operation
                    == "knowledge_base_mount_reconcile",
                )
            ).all()
        )
        assert workspace.knowledge_base_mount_desired_revision == 1
        assert workspace.knowledge_base_mount_observed_revision == 0
        assert len(jobs) == 1
        assert jobs[0].target_revision == 1
        assert jobs[0].job_metadata["mutation_action"] == "attach"


@pytest.mark.integration
def test_workspace_knowledge_base_errors_are_code_only_and_reject_path_mismatch(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="workspace-owner",
        platform_role="member",
        role_status="valid",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    other_workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Workspace Docs", "slug": "workspace-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    first_attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "workspace-docs"},
    )
    attachment_id = first_attach_response.json()["attachment"]["id"]
    duplicate_correlation_id = str(uuid4())
    duplicate_attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "workspace-docs"},
        headers={"X-Correlation-ID": duplicate_correlation_id},
    )
    mismatch_correlation_id = str(uuid4())
    path_mismatch_response = client.patch(
        f"/api/v1/workspaces/{other_workspace_id}/knowledge-bases/{attachment_id}",
        json={"mountAlias": "mismatched-docs"},
        headers={"X-Correlation-ID": mismatch_correlation_id},
    )
    missing_correlation_id = str(uuid4())
    missing_attachment_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases/not-found-attachment",
        headers={"X-Correlation-ID": missing_correlation_id},
    )

    assert first_attach_response.status_code == 202
    assert duplicate_attach_response.status_code == 409
    assert duplicate_attach_response.json()["detail"]["errorCode"] == (
        "KB_ALREADY_ATTACHED"
    )
    assert duplicate_attach_response.json()["detail"]["details"]["correlationId"] == (
        duplicate_correlation_id
    )
    assert path_mismatch_response.status_code == 404
    assert path_mismatch_response.json()["detail"]["errorCode"] == (
        "KB_ATTACHMENT_NOT_FOUND"
    )
    assert path_mismatch_response.json()["detail"]["details"]["correlationId"] == (
        mismatch_correlation_id
    )
    assert missing_attachment_response.status_code == 404
    assert missing_attachment_response.json()["detail"]["errorCode"] == (
        "KB_ATTACHMENT_NOT_FOUND"
    )
    assert missing_attachment_response.json()["detail"]["details"]["correlationId"] == (
        missing_correlation_id
    )


@pytest.mark.integration
def test_knowledge_base_file_api_accepts_any_file_extension(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files"},
    )
    kb_id = create_kb_response.json()["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/raw/malware.exe", "type": "file", "content": "boom"},
    )
    read_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/raw/malware.exe"},
    )

    assert response.status_code == 200
    assert read_response.status_code == 200
    assert read_response.json()["content"] == "boom"


@pytest.mark.integration
def test_knowledge_base_api_localizes_error_message_by_request_language(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner-zh", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)
    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files-zh"},
    )
    kb_id = create_kb_response.json()["id"]

    response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/../raw/malware.exe"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_PATH"
    assert response.json()["detail"]["message"] == "無效的路徑"


@pytest.mark.integration
def test_knowledge_base_generic_invalid_request_and_conflict_use_simple_messages(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner-generic", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    with patch(
        "app.modules.knowledge_base.router.KnowledgeBaseService.create_kb",
        side_effect=ValueError("unexpected invalid request detail"),
    ):
        en_invalid_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert en_invalid_response.status_code == 400
        assert en_invalid_response.json()["detail"]["errorCode"] == "KB_INVALID_REQUEST"
        assert (
            en_invalid_response.json()["detail"]["message"]
            == "Invalid knowledge base request"
        )

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.modules.knowledge_base.router.KnowledgeBaseService.create_kb",
        side_effect=ValueError("unexpected invalid request detail"),
    ):
        zh_invalid_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert zh_invalid_response.status_code == 400
        assert zh_invalid_response.json()["detail"]["errorCode"] == "KB_INVALID_REQUEST"
        assert zh_invalid_response.json()["detail"]["message"] == "無效的知識庫請求"

    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.modules.knowledge_base.router.KnowledgeBaseService.create_kb",
        side_effect=KnowledgeBaseConflictError("unexpected conflict detail"),
    ):
        en_conflict_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert en_conflict_response.status_code == 409
        assert en_conflict_response.json()["detail"]["errorCode"] == "KB_CONFLICT"
        assert (
            en_conflict_response.json()["detail"]["message"]
            == "Knowledge base conflict"
        )

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.modules.knowledge_base.router.KnowledgeBaseService.create_kb",
        side_effect=KnowledgeBaseConflictError("unexpected conflict detail"),
    ):
        zh_conflict_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert zh_conflict_response.status_code == 409
        assert zh_conflict_response.json()["detail"]["errorCode"] == "KB_CONFLICT"
        assert zh_conflict_response.json()["detail"]["message"] == "知識庫發生衝突"


@pytest.mark.integration
def test_workspace_knowledge_base_error_contract_is_language_independent(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="workspace-owner-coded",
        platform_role="member",
        role_status="valid",
    )
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    en_correlation_id = str(uuid4())
    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.modules.workspace.router.KnowledgeBaseAttachmentService.attach",
        side_effect=KnowledgeBaseConflictError(
            "totally different conflict wording", code="KB_ALREADY_ATTACHED"
        ),
    ):
        en_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": "kb-123", "mountAlias": "docs"},
            headers={"X-Correlation-ID": en_correlation_id},
        )

    zh_correlation_id = str(uuid4())
    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.modules.workspace.router.KnowledgeBaseAttachmentService.attach",
        side_effect=KnowledgeBaseConflictError(
            "totally different conflict wording", code="KB_ALREADY_ATTACHED"
        ),
    ):
        zh_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": "kb-123", "mountAlias": "docs"},
            headers={"X-Correlation-ID": zh_correlation_id},
        )

    assert en_response.status_code == 409
    assert en_response.json()["detail"]["errorCode"] == "KB_ALREADY_ATTACHED"
    assert en_response.json()["detail"]["details"]["correlationId"] == en_correlation_id
    assert zh_response.status_code == 409
    assert zh_response.json()["detail"]["errorCode"] == "KB_ALREADY_ATTACHED"
    assert zh_response.json()["detail"]["details"]["correlationId"] == zh_correlation_id


@pytest.mark.integration
def test_knowledge_base_file_api_returns_structured_kb_quota_error(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Quota Files", "slug": "quota-files"},
    )
    kb_id = create_kb_response.json()["id"]
    with session_factory() as session:
        knowledge_base = session.get(db_models.KnowledgeBase, kb_id)
        assert knowledge_base is not None
        knowledge_base.quota_bytes = 4
        session.commit()

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/raw/readme.md", "type": "file", "content": "hello"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["errorCode"] == "KB_QUOTA_EXCEEDED"
    assert response.json()["detail"]["message"] == "Knowledge base quota exceeded"
    assert response.json()["detail"]["details"]["quotaBytes"] == 4


@pytest.mark.integration
def test_knowledge_base_file_api_accepts_writes_above_single_file_read_limit(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    monkeypatch.setenv("KB_SINGLE_FILE_SIZE_LIMIT", "4")
    get_settings.cache_clear()

    try:
        create_kb_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "Large Files", "slug": "large-files"},
        )
        kb_id = create_kb_response.json()["id"]

        response = client.post(
            f"/api/v1/knowledge-bases/{kb_id}/files",
            data={"path": "/raw/too-large.md", "type": "file", "content": "hello"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json()["size"] == 5


@pytest.mark.integration
def test_knowledge_base_centric_attachment_mutations_are_not_exposed(
    test_app, create_user, monkeypatch
):
    client, _ = test_app
    owner = create_user(
        username="kb-owner", platform_role="member", role_status="valid"
    )
    _authenticate_as(client, monkeypatch, owner)

    kb = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Docs", "slug": "docs"},
    ).json()

    post_response = client.post(
        f"/api/v1/knowledge-bases/{kb['id']}/attachments",
        json={"workspaceId": "workspace-id", "mountAlias": "docs"},
    )
    patch_response = client.patch(
        f"/api/v1/knowledge-bases/{kb['id']}/attachments",
        json={"mountAlias": "docs-v2"},
    )
    delete_response = client.delete(f"/api/v1/knowledge-bases/{kb['id']}/attachments")
    openapi_schema = client.get("/openapi.json").json()
    openapi_paths = openapi_schema["paths"]

    assert post_response.status_code == 405
    assert patch_response.status_code == 405
    assert delete_response.status_code == 405
    assert set(openapi_paths["/api/v1/knowledge-bases/{kb_id}/attachments"]) == {"get"}
    workspace_mount_conflict_schema = openapi_paths[
        "/api/v1/workspaces/{workspace_id}/knowledge-bases"
    ]["post"]["responses"]["409"]["content"]["application/json"]["schema"]
    assert workspace_mount_conflict_schema == {
        "$ref": "#/components/schemas/WorkspaceKnowledgeBaseErrorResponse"
    }
    mount_error_properties = openapi_schema["components"]["schemas"][
        "WorkspaceKnowledgeBaseErrorDetail"
    ]["properties"]
    assert set(mount_error_properties) == {
        "errorCode",
        "correlationId",
        "details",
    }


@pytest.mark.integration
def test_knowledge_base_usage_masks_inaccessible_workspaces_and_preserves_in_use_guard(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(
        username="kb-owner",
        platform_role="member",
        role_status="valid",
    )
    hidden_workspace_owner = create_user(
        username="hidden-workspace-owner",
        platform_role="member",
        role_status="valid",
    )
    visible_workspace_id = _create_workspace(
        session_factory,
        owner_id=owner.id,
        name="Visible Workspace",
    )
    hidden_workspace_id = _create_workspace(
        session_factory,
        owner_id=hidden_workspace_owner.id,
        name="Hidden Workspace",
    )
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Shared Runtime Docs", "slug": "shared-runtime-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    visible_attach_response = client.post(
        f"/api/v1/workspaces/{visible_workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "visible-docs"},
    )
    share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={
            "targetType": "user",
            "targetId": hidden_workspace_owner.id,
            "role": "manager",
        },
    )

    _authenticate_as(client, monkeypatch, hidden_workspace_owner)
    hidden_attach_response = client.post(
        f"/api/v1/workspaces/{hidden_workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mountAlias": "hidden-docs"},
    )

    _authenticate_as(client, monkeypatch, owner)
    usage_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/attachments")
    delete_conflict_response = client.request(
        "DELETE",
        f"/api/v1/knowledge-bases/{kb_id}",
        json={"confirmationName": "Shared Runtime Docs"},
    )
    read_response = client.get(f"/api/v1/knowledge-bases/{kb_id}")

    assert visible_attach_response.status_code == 202
    assert share_response.status_code == 201
    assert hidden_attach_response.status_code == 202
    assert usage_response.status_code == 200
    assert usage_response.json() == {
        "visibleItems": [
            {
                "attachmentId": visible_attach_response.json()["attachment"]["id"],
                "workspaceId": visible_workspace_id,
                "workspaceName": "Visible Workspace",
                "mountAlias": "visible-docs",
                "attachmentStatus": "pending",
            }
        ],
        "hiddenWorkspaceCount": 1,
        "attachmentCount": 2,
    }
    assert delete_conflict_response.status_code == 409
    assert (
        delete_conflict_response.json()["detail"]["errorCode"]
        == "KB_DELETE_ATTACHMENT_CONFLICT"
    )
    assert delete_conflict_response.json()["detail"]["details"] == {
        "attachmentCount": 2,
        "visibleWorkspaces": [
            {
                "attachmentId": visible_attach_response.json()["attachment"]["id"],
                "workspaceId": visible_workspace_id,
                "workspaceName": "Visible Workspace",
                "mountAlias": "visible-docs",
                "attachmentStatus": "pending",
            }
        ],
        "hiddenWorkspaceCount": 1,
    }
    assert read_response.status_code == 200
