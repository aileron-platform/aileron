"""Plugin Loader 单元测试"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open

from app.modules.claude_code.plugins.loader import (
    PluginComponentsLoader,
    ComponentFileInfo,
    SkillDirectoryInfo,
    get_plugin_loader,
)
from app.modules.claude_code.common import DocumentScope


@pytest.fixture
def mock_settings_service():
    """Mock SettingsService fixture."""
    service = Mock()
    service._read_scope_state = Mock(return_value={})
    service._extract_enabled_plugins = Mock(return_value={})
    return service


@pytest.fixture
def plugin_loader(mock_settings_service):
    """Plugin loader fixture."""
    return PluginComponentsLoader(mock_settings_service)


@pytest.fixture
def sample_marketplace_data():
    """Sample marketplace.json data."""
    return {
        "name": "test-marketplace",
        "plugins": [
            {
                "name": "test-plugin",
                "version": "1.0.0",
                "source": "./plugins/test-plugin",
                "strict": True,
                "commands": ["commands/test.md"],
                "agents": ["agents/test-agent.md"],
                "skills": ["skills/pdf", "skills/xlsx"],
                "mcpServers": {
                    "test-server": {
                        "command": "node",
                        "args": ["server.js"]
                    }
                },
                "hooks": {
                    "pre-commit": "echo test"
                }
            }
        ]
    }


@pytest.fixture
def sample_plugin_config():
    """Sample plugin configuration."""
    return {
        "name": "test-plugin",
        "version": "1.0.0",
        "source": "./plugins/test-plugin",
        "strict": True,
        "commands": ["commands/test.md"],
        "agents": ["agents/test-agent.md"]
    }


class TestComponentFileInfo:
    """测试 ComponentFileInfo 数据类."""

    def test_component_file_info_creation(self):
        """测试 ComponentFileInfo 创建."""
        # Act
        info = ComponentFileInfo(
            file_path="/path/to/file.md",
            file_name="file",
            plugin_name="test-plugin",
            marketplace_name="test-marketplace",
            description="Test description"
        )

        # Assert
        assert info.file_path == "/path/to/file.md"
        assert info.file_name == "file"
        assert info.plugin_name == "test-plugin"
        assert info.marketplace_name == "test-marketplace"
        assert info.description == "Test description"

    def test_component_file_info_without_description(self):
        """测试不含描述的 ComponentFileInfo 创建."""
        # Act
        info = ComponentFileInfo(
            file_path="/path/to/file.md",
            file_name="file",
            plugin_name="test-plugin",
            marketplace_name="test-marketplace"
        )

        # Assert
        assert info.description is None


class TestSkillDirectoryInfo:
    """测试 SkillDirectoryInfo 数据类."""

    def test_skill_directory_info_creation(self):
        """测试 SkillDirectoryInfo 创建."""
        # Act
        info = SkillDirectoryInfo(
            directory_path="/path/to/skill",
            skill_name="pdf",
            plugin_name="test-plugin",
            marketplace_name="test-marketplace"
        )

        # Assert
        assert info.directory_path == "/path/to/skill"
        assert info.skill_name == "pdf"
        assert info.plugin_name == "test-plugin"
        assert info.marketplace_name == "test-marketplace"


class TestPluginLoaderInitialization:
    """测试 Plugin Loader 初始化."""

    def test_loader_init(self, mock_settings_service):
        """测试 Loader 初始化."""
        # Act
        loader = PluginComponentsLoader(mock_settings_service)

        # Assert
        assert loader.settings_service == mock_settings_service


class TestParsePluginId:
    """测试 Plugin ID 解析."""

    def test_parse_valid_plugin_id(self, plugin_loader):
        """测试解析有效的 plugin ID."""
        # Act
        plugin_name, marketplace_name = plugin_loader._parse_plugin_id(
            "test-plugin@test-marketplace"
        )

        # Assert
        assert plugin_name == "test-plugin"
        assert marketplace_name == "test-marketplace"

    def test_parse_plugin_id_with_special_chars(self, plugin_loader):
        """测试解析包含特殊字符的 plugin ID."""
        # Act
        plugin_name, marketplace_name = plugin_loader._parse_plugin_id(
            "my-plugin-v2@my.marketplace"
        )

        # Assert
        assert plugin_name == "my-plugin-v2"
        assert marketplace_name == "my.marketplace"

    def test_parse_invalid_plugin_id_no_at(self, plugin_loader):
        """测试解析缺少 @ 的 plugin ID."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid plugin_id format"):
            plugin_loader._parse_plugin_id("invalid-plugin-id")

    def test_parse_invalid_plugin_id_multiple_at(self, plugin_loader):
        """测试解析包含多个 @ 的 plugin ID."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid plugin_id format"):
            plugin_loader._parse_plugin_id("plugin@market@extra")

    def test_parse_invalid_plugin_id_empty_parts(self, plugin_loader):
        """测试解析空白部分的 plugin ID."""
        # Act & Assert
        with pytest.raises(ValueError, match="Invalid plugin_id"):
            plugin_loader._parse_plugin_id("@marketplace")

        with pytest.raises(ValueError, match="Invalid plugin_id"):
            plugin_loader._parse_plugin_id("plugin@")


class TestResolvePath:
    """测试路径解析."""

    def test_resolve_relative_path(self, plugin_loader):
        """测试解析相对路径."""
        # Arrange
        base_path = Path("/base/path")
        relative_path = "./subdir/file.md"

        # Act
        result = plugin_loader._resolve_path(base_path, relative_path)

        # Assert
        assert result == (base_path / "subdir/file.md").resolve()

    def test_resolve_absolute_path(self, plugin_loader):
        """测试解析绝对路径."""
        # Arrange
        base_path = Path("/base/path")
        absolute_path = "/absolute/path/file.md"

        # Act
        result = plugin_loader._resolve_path(base_path, absolute_path)

        # Assert
        assert result == Path("/absolute/path/file.md")

    def test_resolve_path_with_env_var(self, plugin_loader):
        """测试解析包含环境变量的路径."""
        # Arrange
        base_path = Path("/base/path")
        path_with_env = "${CLAUDE_PLUGIN_ROOT}/subdir/file.md"

        # Act
        result = plugin_loader._resolve_path(base_path, path_with_env)

        # Assert
        assert result == Path("/subdir/file.md")


class TestReplaceEnvVars:
    """测试环境变量替换."""

    def test_replace_env_vars_in_string(self, plugin_loader):
        """测试替换字符串中的环境变量."""
        # Arrange
        base_path = Path("/base/path")
        config = "${CLAUDE_PLUGIN_ROOT}/test"

        # Act
        result = plugin_loader._replace_env_vars(base_path, config)

        # Assert
        assert result == "/base/path/test"

    def test_replace_env_vars_in_dict(self, plugin_loader):
        """测试替换字典中的环境变量."""
        # Arrange
        base_path = Path("/base/path")
        config = {
            "command": "${CLAUDE_PLUGIN_ROOT}/bin/tool",
            "args": ["--path", "${CLAUDE_PLUGIN_ROOT}/data"]
        }

        # Act
        result = plugin_loader._replace_env_vars(base_path, config)

        # Assert
        assert result["command"] == "/base/path/bin/tool"
        assert result["args"][1] == "/base/path/data"

    def test_replace_env_vars_in_list(self, plugin_loader):
        """测试替换列表中的环境变量."""
        # Arrange
        base_path = Path("/base/path")
        config = ["${CLAUDE_PLUGIN_ROOT}/a", "${CLAUDE_PLUGIN_ROOT}/b"]

        # Act
        result = plugin_loader._replace_env_vars(base_path, config)

        # Assert
        assert result == ["/base/path/a", "/base/path/b"]

    def test_replace_env_vars_nested_structure(self, plugin_loader):
        """测试替换嵌套结构中的环境变量."""
        # Arrange
        base_path = Path("/base/path")
        config = {
            "servers": {
                "server1": {
                    "command": "${CLAUDE_PLUGIN_ROOT}/server1",
                    "env": {
                        "PATH": "${CLAUDE_PLUGIN_ROOT}/bin"
                    }
                }
            }
        }

        # Act
        result = plugin_loader._replace_env_vars(base_path, config)

        # Assert
        assert result["servers"]["server1"]["command"] == "/base/path/server1"
        assert result["servers"]["server1"]["env"]["PATH"] == "/base/path/bin"


class TestReadJsonFile:
    """测试 JSON 文件读取."""

    def test_read_valid_json_file(self, plugin_loader, tmp_path):
        """测试读取有效的 JSON 文件."""
        # Arrange
        json_file = tmp_path / "test.json"
        json_data = {"key": "value", "number": 42}
        json_file.write_text(json.dumps(json_data))

        # Act
        result = plugin_loader._read_json_file(json_file)

        # Assert
        assert result == json_data

    def test_read_invalid_json_file(self, plugin_loader, tmp_path):
        """测试读取无效的 JSON 文件."""
        # Arrange
        json_file = tmp_path / "invalid.json"
        json_file.write_text("{ invalid json }")

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid JSON"):
            plugin_loader._read_json_file(json_file)

    def test_read_nonexistent_json_file(self, plugin_loader, tmp_path):
        """测试读取不存在的 JSON 文件."""
        # Arrange
        json_file = tmp_path / "nonexistent.json"

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            plugin_loader._read_json_file(json_file)


class TestExtractDescription:
    """测试描述提取."""

    def test_extract_description_from_frontmatter(self, plugin_loader, tmp_path):
        """测试从 frontmatter 提取描述."""
        # Arrange
        md_file = tmp_path / "test.md"
        content = """---
