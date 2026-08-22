import json
from pathlib import Path

import pytest

from aileron_marketplace_core import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopyResourceType,
    extract_user_copy_source_profile,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_agent_plugin_extractor_returns_source_only_portable_resources(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": (
                    "https://agent-plugins.org/schemas/1.0.0/" "plugin.schema.json"
                ),
                "name": "deployment.tools",
            }
        ),
    )
    _write(
        tmp_path / "skills" / "deploy" / "SKILL.md",
        "---\nname: deploy\ndescription: Deploy safely.\n---\n",
    )
    _write(
        tmp_path / "mcp.json",
        json.dumps(
            {
                "$schema": (
                    "https://agent-plugins.org/schemas/1.0.0/" "mcp.schema.json"
                ),
                "mcpServers": {"validator": {"type": "stdio", "command": "node"}},
            }
        ),
    )

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="universal/deployment.tools",
            revision="a" * 64,
        ),
    )

    assert profile.package_format is PluginPackageFormat.AGENT_PLUGIN_V1
    assert profile.release_identity.catalog_plugin_id == ("universal/deployment.tools")
    assert profile.diagnostics == ()
    assert [
        (
            resource.resource_type,
            resource.resource_id,
            resource.source_locator,
            resource.structured_value,
        )
        for resource in profile.resources
    ] == [
        (
            UserCopyResourceType.MCP,
            "validator",
            "mcp.json",
            {"type": "stdio", "command": "node"},
        ),
        (
            UserCopyResourceType.SKILL,
            "deploy",
            "skills/deploy",
            None,
        ),
    ]
    assert "package_format" not in profile.canonical_dict()
    assert all(
        "targetResource" not in resource.canonical_dict()
        and "copySemantics" not in resource.canonical_dict()
        for resource in profile.resources
    )


def test_agent_plugin_extractor_proves_plugin_root_dependencies(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "deployment.tools",
            }
        ),
    )
    _write(tmp_path / "bin" / "server.js", "server\n")
    _write(
        tmp_path / "mcp.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "server": {
                        "type": "stdio",
                        "command": "node",
                        "args": ["${PLUGIN_ROOT}/bin/server.js"],
                    }
                },
            }
        ),
    )

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="universal/deployment.tools",
            revision="a" * 64,
        ),
    )

    mcp = next(item for item in profile.resources if item.resource_id == "server")
    assert [item.source_locator for item in mcp.dependency_references] == [
        "bin/server.js"
    ]
    assert mcp.dependency_references[0].source_kind == "file"


def test_agent_plugin_extractor_isolates_invalid_mcp_entries(tmp_path: Path) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "deployment.tools",
            }
        ),
    )
    _write(
        tmp_path / "mcp.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {
                    "valid": {
                        "type": "streamable-http",
                        "url": "https://mcp.example.com/api",
                        "headers": {"X-Mode": "review"},
                    },
                    "shell-command": {
                        "type": "stdio",
                        "command": "node server.js",
                    },
                    "bad-env": {
                        "type": "stdio",
                        "command": "node",
                        "env": {"PLUGIN_ROOT": "override"},
                    },
                    "insecure-remote": {
                        "type": "streamable-http",
                        "url": "http://mcp.example.com/api",
                    },
                },
            }
        ),
    )

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="universal/deployment.tools",
            revision="a" * 64,
        ),
    )

    assert [resource.resource_id for resource in profile.resources] == ["valid"]
    assert [
        (diagnostic.resource_id, diagnostic.code) for diagnostic in profile.diagnostics
    ] == [
        ("bad-env", "mcp-entry-invalid"),
        ("insecure-remote", "mcp-entry-invalid"),
        ("shell-command", "mcp-entry-invalid"),
    ]


def test_agent_plugin_extractor_isolates_malformed_mcp_and_invalid_skill(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "deployment.tools",
            }
        ),
    )
    _write(tmp_path / "mcp.json", "{")
    _write(tmp_path / "skills" / "valid" / "SKILL.md", "# Valid\n")
    _write(tmp_path / "skills" / "invalid" / "SKILL.md", "# Invalid\n")
    (tmp_path / "skills" / "invalid" / "escape").symlink_to(tmp_path)

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="universal/deployment.tools",
            revision="a" * 64,
        ),
    )

    assert [resource.resource_id for resource in profile.resources] == ["valid"]
    assert {(item.resource_id, item.code) for item in profile.diagnostics} == {
        (None, "mcp-component-invalid"),
        ("invalid", "skill-invalid"),
    }


def test_agent_plugin_extractor_reports_unsupported_components(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "deployment.tools",
                "extensions": {"com.example.review": {"enabled": True}},
            }
        ),
    )
    _write(tmp_path / "commands" / "review.md", "# Review\n")
    _write(tmp_path / "hooks" / "hooks.json", "{}\n")
    _write(tmp_path / "agents" / "review.md", "# Review agent\n")

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="universal/deployment.tools",
            revision="a" * 64,
        ),
    )

    assert {(item.resource_id, item.code) for item in profile.diagnostics} == {
        ("agents", "nonportable-component-unsupported"),
        ("commands", "nonportable-component-unsupported"),
        ("hooks", "nonportable-component-unsupported"),
        ("com.example.review", "extension-unsupported"),
    }


def test_agent_plugin_manifest_enforces_closed_known_fields(tmp_path: Path) -> None:
    _write(
        tmp_path / "plugin.json",
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": "deployment.tools",
                "author": {"name": "Team", "unexpected": "field"},
            }
        ),
    )

    with pytest.raises(Exception, match="manifest-invalid"):
        extract_user_copy_source_profile(
            PluginPackageFormat.AGENT_PLUGIN_V1,
            tmp_path,
            release=PluginReleaseIdentity(
                catalog_plugin_id="universal/deployment.tools",
                revision="a" * 64,
            ),
        )


def test_codex_native_extractor_preserves_sources_without_target_semantics(
    tmp_path: Path,
) -> None:
    _write(tmp_path / ".codex-plugin" / "plugin.json", '{"name":"demo"}')
    _write(tmp_path / "AGENTS.md", "# Workspace instructions\n")
    _write(tmp_path / "skills" / "review" / "SKILL.md", "# Review\n")

    profile = extract_user_copy_source_profile(
        PluginPackageFormat.CODEX_NATIVE,
        tmp_path,
        release=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision="b" * 64,
        ),
    )

    assert [
        (resource.resource_type, resource.resource_id, resource.source_locator)
        for resource in profile.resources
    ] == [
        (
            UserCopyResourceType.INSTRUCTIONS,
            "root-instructions",
            "AGENTS.md",
        ),
        (UserCopyResourceType.SKILL, "review", "skills/review"),
    ]
    assert profile.diagnostics == ()
    assert all(
        set(resource.canonical_dict()).isdisjoint(
            {"targetResource", "copySemantics", "relativeTarget"}
        )
        for resource in profile.resources
    )
