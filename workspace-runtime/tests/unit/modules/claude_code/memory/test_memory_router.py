from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.revision import compute_revision

memory_router_module = importlib.import_module("app.modules.claude_code.memory.router")
EMPTY_REVISION = compute_revision("{}")
TODAY_REVISION = compute_revision("# Today")


class FakeMemoryService:
    def list_documents(self, workspace_id):
        return {
            "workspaceId": workspace_id,
            "revision": EMPTY_REVISION,
            "items": [
                {
                    "path": "notes/today.md",
                    "scope": "user",
                    "name": "today",
                    "description": None,
                    "size": "1KB",
                }
            ],
            "availableScopes": [
                {"scope": "project", "readOnly": False},
                {"scope": "user", "readOnly": False},
            ],
        }

    def get_document(self, workspace_id, scope, path):
        return {
            "revision": TODAY_REVISION,
            "resource": {
                "path": path,
                "scope": scope,
                "name": "today",
                "description": None,
                "size": "1KB",
                "content": "# Today",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        return {
            "revision": compute_revision(payload.content),
            "resource": {
                "path": payload.path,
                "scope": scope,
                "name": payload.path,
                "description": None,
                "size": "1KB",
                "content": payload.content,
            },
        }

    def update_document(self, workspace_id, scope, payload):
        return {
            "revision": compute_revision(payload.content),
            "resource": {
                "path": payload.path,
                "scope": scope,
                "name": payload.path,
                "description": None,
                "size": "1KB",
                "content": payload.content,
            },
        }

    def delete_document(self, workspace_id, scope, path, revision):
        return {
            "revision": EMPTY_REVISION,
            "resource": {"path": path, "scope": scope, "deleted": True},
        }


def _client(service: FakeMemoryService) -> TestClient:
    app = FastAPI()
    app.include_router(
        memory_router_module.router, prefix="/workspaces/{workspace_id}/claude-code"
    )
    app.dependency_overrides[memory_router_module.get_memory_service] = lambda: service
    return TestClient(app)


def test_memory_router_happy_paths() -> None:
    client = _client(FakeMemoryService())

    response = client.get("/workspaces/ws-1/claude-code/memory")
    assert response.status_code == 200
    assert response.json()["items"][0]["path"] == "notes/today.md"
    assert response.json()["availableScopes"] == [
        {"scope": "project", "readOnly": False},
        {"scope": "user", "readOnly": False},
    ]

    response = client.get(
        "/workspaces/ws-1/claude-code/memory/user/content",
        params={"path": "notes/today.md"},
    )
    assert response.status_code == 200
    assert response.json()["revision"] == TODAY_REVISION
    assert response.json()["resource"]["content"] == "# Today"

    response = client.post(
        "/workspaces/ws-1/claude-code/memory/user",
        json={"path": "notes/new", "content": "# New", "revision": EMPTY_REVISION},
    )
    assert response.status_code == 200
    assert response.json()["resource"]["path"] == "notes/new"

    response = client.put(
        "/workspaces/ws-1/claude-code/memory/user/content",
        json={
            "path": "notes/today.md",
            "content": "# Updated",
            "revision": TODAY_REVISION,
        },
    )
    assert response.status_code == 200
    assert response.json()["resource"]["content"] == "# Updated"

    response = client.delete(
        "/workspaces/ws-1/claude-code/memory/user/content",
        params={"path": "notes/today.md", "revision": TODAY_REVISION},
    )
    assert response.status_code == 200
    assert response.json()["resource"]["deleted"] is True
