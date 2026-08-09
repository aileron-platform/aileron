from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def _initializer() -> Path:
    return (
        Path(__file__).resolve().parents[4] / "scripts" / "initialize_agent_defaults.sh"
    )


def _environment(tmp_path: Path, source: Path) -> dict[str, str]:
    home = tmp_path / "home"
    return {
        **os.environ,
        "AILERON_AGENT_DEFAULTS_SOURCE": str(source),
        "AILERON_WORKSPACE_PATH": str(tmp_path / "workspace"),
        "HOME": str(home),
        "CODEX_HOME": str(home / ".codex"),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "XDG_STATE_HOME": str(home / ".local" / "state"),
    }


def _defaults_source(tmp_path: Path) -> Path:
    source = tmp_path / "defaults"
    skill = source / "skills" / "example-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    (source / "mcp.json").write_text("{}\n", encoding="utf-8")
    (source / "CLAUDE.md").write_text("Claude policy\n", encoding="utf-8")
    (source / "AGENTS.md").write_text("Agent policy\n", encoding="utf-8")
    return source


def test_initializer_seeds_once_and_does_not_restore_deleted_defaults(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    workspace.mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    skill = workspace / ".agents" / "skills" / "example-skill"
    marker = (
        Path(environment["XDG_STATE_HOME"])
        / "aileron"
        / "bootstrap"
        / "agent-defaults-v1.json"
    )
    layout_marker = marker.with_name("agent-defaults-v2.json")
    assert (skill / "SKILL.md").read_text(encoding="utf-8") == "# Example\n"
    assert (workspace / ".claude" / "skills").resolve() == (
        workspace / ".agents" / "skills"
    ).resolve()
    for tool in (".codex", ".opencode"):
        assert (workspace / tool / "skills" / "example-skill" / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# Example\n"
    assert json.loads(marker.read_text(encoding="utf-8"))["schemaVersion"] == 1
    assert json.loads(layout_marker.read_text(encoding="utf-8"))["schemaVersion"] == 2

    (skill / "SKILL.md").unlink()
    skill.rmdir()
    layout_marker.unlink()
    subprocess.run([str(_initializer())], env=environment, check=True)

    assert not skill.exists()


def test_initializer_upgrades_existing_workspace_without_overwriting_skills(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    workspace.mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    marker_dir = Path(environment["XDG_STATE_HOME"]) / "aileron" / "bootstrap"
    (marker_dir / "agent-defaults-v2.json").unlink()
    codex_skill = workspace / ".codex" / "skills" / "example-skill"
    codex_skill.joinpath("SKILL.md").write_text(
        "# Project override\n",
        encoding="utf-8",
    )
    opencode_skill = workspace / ".opencode" / "skills" / "example-skill"
    opencode_skill.joinpath("SKILL.md").unlink()
    opencode_skill.rmdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    assert codex_skill.joinpath("SKILL.md").read_text(encoding="utf-8") == (
        "# Project override\n"
    )
    assert opencode_skill.joinpath("SKILL.md").read_text(encoding="utf-8") == (
        "# Example\n"
    )
    assert (
        json.loads((marker_dir / "agent-defaults-v2.json").read_text(encoding="utf-8"))[
            "schemaVersion"
        ]
        == 2
    )


def test_initializer_does_not_follow_tool_skills_symlink(tmp_path: Path) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    workspace = Path(environment["AILERON_WORKSPACE_PATH"])
    workspace.mkdir()

    subprocess.run([str(_initializer())], env=environment, check=True)

    marker_dir = Path(environment["XDG_STATE_HOME"]) / "aileron" / "bootstrap"
    (marker_dir / "agent-defaults-v2.json").unlink()
    opencode_skills = workspace / ".opencode" / "skills"
    external_skills = tmp_path / "external-skills"
    external_skills.mkdir()
    shutil.rmtree(opencode_skills)
    opencode_skills.symlink_to(external_skills, target_is_directory=True)

    subprocess.run([str(_initializer())], env=environment, check=True)

    assert opencode_skills.is_symlink()
    assert not list(external_skills.iterdir())


def test_initializer_rejects_conflicting_workspace_skills_layout(
    tmp_path: Path,
) -> None:
    source = _defaults_source(tmp_path)
    environment = _environment(tmp_path, source)
    conflict = Path(environment["AILERON_WORKSPACE_PATH"]) / ".claude" / "skills"
    conflict.mkdir(parents=True)

    result = subprocess.run(
        [str(_initializer())],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "AGENT_DEFAULTS_INIT_FAILED" in result.stderr
