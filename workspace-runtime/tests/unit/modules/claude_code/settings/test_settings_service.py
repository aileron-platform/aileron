"""Claude Code Settings Service 單元測試"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.modules.claude_code.settings.service import SettingsService
from app.modules.claude_code.settings.models import (
    ClaudeCodeSettings,
    ClaudeCodeSettingsUpdateRequest,
    PermissionMode,
    PermissionRules,
)
from app.modules.claude_code.common import DocumentScope


def _mock_write_json_creates_file(file_path: Path, payload: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def settings_service():
    """Settings service fixture."""
    return SettingsService()


@pytest.fixture
def mock_workspace(tmp_path):
    """創建模擬的 workspace 目錄結構."""
    workspace_id = "test-workspace"

    # 創建目錄結構
    user_root = tmp_path / ".claude"
    project_root = tmp_path / "workspace" / ".claude"

    user_root.mkdir(parents=True, exist_ok=True)
    project_root.mkdir(parents=True, exist_ok=True)

    return workspace_id, tmp_path, user_root, project_root


class TestGetSettings:
    """測試讀取設定功能."""

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    def test_get_settings_default(self, mock_read_json, mock_resolve, settings_service, mock_workspace):
        """測試讀取預設設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}

        # Act
        result = settings_service.get_settings(workspace_id)

        # Assert
        assert result is not None
        assert result.mode == PermissionMode.DEFAULT
        assert result.default_mode == PermissionMode.DEFAULT

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    def test_get_settings_with_mode(self, mock_read_json, mock_resolve, settings_service, mock_workspace):
        """測試讀取帶有 mode 的設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect

        def read_side_effect(path):
            if "settings.json" in str(path):
                return {"defaultMode": "plan"}
            return {}

        mock_read_json.side_effect = read_side_effect

        # Act
        result = settings_service.get_settings(workspace_id)

        # Assert
        assert result.mode == PermissionMode.PLAN

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    def test_get_settings_with_env(self, mock_read_json, mock_resolve, settings_service, mock_workspace):
        """測試讀取包含環境變數的設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect

        def read_side_effect(path):
            if "settings.json" in str(path):
                return {"env": {"API_KEY": "test-key", "DEBUG": "true"}}
            return {}

        mock_read_json.side_effect = read_side_effect

        # Act
        result = settings_service.get_settings(workspace_id)

        # Assert
        assert "API_KEY" in result.env
        assert result.env["API_KEY"] == "test-key"


