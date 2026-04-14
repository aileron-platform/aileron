from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.claude_code.common import DocumentScope

subagents_router_module = importlib.import_module("app.modules.claude_code.subagents.router")


class FakeSubagentService:
    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scopes": [{"scope": scope or "project", "documents": []}],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "documents": [{"fileName": "reviewer.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, file_name):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "content": "# subagent",
                "name": "Reviewer",
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


def _client(service: FakeSubagentService) -> TestClient:
    app = FastAPI()
    app.include_router(subagents_router_module.router, prefix="/workspaces/{workspace_id}/claude-code")
    app.dependency_overrides[subagents_router_module.get_subagent_service] = lambda: service
    return TestClient(app)


def test_subagents_router_happy_paths() -> None:
    client = _client(FakeSubagentService())

    assert client.get("/workspaces/ws-1/claude-code/subagents", params={"scope": "project"}).status_code == 200
    assert client.get("/workspaces/ws-1/claude-code/subagents/project").json()["scope"] == "project"
    assert client.get("/workspaces/ws-1/claude-code/subagents/project/reviewer.md").json()["document"]["name"] == "Reviewer"

    response = client.post(
        "/workspaces/ws-1/claude-code/subagents/project",
        json={"fileName": "new.md", "content": "# new", "name": "Helper", "description": "desc"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["name"] == "Helper"

    response = client.put(
        "/workspaces/ws-1/claude-code/subagents/project/reviewer.md",
        json={"content": "# updated", "name": "Planner", "description": "changed"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["description"] == "changed"

    response = client.delete("/workspaces/ws-1/claude-code/subagents/project/reviewer.md")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_subagents_router_rejects_local_scope() -> None:
    client = _client(FakeSubagentService())

    response = client.get(f"/workspaces/ws-1/claude-code/subagents/{DocumentScope.LOCAL.value}")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"

    response = client.delete(f"/workspaces/ws-1/claude-code/subagents/{DocumentScope.LOCAL.value}/reviewer.md")
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Subagents 不支援 LOCAL scope"


def test_subagents_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeSubagentService())
    monkeypatch.setattr(
        subagents_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("plugin is read-only")),
    )

    response = client.post(
        "/workspaces/ws-1/claude-code/subagents/plugin",
        json={"fileName": "reviewer.md", "content": "# blocked"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "SCOPE_READ_ONLY"
