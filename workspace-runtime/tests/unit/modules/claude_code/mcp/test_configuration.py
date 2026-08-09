"""MCP Service unit tests"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.claude_code.mcp.configuration import McpService, McpServerEntry
from app.modules.claude_code.mcp.models import (
    McpServerConfig,
    McpServerCreateRequest,
    McpServerUpdateRequest,
    McpTransportType,
)
from app.modules.claude_code.documents import DocumentScope


def _revision_for_servers(
    servers: dict[str, dict],
    disabled_servers: list[str] | None = None,
) -> str:
    content = {
        "mcpServers": servers,
        "disabledMcpServers": sorted(disabled_servers or []),
    }
    return compute_revision(json.dumps(content, sort_keys=True, separators=(",", ":")))


EMPTY_REVISION = _revision_for_servers({})


@pytest.fixture
def mcp_service():
    """MCP service fixture."""
    return McpService()


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace directory structure."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    project_root = workspace_root / ".claude"
    project_root.mkdir(parents=True, exist_ok=True)

    return workspace_root, project_root


class TestListServers:
    """Test listing MCP servers functionality."""

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_list_servers_all(self, mock_read_json, mcp_service, tmp_path):
        """Test listing all scopes MCP servers."""
        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        # Act
        result = mcp_service.list_servers(workspace_id, None)

        # Assert
        assert result is not None
        assert result.workspaceId == workspace_id
        assert len(result.scopes) >= 0
        assert all(scope.revision == EMPTY_REVISION for scope in result.scopes)

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_list_servers_project_only(self, mock_read_json, mcp_service, tmp_path):
        """Test listing only project scope MCP servers."""
        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        # Act
        result = mcp_service.list_servers(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert len(result.scopes) >= 0


class TestGetScope:
    """Test getting specific scope MCP servers."""

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_get_scope_success(self, mock_read_json, mcp_service, tmp_path):
        """Test successful scope retrieval."""
        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "test-command"}}
        }

        # Act
        result = mcp_service.get_scope(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert result.workspaceId == workspace_id
        assert result.scope == DocumentScope.PROJECT


class TestCreateServers:
    """Test creating MCP servers."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_create_servers_success(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test successful server creation."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_read_json.return_value = {"mcpServers": {}}

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="test-command"
        )
        payload = McpServerCreateRequest(
            revision=EMPTY_REVISION, mcpServers={"test-server": server_config}
        )

        # Act
        result = mcp_service.create_servers(workspace_id, scope, payload)

        # Assert
        assert result is not None
        assert result.revision == _revision_for_servers(
            {"test-server": {"type": "stdio", "command": "test-command"}}
        )
        assert mock_write_json.called

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_create_rejects_stale_revision(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test stale revision rejects creation."""
        workspace_id = "test-workspace"
        mock_read_json.return_value = {
            "mcpServers": {
                "existing": {
                    "type": "stdio",
                    "command": "existing-command",
                }
            }
        }
        payload = McpServerCreateRequest(
            revision=EMPTY_REVISION,
            mcpServers={
                "test-server": McpServerConfig(
                    type=McpTransportType.STDIO,
                    command="test-command",
                )
            },
        )

        with pytest.raises(HTTPException) as exc_info:
            mcp_service.create_servers(workspace_id, DocumentScope.PROJECT, payload)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"


class TestUpdateServer:
    """Test updating MCP server."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_update_server_success(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test successful server update."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        server_name = "test-server"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "old-command"}}
        }

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="new-command"
        )

        update_request = McpServerUpdateRequest(
            revision=_revision_for_servers(
                {"test-server": {"type": "stdio", "command": "old-command"}}
            ),
            mcpServers={server_name: server_config},
        )

        # Act
        result = mcp_service.update_server(
            workspace_id, scope, server_name, update_request
        )

        # Assert
        assert result is not None
        assert mock_write_json.called


