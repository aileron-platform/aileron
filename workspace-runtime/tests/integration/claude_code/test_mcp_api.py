"""Claude Code API 測試案例 - MCP 伺服器"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.mcp.dependencies import get_mcp_service
from app.modules.claude_code.mcp.models import (
    McpImportResponse,
    McpScopeResponse,
    McpScopeServers,
    McpServerCollectionResponse,
    McpServerCreateRequest,
    McpServerDeleteResponse,
    McpServerExportResponse,
    McpServerUpdateRequest,
)
from app.modules.claude_code.mcp.service import (
    McpScopeNotSupportedError,
    McpServerAlreadyExistsError,
    McpServerNotFoundError,
)

from .helpers import WORKSPACE_ID, override_dependency


@dataclass
class StubMcpService:
    list_result: Optional[McpServerCollectionResponse] = None
    scope_result: Optional[McpScopeResponse] = None
    server_result: Optional[McpScopeResponse] = None
    create_result: Optional[McpScopeResponse] = None
    update_result: Optional[McpScopeResponse] = None
    delete_result: Optional[McpServerDeleteResponse] = None
    toggle_result: Optional[McpScopeResponse] = None
    export_result: Optional[McpServerExportResponse] = None
    import_result: Optional[McpImportResponse] = None
    list_error: Optional[Exception] = None
    scope_error: Optional[Exception] = None
    server_error: Optional[Exception] = None
    create_error: Optional[Exception] = None
    update_error: Optional[Exception] = None
    delete_error: Optional[Exception] = None
    toggle_error: Optional[Exception] = None
    export_error: Optional[Exception] = None
    import_error: Optional[Exception] = None
    created_payloads: list[tuple[str, DocumentScope, McpServerCreateRequest]] = field(
        default_factory=list
    )
    updated_payloads: list[
        tuple[str, DocumentScope, str, McpServerUpdateRequest]
    ] = field(default_factory=list)
    toggled: list[tuple[str, DocumentScope, str, bool]] = field(default_factory=list)
    imports: list[tuple[str, bytes, bool]] = field(default_factory=list)

    def list_servers(
        self, workspace_id: str, scope: DocumentScope | None
    ) -> McpServerCollectionResponse:
        if self.list_error:
            raise self.list_error
        assert self.list_result is not None
        return self.list_result

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> McpScopeResponse:
        if self.scope_error:
            raise self.scope_error
        assert self.scope_result is not None
        return self.scope_result

    def get_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpScopeResponse:
        if self.server_error:
            raise self.server_error
        assert self.server_result is not None
        return self.server_result

    def create_servers(
        self, workspace_id: str, scope: DocumentScope, payload: McpServerCreateRequest
    ) -> McpScopeResponse:
        self.created_payloads.append((workspace_id, scope, payload))
        if self.create_error:
            raise self.create_error
        assert self.create_result is not None
        return self.create_result

    def update_server(
        self,
        workspace_id: str,
        scope: DocumentScope,
        server_name: str,
        payload: McpServerUpdateRequest,
    ) -> McpScopeResponse:
        self.updated_payloads.append((workspace_id, scope, server_name, payload))
        if self.update_error:
            raise self.update_error
        assert self.update_result is not None
        return self.update_result

    def delete_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpServerDeleteResponse:
        if self.delete_error:
            raise self.delete_error
        assert self.delete_result is not None
        return self.delete_result

    def toggle_server_status(
        self,
        workspace_id: str,
        scope: DocumentScope,
        server_name: str,
        enabled: bool,
    ) -> McpScopeResponse:
        self.toggled.append((workspace_id, scope, server_name, enabled))
        if self.toggle_error:
            raise self.toggle_error
        assert self.toggle_result is not None
        return self.toggle_result

    def export_server(
        self, workspace_id: str, scope: DocumentScope, server_name: str
    ) -> McpServerExportResponse:
        if self.export_error:
            raise self.export_error
        assert self.export_result is not None
        return self.export_result

    def import_servers_from_file(
        self, workspace_id: str, payload: Any
    ) -> McpImportResponse:
        self.imports.append((workspace_id, payload.file, payload.overwrite))
        if self.import_error:
            raise self.import_error
        assert self.import_result is not None
        return self.import_result


def _mcp_scope(scope: DocumentScope, servers: dict[str, Any]) -> McpScopeResponse:
    return McpScopeResponse(workspaceId=WORKSPACE_ID, scope=scope, mcpServers=servers)


def test_mcp_001_list_all_scopes(client):
    service = StubMcpService(
        list_result=McpServerCollectionResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                McpScopeServers(
                    scope=DocumentScope.PROJECT,
                    mcpServers={"cli": {"type": "stdio", "command": "echo", "enabled": True}},
                )
            ],
        )
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers"
        )

    assert response.status_code == 200
    scopes = response.json()["scopes"]
    assert scopes[0]["scope"] == "project"


def test_mcp_002_list_filtered_scope(client):
    service = StubMcpService(
        list_result=McpServerCollectionResponse(
            workspaceId=WORKSPACE_ID,
            scopes=[
                McpScopeServers(
                    scope=DocumentScope.USER,
                    mcpServers={"desktop": {"type": "http", "url": "http://localhost:8080", "enabled": True}},
                )
            ],
        )
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers",
            params={"scope": "user"},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["scopes"]) == 1
    assert data["scopes"][0]["scope"] == "user"


def test_mcp_003_get_scope_success(client):
    service = StubMcpService(
        scope_result=_mcp_scope(DocumentScope.PROJECT, {"cli": {"type": "stdio", "command": "echo"}})
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project"
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"


def test_mcp_004_scope_not_supported(client):
    # 測試在 PLUGIN scope 嘗試建立伺服器會失敗
    service = StubMcpService(create_error=McpScopeNotSupportedError("plugin"))

    payload = {
        "mcpServers": {"test": {"type": "stdio", "command": "echo"}}
    }

    with override_dependency(get_mcp_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/plugin",
            json=payload,
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SCOPE_NOT_SUPPORTED"


def test_mcp_005_get_server_success(client):
    service = StubMcpService(
        server_result=_mcp_scope(DocumentScope.PROJECT, {"cli": {"type": "stdio", "command": "echo"}})
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli"
        )

    assert response.status_code == 200
    assert response.json()["mcpServers"]["cli"]["type"] == "stdio"


def test_mcp_006_get_server_missing(client):
    service = StubMcpService(server_error=McpServerNotFoundError("cli"))

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli"
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "SERVER_NOT_FOUND"


def test_mcp_007_create_server_success(client):
    service = StubMcpService(
        create_result=_mcp_scope(DocumentScope.PROJECT, {"new": {"type": "stdio", "command": "cmd"}})
    )

    payload = {
        "mcpServers": {"new": {"type": "stdio", "command": "cmd"}}
    }

    with override_dependency(get_mcp_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project",
            json=payload,
        )

    assert response.status_code == 200
    assert service.created_payloads


def test_mcp_008_create_duplicate(client):
    service = StubMcpService(
        create_error=McpServerAlreadyExistsError("exists")
    )

    payload = {
        "mcpServers": {"dup": {"type": "stdio", "command": "cmd"}}
    }

    with override_dependency(get_mcp_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project",
            json=payload,
        )

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "409_DUPLICATE_NAME"


def test_mcp_009_create_invalid_payload(client):
    service = StubMcpService(create_error=ValueError("bad"))

    payload = {"mcpServers": {"bad": {"type": "stdio", "command": "echo"}}}

    with override_dependency(get_mcp_service, lambda: service):
        response = client.post(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project",
            json=payload,
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "400_INVALID_PAYLOAD"


def test_mcp_010_update_server_success(client):
    service = StubMcpService(
        update_result=_mcp_scope(DocumentScope.PROJECT, {"cli": {"type": "stdio", "command": "cmd"}})
    )

    payload = {
        "mcpServers": {"cli": {"type": "stdio", "command": "cmd"}}
    }

    with override_dependency(get_mcp_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli",
            json=payload,
        )

    assert response.status_code == 200
    assert service.updated_payloads


def test_mcp_011_update_conflict(client):
    service = StubMcpService(
        update_error=McpServerAlreadyExistsError("conflict")
    )

    payload = {
        "mcpServers": {"cli": {"type": "stdio", "command": "cmd"}}
    }

    with override_dependency(get_mcp_service, lambda: service):
        response = client.put(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli",
            json=payload,
        )

    assert response.status_code == 409


def test_mcp_012_delete_success(client):
    service = StubMcpService(
        delete_result=McpServerDeleteResponse(
            workspaceId=WORKSPACE_ID, scope=DocumentScope.PROJECT
        )
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli"
        )

    assert response.status_code == 200
    assert response.json()["scope"] == "project"


def test_mcp_013_delete_missing(client):
    service = StubMcpService(delete_error=McpServerNotFoundError("cli"))

    with override_dependency(get_mcp_service, lambda: service):
        response = client.delete(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli"
        )

    assert response.status_code == 404


def test_mcp_014_toggle_status(client):
    service = StubMcpService(
        toggle_result=_mcp_scope(DocumentScope.PROJECT, {"cli": {"type": "stdio", "command": "echo", "enabled": False}})
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.patch(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli/toggle",
            params={"enabled": False},
        )

    assert response.status_code == 200
    assert service.toggled[0][-1] is False


def test_mcp_015_export_server(client):
    service = StubMcpService(
        export_result=McpServerExportResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.PROJECT,
            mcpServers={"cli": {"type": "stdio", "command": "echo"}},
        )
    )

    with override_dependency(get_mcp_service, lambda: service):
        response = client.get(
            f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-servers/project/cli/export"
        )

    assert response.status_code == 200
    assert "cli" in response.json()["mcpServers"]


def test_mcp_016_import_success(client, tmp_path):
    service = StubMcpService(
        import_result=McpImportResponse(
            workspaceId=WORKSPACE_ID,
            scope=DocumentScope.USER,
            created=["cli"],
            updated=[],
            skipped=[],
        )
    )

    file_path = tmp_path / "config.json"
    file_path.write_text("{}", encoding="utf-8")

    with override_dependency(get_mcp_service, lambda: service):
        with file_path.open("rb") as fp:
            response = client.post(
                f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-import",
                files={"file": ("config.json", fp, "application/json")},
                data={"scope": "user", "overwrite": "true"},
            )

    assert response.status_code == 200
    assert response.json()["created"] == ["cli"]
    assert service.imports


def test_mcp_017_import_invalid_payload(client, tmp_path):
    service = StubMcpService(import_error=ValueError("invalid"))

    file_path = tmp_path / "broken.json"
    file_path.write_text("{}", encoding="utf-8")

    with override_dependency(get_mcp_service, lambda: service):
        with file_path.open("rb") as fp:
            response = client.post(
                f"/api/v1/workspaces/{WORKSPACE_ID}/claude-code/mcp-import",
                files={"file": ("broken.json", fp, "application/json")},
                data={"scope": "user"},
            )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "400_INVALID_PAYLOAD"
