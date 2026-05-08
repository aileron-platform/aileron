"""Marketplace provider adapter tests."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from app.models.marketplace import (
    MarketplaceCliCapabilities,
    MarketplaceCliPreflightResult,
    MarketplacePackageCreateRequest,
)
from app.services.marketplace_adapters import (
    BaseMarketplaceProviderAdapter,
    ClaudeCodeMarketplaceAdapter,
    CodexMarketplaceAdapter,
    GeminiExtensionAdapter,
    create_marketplace_adapters,
)


def test_adapter_registry_exposes_all_supported_providers():
    adapters = create_marketplace_adapters()

    assert sorted(adapters.keys()) == ["claude-code", "codex", "gemini"]
    assert isinstance(adapters["claude-code"], ClaudeCodeMarketplaceAdapter)
    assert isinstance(adapters["codex"], CodexMarketplaceAdapter)
    assert isinstance(adapters["gemini"], GeminiExtensionAdapter)


def test_claude_adapter_paths_scaffold_and_resource_index(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "review-assistant")
    package_path.mkdir(parents=True)

    adapter.create_package(
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
        tmp_path / "claude-code" / ".claude-plugin" / "marketplace.json"
    )
    assert adapter.manifest_path(package_path) == package_path / ".claude-plugin" / "plugin.json"
    assert json.loads(adapter.manifest_path(package_path).read_text()) == {"name": "review-assistant"}
    assert adapter.indexed_resource_names(package_path) == ["agentsMd", "output-style"]
    assert adapter.validate_package(package_path) == []


def test_codex_adapter_listing_and_hooks_variants(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    adapter.atomic_write_json(manifest_path, {"name": "Codex Registry", "plugins": []})
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)
    adapter.create_package(
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

    adapter.upsert_listing_entry(
        tmp_path,
        "figma-context",
        {
            "name": "figma-context",
            "source": {"source": "local", "path": "./plugins/figma-context"},
            "category": "design",
        },
    )
    scanned = adapter.scan_registry(tmp_path)
    adapter.remove_listing_entry(tmp_path, "figma-context")
    updated_manifest = json.loads(manifest_path.read_text())

    assert adapter.marketplace_manifest_path(tmp_path) == (
        tmp_path / "codex" / ".agents" / "plugins" / "marketplace.json"
    )
    assert adapter.manifest_path(package_path) == package_path / ".codex-plugin" / "plugin.json"
    assert scanned[0].provider == "codex"
    assert scanned[0].package_id == "figma-context"
    assert scanned[0].category == "design"
    assert "hooks" in scanned[0].indexed_resource_names
    assert updated_manifest["plugins"] == []


def test_listing_projection_read_write_preserves_sibling_entries_and_root_metadata(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    adapter.atomic_write_json(
        manifest_path,
        {
            "name": "Team Marketplace",
            "owner": {"name": "Team Maintainer", "email": "team@example.local"},
            "plugins": [
                {"name": "review-assistant", "source": "./plugins/review-assistant"},
                {"name": "doc-writer", "source": "./plugins/doc-writer", "category": "writing"},
            ],
        },
    )

    existing_entry = adapter.read_listing_entry(tmp_path, "review-assistant")
    adapter.upsert_listing_entry(
        tmp_path,
        "review-assistant",
        {
            "name": "review-assistant",
            "source": "./plugins/review-assistant",
            "category": "quality",
        },
    )
    updated_manifest = json.loads(manifest_path.read_text())

    assert existing_entry == {"name": "review-assistant", "source": "./plugins/review-assistant"}
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
    adapter.atomic_write_json(manifest_path, {"name": "Codex Registry", "plugins": []})

    adapter.upsert_listing_entry(
        tmp_path,
        "figma-context",
        {
            "name": "wrong-id",
            "source": {"source": "local", "path": "./plugins/figma-context"},
        },
    )

    updated_manifest = json.loads(manifest_path.read_text())
    assert updated_manifest["plugins"][0]["name"] == "figma-context"


def test_provider_validation_reports_manifest_shape_identity_and_required_fields(tmp_path):
    codex = CodexMarketplaceAdapter()
    package_path = tmp_path / "codex" / "plugins" / "figma-context"
    (package_path / ".codex-plugin").mkdir(parents=True)
    (package_path / ".codex-plugin" / "plugin.json").write_text("[]", encoding="utf-8")

    invalid_shape = codex.validate_package(package_path)

    assert invalid_shape[0]["code"] == "marketplace.validation.invalid_manifest_shape"
    assert invalid_shape[0]["messageKey"] == "marketplace.validation.invalid_manifest_shape"

    codex.atomic_write_json(
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


def test_adapter_scan_prefers_catalog_metadata_and_marks_manifest_conflicts(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    adapter.atomic_write_json(
        manifest_path,
        {
            "name": "Codex Registry",
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "displayName": "Catalog Name",
                "description": "Catalog description",
                "version": "1.0.0",
                "category": "design",
                "tags": ["catalog"],
            }],
        },
    )
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)
    adapter.create_package(
        package_path,
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Manifest Name",
            description="Manifest description",
        ),
    )
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "review-assistant",
            "description": "Manifest description",
        },
    )
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "figma-context",
            "displayName": "Manifest Name",
            "version": "0.1.0",
            "description": "Manifest description",
            "keywords": ["manifest"],
        },
    )

    scanned = adapter.scan_registry(tmp_path)
    conflicts = adapter.validate_catalog_metadata(
        adapter.read_listing_entry(tmp_path, "figma-context"),
        adapter.read_manifest(package_path),
    )

    assert scanned[0].display_name == "Catalog Name"
    assert scanned[0].description == "Catalog description"
    assert scanned[0].version == "1.0.0"
    assert scanned[0].tags == ["catalog"]
    assert scanned[0].validation_severity == "warning"
    assert conflicts[0]["code"] == "marketplace.validation.metadata_conflict"
    assert sorted(conflicts[0]["details"]["fields"]) == [
        "description",
        "displayName",
        "tags",
        "version",
    ]


def test_codex_scan_derives_package_index_fields_from_registry_state(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    manifest_path = adapter.marketplace_manifest_path(tmp_path)
    adapter.atomic_write_json(
        manifest_path,
        {
            "name": "Codex Registry",
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "sourceType": "imported",
            }],
        },
    )
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "figma-context",
            "displayName": "Figma Context",
            "version": "0.1.0",
            "description": "Figma MCP package",
            "category": "design",
            "tags": ["mcp", "design"],
        },
    )
    (package_path / "skills").mkdir()
    (package_path / "skills" / "review.md").write_text("# Review Skill\n", encoding="utf-8")
    (package_path / "commands").mkdir()
    (package_path / "commands" / "sync.md").write_text("---\ntitle: Sync Command\n---\n", encoding="utf-8")
    (package_path / "agents").mkdir()
    (package_path / "agents" / "designer.json").write_text(
        json.dumps({"name": "Designer Agent"}),
        encoding="utf-8",
    )
    (package_path / "hooks.json").write_text(json.dumps({"name": "Root Hook"}), encoding="utf-8")
    old_time = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    new_time = datetime(2026, 1, 2, tzinfo=timezone.utc).timestamp()
    for path in package_path.rglob("*"):
        if path.is_file():
            os.utime(path, (old_time, old_time))
    os.utime(manifest_path, (new_time, new_time))

    scanned = adapter.scan_registry(tmp_path)

    assert scanned[0].display_name == "Figma Context"
    assert scanned[0].category == "design"
    assert scanned[0].tags == ["mcp", "design"]
    assert scanned[0].source_type == "imported"
    assert scanned[0].updated_at == "2026-01-02T00:00:00Z"
    assert set(scanned[0].indexed_resource_names) >= {
        "skills",
        "review",
        "Review Skill",
        "commands",
        "sync",
        "Sync Command",
        "agents",
        "designer",
        "Designer Agent",
        "hooks",
    }


def test_gemini_scan_derives_manifest_metadata_and_command_names(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "workspace-tools")
    package_path.mkdir(parents=True)
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "workspace-tools",
            "displayName": "Workspace Tools",
            "version": "0.3.0",
            "description": "Workspace package",
            "category": "ops",
            "keywords": ["workspace"],
            "sourceType": "cloned",
        },
    )
    (package_path / "commands").mkdir()
    (package_path / "commands" / "inspect.toml").write_text(
        "id = \"inspect-workspace\"\nname = \"Inspect Workspace\"\n",
        encoding="utf-8",
    )

    scanned = adapter.scan_registry(tmp_path)

    assert scanned[0].display_name == "Workspace Tools"
    assert scanned[0].category == "ops"
    assert scanned[0].tags == ["workspace"]
    assert scanned[0].source_type == "cloned"
    assert set(scanned[0].indexed_resource_names) >= {
        "commands",
        "inspect",
        "inspect-workspace",
        "Inspect Workspace",
    }


def test_gemini_adapter_accepts_extension_manifest_without_description(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "conductor")
    package_path.mkdir(parents=True)
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "conductor",
            "version": "0.4.1",
            "contextFileName": "GEMINI.md",
            "plan": {"directory": "conductor"},
        },
    )
    (package_path / "GEMINI.md").write_text("# Conductor\n", encoding="utf-8")

    validation = adapter.validate_package(package_path)
    scanned = adapter.scan_external_source(package_path)

    assert validation == []
    assert scanned[0]["packageId"] == "conductor"
    assert scanned[0]["validationSeverity"] == "none"
    assert scanned[0]["validationResults"] == []


def test_gemini_adapter_scans_extension_roots_without_marketplace_manifest(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "workspace-tools")
    package_path.mkdir(parents=True)
    adapter.create_package(
        package_path,
        MarketplacePackageCreateRequest(
            provider="gemini",
            package_id="workspace-tools",
            display_name="Workspace Tools",
            description="Workspace package",
        ),
    )

    scanned = adapter.scan_registry(tmp_path)

    assert not (tmp_path / "gemini" / "marketplace.json").exists()
    assert adapter.manifest_path(package_path) == package_path / "gemini-extension.json"
    assert scanned[0].provider == "gemini"
    assert scanned[0].package_type == "extension"
    assert scanned[0].package_id == "workspace-tools"
    assert "agentsMd" in scanned[0].indexed_resource_names


def test_claude_adapter_scans_external_marketplace_candidates(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "name": "Claude Marketplace",
            "plugins": [{
                "name": "review-assistant",
                "source": "./plugins/review-assistant",
                "description": "Catalog description",
                "category": "quality",
            }],
        },
    )
    package_path = tmp_path / "plugins" / "review-assistant"
    package_path.mkdir(parents=True)
    adapter.create_package(
        package_path,
        MarketplacePackageCreateRequest(
            provider="claude-code",
            package_id="review-assistant",
            display_name="Review Assistant",
            description="Manifest description",
        ),
    )
    adapter.atomic_write_json(
        adapter.manifest_path(package_path),
        {
            "name": "review-assistant",
            "description": "Manifest description",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [{
        "id": "claude-code:review-assistant",
        "provider": "claude-code",
        "packageId": "review-assistant",
        "displayName": "review-assistant",
        "sourcePath": "plugins/review-assistant",
        "duplicate": False,
        "duplicateAction": "skip",
        "validationSeverity": "warning",
            "validationResults": [{
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
            }],
            "sourceMetadata": {},
        }]


def test_claude_external_scan_validates_root_source_with_catalog_package_id(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "superpowers",
                "source": "./",
            }],
        },
    )
    adapter.atomic_write_json(
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
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "escape-plugin",
                "source": "../escape-plugin",
            }],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "escape-plugin"
    assert candidates[0]["sourcePath"] == "../escape-plugin"
    assert candidates[0]["validationSeverity"] == "error"
    assert candidates[0]["validationResults"][0]["code"] == "marketplace.validation.path_escape"


def test_claude_external_scan_keeps_nested_remote_source_metadata(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "remote-plugin",
                "source": "https://example.com/org/remote-plugin.git",
            }],
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
    adapter.atomic_write_json(
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
    assert [candidate["validationSeverity"] for candidate in candidates] == ["none", "none"]


def test_claude_external_scan_keeps_structured_remote_source_metadata(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    manifest_path = tmp_path / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "remote-plugin",
                "source": {
                    "source": "git-subdir",
                    "url": "https://example.com/org/remote-plugin.git",
                    "path": "plugins/remote-plugin",
                },
            }],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "remote-plugin"
    assert candidates[0]["sourcePath"] == "https://example.com/org/remote-plugin.git:plugins/remote-plugin"
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
    adapter.atomic_write_json(
        manifest_path,
        {
            "name": "Codex Marketplace",
            "plugins": [{
                "name": "figma-context",
                "source": {"source": "local", "path": "./plugins/figma-context"},
                "displayName": "Catalog Name",
                "description": "Catalog description",
                "category": "design",
            }],
        },
    )
    package_path = tmp_path / "plugins" / "figma-context"
    package_path.mkdir(parents=True)
    adapter.create_package(
        package_path,
        MarketplacePackageCreateRequest(
            provider="codex",
            package_id="figma-context",
            display_name="Manifest Name",
            description="Manifest description",
        ),
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [{
        "id": "codex:figma-context",
        "provider": "codex",
        "packageId": "figma-context",
        "displayName": "Catalog Name",
        "sourcePath": "plugins/figma-context",
        "duplicate": False,
        "duplicateAction": "skip",
        "validationSeverity": "warning",
            "validationResults": [{
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
            }],
            "sourceMetadata": {},
        }]


def test_codex_external_scan_validates_root_source_with_catalog_package_id(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "superpowers",
                "source": {"source": "local", "path": "./"},
            }],
        },
    )
    adapter.atomic_write_json(
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
    adapter.atomic_write_json(
        tmp_path / ".codex-plugin" / "plugin.json",
        {
            "name": "superpowers",
            "version": "1.0.0",
            "description": "Core skills library",
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [{
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
    }]


def test_codex_import_listing_entry_falls_back_to_root_plugin_manifest(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.atomic_write_json(
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
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "escape-plugin",
                "source": {"source": "local", "path": "../escape-plugin"},
            }],
        },
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates[0]["packageId"] == "escape-plugin"
    assert candidates[0]["sourcePath"] == "../escape-plugin"
    assert candidates[0]["validationSeverity"] == "error"
    assert candidates[0]["validationResults"][0]["code"] == "marketplace.validation.path_escape"


def test_codex_external_scan_keeps_nested_remote_source_metadata(tmp_path):
    adapter = CodexMarketplaceAdapter()
    manifest_path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True)
    adapter.atomic_write_json(
        manifest_path,
        {
            "plugins": [{
                "name": "remote-plugin",
                "source": {"source": "github", "repo": "example/remote-plugin"},
            }],
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


def test_gemini_adapter_scans_external_extension_root(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.create_package(
        tmp_path,
        MarketplacePackageCreateRequest(
            provider="gemini",
            package_id="workspace-tools",
            display_name="Workspace Tools",
            description="Workspace package",
        ),
    )

    candidates = adapter.scan_external_source(tmp_path)

    assert candidates == [{
        "id": "gemini:workspace-tools",
        "provider": "gemini",
        "packageId": "workspace-tools",
        "displayName": "workspace-tools",
        "sourcePath": ".",
        "duplicate": False,
        "duplicateAction": "skip",
        "validationSeverity": "none",
        "validationResults": [],
    }]


def test_gemini_adapter_scans_external_extension_directory_children(tmp_path):
    adapter = GeminiExtensionAdapter()
    extension_path = tmp_path / "extensions" / "workspace-tools"
    extension_path.mkdir(parents=True)
    adapter.create_package(
        extension_path,
        MarketplacePackageCreateRequest(
            provider="gemini",
            package_id="workspace-tools",
            display_name="Workspace Tools",
            description="Workspace package",
        ),
    )
    (tmp_path / "extensions" / "not-extension").mkdir()

    candidates = adapter.scan_external_source(tmp_path / "extensions")

    assert len(candidates) == 1
    assert candidates[0]["packageId"] == "workspace-tools"
    assert candidates[0]["sourcePath"] == "workspace-tools"
    assert candidates[0]["validationSeverity"] == "none"


def test_adapter_install_command_plans_are_argv_based_with_limits(tmp_path):
    adapters = [
        (ClaudeCodeMarketplaceAdapter(), "review-assistant", "/usr/bin/claude"),
        (CodexMarketplaceAdapter(), "figma-context", "/usr/bin/codex"),
        (GeminiExtensionAdapter(), "workspace-tools", "/usr/bin/gemini"),
    ]

    for adapter, package_id, executable in adapters:
        adapter.ensure_roots(tmp_path)
        package_path = adapter.package_path(tmp_path, package_id)
        package_path.mkdir(parents=True, exist_ok=True)
        plan = adapter.build_install_command(
            package_path,
            "workspace-1",
            MarketplaceCliPreflightResult(
                provider=adapter.provider,
                available=True,
                executable_path=executable,
                version="1.0.0",
                capabilities=MarketplaceCliCapabilities(
                    supports_user_scope=True,
                    supports_marketplace_add=adapter.provider != "gemini",
                    supports_extension_install=adapter.provider == "gemini",
                ),
            ),
        )

        assert plan.provider == adapter.provider
        assert plan.argv[0] == executable
        if adapter.provider == "claude-code":
            assert "--scope" in plan.argv
            assert "user" in plan.argv
        else:
            assert "--user" in plan.argv
        assert "&&" not in plan.argv
        assert ";" not in plan.argv
        assert plan.cwd
        assert plan.env["WORKSPACE_ID"] == "workspace-1"
        assert plan.timeout_ms > 0
        assert plan.stdout_limit_bytes > 0
        assert plan.stderr_limit_bytes > 0
        assert plan.redact_patterns


def test_claude_install_command_uses_local_marketplace_plugin_ref_and_user_scope(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "review-assistant")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="claude-code",
            available=True,
            executable_path="/usr/bin/claude",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_marketplace_add=True,
            ),
        ),
    )

    provider_root = tmp_path / "claude-code"
    assert plan.argv == [
        "/usr/bin/claude",
        "plugin",
        "install",
        "review-assistant@local-marketplace",
        "--scope",
        "user",
    ]
    assert plan.cwd == str(provider_root)
    assert plan.env == {
        "WORKSPACE_ID": "workspace-1",
        "MARKETPLACE_NAME": "local-marketplace",
    }


def test_claude_install_command_uses_cli_default_scope_when_user_scope_missing(tmp_path):
    adapter = ClaudeCodeMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "review-assistant")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="claude-code",
            available=True,
            executable_path="/usr/bin/claude",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
        ),
    )

    assert plan.argv == [
        "/usr/bin/claude",
        "plugin",
        "install",
        "review-assistant@local-marketplace",
    ]
    assert "--scope" not in plan.argv


def test_codex_install_command_uses_local_marketplace_registry_and_user_scope(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="codex",
            available=True,
            executable_path="/usr/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_marketplace_add=True,
            ),
        ),
    )

    provider_root = tmp_path / "codex"
    assert plan.argv == [
        "/usr/bin/codex",
        "plugin",
        "marketplace",
        "add",
        str(provider_root),
        "--user",
    ]
    assert plan.cwd == str(provider_root)
    assert plan.env == {
        "WORKSPACE_ID": "workspace-1",
    }


def test_codex_install_command_uses_cli_default_scope_when_user_scope_missing(tmp_path):
    adapter = CodexMarketplaceAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "figma-context")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="codex",
            available=True,
            executable_path="/usr/bin/codex",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_marketplace_add=True),
        ),
    )

    assert plan.argv == [
        "/usr/bin/codex",
        "plugin",
        "marketplace",
        "add",
        str(tmp_path / "codex"),
    ]
    assert "--user" not in plan.argv
    assert plan.env == {
        "WORKSPACE_ID": "workspace-1",
    }


def test_gemini_install_command_uses_default_scope_when_user_scope_missing(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "workspace-tools")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="gemini",
            available=True,
            executable_path="/usr/bin/gemini",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(supports_extension_install=True),
        ),
    )

    assert plan.argv == [
        "/usr/bin/gemini",
        "extensions",
        "install",
        str(package_path),
        "--consent",
    ]
    assert "--user" not in plan.argv


def test_gemini_install_command_uses_local_extension_path_and_user_scope(tmp_path):
    adapter = GeminiExtensionAdapter()
    adapter.ensure_roots(tmp_path)
    package_path = adapter.package_path(tmp_path, "workspace-tools")
    package_path.mkdir(parents=True)

    plan = adapter.build_install_command(
        package_path,
        "workspace-1",
        MarketplaceCliPreflightResult(
            provider="gemini",
            available=True,
            executable_path="/usr/bin/gemini",
            version="1.0.0",
            capabilities=MarketplaceCliCapabilities(
                supports_user_scope=True,
                supports_extension_install=True,
            ),
        ),
    )

    assert plan.argv == [
        "/usr/bin/gemini",
        "extensions",
        "install",
        str(package_path),
        "--consent",
        "--user",
    ]
    assert plan.cwd == str(package_path.parent)
    assert plan.env == {
        "WORKSPACE_ID": "workspace-1",
        "GEMINI_CLI_TRUST_WORKSPACE": "true",
    }


def test_adapter_unsupported_future_methods_are_explicit(tmp_path):
    adapter = BaseMarketplaceProviderAdapter()

    with pytest.raises(NotImplementedError, match="marketplace.import.not_implemented"):
        adapter.scan_external_source(tmp_path)
    with pytest.raises(NotImplementedError, match="marketplace.export.not_implemented"):
        adapter.export_package(tmp_path)
    with pytest.raises(NotImplementedError, match="marketplace.install.not_implemented"):
        adapter.build_install_command(
            tmp_path,
            "workspace-1",
            MarketplaceCliPreflightResult(provider="codex", available=True),
        )
