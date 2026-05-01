from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.config.settings import get_settings
from app.db import models as db_models
from app.services.knowledge_base_service import KnowledgeBaseConflictError


def _authenticate_as(client, monkeypatch, user: db_models.User) -> None:
    async def mock_validate_token(self, token: str) -> dict[str, str]:
        return {
            "sub": f"keycloak-{user.id}",
            "preferred_username": user.username,
            "email": user.email,
        }

    async def mock_ensure_local_user(payload: dict) -> str:
        return user.id

    monkeypatch.setattr(
        "app.modules.auth.middleware.JWTAuthenticationMiddleware._validate_token",
        mock_validate_token,
    )
    monkeypatch.setattr(
        "app.modules.auth.middleware._ensure_local_user",
        mock_ensure_local_user,
    )
    client.headers.pop("X-Internal-Token", None)
    client.headers.update({"Authorization": "Bearer test-access-token"})


def _create_workspace(
    session_factory,
    *,
    owner_id: str,
    runtime_status: str = "stopped",
    runtime_container_id: str | None = None,
) -> str:
    with session_factory() as session:
        workspace = db_models.Workspace(
            id=f"workspace-{uuid4().hex[:8]}",
            owner_id=owner_id,
            name="KB Workspace",
            runtime="universal",
            provisioner="docker",
            runtime_status=runtime_status,
            runtime_container_id=runtime_container_id,
            env_vars=[],
            port_mappings=[],
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
    owner = create_user(username="kb-owner")
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
def test_knowledge_base_share_and_attachment_flow(test_app, create_user, monkeypatch):
    client, session_factory = test_app
    owner = create_user(username="kb-owner")
    member = create_user(username="kb-member")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)

    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Team Docs", "slug": "team-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    create_share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"userId": member.id, "role": "viewer"},
    )
    list_share_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/shares")
    create_attachment_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/attachments",
        json={"workspaceId": workspace_id, "mode": "rw"},
    )
    list_attachment_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/attachments")

    assert create_share_response.status_code == 201
    assert create_share_response.json()["role"] == "viewer"
    assert list_share_response.status_code == 200
    assert len(list_share_response.json()["items"]) == 1
    assert create_attachment_response.status_code == 201
    assert create_attachment_response.json()["mountAlias"] == "team-docs"
    assert create_attachment_response.json()["mode"] == "rw"
    assert create_attachment_response.json()["workspaceName"] == "KB Workspace"
    assert list_attachment_response.status_code == 200
    assert len(list_attachment_response.json()["items"]) == 1
    assert list_attachment_response.json()["items"][0]["workspaceName"] == "KB Workspace"


@pytest.mark.integration
def test_knowledge_base_file_endpoints_support_create_read_delete(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files"},
    )
    kb_id = create_kb_response.json()["id"]

    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/readme.md", "type": "file", "content": "hello kb"},
    )
    read_file_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/readme.md"},
    )
    delete_file_response = client.delete(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        params={"path": "/readme.md"},
    )

    assert create_file_response.status_code == 200
    assert read_file_response.status_code == 200
    assert read_file_response.json()["content"] == "hello kb"
    assert delete_file_response.status_code == 200


@pytest.mark.integration
def test_knowledge_base_file_content_raw_supports_viewer_and_rejects_bad_paths(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-raw-owner")
    viewer = create_user(username="kb-raw-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Raw Files", "slug": "raw-files"},
    )
    kb_id = create_kb_response.json()["id"]
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={"path": "/pixel.png", "type": "file", "content": "png-bytes"},
    )
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    raw_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/pixel.png", "raw": "true"},
    )
    traversal_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/../pixel.png", "raw": "true"},
    )
    missing_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/missing.png", "raw": "true"},
    )

    assert write_response.status_code == 200
    assert raw_response.status_code == 200
    assert raw_response.headers["content-type"].startswith("image/png")
    assert raw_response.content == b"png-bytes"
    assert traversal_response.status_code == 400
    assert traversal_response.json()["detail"]["code"] == "INVALID_PATH"
    assert missing_response.status_code == 404


