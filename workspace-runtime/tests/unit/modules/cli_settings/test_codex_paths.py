from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.cli_settings.codex_paths import (
    CodexLayer,
    CodexPathResolver,
    CodexResource,
    get_codex_path_resolver,
)


def test_codex_path_resolver_uses_managed_home_and_workspace_paths() -> None:
    resolver = CodexPathResolver(
        user_home=Path("/home/developer"),
        workspace_root=Path("/workspace"),
    )

    assert resolver.codex_home == Path("/home/developer/.codex")
    assert resolver.resolve(CodexLayer.USER, CodexResource.AGENTS_MD) == Path("/home/developer/.codex/AGENTS.md")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.AGENTS_MD) == Path("/workspace/AGENTS.md")
    assert resolver.resolve(CodexLayer.USER, CodexResource.CONFIG) == Path("/home/developer/.codex/config.toml")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.CONFIG) == Path("/workspace/.codex/config.toml")
    assert resolver.resolve(CodexLayer.USER, CodexResource.SKILLS) == Path("/home/developer/.agents/skills")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.SKILLS) == Path("/workspace/.agents/skills")
    assert resolver.resolve(CodexLayer.USER, CodexResource.SUBAGENTS) == Path("/home/developer/.codex/agents")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.SUBAGENTS) == Path("/workspace/.codex/agents")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.HOOKS) == Path("/workspace/.codex/hooks.json")
    assert resolver.resolve(CodexLayer.PROJECT, CodexResource.MANAGED_REQUIREMENTS) == Path("/workspace/.codex/requirements.toml")


def test_codex_path_resolver_rejects_unknown_layer_or_resource() -> None:
    resolver = CodexPathResolver()

    with pytest.raises(ValueError):
        resolver.resolve("local", CodexResource.CONFIG)

    with pytest.raises(ValueError):
        resolver.resolve(CodexLayer.USER, "unknown")


def test_get_codex_path_resolver_uses_runtime_workspace_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.modules.cli_settings.codex_paths.get_workspace_path",
        lambda: "/workspace/custom",
    )

    resolver = get_codex_path_resolver()

    assert resolver.codex_home == Path("/home/developer/.codex")
    assert resolver.workspace_root == Path("/workspace/custom")
