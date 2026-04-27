"""CLI MCP Service unit tests

Test Gemini, Codex, OpenCode MCP CRUD, import/export, toggle functionality.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

from app.modules.cli_settings.mcp.config_strategies import (
    JsonConfigStrategy,
    TomlConfigStrategy,
)
from app.modules.cli_settings.mcp.models import (
    CliMcpImportRequest,
    CliMcpImportUploadRequest,
    CliMcpScope,
    CliMcpServerConfig,
    CliMcpServerCreateRequest,
    CliMcpServerUpdateRequest,
    CliMcpTransportType,
)
from app.modules.cli_settings.mcp.service import (
    CliMcpServerAlreadyExistsError,
    CliMcpServerNotFoundError,
    CliMcpService,
    CliMcpToggleNotSupportedError,
    CliMcpToolConfig,
    McpTool,
)


# === Fixtures =============================================================


def _make_json_config(
    tmp_path: Path,
    tool: McpTool,
    servers_key: str,
    supports_toggle: bool = True,
) -> CliMcpToolConfig:
    """Create test config using JSON strategy"""
    project_dir = tmp_path / "workspace"
    project_dir.mkdir(exist_ok=True)
    return CliMcpToolConfig(
        tool=tool,
        project_file="settings.json",
        user_file_path=tmp_path / "user" / "settings.json",
        servers_key=servers_key,
        strategy=JsonConfigStrategy(),
        supports_toggle=supports_toggle,
    )


def _make_toml_config(
    tmp_path: Path,
    tool: McpTool = McpTool.CODEX,
    servers_key: str = "mcp_servers",
) -> CliMcpToolConfig:
    """Create test config using TOML strategy"""
    project_dir = tmp_path / "workspace"
    project_dir.mkdir(exist_ok=True)
    return CliMcpToolConfig(
        tool=tool,
        project_file="config.toml",
        user_file_path=tmp_path / "user" / "config.toml",
        servers_key=servers_key,
        strategy=TomlConfigStrategy(),
        supports_toggle=True,
    )


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_toml(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(tomli_w.dumps(data).encode("utf-8"))


def _read_toml(path: Path) -> Dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def workspace_path(tmp_path: Path, monkeypatch):
    """Set workspace path to tmp_path/workspace"""
    ws_path = tmp_path / "workspace"
    ws_path.mkdir(exist_ok=True)
    monkeypatch.setattr(
        "app.modules.cli_settings.mcp.service.get_workspace_path",
        lambda: str(ws_path),
    )
    return ws_path


# === Gemini Tests ==================================================


class TestGeminiMcp:
    """Gemini MCP tests (JSON, mcpServers, no toggle)"""

    def _make_service(self, tmp_path: Path) -> CliMcpService:
        config = _make_json_config(
            tmp_path, McpTool.GEMINI, "mcpServers", supports_toggle=False
        )
        return CliMcpService(config)

    def test_list_empty(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        result = svc.list_servers("ws1")
        assert len(result.scopes) == 2
        assert all(len(s.mcpServers) == 0 for s in result.scopes)

    def test_create_and_list(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        payload = CliMcpServerCreateRequest(
            mcpServers={
                "my-server": CliMcpServerConfig(
                    type=CliMcpTransportType.STDIO,
                    command="npx",
                    args=["-y", "my-mcp"],
                )
            }
        )
        result = svc.create_servers("ws1", CliMcpScope.PROJECT, payload)
        assert "my-server" in result.mcpServers
        assert result.mcpServers["my-server"].command == "npx"

        # Verify list
        listed = svc.list_servers("ws1", CliMcpScope.PROJECT)
        assert "my-server" in listed.scopes[0].mcpServers

    def test_update_server(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "srv": CliMcpServerConfig(command="old-cmd")
                }
            ),
        )
        result = svc.update_server(
            "ws1",
            CliMcpScope.PROJECT,
            "srv",
            CliMcpServerUpdateRequest(
                mcpServers={
                    "srv": CliMcpServerConfig(command="new-cmd")
                }
            ),
        )
        assert result.mcpServers["srv"].command == "new-cmd"

    def test_delete_server(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "srv": CliMcpServerConfig(command="cmd")
                }
            ),
        )
        svc.delete_server("ws1", CliMcpScope.PROJECT, "srv")
        result = svc.list_servers("ws1", CliMcpScope.PROJECT)
        assert len(result.scopes[0].mcpServers) == 0

    def test_delete_not_found(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        with pytest.raises(CliMcpServerNotFoundError):
            svc.delete_server("ws1", CliMcpScope.PROJECT, "nonexistent")

    def test_create_duplicate(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        payload = CliMcpServerCreateRequest(
            mcpServers={"srv": CliMcpServerConfig(command="cmd")}
        )
        svc.create_servers("ws1", CliMcpScope.PROJECT, payload)
        with pytest.raises(CliMcpServerAlreadyExistsError):
            svc.create_servers("ws1", CliMcpScope.PROJECT, payload)

    def test_toggle_not_supported(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"srv": CliMcpServerConfig(command="cmd")}
            ),
        )
        with pytest.raises(CliMcpToggleNotSupportedError):
            svc.toggle_server_status("ws1", CliMcpScope.PROJECT, "srv", False)

    def test_enabled_always_true(self, tmp_path: Path, workspace_path: Path):
        """Gemini does not support toggle, enabled is always True"""
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"srv": CliMcpServerConfig(command="cmd")}
            ),
        )
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "srv")
        assert result.mcpServers["srv"].enabled is True

    def test_export_import(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "srv": CliMcpServerConfig(
                        command="npx",
                        args=["-y", "mcp-tool"],
                        env={"KEY": "val"},
                    )
                }
            ),
        )
        exported = svc.export_server("ws1", CliMcpScope.PROJECT, "srv")
        assert "srv" in exported.mcpServers
        assert exported.mcpServers["srv"].command == "npx"


# === Codex Tests (TOML) ==================================================


class TestCodexMcp:
    """Codex MCP tests (TOML, mcp_servers, supports toggle)"""

    def _make_service(self, tmp_path: Path) -> CliMcpService:
        config = _make_toml_config(tmp_path)
        return CliMcpService(config)

    def test_crud_with_toml(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        # Create
        result = svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "codex-srv": CliMcpServerConfig(
                        command="npx",
                        args=["-y", "codex-mcp"],
                    )
                }
            ),
        )
        assert "codex-srv" in result.mcpServers

        # Verify TOML file is written correctly
        toml_path = workspace_path / "config.toml"
        assert toml_path.exists()
        data = _read_toml(toml_path)
        assert "mcp_servers" in data
        assert "codex-srv" in data["mcp_servers"]
        # Codex natively does not store type field
        assert "type" not in data["mcp_servers"]["codex-srv"]

    def test_toml_roundtrip(self, tmp_path: Path, workspace_path: Path):
        """TOML roundtrip test: write and read back should be consistent"""
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "srv1": CliMcpServerConfig(
                        command="node",
                        args=["server.js"],
                        env={"PORT": "3000"},
                    )
                }
            ),
        )
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "srv1")
        assert result.mcpServers["srv1"].command == "node"
        assert result.mcpServers["srv1"].args == ["server.js"]
        assert result.mcpServers["srv1"].env == {"PORT": "3000"}

    def test_toggle(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"srv": CliMcpServerConfig(command="cmd")}
            ),
        )
        # Disable
        result = svc.toggle_server_status("ws1", CliMcpScope.PROJECT, "srv", False)
        assert result.mcpServers["srv"].enabled is False

        # Enable
        result = svc.toggle_server_status("ws1", CliMcpScope.PROJECT, "srv", True)
        assert result.mcpServers["srv"].enabled is True

    def test_codex_http_server(self, tmp_path: Path, workspace_path: Path):
        "Codex HTTP server: determine based on url presence"""
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "remote": CliMcpServerConfig(
                        type=CliMcpTransportType.HTTP,
                        url="http://localhost:8080/mcp",
                    )
                }
            ),
        )
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "remote")
        assert result.mcpServers["remote"].type == CliMcpTransportType.HTTP
        assert result.mcpServers["remote"].url == "http://localhost:8080/mcp"

    def test_user_scope(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.USER,
            CliMcpServerCreateRequest(
                mcpServers={"user-srv": CliMcpServerConfig(command="cmd")}
            ),
        )
        result = svc.list_servers("ws1", CliMcpScope.USER)
        assert "user-srv" in result.scopes[0].mcpServers

        # Verify write location
        user_path = tmp_path / "user" / "config.toml"
        assert user_path.exists()


