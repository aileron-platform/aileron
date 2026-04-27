"""MCP Service enhanced unit tests - improve coverage"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.modules.claude_code.mcp.service import (
    McpService,
    McpServerEntry,
    McpScopeNotSupportedError,
    McpServerAlreadyExistsError,
    McpServerNotFoundError,
)
from app.modules.claude_code.mcp.models import (
    McpServerConfig,
    McpServerUpdateRequest,
    McpImportRequest,
    McpImportUploadRequest,
    McpTransportType,
)
from app.modules.claude_code.common import DocumentScope


@pytest.fixture
def mcp_service():
    """MCP service fixture"""
    return McpService()


@pytest.fixture
def workspace_id():
    """Workspace ID fixture"""
    return "test-workspace"


@pytest.fixture
def sample_server_config():
    """Sample server config fixture"""
    return McpServerConfig(
        type=McpTransportType.STDIO,
        command="test-command",
        args=["arg1", "arg2"],
    )


@pytest.fixture
def sample_server_entry(sample_server_config):
    """Sample server entry fixture"""
    return McpServerEntry(
        name="test-server",
        config=sample_server_config,
    )


class TestMcpServerEntry:
    """Test McpServerEntry data class"""

    def test_server_entry_creation(self, sample_server_config):
        """Test creating server entry"""
        # Act
        entry = McpServerEntry(
            name="test-server",
            config=sample_server_config,
        )

        # Assert
        assert entry.name == "test-server"
        assert entry.config == sample_server_config

    def test_to_runtime_enabled(self, sample_server_entry):
        """Test conversion to runtime (enabled)"""
        # Act
        runtime = sample_server_entry.to_runtime(enabled=True)

        # Assert
        assert runtime.enabled is True
        assert runtime.type == McpTransportType.STDIO
        assert runtime.command == "test-command"

    def test_to_runtime_disabled(self, sample_server_entry):
        """Test conversion to runtime (disabled)"""
        # Act
        runtime = sample_server_entry.to_runtime(enabled=False)

        # Assert
        assert runtime.enabled is False

    def test_to_storage(self, sample_server_entry):
        """Test conversion to storage format"""
        # Act
        storage = sample_server_entry.to_storage()

        # Assert
        assert isinstance(storage, dict)
        assert storage["type"] == "stdio"
        assert storage["command"] == "test-command"
        assert "enabled" not in storage  # storage format does not include enabled


class TestScopeNormalization:
    """Test scope normalization"""

    def test_normalize_scope_project(self, mcp_service):
        """Test normalizing PROJECT scope"""
        # Act
        result = mcp_service._normalize_scope(DocumentScope.PROJECT)

        # Assert
        assert result == DocumentScope.PROJECT

    def test_normalize_scope_user(self, mcp_service):
        """Test normalizing USER scope"""
        # Act
        result = mcp_service._normalize_scope(DocumentScope.USER)

        # Assert
        assert result == DocumentScope.USER

    def test_normalize_scope_local(self, mcp_service):
        """Test normalizing LOCAL scope"""
        # Act
        result = mcp_service._normalize_scope(DocumentScope.LOCAL)

        # Assert
        assert result == DocumentScope.LOCAL

    def test_normalize_scope_plugin_not_supported(self, mcp_service):
        """Test PLUGIN scope not supported for writes"""
        # Act & Assert
        with pytest.raises(McpScopeNotSupportedError):
            mcp_service._normalize_scope(DocumentScope.PLUGIN)

    def test_normalize_scope_for_read_plugin(self, mcp_service):
        """Test PLUGIN scope supported for reads"""
        # Act
        result = mcp_service._normalize_scope_for_read(DocumentScope.PLUGIN)

        # Assert
        assert result == DocumentScope.PLUGIN

    def test_normalize_optional_scope_none(self, mcp_service):
        """測試正規化 None scope"""
        # Act
        result = mcp_service._normalize_optional_scope(None)

        # Assert
        assert result is None


class TestPathResolution:
    """測試路徑解析"""

    @patch("app.modules.claude_code.mcp.service.workspace_root")
    def test_project_file_path(self, mock_workspace_root, mcp_service, workspace_id, tmp_path):
        """測試 project 文件路徑"""
        # Arrange
        mock_workspace_root.return_value = tmp_path

        # Act
        result = mcp_service._project_file(workspace_id)

        # Assert
        assert result == tmp_path / ".mcp.json"

    def test_local_file_path(self, mcp_service):
        """測試 local 文件路徑"""
        # Act
        result = mcp_service._local_file()

        # Assert
        assert result == Path.home() / ".claude.json"

    def test_user_file_path(self, mcp_service):
        """測試 user 文件路徑"""
        # Act
        result = mcp_service._user_file()

        # Assert
        assert result == Path.home() / ".claude.json"

    @patch("app.modules.claude_code.mcp.service.workspace_root")
    def test_possible_user_project_keys(self, mock_workspace_root, mcp_service, workspace_id, tmp_path):
        """測試可能的 user project keys"""
        # Arrange
        mock_workspace_root.return_value = tmp_path

        # Act
        result = mcp_service._possible_user_project_keys(workspace_id)

        # Assert
        assert isinstance(result, list)
        assert len(result) > 0
        assert "/workspace" in result  # 最常見的 key

    @patch("app.modules.claude_code.mcp.service.workspace_root")
    def test_primary_user_project_key(self, mock_workspace_root, mcp_service, workspace_id, tmp_path):
        """測試主要 user project key"""
        # Arrange
        mock_workspace_root.return_value = tmp_path

        # Act
        result = mcp_service._primary_user_project_key(workspace_id)

        # Assert
        assert result == "/workspace"


class TestDecodeServers:
    """測試解碼 servers"""

    def test_decode_servers_valid(self, mcp_service):
        """測試解碼有效的 servers"""
        # Arrange
        payload = {
            "server1": {
                "type": "stdio",
                "command": "cmd1",
            },
            "server2": {
                "type": "sse",
                "url": "https://example.com",
            },
        }

        # Act
        result = mcp_service._decode_servers(payload)

        # Assert
        assert len(result) == 2
        assert "server1" in result
        assert "server2" in result
        assert result["server1"].config.command == "cmd1"

    def test_decode_servers_invalid_config(self, mcp_service):
        """測試解碼無效配置時跳過"""
        # Arrange
        payload = {
            "valid": {
                "type": "stdio",
                "command": "cmd",
            },
            "invalid": {
                "type": "invalid_type",  # 無效類型
            },
        }

        # Act
        result = mcp_service._decode_servers(payload)

        # Assert
        assert len(result) == 1
        assert "valid" in result
        assert "invalid" not in result

    def test_decode_servers_empty_name(self, mcp_service):
        """測試空名稱被跳過"""
        # Arrange
        payload = {
            "": {
                "type": "stdio",
                "command": "cmd",
            },
        }

        # Act
        result = mcp_service._decode_servers(payload)

        # Assert
        assert len(result) == 0

    def test_decode_servers_non_dict_value(self, mcp_service):
        """測試非字典值被跳過"""
        # Arrange
        payload = {
            "server": "not a dict",
        }

        # Act
        result = mcp_service._decode_servers(payload)

        # Assert
        assert len(result) == 0


class TestEncodeServers:
    """測試編碼 servers"""

    def test_encode_servers(self, mcp_service, sample_server_entry):
        """測試編碼 servers"""
        # Arrange
        entries = {
            "server1": sample_server_entry,
        }

        # Act
        result = mcp_service._encode_servers(entries)

        # Assert
        assert isinstance(result, dict)
        assert "server1" in result
        assert result["server1"]["type"] == "stdio"

    def test_encode_servers_sorted(self, mcp_service, sample_server_config):
        """測試編碼時排序"""
        # Arrange
        entries = {
            "z-server": McpServerEntry("z-server", sample_server_config),
            "a-server": McpServerEntry("a-server", sample_server_config),
            "m-server": McpServerEntry("m-server", sample_server_config),
        }

        # Act
        result = mcp_service._encode_servers(entries)

        # Assert
        keys = list(result.keys())
        assert keys == ["a-server", "m-server", "z-server"]


class TestPreparePayload:
    """測試準備 payload"""

    def test_prepare_payload_valid(self, mcp_service, sample_server_config):
        """測試準備有效 payload"""
        # Arrange
        payload = {
            "server1": sample_server_config,
            "server2": sample_server_config,
        }

        # Act
        result = mcp_service._prepare_payload(payload)

        # Assert
        assert len(result) == 2
        assert "server1" in result
        assert "server2" in result

    def test_prepare_payload_empty_name(self, mcp_service, sample_server_config):
        """測試跳過空名稱"""
        # Arrange
        payload = {
            "": sample_server_config,
            "  ": sample_server_config,
            "valid": sample_server_config,
        }

        # Act
        result = mcp_service._prepare_payload(payload)

        # Assert
        assert len(result) == 1
        assert "valid" in result

    def test_prepare_payload_strip_whitespace(self, mcp_service, sample_server_config):
        """測試去除名稱空白"""
        # Arrange
        payload = {
            " server1 ": sample_server_config,
        }

        # Act
        result = mcp_service._prepare_payload(payload)

        # Assert
        assert "server1" in result


class TestImportServers:
    """測試匯入 servers"""

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    @patch("app.modules.claude_code.mcp.service.resolve_scope_root")
    def test_import_servers_create_new(
        self, mock_resolve, mock_read, mock_write, mcp_service, workspace_id, sample_server_config, tmp_path
    ):
        """測試匯入新 servers"""
        # Arrange
        mock_resolve.return_value = tmp_path
        mock_read.return_value = {"mcpServers": {}}

        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            mcpServers={"new-server": sample_server_config},
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert len(result.created) == 1
        assert "new-server" in result.created
        assert len(result.updated) == 0
        assert len(result.skipped) == 0
        mock_write.assert_called_once()

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    @patch("app.modules.claude_code.mcp.service.resolve_scope_root")
    def test_import_servers_skip_existing(
        self, mock_resolve, mock_read, mock_write, mcp_service, workspace_id, sample_server_config, tmp_path
    ):
        """測試跳過已存在的 servers"""
        # Arrange
        mock_resolve.return_value = tmp_path
        mock_read.return_value = {
            "mcpServers": {
                "existing-server": {
                    "type": "stdio",
                    "command": "old-command",
                }
            }
        }

        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            mcpServers={"existing-server": sample_server_config},
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert len(result.created) == 0
        assert len(result.updated) == 0
        assert len(result.skipped) == 1
        assert "existing-server" in result.skipped
        mock_write.assert_not_called()

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    @patch("app.modules.claude_code.mcp.service.resolve_scope_root")
    def test_import_servers_overwrite_existing(
        self, mock_resolve, mock_read, mock_write, mcp_service, workspace_id, sample_server_config, tmp_path
    ):
        """測試覆蓋已存在的 servers"""
        # Arrange
        mock_resolve.return_value = tmp_path
        mock_read.return_value = {
            "mcpServers": {
                "existing-server": {
                    "type": "stdio",
                    "command": "old-command",
                }
            }
        }

        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            mcpServers={"existing-server": sample_server_config},
            overwrite=True,
        )

        # Act
        result = mcp_service.import_servers(workspace_id, payload)

        # Assert
        assert len(result.created) == 0
        assert len(result.updated) == 1
        assert "existing-server" in result.updated
        assert len(result.skipped) == 0
        mock_write.assert_called_once()

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    @patch("app.modules.claude_code.mcp.service.resolve_scope_root")
    def test_import_servers_empty_payload(
        self, mock_resolve, mock_read, mcp_service, workspace_id, tmp_path, sample_server_config
    ):
        """Test empty payload (use valid but processed-as-empty payload)"""
        # Arrange
        mock_resolve.return_value = tmp_path
        mock_read.return_value = {"mcpServers": {}}

        # Since McpImportRequest requires at least 1 item, we test _prepare_payload's empty handling
        # Test empty payload logic by directly calling internal method
        payload = McpImportRequest(
            scope=DocumentScope.PROJECT,
            mcpServers={"": sample_server_config},  # Will be filtered out by _prepare_payload
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mcp_service.import_servers(workspace_id, payload)
        assert "Empty payload" in str(exc_info.value)


class TestImportServersFromFile:
    """Test importing servers from file"""

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    @patch("app.modules.claude_code.mcp.service.resolve_scope_root")
    def test_import_from_file_success(
        self, mock_resolve, mock_read, mock_write, mcp_service, workspace_id, tmp_path
    ):
        """測試成功從文件匯入"""
        # Arrange
        mock_resolve.return_value = tmp_path
        mock_read.return_value = {"mcpServers": {}}

        file_content = json.dumps({
            "mcpServers": {
                "test-server": {
                    "type": "stdio",
                    "command": "test-cmd",
                }
            }
        })

        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=file_content.encode('utf-8'),
            overwrite=False,
        )

        # Act
        result = mcp_service.import_servers_from_file(workspace_id, payload)

        # Assert
        assert len(result.created) == 1
        assert "test-server" in result.created

    def test_import_from_file_invalid_json(self, mcp_service, workspace_id):
        """Test invalid JSON"""
        # Arrange
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=b"invalid json",
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mcp_service.import_servers_from_file(workspace_id, payload)
        assert "Invalid JSON format" in str(exc_info.value)

    def test_import_from_file_missing_mcp_servers_field(self, mcp_service, workspace_id):
        """Test missing mcpServers field"""
        # Arrange
        file_content = json.dumps({"other": "data"})
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=file_content.encode('utf-8'),
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mcp_service.import_servers_from_file(workspace_id, payload)
        assert "missing 'mcpServers' field" in str(exc_info.value)

    def test_import_from_file_invalid_encoding(self, mcp_service, workspace_id):
        """Test invalid encoding"""
        # Arrange
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=b"\xFF\xFE",  # Invalid UTF-8
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mcp_service.import_servers_from_file(workspace_id, payload)
        assert "encoding error" in str(exc_info.value).lower()

    def test_import_from_file_mcp_servers_not_dict(self, mcp_service, workspace_id):
        """Test mcpServers is not a dictionary"""
        # Arrange
        file_content = json.dumps({"mcpServers": []})
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=file_content.encode('utf-8'),
            overwrite=False,
        )

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            mcp_service.import_servers_from_file(workspace_id, payload)
        assert "'mcpServers' must be an object" in str(exc_info.value)


class TestLoadDisabledServers:
    """Test loading disabled servers list"""

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_disabled_servers_success(self, mock_read, mcp_service, workspace_id):
        """Test successful loading of disabled list"""
        # Arrange
        mock_read.return_value = {
            "projects": {
                "/workspace": {
                    "disabledMcpServers": ["server1", "server2"]
                }
            }
        }

        # Act
        result = mcp_service._load_disabled_servers(workspace_id)

        # Assert
        assert result == ["server1", "server2"]

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_disabled_servers_empty(self, mock_read, mcp_service, workspace_id):
        """Test empty disabled list"""
        # Arrange
        mock_read.return_value = {
            "projects": {
                "/workspace": {}
            }
        }

        # Act
        result = mcp_service._load_disabled_servers(workspace_id)

        # Assert
        assert result == []

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_disabled_servers_not_a_dict(self, mock_read, mcp_service, workspace_id):
        """Test file is not a dictionary"""
        # Arrange
        mock_read.return_value = []

        # Act
        result = mcp_service._load_disabled_servers(workspace_id)

        # Assert
        assert result == []

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_disabled_servers_projects_not_a_dict(self, mock_read, mcp_service, workspace_id):
        """Test projects is not a dictionary"""
        # Arrange
        mock_read.return_value = {"projects": "not a dict"}

        # Act
        result = mcp_service._load_disabled_servers(workspace_id)

        # Assert
        assert result == []


class TestUpdateProjectBlockField:
    """Test updating project block fields"""

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_update_project_block_field_creates_new(self, mock_read, mock_write, mcp_service, workspace_id):
        """Test creating new project block"""
        # Arrange
        mock_read.return_value = {}

        # Act
        mcp_service._update_project_block_field(workspace_id, "testField", "testValue")

        # Assert
        mock_write.assert_called_once()
        written_data = mock_write.call_args[0][1]
        assert "projects" in written_data
        assert "/workspace" in written_data["projects"]
        assert written_data["projects"]["/workspace"]["testField"] == "testValue"

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_update_project_block_field_preserves_other_fields(self, mock_read, mock_write, mcp_service, workspace_id):
        """Test preserving other fields"""
        # Arrange
        mock_read.return_value = {
            "projects": {
                "/workspace": {
                    "existingField": "existingValue",
                }
            }
        }

        # Act
        mcp_service._update_project_block_field(workspace_id, "newField", "newValue")

        # Assert
        written_data = mock_write.call_args[0][1]
        project_block = written_data["projects"]["/workspace"]
        assert project_block["existingField"] == "existingValue"
        assert project_block["newField"] == "newValue"


class TestRuntimeMap:
    """Test runtime map"""

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_runtime_map_with_disabled_servers(self, mock_read, mcp_service, workspace_id, sample_server_entry):
        """Test runtime map with disabled servers"""
        # Arrange
        mock_read.return_value = {
            "projects": {
                "/workspace": {
                    "disabledMcpServers": ["server1"]
                }
            }
        }

        entries = {
            "server1": sample_server_entry,
            "server2": McpServerEntry("server2", sample_server_entry.config),
        }

        # Act
        result = mcp_service._runtime_map(entries, workspace_id)

        # Assert
        assert result["server1"].enabled is False
        assert result["server2"].enabled is True


class TestMcpServiceAdditionalCoverage:
    """Supplement uncovered branches of mcp service."""

    def test_iter_payload_items_non_dict_returns_empty(self, mcp_service):
        assert list(mcp_service._iter_payload_items(["not", "dict"])) == []

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_local_entries_uses_first_matching_project_key(self, mock_read, mcp_service):
        mock_read.return_value = {
            "projects": {
                "/workspace": {
                    "mcpServers": {
                        "local-server": {"type": "stdio", "command": "cmd"},
                    }
                }
            }
        }

        entries = mcp_service._load_local_entries("ws-1")

        assert list(entries.keys()) == ["local-server"]

    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_load_local_entries_returns_empty_for_non_dict_projects(self, mock_read, mcp_service):
        mock_read.return_value = {"projects": []}

        assert mcp_service._load_local_entries("ws-1") == {}

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_write_user_entries_preserves_other_root_fields(self, mock_read, mock_write, mcp_service, sample_server_entry):
        mock_read.return_value = {"other": "value"}

        mcp_service._write_user_entries("ws-1", {"srv": sample_server_entry})

        written = mock_write.call_args.args[1]
        assert written["other"] == "value"
        assert written["mcpServers"]["srv"]["command"] == "test-command"

    @patch("app.modules.claude_code.mcp.service.write_json_file")
    @patch("app.modules.claude_code.mcp.service.read_json_file")
    def test_write_local_entries_updates_only_mcp_servers(self, mock_read, mock_write, mcp_service, sample_server_entry):
        mock_read.return_value = {
            "projects": {"/workspace": {"disabledMcpServers": ["srv"]}}
        }

        mcp_service._write_local_entries("ws-1", {"srv": sample_server_entry})

        written = mock_write.call_args.args[1]
        project_block = written["projects"]["/workspace"]
        assert project_block["disabledMcpServers"] == ["srv"]
        assert project_block["mcpServers"]["srv"]["command"] == "test-command"

    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_list_servers_plugin_scope_only(self, mock_plugin, mcp_service):
        mock_plugin.return_value = {
            "plugin-server": McpServerEntry(
                name="plugin-server",
                config=McpServerConfig(type=McpTransportType.STDIO, command="cmd"),
            ).to_runtime()
        }

        result = mcp_service.list_servers("ws-1", DocumentScope.PLUGIN)

        assert len(result.scopes) == 1
        assert result.scopes[0].scope == DocumentScope.PLUGIN
        assert "plugin-server" in result.scopes[0].mcpServers

    @patch.object(McpService, "_load_scope_entries")
    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_list_servers_logs_and_skips_plugin_load_failures(self, mock_plugin, mock_entries, mcp_service, caplog):
        mock_entries.return_value = {}
        mock_plugin.side_effect = RuntimeError("plugin boom")

        with caplog.at_level("ERROR"):
            result = mcp_service.list_servers("ws-1")

        assert len(result.scopes) == 3
        assert "Failed to load plugin MCP servers" in caplog.text

    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_get_scope_plugin_reads_plugin_servers(self, mock_plugin, mcp_service):
        runtime = McpServerEntry(
            name="plugin-server",
            config=McpServerConfig(type=McpTransportType.STDIO, command="cmd"),
        ).to_runtime()
        mock_plugin.return_value = {"plugin-server": runtime}

        result = mcp_service.get_scope("ws-1", DocumentScope.PLUGIN)

        assert result.scope == DocumentScope.PLUGIN
        assert result.mcpServers["plugin-server"] == runtime

    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_get_server_plugin_missing_raises(self, mock_plugin, mcp_service):
        mock_plugin.return_value = {}

        with pytest.raises(McpServerNotFoundError):
            mcp_service.get_server("ws-1", DocumentScope.PLUGIN, "missing")

    def test_update_server_rejects_empty_payload(self, mcp_service, sample_server_entry):
        with patch.object(mcp_service, "_load_scope_entries", return_value={"srv": sample_server_entry}):
            payload = McpServerUpdateRequest(mcpServers={"": sample_server_entry.config})
            with pytest.raises(ValueError, match="Empty payload"):
                mcp_service.update_server("ws-1", DocumentScope.PROJECT, "srv", payload)

    def test_update_server_rejects_multiple_payload_items(self, mcp_service, sample_server_config):
        entries = {"srv": McpServerEntry("srv", sample_server_config)}
        payload = McpServerUpdateRequest(
            mcpServers={"srv": sample_server_config, "srv2": sample_server_config}
        )

        with patch.object(mcp_service, "_load_scope_entries", return_value=entries):
            with pytest.raises(ValueError, match="Only one server"):
                mcp_service.update_server("ws-1", DocumentScope.PROJECT, "srv", payload)

    def test_update_server_rejects_name_mismatch(self, mcp_service, sample_server_config):
        entries = {"srv": McpServerEntry("srv", sample_server_config)}
        payload = McpServerUpdateRequest(mcpServers={"other": sample_server_config})

        with patch.object(mcp_service, "_load_scope_entries", return_value=entries):
            with pytest.raises(McpServerAlreadyExistsError, match="does not match target"):
                mcp_service.update_server("ws-1", DocumentScope.PROJECT, "srv", payload)

    def test_export_server_missing_raises(self, mcp_service):
        with patch.object(mcp_service, "_load_scope_entries", return_value={}):
            with pytest.raises(McpServerNotFoundError):
                mcp_service.export_server("ws-1", DocumentScope.PROJECT, "missing")

    def test_toggle_server_status_missing_server_raises(self, mcp_service):
        with patch.object(mcp_service, "_load_scope_entries", return_value={}):
            with pytest.raises(McpServerNotFoundError):
                mcp_service.toggle_server_status("ws-1", DocumentScope.PROJECT, "missing", False)

    @patch.object(McpService, "_save_disabled_servers")
    @patch.object(McpService, "_load_disabled_servers")
    @patch.object(McpService, "_load_scope_entries")
    def test_toggle_server_status_updates_disabled_server_list(
        self, mock_load_entries, mock_load_disabled, mock_save_disabled, mcp_service, sample_server_entry
    ):
        mock_load_entries.return_value = {"srv": sample_server_entry}
        mock_load_disabled.side_effect = [["other"], ["other", "srv"]]

        disabled = mcp_service.toggle_server_status("ws-1", DocumentScope.PROJECT, "srv", False)
        enabled = mcp_service.toggle_server_status("ws-1", DocumentScope.PROJECT, "srv", True)

        assert disabled.mcpServers["srv"].enabled is False
        assert enabled.mcpServers["srv"].enabled is True
        assert mock_save_disabled.call_args_list[0].args[1] == ["other", "srv"]
        assert mock_save_disabled.call_args_list[1].args[1] == ["other"]

    def test_import_from_file_invalid_server_config_object(self, mcp_service, workspace_id):
        file_content = json.dumps({"mcpServers": {"bad": "not-an-object"}})
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=file_content.encode("utf-8"),
            overwrite=False,
        )

        with pytest.raises(ValueError, match="must be an object"):
            mcp_service.import_servers_from_file(workspace_id, payload)

    def test_import_from_file_wraps_unexpected_exception(self, mcp_service, workspace_id):
        file_content = json.dumps({"mcpServers": {"srv": {"type": "stdio", "command": "cmd"}}})
        payload = McpImportUploadRequest(
            scope=DocumentScope.PROJECT,
            file=file_content.encode("utf-8"),
            overwrite=False,
        )

        with patch.object(mcp_service, "import_servers", side_effect=RuntimeError("boom")):
            with pytest.raises(ValueError, match="Failed to process import file: boom"):
                mcp_service.import_servers_from_file(workspace_id, payload)

    @patch("app.modules.claude_code.settings.dependencies.get_settings_service")
    @patch("app.modules.claude_code.plugins.loader.get_plugin_loader")
    @patch.object(McpService, "_load_disabled_servers")
    def test_load_plugin_mcp_servers_filters_invalid_entries_and_disabled_states(
        self, mock_disabled, mock_loader_factory, mock_settings_service, mcp_service
    ):
        mock_settings_service.return_value = object()
        loader = MagicMock()
        loader.load_plugin_mcp_servers.return_value = {
            "chrome-devtools-mcp@market": {
                "chrome-devtools": {"type": "stdio", "command": "cmd"},
                "legacy": "invalid",
            },
            "bad-plugin@market": ["invalid"],
            "invalid-runtime@market": {
                "oops": {"type": "unknown"},
            },
        }
        mock_loader_factory.return_value = loader
        mock_disabled.return_value = ["plugin:chrome-devtools-mcp:chrome-devtools"]

        servers = mcp_service._load_plugin_mcp_servers("ws-1")

        assert list(servers.keys()) == ["chrome-devtools"]
        assert servers["chrome-devtools"].enabled is False
        assert servers["chrome-devtools"].plugin_name == "chrome-devtools-mcp"

    @patch.object(McpService, "_save_disabled_servers")
    @patch.object(McpService, "_load_disabled_servers")
    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_toggle_plugin_server_status_enable_and_disable(
        self, mock_load_plugins, mock_load_disabled, mock_save_disabled, mcp_service
    ):
        def make_runtime():
            runtime = McpServerEntry(
                name="chrome-devtools",
                config=McpServerConfig(type=McpTransportType.STDIO, command="cmd"),
            ).to_runtime()
            runtime.plugin_name = "chrome-devtools-mcp"
            return {"chrome-devtools": runtime}

        mock_load_plugins.side_effect = [make_runtime(), make_runtime()]
        mock_load_disabled.side_effect = [
            ["chrome-devtools", "plugin:chrome-devtools-mcp:chrome-devtools"],
            [],
        ]

        disabled = mcp_service._toggle_plugin_server_status("ws-1", "chrome-devtools", False)
        enabled = mcp_service._toggle_plugin_server_status("ws-1", "chrome-devtools", True)

        assert disabled.mcpServers["chrome-devtools"].enabled is False
        assert enabled.mcpServers["chrome-devtools"].enabled is True
        assert mock_save_disabled.call_args_list[0].args[1] == ["plugin:chrome-devtools-mcp:chrome-devtools"]
        assert mock_save_disabled.call_args_list[1].args[1] == []

    @patch.object(McpService, "_load_plugin_mcp_servers")
    def test_toggle_plugin_server_status_requires_plugin_name(self, mock_load_plugins, mcp_service):
        runtime = McpServerEntry(
            name="plain",
            config=McpServerConfig(type=McpTransportType.STDIO, command="cmd"),
        ).to_runtime()
        runtime.plugin_name = None
        mock_load_plugins.return_value = {"plain": runtime}

        with pytest.raises(ValueError, match="is not a plugin server"):
            mcp_service._toggle_plugin_server_status("ws-1", "plain", False)