@pytest.mark.integration
def test_knowledge_base_source_api_uploads_sources_and_imports_web_clip(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-source-owner")
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
    assert clip_response.json()["assetPaths"] == ["/raw/assets/example-page/diagram.txt"]


@pytest.mark.integration
def test_knowledge_base_source_api_rejects_viewer_upload(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-source-owner-2")
    viewer = create_user(username="kb-source-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Viewer Sources", "slug": "viewer-sources"},
    )
    kb_id = create_kb_response.json()["id"]
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        files={"file": ("research.md", b"# Research\n", "text/markdown")},
    )

    assert upload_response.status_code == 403
    assert upload_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_ingest_job_api_supports_list_get_retry_and_cancel(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-ingest-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Ingest Jobs", "slug": "ingest-jobs"},
    )
    kb_id = create_kb_response.json()["id"]
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        files={"file": ("paper.md", b"# Paper\n\nBody\n", "text/markdown")},
    )
    source_path = upload_response.json()["source"]["path"]

    create_job_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/ingest",
        json={"sourcePaths": [source_path]},
    )
    job_id = create_job_response.json()["id"]
    list_jobs_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/jobs")
    get_job_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}")
    cancel_job_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}/cancel")
    retry_job_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}/retry")

    assert create_job_response.status_code == 201
    assert create_job_response.json()["status"] == "queued"
    assert create_job_response.json()["sourcePaths"] == [source_path]
    assert list_jobs_response.status_code == 200
    assert [item["id"] for item in list_jobs_response.json()["items"]] == [job_id]
    assert get_job_response.status_code == 200
    assert get_job_response.json()["id"] == job_id
    assert cancel_job_response.status_code == 200
    assert cancel_job_response.json()["status"] == "canceled"
    assert retry_job_response.status_code == 201
    assert retry_job_response.json()["id"] != job_id
    assert retry_job_response.json()["status"] == "queued"
    assert retry_job_response.json()["sourcePaths"] == [source_path]


@pytest.mark.integration
def test_knowledge_base_ingest_job_api_allows_viewer_reads_only(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-ingest-owner-2")
    viewer = create_user(username="kb-ingest-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Viewer Ingest Jobs", "slug": "viewer-ingest-jobs"},
    )
    kb_id = create_kb_response.json()["id"]
    upload_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/sources",
        files={"file": ("notes.md", b"# Notes\n", "text/markdown")},
    )
    create_job_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/ingest",
        json={"sourcePaths": [upload_response.json()["source"]["path"]]},
    )
    job_id = create_job_response.json()["id"]
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    list_jobs_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/jobs")
    get_job_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}")
    retry_job_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}/retry")
    cancel_job_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/jobs/{job_id}/cancel")

    assert list_jobs_response.status_code == 200
    assert list_jobs_response.json()["items"][0]["id"] == job_id
    assert get_job_response.status_code == 200
    assert get_job_response.json()["id"] == job_id
    assert retry_job_response.status_code == 403
    assert retry_job_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"
    assert cancel_job_response.status_code == 403
    assert cancel_job_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_query_api_returns_context_and_saves_answer(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-query-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Query Docs", "slug": "query-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/wiki/concepts/python.md",
            "type": "file",
            "content": (
                "---\n"
                "title: Python\n"
                "type: concept\n"
                "sources:\n"
                "  - /raw/sources/python.md\n"
                "---\n\n"
                "# Python\n\n"
                "Python packaging uses wheels and package indexes.\n"
            ),
        },
    )

    query_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query",
        json={"query": "python packaging", "limit": 4},
    )
    save_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query/save",
        json={
            "query": "python packaging",
            "answer": "Python packaging uses wheels.",
            "citations": query_response.json()["citations"],
            "title": "Python Packaging Answer",
        },
    )
    saved_path = save_response.json()["path"]
    read_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": saved_path},
    )

    assert query_response.status_code == 200
    query_payload = query_response.json()
    assert query_payload["status"] == "context_ready"
    assert query_payload["kbId"] == kb_id
    assert any(citation["path"] == "wiki/concepts/python.md" for citation in query_payload["citations"])
    assert save_response.status_code == 200
    assert saved_path == "/wiki/queries/python-packaging-answer.md"
    assert save_response.json()["commitId"] is None
    assert read_response.status_code == 200
    assert "type: query" in read_response.json()["content"]
    assert "Python packaging uses wheels." in read_response.json()["content"]


