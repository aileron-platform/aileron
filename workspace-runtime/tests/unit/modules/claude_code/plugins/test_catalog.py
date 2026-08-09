"""Claude plugin workflow service tests."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from app.modules.claude_code.documents import DocumentScope
from app.modules.claude_code.plugins import (
    provider_inventory as provider_inventory_module,
)
from app.modules.claude_code.plugins import catalog as service_module
from app.modules.claude_code.plugins.models import ClaudePluginInstallation
from app.modules.claude_code.plugins.catalog import ClaudePluginsService


def _scope_root(tmp_path: Path, _workspace_id: str, scope: DocumentScope) -> Path:
    if scope == DocumentScope.USER:
        return tmp_path / "home" / ".claude"
    return tmp_path / "workspace" / ".claude"


def _write_installed_frontend_plugin(tmp_path: Path) -> tuple[Path, Path]:
    user_root = tmp_path / "home" / ".claude"
    registry_checkout = (
        user_root / "plugins" / "marketplaces" / "claude-plugins-official"
    )
    registry_checkout.mkdir(parents=True)
    cache_root = (
        user_root
        / "plugins"
        / "cache"
        / "claude-plugins-official"
        / "frontend-design"
        / "unknown"
    )
    skill_root = cache_root / "skills" / "frontend-design"
    skill_root.mkdir(parents=True)
    (cache_root / "README.md").write_text("Cache README body", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\nname: frontend-design\ndescription: Skill description\n---\nBody",
        encoding="utf-8",
    )
    output_style = cache_root / "output-styles" / "compact.md"
    output_style.parent.mkdir()
    output_style.write_text("Compact", encoding="utf-8")
    (cache_root / ".claude-plugin").mkdir()
    (cache_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "frontend-design",
                "description": "Installed description",
                "author": {"name": "Anthropic"},
                "category": "development",
                "homepage": "https://example.test/frontend-design",
            }
        ),
        encoding="utf-8",
    )
    installed_plugins = {
        "version": 1,
        "plugins": {
            "frontend-design@claude-plugins-official": [
                {
                    "scope": "user",
                    "enabled": True,
                    "installPath": str(cache_root),
                    "version": "unknown",
                }
            ]
        },
    }
    (user_root / "plugins").mkdir(parents=True, exist_ok=True)
    (user_root / "plugins" / "installed_plugins.json").write_text(
        json.dumps(installed_plugins), encoding="utf-8"
    )
    return cache_root, registry_checkout


def test_list_plugins_uses_installed_manifest_and_installed_root_resources(
    tmp_path: Path,
) -> None:
    """List response projects metadata and resources from the installed root."""

    cache_root, _registry_checkout = _write_installed_frontend_plugin(tmp_path)

    service = ClaudePluginsService(settings_service=Mock())
    plugin_rows = [
        {
            "id": "frontend-design@claude-plugins-official",
            "scope": "user",
            "enabled": True,
            "installPath": str(cache_root),
            "version": "unknown",
        }
    ]
    marketplace_rows = [
        {
            "name": "claude-plugins-official",
            "source": {
                "source": "github",
                "repo": "anthropics/claude-plugins-official",
            },
        }
    ]

    def cli_result(_workspace_id: str, args: list[str]) -> object:
        return marketplace_rows if "marketplace" in args else plugin_rows

    with (
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_scope_root",
            side_effect=lambda workspace_id, scope: _scope_root(
                tmp_path, workspace_id, scope
            ),
        ),
        patch.object(
            service,
            "_run_claude_json",
            side_effect=cli_result,
        ),
        patch(
            (
                "app.modules.claude_code.plugins.provider_inventory."
                "resolve_claude_plugin_resources"
            ),
            wraps=provider_inventory_module.resolve_claude_plugin_resources,
        ) as resolve_resources,
    ):
        response = service.list_plugins("workspace-1")

    plugin = response.plugins[0]
    assert plugin.description == "Installed description"
    assert plugin.author == "Anthropic"
    assert plugin.category == "development"
    assert plugin.homepage == "https://example.test/frontend-design"
    assert plugin.resourceCounts.skills == 1
    assert plugin.resourceCounts.outputStyles == 1
    assert all(
        "installPath" not in installation.model_dump()
        for installation in plugin.installations
    )
    assert (
        "installPath" not in ClaudePluginInstallation.model_json_schema()["properties"]
    )
    assert response.marketplaces[0].pluginCount == 1
    resolve_resources.assert_called_once_with(cache_root)


def test_list_plugins_rejects_invalid_locator_without_exposing_install_root(
    tmp_path: Path,
) -> None:
    installed_root = tmp_path / "installed"
    manifest = installed_root / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"demo","commands":"../outside"}',
        encoding="utf-8",
    )
    service = ClaudePluginsService(settings_service=Mock())
    rows = [
        {
            "id": "demo@registry",
            "scope": "user",
            "enabled": False,
            "installPath": str(installed_root),
        }
    ]

    with (
        patch.object(service, "_plugin_rows", return_value=rows),
        patch.object(service, "_marketplace_rows", return_value=[]),
    ):
        with pytest.raises(HTTPException) as error:
            service.list_plugins("workspace-1")

    assert error.value.status_code == 409
    assert error.value.detail["errorCode"] == (
        "marketplace.settings.plugin_resource_parse_failed"
    )
    assert error.value.detail["diagnostics"][0]["code"] == ("source-reference-invalid")
    assert str(installed_root) not in json.dumps(error.value.detail)


def test_get_plugin_detail_reads_installed_readme_and_skill_metadata(
    tmp_path: Path,
) -> None:
    """Detail response never falls back to the registry checkout."""

    cache_root, _registry_checkout = _write_installed_frontend_plugin(tmp_path)

    service = ClaudePluginsService(settings_service=Mock())
    rows = [
        {
            "id": "frontend-design@claude-plugins-official",
            "scope": "user",
            "enabled": True,
            "installPath": str(cache_root),
            "version": "unknown",
        }
    ]
    with (
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_scope_root",
            side_effect=lambda workspace_id, scope: _scope_root(
                tmp_path, workspace_id, scope
            ),
        ),
        patch.object(service, "_plugin_rows", return_value=rows),
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_claude_plugin_resources",
            wraps=service_module.resolve_claude_plugin_resources,
        ) as resolve_resources,
    ):
        response = service.get_plugin_detail(
            "workspace-1", "frontend-design@claude-plugins-official"
        )

    detail = response.plugin
    assert detail.description == "Installed description"
    assert detail.readme == "Cache README body"
    assert detail.resourceCounts.skills == 1
    assert detail.resources["skills"][0]["name"] == "frontend-design"
    assert detail.resources["skills"][0]["description"] == "Skill description"
    resolve_resources.assert_called_once_with(cache_root)


def test_list_plugins_parallel_reads_keep_plugin_error_priority() -> None:
    service = ClaudePluginsService(settings_service=Mock())
    reads_started = Barrier(2)

    def failed_read(_workspace_id: str, args: list[str]) -> object:
        reads_started.wait(timeout=2)
        if "marketplace" in args:
            raise HTTPException(
                502,
                detail={"error": "CLAUDE_PLUGIN_MARKETPLACE_FAILED"},
            )
        raise HTTPException(
            503,
            detail={"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"},
        )

    with patch.object(service, "_run_claude_json", side_effect=failed_read):
        with pytest.raises(HTTPException) as error:
            service.list_plugins("workspace-1")

    assert error.value.status_code == 503
    assert error.value.detail == {"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"}


def test_list_plugins_failure_does_not_wait_for_blocked_marketplace_read() -> None:
    service = ClaudePluginsService(settings_service=Mock())
    marketplace_started = Event()
    release_marketplace = Event()

    def failed_read(_workspace_id: str, args: list[str]) -> object:
        if "marketplace" in args:
            marketplace_started.set()
            assert release_marketplace.wait(timeout=2)
            return []
        assert marketplace_started.wait(timeout=2)
        raise HTTPException(
            503,
            detail={"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"},
        )

    with (
        patch.object(service, "_run_claude_json", side_effect=failed_read),
        ThreadPoolExecutor(max_workers=1) as executor,
    ):
        result = executor.submit(service.list_plugins, "workspace-1")
        assert marketplace_started.wait(timeout=2)
        try:
            with pytest.raises(HTTPException) as error:
                result.result(timeout=0.5)
        finally:
            release_marketplace.set()

    assert error.value.status_code == 503
    assert error.value.detail == {"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"}


def test_set_plugin_enabled_rejects_stale_revision(tmp_path: Path) -> None:
    """Plugin toggle rejects stale settings revision before writing."""

    user_root = _scope_root(tmp_path, "workspace-1", DocumentScope.USER)
    user_root.mkdir(parents=True, exist_ok=True)
    settings_file = user_root / "settings.json"
    settings_file.write_text(
        '{"enabledPlugins":{"frontend-design@claude-plugins-official":true}}',
        encoding="utf-8",
    )
    service = ClaudePluginsService(settings_service=Mock())
    rows = [
        {
            "id": "frontend-design@claude-plugins-official",
            "scope": "user",
            "enabled": True,
            "installPath": str(user_root / "plugins" / "cache" / "frontend-design"),
            "version": "unknown",
        }
    ]

    with (
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_scope_root",
            side_effect=lambda workspace_id, scope: _scope_root(
                tmp_path, workspace_id, scope
            ),
        ),
        patch.object(service, "_plugin_rows", return_value=rows),
    ):
        with pytest.raises(HTTPException) as exc:
            service.set_plugin_enabled(
                "workspace-1",
                "frontend-design@claude-plugins-official",
                "user",
                False,
                "stale",
            )

    assert exc.value.status_code == 409
    assert exc.value.detail["errorCode"] == "REVISION_CONFLICT"
    assert settings_file.read_text(encoding="utf-8") == (
        '{"enabledPlugins":{"frontend-design@claude-plugins-official":true}}'
    )


def test_set_plugin_enabled_writes_with_shared_json_codec(tmp_path: Path) -> None:
    """Plugin toggle atomically persists the shared JSON document contract."""

    user_root = _scope_root(tmp_path, "workspace-1", DocumentScope.USER)
    user_root.mkdir(parents=True, exist_ok=True)
    settings_file = user_root / "settings.json"
    settings_file.write_text(
        '{"permissions":{"allow":["Read"]},"enabledPlugins":{}}',
        encoding="utf-8",
    )
    service = ClaudePluginsService(settings_service=Mock())
    rows = [
        {
            "id": "frontend-design@claude-plugins-official",
            "scope": "user",
            "enabled": True,
            "installPath": str(user_root / "plugins" / "cache" / "frontend-design"),
            "version": "unknown",
        }
    ]
    gate = Mock()
    gate.advance_generation.return_value = 7

    with (
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_scope_root",
            side_effect=lambda workspace_id, scope: _scope_root(
                tmp_path, workspace_id, scope
            ),
        ),
        patch.object(service, "_plugin_rows", return_value=rows),
        patch(
            "app.modules.claude_code.plugins.catalog.get_marketplace_provider_gate",
            return_value=gate,
        ),
    ):
        response = service.set_plugin_enabled(
            "workspace-1",
            "frontend-design@claude-plugins-official",
            "user",
            False,
        )

    assert json.loads(settings_file.read_text(encoding="utf-8")) == {
        "permissions": {"allow": ["Read"]},
        "enabledPlugins": {
            "frontend-design@claude-plugins-official": False,
        },
    }
    assert response.providerResourceGeneration == 7
    assert response.enabled is False
    assert response.revision
    gate.advance_generation.assert_called_once_with("claude-code")


def test_list_plugins_ignores_registry_checkout_and_reads_live_installed_root(
    tmp_path: Path,
) -> None:
    """Registry source files never contribute to the live installed projection."""

    cache_root, registry_checkout = _write_installed_frontend_plugin(tmp_path)
    skill_file = cache_root / "skills" / "frontend-design" / "SKILL.md"
    skill_file.unlink()

    service = ClaudePluginsService(settings_service=Mock())
    plugin_rows = [
        {
            "id": "frontend-design@claude-plugins-official",
            "scope": "user",
            "enabled": True,
            "installPath": str(cache_root),
            "version": "unknown",
        }
    ]
    marketplace_rows = [
        {
            "name": "claude-plugins-official",
            "source": {
                "source": "github",
                "repo": "anthropics/claude-plugins-official",
            },
        }
    ]

    def cli_result(_workspace_id: str, args: list[str]) -> object:
        return marketplace_rows if "marketplace" in args else plugin_rows

    with (
        patch(
            "app.modules.claude_code.plugins.catalog.resolve_scope_root",
            side_effect=lambda workspace_id, scope: _scope_root(
                tmp_path, workspace_id, scope
            ),
        ),
        patch.object(
            service,
            "_run_claude_json",
            side_effect=cli_result,
        ),
    ):
        first = service.list_plugins("workspace-1")
        assert first.plugins[0].resourceCounts.skills == 0
        registry_skill = registry_checkout / "skills" / "source-only" / "SKILL.md"
        registry_skill.parent.mkdir(parents=True)
        registry_skill.write_text("Registry-only", encoding="utf-8")
        unchanged = service.list_plugins("workspace-1")
        assert unchanged.plugins[0].resourceCounts.skills == 0
        skill_file.write_text(
            "---\nname: frontend-design\ndescription: Skill description\n---\nBody",
            encoding="utf-8",
        )
        second = service.list_plugins("workspace-1")

    assert second.plugins[0].resourceCounts.skills == 1


def test_marketplace_source_label_never_exposes_absolute_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.modules.claude_code.plugins.catalog.runtime_user_home",
        lambda: Path("/home/developer"),
    )
    monkeypatch.setattr(
        "app.modules.claude_code.plugins.catalog.workspace_root",
        lambda: Path("/workspace"),
    )

    assert (
        ClaudePluginsService._marketplace_source_label(
            "/home/developer/marketplaces/local"
        )
        == "~/marketplaces/local"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            {"source": "directory", "path": "/workspace/vendor/local"}
        )
        == "./vendor/local"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            "/private/provider/checkouts/secret"
        )
        == "local"
    )
    assert ClaudePluginsService._marketplace_source_label(
        "https://user:password@example.test/catalog?token=secret"
    ) == ("https://%5BREDACTED%5D@example.test/catalog?token=%5BREDACTED%5D")
    assert (
        ClaudePluginsService._marketplace_source_label(
            "ssh://user:password@example.test/catalog?token=secret"
        )
        == "ssh://%5BREDACTED%5D@example.test/catalog?token=%5BREDACTED%5D"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            "git+ssh://user:password@example.test/catalog"
        )
        == "git+ssh://%5BREDACTED%5D@example.test/catalog"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            "file:///home/developer/marketplaces/local"
        )
        == "~/marketplaces/local"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            "file:///private/provider/checkouts/secret"
        )
        == "local"
    )
    assert (
        ClaudePluginsService._marketplace_source_label(
            "custom:/private/provider/checkouts/secret"
        )
        == "local"
    )
