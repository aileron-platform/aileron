from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.modules.cli_settings.skills.config import (
    SkillScope,
    SkillTool,
    SkillToolConfig,
    get_skill_config,
)
from app.modules.cli_settings.skills.catalog import CliSkillService
from app.modules.file_system.exceptions import InvalidScopeException
from app.modules.file_system.models import FileTreeResponse


@pytest.fixture
def skill_config(tmp_path: Path) -> SkillToolConfig:
    return SkillToolConfig(
        tool=SkillTool.CODEX,
        project_dot_dir=".codex",
        skill_dir_name="skills",
        user_root=tmp_path / "user-skills",
        supports_plugin=False,
        api_prefix="codex",
    )


def test_scope_resolution_validation_and_readonly(
    skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.catalog.get_workspace_path",
        lambda: str(tmp_path / "workspace"),
    )
    service = CliSkillService(skill_config, workspace_id="ws-1")

    assert service.validate_scope(None) is True
    assert service.validate_scope(SkillScope.PROJECT) is True
    assert service.validate_scope(SkillScope.USER) is True
    assert service.validate_scope(SkillScope.PLUGIN) is False
    assert service.is_readonly_scope(SkillScope.PLUGIN) is False

    project_path = service.resolve_scope_path(SkillScope.PROJECT, "/demo/skill.md")
    user_path = service.resolve_scope_path(SkillScope.USER, "demo/skill.md")

    assert (
        project_path
        == tmp_path / "workspace" / ".codex" / "skills" / "demo" / "skill.md"
    )
    assert user_path == skill_config.user_root / "demo" / "skill.md"

    with pytest.raises(InvalidScopeException):
        service.resolve_scope_path("invalid", "demo.md")


def test_plugin_scope_is_not_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = SkillToolConfig(
        tool=SkillTool.CODEX,
        project_dot_dir=".codex",
        skill_dir_name="skills",
        user_root=tmp_path / "user-skills",
        supports_plugin=False,
        api_prefix="codex",
    )
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.catalog.get_workspace_path",
        lambda: str(tmp_path / "workspace"),
    )
    service = CliSkillService(config, workspace_id="ws-2")

    assert service.validate_scope(SkillScope.PLUGIN) is False


def test_codex_config_uses_codex_skill_directories() -> None:
    config = get_skill_config(SkillTool.CODEX)

    assert config.project_dot_dir == ".codex"
    assert config.user_root == Path("/home/developer/.codex/skills")