description: Test description
title: Test
---

# Content
"""
        md_file.write_text(content)

        # Act
        result = plugin_loader._extract_description(md_file)

        # Assert
        assert result == "Test description"

    def test_extract_description_with_quotes(self, plugin_loader, tmp_path):
        """测试提取带引号的描述."""
        # Arrange
        md_file = tmp_path / "test.md"
        content = """---
description: "Test description with quotes"
---

# Content
"""
        md_file.write_text(content)

        # Act
        result = plugin_loader._extract_description(md_file)

        # Assert
        assert result == "Test description with quotes"

    def test_extract_description_no_frontmatter(self, plugin_loader, tmp_path):
        """测试提取无 frontmatter 的文件."""
        # Arrange
        md_file = tmp_path / "test.md"
        content = "# Simple content without frontmatter"
        md_file.write_text(content)

        # Act
        result = plugin_loader._extract_description(md_file)

        # Assert
        assert result is None

    def test_extract_description_nonexistent_file(self, plugin_loader, tmp_path):
        """测试提取不存在文件的描述."""
        # Arrange
        md_file = tmp_path / "nonexistent.md"

        # Act
        result = plugin_loader._extract_description(md_file)

        # Assert
        assert result is None


class TestFindPluginInMarketplace:
    """测试在 marketplace 中查找 plugin."""

    def test_find_existing_plugin(self, plugin_loader, sample_marketplace_data):
        """测试查找存在的 plugin."""
        # Act
        result = plugin_loader._find_plugin_in_marketplace(
            sample_marketplace_data, "test-plugin"
        )

        # Assert
        assert result["name"] == "test-plugin"
        assert result["version"] == "1.0.0"

    def test_find_nonexistent_plugin(self, plugin_loader, sample_marketplace_data):
        """测试查找不存在的 plugin."""
        # Act & Assert
        with pytest.raises(ValueError, match="Plugin 'nonexistent' not found"):
            plugin_loader._find_plugin_in_marketplace(
                sample_marketplace_data, "nonexistent"
            )


class TestGetEnabledPlugins:
    """测试获取已启用的 plugins."""

    def test_get_enabled_plugins_empty(self, plugin_loader):
        """测试获取空的已启用 plugins."""
        # Arrange
        plugin_loader.settings_service._read_scope_state.return_value = {}
        plugin_loader.settings_service._extract_enabled_plugins.return_value = {}

        # Act
        result = plugin_loader._get_enabled_plugins("test-workspace")

        # Assert
        assert result == {}

    def test_get_enabled_plugins_multiple_scopes(self, plugin_loader):
        """测试从多个 scope 获取已启用 plugins."""
        # Arrange
        def mock_extract(state):
            return state.get("plugins", {})

        plugin_loader.settings_service._extract_enabled_plugins.side_effect = mock_extract

        scope_states = {
            DocumentScope.USER: {"plugins": {"plugin1@market1": True, "plugin2@market1": False}},
            DocumentScope.PROJECT: {"plugins": {"plugin2@market1": True, "plugin3@market1": True}},
            DocumentScope.LOCAL: {"plugins": {"plugin1@market1": False}}
        }

        def mock_read_scope_state(workspace_id, scope):
            return scope_states.get(scope, {})

        plugin_loader.settings_service._read_scope_state.side_effect = mock_read_scope_state

        # Act
        result = plugin_loader._get_enabled_plugins("test-workspace")

        # Assert
        # Local 覆盖 Project 覆盖 User
        # plugin1: True (user) -> False (local) = False (不应该在结果中)
        # plugin2: False (user) -> True (project) = True
        # plugin3: True (project) = True
        assert result == {"plugin2@market1": True, "plugin3@market1": True}


class TestGetMarketplaceBasePath:
    """测试获取 marketplace 根目录."""

    def test_get_marketplace_base_path(self, plugin_loader):
        """测试获取 marketplace 根目录."""
        # Arrange
        marketplace_path = Path("/home/user/.claude/plugins/marketplaces/test/.claude-plugin/marketplace.json")

        # Act
        result = plugin_loader._get_marketplace_base_path(marketplace_path)

        # Assert
        # marketplace.json 的父目录是 .claude-plugin，父目录的父目录是 test
        assert result == Path("/home/user/.claude/plugins/marketplaces/test")


class TestScanCommandsStrictMode:
    """测试 strict 模式下的 commands 扫描."""

    def test_scan_commands_strict_mode(self, plugin_loader, tmp_path):
        """测试 strict 模式下扫描 commands."""
        # Arrange
        base_path = tmp_path
        plugin_dir = base_path / "plugin"
        commands_dir = plugin_dir / "commands"
        commands_dir.mkdir(parents=True)

        (commands_dir / "cmd1.md").touch()
        (commands_dir / "cmd2.md").touch()
        (commands_dir / "subdir").mkdir()
        (commands_dir / "subdir" / "cmd3.md").touch()

        plugin_config = {"source": "./plugin", "strict": True}

        # Act
        result = plugin_loader._scan_commands_strict_mode(base_path, plugin_config)

        # Assert
        assert len(result) == 3
        file_names = [f.name for f in result]
        assert "cmd1.md" in file_names
        assert "cmd2.md" in file_names
        assert "cmd3.md" in file_names

    def test_scan_commands_strict_mode_no_commands_dir(self, plugin_loader, tmp_path):
        """测试 strict 模式下无 commands 目录."""
        # Arrange
        base_path = tmp_path
        plugin_dir = base_path / "plugin"
        plugin_dir.mkdir()

        plugin_config = {"source": "./plugin", "strict": True}

        # Act
        result = plugin_loader._scan_commands_strict_mode(base_path, plugin_config)

        # Assert
        assert result == []


class TestScanCommandsListMode:
    """测试 list 模式下的 commands 扫描."""

    def test_scan_commands_list_mode_files(self, plugin_loader, tmp_path):
        """测试 list 模式下扫描文件."""
        # Arrange
        base_path = tmp_path
        (base_path / "cmd1.md").touch()
        (base_path / "cmd2.md").touch()

        plugin_config = {
            "commands": ["./cmd1.md", "./cmd2.md"],
            "strict": False
        }

        # Act
        result = plugin_loader._scan_commands_list_mode(base_path, plugin_config)

        # Assert
        assert len(result) == 2

    def test_scan_commands_list_mode_directory(self, plugin_loader, tmp_path):
        """测试 list 模式下扫描目录."""
        # Arrange
        base_path = tmp_path
        cmd_dir = base_path / "commands"
        cmd_dir.mkdir()
        (cmd_dir / "cmd1.md").touch()
        (cmd_dir / "cmd2.md").touch()

        plugin_config = {
            "commands": ["./commands"],
            "strict": False
        }

        # Act
        result = plugin_loader._scan_commands_list_mode(base_path, plugin_config)

        # Assert
        assert len(result) == 2


class TestLoadPluginCommands:
    """测试加载 plugin commands."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_commands_for_plugin')
    def test_load_plugin_commands_success(
        self, mock_load_for_plugin, mock_get_enabled, plugin_loader
    ):
        """测试成功加载 plugin commands."""
        # Arrange
        mock_get_enabled.return_value = {
            "plugin1@market1": True,
            "plugin2@market1": True
        }
        mock_load_for_plugin.side_effect = [
            [
                ComponentFileInfo(
                    file_path="/path/cmd1.md",
                    file_name="cmd1",
                    plugin_name="plugin1",
                    marketplace_name="market1"
                )
            ],
            [
                ComponentFileInfo(
                    file_path="/path/cmd2.md",
                    file_name="cmd2",
                    plugin_name="plugin2",
                    marketplace_name="market1"
                )
            ]
        ]

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert len(result) == 2
        assert result[0].file_name == "cmd1"
        assert result[1].file_name == "cmd2"

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    def test_load_plugin_commands_empty(self, mock_get_enabled, plugin_loader):
        """测试加载空的 plugin commands."""
        # Arrange
        mock_get_enabled.return_value = {}

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert result == []


