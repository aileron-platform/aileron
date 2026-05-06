"""Claude plugin workflow service tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

from app.modules.claude_code.common import DocumentScope
from app.modules.claude_code.plugins.service import ClaudePluginsService


def _scope_root(tmp_path: Path, _workspace_id: str, scope: DocumentScope) -> Path:
    if scope == DocumentScope.USER:
        return tmp_path / "home" / ".claude"
    return tmp_path / "workspace" / ".claude"


def _write_sparse_frontend_plugin(tmp_path: Path) -> tuple[Path, Path]:
    user_root = tmp_path / "home" / ".claude"
    marketplace_root = user_root / "plugins" / "marketplaces" / "claude-plugins-official"
    marketplace_config = marketplace_root / ".claude-plugin"
    marketplace_config.mkdir(parents=True)
    marketplace_payload = {
        "name": "claude-plugins-official",
        "plugins": [
            {
                "name": "frontend-design",
                "description": "Registry description",
                "author": {"name": "Anthropic"},
                "category": "development",
                "homepage": "https://example.test/frontend-design",
                "source": "./plugins/frontend-design",
            }
        ],
    }
    (marketplace_config / "marketplace.json").write_text(json.dumps(marketplace_payload), encoding="utf-8")
    cache_root = user_root / "plugins" / "cache" / "claude-plugins-official" / "frontend-design" / "unknown"
    source_root = marketplace_root / "plugins" / "frontend-design"
    skill_root = source_root / "skills" / "frontend-design"
    skill_root.mkdir(parents=True)
    cache_root.mkdir(parents=True)
    (source_root / "README.md").write_text("Marketplace README body", encoding="utf-8")
    (cache_root / "README.md").write_text("Cache README body", encoding="utf-8")
    (skill_root / "SKILL.md").write_text(
        "---\nname: frontend-design\ndescription: Skill description\n---\nBody",
        encoding="utf-8",
    )
    (cache_root / ".claude-plugin").mkdir()
    (cache_root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "frontend-design", "description": "Sparse cache description"}),
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
    (user_root / "plugins" / "installed_plugins.json").write_text(json.dumps(installed_plugins), encoding="utf-8")
    return cache_root, source_root


def test_list_plugins_merges_registry_metadata_and_marketplace_source_resources(tmp_path: Path) -> None:
    """List response uses registry metadata and marketplace source resource counts."""

    ClaudePluginsService._clear_list_cache()
    cache_root, _source_root = _write_sparse_frontend_plugin(tmp_path)

    service = ClaudePluginsService(settings_service=Mock())
    with (
        patch("app.modules.claude_code.plugins.service.resolve_scope_root", side_effect=lambda workspace_id, scope: _scope_root(tmp_path, workspace_id, scope)),
        patch.object(
            service,
            "_run_claude_json",
            side_effect=[
                [
                    {
                        "id": "frontend-design@claude-plugins-official",
                        "scope": "user",
                        "enabled": True,
                        "installPath": str(cache_root),
                        "version": "unknown",
                    }
                ],
                [
                    {
                        "name": "claude-plugins-official",
                        "source": {"source": "github", "repo": "anthropics/claude-plugins-official"},
                    }
                ],
            ],
        ),
    ):
        response = service.list_plugins("workspace-1")

    plugin = response.plugins[0]
    assert plugin.description == "Registry description"
    assert plugin.author == "Anthropic"
    assert plugin.category == "development"
    assert plugin.homepage == "https://example.test/frontend-design"
    assert plugin.resourceCounts.skills == 1
    assert response.marketplaces[0].pluginCount == 1


def test_get_plugin_detail_reads_readme_and_skill_metadata_from_marketplace_source(tmp_path: Path) -> None:
    """Detail response reads resources from the effective marketplace source root."""

    cache_root, _source_root = _write_sparse_frontend_plugin(tmp_path)

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
        patch("app.modules.claude_code.plugins.service.resolve_scope_root", side_effect=lambda workspace_id, scope: _scope_root(tmp_path, workspace_id, scope)),
        patch.object(service, "_plugin_rows", return_value=rows),
    ):
        response = service.get_plugin_detail("workspace-1", "frontend-design@claude-plugins-official")

    detail = response.plugin
    assert detail.description == "Registry description"
    assert detail.readme == "Marketplace README body"
    assert detail.resourceCounts.skills == 1
    assert detail.resources["skills"][0]["name"] == "frontend-design"
    assert detail.resources["skills"][0]["description"] == "Skill description"


def test_list_plugins_cache_invalidates_when_marketplace_source_resource_changes(tmp_path: Path) -> None:
    """List cache signature includes effective marketplace resource roots."""

    ClaudePluginsService._clear_list_cache()
    cache_root, source_root = _write_sparse_frontend_plugin(tmp_path)
    skill_file = source_root / "skills" / "frontend-design" / "SKILL.md"
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
            "source": {"source": "github", "repo": "anthropics/claude-plugins-official"},
        }
    ]
    with (
        patch("app.modules.claude_code.plugins.service.resolve_scope_root", side_effect=lambda workspace_id, scope: _scope_root(tmp_path, workspace_id, scope)),
        patch.object(service, "_run_claude_json", side_effect=[plugin_rows, marketplace_rows, plugin_rows, marketplace_rows]),
    ):
        first = service.list_plugins("workspace-1")
        assert first.plugins[0].resourceCounts.skills == 0
        skill_file.write_text(
            "---\nname: frontend-design\ndescription: Skill description\n---\nBody",
            encoding="utf-8",
        )
        second = service.list_plugins("workspace-1")

    assert second.plugins[0].resourceCounts.skills == 1