@pytest.mark.integration
def test_knowledge_base_query_api_allows_viewer_query_but_rejects_save(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-query-owner-2")
    viewer = create_user(username="kb-query-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Viewer Query Docs", "slug": "viewer-query-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={"path": "/wiki/overview.md", "type": "file", "content": "# Overview\n\nTeam wiki roadmap.\n"},
    )
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    query_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query",
        json={"query": "roadmap"},
    )
    save_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/query/save",
        json={"query": "roadmap", "answer": "Roadmap summary.", "citations": []},
    )

    assert query_response.status_code == 200
    assert query_response.json()["status"] == "context_ready"
    assert save_response.status_code == 403
    assert save_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_lint_api_returns_inline_report(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-lint-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Lint Docs", "slug": "lint-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={"path": "/wiki/broken.md", "type": "file", "content": "# Broken\n\nSee [[missing-page]].\n"},
    )

    lint_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/lint")

    assert lint_response.status_code == 200
    assert lint_response.json()["kbId"] == kb_id
    assert "reportPath" not in lint_response.json()
    assert "broken_wikilink" in lint_response.json()["issueCounts"]
    assert lint_response.json()["issues"][0]["path"] == "wiki/broken.md"


@pytest.mark.integration
def test_knowledge_base_lint_api_rejects_viewer_runs(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-lint-owner-2")
    viewer = create_user(username="kb-lint-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Viewer Lint Docs", "slug": "viewer-lint-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    run_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/lint")

    assert run_response.status_code == 403
    assert run_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_git_api_supports_enable_changes_commit_and_history(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-git-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Git Docs", "slug": "git-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    disabled_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/version-control/status")
    initial_status_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/repository/status")
    enable_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/repository/enable",
        json={"defaultBranch": "main", "initialMessage": "Initialize KB"},
    )
    write_response = client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={"path": "/wiki/api.md", "type": "file", "content": "# API\n"},
    )
    changes_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/version-control/changes")
    stage_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/stage",
        json={"paths": ["wiki/api.md"]},
    )
    commit_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/commit",
        json={"message": "Add API page"},
    )
    commit_id = commit_response.json()["commit"]["id"]
    commits_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/version-control/commits")
    files_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/version-control/commits/{commit_id}/files")
    blob_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/blob",
        params={"path": "wiki/api.md", "revision": commit_id},
    )

    assert disabled_response.status_code == 400
    assert disabled_response.json()["detail"]["code"] == "KB_VERSION_CONTROL_DISABLED"
    assert initial_status_response.status_code == 200
    assert initial_status_response.json()["isGitRepo"] is False
    assert enable_response.status_code == 200
    assert enable_response.json()["isGitRepo"] is True
    assert enable_response.json()["currentBranch"] == "main"
    assert write_response.status_code == 200
    assert changes_response.status_code == 200
    assert [item["path"] for item in changes_response.json()["untracked"]] == ["wiki/api.md"]
    assert stage_response.status_code == 200
    assert stage_response.json()["staged"] == ["wiki/api.md"]
    assert commit_response.status_code == 200
    assert commit_response.json()["commit"]["message"] == "Add API page"
    assert commits_response.status_code == 200
    assert commits_response.json()["total"] == 2
    assert files_response.status_code == 200
    assert [item["path"] for item in files_response.json()["files"]] == ["wiki/api.md"]
    assert blob_response.status_code == 200
    assert blob_response.json()["content"] == "# API"


@pytest.mark.integration
def test_knowledge_base_git_api_supports_lfs_remote_single_branch_and_rollback_guards(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-git-manager")
    viewer = create_user(username="kb-git-viewer")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Managed Git Docs", "slug": "managed-git-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})
    enable_response = client.post(f"/api/v1/knowledge-bases/{kb_id}/git/repository/enable", json={})
    lfs_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/lfs/enable",
        json={"patterns": ["raw/**/*.pdf"]},
    )
    remote_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/remote-url",
        json={"remoteUrl": "https://example.com/team/wiki.git"},
    )
    status_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/repository/status")
    checkout_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/branches/draft/checkout",
        json={"create": True},
    )
    branches_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/git/version-control/branches")
    rollback_guard_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/rollback",
        json={"revision": "HEAD", "confirm": "wrong"},
    )

    _authenticate_as(client, monkeypatch, viewer)
    viewer_rollback_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/git/version-control/rollback",
        json={"revision": "HEAD", "confirm": "RESET_KB_GIT"},
    )

    assert enable_response.status_code == 200
    assert enable_response.json()["currentBranch"] == "main"
    assert lfs_response.status_code == 200
    assert lfs_response.json()["success"] is True
    assert remote_response.status_code == 200
    assert remote_response.json()["success"] is True
    assert status_response.status_code == 200
    assert status_response.json()["remoteUrl"] == "https://example.com/team/wiki.git"
    assert checkout_response.status_code == 409
    assert checkout_response.json()["detail"]["code"] == "KB_SINGLE_BRANCH_POLICY"
    assert {branch["name"] for branch in branches_response.json()["branches"]} == {"main"}
    assert rollback_guard_response.status_code == 400
    assert rollback_guard_response.json()["detail"]["code"] == "KB_GIT_ROLLBACK_CONFIRMATION_REQUIRED"
    assert viewer_rollback_response.status_code == 403
    assert viewer_rollback_response.json()["detail"]["code"] == "KB_PERMISSION_DENIED"


