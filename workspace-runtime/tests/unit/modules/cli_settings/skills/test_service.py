from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.cli_settings.skills.config import SkillScope, SkillTool, SkillToolConfig, get_skill_config
from app.modules.cli_settings.skills.service import CliSkillService
from app.modules.file_system import InvalidScopeException


@pytest.fixture
def skill_config(tmp_path: Path) -> SkillToolConfig:
    return SkillToolConfig(
        tool=SkillTool.CLAUDE,
        project_dot_dir=".claude",
        skill_dir_name="skills",
        user_root=tmp_path / "user-skills",
        supports_plugin=True,
        api_prefix="claude-code",
    )


def test_scope_resolution_validation_and_readonly(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))
    service = CliSkillService(skill_config, workspace_id="ws-1")

    assert service.validate_scope(None) is True
    assert service.validate_scope(SkillScope.PROJECT) is True
    assert service.validate_scope(SkillScope.USER) is True
    assert service.validate_scope(SkillScope.PLUGIN) is True
    assert service.is_readonly_scope(SkillScope.PLUGIN) is True

    project_path = service.resolve_scope_path(SkillScope.PROJECT, "/demo/skill.md")
    user_path = service.resolve_scope_path(SkillScope.USER, "demo/skill.md")

    assert project_path == tmp_path / "workspace" / ".claude" / "skills" / "demo" / "skill.md"
    assert user_path == skill_config.user_root / "demo" / "skill.md"

    with pytest.raises(InvalidScopeException):
        service.resolve_scope_path("invalid", "demo.md")


def test_plugin_scope_validation_depends_on_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert service.get_plugin_skills() == []


def test_get_plugin_skills_returns_serialized_entries(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))
    service = CliSkillService(skill_config, workspace_id="ws-3")

    fake_skill = SimpleNamespace(
        plugin_name="plugin-a",
        marketplace_name="market",
        skill_name="Skill A",
        directory_path="/plugins/skill-a",
    )
    loader = SimpleNamespace(load_plugin_skills=lambda workspace_id: [fake_skill])

    monkeypatch.setattr("app.modules.claude_code.settings.service.SettingsService", lambda: SimpleNamespace())
    monkeypatch.setattr("app.modules.claude_code.plugins.loader.get_plugin_loader", lambda settings: loader)

    result = service.get_plugin_skills()

    assert result == [
        {
            "pluginId": "plugin-a@market",
            "pluginName": "plugin-a",
            "marketplaceName": "market",
            "skillName": "Skill A",
            "skillPath": "/plugins/skill-a",
        }
    ]


def test_get_plugin_skills_swallows_loader_errors(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))
    service = CliSkillService(skill_config, workspace_id="ws-4")

    monkeypatch.setattr("app.modules.claude_code.settings.service.SettingsService", lambda: SimpleNamespace())

    def raise_error(settings):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.modules.claude_code.plugins.loader.get_plugin_loader", raise_error)

    assert service.get_plugin_skills() == []


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