class TestLoadPluginAgents:
    """测试加载 plugin agents."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_agents_for_plugin')
    def test_load_plugin_agents_success(
        self, mock_load_for_plugin, mock_get_enabled, plugin_loader
    ):
        """测试成功加载 plugin agents."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.return_value = [
            ComponentFileInfo(
                file_path="/path/agent1.md",
                file_name="agent1",
                plugin_name="plugin1",
                marketplace_name="market1",
                description="Test agent"
            )
        ]

        # Act
        result = plugin_loader.load_plugin_agents("test-workspace")

        # Assert
        assert len(result) == 1
        assert result[0].file_name == "agent1"
        assert result[0].description == "Test agent"


class TestLoadPluginMcpServers:
    """测试加载 plugin MCP servers."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_mcp_for_plugin')
    def test_load_plugin_mcp_servers_success(
        self, mock_load_for_plugin, mock_get_enabled, plugin_loader
    ):
        """测试成功加载 plugin MCP servers."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.return_value = {
            "server1": {"command": "node", "args": ["server.js"]}
        }

        # Act
        result = plugin_loader.load_plugin_mcp_servers("test-workspace")

        # Assert
        assert "plugin1@market1" in result
        assert "server1" in result["plugin1@market1"]


class TestLoadPluginHooks:
    """测试加载 plugin hooks."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_hooks_for_plugin')
    def test_load_plugin_hooks_success(
        self, mock_load_for_plugin, mock_get_enabled, plugin_loader
    ):
        """测试成功加载 plugin hooks."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.return_value = {
            "pre-commit": "echo test"
        }

        # Act
        result = plugin_loader.load_plugin_hooks("test-workspace")

        # Assert
        assert "plugin1@market1" in result
        assert result["plugin1@market1"]["pre-commit"] == "echo test"