@pytest.mark.integration
def test_knowledge_base_graph_api_returns_wiki_relationships_for_viewer(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-graph-owner")
    viewer = create_user(username="kb-graph-viewer")
    stranger = create_user(username="kb-graph-stranger")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Graph Docs", "slug": "graph-docs"},
    )
    kb_id = create_kb_response.json()["id"]
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/wiki/concepts/python.md",
            "type": "file",
            "content": "---\ntitle: Python\ntype: concept\nsources: [raw/sources/python.md]\n---\n\n# Python\n\nSee [[entities/guido]].\n",
        },
    )
    client.put(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        json={
            "path": "/wiki/entities/guido.md",
            "type": "file",
            "content": "---\ntitle: Guido\ntype: entity\nsources: [raw/sources/python.md]\n---\n\n# Guido\n",
        },
    )
    client.post(f"/api/v1/knowledge-bases/{kb_id}/shares", json={"userId": viewer.id, "role": "viewer"})

    _authenticate_as(client, monkeypatch, viewer)
    graph_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/graph")

    _authenticate_as(client, monkeypatch, stranger)
    denied_response = client.get(f"/api/v1/knowledge-bases/{kb_id}/graph")

    assert graph_response.status_code == 200
    nodes = {node["id"]: node for node in graph_response.json()["nodes"]}
    assert nodes["wiki/concepts/python"]["label"] == "Python"
    assert nodes["wiki/concepts/python"]["type"] == "concept"
    assert nodes["wiki/entities/guido"]["inboundCount"] == 1
    graph_edges = graph_response.json()["edges"]
    edge = next(
        item
        for item in graph_edges
        if {item["source"], item["target"]} == {"wiki/concepts/python", "wiki/entities/guido"}
    )
    assert {reason["type"] for reason in edge["reasons"]} >= {"direct_wikilink", "source_overlap", "type_affinity"}
    assert denied_response.status_code == 403
    assert denied_response.json()["detail"]["code"] == "KB_ACCESS_DENIED"


@pytest.mark.integration
def test_knowledge_base_file_copy_endpoint_supports_copy_and_conflict(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-copy-owner")
    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Copy Files", "slug": "copy-files"},
    )
    kb_id = create_kb_response.json()["id"]

    create_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/readme.md", "type": "file", "content": "hello kb"},
    )
    copy_file_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/copy",
        params={"source_path": "/readme.md", "dest_path": "/copies/readme.md"},
    )
    copied_content_response = client.get(
        f"/api/v1/knowledge-bases/{kb_id}/files/content",
        params={"path": "/copies/readme.md"},
    )
    conflict_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/copy",
        params={"source_path": "/readme.md", "dest_path": "/copies/readme.md"},
    )

    assert create_file_response.status_code == 200
    assert copy_file_response.status_code == 200
    assert copy_file_response.json()["type"] == "file"
    assert copy_file_response.json()["size"] == len("hello kb")
    assert copied_content_response.status_code == 200
    assert copied_content_response.json()["content"] == "hello kb"
    assert conflict_response.status_code == 409
    assert conflict_response.json()["detail"]["code"] == "FILE_ALREADY_EXISTS"


