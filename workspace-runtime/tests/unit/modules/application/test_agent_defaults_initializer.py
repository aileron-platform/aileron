from __future__ import annotations

import json
import os
import stat
import shutil
import subprocess
from pathlib import Path


def _initializer() -> Path:
    return (
        Path(__file__).resolve().parents[4] / "scripts" / "initialize_agent_defaults.sh"
    )


def _environment(tmp_path: Path, source: Path, **overrides: str) -> dict[str, str]:
    home = tmp_path / "home"
    environment = {
        **os.environ,
        "AILERON_AGENT_DEFAULTS_SOURCE": str(source),
        "AILERON_WORKSPACE_PATH": str(tmp_path / "workspace"),
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
    }
    environment.update(overrides)
    return environment


def _defaults_source(tmp_path: Path) -> Path:
    source = tmp_path / "defaults"
    skill = source / "skills" / "example-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    (source / "mcp.json").write_text("{}\n", encoding="utf-8")
    (source / "CLAUDE.md").write_text("Claude policy\n", encoding="utf-8")
    (source / "AGENTS.md").write_text("Agent policy\n", encoding="utf-8")
    return source


def _marker(environment: dict[str, str]) -> Path:
    return (
        Path(environment["XDG_STATE_HOME"])
        / "aileron"
        / "bootstrap"
        / "agent-defaults-v1.json"
    )


def test_initializer_seeds_default_skills_into_each_client_user_scope(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    home = Path(environment["HOME"])
    claude_skill = home / ".claude" / "skills" / "example-skill" / "SKILL.md"
    codex_skill = home / ".codex" / "skills" / "example-skill" / "SKILL.md"
    opencode_skill = (
        home / ".config" / "opencode" / "skills" / "example-skill" / "SKILL.md"
    )
    assert claude_skill.read_text(encoding="utf-8") == "# Example\n"
    assert codex_skill.read_text(encoding="utf-8") == "# Example\n"
    assert opencode_skill.read_text(encoding="utf-8") == "# Example\n"
    assert not (Path(environment["AILERON_WORKSPACE_PATH"]) / ".agents").exists()
    assert not claude_skill.parent.parent.is_symlink()
    assert not codex_skill.parent.parent.is_symlink()
    assert not opencode_skill.parent.parent.is_symlink()
    for path in (
        home / ".claude",
        home / ".claude" / "skills",
        claude_skill.parent,
        claude_skill,
        home / ".codex",
        home / ".codex" / "skills",
        codex_skill.parent,
        codex_skill,
        home / ".config" / "opencode",
        home / ".config" / "opencode" / "skills",
        opencode_skill.parent,
        opencode_skill,
    ):
        assert path.stat().st_mode & stat.S_IWGRP, path
    marker = _marker(environment)
    assert marker.is_file()
    assert json.loads(marker.read_text(encoding="utf-8"))["schemaVersion"] == 1


def test_initializer_keeps_independent_copies_per_client(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    home = Path(environment["HOME"])
    claude_skill = home / ".claude" / "skills" / "example-skill" / "SKILL.md"
    codex_skill = home / ".codex" / "skills" / "example-skill" / "SKILL.md"

    assert not claude_skill.is_symlink()
    assert not codex_skill.is_symlink()
    claude_skill.write_text("# Claude edit\n", encoding="utf-8")

    assert codex_skill.read_text(encoding="utf-8") == "# Example\n"


def test_initializer_honors_client_home_overrides(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    codex_home = tmp_path / "custom-codex-home"
    claude_config_dir = tmp_path / "custom-claude-home"
    environment = _environment(
        tmp_path,
        source,
        CODEX_HOME=str(codex_home),
        CLAUDE_CONFIG_DIR=str(claude_config_dir),
    )
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    assert (codex_home / "skills" / "example-skill" / "SKILL.md").is_file()
    assert (claude_config_dir / "skills" / "example-skill" / "SKILL.md").is_file()


def test_initializer_does_not_restore_a_deleted_skill_on_rerun(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    home = Path(environment["HOME"])
    codex_skill = home / ".codex" / "skills" / "example-skill"
    shutil.rmtree(codex_skill)

    subprocess.run([str(_initializer())], env=environment, check=True)

    assert not codex_skill.exists()


def test_initializer_does_not_overwrite_an_existing_same_named_skill(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()
    home = Path(environment["HOME"])
    existing_skill = home / ".claude" / "skills" / "example-skill"
    existing_skill.mkdir(parents=True)
    (existing_skill / "SKILL.md").write_text("# Workspace owned\n", encoding="utf-8")

    subprocess.run([str(_initializer())], env=environment, check=True)

    assert (existing_skill / "SKILL.md").read_text(encoding="utf-8") == (
        "# Workspace owned\n"
    )


def test_initializer_rejects_symlinked_client_scope_root_without_writing_marker(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()
    home = Path(environment["HOME"])
    home.mkdir(parents=True, exist_ok=True)
    external = tmp_path / "external-codex-home"
    external.mkdir()
    (home / ".codex").symlink_to(external, target_is_directory=True)

    result = subprocess.run(
        [str(_initializer())],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "AGENT_DEFAULTS_INIT_FAILED" in result.stderr
    assert not list(external.iterdir())
    assert not (home / ".claude" / "skills").exists()
    assert not _marker(environment).exists()


def test_initializer_rejects_symlinked_skills_target_without_writing_marker(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()
    home = Path(environment["HOME"])
    claude_home = home / ".claude"
    claude_home.mkdir(parents=True)
    external = tmp_path / "external-claude-skills"
    external.mkdir()
    (claude_home / "skills").symlink_to(external, target_is_directory=True)

    result = subprocess.run(
        [str(_initializer())],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "AGENT_DEFAULTS_INIT_FAILED" in result.stderr
    assert not list(external.iterdir())
    assert not (home / ".codex" / "skills").exists()
    assert not _marker(environment).exists()


def test_initializer_rejects_a_non_directory_client_scope_root(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()
    home = Path(environment["HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / ".config").mkdir(parents=True, exist_ok=True)
    (home / ".config" / "opencode").write_text("not a directory\n", encoding="utf-8")

    result = subprocess.run(
        [str(_initializer())],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "AGENT_DEFAULTS_INIT_FAILED" in result.stderr
    assert not (home / ".codex" / "skills").exists()
    assert not (home / ".claude" / "skills").exists()
    assert not _marker(environment).exists()


def test_initializer_still_places_mcp_claude_and_agents_defaults(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    Path(environment["AILERON_WORKSPACE_PATH"]).mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    home = Path(environment["HOME"])
    assert (workspace / ".mcp.json").read_text(encoding="utf-8") == "{}\n"
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == (
        "Claude policy\n"
    )
    assert (home / ".codex" / "AGENTS.md").read_text(encoding="utf-8") == (
        "Agent policy\n"
    )
    assert (home / ".config" / "opencode" / "AGENTS.md").read_text(
        encoding="utf-8"
    ) == "Agent policy\n"