class TestDeleteServer:
    """Test deleting MCP server."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_delete_server_success(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test successful server deletion."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        server_name = "test-server"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "test-command"}}
        }

        # Act
        result = mcp_service.delete_server(
            workspace_id,
            scope,
            server_name,
            _revision_for_servers(
                {"test-server": {"type": "stdio", "command": "test-command"}}
            ),
        )

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert result.scope == scope
        assert mock_write_json.called


class TestExportServer:
    """Test exporting MCP server."""

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_export_server_success(self, mock_read_json, mcp_service, tmp_path):
        """Test successful server export."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        server_name = "test-server"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "test-command"}}
        }

        # Act
        result = mcp_service.export_server(workspace_id, scope, server_name)

        # Assert
        assert result is not None


class TestToggleServerStatus:
    """Test toggling MCP server status."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_toggle_server_status_success(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test successful server status toggle."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        server_name = "test-server"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "test-command"}}
        }

        # Act
        result = mcp_service.toggle_server_status(
            workspace_id,
            scope,
            server_name,
            False,
            _revision_for_servers(
                {"test-server": {"type": "stdio", "command": "test-command"}}
            ),
        )

        # Assert
        assert result is not None
        assert mock_write_json.called


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = McpService()

        # Assert
        assert service is not None


class TestGetServer:
    """Test getting single MCP server."""

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_get_server_success(self, mock_read_json, mcp_service, tmp_path):
        """Test successfully getting single server."""
        # Arrange
        workspace_id = "test-workspace"
        server_name = "test-server"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "test-command"}}
        }

        # Act
        result = mcp_service.get_server(
            workspace_id, DocumentScope.PROJECT, server_name
        )

        # Assert
        assert result is not None
        assert server_name in result.mcpServers

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_get_server_not_found(self, mock_read_json, mcp_service, tmp_path):
        """Test getting non-existent server."""
        from app.modules.claude_code.mcp.configuration import McpServerNotFoundError

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        # Act & Assert
        with pytest.raises(McpServerNotFoundError):
            mcp_service.get_server(workspace_id, DocumentScope.PROJECT, "nonexistent")


class TestImportServers:
    """Test importing MCP servers."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_import_servers_create_new(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test importing new servers."""
        from app.modules.claude_code.mcp.models import McpImportRequest

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="test-command"
        )
        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            revision=EMPTY_REVISION,
            mcpServers={"test-server": server_config},
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert result is not None
        assert "test-server" in result.created
        assert len(result.updated) == 0
        assert len(result.skipped) == 0

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_import_servers_overwrite(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test importing and overwriting existing servers."""
        from app.modules.claude_code.mcp.models import McpImportRequest

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "old-command"}}
        }

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="new-command"
        )
        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            revision=_revision_for_servers(
                {"test-server": {"type": "stdio", "command": "old-command"}}
            ),
            mcpServers={"test-server": server_config},
            overwrite=True,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert result is not None
        assert "test-server" in result.updated
        assert len(result.created) == 0

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_import_servers_skip_existing(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test skipping existing servers during import."""
        from app.modules.claude_code.mcp.models import McpImportRequest

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {
            "mcpServers": {"test-server": {"type": "stdio", "command": "old-command"}}
        }

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="new-command"
        )
        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            revision=_revision_for_servers(
                {"test-server": {"type": "stdio", "command": "old-command"}}
            ),
            mcpServers={"test-server": server_config},
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert result is not None
        assert "test-server" in result.skipped
        assert len(result.created) == 0
        assert len(result.updated) == 0


