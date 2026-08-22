from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

from aileron_marketplace_core import resolve_user_copy_profile

from app.config.settings import Settings
from app.modules.claude_code.plugins.catalog import ClaudePluginsService
from app.modules.cli_settings.codex.plugin_resources import (
    CodexPluginResourceResolver,
)
from app.modules.cli_settings.user_scope.paths import CodexPathResolver
from app.modules.marketplace_operations import inventory as inventory_module
from app.modules.marketplace_operations.inventory import (
    FilesystemUserCopyInventoryReader,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        ENV="test",
        AILERON_WORKSPACE_ID="workspace-1",
        AILERON_WORKSPACE_PATH=str(tmp_path / "workspace"),
        MARKETPLACE_OPERATION_JOURNAL_DIR=str(tmp_path / "state"),
    )


def _codex_profile(tmp_path: Path):
    package_root = tmp_path / "package"
    (package_root / ".codex-plugin").mkdir(parents=True)
    (package_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"review-helper"}',
        encoding="utf-8",
    )
    (package_root / "AGENTS.md").write_text(
        "# Review helper\n",
        encoding="utf-8",
    )
    return resolve_user_copy_profile("codex-native", package_root)


def test_project_identity_inventory_blocks_same_codex_instructions(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    workspace_root = Path(settings.AILERON_WORKSPACE_PATH)
    workspace_root.mkdir(parents=True)
    (workspace_root / "AGENTS.md").write_text(
        "# Existing project instructions\n",
        encoding="utf-8",
    )
    target_client = FilesystemUserCopyInventoryReader(settings)
    monkeypatch.setattr(
        target_client,
        "_enabled_codex_plugin_roots",
        lambda _toml_documents: (),
    )

    inventory = target_client.inventory(
        "codex",
        profile=_codex_profile(tmp_path),
    )

    assert inventory.complete is True
    assert [
        (
            identity.resource_type,
            identity.resource_id,
            identity.scope,
        )
        for identity in inventory.effective_identities
    ] == [("instructions", "root-instructions", "project")]


def test_invalid_project_config_makes_inventory_incomplete(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    project_root = Path(settings.AILERON_WORKSPACE_PATH) / ".codex"
    project_root.mkdir(parents=True)
    (project_root / "config.toml").write_text(
        "invalid = [",
        encoding="utf-8",
    )
    target_client = FilesystemUserCopyInventoryReader(settings)
    monkeypatch.setattr(
        target_client,
        "_enabled_codex_plugin_roots",
        lambda _toml_documents: (),
    )

    inventory = target_client.inventory(
        "codex",
        profile=_codex_profile(tmp_path),
    )

    assert inventory.complete is False


def test_claude_local_inventory_uses_dynamic_home_resolver(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    workspace_root = Path(settings.AILERON_WORKSPACE_PATH)
    workspace_root.mkdir(parents=True)
    runtime_home = tmp_path / "dynamic-runtime-home"
    runtime_home.mkdir()
    monkeypatch.setenv("HOME", str(runtime_home))
    package_root = tmp_path / "claude-package"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "review-helper",
                "mcpServers": {
                    "review": {
                        "command": "review-server",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (runtime_home / ".claude.json").write_text(
        json.dumps(
            {
                "projects": {
                    str(workspace_root): {
                        "mcpServers": {
                            "review": {
                                "command": "existing-server",
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    target_client = FilesystemUserCopyInventoryReader(settings)
    monkeypatch.setattr(target_client, "_enabled_claude_plugin_roots", lambda: ())

    inventory = target_client.inventory(
        "claude-code",
        profile=resolve_user_copy_profile("claude-native", package_root),
    )

    assert inventory.complete is True
    assert [
        (
            identity.resource_type,
            identity.resource_id,
            identity.scope,
        )
        for identity in inventory.effective_identities
    ] == [("mcp", "review", "local")]


def test_claude_plugin_inventory_accepts_missing_manifest_without_public_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    Path(settings.AILERON_WORKSPACE_PATH).mkdir(parents=True)
    installed_root = tmp_path / "home" / ".claude" / "plugins" / "cache" / "review"
    installed_skill = installed_root / "skills" / "review" / "SKILL.md"
    installed_skill.parent.mkdir(parents=True)
    installed_skill.write_text("# Existing review skill\n", encoding="utf-8")
    package_root = tmp_path / "claude-package"
    (package_root / ".claude-plugin").mkdir(parents=True)
    (package_root / ".claude-plugin" / "plugin.json").write_text(
        '{"name":"review-helper"}',
        encoding="utf-8",
    )
    package_skill = package_root / "skills" / "review" / "SKILL.md"
    package_skill.parent.mkdir(parents=True)
    package_skill.write_text("# Review skill\n", encoding="utf-8")
    rows = [
        {
            "id": "review-helper@local",
            "scope": "user",
            "enabled": True,
            "installPath": str(installed_root),
        }
    ]
    monkeypatch.setattr(
        ClaudePluginsService,
        "_plugin_rows",
        lambda _self, _workspace_id: rows,
    )
    target_client = FilesystemUserCopyInventoryReader(settings)

    inventory = target_client.inventory(
        "claude-code",
        profile=resolve_user_copy_profile("claude-native", package_root),
    )

    assert inventory.complete is True
    assert [
        (
            identity.resource_type,
            identity.resource_id,
            identity.scope,
        )
        for identity in inventory.effective_identities
    ] == [("skill", "review", "plugin")]

    service = ClaudePluginsService(settings_service=Mock())
    monkeypatch.setattr(service, "_marketplace_rows", lambda _workspace_id: [])
    monkeypatch.setattr(service, "_provider_generation", lambda: 1)
    response = service.list_plugins("workspace-1")
    assert response.plugins[0].resourceCounts.skills == 1
    assert all(
        "installPath" not in installation.model_dump()
        for installation in response.plugins[0].installations
    )
    assert service.read_plugin_inventory("workspace-1").enabled_roots() == (
        installed_root.resolve(),
    )


def test_claude_plugin_invalid_locator_makes_disabled_inventory_incomplete(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    Path(settings.AILERON_WORKSPACE_PATH).mkdir(parents=True)
    installed_root = tmp_path / "installed"
    installed_manifest = installed_root / ".claude-plugin" / "plugin.json"
    installed_manifest.parent.mkdir(parents=True)
    installed_manifest.write_text(
        '{"name":"review-helper","commands":"../outside"}',
        encoding="utf-8",
    )
    package_root = tmp_path / "claude-package"
    package_manifest = package_root / ".claude-plugin" / "plugin.json"
    package_manifest.parent.mkdir(parents=True)
    package_manifest.write_text(
        '{"name":"review-helper"}',
        encoding="utf-8",
    )
    rows = [
        {
            "id": "review-helper@local",
            "scope": "user",
            "enabled": False,
            "installPath": str(installed_root),
        }
    ]
    monkeypatch.setattr(
        ClaudePluginsService,
        "_plugin_rows",
        lambda _self, _workspace_id: rows,
    )

    inventory = FilesystemUserCopyInventoryReader(settings).inventory(
        "claude-code",
        profile=resolve_user_copy_profile("claude-native", package_root),
    )

    assert inventory.complete is False
    assert inventory.effective_identities == ()


def test_codex_inventory_parses_each_toml_document_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    workspace_root = Path(settings.AILERON_WORKSPACE_PATH)
    workspace_root.mkdir(parents=True)
    user_home = tmp_path / "home" / "developer"
    resolver = CodexPathResolver(
        user_home=user_home,
        workspace_root=workspace_root,
    )
    project_config = resolver.resolve("project", "config")
    project_config.parent.mkdir(parents=True)
    project_config.write_text("[plugins]\n", encoding="utf-8")
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True)
    user_config.write_text("[plugins]\n", encoding="utf-8")
    calls: list[Path] = []
    original_toml_document = inventory_module._toml_document

    def counted_toml_document(path: Path) -> dict[str, object]:
        calls.append(path)
        return original_toml_document(path)

    monkeypatch.setenv("HOME", str(user_home))
    monkeypatch.setattr(
        inventory_module,
        "get_codex_path_resolver",
        lambda: resolver,
    )
    monkeypatch.setattr(
        CodexPluginResourceResolver,
        "packages",
        lambda _self, _enabled_plugin_ids=None: [],
    )
    monkeypatch.setattr(
        inventory_module,
        "_toml_document",
        counted_toml_document,
    )

    inventory = FilesystemUserCopyInventoryReader(settings).inventory(
        "codex",
        profile=_codex_profile(tmp_path),
    )

    assert inventory.complete is True
    assert calls.count(project_config) == 1
    assert calls.count(user_config) == 1
