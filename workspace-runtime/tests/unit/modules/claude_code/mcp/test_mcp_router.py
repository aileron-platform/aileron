"""MCP Router 單元測試 - 補充覆蓋率"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException, status

from app.modules.claude_code.mcp.router import (
    list_servers,
    get_scope,
    get_server,
    create_server,
    update_server,
    delete_server,
    toggle_server_status,
    export_server,
    import_servers,
)
from app.modules.claude_code.mcp.service import (
    McpScopeNotSupportedError,
    McpServerNotFoundError,
    McpServerAlreadyExistsError,
)
from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.mcp.models import McpServerUpdateRequest


class MockMcpService:
    """Mock MCP 服務"""

    def __init__(self):
        self.raise_error = None

    def list_servers(self, workspace_id, scope):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")

        return {
            "servers": [],
            "workspace_id": workspace_id
        }

    def get_scope(self, workspace_id, scope):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")

        return {
            "scope": scope.value,
            "servers": []
        }

    def get_server(self, workspace_id, scope, server_name):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_not_found":
            raise McpServerNotFoundError(f"Server not found: {server_name}")

        return {
            "scope": scope.value,
            "server_name": server_name
        }

    def create_servers(self, workspace_id, scope, payload):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_exists":
            raise McpServerAlreadyExistsError("Server already exists")
        if self.raise_error == "invalid_payload":
            raise ValueError("Invalid payload")

        return {
            "scope": scope.value,
            "created": True
        }

    def update_server(self, workspace_id, scope, server_name, payload):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_not_found":
            raise McpServerNotFoundError(f"Server not found: {server_name}")
        if self.raise_error == "server_exists":
            raise McpServerAlreadyExistsError("Server already exists")
        if self.raise_error == "invalid_payload":
            raise ValueError("Invalid payload")

        return {
            "scope": scope.value,
            "server_name": server_name,
            "updated": True
        }

    def delete_server(self, workspace_id, scope, server_name):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_not_found":
            raise McpServerNotFoundError(f"Server not found: {server_name}")

        return {
            "deleted": True,
            "server_name": server_name
        }

    def toggle_server_status(self, workspace_id, scope, server_name, enabled):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_not_found":
            raise McpServerNotFoundError(f"Server not found: {server_name}")

        return {
            "server_name": server_name,
            "enabled": enabled
        }

    def export_server(self, workspace_id, scope, server_name):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "server_not_found":
            raise McpServerNotFoundError(f"Server not found: {server_name}")

        return {
            "server_name": server_name,
            "config": {}
        }

    def import_servers_from_file(self, workspace_id, payload):
        if self.raise_error == "scope_not_supported":
            raise McpScopeNotSupportedError("Scope not supported")
        if self.raise_error == "invalid_payload":
            raise ValueError("Invalid payload")

        return {
            "imported": True
        }


@pytest.mark.asyncio
class TestListServers:
    """測試列出 MCP 伺服器"""

    async def test_list_servers_scope_not_supported(self):
        """測試不支援的範圍"""
        service = MockMcpService()
        service.raise_error = "scope_not_supported"

        with pytest.raises(HTTPException) as exc_info:
            await list_servers(
                workspace_id="ws_123",
                scope=DocumentScope.PROJECT,
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestGetScope:
    """測試獲取指定範圍的 MCP 伺服器"""

    async def test_get_scope_not_supported(self):
        """測試不支援的範圍"""
        service = MockMcpService()
        service.raise_error = "scope_not_supported"

        with pytest.raises(HTTPException) as exc_info:
            await get_scope(
                scope=DocumentScope.PROJECT,
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestGetServer:
    """測試獲取單一 MCP 伺服器"""

    async def test_get_server_not_found(self):
        """測試伺服器不存在"""
        service = MockMcpService()
        service.raise_error = "server_not_found"

        with pytest.raises(HTTPException) as exc_info:
            await get_server(
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestUpdateServer:
    """測試更新 MCP 伺服器"""

    async def test_update_server_not_found(self):
        """測試伺服器不存在"""
        service = MockMcpService()
        service.raise_error = "server_not_found"

        payload = McpServerUpdateRequest(
            mcpServers={"test-server": {"command": "node"}}
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_server(
                payload=payload,
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_server_invalid_payload(self):
        """測試無效的 payload"""
        service = MockMcpService()
        service.raise_error = "invalid_payload"

        payload = McpServerUpdateRequest(
            mcpServers={"test-server": {"command": "node"}}
        )

        with pytest.raises(HTTPException) as exc_info:
            await update_server(
                payload=payload,
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
class TestDeleteServer:
    """測試刪除 MCP 伺服器"""

    async def test_delete_server_not_found(self):
        """測試伺服器不存在"""
        service = MockMcpService()
        service.raise_error = "server_not_found"

        with pytest.raises(HTTPException) as exc_info:
            await delete_server(
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestToggleServerStatus:
    """測試切換 MCP 伺服器狀態"""

    async def test_toggle_status_not_found(self):
        """測試伺服器不存在"""
        service = MockMcpService()
        service.raise_error = "server_not_found"

        with pytest.raises(HTTPException) as exc_info:
            await toggle_server_status(
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                enabled=True,
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestExportServer:
    """測試匯出 MCP 伺服器"""

    async def test_export_server_not_found(self):
        """測試伺服器不存在"""
        service = MockMcpService()
        service.raise_error = "server_not_found"

        with pytest.raises(HTTPException) as exc_info:
            await export_server(
                scope=DocumentScope.PROJECT,
                server_name="test-server",
                workspace_id="ws_123",
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestImportServers:
    """測試匯入 MCP 設定"""

    async def test_import_servers_invalid_payload(self):
        """測試無效的 payload"""
        from unittest.mock import AsyncMock

        service = MockMcpService()
        service.raise_error = "invalid_payload"

        # 建立 mock 檔案
        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=b'{"invalid": "json"}')

        with pytest.raises(HTTPException) as exc_info:
            await import_servers(
                workspace_id="ws_123",
                scope=DocumentScope.PROJECT,
                file=mock_file,
                overwrite=False,
                service=service
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
