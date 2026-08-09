from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.revision import compute_revision
from app.modules.claude_code.documents import DocumentScope

slash_router_module = importlib.import_module(
    "app.modules.claude_code.slash_commands.router"
)
EMPTY_REVISION = compute_revision("{}")


class FakeSlashCommandService:
    def list_scopes(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "items": [],
            "availableScopes": [{"scope": scope or "project", "readOnly": False}],
        }

    def get_scope(self, workspace_id, scope):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "documents": [{"path": "team/hello.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, path):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": path,
                "scope": scope,
                "size": "1KB",
                "content": "# hello",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "description": payload.description,
            },
        }

    def update_document(self, workspace_id, scope, payload):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": EMPTY_REVISION,
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "description": payload.description,
            },
        }

    def delete_document(self, workspace_id, scope, path, revision):
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "path": path,
            "revision": EMPTY_REVISION,
            "deleted": True,
        }


def _client(service: FakeSlashCommandService) -> TestClient:
    app = FastAPI()
    app.include_router(
        slash_router_module.router, prefix="/workspaces/{workspace_id}/claude-code"
    )
    app.dependency_overrides[slash_router_module.get_slash_command_service] = (
        lambda: service
    )
    return TestClient(app)


def test_slash_commands_router_happy_paths() -> None:
    client = _client(FakeSlashCommandService())

    response = client.get(
        "/workspaces/ws-1/claude-code/slash-commands", params={"scope": "project"}
    )
    assert response.status_code == 200
    assert response.json()["workspaceId"] == "ws-1"

    response = client.get("/workspaces/ws-1/claude-code/slash-commands/project")
    assert response.status_code == 200
    assert response.json()["scope"] == "project"

    response = client.get(
        "/workspaces/ws-1/claude-code/slash-commands/project/content",
        params={"path": "team/hello.md"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["path"] == "team/hello.md"

    response = client.post(
        "/workspaces/ws-1/claude-code/slash-commands/project",
        json={
            "path": "team/new.md",
            "content": "# new",
            "description": "desc",
            "revision": EMPTY_REVISION,
        },
    )
    assert response.status_code == 201
    assert response.json()["document"]["path"] == "team/new.md"

    response = client.put(
        "/workspaces/ws-1/claude-code/slash-commands/project/content",
        json={
            "path": "team/hello.md",
            "content": "# updated",
            "description": "changed",
            "revision": EMPTY_REVISION,
        },
    )
    assert response.status_code == 200
    assert response.json()["document"]["description"] == "changed"

    response = client.delete(
        "/workspaces/ws-1/claude-code/slash-commands/project/content",
        params={"path": "team/hello.md", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 200
    assert response.json() == {
        "workspaceId": "ws-1",
        "scope": "project",
        "path": "team/hello.md",
        "revision": EMPTY_REVISION,
        "deleted": True,
    }


def test_slash_commands_router_rejects_local_scope() -> None:
    client = _client(FakeSlashCommandService())

    response = client.get(
        f"/workspaces/ws-1/claude-code/slash-commands/{DocumentScope.LOCAL.value}"
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"

    response = client.post(
        f"/workspaces/ws-1/claude-code/slash-commands/{DocumentScope.LOCAL.value}",
        json={"path": "bad.md", "content": "# bad", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]["message"]
        == "Slash Commands does not support LOCAL scope"
    )


def test_slash_commands_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeSlashCommandService())
    monkeypatch.setattr(
        slash_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("plugin is read-only")),
    )

    response = client.put(
        "/workspaces/ws-1/claude-code/slash-commands/plugin/content",
        json={"path": "hello.md", "content": "# no", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == {
        "errorCode": "SCOPE_READ_ONLY",
        "message": "plugin is read-only",
    }


def test_slash_commands_router_requires_revision_for_mutations() -> None:
    client = _client(FakeSlashCommandService())

    response = client.post(
        "/workspaces/ws-1/claude-code/slash-commands/project",
        json={"path": "new.md", "content": "# new"},
    )

    assert response.status_code == 422
