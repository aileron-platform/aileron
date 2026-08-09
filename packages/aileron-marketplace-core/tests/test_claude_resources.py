import os
from pathlib import Path

from aileron_marketplace_core import read_plugin_resource_owner
from aileron_marketplace_core.claude_resources import resolve_claude_plugin_resources


def test_resolves_default_file_components_and_lsp_servers(tmp_path: Path) -> None:
    (tmp_path / "commands").mkdir()
    (tmp_path / "commands" / "review.md").write_text("Review", encoding="utf-8")
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "reviewer.md").write_text("Agent", encoding="utf-8")
    skill = tmp_path / "skills" / "pdf" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Skill", encoding="utf-8")
    (tmp_path / "output-styles").mkdir()
    (tmp_path / "output-styles" / "calm.md").write_text(
        "Style",
        encoding="utf-8",
    )
    (tmp_path / ".lsp.json").write_text(
        '{"python":{"command":"pyright","extensionToLanguage":{".py":"python"}}}',
        encoding="utf-8",
    )

    resources = resolve_claude_plugin_resources(tmp_path)

    assert {
        (item.resource_type, item.source_locator, item.resource_root_locator)
        for item in resources.file_resources
    } == {
        ("agent", "agents/reviewer.md", "agents/reviewer.md"),
        ("command", "commands/review.md", "commands/review.md"),
        ("output-style", "output-styles/calm.md", "output-styles/calm.md"),
        ("skill", "skills/pdf/SKILL.md", "skills/pdf"),
    }
    assert set(resources.lsp_servers) == {"python"}
    assert (
        read_plugin_resource_owner(
            tmp_path,
            resources.lsp_servers["python"],
        )["command"]
        == "pyright"
    )
    assert resources.diagnostics == ()


def test_manifest_file_component_paths_replace_defaults(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        """
        {
          "name": "demo",
          "commands": "./custom/commands",
          "agents": ["./custom/reviewer.md"],
          "skills": "./custom/skills",
          "outputStyles": "./custom/styles"
        }
        """,
        encoding="utf-8",
    )
    for path in (
        tmp_path / "commands" / "ignored.md",
        tmp_path / "custom" / "commands" / "deploy.md",
        tmp_path / "custom" / "reviewer.md",
        tmp_path / "output-styles" / "ignored.md",
        tmp_path / "custom" / "styles" / "compact.md",
        tmp_path / "skills" / "default" / "SKILL.md",
        tmp_path / "custom" / "skills" / "extra" / "SKILL.md",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(path.name, encoding="utf-8")

    resources = resolve_claude_plugin_resources(tmp_path)

    locators = {item.source_locator for item in resources.file_resources}
    assert locators == {
        "custom/commands/deploy.md",
        "custom/reviewer.md",
        "custom/styles/compact.md",
        "custom/skills/extra/SKILL.md",
    }
    assert resources.diagnostics == ()


def test_file_component_resolver_rejects_source_escape(tmp_path: Path) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","commands":"../outside"}',
        encoding="utf-8",
    )

    resources = resolve_claude_plugin_resources(tmp_path)

    assert resources.file_resources == ()
    assert resources.diagnostics[0].code == "source-reference-invalid"


def test_resolves_inline_claude_mcp_and_hook_entries(tmp_path: Path) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        """
        {
          "name": "demo",
          "mcpServers": {"local/server": {"command": "node"}},
          "hooks": {"PreToolUse": [{"hooks": [{"type": "command"}]}]}
        }
        """,
        encoding="utf-8",
    )

    resources = resolve_claude_plugin_resources(tmp_path)

    assert (
        resources.mcp_servers["local/server"].json_pointer
        == "/mcpServers/local~1server"
    )
    assert resources.hooks is not None
    assert resources.hooks.json_pointer == "/hooks"
    assert resources.hook_entries[0].json_pointer == "/hooks/PreToolUse/0"
    assert resources.diagnostics == ()


def test_resolves_claude_default_direct_map_mcp_and_hook_document(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text('{"name":"demo"}', encoding="utf-8")
    (tmp_path / ".mcp.json").write_text(
        '{"direct":{"command":"node"}}',
        encoding="utf-8",
    )
    hooks = tmp_path / "hooks" / "hooks.json"
    hooks.parent.mkdir()
    hooks.write_text(
        '{"hooks":{"PostToolUse":[{"hooks":[]}]}}',
        encoding="utf-8",
    )

    resources = resolve_claude_plugin_resources(tmp_path)

    assert resources.mcp_servers["direct"].json_pointer == "/direct"
    assert resources.hooks is not None
    assert resources.hooks.file_path == "hooks/hooks.json"
    assert resources.hook_entries[0].json_pointer == "/hooks/PostToolUse/0"


def test_claude_resolver_reports_unsafe_and_wrong_extension_references(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","mcpServers":"../outside.json","hooks":"hooks.yaml"}',
        encoding="utf-8",
    )
    (tmp_path / "hooks.yaml").write_text("hooks: {}", encoding="utf-8")

    resources = resolve_claude_plugin_resources(tmp_path)

    assert resources.mcp_servers == {}
    assert resources.hooks is None
    assert {(item.code, item.source_locator) for item in resources.diagnostics} == {
        ("source-not-allowed", "hooks.yaml"),
        ("source-reference-invalid", "../outside.json"),
    }


def test_claude_resolver_reports_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text('{"server":{"command":"node"}}', encoding="utf-8")
    package = tmp_path / "package"
    manifest = package / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"demo","mcpServers":"config/mcp.json"}',
        encoding="utf-8",
    )
    config = package / "config"
    config.mkdir()
    os.symlink("../../outside.json", config / "mcp.json")

    resources = resolve_claude_plugin_resources(package)

    assert resources.mcp_servers == {}
    assert resources.diagnostics[0].code == "source-reference-invalid"


def test_claude_resolver_rejects_malformed_inline_components(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".claude-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        """
        {
          "name": "demo",
          "mcpServers": {"invalid": "not-an-object"},
          "hooks": {"Stop": ["not-an-object"]}
        }
        """,
        encoding="utf-8",
    )

    resources = resolve_claude_plugin_resources(tmp_path)

    assert resources.mcp_servers == {}
    assert resources.hooks is not None
    assert resources.hooks.file_path == ".claude-plugin/plugin.json"
    assert resources.hooks.json_pointer == "/hooks"
    assert resources.hook_sources == (resources.hooks,)
    assert {(item.code, item.source_locator) for item in resources.diagnostics} == {
        (
            "source-document-invalid",
            ".claude-plugin/plugin.json#/mcpServers",
        ),
        (
            "source-document-invalid",
            ".claude-plugin/plugin.json#/hooks",
        ),
    }
