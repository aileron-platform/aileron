from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

memory_router_module = importlib.import_module("app.modules.claude_code.memory.router")


class FakeMemoryService:
    def list_documents(self, workspace_id):
        return {
            "workspaceId": workspace_id,
            "documents": [{"fileName": "today.md", "name": "today", "description": None, "size": "1KB"}],
        }

    def get_document(self, workspace_id, file_name):
        return {
            "workspaceId": workspace_id,
            "document": {
                "fileName": file_name,
                "name": "today",
                "description": None,
                "size": "1KB",
                "content": "# Today",
            },
        }

    def create_document(self, workspace_id, payload):
        return {
            "workspaceId": workspace_id,
            "document": {
                "fileName": payload.file_name,
                "name": payload.file_name,
                "description": None,
                "size": "1KB",
                "content": payload.content,
            },
        }

    def update_document(self, workspace_id, file_name, payload):
        return {
            "workspaceId": workspace_id,
            "document": {
                "fileName": file_name,
                "name": file_name,
                "description": None,
                "size": "1KB",
                "content": payload.content,
            },
        }

    def delete_document(self, workspace_id, file_name):
        return {"workspaceId": workspace_id, "fileName": file_name, "deleted": True}


def _client(service: FakeMemoryService) -> TestClient:
    app = FastAPI()
    app.include_router(memory_router_module.router, prefix="/workspaces/{workspace_id}/claude-code")
    app.dependency_overrides[memory_router_module.get_memory_service] = lambda: service
    return TestClient(app)


def test_memory_router_happy_paths() -> None:
    client = _client(FakeMemoryService())

    response = client.get("/workspaces/ws-1/claude-code/memory")
    assert response.status_code == 200
    assert response.json()["documents"][0]["fileName"] == "today.md"

    response = client.get("/workspaces/ws-1/claude-code/memory/today.md")
    assert response.status_code == 200
    assert response.json()["document"]["content"] == "# Today"

    response = client.post(
        "/workspaces/ws-1/claude-code/memory",
        json={"fileName": "new", "content": "# New"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["fileName"] == "new"

    response = client.put(
        "/workspaces/ws-1/claude-code/memory/today.md",
        json={"content": "# Updated"},
    )
    assert response.status_code == 200
    assert response.json()["document"]["content"] == "# Updated"

    response = client.delete("/workspaces/ws-1/claude-code/memory/today.md")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
