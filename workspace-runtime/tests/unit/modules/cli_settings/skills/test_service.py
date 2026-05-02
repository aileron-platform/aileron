from __future__ import annotations

from pathlib import Path
import pytest

from app.modules.cli_settings.skills.config import SkillScope, SkillTool, SkillToolConfig, get_skill_config
from app.modules.cli_settings.skills.service import CliSkillService
from app.modules.file_system import InvalidScopeException


@pytest.fixture
def skill_config(tmp_path: Path) -> SkillToolConfig:
    return SkillToolConfig(
        tool=SkillTool.GEMINI,
        project_dot_dir=".gemini",
        skill_dir_name="skills",
        user_root=tmp_path / "user-skills",
        supports_plugin=False,
        api_prefix="gemini",
    )


def test_scope_resolution_validation_and_readonly(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))
    service = CliSkillService(skill_config, workspace_id="ws-1")

    assert service.validate_scope(None) is True
    assert service.validate_scope(SkillScope.PROJECT) is True
    assert service.validate_scope(SkillScope.USER) is True
    assert service.validate_scope(SkillScope.PLUGIN) is False
    assert service.is_readonly_scope(SkillScope.PLUGIN) is False

    project_path = service.resolve_scope_path(SkillScope.PROJECT, "/demo/skill.md")
    user_path = service.resolve_scope_path(SkillScope.USER, "demo/skill.md")

    assert project_path == tmp_path / "workspace" / ".gemini" / "skills" / "demo" / "skill.md"
    assert user_path == skill_config.user_root / "demo" / "skill.md"

    with pytest.raises(InvalidScopeException):
        service.resolve_scope_path("invalid", "demo.md")


def test_plugin_scope_is_not_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = SkillToolConfig(
        tool=SkillTool.GEMINI,
        project_dot_dir=".gemini",
        skill_dir_name="skills",
        user_root=tmp_path / "user-skills",
        supports_plugin=False,
        api_prefix="gemini",
    )
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))
    service = CliSkillService(config, workspace_id="ws-2")

    assert service.validate_scope(SkillScope.PLUGIN) is False


def test_codex_config_uses_codex_skill_directories() -> None:
    config = get_skill_config(SkillTool.CODEX)

    assert config.project_dot_dir == ".codex"
    assert config.user_root == Path.home() / ".codex" / "skills"


def test_codex_project_tree_reads_from_dot_codex(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    codex_config = SkillToolConfig(
        tool=SkillTool.CODEX,
        project_dot_dir=".codex",
        skill_dir_name="skills",
        user_root=tmp_path / "user-codex-skills",
        supports_plugin=False,
        api_prefix="codex",
    )
    workspace_root = tmp_path / "workspace"
    skill_file = workspace_root / ".codex" / "skills" / "openspec-explore" / "SKILL.md"
    skill_file.parent.mkdir(parents=True, exist_ok=True)
    skill_file.write_text("---\nname: openspec-explore\n---\nbody\n", encoding="utf-8")

    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(workspace_root))
    service = CliSkillService(codex_config, workspace_id="ws-codex")

    tree = service.get_tree("/", SkillScope.PROJECT, include_hidden=False, max_depth=3)

    assert tree["path"] == "/"
    assert tree["nodes"][0]["name"] == "openspec-explore"
    assert tree["nodes"][0]["path"] == "/openspec-explore"
    assert tree["nodes"][0]["children"][0]["name"] == "SKILL.md"
