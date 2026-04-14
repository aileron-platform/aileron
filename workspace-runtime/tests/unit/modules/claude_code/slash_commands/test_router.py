from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.claude_code.common import DocumentScope

slash_router_module = importlib.import_module("app.modules.claude_code.slash_commands.router")


class FakeSlashCommandService:
    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scopes": [
                {
                    "scope": scope or "project",
                    "documents": [],
                }
            ],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "documents": [{"fileName": "hello.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, file_name):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "document": {
                "fileName": file_name,
                "scope": scope,
                "size": "1KB",
                "content": "# hello",
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
                "namespace": payload.namespace,
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
                "namespace": payload.namespace,
                "description": payload.description,
            },
        }

    def delete_document(self, workspace_id, scope, file_name):
        return None


def _client(service: FakeSlashCommandService) -> TestClient:
    app = FastAPI()
    app.include_router(slash_router_module.router, prefix="/workspaces/{workspace_id}/claude-code")
    app.dependency_overrides[slash_router_module.get_slash_command_service] = lambda: service
    return TestClient(app)


def test_slash_commands_router_happy_paths() -> None:
    client = _client(FakeSlashCommandService())

    response = client.get("/workspaces/ws-1/claude-code/slash-commands", params={"scope": "project"})
    assert response.status_code == 200
    assert response.json()["workspaceId"] == "ws-1"

    response = client.get("/workspaces/ws-1/claude-code/slash-commands/project")
    assert response.status_code == 200
    assert response.json()["scope"] == "project"

    response = client.get("/workspaces/ws-1/claude-code/slash-commands/project/hello.md")
    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "hello.md"

    response = client.post(
        "/workspaces/ws-1/claude-code/slash-commands/project",
        json={"fileName": "new.md", "content": "# new", "namespace": "team", "description": "desc"},
    )
    assert response.status_code == 201
    assert response.json()["document"]["namespace"] == "team"

    response = client.put(
        "/workspaces/ws-1/claude-code/slash-commands/project/hello.md",
        json={"content": "# updated", "namespace": "ops", "description": "changed"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["description"] == "changed"

    response = client.delete("/workspaces/ws-1/claude-code/slash-commands/project/hello.md")
    assert response.status_code == 200
    assert response.json() == {
        "workspaceId": "ws-1",
        "scope": "project",
        "fileName": "hello.md",
        "deleted": True,
    }


def test_slash_commands_router_rejects_local_scope() -> None:
    client = _client(FakeSlashCommandService())

    response = client.get(f"/workspaces/ws-1/claude-code/slash-commands/{DocumentScope.LOCAL.value}")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"

    response = client.post(
        f"/workspaces/ws-1/claude-code/slash-commands/{DocumentScope.LOCAL.value}",
        json={"fileName": "bad.md", "content": "# bad"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Slash Commands 不支援 LOCAL scope"


def test_slash_commands_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeSlashCommandService())
    monkeypatch.setattr(
        slash_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("plugin is read-only")),
    )

    response = client.put(
        "/workspaces/ws-1/claude-code/slash-commands/plugin/hello.md",
        json={"content": "# no"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "error": "SCOPE_READ_ONLY",
        "message": "plugin is read-only",
    }
