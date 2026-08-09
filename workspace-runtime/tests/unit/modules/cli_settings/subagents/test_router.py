from __future__ import annotations

import importlib

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient

from app.modules.claude_code.documents import DocumentScope

subagents_router_module = importlib.import_module(
    "app.modules.cli_settings.subagents.router"
)
subagents_config_module = importlib.import_module(
    "app.modules.cli_settings.subagents.config"
)


class FakeSubagentService:
    def __init__(self) -> None:
        self.calls = []

    def list_scopes(self, workspace_id, scope):
        self.calls.append(("list_scopes", workspace_id, scope))
        return {
            "workspaceId": workspace_id,
            "items": [],
            "availableScopes": [{"scope": scope or "project", "readOnly": False}],
        }

    def get_scope(self, workspace_id, scope):
        self.calls.append(("get_scope", workspace_id, scope))
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "scope-revision",
            "documents": [{"path": "team/reviewer.md", "scope": scope, "size": "1KB"}],
        }

    def get_document(self, workspace_id, scope, path):
        self.calls.append(("get_document", workspace_id, scope, path))
        if path == "missing.md":
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": "missing.md"},
            )
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "path": path,
                "scope": scope,
                "size": "1KB",
                "content": "# subagent",
                "name": "Reviewer",
            },
        }

    def create_document(self, workspace_id, scope, payload):
        self.calls.append(("create_document", workspace_id, scope, payload.path))
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "name": payload.name,
                "description": payload.description,
            },
        }

    def update_document(self, workspace_id, scope, payload):
        self.calls.append(("update_document", workspace_id, scope, payload.path))
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "revision": "document-revision",
            "document": {
                "path": payload.path,
                "scope": scope,
                "size": "1KB",
                "content": payload.content,
                "name": payload.name,
                "description": payload.description,
            },
        }

    def delete_document(self, workspace_id, scope, path, *, revision):
        self.calls.append(("delete_document", workspace_id, scope, path, revision))
        return {
            "workspaceId": workspace_id,
            "scope": scope,
            "path": path,
            "revision": "scope-revision-after-delete",
            "deleted": True,
        }


def _client(service: FakeSubagentService, tool=None, monkeypatch=None) -> TestClient:
    selected_tool = tool or subagents_config_module.SubagentTool.CLAUDE
    if selected_tool != subagents_config_module.SubagentTool.CLAUDE:
        assert monkeypatch is not None
        monkeypatch.setattr(
            subagents_router_module,
            "get_subagent_service",
            lambda _tool=selected_tool: service,
        )
    app = FastAPI()
    app.include_router(
        subagents_router_module.create_subagents_router(selected_tool),
        prefix="/workspaces/{workspace_id}",
    )
    if selected_tool == subagents_config_module.SubagentTool.CLAUDE:
        app.dependency_overrides[
            subagents_router_module.get_claude_subagent_service
        ] = lambda: service
    return TestClient(app)


