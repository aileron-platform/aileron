from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.claude_code.common import DocumentScope

subagents_router_module = importlib.import_module("app.modules.cli_settings.subagents.router")
subagents_config_module = importlib.import_module("app.modules.cli_settings.subagents.config")


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
    app.include_router(
        subagents_router_module.create_subagents_router(subagents_config_module.SubagentTool.CLAUDE),
        prefix="/workspaces/{workspace_id}",
    )
    app.dependency_overrides[subagents_router_module.get_subagent_service] = lambda: service
    return TestClient(app)


def _gemini_client(service: FakeSubagentService) -> TestClient:
    app = FastAPI()
    app.include_router(
        subagents_router_module.create_subagents_router(subagents_config_module.SubagentTool.GEMINI),
        prefix="/workspaces/{workspace_id}",
    )
    app.dependency_overrides[subagents_router_module.get_gemini_subagent_service] = lambda: service
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
    assert response.json()["detail"]["message"] == "Subagents does not support LOCAL scope"


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


def test_gemini_subagents_router_happy_paths() -> None:
    client = _gemini_client(FakeSubagentService())

    assert client.get("/workspaces/ws-1/gemini/subagents", params={"scope": "project"}).status_code == 200
    assert client.get("/workspaces/ws-1/gemini/subagents/user").json()["scope"] == "user"

    response = client.post(
        "/workspaces/ws-1/gemini/subagents/project",
        json={"fileName": "helper.md", "content": "---\nname: helper\n---\n# helper"},
    )
    assert response.status_code == 201


def test_gemini_subagents_router_rejects_plugin_scope() -> None:
    client = _gemini_client(FakeSubagentService())

    response = client.get("/workspaces/ws-1/gemini/subagents/plugin")
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_SCOPE"
