"""Installed-root Claude plugin component adapter tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.plugins import loader as loader_module
from app.modules.claude_code.plugins.loader import (
    ComponentFileInfo,
    PluginComponentsLoader,
    SkillDirectoryInfo,
    get_plugin_loader,
)


@pytest.fixture
def settings_service() -> Mock:
    service = Mock()
    service._read_scope_state.return_value = {}
    service._extract_enabled_plugins.return_value = {}
    return service


@pytest.fixture
def plugin_loader(settings_service: Mock, monkeypatch: pytest.MonkeyPatch):
    gate = Mock()
    gate.generation.return_value = 7
    monkeypatch.setattr(
        loader_module,
        "get_marketplace_target_client_gate",
        Mock(return_value=gate),
    )
    return PluginComponentsLoader(settings_service)


def _enable(
    plugin_loader: PluginComponentsLoader,
    plugin_id: str = "demo@registry",
) -> None:
    plugin_loader.settings_service._extract_enabled_plugins.side_effect = (
        lambda state: (state.get("enabledPlugins", {}))
    )
    plugin_loader.settings_service._read_scope_state.side_effect = (
        lambda _workspace_id, scope: (
            {"enabledPlugins": {plugin_id: True}} if scope == DocumentScope.USER else {}
        )
    )


def _installed_plugin(tmp_path: Path) -> Path:
    root = tmp_path / "installed" / "demo"
    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        '{"name":"demo"}',
        encoding="utf-8",
    )
    return root


def test_component_models_keep_consumer_contract() -> None:
    component = ComponentFileInfo(
        file_path="/plugin/commands/review.md",
        file_name="review.md",
        plugin_name="demo",
        marketplace_name="registry",
        description="Review changes",
    )
    skill = SkillDirectoryInfo(
        directory_path="/plugin/skills/pdf",
        skill_name="pdf",
        plugin_name="demo",
        marketplace_name="registry",
    )

    assert component.file_name == "review.md"
    assert component.description == "Review changes"
    assert skill.skill_name == "pdf"


def test_enabled_plugins_follow_claude_scope_precedence(
    plugin_loader: PluginComponentsLoader,
) -> None:
    plugin_loader.settings_service._extract_enabled_plugins.side_effect = (
        lambda state: (state["enabledPlugins"])
    )
    plugin_loader.settings_service._read_scope_state.side_effect = (
        lambda _workspace_id, scope: {
            DocumentScope.USER: {
                "enabledPlugins": {
                    "user-disabled@registry": True,
                    "project-enabled@registry": False,
                }
            },
            DocumentScope.PROJECT: {
                "enabledPlugins": {"project-enabled@registry": True}
            },
            DocumentScope.LOCAL: {"enabledPlugins": {"user-disabled@registry": False}},
        }[scope]
    )

    assert plugin_loader._get_enabled_plugins("workspace-1") == {
        "project-enabled@registry": True
    }


def test_loader_projects_only_provider_reported_installed_root(
    plugin_loader: PluginComponentsLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(plugin_loader)
    installed_root = _installed_plugin(tmp_path)
    command = installed_root / "commands" / "installed.md"
    command.parent.mkdir()
    command.write_text(
        "---\ndescription: Installed command\n---\nBody",
        encoding="utf-8",
    )
    skill = installed_root / "skills" / "pdf" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Skill", encoding="utf-8")

    marketplace_source = tmp_path / "marketplace-source"
    source_command = marketplace_source / "commands" / "source-only.md"
    source_command.parent.mkdir(parents=True)
    source_command.write_text("Must not load", encoding="utf-8")

    monkeypatch.setattr(
        plugin_loader,
        "_plugin_rows",
        Mock(
            return_value=[
                {
                    "id": "demo@registry",
                    "scope": "user",
                    "enabled": True,
                    "installPath": str(installed_root),
                }
            ]
        ),
    )

    commands = plugin_loader.load_plugin_commands("workspace-1")
    skills = plugin_loader.load_plugin_skills("workspace-1")

    assert [item.file_path for item in commands] == [str(command)]
    assert commands[0].description == "Installed command"
    assert [item.directory_path for item in skills] == [str(skill.parent)]
    assert all("marketplace-source" not in item.file_path for item in commands)


def test_loader_uses_canonical_mcp_and_hook_owners(
    plugin_loader: PluginComponentsLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(plugin_loader)
    installed_root = _installed_plugin(tmp_path)
    (installed_root / ".mcp.json").write_text(
        json.dumps(
            {
                "server": {
                    "command": "${CLAUDE_PLUGIN_ROOT}/bin/server",
                }
            }
        ),
        encoding="utf-8",
    )
    hooks = installed_root / "hooks" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(
        '{"hooks":{"PreToolUse":[{"hooks":[]}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        plugin_loader,
        "_plugin_rows",
        Mock(
            return_value=[
                {
                    "id": "demo@registry",
                    "enabled": True,
                    "installPath": str(installed_root),
                }
            ]
        ),
    )

    mcp_servers = plugin_loader.load_plugin_mcp_servers("workspace-1")
    plugin_hooks = plugin_loader.load_plugin_hooks("workspace-1")

    assert (
        mcp_servers["demo@registry"]["server"]["command"]
        == "${CLAUDE_PLUGIN_ROOT}/bin/server"
    )
    assert set(plugin_hooks["demo@registry"]) == {"PreToolUse"}


def test_loader_projects_output_styles_from_installed_root(
    plugin_loader: PluginComponentsLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(plugin_loader)
    installed_root = _installed_plugin(tmp_path)
    output_style = installed_root / "output-styles" / "calm.md"
    output_style.parent.mkdir()
    output_style.write_text(
        "---\ndescription: Calm output\n---\n# Calm",
        encoding="utf-8",
    )
    for nested_directory in ("a", "b"):
        nested_style = installed_root / "output-styles" / nested_directory / "style.md"
        nested_style.parent.mkdir()
        nested_style.write_text(
            f"# {nested_directory.upper()}",
            encoding="utf-8",
        )
    monkeypatch.setattr(
        plugin_loader,
        "_plugin_rows",
        Mock(
            return_value=[
                {
                    "id": "demo@registry",
                    "enabled": True,
                    "installPath": str(installed_root),
                }
            ]
        ),
    )

    styles = plugin_loader.load_plugin_output_styles("workspace-1")
    styles_by_locator = {item.relative_source_path: item for item in styles}
    assert set(styles_by_locator) == {
        "output-styles/a/style.md",
        "output-styles/b/style.md",
        "output-styles/calm.md",
    }
    assert styles_by_locator["output-styles/calm.md"].plugin_id == "demo@registry"
    assert styles_by_locator["output-styles/calm.md"].file_path == str(output_style)
    assert (
        styles_by_locator["output-styles/a/style.md"].file_name
        == styles_by_locator["output-styles/b/style.md"].file_name
        == "style.md"
    )


def test_loader_rejects_invalid_installed_manifest_resources(
    plugin_loader: PluginComponentsLoader,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(plugin_loader)
    installed_root = _installed_plugin(tmp_path)
    (installed_root / ".claude-plugin" / "plugin.json").write_text(
        '{"name":"demo","commands":"../outside"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        plugin_loader,
        "_plugin_rows",
        Mock(
            return_value=[
                {
                    "id": "demo@registry",
                    "enabled": True,
                    "installPath": str(installed_root),
                }
            ]
        ),
    )

    with pytest.raises(ValueError, match="Invalid installed plugin resources"):
        plugin_loader.load_plugin_commands("workspace-1")


def test_plugin_rows_accepts_cli_object_shape(
    plugin_loader: PluginComponentsLoader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = Mock(
        returncode=0,
        stdout='{"plugins":[{"id":"demo@registry"}]}',
        stderr="",
    )
    monkeypatch.setattr(loader_module.subprocess, "run", Mock(return_value=completed))

    assert plugin_loader._plugin_rows() == [{"id": "demo@registry"}]


@pytest.mark.parametrize(
    "plugin_id",
    ["demo", "demo@registry@extra", "@registry", "demo@"],
)
def test_plugin_id_requires_exact_provider_identity(
    plugin_loader: PluginComponentsLoader,
    plugin_id: str,
) -> None:
    with pytest.raises(ValueError):
        plugin_loader._parse_plugin_id(plugin_id)


def test_global_loader_is_thread_safe_singleton(settings_service: Mock) -> None:
    original = loader_module._loader_instance
    loader_module._loader_instance = None
    try:
        first = get_plugin_loader(settings_service)
        second = get_plugin_loader(Mock())
    finally:
        loader_module._loader_instance = original

    assert first is second
