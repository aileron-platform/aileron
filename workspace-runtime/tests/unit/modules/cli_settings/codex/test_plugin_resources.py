from __future__ import annotations

from pathlib import Path

from app.modules.cli_settings.codex.plugin_resources import CodexPluginResourceResolver
from app.modules.cli_settings.codex_paths import CodexPathResolver


def _plugin_resolver(tmp_path: Path) -> CodexPluginResourceResolver:
    return CodexPluginResourceResolver(
        CodexPathResolver(
            user_home=tmp_path / "home" / "developer",
            workspace_root=tmp_path / "workspace",
        ),
    )


def test_plugin_resource_resolver_discovers_documented_defaults(tmp_path: Path) -> None:
    resolver = _plugin_resolver(tmp_path)
    codex_home = tmp_path / "home" / "developer" / ".codex"
    package_root = codex_home / "plugins" / "cache" / "local" / "demo" / "abc"
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","name":"Demo"}', encoding="utf-8")
    skill = package_root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")
    (package_root / ".mcp.json").write_text(
        '{"mcpServers":{"docs":{"command":"npx","args":["-y","docs-mcp"]}}}',
        encoding="utf-8",
    )
    hooks = package_root / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text('{"SessionStart":[{"hooks":[{"type":"command","command":"echo ready"}]}]}', encoding="utf-8")

    assert resolver.packages()[0].plugin_id == "demo@local"
    assert resolver.skills()[0].relative_path == "review/SKILL.md"
    assert resolver.mcp_servers()[0].name == "docs"
    assert resolver.hook_documents()[0].source_path == hooks
    assert resolver.skills({"other@local"}) == []
    assert resolver.mcp_servers({"demo@local"})[0].name == "docs"
    assert resolver.hook_documents({"other@local"}) == []


def test_plugin_resource_resolver_rejects_unsafe_manifest_paths(tmp_path: Path) -> None:
    resolver = _plugin_resolver(tmp_path)
    codex_home = tmp_path / "home" / "developer" / ".codex"
    package_root = codex_home / ".tmp" / "plugins" / "plugins" / "unsafe"
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"id":"unsafe","marketplace":"local","skills":"../skills","mcpServers":"/tmp/mcp.json","hooks":"../hooks.json"}',
        encoding="utf-8",
    )

    assert resolver.skills() == []
    assert resolver.mcp_servers() == []
    assert resolver.hook_documents() == []


def test_plugin_resource_resolver_discovers_tmp_clone_marketplace_packages(tmp_path: Path) -> None:
    resolver = _plugin_resolver(tmp_path)
    codex_home = tmp_path / "home" / "developer" / ".codex"
    clone_root = codex_home / ".tmp" / "plugins-clone-test"
    marketplace = clone_root / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text('{"name":"openai-curated","plugins":[{"name":"github"}]}', encoding="utf-8")
    package_root = clone_root / "plugins" / "github"
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"name":"github","skills":"./skills"}', encoding="utf-8")
    skill = package_root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")

    skills = resolver.skills({"github@openai-curated"})

    assert len(skills) == 1
    assert skills[0].plugin.plugin_id == "github@openai-curated"


def test_plugin_resource_resolver_reuses_package_discovery(tmp_path: Path, monkeypatch) -> None:
    resolver = _plugin_resolver(tmp_path)
    codex_home = tmp_path / "home" / "developer" / ".codex"
    package_root = codex_home / "plugins" / "cache" / "local" / "demo" / "abc"
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","name":"Demo"}', encoding="utf-8")
    skill = package_root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")

    calls = 0
    original = resolver._manifest_paths

    def counted_manifest_paths():
        nonlocal calls
        calls += 1
        return original()

    monkeypatch.setattr(resolver, "_manifest_paths", counted_manifest_paths)

    assert resolver.skills({"demo@local"})[0].name == "review"
    assert resolver.mcp_servers({"demo@local"}) == []
    assert calls == 1

    resolver.clear_cache()
    assert resolver.skills({"demo@local"})[0].name == "review"
    assert calls == 2