class TestLoadPluginSkills:
    """测试加载 plugin skills."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_skills_for_plugin')
    def test_load_plugin_skills_success(
        self, mock_load_for_plugin, mock_get_enabled, plugin_loader
    ):
        """测试成功加载 plugin skills."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.return_value = [
            SkillDirectoryInfo(
                directory_path="/path/to/pdf",
                skill_name="pdf",
                plugin_name="plugin1",
                marketplace_name="market1"
            )
        ]

        # Act
        result = plugin_loader.load_plugin_skills("test-workspace")

        # Assert
        assert len(result) == 1
        assert result[0].skill_name == "pdf"


class TestGetPluginLoaderSingleton:
    """测试 get_plugin_loader 单例模式."""

    @patch('app.modules.claude_code.plugins.loader._loader_instance', None)
    def test_get_plugin_loader_creates_instance(self, mock_settings_service):
        """测试首次调用创建实例."""
        # Act
        loader = get_plugin_loader(mock_settings_service)

        # Assert
        assert loader is not None
        assert isinstance(loader, PluginComponentsLoader)

    @patch('app.modules.claude_code.plugins.loader._loader_instance', None)
    def test_get_plugin_loader_returns_same_instance(self, mock_settings_service):
        """测试多次调用返回相同实例."""
        # Act
        loader1 = get_plugin_loader(mock_settings_service)
        loader2 = get_plugin_loader(mock_settings_service)

        # Assert
        assert loader1 is loader2


