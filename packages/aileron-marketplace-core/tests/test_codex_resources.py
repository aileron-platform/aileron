import os
from pathlib import Path

from aileron_marketplace_core.codex_resources import (
    CodexPluginResourceOwner,
    resolve_codex_plugin_resources,
)


def test_resolves_manifest_mcp_servers_and_hooks(tmp_path: Path) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo",'
        '"mcpServers":{"local":{"command":"node"}},'
        '"hooks":{"PreToolUse":[]}}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers["local"] == CodexPluginResourceOwner(
        file_path=".codex-plugin/plugin.json",
        json_pointer="/mcpServers/local",
        standalone_file=False,
    )
    assert resources.hooks.file_path == ".codex-plugin/plugin.json"
    assert resources.hooks.json_pointer == "/hooks"


def test_resolves_referenced_mcp_file(tmp_path: Path) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","mcp_servers":"config/mcp.json"}', encoding="utf-8"
    )
    mcp = tmp_path / "config" / "mcp.json"
    mcp.parent.mkdir()
    mcp.write_text(
        '{"mcpServers":{"remote":{"url":"http://localhost"}}}', encoding="utf-8"
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers["remote"].file_path == "config/mcp.json"
    assert resources.mcp_servers["remote"].json_pointer == "/mcpServers/remote"


def test_default_mcp_matches_runtime_and_ignores_mcp_json_without_manifest_reference(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text('{"name":"demo"}', encoding="utf-8")
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers":{"dot":{"command":"node"}}}',
        encoding="utf-8",
    )
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers":{"plain":{"command":"python"}}}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert set(resources.mcp_servers) == {"dot"}


def test_rejects_absolute_and_parent_relative_manifest_references(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","mcp_servers":"../outside.json","hooks":"/tmp/hooks.json"}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers == {}
    assert resources.hooks is None


def test_resolves_direct_map_mcp_and_hook_entry_owners(tmp_path: Path) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","mcp_servers":"config/mcp.json","hooks":"config/hooks.json"}',
        encoding="utf-8",
    )
    config = tmp_path / "config"
    config.mkdir()
    (config / "mcp.json").write_text(
        '{"direct/server":{"command":"node"}}',
        encoding="utf-8",
    )
    (config / "hooks.json").write_text(
        '{"hooks":{"SessionStart":[{"command":"echo"}]}}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers["direct/server"].json_pointer == "/direct~1server"
    assert resources.hooks is not None
    assert resources.hook_entries[0].json_pointer == "/hooks/SessionStart/0"
    assert resources.diagnostics == ()


def test_reports_wrong_extension_and_symlink_escape(tmp_path: Path) -> None:
    package = tmp_path / "package"
    manifest = package / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        '{"name":"demo","mcp_servers":"config/mcp.yaml","hooks":"config/hooks.json"}',
        encoding="utf-8",
    )
    config = package / "config"
    config.mkdir()
    (config / "mcp.yaml").write_text("{}", encoding="utf-8")
    outside = tmp_path / "outside.json"
    outside.write_text('{"hooks":{}}', encoding="utf-8")
    os.symlink("../../outside.json", config / "hooks.json")

    resources = resolve_codex_plugin_resources(package)

    assert resources.mcp_servers == {}
    assert resources.hooks is None
    assert {item.code for item in resources.diagnostics} == {
        "source-not-allowed",
        "source-reference-invalid",
    }


def test_invalid_manifest_fails_closed_with_package_relative_diagnostic(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text("{invalid", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers":{"must-not-load":{"command":"node"}}}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers == {}
    assert resources.hooks is None
    assert [(item.code, item.source_locator) for item in resources.diagnostics] == [
        ("source-document-invalid", ".codex-plugin/plugin.json"),
    ]


def test_malformed_structured_documents_are_rejected(tmp_path: Path) -> None:
    manifest = tmp_path / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir()
    manifest.write_text(
        '{"name":"demo","mcpServers":"mcp.json","hooks":"hooks.json"}',
        encoding="utf-8",
    )
    (tmp_path / "mcp.json").write_text(
        '{"mcpServers":["not-an-object"]}',
        encoding="utf-8",
    )
    (tmp_path / "hooks.json").write_text(
        '{"hooks":{"SessionStart":["not-an-object"]}}',
        encoding="utf-8",
    )

    resources = resolve_codex_plugin_resources(tmp_path)

    assert resources.mcp_servers == {}
    assert resources.hooks is not None
    assert resources.hooks.file_path == "hooks.json"
    assert resources.hook_sources == (resources.hooks,)
    assert {(item.code, item.source_locator) for item in resources.diagnostics} == {
        ("source-document-invalid", "mcp.json"),
        ("source-document-invalid", "hooks.json"),
    }
