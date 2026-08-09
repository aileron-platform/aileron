from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

output_styles_router_module = importlib.import_module(
    "app.modules.claude_code.output_styles.router"
)


class FakeOutputStyleService:
    def list_scopes(self, workspace_id, scope, *, plugin_id=None):
        _ = plugin_id
        return {
            "workspaceId": workspace_id,
            "scopes": [
                {
                    "scope": scope or "project",
                    "revision": "scope-revision",
                    "documents": [],
                }
            ],
        }

    def get_scope(self, workspace_id, scope, *, plugin_id=None):
        _ = plugin_id
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "scope-revision",
            "documents": [{"fileName": "calm.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, file_name, *, plugin_id=None):
        _ = plugin_id
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "content": "# style",
                "name": "Calm",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "fileName": payload.file_name,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "name": payload.name,
                "description": payload.description,
            },
        }

    def update_document(self, workspace_id, scope, file_name, payload):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "name": payload.name,
                "description": payload.description,
            },
        }

    def delete_document(self, workspace_id, scope, file_name, *, revision):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "fileName": file_name,
            "revision": "scope-revision-after-delete",
            "deleted": True,
        }


def _client(service: FakeOutputStyleService) -> TestClient:
    app = FastAPI()
    app.include_router(
        output_styles_router_module.router,
        prefix="/workspaces/{workspace_id}/claude-code",
    )
    app.dependency_overrides[output_styles_router_module.get_output_style_service] = (
        lambda: service
    )
    return TestClient(app)


def test_output_styles_router_happy_paths() -> None:
    client = _client(FakeOutputStyleService())

    assert (
        client.get(
            "/workspaces/ws-1/claude-code/output-styles", params={"scope": "project"}
        ).status_code
        == 200
    )
    assert (
        client.get("/workspaces/ws-1/claude-code/output-styles/project").json()["scope"]
        == "project"
    )
    assert (
        client.get("/workspaces/ws-1/claude-code/output-styles/project/calm.md").json()[
            "document"
        ]["name"]
        == "Calm"
    )
    nested_plugin = client.get(
        (
            "/workspaces/ws-1/claude-code/output-styles/plugin/"
            "output-styles/a/style.md"
        ),
        params={"pluginId": "demo@registry"},
    )
    assert nested_plugin.status_code == 200
    assert nested_plugin.json()["document"]["fileName"] == "output-styles/a/style.md"

    response = client.post(
        "/workspaces/ws-1/claude-code/output-styles/project",
        json={
            "fileName": "new.md",
            "content": "# new",
            "name": "Sharp",
            "description": "desc",
            "revision": "scope-revision",
        },
    )
    assert response.status_code == 201
    assert response.json()["document"]["description"] == "desc"

    response = client.put(
        "/workspaces/ws-1/claude-code/output-styles/project/calm.md",
        json={
            "content": "# updated",
            "name": "Warm",
            "description": "changed",
            "revision": "document-revision",
        },
    )
    assert response.status_code == 200
    assert response.json()["document"]["name"] == "Warm"

    response = client.delete(
        "/workspaces/ws-1/claude-code/output-styles/project/calm.md",
        params={"revision": "document-revision"},
    )
    assert response.status_code == 200
    assert response.json()["fileName"] == "calm.md"
    assert response.json()["revision"] == "scope-revision-after-delete"


def test_output_styles_router_requires_revision_for_mutations() -> None:
    client = _client(FakeOutputStyleService())

    create_response = client.post(
        "/workspaces/ws-1/claude-code/output-styles/project",
        json={
            "fileName": "new.md",
            "content": "# new",
            "name": "Sharp",
            "description": "desc",
        },
    )
    update_response = client.put(
        "/workspaces/ws-1/claude-code/output-styles/project/calm.md",
        json={"content": "# updated", "name": "Warm", "description": "changed"},
    )
    delete_response = client.delete(
        "/workspaces/ws-1/claude-code/output-styles/project/calm.md"
    )

    assert create_response.status_code == 422
    assert update_response.status_code == 422
    assert delete_response.status_code == 422


def test_output_styles_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeOutputStyleService())
    monkeypatch.setattr(
        output_styles_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("user scope is read-only")),
    )

    response = client.post(
        "/workspaces/ws-1/claude-code/output-styles/user",
        json={
            "fileName": "blocked.md",
            "content": "# blocked",
            "revision": "scope-revision",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "errorCode": "SCOPE_READ_ONLY",
        "message": "user scope is read-only",
    }
