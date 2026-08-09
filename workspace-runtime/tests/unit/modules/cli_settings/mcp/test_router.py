from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.revision import compute_revision
from app.modules.cli_settings.mcp.models import (
    CliMcpImportResponse,
    CliMcpScope,
    CliMcpScopeResponse,
    CliMcpScopeServers,
    CliMcpServerCollectionResponse,
    CliMcpServerConfig,
    CliMcpServerDeleteResponse,
    CliMcpServerExportResponse,
    CliMcpServerRuntime,
    CliMcpTransportType,
)
from app.modules.cli_settings.mcp.router import create_mcp_router
from app.modules.cli_settings.mcp.configuration import (
    CliMcpScopeNotSupportedError,
    CliMcpServerAlreadyExistsError,
    CliMcpServerNotFoundError,
    CliMcpToggleNotSupportedError,
    McpTool,
)


def _empty_revision() -> str:
    return compute_revision("{}")


class FakeService:
    def __init__(self) -> None:
        runtime = CliMcpServerRuntime(
            type=CliMcpTransportType.STDIO,
            command="npx",
            args=["-y", "demo"],
            enabled=True,
        )
        self.scope_response = CliMcpScopeResponse(
            workspaceId="ws-1",
            scope=CliMcpScope.PROJECT,
            revision=_empty_revision(),
            mcpServers={"demo": runtime},
        )
        self.collection_response = CliMcpServerCollectionResponse(
            workspaceId="ws-1",
            scopes=[
                CliMcpScopeServers(
                    scope=CliMcpScope.PROJECT,
                    revision=_empty_revision(),
                    mcpServers={"demo": runtime},
                ),
            ],
        )
        self.export_response = CliMcpServerExportResponse(
            workspaceId="ws-1",
            scope=CliMcpScope.PROJECT,
            mcpServers={
                "demo": CliMcpServerConfig(
                    type=CliMcpTransportType.STDIO,
                    command="npx",
                    args=["-y", "demo"],
                )
            },
        )
        self.delete_response = CliMcpServerDeleteResponse(
            workspaceId="ws-1",
            scope=CliMcpScope.PROJECT,
            revision=_empty_revision(),
        )
        self.import_response = CliMcpImportResponse(
            workspaceId="ws-1",
            scope=CliMcpScope.PROJECT,
            revision=_empty_revision(),
            created=["demo"],
            updated=[],
            skipped=[],
        )

    def list_servers(self, workspace_id, scope):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        return self.collection_response

    def get_scope(self, workspace_id, scope):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        return self.scope_response

    def get_server(self, workspace_id, scope, server_name):
        if server_name == "missing":
            raise CliMcpServerNotFoundError(server_name)
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        return self.scope_response

    def create_servers(self, workspace_id, scope, payload):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if workspace_id == "dup":
            raise CliMcpServerAlreadyExistsError("duplicate")
        if workspace_id == "invalid":
            raise ValueError("bad payload")
        return self.scope_response

    def update_server(self, workspace_id, scope, server_name, payload):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if server_name == "missing":
            raise CliMcpServerNotFoundError(server_name)
        if workspace_id == "dup":
            raise CliMcpServerAlreadyExistsError("duplicate")
        if workspace_id == "invalid":
            raise ValueError("bad payload")
        return self.scope_response

    def delete_server(self, workspace_id, scope, server_name, revision):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if server_name == "missing":
            raise CliMcpServerNotFoundError(server_name)
        return self.delete_response

    def toggle_server_status(self, workspace_id, scope, server_name, enabled, revision):
        if workspace_id == "toggle-error":
            raise CliMcpToggleNotSupportedError("toggle unsupported")
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if server_name == "missing":
            raise CliMcpServerNotFoundError(server_name)
        return self.scope_response

    def export_server(self, workspace_id, scope, server_name):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if server_name == "missing":
            raise CliMcpServerNotFoundError(server_name)
        return self.export_response

    def import_servers_from_file(self, workspace_id, payload):
        if workspace_id == "scope-error":
            raise CliMcpScopeNotSupportedError("scope bad")
        if workspace_id == "invalid":
            raise ValueError("bad payload")
        return self.import_response


def _client() -> TestClient:
    app = FastAPI()
    router = create_mcp_router(McpTool.CODEX)
    app.include_router(router, prefix="/workspaces/{workspace_id}/cli-settings")
    return TestClient(app)


def test_mcp_router_happy_paths(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(
        "app.modules.cli_settings.mcp.router.make_mcp_service_dependency",
        lambda tool: (lambda: service),
    )

    client = _client()

    assert (
        client.get("/workspaces/ws-1/cli-settings/codex/mcp-servers").status_code == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project"
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/demo"
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/demo",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 200
    )
    assert (
        client.delete(
            f"/workspaces/ws-1/cli-settings/codex/mcp-servers/project/demo?revision={_empty_revision()}"
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/workspaces/ws-1/cli-settings/codex/mcp-servers/project/demo/toggle?enabled=true&revision={_empty_revision()}"
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/demo/export"
        ).status_code
        == 200
    )

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/mcp-import",
        data={"scope": "project", "overwrite": "true", "revision": _empty_revision()},
        files={"file": ("mcp.json", b'{"mcpServers": {}}', "application/json")},
    )
    assert response.status_code == 200
    assert response.json()["created"] == ["demo"]


def test_mcp_router_error_paths(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(
        "app.modules.cli_settings.mcp.router.make_mcp_service_dependency",
        lambda tool: (lambda: service),
    )
    client = _client()

    scope_response = client.get(
        "/workspaces/scope-error/cli-settings/codex/mcp-servers"
    )
    assert scope_response.status_code == 404
    assert scope_response.json()["detail"] == {
        "errorCode": "SCOPE_NOT_SUPPORTED",
        "message": "scope bad",
    }
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/missing"
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/workspaces/dup/cli-settings/codex/mcp-servers/project",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/workspaces/invalid/cli-settings/codex/mcp-servers/project",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/missing",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/workspaces/dup/cli-settings/codex/mcp-servers/project/demo",
            json={
                "revision": _empty_revision(),
                "mcpServers": {"demo": {"type": "stdio", "command": "npx"}},
            },
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/workspaces/toggle-error/cli-settings/codex/mcp-servers/project/demo/toggle?enabled=true&revision={_empty_revision()}"
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/workspaces/ws-1/cli-settings/codex/mcp-servers/project/missing/export"
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/workspaces/invalid/cli-settings/codex/mcp-import",
            data={
                "scope": "project",
                "overwrite": "false",
                "revision": _empty_revision(),
            },
            files={"file": ("mcp.json", b"{}", "application/json")},
        ).status_code
        == 400
    )


def test_mcp_router_requires_revision_for_mutations(monkeypatch) -> None:
    service = FakeService()
    monkeypatch.setattr(
        "app.modules.cli_settings.mcp.router.make_mcp_service_dependency",
        lambda tool: (lambda: service),
    )
    client = _client()

    response = client.post(
        "/workspaces/ws-1/cli-settings/codex/mcp-servers/project",
        json={"mcpServers": {"demo": {"type": "stdio", "command": "npx"}}},
    )

    assert response.status_code == 422