# === OpenCode tests =========================================================


class TestOpenCodeMcp:
    "OpenCode MCP tests (JSON, mcp, supports toggle, format conversion)"""

    def _make_service(self, tmp_path: Path) -> CliMcpService:
        config = _make_json_config(
            tmp_path, McpTool.OPENCODE, "mcp", supports_toggle=True
        )
        return CliMcpService(config)

    def test_opencode_stdio_format_conversion(
        self, tmp_path: Path, workspace_path: Path
    ):
        """OpenCode stdio: command list <-> command + args"""
        svc = self._make_service(tmp_path)

        # Create from unified format
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "local-srv": CliMcpServerConfig(
                        type=CliMcpTransportType.STDIO,
                        command="npx",
                        args=["-y", "my-mcp-server"],
                        env={"DEBUG": "true"},
                    )
                }
            ),
        )

        # Verify native format
        json_path = workspace_path / "settings.json"
        data = _read_json(json_path)
        native = data["mcp"]["local-srv"]
        assert native["type"] == "local"
        assert native["command"] == ["npx", "-y", "my-mcp-server"]
        assert native["environment"] == {"DEBUG": "true"}

        # Read back unified format
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "local-srv")
        srv = result.mcpServers["local-srv"]
        assert srv.type == CliMcpTransportType.STDIO
        assert srv.command == "npx"
        assert srv.args == ["-y", "my-mcp-server"]
        assert srv.env == {"DEBUG": "true"}

    def test_opencode_remote_format_conversion(
        self, tmp_path: Path, workspace_path: Path
    ):
        """OpenCode remote: type remote <-> http"""
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "remote-srv": CliMcpServerConfig(
                        type=CliMcpTransportType.HTTP,
                        url="http://localhost:9090",
                    )
                }
            ),
        )

        # Verify native format
        json_path = workspace_path / "settings.json"
        data = _read_json(json_path)
        native = data["mcp"]["remote-srv"]
        assert native["type"] == "remote"
        assert native["url"] == "http://localhost:9090"

        # Read back unified format
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "remote-srv")
        srv = result.mcpServers["remote-srv"]
        assert srv.type == CliMcpTransportType.HTTP
        assert srv.url == "http://localhost:9090"

    def test_opencode_toggle(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"srv": CliMcpServerConfig(command="cmd")}
            ),
        )
        result = svc.toggle_server_status("ws1", CliMcpScope.PROJECT, "srv", False)
        assert result.mcpServers["srv"].enabled is False

    def test_opencode_native_read(self, tmp_path: Path, workspace_path: Path):
        """Write OpenCode native format directly, verify it reads correctly"""
        native_data = {
            "mcp": {
                "filesystem": {
                    "type": "local",
                    "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace"],
                    "environment": {"HOME": "/root"},
                },
                "api-server": {
                    "type": "remote",
                    "url": "http://api.example.com/mcp",
                },
            }
        }
        _write_json(workspace_path / "settings.json", native_data)

        svc = self._make_service(tmp_path)
        result = svc.list_servers("ws1", CliMcpScope.PROJECT)
        servers = result.scopes[0].mcpServers

        assert "filesystem" in servers
        fs = servers["filesystem"]
        assert fs.type == CliMcpTransportType.STDIO
        assert fs.command == "npx"
        assert fs.args == ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
        assert fs.env == {"HOME": "/root"}

        assert "api-server" in servers
        api = servers["api-server"]
        assert api.type == CliMcpTransportType.HTTP
        assert api.url == "http://api.example.com/mcp"

    def test_import_from_file(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        file_content = json.dumps({
            "mcpServers": {
                "imported-srv": {
                    "type": "stdio",
                    "command": "node",
                    "args": ["dist/index.js"],
                }
            }
        }).encode("utf-8")
        payload = CliMcpImportUploadRequest(
            scope=CliMcpScope.PROJECT,
            file=file_content,
            overwrite=False,
        )
        result = svc.import_servers_from_file("ws1", payload)
        assert "imported-srv" in result.created

    def test_import_overwrite(self, tmp_path: Path, workspace_path: Path):
        svc = self._make_service(tmp_path)
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"srv": CliMcpServerConfig(command="old")}
            ),
        )
        import_req = CliMcpImportRequest(
            scope=CliMcpScope.PROJECT,
            mcpServers={"srv": CliMcpServerConfig(command="new")},
            overwrite=False,
        )
        result = svc.import_servers("ws1", import_req)
        assert "srv" in result.skipped

        import_req.overwrite = True
        result = svc.import_servers("ws1", import_req)
        assert "srv" in result.updated