@pytest.mark.integration
def test_knowledge_base_file_copy_endpoint_rejects_viewer_and_missing_source(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-copy-owner-2")
    viewer = create_user(username="kb-copy-viewer")

    _authenticate_as(client, monkeypatch, owner)
    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Viewer Copy Files", "slug": "viewer-copy-files"},
    )
    kb_id = create_kb_response.json()["id"]
    share_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/shares",
        json={"userId": viewer.id, "role": "viewer"},
    )
    assert share_response.status_code == 201

    owner_missing_source_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/copy",
        params={"source_path": "/missing.md", "dest_path": "/copies/missing.md"},
    )
    assert owner_missing_source_response.status_code == 404
    assert owner_missing_source_response.json()["detail"]["code"] == "FILE_NOT_FOUND"

    _authenticate_as(client, monkeypatch, viewer)
    viewer_copy_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files/copy",
        params={"source_path": "/missing.md", "dest_path": "/copies/missing.md"},
    )

    assert viewer_copy_response.status_code == 403
    assert viewer_copy_response.json()["detail"]["code"] == "KB_ACCESS_DENIED"


@pytest.mark.integration
def test_workspace_knowledge_base_endpoints_and_detail_fields(test_app, create_user, monkeypatch):
    client, session_factory = test_app
    owner = create_user(username="workspace-owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Runtime Docs", "slug": "runtime-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mode": "rw"},
    )
    list_response = client.get(f"/api/v1/workspaces/{workspace_id}/knowledge-bases")
    detail_response = client.get(f"/api/v1/workspaces/{workspace_id}")

    assert attach_response.status_code == 201
    assert attach_response.json()["kbId"] == kb_id
    assert attach_response.json()["mountAlias"] == "runtime-docs"
    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert detail_response.status_code == 200
    assert len(detail_response.json()["attachedKnowledgeBases"]) == 1
    assert detail_response.json()["attachedKnowledgeBases"][0]["kbId"] == kb_id
    assert detail_response.json()["attachedKnowledgeBases"][0]["role"] == "owner"
    assert detail_response.json()["mountedKbSignature"] is None
    assert detail_response.json()["hasPendingKbChanges"] is True


@pytest.mark.integration
def test_workspace_knowledge_base_endpoints_schedule_runtime_sync_for_running_docker_workspace(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(username="workspace-runtime-owner")
    workspace_id = _create_workspace(
        session_factory,
        owner_id=owner.id,
        runtime_status="running",
        runtime_container_id="runtime-container-123",
    )
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Runtime Sync Docs", "slug": "runtime-sync-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    with patch("app.routers.workspaces.run_runtime_provision_task") as mock_runtime_sync:
        attach_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": kb_id, "mode": "rw"},
        )
        attachment_id = attach_response.json()["id"]
        update_response = client.patch(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}",
            json={"mountAlias": "runtime-sync-docs-v2", "mode": "ro"},
        )
        delete_response = client.delete(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}"
        )

    assert attach_response.status_code == 201
    assert update_response.status_code == 200
    assert delete_response.status_code == 204
    assert mock_runtime_sync.call_count == 3
    assert mock_runtime_sync.call_args_list[0].args == (workspace_id,)
    assert mock_runtime_sync.call_args_list[1].args == (workspace_id,)
    assert mock_runtime_sync.call_args_list[2].args == (workspace_id,)