def test_subagents_router_happy_paths() -> None:
    client = _client(FakeSubagentService())

    assert (
        client.get(
            "/workspaces/ws-1/claude-code/subagents", params={"scope": "project"}
        ).status_code
        == 200
    )
    assert (
        client.get("/workspaces/ws-1/claude-code/subagents/project").json()["scope"]
        == "project"
    )
    assert (
        client.get(
            "/workspaces/ws-1/claude-code/subagents/project/content",
            params={"path": "team/reviewer.md"},
        ).json()["document"]["name"]
        == "Reviewer"
    )

    response = client.post(
        "/workspaces/ws-1/claude-code/subagents/project",
        json={
            "path": "team/new.md",
            "content": "# new",
            "name": "Helper",
            "description": "desc",
            "revision": "scope-revision",
        },
    )
    assert response.status_code == 201
    assert response.json()["document"]["name"] == "Helper"

    response = client.put(
        "/workspaces/ws-1/claude-code/subagents/project/content",
        json={
            "path": "team/reviewer.md",
            "content": "# updated",
            "name": "Planner",
            "description": "changed",
            "revision": "document-revision",
        },
    )
    assert response.status_code == 200
    assert response.json()["document"]["description"] == "changed"

    response = client.delete(
        "/workspaces/ws-1/claude-code/subagents/project/content",
        params={"path": "team/reviewer.md", "revision": "document-revision"},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["revision"] == "scope-revision-after-delete"


def test_subagents_router_requires_revision_for_mutations() -> None:
    client = _client(FakeSubagentService())

    create_response = client.post(
        "/workspaces/ws-1/claude-code/subagents/project",
        json={
            "path": "new.md",
            "content": "# new",
            "name": "Helper",
            "description": "desc",
        },
    )
    update_response = client.put(
        "/workspaces/ws-1/claude-code/subagents/project/content",
        json={
            "path": "reviewer.md",
            "content": "# updated",
            "name": "Planner",
            "description": "changed",
        },
    )
    delete_response = client.delete(
        "/workspaces/ws-1/claude-code/subagents/project/content",
        params={"path": "reviewer.md"},
    )

    assert create_response.status_code == 422
    assert update_response.status_code == 422
    assert delete_response.status_code == 422


def test_subagents_router_does_not_expose_service_tool_query_parameter() -> None:
    app = FastAPI()
    app.include_router(
        subagents_router_module.create_subagents_router(
            subagents_config_module.SubagentTool.CLAUDE
        ),
        prefix="/workspaces/{workspace_id}",
    )

    parameters = app.openapi()["paths"][
        "/workspaces/{workspace_id}/claude-code/subagents"
    ]["get"].get("parameters", [])

    assert {parameter["name"] for parameter in parameters} == {"workspace_id", "scope"}


def test_opencode_subagents_router_happy_paths(monkeypatch) -> None:
    service = FakeSubagentService()
    client = _client(
        service, subagents_config_module.SubagentTool.OPENCODE, monkeypatch
    )

    assert (
        client.get(
            "/workspaces/ws-1/opencode/subagents", params={"scope": "project"}
        ).status_code
        == 200
    )
    assert (
        client.get("/workspaces/ws-1/opencode/subagents/user").json()["scope"] == "user"
    )
    assert (
        client.get(
            "/workspaces/ws-1/opencode/subagents/project/content",
            params={"path": "team/reviewer.md"},
        ).json()["document"]["name"]
        == "Reviewer"
    )

    response = client.post(
        "/workspaces/ws-1/opencode/subagents/project",
        json={
            "path": "team/new.md",
            "content": "---\nname: Helper\ndescription: desc\n---\n\n# new",
            "name": "Helper",
            "description": "desc",
            "revision": "scope-revision",
        },
    )
    assert response.status_code == 201

    response = client.put(
        "/workspaces/ws-1/opencode/subagents/user/content",
        json={
            "path": "team/reviewer.md",
            "content": "---\nname: Planner\ndescription: changed\n---\n\n# updated",
            "revision": "document-revision",
        },
    )
    assert response.status_code == 200

    response = client.delete(
        "/workspaces/ws-1/opencode/subagents/project/content",
        params={"path": "team/reviewer.md", "revision": "document-revision"},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True

    assert service.calls == [
        ("list_scopes", "ws-1", DocumentScope.PROJECT),
        ("get_scope", "ws-1", DocumentScope.USER),
        ("get_document", "ws-1", DocumentScope.PROJECT, "team/reviewer.md"),
        ("create_document", "ws-1", DocumentScope.PROJECT, "team/new.md"),
        ("update_document", "ws-1", DocumentScope.USER, "team/reviewer.md"),
        (
            "delete_document",
            "ws-1",
            DocumentScope.PROJECT,
            "team/reviewer.md",
            "document-revision",
        ),
    ]


def test_opencode_subagents_router_rejects_local_and_plugin_scopes(monkeypatch) -> None:
    client = _client(
        FakeSubagentService(),
        subagents_config_module.SubagentTool.OPENCODE,
        monkeypatch,
    )

    response = client.get(
        f"/workspaces/ws-1/opencode/subagents/{DocumentScope.LOCAL.value}"
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"

    response = client.get(
        f"/workspaces/ws-1/opencode/subagents/{DocumentScope.PLUGIN.value}"
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]["message"]
        == "Subagents does not support PLUGIN scope"
    )


def test_subagents_router_rejects_local_scope() -> None:
    client = _client(FakeSubagentService())

    response = client.get(
        f"/workspaces/ws-1/claude-code/subagents/{DocumentScope.LOCAL.value}"
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_SCOPE"

    response = client.delete(
        f"/workspaces/ws-1/claude-code/subagents/{DocumentScope.LOCAL.value}/content",
        params={"path": "reviewer.md", "revision": "document-revision"},
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]["message"] == "Subagents does not support LOCAL scope"
    )


def test_subagents_router_rejects_read_only_scope(monkeypatch) -> None:
    client = _client(FakeSubagentService())
    monkeypatch.setattr(
        subagents_router_module,
        "check_scope_writable",
        lambda scope: (_ for _ in ()).throw(ValueError("plugin is read-only")),
    )

    response = client.post(
        "/workspaces/ws-1/claude-code/subagents/plugin",
        json={
            "path": "reviewer.md",
            "content": "# blocked",
            "revision": "scope-revision",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["errorCode"] == "SCOPE_READ_ONLY"


def test_subagents_router_maps_service_error_envelope() -> None:
    client = _client(FakeSubagentService())

    response = client.get(
        "/workspaces/ws-1/claude-code/subagents/project/content",
        params={"path": "missing.md"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "errorCode": "404_NOT_FOUND",
        "message": "missing.md",
    }