# === Config Strategies tests ==============================================


class TestJsonConfigStrategy:
    def test_read_missing_file(self, tmp_path: Path):
        strategy = JsonConfigStrategy()
        result = strategy.read(tmp_path / "nonexistent.json")
        assert result == {}

    def test_read_jsonc_comments(self, tmp_path: Path):
        "Test JSONC comment removal"""
        path = tmp_path / "test.json"
        path.write_text(
            '{\n  // comment\n  "key": "value" /* block comment */\n}',
            encoding="utf-8",
        )
        strategy = JsonConfigStrategy()
        result = strategy.read(path)
        assert result == {"key": "value"}

    def test_write_creates_directories(self, tmp_path: Path):
        strategy = JsonConfigStrategy()
        path = tmp_path / "deep" / "nested" / "file.json"
        strategy.write(path, {"hello": "world"})
        assert path.exists()
        assert _read_json(path) == {"hello": "world"}


class TestTomlConfigStrategy:
    def test_read_missing_file(self, tmp_path: Path):
        strategy = TomlConfigStrategy()
        result = strategy.read(tmp_path / "nonexistent.toml")
        assert result == {}

    def test_roundtrip(self, tmp_path: Path):
        strategy = TomlConfigStrategy()
        path = tmp_path / "test.toml"
        data = {
            "mcp_servers": {
                "srv1": {
                    "command": "node",
                    "args": ["index.js"],
                    "env": {"PORT": "3000"},
                }
            }
        }
        strategy.write(path, data)
        result = strategy.read(path)
        assert result == data

    def test_write_creates_directories(self, tmp_path: Path):
        strategy = TomlConfigStrategy()
        path = tmp_path / "deep" / "nested" / "config.toml"
        strategy.write(path, {"key": "value"})
        assert path.exists()