class TestLoadPluginCommandsForPlugin:
    """测试加载单个 plugin 的 commands."""

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_scan_commands_strict_mode')
    def test_load_plugin_commands_for_plugin_strict_mode(
        self,
        mock_scan_strict,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试 strict 模式加载单个 plugin 的 commands."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {"name": "test-plugin", "strict": True, "source": "./"}
        mock_get_base.return_value = tmp_path

        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("# Test")
        mock_scan_strict.return_value = [cmd_file]

        # Act
        result = plugin_loader._load_plugin_commands_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert len(result) == 1
        assert result[0].file_name == "test.md"

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_scan_commands_list_mode')
    def test_load_plugin_commands_for_plugin_list_mode(
        self,
        mock_scan_list,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试 list 模式加载单个 plugin 的 commands."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {"name": "test-plugin", "strict": False, "source": "./"}
        mock_get_base.return_value = tmp_path

        cmd_file = tmp_path / "test.md"
        cmd_file.write_text("# Test")
        mock_scan_list.return_value = [cmd_file]

        # Act
        result = plugin_loader._load_plugin_commands_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert len(result) == 1


class TestLoadPluginMcpForPlugin:
    """测试加载单个 plugin 的 MCP 配置."""

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_replace_env_vars')
    def test_load_plugin_mcp_with_config(
        self,
        mock_replace,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试加载包含 MCP 配置的 plugin."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./",
            "mcpServers": {
                "server1": {"command": "node", "args": ["server.js"]}
            }
        }
        mock_get_base.return_value = tmp_path
        mock_replace.side_effect = lambda base, config: config

        # Act
        result = plugin_loader._load_plugin_mcp_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result is not None
        assert "server1" in result

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_resolve_path')
    def test_load_plugin_mcp_from_file(
        self,
        mock_resolve,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试从 .mcp.json 文件加载 MCP 配置."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_get_base.return_value = tmp_path

        source_path = tmp_path / "plugin"
        source_path.mkdir()
        mcp_file = source_path / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {
                "server1": {"command": "node"}
            }
        }))

        mock_resolve.return_value = source_path
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./plugin"
        }

        def read_side_effect(path):
            if str(path).endswith("marketplace.json"):
                return {"plugins": []}
            else:
                with open(path, 'r') as f:
                    return json.load(f)

        mock_read.side_effect = read_side_effect

        # Act
        result = plugin_loader._load_plugin_mcp_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result is not None
        assert "server1" in result

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    def test_load_plugin_mcp_string_reference(
        self,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试 MCP 配置为字符串引用的情况."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_get_base.return_value = tmp_path

        mcp_config_file = tmp_path / "mcp-config.json"
        mcp_config_file.write_text(json.dumps({
            "mcpServers": {
                "server1": {"command": "node"}
            }
        }))

        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./",
            "mcpServers": "./mcp-config.json"
        }

        def read_side_effect(path):
            if str(path).endswith("marketplace.json"):
                return {"plugins": []}
            with open(path, 'r') as f:
                return json.load(f)

        mock_read.side_effect = read_side_effect

        # Act
        result = plugin_loader._load_plugin_mcp_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result is not None


