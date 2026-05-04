from __future__ import annotations

import json
import inspect
import subprocess
from pathlib import Path

import pytest

from app.modules.cli_settings.gemini import extension_resources
from app.modules.cli_settings.gemini.extension_resources import (
    GeminiExtensionResourceResolver,
    disable,
    enable,
    is_enabled_for,
    resolve_toggle_cwd,
)
from app.modules.cli_settings.gemini.models import (
    GeminiExtensionCommandError,
    GeminiExtensionToggleScope,
)
from app.modules.cli_settings.gemini.router import _summary


def test_is_enabled_for_uses_glob_negation_last_match_and_realpath(tmp_path: Path) -> None:
    workspace = tmp_path / "real" / "project"
    workspace.mkdir(parents=True)
    symlink = tmp_path / "link"
    symlink.symlink_to(workspace)

    assert is_enabled_for([f"{tmp_path}/real/**"], symlink)
    assert not is_enabled_for([f"{tmp_path}/real/**", f"!{workspace}"], symlink)
    assert is_enabled_for([f"!{tmp_path}/real/**", f"{workspace}"], symlink)
    assert is_enabled_for([f"{tmp_path}/other/**"], workspace)


def test_is_enabled_for_defaults_to_enabled_and_uses_disable_overrides(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home" / "developer"
    home.mkdir(parents=True)

    assert is_enabled_for([], workspace)
    assert is_enabled_for([f"!{home}/*"], workspace)
    assert not is_enabled_for([f"!{home}/*"], home)


def test_is_enabled_for_treats_gemini_workspace_star_pattern_as_root_match(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    assert is_enabled_for([f"{workspace}/*"], workspace)
    assert not is_enabled_for([f"{workspace}/*", f"!{workspace}/*"], workspace)
    assert is_enabled_for([f"!{workspace}/*", f"{workspace}/*"], workspace)


def test_resolver_reads_enabled_extension_contributions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    extensions_dir = tmp_path / ".gemini" / "extensions"
    extension_dir = extensions_dir / "demo"
    (extension_dir / "commands" / "ops").mkdir(parents=True)
    (extension_dir / "skills" / "review").mkdir(parents=True)
    (extension_dir / "hooks").mkdir()
    (extension_dir / "policies").mkdir()

    (extension_dir / "gemini-extension.json").write_text(
        json.dumps(
            {
                "name": "demo",
                "version": "1.2.3",
                "description": "Demo extension",
                "mcpServers": {"fs": {"command": "node", "args": ["${extensionPath}${/}server.js"]}},
                "excludeTools": ["Shell"],
            }
        ),
        encoding="utf-8",
    )
    (extension_dir / ".gemini-extension-install.json").write_text(
        json.dumps({"source": "github:example/demo", "type": "git", "releaseTag": "v1.2.3"}),
        encoding="utf-8",
    )
    (extension_dir / "commands" / "ops" / "deploy.toml").write_text(
        'description = "Deploy"\nprompt = "ship it"\n',
        encoding="utf-8",
    )
    (extension_dir / "skills" / "review" / "SKILL.md").write_text("# Review\n", encoding="utf-8")
    (extension_dir / "hooks" / "hooks.json").write_text(
        json.dumps({"hooks": {"SessionStart": [{"matcher": "*", "hooks": [{"type": "command", "command": "echo hi"}]}]}}),
        encoding="utf-8",
    )
    (extension_dir / "policies" / "policy.toml").write_text("allow = true\n", encoding="utf-8")
    (extension_dir / "GEMINI.md").write_text("context\n", encoding="utf-8")
    (extensions_dir / "extension-enablement.json").write_text(
        json.dumps({"demo": {"overrides": [f"{workspace}"]}}),
        encoding="utf-8",
    )

    resolver = GeminiExtensionResourceResolver(extensions_dir)
    package = resolver.list_extensions(workspace)[0]

    assert package.enabledHere is True
    assert package.description == "Demo extension"
    assert package.installInfo is not None
    assert package.installInfo.source == "github:example/demo"
    assert package.mcpServers[0].name == "fs"
    assert package.slashCommands[0].namespace == "ops"
    assert package.skills[0].name == "review"
    assert package.hooks[0].hooks["SessionStart"][0]["matcher"] == "*"
    assert package.policies[0].content == "allow = true\n"
    assert package.contextFile is not None
    assert package.contextFile.content == "context\n"
    assert _summary(package).contextFileName == "GEMINI.md"
    assert package.excludeTools == ["Shell"]


def test_resolver_derives_description_from_context_when_manifest_description_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    extensions_dir = tmp_path / ".gemini" / "extensions"
    extension_dir = extensions_dir / "demo"
    extension_dir.mkdir(parents=True)

    (extension_dir / "gemini-extension.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")
    (extension_dir / "GEMINI.md").write_text(
        "\n# Demo Extension\n\nSecond paragraph should not be used.\n",
        encoding="utf-8",
    )

    package = GeminiExtensionResourceResolver(extensions_dir).list_extensions(workspace)[0]

    assert package.description == "Demo Extension"


def test_resolver_keeps_description_empty_when_manifest_and_context_missing(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    extensions_dir = tmp_path / ".gemini" / "extensions"
    extension_dir = extensions_dir / "demo"
    extension_dir.mkdir(parents=True)

    (extension_dir / "gemini-extension.json").write_text(
        json.dumps({"name": "demo", "description": "   "}),
        encoding="utf-8",
    )

    package = GeminiExtensionResourceResolver(extensions_dir).list_extensions(workspace)[0]

    assert package.description is None


def test_toggle_wrapper_uses_expected_argv_and_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], str]] = []

    def fake_run(command, cwd, capture_output, text, check):
        calls.append((command, cwd))
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(extension_resources.subprocess, "run", fake_run)

    enable("demo", GeminiExtensionToggleScope.WORKSPACE, tmp_path)
    disable("demo", GeminiExtensionToggleScope.USER, tmp_path)

    assert calls == [
        (["gemini", "extensions", "enable", "demo", "--scope=workspace"], str(tmp_path)),
        (["gemini", "extensions", "disable", "demo", "--scope=user"], str(tmp_path)),
    ]


def test_toggle_wrapper_surfaces_stderr(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(command, cwd, capture_output, text, check):
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="boom")

    monkeypatch.setattr(extension_resources.subprocess, "run", fake_run)

    with pytest.raises(GeminiExtensionCommandError) as error:
        enable("demo", GeminiExtensionToggleScope.WORKSPACE, tmp_path)

    assert error.value.stderr == "boom"
    assert error.value.command == ["gemini", "extensions", "enable", "demo", "--scope=workspace"]


def test_extension_resource_module_does_not_directly_write_cli_owned_files() -> None:
    source = inspect.getsource(extension_resources)

    assert "extension_integrity.json" not in source
    assert ".write_text(" not in source
    assert ".open(" not in source


def test_resolve_toggle_cwd_uses_workspace_realpath_and_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(extension_resources.Path, "home", lambda: home)

    assert resolve_toggle_cwd(GeminiExtensionToggleScope.WORKSPACE, workspace) == workspace
    assert resolve_toggle_cwd(GeminiExtensionToggleScope.USER, workspace) == home
