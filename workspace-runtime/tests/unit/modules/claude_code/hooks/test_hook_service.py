"""Hook Service unit tests"""

from __future__ import annotations

import pytest
import sys
from types import ModuleType
from unittest.mock import patch, MagicMock

from fastapi import HTTPException

from app.modules.claude_code.hooks.service import HookService
from app.modules.claude_code.hooks.models import (
    HookScopeUpsertRequest,
    HookRule,
    HookAction,
    HookActionType,
    HookImportMode,
    HookImportRequest,
    HookScopeDocument,
)
from app.modules.claude_code.common import DocumentScope


@pytest.fixture
def hook_service():
    """Hook service fixture."""
    return HookService()


@pytest.fixture
def tmp_workspace(tmp_path):
    "Create temporary workspace directory structure."
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    project_root = workspace_root / ".claude"
    project_root.mkdir(parents=True, exist_ok=True)

    return workspace_root, project_root


class TestListScopes:
    """Test listing hooks functionality."""

    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    @patch.object(HookService, "_load_plugin_hooks")
    def test_list_scopes_all(
        self, mock_load_plugins, mock_resolve, mock_read_json, hook_service, tmp_path
    ):
        """Test listing all scope hooks."""
        # Arrange
        workspace_id = "test-workspace"
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {"hooks": {}}
        mock_load_plugins.return_value = {}

        # Act
        result = hook_service.list_scopes(workspace_id, None)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert len(result.scopes) >= 0

    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_list_scopes_project_only(
        self, mock_resolve, mock_read_json, hook_service, tmp_path
    ):
        """Test listing only project scope hooks."""
        # Arrange
        workspace_id = "test-workspace"
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {"hooks": {}}

        # Act
        result = hook_service.list_scopes(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert len(result.scopes) >= 0

    @patch.object(HookService, "_load_plugin_hooks")
    @patch.object(HookService, "_build_plugin_sources")
    def test_list_scopes_plugin_only(self, mock_sources, mock_load_plugins, hook_service):
        mock_load_plugins.return_value = {"PreToolUse": []}
        mock_sources.return_value = {"PreToolUse:0": "demo@market"}

        result = hook_service.list_scopes("test-workspace", DocumentScope.PLUGIN)

        assert len(result.scopes) == 1
        assert result.scopes[0].scope == DocumentScope.PLUGIN
        assert result.scopes[0].plugin_sources == {"PreToolUse:0": "demo@market"}

    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    @patch.object(HookService, "_load_plugin_hooks")
    def test_list_scopes_plugin_failure_returns_base_scopes(
        self, mock_load_plugins, mock_resolve, mock_read_json, hook_service, tmp_path
    ):
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {"hooks": {}}
        mock_load_plugins.side_effect = RuntimeError("plugin load failed")

        result = hook_service.list_scopes("test-workspace", None)

        assert len(result.scopes) == 3


class TestGetScope:
    """Test getting specific scope hooks."""

    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_get_scope_success(self, mock_resolve, mock_read_json, hook_service, tmp_path):
        """Test successfully getting scope."""
        # Arrange
        workspace_id = "test-workspace"
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {
            "hooks": {
                "test-hook": [
                    {
                        "matcher": "user_prompt_submit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo test"
                            }
                        ]
                    }
                ]
            }
        }

        # Act
        result = hook_service.get_scope(workspace_id, DocumentScope.PROJECT)

        # Assert
        assert result is not None
        assert result.workspace_id == workspace_id
        assert result.scope == DocumentScope.PROJECT

    @patch.object(HookService, "_load_plugin_hooks")
    def test_get_scope_plugin(self, mock_load_plugins, hook_service):
        mock_load_plugins.return_value = {"PreToolUse": []}

        result = hook_service.get_scope("test-workspace", DocumentScope.PLUGIN)

        assert result.scope == DocumentScope.PLUGIN
        assert result.hooks == {"PreToolUse": []}