class TestLoadPluginHooksForPlugin:
    """测试加载单个 plugin 的 hooks 配置."""

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_replace_env_vars')
    def test_load_plugin_hooks_with_config(
        self,
        mock_replace,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试加载包含 hooks 配置的 plugin."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./",
            "hooks": {
                "pre-commit": "echo test"
            }
        }
        mock_get_base.return_value = tmp_path
        mock_replace.side_effect = lambda base, config: config

        # Act
        result = plugin_loader._load_plugin_hooks_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result is not None
        assert "pre-commit" in result

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_resolve_path')
    def test_load_plugin_hooks_from_file(
        self,
        mock_resolve,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试从 hooks.json 文件加载 hooks 配置."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_get_base.return_value = tmp_path

        source_path = tmp_path / "plugin"
        source_path.mkdir()
        hooks_dir = source_path / "hooks"
        hooks_dir.mkdir()
        hooks_file = hooks_dir / "hooks.json"
        hooks_file.write_text(json.dumps({
            "hooks": {
                "pre-commit": "echo test"
            }
        }))

        mock_resolve.return_value = source_path
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./plugin"
        }

        def read_side_effect(path):
            if str(path).endswith("marketplace.json"):
                return {"plugins": []}
            else:
                with open(path, 'r') as f:
                    return json.load(f)

        mock_read.side_effect = read_side_effect

        # Act
        result = plugin_loader._load_plugin_hooks_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result is not None