# === Cross-tool parameterized tests =============================================


@pytest.fixture(params=["gemini", "codex", "opencode"])
def tool_service(
    request, tmp_path: Path, workspace_path: Path
) -> tuple[str, CliMcpService]:
    "Parameterized fixture: return (tool_name, service)"""
    tool_name = request.param
    if tool_name == "gemini":
        config = _make_json_config(
            tmp_path, McpTool.GEMINI, "mcpServers", supports_toggle=False
        )
    elif tool_name == "codex":
        config = _make_toml_config(tmp_path)
    else:
        config = _make_json_config(
            tmp_path, McpTool.OPENCODE, "mcp", supports_toggle=True
        )
    return tool_name, CliMcpService(config)


class TestCrossToolCrud:
    "Cross-tool basic CRUD tests"""

    def test_create_get_delete(self, tool_service: tuple[str, CliMcpService]):
        tool_name, svc = tool_service

        # Create
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={"test-srv": CliMcpServerConfig(command="echo")}
            ),
        )

        # Get
        result = svc.get_server("ws1", CliMcpScope.PROJECT, "test-srv")
        assert "test-srv" in result.mcpServers
        assert result.mcpServers["test-srv"].command == "echo"

        # Delete
        svc.delete_server("ws1", CliMcpScope.PROJECT, "test-srv")
        with pytest.raises(CliMcpServerNotFoundError):
            svc.get_server("ws1", CliMcpScope.PROJECT, "test-srv")

    def test_export_roundtrip(self, tool_service: tuple[str, CliMcpService]):
        tool_name, svc = tool_service
        svc.create_servers(
            "ws1",
            CliMcpScope.PROJECT,
            CliMcpServerCreateRequest(
                mcpServers={
                    "exp-srv": CliMcpServerConfig(
                        command="node",
                        args=["server.js"],
                    )
                }
            ),
        )
        exported = svc.export_server("ws1", CliMcpScope.PROJECT, "exp-srv")
        assert "exp-srv" in exported.mcpServers
        cfg = exported.mcpServers["exp-srv"]
        assert cfg.command == "node"