def test_codex_project_tree_reads_from_dot_codex(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
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

    monkeypatch.setattr(
        "app.modules.cli_settings.skills.catalog.get_workspace_path",
        lambda: str(workspace_root),
    )
    service = CliSkillService(codex_config, workspace_id="ws-codex")

    tree = service.get_tree("/", SkillScope.PROJECT, include_hidden=False, max_depth=3)

    assert tree["path"] == "/"
    assert tree["nodes"][0]["name"] == "openspec-explore"
    assert tree["nodes"][0]["path"] == "/openspec-explore"
    assert tree["nodes"][0]["children"][0]["name"] == "SKILL.md"


def test_all_scope_aggregates_scopes_and_refreshes_cached_tree(
    skill_config: SkillToolConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    project_skill = workspace_root / ".codex" / "skills" / "project" / "SKILL.md"
    user_skill = skill_config.user_root / "user" / "SKILL.md"
    for path in (project_skill, user_skill):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Skill\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.catalog.get_workspace_path",
        lambda: str(workspace_root),
    )
    service = CliSkillService(skill_config, workspace_id="ws-all")

    first = service.get_tree("/", "all", include_hidden=False, max_depth=3)
    assert first["scope"] == "all"
    assert {node["scope"] for node in first["nodes"]} == {"project", "user"}

    external_skill = skill_config.user_root / "external" / "SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("# External\n", encoding="utf-8")
    warm = service.get_tree("/", "all", include_hidden=False, max_depth=3)
    assert {node["name"] for node in warm["nodes"]} == {"project", "user"}

    service.clear_tree_cache("user")
    refreshed = service.get_tree("/", "all", include_hidden=False, max_depth=3)
    assert {node["name"] for node in refreshed["nodes"]} == {
        "external",
        "project",
        "user",
    }


def test_all_scope_clear_invalidates_cached_child_scopes(
    skill_config: SkillToolConfig,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    project_skill = workspace_root / ".codex" / "skills" / "project" / "SKILL.md"
    user_skill = skill_config.user_root / "user" / "SKILL.md"
    for path in (project_skill, user_skill):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Skill\n", encoding="utf-8")
    monkeypatch.setattr(
        "app.modules.cli_settings.skills.catalog.get_workspace_path",
        lambda: str(workspace_root),
    )
    service = CliSkillService(skill_config, workspace_id="ws-clear-all")

    service.get_tree("/", "project", include_hidden=False, max_depth=3)
    service.get_tree("/", "user", include_hidden=False, max_depth=3)
    service.get_tree("/", "all", include_hidden=False, max_depth=3)

    external_skill = skill_config.user_root / "external" / "SKILL.md"
    external_skill.parent.mkdir(parents=True)
    external_skill.write_text("# External\n", encoding="utf-8")

    service.clear_tree_cache("all")

    refreshed = service.get_tree("/", "all", include_hidden=False, max_depth=3)
    assert {node["name"] for node in refreshed["nodes"]} == {
        "external",
        "project",
        "user",
    }


def test_codex_tree_clear_also_clears_codex_skills_collection(
    skill_config: SkillToolConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = MagicMock()
    monkeypatch.setattr(
        "app.modules.cli_settings.codex.settings.get_codex_agent_settings",
        lambda: settings,
    )

    CliSkillService(skill_config, workspace_id="ws-codex").clear_tree_cache("user")

    settings.execute.assert_called_once()
    (_intent,) = settings.execute.call_args.args
    assert _intent.value == "refresh_cache"
    assert settings.execute.call_args.kwargs == {
        "workspace_id": "ws-codex",
        "capability": "skills",
        "scope": "user",
    }


@pytest.fixture
def claude_skill_config(tmp_path: Path) -> SkillToolConfig:
    return SkillToolConfig(
        tool=SkillTool.CLAUDE,
        project_dot_dir=".claude",
        skill_dir_name="skills",
        user_root=tmp_path / "user-claude-skills",
        supports_plugin=True,
        api_prefix="claude-code",
    )


def test_claude_config_uses_claude_skill_directories() -> None:
    config = get_skill_config(SkillTool.CLAUDE)

    assert config.project_dot_dir == ".claude"
    assert config.user_root == Path("/home/developer/.claude/skills")
    assert config.supports_plugin is True


def test_claude_plugin_scope_is_supported_and_readonly(
    claude_skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")

    assert service.validate_scope(SkillScope.PLUGIN) is True
    assert service.is_readonly_scope(SkillScope.PLUGIN) is True


def test_parse_front_matter_with_metadata(claude_skill_config: SkillToolConfig) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    content = "---\nname: my-skill\ndescription: My skill description\n---\nBody\n"

    metadata, body = service._parse_front_matter(content)

    assert metadata == {"name": "my-skill", "description": "My skill description"}
    assert body == "Body\n"


def test_parse_front_matter_without_metadata(
    claude_skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")

    metadata, body = service._parse_front_matter("# Simple Content")

    assert metadata is None
    assert body == "# Simple Content"


def test_parse_front_matter_invalid_yaml_returns_original_content(
    claude_skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    content = "---\nfoo: [\n---\nBody"

    metadata, body = service._parse_front_matter(content)

    assert metadata is None
    assert body == content


def test_parse_front_matter_without_closing_marker(
    claude_skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    content = "---\nfoo: bar\nBody"

    metadata, body = service._parse_front_matter(content)

    assert metadata is None
    assert body == content


def test_get_plugin_skills_empty_for_non_plugin_tool(
    skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(skill_config, workspace_id="ws-codex")

    assert service.get_plugin_skills() == []


def test_get_plugin_skills_reads_loader_skill_directories(
    claude_skill_config: SkillToolConfig, tmp_path: Path
) -> None:
    skill_dir = tmp_path / "plugin-a" / "skills" / "good"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\ndescription: Good skill\n---\nBody", encoding="utf-8"
    )
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    mock_loader = MagicMock()
    mock_loader.load_plugin_skills.return_value = [
        SimpleNamespace(
            directory_path=str(skill_dir),
            plugin_name="plugin-a",
            marketplace_name="market-a",
            skill_name="good",
        )
    ]
    service._plugin_loader = lambda: mock_loader

    result = service.get_plugin_skills()

    assert len(result) == 1
    assert result[0].plugin_name == "plugin-a"
    assert result[0].marketplace_name == "market-a"
    assert result[0].skill_name == "good"
    assert result[0].plugin_id == "plugin-a@market-a"


def test_get_plugin_skills_returns_empty_on_loader_error(
    claude_skill_config: SkillToolConfig,
) -> None:
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    mock_loader = MagicMock()
    mock_loader.load_plugin_skills.side_effect = RuntimeError("boom")
    service._plugin_loader = lambda: mock_loader

    assert service.get_plugin_skills() == []


def test_plugin_scope_tree_uses_enabled_plugin_skills(
    claude_skill_config: SkillToolConfig, tmp_path: Path
) -> None:
    skill_dir = tmp_path / "plugin-a" / "skills" / "good"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: Good Skill\n---\nBody", encoding="utf-8"
    )
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    mock_loader = MagicMock()
    mock_loader.load_plugin_skills.return_value = [
        SimpleNamespace(
            directory_path=str(skill_dir),
            plugin_name="plugin-a",
            marketplace_name="market-a",
            skill_name="good",
        )
    ]
    service._plugin_loader = lambda: mock_loader

    result = service.get_tree(scope=SkillScope.PLUGIN)

    FileTreeResponse.model_validate(result)
    assert result["scope"] == "plugin"
    assert result["nodes"][0]["name"] == "plugin-a@market-a"
    assert result["nodes"][0]["scope"] == "plugin"
    assert result["nodes"][0]["updatedAt"]
    skill_node = result["nodes"][0]["children"][0]
    assert skill_node["name"] == "good"
    assert skill_node["scope"] == "plugin"
    skill_md_node = skill_node["children"][0]
    assert skill_md_node["path"] == "/plugin-a@market-a/good/SKILL.md"
    assert skill_md_node["scope"] == "plugin"
    assert skill_md_node["skillName"] == "Good Skill"


def test_claude_all_scope_normalizes_plugin_scope(
    claude_skill_config: SkillToolConfig, tmp_path: Path
) -> None:
    skill_dir = tmp_path / "plugin-a" / "skills" / "good"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Plugin Skill\n", encoding="utf-8")
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude-all")
    mock_loader = MagicMock()
    mock_loader.load_plugin_skills.return_value = [
        SimpleNamespace(
            directory_path=str(skill_dir),
            plugin_name="plugin-a",
            marketplace_name="market-a",
            skill_name="good",
        )
    ]
    service._plugin_loader = lambda: mock_loader

    result = service.get_tree("/", "all", include_hidden=False, max_depth=3)

    plugin_node = next(
        node for node in result["nodes"] if node["name"] == "plugin-a@market-a"
    )
    assert plugin_node["scope"] == "plugin"
    assert plugin_node["children"][0]["scope"] == "plugin"
    assert plugin_node["children"][0]["children"][0]["scope"] == "plugin"


def test_plugin_scope_read_file_resolves_loader_skill_directory(
    claude_skill_config: SkillToolConfig, tmp_path: Path
) -> None:
    skill_dir = tmp_path / "plugin-a" / "skills" / "good"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Body", encoding="utf-8")
    service = CliSkillService(claude_skill_config, workspace_id="ws-claude")
    mock_loader = MagicMock()
    mock_loader.load_plugin_skills.return_value = [
        SimpleNamespace(
            directory_path=str(skill_dir),
            plugin_name="plugin-a",
            marketplace_name="market-a",
            skill_name="good",
        )
    ]
    service._plugin_loader = lambda: mock_loader

    result = service.read_file("/plugin-a@market-a/good/SKILL.md", SkillScope.PLUGIN)

    assert result["content"] == "Body"