@pytest.mark.integration
def test_workspace_knowledge_base_endpoints_do_not_schedule_runtime_sync_without_runtime_container(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(username="workspace-no-runtime-owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Pending Docs", "slug": "pending-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    with patch("app.routers.workspaces.run_runtime_provision_task") as mock_runtime_sync:
        attach_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": kb_id, "mode": "rw"},
        )

    assert attach_response.status_code == 201
    mock_runtime_sync.assert_not_called()


@pytest.mark.integration
def test_workspace_knowledge_base_endpoints_return_structured_conflict_and_not_found_errors(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(username="workspace-owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Workspace Docs", "slug": "workspace-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    first_attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mode": "rw"},
    )
    duplicate_attach_response = client.post(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
        json={"kbId": kb_id, "mode": "rw"},
    )
    missing_attachment_response = client.delete(
        f"/api/v1/workspaces/{workspace_id}/knowledge-bases/not-found-attachment"
    )

    assert first_attach_response.status_code == 201
    assert duplicate_attach_response.status_code == 409
    assert duplicate_attach_response.json()["detail"]["code"] == "KB_ALREADY_ATTACHED"
    assert duplicate_attach_response.json()["detail"]["message"] == "Knowledge base is already attached to this workspace"
    assert duplicate_attach_response.json()["detail"]["details"]["resource"] == "knowledge_base_attachment"
    assert missing_attachment_response.status_code == 404
    assert missing_attachment_response.json()["detail"]["code"] == "KB_ATTACHMENT_NOT_FOUND"
    assert missing_attachment_response.json()["detail"]["message"] == "Knowledge base attachment not found"
    assert missing_attachment_response.json()["detail"]["details"]["resource"] == "knowledge_base_attachment"


@pytest.mark.integration
def test_knowledge_base_file_api_returns_structured_invalid_file_type_error(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner")
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files"},
    )
    kb_id = create_kb_response.json()["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/malware.exe", "type": "file", "content": "boom"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_FILE_TYPE"
    assert response.json()["detail"]["message"] == "Unsupported file extension: .exe"
    assert response.json()["detail"]["details"]["path"] == "/malware.exe"


@pytest.mark.integration
def test_knowledge_base_api_localizes_error_message_by_request_language(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner-zh")
    _authenticate_as(client, monkeypatch, owner)
    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Files", "slug": "files-zh"},
    )
    kb_id = create_kb_response.json()["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/malware.exe", "type": "file", "content": "boom"},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "INVALID_FILE_TYPE"
    assert response.json()["detail"]["message"] == "不支援的檔案副檔名: .exe"


@pytest.mark.integration
def test_knowledge_base_generic_invalid_request_and_conflict_use_simple_messages(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner-generic")
    _authenticate_as(client, monkeypatch, owner)

    with patch(
        "app.routers.knowledge_bases.KnowledgeBaseService.create_kb",
        side_effect=ValueError("unexpected invalid request detail"),
    ):
        en_invalid_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert en_invalid_response.status_code == 400
        assert en_invalid_response.json()["detail"]["code"] == "KB_INVALID_REQUEST"
        assert en_invalid_response.json()["detail"]["message"] == "Invalid knowledge base request"

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.routers.knowledge_bases.KnowledgeBaseService.create_kb",
        side_effect=ValueError("unexpected invalid request detail"),
    ):
        zh_invalid_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert zh_invalid_response.status_code == 400
        assert zh_invalid_response.json()["detail"]["code"] == "KB_INVALID_REQUEST"
        assert zh_invalid_response.json()["detail"]["message"] == "無效的知識庫請求"

    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.routers.knowledge_bases.KnowledgeBaseService.create_kb",
        side_effect=KnowledgeBaseConflictError("unexpected conflict detail"),
    ):
        en_conflict_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert en_conflict_response.status_code == 409
        assert en_conflict_response.json()["detail"]["code"] == "KB_CONFLICT"
        assert en_conflict_response.json()["detail"]["message"] == "Knowledge base conflict"

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.routers.knowledge_bases.KnowledgeBaseService.create_kb",
        side_effect=KnowledgeBaseConflictError("unexpected conflict detail"),
    ):
        zh_conflict_response = client.post(
            "/api/v1/knowledge-bases",
            json={"name": "API Docs", "slug": "api-docs-generic"},
        )
        assert zh_conflict_response.status_code == 409
        assert zh_conflict_response.json()["detail"]["code"] == "KB_CONFLICT"
        assert zh_conflict_response.json()["detail"]["message"] == "知識庫發生衝突"


@pytest.mark.integration
def test_workspace_knowledge_base_error_translation_uses_code_instead_of_exception_message(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(username="workspace-owner-coded")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    client.headers.update({"Accept-Language": "en", "X-Language": "en"})
    with patch(
        "app.routers.workspaces.KnowledgeBaseAttachmentService.attach",
        side_effect=KnowledgeBaseConflictError("totally different conflict wording", code="KB_ALREADY_ATTACHED"),
    ):
        en_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": "kb-123", "mode": "rw"},
        )

    client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
    with patch(
        "app.routers.workspaces.KnowledgeBaseAttachmentService.attach",
        side_effect=KnowledgeBaseConflictError("totally different conflict wording", code="KB_ALREADY_ATTACHED"),
    ):
        zh_response = client.post(
            f"/api/v1/workspaces/{workspace_id}/knowledge-bases",
            json={"kbId": "kb-123", "mode": "rw"},
        )

    assert en_response.status_code == 409
    assert en_response.json()["detail"]["code"] == "KB_ALREADY_ATTACHED"
    assert en_response.json()["detail"]["message"] == "Knowledge base is already attached to this workspace"
    assert zh_response.status_code == 409
    assert zh_response.json()["detail"]["code"] == "KB_ALREADY_ATTACHED"
    assert zh_response.json()["detail"]["message"] == "知識庫已掛載到此工作區"


