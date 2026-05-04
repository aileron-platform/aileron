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


def test_non_gemini_extension_scope_is_rejected_before_loading_extensions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = SkillToolConfig(
        tool=SkillTool.CODEX,
        project_dot_dir=".codex",
        skill_dir_name="skills",
        user_root=tmp_path / "user-codex-skills",
        supports_plugin=False,
        api_prefix="codex",
    )
    monkeypatch.setattr("app.modules.cli_settings.skills.service.get_workspace_path", lambda: str(tmp_path / "workspace"))

    class FakeResolver:
        def enabled_skills(self, workspace_root_arg: Path):
            raise AssertionError("Non-Gemini skills must not read Gemini extensions")

    monkeypatch.setattr("app.modules.cli_settings.skills.service.GeminiExtensionResourceResolver", FakeResolver)
    service = CliSkillService(config, workspace_id="ws-codex")

    with pytest.raises(InvalidScopeException):
        service.get_tree("/", SkillScope.EXTENSION, include_hidden=False, max_depth=3)

    with pytest.raises(InvalidScopeException):
        service.read_file("dependency-manager/SKILL.md", SkillScope.EXTENSION)


def test_codex_config_uses_codex_skill_directories() -> None:
    config = get_skill_config(SkillTool.CODEX)

    assert config.project_dot_dir == ".codex"
    assert config.user_root == Path("/home/developer/.codex/skills")


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


def test_gemini_extension_tree_groups_skills_as_directories(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    class FakeResolver:
        def enabled_skills(self, workspace_root_arg: Path):
            assert workspace_root_arg == workspace_root
            package = SimpleNamespace(name="gemini-cli-security", version="0.5.0")
            return [
                (package, SimpleNamespace(name="dependency-manager", content="# Dependency Manager\n", path="/extensions/security/skills/dependency-manager/SKILL.md")),
                (package, SimpleNamespace(name="poc", content="# POC\n", path="/extensions/security/skills/poc/SKILL.md")),
                (package, SimpleNamespace(name="security-patcher", content="# Security Patcher\n", path="/extensions/security/skills/security-patcher/SKILL.md")),
            ]

    monkeypatch.setattr("app.modules.cli_settings.skills.service.resolve_workspace_root", lambda: workspace_root)
    monkeypatch.setattr("app.modules.cli_settings.skills.service.GeminiExtensionResourceResolver", FakeResolver)
    service = CliSkillService(skill_config, workspace_id="ws-gemini")

    tree = service.get_tree("/", SkillScope.EXTENSION, include_hidden=False, max_depth=3)

    assert [node["name"] for node in tree["nodes"]] == ["dependency-manager", "poc", "security-patcher"]
    assert all(node["type"] == "directory" for node in tree["nodes"])
    assert [node["children"][0]["path"] for node in tree["nodes"]] == [
        "dependency-manager/SKILL.md",
        "poc/SKILL.md",
        "security-patcher/SKILL.md",
    ]
    assert tree["nodes"][0]["children"][0]["metadata"]["extensionName"] == "gemini-cli-security"


def test_gemini_extension_read_file_uses_enabled_skill_content(skill_config: SkillToolConfig, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    class FakeResolver:
        def enabled_skills(self, workspace_root_arg: Path):
            assert workspace_root_arg == workspace_root
            package = SimpleNamespace(name="gemini-cli-security", version="0.5.0")
            return [
                (
                    package,
                    SimpleNamespace(
                        name="dependency-manager",
                        content="# Dependency Manager\nRead dependency manifests.\n",
                        path="/extensions/security/skills/dependency-manager/SKILL.md",
                    ),
                )
            ]

    monkeypatch.setattr("app.modules.cli_settings.skills.service.resolve_workspace_root", lambda: workspace_root)
    monkeypatch.setattr("app.modules.cli_settings.skills.service.GeminiExtensionResourceResolver", FakeResolver)
    service = CliSkillService(skill_config, workspace_id="ws-gemini")

    result = service.read_file("dependency-manager/SKILL.md", SkillScope.EXTENSION)

    assert result["path"] == "dependency-manager/SKILL.md"
    assert result["scope"] == SkillScope.EXTENSION
    assert result["content"] == "# Dependency Manager\nRead dependency manifests.\n"
    assert result["metadata"]["extensionName"] == "gemini-cli-security"
    assert result["metadata"]["extensionVersion"] == "0.5.0"
