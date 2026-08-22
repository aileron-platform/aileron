import json
from pathlib import Path

from app.modules.marketplace.resource_resolvers import (
    resolve_mcp_owner,
    resolve_mcp_owners,
)


def _write_manifest(
    package_root: Path,
    target_client: str,
    data: dict,
) -> None:
    manifest_path = package_root / (
        ".claude-plugin/plugin.json"
        if target_client == "claude-code"
        else ".codex-plugin/plugin.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")


def test_resolves_claude_inline_mcp_owner(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "claude-code",
        {
            "name": "demo",
            "mcpServers": {"local/server": {"command": "node"}},
        },
    )

    bindings = resolve_mcp_owners(tmp_path, "claude-code")

    assert [(binding.name, binding.owner.file_path) for binding in bindings] == [
        ("local/server", ".claude-plugin/plugin.json")
    ]
    assert bindings[0].owner.json_pointer == "/mcpServers/local~1server"
    assert bindings[0].owner.standalone_file is False


def test_resolves_only_canonical_claude_owner_for_duplicate_name(
    tmp_path: Path,
) -> None:
    _write_manifest(
        tmp_path,
        "claude-code",
        {
            "name": "demo",
            "mcpServers": ["config/primary.json", "config/secondary.json"],
        },
    )
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "primary.json").write_text(
        '{"shared":{"command":"node"}}',
        encoding="utf-8",
    )
    (config_root / "secondary.json").write_text(
        '{"shared":{"command":"python"}}',
        encoding="utf-8",
    )

    bindings = resolve_mcp_owners(tmp_path, "claude-code")

    assert [
        (binding.name, binding.owner.file_path, binding.owner.json_pointer)
        for binding in bindings
    ] == [
        ("shared", "config/primary.json", "/shared"),
    ]
    primary = resolve_mcp_owner(
        tmp_path,
        "claude-code",
        "shared",
        owner_file_path="config/primary.json",
    )
    assert primary is not None
    assert primary.file_path == "config/primary.json"
    assert (
        resolve_mcp_owner(
            tmp_path,
            "claude-code",
            "shared",
            owner_file_path="config/secondary.json",
        )
        is None
    )


def test_resolves_claude_referenced_wrapped_mcp_map(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path,
        "claude-code",
        {"name": "demo", "mcpServers": "config/mcp.json"},
    )
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "mcp.json").write_text(
        '{"mcpServers":{"remote":{"url":"https://example.test"}}}',
        encoding="utf-8",
    )

    bindings = resolve_mcp_owners(tmp_path, "claude-code")

    assert bindings[0].owner.file_path == "config/mcp.json"
    assert bindings[0].owner.json_pointer == "/mcpServers/remote"


def test_resolves_codex_default_wrapped_mcp_map(tmp_path: Path) -> None:
    _write_manifest(tmp_path, "codex", {"name": "demo"})
    (tmp_path / ".mcp.json").write_text(
        '{"mcpServers":{"local":{"command":"node"}}}',
        encoding="utf-8",
    )

    bindings = resolve_mcp_owners(tmp_path, "codex")

    assert [(binding.name, binding.owner.file_path) for binding in bindings] == [
        ("local", ".mcp.json")
    ]
    assert bindings[0].owner.json_pointer == "/mcpServers/local"
