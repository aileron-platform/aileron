"""Marketplace provider adapter tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.marketplace.models import (
    MarketplacePackageCreateRequest,
)
from app.modules.marketplace.providers import (
    BaseMarketplaceProviderAdapter,
    ClaudeCodeMarketplaceAdapter,
    CodexMarketplaceAdapter,
    create_marketplace_adapters,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _create_package_scaffold(
    adapter: BaseMarketplaceProviderAdapter,
    package_path: Path,
    request: MarketplacePackageCreateRequest,
) -> None:
    manifest_path = adapter.manifest_path(package_path)
    manifest = {"name": request.package_id}
    if request.provider == "codex":
        manifest.update(
            {
                "version": "0.1.0",
                "description": request.description or "",
            }
        )
    _write_json(manifest_path, manifest)
    readme_path = package_path / "README.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(
        f"# {request.display_name or request.package_id}\n", encoding="utf-8"
    )


def _upsert_listing_entry(
    adapter: BaseMarketplaceProviderAdapter,
    registry_root: Path,
    package_id: str,
    entry: dict,
) -> None:
    manifest_path = adapter.marketplace_manifest_path(registry_root)
    document = (
        adapter.read_json(manifest_path) if manifest_path.exists() else {"plugins": []}
    )
    plugins: list[dict] = []
    replaced = False
    for plugin in document.get("plugins", []):
        if not isinstance(plugin, dict):
            continue
        if plugin.get("name") == package_id:
            plugins.append({**entry, "name": package_id})
            replaced = True
            continue
        plugins.append(plugin)
    if not replaced:
        plugins.append({**entry, "name": package_id})
    document["plugins"] = plugins
    _write_json(manifest_path, document)


def test_adapter_registry_exposes_all_supported_providers():
    adapters = create_marketplace_adapters()

    assert sorted(adapters.keys()) == ["claude-code", "codex"]
    assert isinstance(adapters["claude-code"], ClaudeCodeMarketplaceAdapter)
    assert isinstance(adapters["codex"], CodexMarketplaceAdapter)


def test_claude_adapter_paths_scaffold_and_resource_index(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "review-assistant")
    package_path.mkdir(parents=True)

    _create_package_scaffold(
        adapter,
        package_path,
        MarketplacePackageCreateRequest(
            provider="claude-code",
            package_id="review-assistant",
            display_name="Review Assistant",
            description="Review package",
        ),
    )
    (package_path / "output-styles").mkdir()
    (package_path / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")

    assert adapter.marketplace_manifest_path(tmp_path) == (
        tmp_path / ".claude-plugin" / "marketplace.json"
    )
    assert (
        adapter.manifest_path(package_path)
        == package_path / ".claude-plugin" / "plugin.json"
    )
    assert json.loads(adapter.manifest_path(package_path).read_text()) == {
        "name": "review-assistant"
    }
    assert adapter.indexed_resource_names(package_path) == ["output-style"]
    (package_path / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
    assert adapter.indexed_resource_names(package_path) == ["agentsMd", "output-style"]
    assert adapter.validate_package(package_path) == []


def test_codex_adapter_paths_and_hooks_variants(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)
    _create_package_scaffold(
        adapter,
        package_path,
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Figma Context",
            description="Figma package",
        ),
    )
    (package_path / "hooks").mkdir()
    (package_path / "hooks" / "hooks.json").write_text("{}", encoding="utf-8")

    assert adapter.marketplace_manifest_path(tmp_path) == (
        tmp_path / ".agents" / "plugins" / "marketplace.json"
    )
    assert (
        adapter.manifest_path(package_path)
        == package_path / ".codex-plugin" / "plugin.json"
    )
    assert "hooks" in adapter.indexed_resource_names(package_path)


def test_codex_adapter_indexes_only_native_root_document(tmp_path: Path) -> None:
    adapter = CodexMarketplaceAdapter()
    package_path = tmp_path / "package"
    package_path.mkdir()
    (package_path / "CLAUDE.md").write_text("# Wrong provider\n", encoding="utf-8")

    assert "agentsMd" not in adapter.indexed_resource_names(package_path)

    (package_path / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")

    assert "agentsMd" in adapter.indexed_resource_names(package_path)


def test_listing_projection_read_write_preserves_sibling_entries_and_root_metadata(
    tmp_path,
):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    _write_json(
        manifest_path,
        {
            "name": "Team Marketplace",
            "owner": {"name": "Team Maintainer", "email": "team@example.local"},
            "plugins": [
                {"name": "review-assistant", "source": "./plugins/review-assistant"},
                {
                    "name": "doc-writer",
                    "source": "./plugins/doc-writer",
                    "category": "writing",
                },
            ],
        },
    )

    existing_entry = adapter.read_listing_entry(tmp_path, "review-assistant")
    _upsert_listing_entry(
        adapter,
        tmp_path,
        "review-assistant",
        {
            "name": "review-assistant",
            "source": "./plugins/review-assistant",
            "category": "quality",
        },
    )
    updated_manifest = json.loads(manifest_path.read_text())

    assert existing_entry == {
        "name": "review-assistant",
        "source": "./plugins/review-assistant",
    }
    assert updated_manifest["name"] == "Team Marketplace"
    assert updated_manifest["owner"]["name"] == "Team Maintainer"
    assert updated_manifest["plugins"] == [
        {
            "name": "review-assistant",
            "source": "./plugins/review-assistant",
            "category": "quality",
        },
        {"name": "doc-writer", "source": "./plugins/doc-writer", "category": "writing"},
    ]


def test_listing_projection_write_forces_current_package_name(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    _write_json(manifest_path, {"name": "Codex Registry", "plugins": []})

    _upsert_listing_entry(
        adapter,
        tmp_path,
        "figma-context",
        {
            "name": "wrong-id",
            "source": {"source": "local", "path": "./plugins/figma-context"},
        },
    )

    updated_manifest = json.loads(manifest_path.read_text())
    assert updated_manifest["plugins"][0]["name"] == "figma-context"


def test_provider_validation_reports_manifest_shape_identity_and_required_fields(
    tmp_path,
):
    codex = CodexMarketplaceAdapter()
    package_path = tmp_path / "codex" / "plugins" / "figma-context"
    (package_path / ".codex-plugin").mkdir(parents=True)
    (package_path / ".codex-plugin" / "plugin.json").write_text("[]", encoding="utf-8")

    invalid_shape = codex.validate_package(package_path)

    assert invalid_shape[0]["code"] == "marketplace.validation.invalid_manifest_shape"
    assert (
        invalid_shape[0]["messageKey"]
        == "marketplace.validation.invalid_manifest_shape"
    )

    _write_json(
        codex.manifest_path(package_path),
        {
            "name": "wrong-id",
            "version": "0.1.0",
        },
    )
    invalid_manifest = codex.validate_package(package_path)

    assert [result["code"] for result in invalid_manifest] == [
        "marketplace.validation.invalid_manifest_shape",
        "marketplace.validation.package_identity_mismatch",
    ]
    assert invalid_manifest[0]["details"] == {"missingFields": ["description"]}


def test_adapter_reports_catalog_metadata_conflicts(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    _write_json(
        manifest_path,
        {
            "name": "Codex Registry",
            "plugins": [
                {
                    "name": "figma-context",
                    "source": {"source": "local", "path": "./plugins/figma-context"},
                    "displayName": "Catalog Name",
                    "description": "Catalog description",
                    "version": "1.0.0",
                    "category": "design",
                    "tags": ["catalog"],
                }
            ],
        },
    )
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)
    _write_json(
        adapter.manifest_path(package_path),
        {
            "name": "figma-context",
            "displayName": "Manifest Name",
            "version": "0.1.0",
            "description": "Manifest description",
            "keywords": ["manifest"],
        },
    )

    conflicts = adapter.validate_catalog_metadata(
        adapter.read_listing_entry(tmp_path, "figma-context"),
        adapter.read_manifest(package_path),
    )

    assert conflicts[0]["code"] == "marketplace.validation.metadata_conflict"
    assert sorted(conflicts[0]["details"]["fields"]) == [
        "description",
        "displayName",
        "tags",
        "version",
    ]


def test_claude_adapter_scans_external_marketplace_candidates(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "name": "Claude Marketplace",
            "plugins": [
                {
                    "name": "review-assistant",
                    "source": "./plugins/review-assistant",
                    "description": "Catalog description",
                    "category": "quality",
                }
            ],
        },
    )
    package_path = tmp_path / "plugins" / "review-assistant"
    package_path.mkdir(parents=True)
    _create_package_scaffold(
        adapter,
        package_path,
        MarketplacePackageCreateRequest(
            provider="claude-code",
            package_id="review-assistant",
            display_name="Review Assistant",
            description="Manifest description",
        ),
    )
    _write_json(
        adapter.manifest_path(package_path),
        {
            "name": "review-assistant",
            "description": "Manifest description",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [
        {
            "id": "claude-code:review-assistant",
            "provider": "claude-code",
            "packageId": "review-assistant",
            "displayName": "review-assistant",
            "sourcePath": "plugins/review-assistant",
            "duplicate": False,
            "duplicateAction": "skip",
            "validationSeverity": "warning",
            "validationResults": [
                {
                    "severity": "warning",
                    "code": "marketplace.validation.metadata_conflict",
                    "messageKey": "marketplace.validation.metadata_conflict",
                    "filePath": ".claude-plugin/marketplace.json",
                    "details": {
                        "fields": {
                            "description": {
                                "catalog": "Catalog description",
                                "manifest": "Manifest description",
                            },
                        },
                    },
                }
            ],
            "sourceMetadata": {},
        }
    ]


def test_claude_external_scan_validates_root_source_with_catalog_package_id(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "superpowers",
                    "source": "./",
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".claude-plugin" / "plugin.json",
        {
            "name": "superpowers",
            "description": "Core skills library",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "superpowers"
    assert candidates[0]["sourcePath"] == "."
    assert candidates[0]["validationSeverity"] == "none"
    assert candidates[0]["validationResults"] == []


def test_claude_external_scan_marks_source_path_escape(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "escape-plugin",
                    "source": "../escape-plugin",
                }
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "escape-plugin"
    assert candidates[0]["sourcePath"] == "../escape-plugin"
    assert candidates[0]["validationSeverity"] == "error"
    assert (
        candidates[0]["validationResults"][0]["code"]
        == "marketplace.validation.path_escape"
    )


def test_claude_external_scan_keeps_nested_remote_source_metadata(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "remote-plugin",
                    "source": "https://example.com/org/remote-plugin.git",
                }
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "remote-plugin"
    assert candidates[0]["sourcePath"] == "https://example.com/org/remote-plugin.git"
    assert candidates[0]["validationSeverity"] == "none"
    assert candidates[0]["validationResults"] == []
    assert candidates[0]["sourceMetadata"] == {
        "kind": "git",
        "sourceType": "url",
        "url": "https://example.com/org/remote-plugin.git",
    }


def test_claude_external_scan_allows_official_numeric_and_dot_package_ids(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "42crunch-api-security-testing",
                    "source": "https://example.com/org/42crunch.git",
                },
                {
                    "name": "wordpress.com",
                    "source": "https://example.com/org/wordpress.git",
                },
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert [candidate["packageId"] for candidate in candidates] == [
        "42crunch-api-security-testing",
        "wordpress.com",
    ]
    assert [candidate["validationSeverity"] for candidate in candidates] == [
        "none",
        "none",
    ]


def test_claude_external_scan_keeps_structured_remote_source_metadata(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "remote-plugin",
                    "source": {
                        "source": "git-subdir",
                        "url": "https://example.com/org/remote-plugin.git",
                        "path": "plugins/remote-plugin",
                    },
                }
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "remote-plugin"
    assert (
        candidates[0]["sourcePath"]
        == "https://example.com/org/remote-plugin.git:plugins/remote-plugin"
    )
    assert candidates[0]["validationSeverity"] == "none"
    assert candidates[0]["validationResults"] == []
    assert candidates[0]["sourceMetadata"] == {
        "kind": "git",
        "sourceType": "git-subdir",
        "url": "https://example.com/org/remote-plugin.git",
        "path": "plugins/remote-plugin",
    }


def test_codex_adapter_scans_external_marketplace_candidates(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "name": "Codex Marketplace",
            "plugins": [
                {
                    "name": "figma-context",
                    "source": {"source": "local", "path": "./plugins/figma-context"},
                    "displayName": "Catalog Name",
                    "description": "Catalog description",
                    "category": "design",
                }
            ],
        },
    )
    package_path = tmp_path / "plugins" / "figma-context"
    package_path.mkdir(parents=True)
    _create_package_scaffold(
        adapter,
        package_path,
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Manifest Name",
            description="Manifest description",
        ),
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [
        {
            "id": "codex:figma-context",
            "provider": "codex",
            "packageId": "figma-context",
            "displayName": "Catalog Name",
            "sourcePath": "plugins/figma-context",
            "duplicate": False,
            "duplicateAction": "skip",
            "validationSeverity": "warning",
            "validationResults": [
                {
                    "severity": "warning",
                    "code": "marketplace.validation.metadata_conflict",
                    "messageKey": "marketplace.validation.metadata_conflict",
                    "filePath": ".agents/plugins/marketplace.json",
                    "details": {
                        "fields": {
                            "description": {
                                "catalog": "Catalog description",
                                "manifest": "Manifest description",
                            },
                        },
                    },
                }
            ],
            "sourceMetadata": {},
        }
    ]


def test_codex_external_scan_validates_root_source_with_catalog_package_id(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "superpowers",
                    "source": {"source": "local", "path": "./"},
                }
            ],
        },
    )
    _write_json(
        tmp_path / ".codex-plugin" / "plugin.json",
        {
            "name": "superpowers",
            "version": "1.0.0",
            "description": "Core skills library",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "superpowers"
    assert candidates[0]["sourcePath"] == "."
    assert candidates[0]["validationSeverity"] == "none"
    assert candidates[0]["validationResults"] == []


def test_codex_external_scan_detects_root_plugin_without_marketplace_manifest(tmp_path):
    adapter = CodexMarketplaceAdapter()
    _write_json(
        tmp_path / ".codex-plugin" / "plugin.json",
        {
            "name": "superpowers",
            "version": "1.0.0",
            "description": "Core skills library",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [
        {
            "id": "codex:superpowers",
            "provider": "codex",
            "packageId": "superpowers",
            "displayName": "superpowers",
            "sourcePath": ".",
            "duplicate": False,
            "duplicateAction": "skip",
            "validationSeverity": "none",
            "validationResults": [],
            "sourceMetadata": {},
        }
    ]


def test_codex_import_listing_entry_falls_back_to_root_plugin_manifest(tmp_path):
    adapter = CodexMarketplaceAdapter()
    _write_json(
        tmp_path / ".codex-plugin" / "plugin.json",
        {
            "name": "superpowers",
            "version": "1.0.0",
            "description": "Core skills library",
        },
    )

    listing = adapter.import_listing_entry(tmp_path, "superpowers", "superpowers")

    assert listing == {
        "name": "superpowers",
        "description": "Core skills library",
        "version": "1.0.0",
        "source": {
            "source": "local",
            "path": "./plugins/superpowers",
        },
    }


def test_codex_external_scan_marks_source_path_escape(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "escape-plugin",
                    "source": {"source": "local", "path": "../escape-plugin"},
                }
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "escape-plugin"
    assert candidates[0]["sourcePath"] == "../escape-plugin"
    assert candidates[0]["validationSeverity"] == "error"
    assert (
        candidates[0]["validationResults"][0]["code"]
        == "marketplace.validation.path_escape"
    )


def test_codex_external_scan_keeps_nested_remote_source_metadata(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    _write_json(
        manifest_path,
        {
            "plugins": [
                {
                    "name": "remote-plugin",
                    "source": {"source": "github", "repo": "example/remote-plugin"},
                }
            ],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "remote-plugin"
    assert candidates[0]["sourcePath"] == "https://github.com/example/remote-plugin.git"
    assert candidates[0]["validationSeverity"] == "none"
    assert candidates[0]["validationResults"] == []
    assert candidates[0]["sourceMetadata"] == {
        "kind": "git",
        "sourceType": "github",
        "url": "https://github.com/example/remote-plugin.git",
    }


def test_adapter_unsupported_future_methods_are_explicit(tmp_path):
    adapter = BaseMarketplaceProviderAdapter()

    with pytest.raises(NotImplementedError, match="marketplace.import.not_implemented"):
        adapter.scan_external_source(tmp_path)


def test_claude_shared_root_selectors_match_anthropic_package_shape(
    tmp_path: Path,
) -> None:
    adapter = ClaudeCodeMarketplaceAdapter()
    selector_sets = {
        "document-skills": ["pdf", "docx", "pptx", "xlsx"],
        "example-skills": [f"example-{index:02d}" for index in range(12)],
        "claude-api": ["claude-api"],
    }
    _write_json(
        tmp_path / ".claude-plugin" / "marketplace.json",
        {
            "plugins": [
                {
                    "name": package_id,
                    "source": "./",
                    "skills": [f"./skills/{name}" for name in names],
                }
                for package_id, names in selector_sets.items()
            ]
        },
    )
    for names in selector_sets.values():
        for name in names:
            skill = tmp_path / "skills" / name
            skill.mkdir(parents=True, exist_ok=True)
            (skill / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")

    candidates = adapter.scan_external_source(tmp_path)

    assert {
        candidate["packageId"]: len(
            candidate["sourceMetadata"]["componentSelectors"]["skills"]
        )
        for candidate in candidates
    } == {
        "document-skills": 4,
        "example-skills": 12,
        "claude-api": 1,
    }
    assert all(candidate["validationSeverity"] == "none" for candidate in candidates)


def test_component_selectors_reject_duplicate_logical_skill_targets(
    tmp_path: Path,
) -> None:
    adapter = ClaudeCodeMarketplaceAdapter()
    _write_json(
        tmp_path / ".claude-plugin" / "marketplace.json",
        {
            "plugins": [
                {
                    "name": "duplicate-skills",
                    "source": "./",
                    "skills": [
                        "./skills/a/review",
                        "./skills/b/review",
                    ],
                }
            ]
        },
    )
    for locator in ("skills/a/review", "skills/b/review"):
        skill = tmp_path / locator
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("# Review\n", encoding="utf-8")

    selectors, results = adapter.import_component_selectors(
        tmp_path,
        tmp_path,
        "duplicate-skills",
    )

    assert selectors["skills"] == ["skills/a/review"]
    assert [result["code"] for result in results] == [
        "marketplace.validation.component_selector_conflict"
    ]


def test_component_projection_blocks_unresolved_manifest_dependency(
    tmp_path: Path,
) -> None:
    adapter = ClaudeCodeMarketplaceAdapter()
    _write_json(
        adapter.manifest_path(tmp_path),
        {
            "name": "projected",
            "skills": ["./skills/review"],
            "mcpServers": "config/mcp.json",
        },
    )
    skill = tmp_path / "skills" / "review"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Review\n", encoding="utf-8")

    results = adapter.validate_component_projection(tmp_path)

    assert [result["code"] for result in results] == [
        "marketplace.validation.component_selector_dependency_unprojectable"
    ]
    assert results[0]["details"]["diagnosticCode"] == "source-missing"