class TestUpdateScope:
    """Test updating hooks."""

    @patch("app.modules.claude_code.hooks.service.write_json_file")
    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_update_scope_success(
        self, mock_resolve, mock_read_json, mock_write_json, hook_service, tmp_path
    ):
        """Test successfully updating hooks."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {}

        hook_action = HookAction(
            type=HookActionType.COMMAND,
            command="echo test"
        )
        hook_rule = HookRule(
            matcher="user_prompt_submit",
            hooks=[hook_action]
        )
        payload = HookScopeUpsertRequest(
            hooks={
                "test-hook": [hook_rule]
            }
        )

        # Act
        result = hook_service.update_scope(workspace_id, scope, payload)

        # Assert
        assert result is not None
        assert mock_write_json.called

    def test_update_scope_plugin_read_only(self, hook_service):
        payload = HookScopeUpsertRequest(hooks={})

        with pytest.raises(HTTPException) as exc:
            hook_service.update_scope("test-workspace", DocumentScope.PLUGIN, payload)

        assert exc.value.status_code == 403


class TestDeleteScope:
    """Test deleting scope."""

    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_delete_scope_success(
        self, mock_resolve, hook_service, tmp_path
    ):
        """Test successfully deleting scope."""
        # Arrange
        workspace_id = "test-workspace"
        scope = DocumentScope.PROJECT
        hooks_file = tmp_path / "hooks.json"
        hooks_file.write_text('{"hooks": {}}')
        mock_resolve.return_value = tmp_path

        # Act
        result = hook_service.delete_scope(workspace_id, scope)

        # Assert
        assert result is not None
        assert result.deleted is True

    def test_delete_scope_plugin_read_only(self, hook_service):
        with pytest.raises(HTTPException) as exc:
            hook_service.delete_scope("test-workspace", DocumentScope.PLUGIN)

        assert exc.value.status_code == 403


class TestExportScopes:
    """Test exporting hooks."""

    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_export_scopes_success(self, mock_resolve, mock_read_json, hook_service, tmp_path):
        """Test successfully exporting hooks."""
        # Arrange
        workspace_id = "test-workspace"
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {
            "hooks": {
                "test-hook": [
                    {
                        "matcher": "user_prompt_submit",
                        "hooks": [
                            {
                                "type": "command",
                                "command": "echo test"
                            }
                        ]
                    }
                ]
            }
        }

        # Act
        result = hook_service.export_scopes(workspace_id, [DocumentScope.PROJECT])

        # Assert
        assert result is not None


class TestImportScopes:
    """Test importing hooks."""

    @patch("app.modules.claude_code.hooks.service.write_json_file")
    @patch("app.modules.claude_code.hooks.service.read_json_file")
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_import_scopes_success(
        self, mock_resolve, mock_read_json, mock_write_json, hook_service, tmp_path
    ):
        """Test successfully importing hooks."""
        # Arrange
        workspace_id = "test-workspace"
        mock_resolve.return_value = tmp_path
        mock_read_json.return_value = {}

        from app.modules.claude_code.hooks.models import (
            HookImportRequest,
            HookImportMode,
            HookScopeDocument,
        )

        scope_doc = HookScopeDocument(
            scope=DocumentScope.PROJECT,
            hooks={
                "test-hook": [
                    HookRule(
                        matcher="user_prompt_submit",
                        hooks=[
                            HookAction(
                                type=HookActionType.COMMAND,
                                command="echo test"
                            )
                        ]
                    )
                ]
            }
        )

        import_data = HookImportRequest(
            mode=HookImportMode.MERGE,
            scopes=[scope_doc]
        )

        # Act
        result = hook_service.import_scopes(workspace_id, import_data)

        # Assert
        assert result is not None

    @patch.object(HookService, "_load_scope_document")
    @patch.object(HookService, "_write_scope")
    def test_import_scopes_merge_skip_and_replace_counts(
        self, mock_write_scope, mock_load_scope_document, hook_service
    ):
        rule = HookRule(
            matcher="user_prompt_submit",
            hooks=[HookAction(type=HookActionType.COMMAND, command="echo test")],
        )
        existing = HookScopeDocument(scope=DocumentScope.PROJECT, hooks={"event": [rule]})
        empty = HookScopeDocument(scope=DocumentScope.USER, hooks={})
        mock_load_scope_document.side_effect = [existing, empty]

        merge_request = HookImportRequest(
            mode=HookImportMode.MERGE,
            scopes=[
                HookScopeDocument(scope=DocumentScope.PROJECT, hooks={"event": [rule]}),
                HookScopeDocument(scope=DocumentScope.USER, hooks={"new": [rule]}),
            ],
        )
        result = hook_service.import_scopes("test-workspace", merge_request)

        assert result.imported == 1
        assert result.updated == 0
        assert result.skipped == 1
        assert mock_write_scope.call_count == 1

    @patch.object(HookService, "_load_scope_document")
    @patch.object(HookService, "_write_scope")
    def test_import_scopes_replace_updates_existing(
        self, mock_write_scope, mock_load_scope_document, hook_service
    ):
        rule = HookRule(
            matcher="user_prompt_submit",
            hooks=[HookAction(type=HookActionType.COMMAND, command="echo test")],
        )
        mock_load_scope_document.return_value = HookScopeDocument(
            scope=DocumentScope.PROJECT,
            hooks={"old": [rule]},
        )

        request = HookImportRequest(
            mode=HookImportMode.REPLACE,
            scopes=[HookScopeDocument(scope=DocumentScope.PROJECT, hooks={"new": [rule]})],
        )
        result = hook_service.import_scopes("test-workspace", request)

        assert result.imported == 0
        assert result.updated == 1
        assert result.skipped == 0
        mock_write_scope.assert_called_once()


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self):
        """Test service initialization."""
        # Act
        service = HookService()

        # Assert
        assert service is not None


class TestHookServiceInternals:
    @patch("app.modules.claude_code.hooks.service.resolve_scope_root")
    def test_scope_file_uses_hooks_json_for_writable_claude_scopes(
        self, mock_resolve, hook_service, tmp_path
    ):
        mock_resolve.return_value = tmp_path

        assert hook_service._scope_file("test-workspace", DocumentScope.PROJECT) == tmp_path / "hooks.json"
        assert hook_service._scope_file("test-workspace", DocumentScope.USER) == tmp_path / "hooks.json"
        assert hook_service._scope_file("test-workspace", DocumentScope.LOCAL) == tmp_path / "settings.local.json"

    def test_scope_file_rejects_plugin_scope(self, hook_service):
        with pytest.raises(HTTPException) as exc:
            hook_service._scope_file("test-workspace", DocumentScope.PLUGIN)

        assert exc.value.status_code == 400

    def test_merge_hooks_and_build_plugin_sources(self, hook_service):
        current_rule = HookRule(
            matcher="a",
            hooks=[HookAction(type=HookActionType.COMMAND, command="echo a")],
        )
        plugin_rule = HookRule(
            matcher="b",
            hooks=[HookAction(type=HookActionType.COMMAND, command="echo b")],
            pluginName="demo",
            marketplaceName="market",
        )

        merged = hook_service._merge_hooks({"one": [current_rule]}, {"two": [plugin_rule]})
        sources = hook_service._build_plugin_sources({"two": [plugin_rule]})

        assert set(merged.keys()) == {"one", "two"}
        assert sources == {"two:0": "demo@market"}

    def test_load_plugin_hooks_merges_plugin_metadata(self, hook_service, monkeypatch):
        loader = MagicMock()
        loader.load_plugin_hooks.return_value = {
            "demo@market": {
                "PreToolUse": [
                    {
                        "matcher": "x",
                        "hooks": [{"type": "command", "command": "echo x"}],
                    }
                ]
            }
        }
        fake_loader_module = ModuleType("app.modules.claude_code.plugins.loader")
        fake_loader_module.get_plugin_loader = lambda settings_service: loader
        fake_settings_module = ModuleType("app.modules.claude_code.settings.dependencies")
        fake_settings_module.get_settings_service = lambda: MagicMock()
        monkeypatch.setitem(sys.modules, "app.modules.claude_code.plugins.loader", fake_loader_module)
        monkeypatch.setitem(sys.modules, "app.modules.claude_code.settings.dependencies", fake_settings_module)

        hooks = hook_service._load_plugin_hooks("ws-1")

        assert list(hooks.keys()) == ["PreToolUse"]
        assert hooks["PreToolUse"][0].plugin_name == "demo"
        assert hooks["PreToolUse"][0].marketplace_name == "market"
