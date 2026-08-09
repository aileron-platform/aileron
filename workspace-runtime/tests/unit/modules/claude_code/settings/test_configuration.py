"""Claude Code Settings Service unit tests"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.claude_code.settings.configuration import SettingsService
from app.modules.claude_code.settings.models import (
    ClaudeCodeSettingsUpdateRequest,
    PermissionMode,
    PermissionRules,
)
from app.modules.claude_code.documents import DocumentScope


def _mock_write_json_creates_file(file_path: Path, payload: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def settings_service():
    """Settings service fixture."""
    return SettingsService()


@pytest.fixture
def mock_workspace(tmp_path, monkeypatch):
    """Create mock workspace directory structure."""
    workspace_id = "test-workspace"
    monkeypatch.setenv("HOME", str(tmp_path))

    # Create directory structure
    user_root = tmp_path / ".claude"
    project_root = tmp_path / "workspace" / ".claude"

    user_root.mkdir(parents=True, exist_ok=True)
    project_root.mkdir(parents=True, exist_ok=True)

    return workspace_id, tmp_path, user_root, project_root


class TestGetSettings:
    """Test settings reading functionality."""

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_get_settings_default(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test reading default settings."""
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

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_get_settings_with_mode(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test reading settings with mode."""
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

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_get_settings_with_env(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test reading settings with environment variables."""
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
    """Test settings update functionality."""

    def test_update_settings_revision_conflict(
        self, settings_service, tmp_path, monkeypatch
    ):
        """Test stale revision is rejected before writing settings."""
        workspace_id = "test-workspace"
        monkeypatch.setenv("HOME", str(tmp_path))
        settings_file = tmp_path / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings_file.write_text('{"model":"claude-old"}', encoding="utf-8")

        current = settings_service.get_settings(workspace_id, DocumentScope.USER)
        assert current.revision == compute_revision('{"model":"claude-old"}')

        payload = ClaudeCodeSettingsUpdateRequest(model="claude-new", revision="stale")

        with pytest.raises(HTTPException) as exc:
            settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        assert exc.value.status_code == 409
        assert exc.value.detail["errorCode"] == "REVISION_CONFLICT"
        assert settings_file.read_text(encoding="utf-8") == '{"model":"claude-old"}'

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_mode(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating mode settings."""
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

        payload = ClaudeCodeSettingsUpdateRequest(
            mode=PermissionMode.BYPASS_PERMISSIONS
        )

        # Act
        result = settings_service.update_settings(
            workspace_id, payload, DocumentScope.USER
        )

        # Assert
        assert mock_write_json.called
        assert result.mode == PermissionMode.BYPASS_PERMISSIONS

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_env(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating environment variable settings."""
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
        settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called


class TestRawSettings:
    """Test raw settings passthrough functionality."""

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_get_raw_settings_returns_file_content(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test reading raw settings content from a scope file."""
        workspace_id, _tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {
            "model": "claude-sonnet-5",
            "unknownField": {"nested": True},
        }

        result = settings_service.get_raw_settings(workspace_id, DocumentScope.LOCAL)

        assert result == {
            "model": "claude-sonnet-5",
            "unknownField": {"nested": True},
        }
        mock_read_json.assert_called_once_with(project_root / "settings.local.json")

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_get_raw_settings_returns_empty_object_when_missing(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test missing raw settings file returns empty content."""
        workspace_id, _tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}

        result = settings_service.get_raw_settings(workspace_id, DocumentScope.PROJECT)

        assert result == {}
        mock_read_json.assert_called_once_with(project_root / "settings.json")

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_raw_settings_writes_content(
        self, mock_write_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test raw settings update writes the provided content unchanged."""
        workspace_id, _tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        content = {"env": {"DEBUG": "1"}, "unknownField": [1, 2, 3]}

        result = settings_service.update_raw_settings(
            workspace_id, DocumentScope.USER, content
        )

        assert result == content
        mock_write_json.assert_called_once_with(user_root / "settings.json", content)

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_raw_settings_empty_content_deletes_file(
        self, mock_write_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test empty raw settings content removes the scope file."""
        workspace_id, _tmp_path, user_root, project_root = mock_workspace
        settings_file = project_root / "settings.local.json"
        settings_file.write_text('{"model": "old"}', encoding="utf-8")

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect

        result = settings_service.update_raw_settings(
            workspace_id, DocumentScope.LOCAL, {}
        )

        assert result == {}
        assert not settings_file.exists()
        mock_write_json.assert_not_called()


class TestSettingsAggregation:
    """Test settings merge functionality."""

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_settings_merge_order(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace
    ):
        """Test settings merge in correct order (USER < PROJECT < LOCAL)."""
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
        # LOCAL should override PROJECT and USER
        assert result.mode == PermissionMode.ACCEPT_EDITS


class TestPrivateMethods:
    """Test private methods."""

    def test_extract_mode_valid(self, settings_service):
        """Test extracting valid mode from state."""
        # Arrange
        state = {"defaultMode": "plan"}

        # Act
        result = settings_service._extract_mode(state)

        # Assert
        assert result == PermissionMode.PLAN

    def test_extract_mode_invalid(self, settings_service):
        """Test extracting invalid mode from state."""
        # Arrange
        state = {"defaultMode": "invalid-mode"}

        # Act
        result = settings_service._extract_mode(state)

        # Assert
        assert result is None

    def test_normalize_string_list(self, settings_service):
        """Test string list normalization."""
        # Arrange
        values = ["tool1", "tool2", "tool1", "", "  tool3  ", None]

        # Act
        result = settings_service._normalize_string_list(values)

        # Assert
        assert result == ["tool1", "tool2", "tool3"]

    def test_extract_enabled_plugins(self, settings_service):
        """Test extracting enabled plugins."""
        # Arrange
        state = {
            "enabledPlugins": {
                "plugin1": True,
                "plugin2": False,
                "  plugin3  ": "yes",  # Should convert to True
            }
        }

        # Act
        result = settings_service._extract_enabled_plugins(state)

        # Assert
        assert result["plugin1"] is True
        assert result["plugin2"] is False
        assert result["plugin3"] is True

    def test_extract_model_valid(self, settings_service):
        """Test extracting valid model."""
        # Arrange
        state = {"model": "claude-sonnet-5"}

        # Act
        result = settings_service._extract_model(state)

        # Assert
        assert result == "claude-sonnet-5"

    def test_extract_model_empty_string(self, settings_service):
        """Test extracting empty string model."""
        # Arrange
        state = {"model": "  "}

        # Act
        result = settings_service._extract_model(state)

        # Assert
        assert result is None

    def test_extract_permissions_valid(self, settings_service):
        """Test extracting valid permissions."""
        # Arrange
        state = {
            "permissions": {
                "allow": ["tool1", "tool2"],
                "deny": ["tool3"],
                "ask": ["tool4"],
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
        """Test extracting permissions with additionalDirectories."""
        # Arrange
        state = {
            "permissions": {
                "allow": ["tool1"],
                "additionalDirectories": ["/path/to/dir"],
            }
        }

        # Act
        result = settings_service._extract_permissions(state)

        # Assert
        assert result is not None
        assert result.additional_directories == ["/path/to/dir"]

    def test_extract_api_key_helper(self, settings_service):
        """Test extracting API key helper."""
        # Arrange
        state = {"apiKeyHelper": "helper-command"}

        # Act
        result = settings_service._extract_api_key_helper(state)

        # Assert
        assert result == "helper-command"

    def test_extract_api_key_helper_empty(self, settings_service):
        """Test extracting empty API key helper."""
        # Arrange
        state = {"apiKeyHelper": ""}

        # Act
        result = settings_service._extract_api_key_helper(state)

        # Assert
        assert result is None

    def test_extract_cleanup_period(self, settings_service):
        """Test extracting cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": 30}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result == 30

    def test_extract_cleanup_period_zero(self, settings_service):
        """Test extracting zero value cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": 0}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result == 0

    def test_extract_cleanup_period_negative(self, settings_service):
        """Test extracting negative value cleanup period."""
        # Arrange
        state = {"cleanupPeriodDays": -1}

        # Act
        result = settings_service._extract_cleanup_period(state)

        # Assert
        assert result is None

    def test_extract_bool_true(self, settings_service):
        """Test extracting boolean value true."""
        # Arrange
        state = {"includeCoAuthoredBy": True}

        # Act
        result = settings_service._extract_bool(state, "includeCoAuthoredBy")

        # Assert
        assert result is True

    def test_extract_bool_false(self, settings_service):
        """Test extracting boolean value false."""
        # Arrange
        state = {"disableAllHooks": False}

        # Act
        result = settings_service._extract_bool(state, "disableAllHooks")

        # Assert
        assert result is False

    def test_extract_bool_not_present(self, settings_service):
        """Test extracting non-existent boolean value."""
        # Arrange
        state = {}

        # Act
        result = settings_service._extract_bool(state, "someKey")

        # Assert
        assert result is None

    def test_extract_string_list(self, settings_service):
        """Test extracting string list."""
        # Arrange
        state = {"enabledMcpjsonServers": ["server1", "server2"]}

        # Act
        provided, result = settings_service._extract_string_list(
            state, "enabledMcpjsonServers"
        )

        # Assert
        assert provided is True
        assert result == ["server1", "server2"]

    def test_extract_string_list_not_provided(self, settings_service):
        """Test extracting non-existent string list."""
        # Arrange
        state = {}

        # Act
        provided, result = settings_service._extract_string_list(
            state, "enabledMcpjsonServers"
        )

        # Assert
        assert provided is False
        assert result == []

    def test_extract_mcp_policies(self, settings_service):
        """Test extracting MCP policies."""
        # Arrange
        state = {
            "allowedMcpServers": [{"serverName": "server1"}, {"serverName": "server2"}]
        }

        # Act
        provided, result = settings_service._extract_mcp_policies(
            state, "allowedMcpServers"
        )

        # Assert
        assert provided is True
        assert len(result) == 2
        assert result[0].server_name == "server1"

    def test_extract_mcp_policies_with_duplicates(self, settings_service):
        """Test extracting MCP policies with duplicates."""
        # Arrange
        state = {
            "allowedMcpServers": [{"serverName": "server1"}, {"serverName": "server1"}]
        }

        # Act
        provided, result = settings_service._extract_mcp_policies(
            state, "allowedMcpServers"
        )

        # Assert
        assert provided is True
        assert len(result) == 1

    def test_extract_mcp_policies_string_format(self, settings_service):
        """Test extracting string format MCP policies."""
        # Arrange
        state = {"allowedMcpServers": ["server1", "server2"]}

        # Act
        provided, result = settings_service._extract_mcp_policies(
            state, "allowedMcpServers"
        )

        # Assert
        assert provided is True
        assert len(result) == 2

    def test_settings_file_user_scope(self, settings_service, tmp_path, monkeypatch):
        """Test getting settings file path for USER scope."""
        workspace_id = "test-workspace"
        monkeypatch.setenv("HOME", str(tmp_path))

        result = settings_service._settings_file(workspace_id, DocumentScope.USER)

        assert result == tmp_path / ".claude" / "settings.json"

    def test_settings_file_project_scope(self, settings_service, tmp_path):
        """Test getting settings file path for PROJECT scope."""
        # Arrange
        workspace_id = "test-workspace"

        with patch(
            "app.modules.claude_code.settings.configuration.resolve_scope_root",
            return_value=tmp_path,
        ):
            # Act
            result = settings_service._settings_file(
                workspace_id, DocumentScope.PROJECT
            )

            # Assert
            assert result == tmp_path / "settings.json"

    def test_settings_file_local_scope(self, settings_service, tmp_path):
        """Test getting settings file path for LOCAL scope."""
        # Arrange
        workspace_id = "test-workspace"

        with patch(
            "app.modules.claude_code.settings.configuration.resolve_scope_root",
            return_value=tmp_path,
        ):
            # Act
            result = settings_service._settings_file(workspace_id, DocumentScope.LOCAL)

            # Assert
            assert result == tmp_path / "settings.local.json"


class TestUpdateSettingsAdvanced:
    """Test advanced settings update functionality."""

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_permissions(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating permissions settings."""
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
            permissions=PermissionRules(allow=["tool1", "tool2"], deny=["tool3"])
        )

        # Act
        settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_enabled_plugins(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating enabled plugins settings."""
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
        settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_output_style(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating output style settings."""
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
        settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_model(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating model settings."""
        # Arrange
        workspace_id, tmp_path, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {}
        mock_write_json.side_effect = _mock_write_json_creates_file

        payload = ClaudeCodeSettingsUpdateRequest(model="claude-sonnet-5")

        # Act
        settings_service.update_settings(workspace_id, payload, DocumentScope.PROJECT)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    @patch("app.modules.claude_code.settings.configuration.write_json_file")
    def test_update_settings_mcp_servers(
        self,
        mock_write_json,
        mock_read_json,
        mock_resolve,
        settings_service,
        mock_workspace,
    ):
        """Test updating MCP servers settings."""
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
        settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        assert mock_write_json.called

    @patch("app.modules.claude_code.settings.configuration.resolve_scope_root")
    @patch("app.modules.claude_code.settings.configuration.read_json_file")
    def test_update_settings_remove_field(
        self, mock_read_json, mock_resolve, settings_service, mock_workspace, tmp_path
    ):
        """Test removing settings field."""
        # Arrange
        workspace_id, _, user_root, project_root = mock_workspace

        def resolve_side_effect(wid, scope):
            if scope == DocumentScope.USER:
                return user_root
            return project_root

        mock_resolve.side_effect = resolve_side_effect
        mock_read_json.return_value = {"model": "claude-sonnet-5"}

        # Create empty file
        settings_file = user_root / "settings.json"
        settings_file.write_text("{}")

        payload = ClaudeCodeSettingsUpdateRequest(model=None)

        # Act
        settings_service.update_settings(workspace_id, payload, DocumentScope.USER)

        # Assert
        # File should be updated (model removed)