@pytest.mark.integration
def test_knowledge_base_file_api_returns_structured_kb_quota_error(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner")
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Quota Files", "slug": "quota-files", "quotaBytes": 4},
    )
    kb_id = create_kb_response.json()["id"]

    response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/files",
        data={"path": "/readme.md", "type": "file", "content": "hello"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "KB_QUOTA_EXCEEDED"
    assert response.json()["detail"]["message"] == "Knowledge base quota exceeded"
    assert response.json()["detail"]["details"]["quotaBytes"] == 4


@pytest.mark.integration
def test_knowledge_base_file_api_returns_structured_file_too_large_error(test_app, create_user, monkeypatch):
    client, _ = test_app
    owner = create_user(username="kb-owner")
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
            data={"path": "/too-large.md", "type": "file", "content": "hello"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "FILE_TOO_LARGE"
    assert response.json()["detail"]["message"] == "File size exceeds the limit"
    assert response.json()["detail"]["details"]["maxSize"] == 4


@pytest.mark.integration
def test_knowledge_base_attachment_api_returns_structured_conflict_errors(test_app, create_user, monkeypatch):
    client, session_factory = test_app
    owner = create_user(username="kb-owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    kb1 = client.post("/api/v1/knowledge-bases", json={"name": "Docs One", "slug": "docs-one"}).json()
    kb2 = client.post("/api/v1/knowledge-bases", json={"name": "Docs Two", "slug": "docs-two"}).json()

    first_attach_response = client.post(
        f"/api/v1/knowledge-bases/{kb1['id']}/attachments",
        json={"workspaceId": workspace_id, "mountAlias": "shared-docs", "mode": "rw"},
    )
    duplicate_attach_response = client.post(
        f"/api/v1/knowledge-bases/{kb1['id']}/attachments",
        json={"workspaceId": workspace_id, "mode": "rw"},
    )
    alias_conflict_response = client.post(
        f"/api/v1/knowledge-bases/{kb2['id']}/attachments",
        json={"workspaceId": workspace_id, "mountAlias": "shared-docs", "mode": "rw"},
    )

    assert first_attach_response.status_code == 201
    assert duplicate_attach_response.status_code == 409
    assert duplicate_attach_response.json()["detail"]["code"] == "KB_ALREADY_ATTACHED"
    assert duplicate_attach_response.json()["detail"]["message"] == "Knowledge base is already attached to this workspace"
    assert alias_conflict_response.status_code == 409
    assert alias_conflict_response.json()["detail"]["code"] == "KB_MOUNT_ALIAS_CONFLICT"
    assert alias_conflict_response.json()["detail"]["message"] == "Knowledge base mount alias already exists"


@pytest.mark.integration
def test_knowledge_base_delete_and_read_api_return_structured_in_use_and_tombstoned_errors(
    test_app, create_user, monkeypatch
):
    client, session_factory = test_app
    owner = create_user(username="kb-owner")
    workspace_id = _create_workspace(session_factory, owner_id=owner.id)
    _authenticate_as(client, monkeypatch, owner)

    create_kb_response = client.post(
        "/api/v1/knowledge-bases",
        json={"name": "Runtime Docs", "slug": "runtime-docs"},
    )
    kb_id = create_kb_response.json()["id"]

    attach_response = client.post(
        f"/api/v1/knowledge-bases/{kb_id}/attachments",
        json={"workspaceId": workspace_id, "mode": "rw"},
    )
    delete_conflict_response = client.delete(f"/api/v1/knowledge-bases/{kb_id}")
    force_delete_response = client.delete(f"/api/v1/knowledge-bases/{kb_id}", params={"force": "true"})
    read_tombstoned_response = client.get(f"/api/v1/knowledge-bases/{kb_id}")

    assert attach_response.status_code == 201
    assert delete_conflict_response.status_code == 409
    assert delete_conflict_response.json()["detail"]["code"] == "KB_IN_USE"
    assert delete_conflict_response.json()["detail"]["message"] == "Knowledge base is still attached to a workspace"
    assert force_delete_response.status_code == 200
    assert read_tombstoned_response.status_code == 404
    assert read_tombstoned_response.json()["detail"]["code"] == "KB_NOT_FOUND"
    assert read_tombstoned_response.json()["detail"]["message"] == "Knowledge base not found"