class TestLoadPluginSkillsForPlugin:
    """测试加载单个 plugin 的 skills."""

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    @patch.object(PluginComponentsLoader, '_get_marketplace_base_path')
    @patch.object(PluginComponentsLoader, '_resolve_path')
    def test_load_plugin_skills_for_plugin_success(
        self,
        mock_resolve,
        mock_get_base,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader,
        tmp_path
    ):
        """测试成功加载 plugin skills."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./",
            "skills": ["skills/pdf", "skills/xlsx"]
        }
        mock_get_base.return_value = tmp_path

        skills_path = tmp_path / "skills"
        skills_path.mkdir()

        def resolve_side_effect(base, relative):
            if relative == "./":
                return tmp_path
            else:
                return base / relative.lstrip("./")

        mock_resolve.side_effect = resolve_side_effect

        # Act
        result = plugin_loader._load_plugin_skills_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert len(result) == 2
        assert result[0].skill_name == "pdf"
        assert result[1].skill_name == "xlsx"

    @patch.object(PluginComponentsLoader, '_parse_plugin_id')
    @patch.object(PluginComponentsLoader, '_get_marketplace_path')
    @patch.object(PluginComponentsLoader, '_read_json_file')
    @patch.object(PluginComponentsLoader, '_find_plugin_in_marketplace')
    def test_load_plugin_skills_for_plugin_no_skills(
        self,
        mock_find,
        mock_read,
        mock_get_path,
        mock_parse,
        plugin_loader
    ):
        """测试加载没有 skills 的 plugin."""
        # Arrange
        mock_parse.return_value = ("test-plugin", "test-marketplace")
        mock_get_path.return_value = Path("/path/to/marketplace.json")
        mock_read.return_value = {"plugins": []}
        mock_find.return_value = {
            "name": "test-plugin",
            "source": "./"
        }

        # Act
        result = plugin_loader._load_plugin_skills_for_plugin(
            "workspace-1",
            "test-plugin@test-marketplace"
        )

        # Assert
        assert result == []


class TestErrorHandling:
    """测试错误处理."""

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_commands_for_plugin')
    def test_load_plugin_commands_handles_file_not_found(
        self,
        mock_load_for_plugin,
        mock_get_enabled,
        plugin_loader
    ):
        """测试处理文件未找到错误."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.side_effect = FileNotFoundError("File not found")

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert result == []

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_commands_for_plugin')
    def test_load_plugin_commands_handles_value_error(
        self,
        mock_load_for_plugin,
        mock_get_enabled,
        plugin_loader
    ):
        """测试处理值错误."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.side_effect = ValueError("Invalid value")

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert result == []

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    @patch.object(PluginComponentsLoader, '_load_plugin_commands_for_plugin')
    def test_load_plugin_commands_handles_json_decode_error(
        self,
        mock_load_for_plugin,
        mock_get_enabled,
        plugin_loader
    ):
        """测试处理 JSON 解析错误."""
        # Arrange
        mock_get_enabled.return_value = {"plugin1@market1": True}
        mock_load_for_plugin.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert result == []

    @patch.object(PluginComponentsLoader, '_get_enabled_plugins')
    def test_load_plugin_commands_handles_general_error(
        self,
        mock_get_enabled,
        plugin_loader
    ):
        """测试处理一般错误."""
        # Arrange
        mock_get_enabled.side_effect = Exception("General error")

        # Act
        result = plugin_loader.load_plugin_commands("test-workspace")

        # Assert
        assert result == []