class TestImportServersFromFile:
    """Test importing MCP servers from file."""

    @patch("app.modules.claude_code.mcp.configuration.write_json_file")
    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_import_from_file_success(
        self, mock_read_json, mock_write_json, mcp_service, tmp_path
    ):
        """Test successful import from file."""
        from app.modules.claude_code.mcp.models import McpImportUploadRequest

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        file_content = json.dumps(
            {
                "mcpServers": {
                    "test-server": {"type": "stdio", "command": "test-command"}
                }
            }
        ).encode("utf-8")

        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            revision=EMPTY_REVISION,
            file=file_content,
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers_from_file(workspace_id, payload)

        # Assert
        assert result is not None
        assert "test-server" in result.created

    def test_import_from_file_invalid_json(self, mcp_service):
        """Test importing invalid JSON file."""
        from app.modules.claude_code.mcp.models import McpImportUploadRequest

        # Arrange
        workspace_id = "test-workspace"
        file_content = b"invalid json{"

        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            revision=EMPTY_REVISION,
            file=file_content,
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid JSON format"):
            mcp_service.import_servers_from_file(workspace_id, payload)

    def test_import_from_file_missing_mcpservers(self, mcp_service):
        """Test importing file missing mcpServers field."""
        from app.modules.claude_code.mcp.models import McpImportUploadRequest

        # Arrange
        workspace_id = "test-workspace"
        file_content = json.dumps({"other": "data"}).encode("utf-8")

        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            revision=EMPTY_REVISION,
            file=file_content,
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="missing 'mcpServers' field"):
            mcp_service.import_servers_from_file(workspace_id, payload)


class TestErrorHandling:
    """Test error handling."""

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_create_duplicate_server(self, mock_read_json, mcp_service, tmp_path):
        """Test creating duplicate server."""
        from app.modules.claude_code.mcp.configuration import (
            McpServerAlreadyExistsError,
        )

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {
            "mcpServers": {
                "test-server": {"type": "stdio", "command": "existing-command"}
            }
        }

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="new-command"
        )
        payload = McpServerCreateRequest(
            revision=_revision_for_servers(
                {"test-server": {"type": "stdio", "command": "existing-command"}}
            ),
            mcpServers={"test-server": server_config},
        )

        # Act & Assert
        with pytest.raises(McpServerAlreadyExistsError):
            mcp_service.create_servers(workspace_id, DocumentScope.PROJECT, payload)

    @patch("app.modules.claude_code.mcp.configuration.read_json_file")
    def test_update_nonexistent_server(self, mock_read_json, mcp_service, tmp_path):
        """Test updating non-existent server."""
        from app.modules.claude_code.mcp.configuration import McpServerNotFoundError

        # Arrange
        workspace_id = "test-workspace"
        mock_read_json.return_value = {"mcpServers": {}}

        server_config = McpServerConfig(
            type=McpTransportType.STDIO, command="new-command"
        )
        payload = McpServerUpdateRequest(
            revision=EMPTY_REVISION,
            mcpServers={"nonexistent": server_config},
        )

        # Act & Assert
        with pytest.raises(McpServerNotFoundError):
            mcp_service.update_server(
                workspace_id, DocumentScope.PROJECT, "nonexistent", payload
            )

    def test_create_empty_payload(self, mcp_service):
        """Test creating empty payload."""
        # Arrange
        from pydantic import ValidationError

        # Act & Assert - Pydantic validates when creating object
        with pytest.raises(ValidationError):
            McpServerCreateRequest(revision=EMPTY_REVISION, mcpServers={})


class TestMcpServerEntry:
    """Test McpServerEntry data class."""

    def test_to_runtime(self):
        """Test converting to runtime model."""
        # Arrange
        config = McpServerConfig(type=McpTransportType.STDIO, command="test-command")
        entry = McpServerEntry(name="test-server", config=config)

        # Act
        runtime = entry.to_runtime(enabled=True)

        # Assert
        assert runtime.enabled is True
        assert runtime.type == McpTransportType.STDIO
        assert runtime.command == "test-command"

    def test_to_storage(self):
        """Test converting to storage format."""
        # Arrange
        config = McpServerConfig(type=McpTransportType.STDIO, command="test-command")
        entry = McpServerEntry(name="test-server", config=config)

        # Act
        storage = entry.to_storage()

        # Assert
        assert isinstance(storage, dict)
        assert "type" in storage
        assert "command" in storage
