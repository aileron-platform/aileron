from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

output_styles_router_module = importlib.import_module("app.modules.claude_code.output_styles.router")


class FakeOutputStyleService:
    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scopes": [{"scope": scope or "project", "documents": []}],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "documents": [{"fileName": "calm.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, file_name):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
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
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "name": payload.name,
                "description": payload.description,
            },
        }

    def delete_document(self, workspace_id, scope, file_name):
        return None


def _client(service: FakeOutputStyleService) -> TestClient:
    app = FastAPI()
    app.include_router(output_styles_router_module.router, prefix="/workspaces/{workspace_id}/claude-code")
    app.dependency_overrides[output_styles_router_module.get_output_style_service] = lambda: service
    return TestClient(app)


def test_output_styles_router_happy_paths() -> None:
    client = _client(FakeOutputStyleService())

    assert client.get("/workspaces/ws-1/claude-code/output-styles", params={"scope": "project"}).status_code == 200
    assert client.get("/workspaces/ws-1/claude-code/output-styles/project").json()["scope"] == "project"
    assert client.get("/workspaces/ws-1/claude-code/output-styles/project/calm.md").json()["document"]["name"] == "Calm"

    response = client.post(
        "/workspaces/ws-1/claude-code/output-styles/project",
        json={"fileName": "new.md", "content": "# new", "name": "Sharp", "description": "desc"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["description"] == "desc"

    response = client.put(
        "/workspaces/ws-1/claude-code/output-styles/project/calm.md",
        json={"content": "# updated", "name": "Warm", "description": "changed"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["name"] == "Warm"

    response = client.delete("/workspaces/ws-1/claude-code/output-styles/project/calm.md")
    assert response.status_code == 200
    assert response.json()["fileName"] == "calm.md"


def test_output_styles_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeOutputStyleService())
    monkeypatch.setattr(
        output_styles_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("user scope is read-only")),
    )

    response = client.post(
        "/workspaces/ws-1/claude-code/output-styles/user",
        json={"fileName": "blocked.md", "content": "# blocked"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "error": "SCOPE_READ_ONLY",
        "message": "user scope is read-only",
    }