class TestUpdateSettings:
    """測試更新設定功能."""

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_mode(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 mode 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(mode=PermissionMode.BYPASS_PERMISSIONS)

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called
        assert result.mode == PermissionMode.BYPASS_PERMISSIONS

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_env(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新環境變數設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(env={"NEW_VAR": "new-value"})

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called


class TestSettingsAggregation:
    """測試設定合併功能."""

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    def test_settings_merge_order(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試設定按照正確順序合併（USER < PROJECT < LOCAL）."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect

        def read_side_effect(path):
            path_str = str(path)
            if "settings.local.json" in path_str:
                return {"defaultMode": "acceptEdits"}
            elif "settings.json" in path_str and ".claude" in path_str:
                # Project settings
                return {"defaultMode": "plan"}
            return {}  # User settings

        mock_read_json.side_effect = read_side_effect

        # Act
        result = settings_service.get_settings(workspace_id)

        # Assert
        # LOCAL 應該覆蓋 PROJECT 和 USER
        assert result.mode == PermissionMode.ACCEPT_EDITS


class TestGetMarketplaces:
    """測試讀取 marketplaces 功能."""

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    def test_get_marketplaces_empty(self, mock_resolve, settings_service, mock_workspace):
        """測試讀取空的 marketplaces."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace
        mock_resolve.return_value = user_root

        # Act
        result = settings_service.get_marketplaces(workspace_id)

        # Assert
        assert result is not None
        assert len(result.marketplaces) == 0

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    def test_get_marketplaces_with_data(self, mock_resolve, settings_service, mock_workspace):
        """測試讀取包含數據的 marketplaces."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace
        mock_resolve.return_value = user_root

        # 創建 marketplace 目錄和文件
        marketplace_dir = user_root / "plugins" / "marketplaces" / "test-marketplace"
        marketplace_dir.mkdir(parents=True, exist_ok=True)

        claude_plugin_dir = marketplace_dir / ".claude-plugin"
        claude_plugin_dir.mkdir(parents=True, exist_ok=True)

        marketplace_json = claude_plugin_dir / "marketplace.json"
        marketplace_data = {
            "name": "Test Marketplace",
            "owner": {"name": "Test Owner", "url": "https://example.com"},
            "description": "Test Description",
            "version": "1.0.0",
            "plugins": []
        }
        marketplace_json.write_text(json.dumps(marketplace_data))

        # Act
        result = settings_service.get_marketplaces(workspace_id)

        # Assert
        assert len(result.marketplaces) == 1
        assert result.marketplaces[0].name == "Test Marketplace"


class TestPrivateMethods:
    """測試私有方法."""

    def test_extract_mode_valid(self, settings_service):
        """測試從狀態中提取有效的 mode."""
        # Arrange
        state = {"defaultMode": "plan"}

        # Act
        result = settings_service._extract_mode(state)

        # Assert
        assert result == PermissionMode.PLAN

    def test_extract_mode_invalid(self, settings_service):
        """測試從狀態中提取無效的 mode."""
        # Arrange
        state = {"defaultMode": "invalid-mode"}

        # Act
        result = settings_service._extract_mode(state)

        # Assert
        assert result is None

    def test_normalize_string_list(self, settings_service):
        """測試字串清單正規化."""
        # Arrange
        values = ["tool1", "tool2", "tool1", "", "  tool3  ", None]

        # Act
        result = settings_service._normalize_string_list(values)

        # Assert
        assert result == ["tool1", "tool2", "tool3"]

    def test_extract_enabled_plugins(self, settings_service):
        """測試提取 enabled plugins."""
        # Arrange
        state = {
            "enabledPlugins": {
                "plugin1": True,
                "plugin2": False,
                "  plugin3  ": "yes"  # 應該轉為 True
            }
        }

        # Act
        result = settings_service._extract_enabled_plugins(state)

        # Assert
        assert result["plugin1"] is True
        assert result["plugin2"] is False
        assert result["plugin3"] is True

    def test_extract_model_valid(self, settings_service):
        """測試提取有效的 model."""
        # Arrange
        state = {"model": "claude-3-5-sonnet"}

        # Act
        result = settings_service._extract_model(state)

        # Assert
        assert result == "claude-3-5-sonnet"

    def test_extract_model_empty_string(self, settings_service):
        """測試提取空字串 model."""
        # Arrange
        state = {"model": "  "}

        # Act
        result = settings_service._extract_model(state)

        # Assert
        assert result is None

    def test_extract_permissions_valid(self, settings_service):
        """測試提取有效的 permissions."""
        # Arrange
        state = {
            "permissions": {
                "allow": ["tool1", "tool2"],
                "deny": ["tool3"],
                "ask": ["tool4"]
            }
        }

        # Act
        result = settings_service._extract_permissions(state)

        # Assert
        assert result is not None
        assert result.allow == ["tool1", "tool2"]
        assert result.deny == ["tool3"]
        assert result.ask == ["tool4"]

    def test_extract_permissions_with_additional_directories(self, settings_service):
        """測試提取包含 additionalDirectories 的 permissions."""
        # Arrange
        state = {
            "permissions": {
                "allow": ["tool1"],
                "additionalDirectories": ["/path/to/dir"]
            }
        }

        # Act
        result = settings_service._extract_permissions(state)

        # Assert
        assert result is not None
        assert result.additional_directories == ["/path/to/dir"]

    def test_extract_api_key_helper(self, settings_service):
        """測試提取 API key helper."""
        # Arrange
        state = {"apiKeyHelper": "helper-command"}

        # Act
        result = settings_service._extract_api_key_helper(state)

        # Assert
        assert result == "helper-command"

    def test_extract_api_key_helper_empty(self, settings_service):
        """測試提取空的 API key helper."""
        # Arrange
        state = {"apiKeyHelper": ""}

        # Act
        result = settings_service._extract_api_key_helper(state)

        # Assert
        assert result is None

    def test_extract_cleanup_period(self, settings_service):
        """測試提取 cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": 30}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result == 30

    def test_extract_cleanup_period_zero(self, settings_service):
        """測試提取零值的 cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": 0}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result == 0

    def test_extract_cleanup_period_negative(self, settings_service):
        """測試提取負值的 cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": -1}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result is None

    def test_extract_bool_true(self, settings_service):
        """測試提取布爾值 true."""
        # Arrange
        state = {"includeCoAuthoredBy": True}

        # Act
        result = settings_service._extract_bool(state, "includeCoAuthoredBy")

        # Assert
        assert result is True

    def test_extract_bool_false(self, settings_service):
        """測試提取布爾值 false."""
        # Arrange
        state = {"disableAllHooks": False}

        # Act
        result = settings_service._extract_bool(state, "disableAllHooks")

        # Assert
        assert result is False

    def test_extract_bool_not_present(self, settings_service):
        """測試提取不存在的布爾值."""
        # Arrange
        state = {}

        # Act
        result = settings_service._extract_bool(state, "someKey")

        # Assert
        assert result is None

    def test_extract_string_list(self, settings_service):
        """測試提取字串列表."""
        # Arrange
        state = {"enabledMcpjsonServers": ["server1", "server2"]}

        # Act
        provided, result = settings_service._extract_string_list(state, "enabledMcpjsonServers")

        # Assert
        assert provided is True
        assert result == ["server1", "server2"]

    def test_extract_string_list_not_provided(self, settings_service):
        """測試提取不存在的字串列表."""
        # Arrange
        state = {}

        # Act
        provided, result = settings_service._extract_string_list(state, "enabledMcpjsonServers")

        # Assert
        assert provided is False
        assert result == []

    def test_extract_mcp_policies(self, settings_service):
        """測試提取 MCP policies."""
        # Arrange
        state = {
            "allowedMcpServers": [
                {"serverName": "server1"},
                {"serverName": "server2"}
            ]
        }

        # Act
        provided, result = settings_service._extract_mcp_policies(state, "allowedMcpServers")

        # Assert
        assert provided is True
        assert len(result) == 2
        assert result[0].server_name == "server1"

    def test_extract_mcp_policies_with_duplicates(self, settings_service):
        """測試提取包含重複的 MCP policies."""
        # Arrange
        state = {
            "allowedMcpServers": [
                {"serverName": "server1"},
                {"serverName": "server1"}
            ]
        }

        # Act
        provided, result = settings_service._extract_mcp_policies(state, "allowedMcpServers")

        # Assert
        assert provided is True
        assert len(result) == 1

    def test_extract_mcp_policies_string_format(self, settings_service):
        """測試提取字串格式的 MCP policies."""
        # Arrange
        state = {
            "allowedMcpServers": ["server1", "server2"]
        }

        # Act
        provided, result = settings_service._extract_mcp_policies(state, "allowedMcpServers")

        # Assert
        assert provided is True
        assert len(result) == 2

    def test_settings_file_user_scope(self, settings_service, tmp_path):
        """測試獲取 USER scope 的設定文件路徑."""
        # Arrange
        workspace_id = "test-workspace"

        with patch("app.modules.claude_code.settings.service.resolve_scope_root", return_value=tmp_path):
            # Act
            result = settings_service._settings_file(workspace_id, DocumentScope.USER)

            # Assert
            assert result == tmp_path / "settings.json"

    def test_settings_file_project_scope(self, settings_service, tmp_path):
        """測試獲取 PROJECT scope 的設定文件路徑."""
        # Arrange
        workspace_id = "test-workspace"

        with patch("app.modules.claude_code.settings.service.resolve_scope_root", return_value=tmp_path):
            # Act
            result = settings_service._settings_file(workspace_id, DocumentScope.PROJECT)

            # Assert
            assert result == tmp_path / "settings.json"

    def test_settings_file_local_scope(self, settings_service, tmp_path):
        """測試獲取 LOCAL scope 的設定文件路徑."""
        # Arrange
        workspace_id = "test-workspace"

        with patch("app.modules.claude_code.settings.service.resolve_scope_root", return_value=tmp_path):
            # Act
            result = settings_service._settings_file(workspace_id, DocumentScope.LOCAL)

            # Assert
            assert result == tmp_path / "settings.local.json"


class TestUpdateSettingsAdvanced:
    """測試進階的設定更新功能."""

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_permissions(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 permissions 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(
            permissions=PermissionRules(
                allow=["tool1", "tool2"],
                deny=["tool3"]
            )
        )

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_enabled_plugins(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 enabled plugins 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(
            enabled_plugins={"plugin1@market1": True}
        )

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_output_style(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 output style 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(output_style="concise")

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_model(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 model 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(model="claude-3-5-sonnet")

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    @patch("app.modules.claude_code.settings.service.write_json_file")
    def test_update_settings_mcp_servers(
        self, mock_write_json, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """測試更新 MCP servers 設定."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        from app.modules.claude_code.settings.models import McpServerPolicy

        payload = ClaudeCodeSettingsUpdateRequest(
            allowed_mcp_servers=[McpServerPolicy(server_name="server1")]
        )

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.service.resolve_scope_root")
    @patch("app.modules.claude_code.settings.service.read_json_file")
    def test_update_settings_remove_field(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace, tmp_path
    ):
        """測試移除設定欄位."""
        # Arrange
        workspace_id, _, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {"model": "claude-3-5-sonnet"}

        # Create empty file
        settings_file = user_root / "settings.json"
        settings_file.write_text("{}")

        payload = ClaudeCodeSettingsUpdateRequest(model=None)

        # Act
        result = settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        # File should be updated (model removed)
