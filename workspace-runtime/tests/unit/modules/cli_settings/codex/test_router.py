from __future__ import annotations

import errno
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.revision import compute_revision
from app.modules.cli_settings import raw_file as raw_file_module
from app.modules.cli_settings.codex import router as codex_router_module
from app.modules.cli_settings.codex import settings as codex_settings_module
from app.modules.cli_settings.codex.models import (
    CodexHookCommandAction,
    CodexHookEntry,
)
from app.modules.cli_settings.codex.settings import (
    CodexAgentSettings,
    CodexSettingsIntent,
    get_codex_agent_settings,
)
from app.modules.cli_settings.router import router


@dataclass(frozen=True)
class _CodexTestRoots:
    user_home: Path
    workspace_root: Path

    @property
    def codex_home(self) -> Path:
        return self.user_home / ".codex"

    def resolve(self, scope: str, resource: str) -> Path:
        names = {
            "agents_md": "AGENTS.md",
            "config": "config.toml",
            "hooks": "hooks.json",
            "managed_requirements": "requirements.toml",
            "prompts": "prompts",
            "rules": "rules",
            "skills": "skills",
            "subagents": "agents",
        }
        base = self.codex_home if scope == "user" else self.workspace_root / ".codex"
        if scope == "project" and resource == "agents_md":
            return self.workspace_root / "AGENTS.md"
        return base / names[resource]


def _plugin_cli_inventory(
    package_root,
    *,
    plugin_id="demo@local",
    version="1.2.3",
    enabled=True,
):
    name, marketplace_id = plugin_id.rsplit("@", 1)
    return {
        "available": [],
        "installed": [
            {
                "pluginId": plugin_id,
                "name": name,
                "marketplaceName": marketplace_id,
                "version": version,
                "installed": True,
                "enabled": enabled,
                "source": {
                    "source": "local",
                    "path": str(package_root),
                },
            }
        ],
    }


def _plugin_cache_root(
    tmp_path,
    *,
    name="demo",
    marketplace_name="local",
    version="1.2.3",
):
    return (
        tmp_path
        / "home"
        / "developer"
        / ".codex"
        / "plugins"
        / "cache"
        / marketplace_name
        / name
        / version
    )


def _client(tmp_path, monkeypatch=None, *, plugin_inventory=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    resolver = _CodexTestRoots(
        user_home=tmp_path / "home" / "developer",
        workspace_root=tmp_path / "workspace",
    )
    if monkeypatch is not None:
        monkeypatch.setenv("HOME", str(resolver.user_home))
        monkeypatch.setattr(
            "app.modules.cli_settings.agents_md.documents.get_workspace_path",
            lambda: str(resolver.workspace_root),
        )
    inventory = plugin_inventory or {"available": [], "installed": []}
    service = CodexAgentSettings(
        user_home=resolver.user_home,
        workspace_root=resolver.workspace_root,
        plugin_inventory=lambda: inventory["installed"],
    )
    app.dependency_overrides[get_codex_agent_settings] = lambda: service
    return TestClient(app), resolver


def test_codex_agent_settings_exposes_one_intent_interface() -> None:
    public_methods = {
        name
        for name, member in CodexAgentSettings.__dict__.items()
        if callable(member) and not name.startswith("_")
    }

    assert public_methods == {"execute"}


def test_codex_settings_api_group_lists_capabilities(tmp_path) -> None:
    client, _resolver = _client(tmp_path)

    response = client.get("/api/v1/workspaces/ws-1/codex")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspaceId"] == "ws-1"
    assert payload["editableLayers"] == ["user", "project"]
    capability_ids = {item["id"] for item in payload["capabilities"]}
    assert {
        "overview",
        "agents-md",
        "config",
        "profiles",
        "permissions-profiles",
        "features",
        "apps",
        "rules",
        "hooks",
        "mcp-servers",
        "plugins",
        "skills",
        "subagents",
        "prompts",
        "managed-requirements",
    }.issubset(capability_ids)
    implemented = {item["id"]: item["implemented"] for item in payload["capabilities"]}
    assert implemented["overview"] is True
    assert implemented["agents-md"] is True
    assert implemented["managed-requirements"] is True


def test_codex_skills_all_scope_is_one_aggregate_response(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    for scope, name in (("project", "project-skill"), ("user", "user-skill")):
        skill = resolver.resolve(scope, "skills") / name / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("# Skill\n", encoding="utf-8")

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/files",
        params={"scope": "all"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope"] == "all"
    assert {(item["name"], item["scope"]) for item in payload["files"]} == {
        ("SKILL.md", "project"),
        ("SKILL.md", "user"),
    }


def test_codex_overview_reads_trust_plugins_requirements_and_memories(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.codex_home / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
model = "gpt-5.6-luna"
profile = "work"

[projects."{workspace_path}"]
trust_level = "trusted"

[plugins."github@openai-curated"]
enabled = true

[plugins."demo@local"]
enabled = false

[memories]
use = true
generate = false

[profiles.work]
model = "gpt-5.6-terra"
""".strip().format(
            workspace_path=str(resolver.workspace_root)
        ),
        encoding="utf-8",
    )
    (resolver.resolve("project", "managed_requirements")).parent.mkdir(
        parents=True, exist_ok=True
    )
    resolver.resolve("project", "managed_requirements").write_text(
        "version = 1\n", encoding="utf-8"
    )

    response = client.get("/api/v1/workspaces/ws-1/codex/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["codexHome"] == "~/.codex"
    assert payload["trust"]["workspacePath"] == "."
    assert payload["trust"]["sourcePath"] == "~/.codex/config.toml"
    assert payload["activeModel"] == "gpt-5.6-terra"
    assert payload["activeProfile"] == "work"
    assert payload["trust"]["trusted"] is True
    assert payload["plugins"] == {"configured": 2, "enabled": 1, "disabled": 1}
    assert payload["managedRequirements"]["present"] is True
    assert payload["memories"] == {"use": True, "generate": False}


def test_codex_public_path_fields_use_logical_locators(tmp_path) -> None:
    resolver = _CodexTestRoots(
        user_home=tmp_path / "home" / "developer",
        workspace_root=tmp_path / "workspace",
    )
    service = CodexAgentSettings(
        user_home=resolver.user_home,
        workspace_root=resolver.workspace_root,
        plugin_inventory=lambda: [],
    )

    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text(
        """
[agents]
max_threads = 4

[hooks.Stop]
type = "command"
command = "echo inline"
""".strip(),
        encoding="utf-8",
    )
    project_config = resolver.resolve("project", "config")
    project_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.write_text('model = "gpt-5.6-terra"\n', encoding="utf-8")

    rule = resolver.resolve("user", "rules") / "safe.rules"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text("allow\n", encoding="utf-8")
    skill = resolver.resolve("user", "skills") / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")
    hook = resolver.resolve("user", "hooks")
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        '{"PreToolUse":[{"hooks":[{"type":"command","command":"echo user"}]}]}',
        encoding="utf-8",
    )
    subagent = resolver.resolve("user", "subagents") / "worker.toml"
    subagent.parent.mkdir(parents=True, exist_ok=True)
    subagent.write_text(
        """
name = "worker"
description = "Worker"
developer_instructions = "Work."
""".strip(),
        encoding="utf-8",
    )
    requirements = resolver.resolve("user", "managed_requirements")
    requirements.write_text(
        """
[hooks.SessionStart]
type = "command"
command = "echo requirements"

[agents.requirements_worker]
description = "Requirements worker"
developer_instructions = "Follow requirements."
""".strip(),
        encoding="utf-8",
    )

    overview = service.execute(CodexSettingsIntent.GET_OVERVIEW, "ws-1")
    user_config_document = service.execute(
        CodexSettingsIntent.GET_CONFIG_DOCUMENT, "ws-1", "user"
    )
    project_config_document = service.execute(
        CodexSettingsIntent.GET_CONFIG_DOCUMENT, "ws-1", "project"
    )
    config_section = service.execute(
        CodexSettingsIntent.GET_CONFIG_SECTION, "ws-1", "user", "features"
    )
    rules = service.execute(CodexSettingsIntent.LIST_RULES, "ws-1", "user")
    rule_document = service.execute(
        CodexSettingsIntent.GET_RULES_FILE, "ws-1", "user", "safe.rules"
    )
    hooks = service.execute(CodexSettingsIntent.GET_HOOKS_DOCUMENT, "ws-1", "user")
    skills = service.execute(CodexSettingsIntent.LIST_FILES, "ws-1", "user", "skills")
    skill_document = service.execute(
        CodexSettingsIntent.GET_FILE,
        "ws-1",
        "user",
        "skills",
        "review/SKILL.md",
    )
    subagents = service.execute(CodexSettingsIntent.LIST_SUBAGENTS, "ws-1")
    updated_config = service.execute(
        CodexSettingsIntent.UPDATE_CONFIG_DOCUMENT,
        "ws-1",
        "user",
        user_config_document.content,
        revision=user_config_document.revision,
    )
    deleted_rule = service.execute(
        CodexSettingsIntent.DELETE_RULES_FILE, "ws-1", "user", "safe.rules"
    )
    deleted_skill = service.execute(
        CodexSettingsIntent.DELETE_FILE,
        "ws-1",
        "user",
        "skills",
        "review/SKILL.md",
    )

    assert overview.codexHome == "~/.codex"
    assert overview.trust.workspacePath == "."
    assert overview.trust.sourcePath == "~/.codex/config.toml"
    assert user_config_document.path == "~/.codex/config.toml"
    assert updated_config.path == "~/.codex/config.toml"
    assert project_config_document.path == "./.codex/config.toml"
    assert config_section.path == "~/.codex/config.toml"
    assert rules.directory == "~/.codex/rules"
    assert rule_document.path == "~/.codex/rules/safe.rules"
    assert hooks.path == "~/.codex/hooks.json"
    assert {entry.sourcePath for entry in hooks.entries if entry.sourcePath} <= {
        "~/.codex/config.toml",
        "~/.codex/hooks.json",
        "~/.codex/requirements.toml",
    }
    assert skills.directory == "~/.codex/skills"
    assert skill_document.path == "~/.codex/skills/review/SKILL.md"
    assert deleted_rule["path"] == "~/.codex/rules/safe.rules"
    assert deleted_skill["path"] == "~/.codex/skills/review/SKILL.md"
    editable_subagent = next(
        item
        for item in subagents.items
        if item.source == "user" and item.name == "worker"
    )
    assert editable_subagent.path == "~/.codex/agents/worker.toml"
    assert editable_subagent.sourcePath == "~/.codex/agents/worker.toml"
    assert subagents.registry[0].path == "~/.codex/config.toml"

    public_payload = json.dumps(
        {
            "overview": overview.model_dump(by_alias=True),
            "configs": [
                user_config_document.model_dump(by_alias=True),
                project_config_document.model_dump(by_alias=True),
                config_section.model_dump(by_alias=True),
            ],
            "rules": rules.model_dump(by_alias=True),
            "rule": rule_document.model_dump(by_alias=True),
            "hooks": hooks.model_dump(by_alias=True),
            "skills": skills.model_dump(by_alias=True),
            "skill": skill_document.model_dump(by_alias=True),
            "subagents": subagents.model_dump(by_alias=True),
            "updatedConfig": updated_config.model_dump(by_alias=True),
            "deletedRule": deleted_rule,
            "deletedSkill": deleted_skill,
        },
        sort_keys=True,
    )
    assert str(tmp_path) not in public_payload

    user_config.write_text("[invalid", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        service.execute(CodexSettingsIntent.GET_OVERVIEW, "ws-1")
    assert exc.value.detail == {"error": "INVALID_TOML"}
    assert str(tmp_path) not in json.dumps(exc.value.detail)


def test_codex_trust_update_writes_user_config(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.patch(
        "/api/v1/workspaces/ws-1/codex/overview/trust", json={"trusted": True}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trust"]["trusted"] is True
    assert f'[projects."{resolver.workspace_root}"]' in resolver.resolve(
        "user", "config"
    ).read_text(encoding="utf-8")


def test_codex_agents_md_uses_shared_query_scope_route(tmp_path, monkeypatch) -> None:
    client, resolver = _client(tmp_path, monkeypatch)
    workspace = resolver.workspace_root
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("0123456789", encoding="utf-8")

    removed_path_response = client.get(
        "/api/v1/workspaces/ws-1/codex/agents-md/project"
    )
    assert removed_path_response.status_code == 404

    response = client.get("/api/v1/workspaces/ws-1/codex/agents-md?scope=project")
    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "0123456789"
    assert payload["revision"] == compute_revision("0123456789")


def test_codex_agents_md_writes_user_and_project_documents(
    tmp_path, monkeypatch
) -> None:
    client, resolver = _client(tmp_path, monkeypatch)

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/agents-md",
        json={"scope": "user", "content": "User instructions"},
    )
    assert response.status_code == 422

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/agents-md",
        json={
            "scope": "user",
            "content": "User instructions",
            "revision": compute_revision(""),
        },
    )

    assert response.status_code == 200
    assert response.json()["revision"] == compute_revision("User instructions")
    assert (
        resolver.resolve("user", "agents_md").read_text(encoding="utf-8")
        == "User instructions"
    )

    stale = client.put(
        "/api/v1/workspaces/ws-1/codex/agents-md",
        json={
            "scope": "user",
            "content": "Stale write",
            "revision": compute_revision(""),
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["errorCode"] == "REVISION_CONFLICT"
    assert (
        resolver.resolve("user", "agents_md").read_text(encoding="utf-8")
        == "User instructions"
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/agents-md",
        json={
            "scope": "user",
            "content": "Updated instructions",
            "revision": compute_revision("User instructions"),
        },
    )
    assert response.status_code == 200
    assert response.json()["revision"] == compute_revision("Updated instructions")
    assert (
        resolver.resolve("user", "agents_md").read_text(encoding="utf-8")
        == "Updated instructions"
    )


def test_codex_managed_requirements_are_read_only_sources(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    resolver.resolve("user", "managed_requirements").parent.mkdir(
        parents=True, exist_ok=True
    )
    resolver.resolve("user", "managed_requirements").write_text(
        "user = true\n", encoding="utf-8"
    )
    resolver.resolve("project", "managed_requirements").parent.mkdir(
        parents=True, exist_ok=True
    )
    resolver.resolve("project", "managed_requirements").write_text(
        "project = true\n", encoding="utf-8"
    )

    response = client.get("/api/v1/workspaces/ws-1/codex/managed-requirements")

    assert response.status_code == 200
    payload = response.json()
    assert [source["layer"] for source in payload["sources"]] == ["user", "project"]
    assert all("content" in source for source in payload["sources"])


def test_codex_config_raw_update_validates_toml(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    old_query = client.get("/api/v1/workspaces/ws-1/codex/config?layer=user")
    assert old_query.status_code == 422

    invalid_scope = client.get("/api/v1/workspaces/ws-1/codex/config?scope=local")
    assert invalid_scope.status_code == 422

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config?scope=user",
        json={"content": 'model = "gpt-5.6-terra"\n'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == 'model = "gpt-5.6-terra"\n'
    assert payload["scope"] == "user"
    assert payload["exists"] is True
    assert (
        resolver.resolve("user", "config").read_text(encoding="utf-8")
        == 'model = "gpt-5.6-terra"\n'
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config?scope=user",
        json={"content": "model = ["},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_TOML"


def test_codex_config_revision_conflict(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.resolve("user", "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text('model = "gpt-5.6-luna"\n', encoding="utf-8")

    got = client.get("/api/v1/workspaces/ws-1/codex/config?scope=user")

    assert got.status_code == 200
    assert got.json()["revision"] == compute_revision('model = "gpt-5.6-luna"\n')

    bad = client.put(
        "/api/v1/workspaces/ws-1/codex/config?scope=user",
        json={"content": 'model = "gpt-5.6-terra"\n', "revision": "stale"},
    )

    assert bad.status_code == 409
    assert bad.json()["detail"]["errorCode"] == "REVISION_CONFLICT"
    assert config_path.read_text(encoding="utf-8") == 'model = "gpt-5.6-luna"\n'


def test_codex_config_sections_preserve_unknown_keys(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.resolve("project", "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
unknown = "keep"
model = "old"

[profiles.default]
model = "gpt-5.6-luna"
""".strip(),
        encoding="utf-8",
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config/structured?scope=project",
        json={"data": {"model": "gpt-5.6-terra", "unknown_update": "ignored"}},
    )

    assert response.status_code == 200
    content = config_path.read_text(encoding="utf-8")
    assert 'unknown = "keep"' in content
    assert 'model = "gpt-5.6-terra"' in content
    assert "unknown_update" not in content

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config/profiles?scope=project",
        json={
            "data": {
                "default": {"model": "gpt-5.6-sol"},
                "explorer": {"model": "gpt-5.6-terra"},
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["default"]["model"] == "gpt-5.6-sol"
    assert payload["data"]["explorer"]["model"] == "gpt-5.6-terra"


def test_codex_subagents_list_sources_and_registry(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    user_agents = resolver.resolve("user", "subagents")
    project_agents = resolver.resolve("project", "subagents")
    user_agents.mkdir(parents=True, exist_ok=True)
    project_agents.mkdir(parents=True, exist_ok=True)
    (user_agents / "worker.toml").write_text(
        """
name = "worker"
description = "User worker"
developer_instructions = "Use user worker instructions."
nickname_candidates = ["Atlas", "Delta"]
model = "gpt-5.4"
""".strip(),
        encoding="utf-8",
    )
    (project_agents / "worker.toml").write_text(
        """
name = "worker"
description = "Project worker"
developer_instructions = "Use project worker instructions."
sandbox_mode = "workspace-write"
""".strip(),
        encoding="utf-8",
    )
    resolver.resolve("user", "config").parent.mkdir(parents=True, exist_ok=True)
    resolver.resolve("user", "config").write_text(
        "[agents]\nmax_threads = 4\nmax_depth = 1\n", encoding="utf-8"
    )
    requirements = resolver.resolve("project", "managed_requirements")
    requirements.parent.mkdir(parents=True, exist_ok=True)
    requirements.write_text(
        """
[agents.requirements_worker]
description = "Project requirements worker"
developer_instructions = "Use requirements instructions."
""".strip(),
        encoding="utf-8",
    )

    response = client.get("/api/v1/workspaces/ws-1/codex/subagents")

    assert response.status_code == 200
    payload = response.json()
    assert all("layer" not in item for item in payload["items"])
    assert all(item["source"] != "managed" for item in payload["items"])
    worker_items = [item for item in payload["items"] if item["name"] == "worker"]
    assert {item["source"] for item in worker_items} == {"project", "user", "built_in"}
    project_worker = next(item for item in worker_items if item["source"] == "project")
    user_worker = next(item for item in worker_items if item["source"] == "user")
    assert project_worker["effective"] is True
    assert project_worker["scope"] == "project"
    assert user_worker["overridden"] is True
    assert user_worker["scope"] == "user"
    assert (
        next(item for item in worker_items if item["source"] == "built_in")["readOnly"]
        is True
    )
    requirements_item = next(
        item for item in payload["items"] if item["name"] == "requirements_worker"
    )
    assert requirements_item["source"] == "project"
    assert requirements_item["readOnly"] is True
    assert requirements_item["scope"] == "project"
    assert all(item["content"] == "" for item in payload["items"])
    assert payload["registry"][0]["settings"]["max_threads"] == 4

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/subagents/detail?source=project&path=worker.toml"
    )
    assert response.status_code == 200
    detail = response.json()
    assert "layer" not in detail
    assert detail["scope"] == "project"
    assert detail["content"].startswith('name = "worker"')
    assert (
        detail["definition"]["developer_instructions"]
        == "Use project worker instructions."
    )


def test_codex_subagents_save_raw_toml_preserves_advanced_fields_and_renames(
    tmp_path,
) -> None:
    client, resolver = _client(tmp_path)

    response = client.post(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "project",
            "path": "reviewer.toml",
            "content": """
name = "Code Reviewer"
description = "Reviews code"
developer_instructions = "Review code like an owner."
model = "gpt-5.4"
custom_key = "keep"

[mcp_servers.docs]
url = "https://example.test/mcp"
""".strip(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["relativePath"] == "reviewer.toml"
    assert payload["scope"] == "project"
    assert "layer" not in payload
    content = (resolver.resolve("project", "subagents") / "reviewer.toml").read_text(
        encoding="utf-8"
    )
    assert 'custom_key = "keep"' in content
    assert "[mcp_servers.docs]" in content

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "project",
            "path": "security-reviewer.toml",
            "previousPath": "reviewer.toml",
            "content": """
name = "Security Reviewer"
description = "Reviews security"
developer_instructions = "Focus on security bugs."
model_reasoning_effort = "high"
nickname_candidates = ["Echo"]
""".strip(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["relativePath"] == "security-reviewer.toml"
    assert payload["scope"] == "project"
    assert "layer" not in payload
    assert not (resolver.resolve("project", "subagents") / "reviewer.toml").exists()
    assert (
        resolver.resolve("project", "subagents") / "security-reviewer.toml"
    ).is_file()


def test_codex_subagents_validation_conflict_and_delete(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    agents_dir = resolver.resolve("user", "subagents")
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "existing.toml").write_text(
        'name = "existing"\ndescription = "Existing"\ndeveloper_instructions = "Keep."\n',
        encoding="utf-8",
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "user",
            "path": "missing.toml",
            "content": 'name = "missing"\ndescription = "Missing"\n',
        },
    )
    assert response.status_code == 400

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "user",
            "path": "existing.toml",
            "content": 'name = "existing"\ndescription = "Duplicate"\ndeveloper_instructions = "Duplicate."\n',
        },
    )
    assert response.status_code == 409

    invalid = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "user",
            "path": "../escape.toml",
            "content": 'name = "escape"\ndescription = "Escape"\ndeveloper_instructions = "No."\n',
        },
    )
    assert invalid.status_code == 400
    assert not (agents_dir.parent / "escape.toml").exists()

    invalid_toml = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={"scope": "user", "path": "broken.toml", "content": "name = ["},
    )
    assert invalid_toml.status_code == 400
    assert not (agents_dir / "broken.toml").exists()

    old_layer = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "layer": "user",
            "path": "legacy.toml",
            "content": 'name = "legacy"\ndescription = "Legacy"\ndeveloper_instructions = "No compatibility."\n',
        },
    )
    assert old_layer.status_code == 422
    assert not (agents_dir / "legacy.toml").exists()

    old_delete_query = client.delete(
        "/api/v1/workspaces/ws-1/codex/subagents?layer=user&path=existing.toml"
    )
    assert old_delete_query.status_code == 422
    assert (agents_dir / "existing.toml").exists()

    response = client.delete(
        "/api/v1/workspaces/ws-1/codex/subagents?scope=user&path=existing.toml"
    )
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["scope"] == "user"
    assert "layer" not in response.json()
    assert not (agents_dir / "existing.toml").exists()


def test_codex_rules_crud_stays_inside_rules_directory(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/rules/file?scope=project&path=default.rules",
        json={
            "content": 'prefix_rule(pattern = ["git", "status"], decision = "allow", justification = "Read-only")\n'
        },
    )

    assert response.status_code == 200
    assert response.json()["exists"] is True
    assert (resolver.resolve("project", "rules") / "default.rules").is_file()

    response = client.get("/api/v1/workspaces/ws-1/codex/rules?scope=project")
    assert response.status_code == 200
    assert response.json()["files"][0]["name"] == "default.rules"

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/rules/file?scope=project&path=../escape.rules"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == {
        "errorCode": "INVALID_RULES_PATH",
        "message": "../escape.rules",
    }

    response = client.delete(
        "/api/v1/workspaces/ws-1/codex/rules/file?scope=project&path=default.rules"
    )
    assert response.status_code == 200
    assert not (resolver.resolve("project", "rules") / "default.rules").exists()


def test_codex_rules_file_revision_conflict(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    rules_path = resolver.resolve("user", "rules") / "default.rules"
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(
        'prefix_rule(pattern = ["git"], decision = "allow")\n', encoding="utf-8"
    )

    got = client.get(
        "/api/v1/workspaces/ws-1/codex/rules/file?scope=user&path=default.rules"
    )

    assert got.status_code == 200
    assert got.json()["revision"] == compute_revision(
        'prefix_rule(pattern = ["git"], decision = "allow")\n'
    )

    bad = client.put(
        "/api/v1/workspaces/ws-1/codex/rules/file?scope=user&path=default.rules",
        json={
            "content": 'prefix_rule(pattern = ["git"], decision = "deny")\n',
            "revision": "stale",
        },
    )

    assert bad.status_code == 409
    assert bad.json()["detail"]["errorCode"] == "REVISION_CONFLICT"
    assert (
        rules_path.read_text(encoding="utf-8")
        == 'prefix_rule(pattern = ["git"], decision = "allow")\n'
    )


def test_codex_rules_validation_normalizes_execpolicy_result(
    tmp_path, monkeypatch
) -> None:
    client, resolver = _client(tmp_path)
    rules_path = resolver.resolve("user", "rules") / "default.rules"
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(
        'prefix_rule(pattern = ["git"], decision = "allow")\n', encoding="utf-8"
    )

    def fake_run(command, **kwargs):
        assert command == [
            "codex",
            "execpolicy",
            "check",
            "--rules",
            str(rules_path),
            "git",
            "status",
        ]
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            command, 0, stdout='{"decision":"allow"}\n', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workspaces/ws-1/codex/rules/validate",
        json={"scope": "user", "path": "default.rules", "command": ["git", "status"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["exitCode"] == 0
    assert "allow" in payload["stdout"]


def test_codex_hooks_documents_read_write_and_expose_all_sources(
    tmp_path,
    monkeypatch,
) -> None:
    package_root = _plugin_cache_root(tmp_path, name="hook-demo")
    client, resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(
            package_root,
            plugin_id="hook-demo@local",
        ),
    )
    project_config = resolver.resolve("project", "config")
    project_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.write_text(
        """
[features]
hooks = true

[[hooks.PreToolUse]]
type = "command"
command = "echo inline"
statusMessage = "Checking inline"
""".strip(),
        encoding="utf-8",
    )
    managed = resolver.resolve("project", "managed_requirements")
    managed.parent.mkdir(parents=True, exist_ok=True)
    managed.write_text(
        """
[hooks.Stop]
type = "command"
command = "echo managed"
statusMessage = "Checking managed"
""".strip(),
        encoding="utf-8",
    )
    plugin_hooks = package_root / "hooks" / "hooks.json"
    plugin_hooks.parent.mkdir(parents=True, exist_ok=True)
    plugin_hooks.write_text(
        '{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"echo plugin","statusMessage":"Loading plugin"}]}]}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.modules.cli_settings.codex.app_server_hooks.CodexHooksListClient.list_hooks",
        lambda _self, _cwd: (
            SimpleNamespace(
                plugin_id="hook-demo@local",
                source_path=plugin_hooks.resolve(strict=False),
                key="hook-demo",
                current_hash="sha256:hook-demo",
                enabled=True,
                trust_status="untrusted",
            ),
        ),
    )
    manifest = plugin_hooks.parents[1] / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"hook-demo","version":"1.2.3","hooks":"./hooks/hooks.json"}',
        encoding="utf-8",
    )
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text(
        '[plugins."hook-demo@local"]\nenabled = true\n', encoding="utf-8"
    )

    old_query_response = client.get("/api/v1/workspaces/ws-1/codex/hooks?scope=project")
    assert old_query_response.status_code in {404, 405, 422}

    response = client.get("/api/v1/workspaces/ws-1/codex/hooks/project")
    assert response.status_code == 200
    assert response.json()["revision"] == compute_revision("")

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={
            "content": '{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo json","timeout":600,"statusMessage":"Checking JSON","unknownField":true}]}]}'
        },
    )
    assert response.status_code == 422

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={
            "content": '{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo json","timeout":600,"statusMessage":"Checking JSON","unknownField":true}]}]}',
            "revision": compute_revision(""),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["revision"] == compute_revision(
        '{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo json","timeout":600,"statusMessage":"Checking JSON","unknownField":true}]}]}'
    )
    assert payload["featureEnabled"] is True
    assert payload["inlineHooks"] == []
    assert {entry["source"] for entry in payload["entries"]} == {"hooks_json"}
    json_entry = next(
        entry for entry in payload["entries"] if entry["source"] == "hooks_json"
    )
    assert json_entry["readOnly"] is False
    assert json_entry["layer"] == "project"
    assert json_entry["actions"][0]["statusMessage"] == "Checking JSON"
    assert json_entry["actions"][0]["raw"]["unknownField"] is True
    session_metadata = next(
        item for item in payload["eventMetadata"] if item["event"] == "SessionStart"
    )
    assert session_metadata["matcherTarget"] == "source"
    assert (
        resolver.resolve("project", "hooks")
        .read_text(encoding="utf-8")
        .startswith('{"PreToolUse"')
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={"content": "{}", "revision": compute_revision("")},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["errorCode"] == "REVISION_CONFLICT"

    response = client.get("/api/v1/workspaces/ws-1/codex/hooks-scopes")
    assert response.status_code == 200
    documents = response.json()["scopes"]
    assert {(document["scope"], document.get("source")) for document in documents} == {
        ("project", "hooks_json"),
        ("project", "inline_config"),
        ("user", "hooks_json"),
        ("plugin", "plugin"),
    }
    inline_document = next(
        document
        for document in documents
        if document["scope"] == "project" and document["source"] == "inline_config"
    )
    assert inline_document["entries"][0]["event"] == "PreToolUse"
    assert inline_document["entries"][0]["readOnly"] is False
    assert (
        inline_document["entries"][0]["actions"][0]["statusMessage"]
        == "Checking inline"
    )
    plugin_document = next(
        document for document in documents if document["source"] == "plugin"
    )
    assert plugin_document["entries"][0]["pluginId"] == "hook-demo@local"
    assert plugin_document["entries"][0]["readOnly"] is True
    assert all(
        entry["source"] != "managed"
        for document in documents
        for entry in document["entries"]
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={"content": '{"PreToolUse": [', "revision": payload["revision"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_JSON"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={"content": '["PreToolUse"]', "revision": payload["revision"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_HOOKS_DOCUMENT"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={
            "content": '{"PreToolUse":[{"hooks":[{"type":"command"}]}]}',
            "revision": payload["revision"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "MISSING_HOOK_COMMAND"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={
            "content": '{"PreToolUse":[{"hooks":[{"type":"command","command":"echo bad","statusMessage":123}]}]}',
            "revision": payload["revision"],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "INVALID_HOOK_STATUS_MESSAGE"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/project",
        json={
            "content": '{"PreToolUse":[{"hooks":[{"type":"command","command":"echo bad","additionalContextLimit":-1}]}]}',
            "revision": payload["revision"],
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]["errorCode"]
        == "INVALID_HOOK_ADDITIONAL_CONTEXT_LIMIT"
    )


def test_codex_hooks_structured_entry_upsert_and_delete_touch_only_hooks_json(
    tmp_path,
) -> None:
    client, resolver = _client(tmp_path)
    hooks_path = resolver.resolve("user", "hooks")
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    hooks_path.write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": "echo old"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    config_path = resolver.resolve("user", "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
[hooks.Stop]
type = "command"
command = "echo inline"
""".strip(),
        encoding="utf-8",
    )

    entry = CodexHookEntry(
        id="",
        event="PostToolUse",
        index=0,
        matcher="Bash",
        actions=[CodexHookCommandAction(type="command", command="echo hi")],
        source="hooks_json",
        layer="user",
        readOnly=False,
    )
    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/user/entry",
        json={"entry": entry.model_dump(), "previous": None},
    )
    assert response.status_code == 422

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/user/entry",
        json={
            "entry": entry.model_dump(),
            "previous": None,
            "revision": compute_revision(hooks_path.read_text(encoding="utf-8")),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert any(
        item["source"] == "hooks_json"
        and item["event"] == "PostToolUse"
        and item["matcher"] == "Bash"
        for item in payload["entries"]
    )
    scopes = client.get("/api/v1/workspaces/ws-1/codex/hooks-scopes").json()["scopes"]
    assert any(
        item["source"] == "inline_config" and item["event"] == "Stop"
        for document in scopes
        for item in document["entries"]
    )
    written = json.loads(hooks_path.read_text(encoding="utf-8"))
    assert set(written["hooks"]) == {"PreToolUse", "PostToolUse"}

    created = next(
        item
        for item in payload["entries"]
        if item["source"] == "hooks_json" and item["event"] == "PostToolUse"
    )
    response = client.request(
        "DELETE",
        "/api/v1/workspaces/ws-1/codex/hooks/user/entry",
        json={"entry": created, "revision": payload["revision"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(
        item["id"] != created["id"]
        for item in payload["entries"]
        if item["source"] == "hooks_json"
    )
    scopes = client.get("/api/v1/workspaces/ws-1/codex/hooks-scopes").json()["scopes"]
    assert any(
        item["source"] == "inline_config" and item["event"] == "Stop"
        for document in scopes
        for item in document["entries"]
    )
    written = json.loads(hooks_path.read_text(encoding="utf-8"))
    assert set(written["hooks"]) == {"PreToolUse"}


def test_codex_hooks_structured_entry_rejects_plugin_sources(tmp_path) -> None:
    client, _resolver = _client(tmp_path)
    entry = CodexHookEntry(
        id="plugin:demo:Stop:0",
        event="Stop",
        index=0,
        actions=[CodexHookCommandAction(type="command", command="echo plugin")],
        source="plugin",
        layer=None,
        readOnly=True,
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/user/entry",
        json={
            "entry": entry.model_dump(),
            "previous": None,
            "revision": compute_revision(""),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["errorCode"] == "READ_ONLY_HOOK_ENTRY"


def test_codex_hooks_structured_entry_updates_inline_config_without_dropping_other_keys(
    tmp_path,
) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.resolve("user", "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
[hooks]
managed_dir = "managed"

[hooks.Stop]
type = "command"
command = "echo old"
""".strip(),
        encoding="utf-8",
    )
    entry = CodexHookEntry(
        id="inline:user:0:Stop:0",
        event="Stop",
        index=0,
        actions=[CodexHookCommandAction(type="command", command="echo new")],
        source="inline_config",
        layer="user",
        readOnly=False,
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks/user/entry",
        json={
            "entry": entry.model_dump(),
            "previous": None,
            "revision": compute_revision(config_path.read_text(encoding="utf-8")),
        },
    )

    assert response.status_code == 200
    written = resolver.resolve("user", "config").read_text(encoding="utf-8")
    assert 'managed_dir = "managed"' in written
    assert 'command = "echo new"' in written
    assert "codex_hooks" not in written


def test_codex_hooks_enable_writes_selected_layer(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.post("/api/v1/workspaces/ws-1/codex/hooks/project/enable")

    assert response.status_code == 200
    assert response.json()["featureEnabled"] is True
    assert "hooks = true" in resolver.resolve("project", "config").read_text(
        encoding="utf-8"
    )


def test_codex_plugins_use_provider_installed_root_and_toggle_config(tmp_path) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"demo","version":"1.2.3","interface":{"displayName":"Demo Plugin"}}',
        encoding="utf-8",
    )

    response = client.patch(
        "/api/v1/workspaces/ws-1/codex/plugins/demo@local",
        json={"scope": "user", "enabled": True},
    )

    assert response.status_code == 200
    assert response.json()["newThreadRequired"] is True
    assert response.json()["scope"] == "user"
    assert "layer" not in response.json()
    assert '[plugins."demo@local"]' in resolver.resolve("user", "config").read_text(
        encoding="utf-8"
    )

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")
    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["id"] == "demo@local"
    assert plugin["listed"] is True
    assert plugin["installed"] is True
    assert plugin["effectiveEnabled"] is True
    assert "enabled" not in plugin
    assert "layers" not in plugin
    assert "path" not in plugin
    assert "sourcePath" not in plugin
    assert plugin["scopes"] == [
        {"scope": "user", "configured": True, "enabled": True},
        {"scope": "project", "configured": False, "enabled": None},
    ]
    assert plugin["resourceCounts"]["skills"] == 0
    assert "bundled" not in plugin

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins/demo@local")
    assert response.status_code == 200
    detail = response.json()["plugin"]
    assert detail["effectiveEnabled"] is True
    assert detail["scopes"] == plugin["scopes"]
    assert "layers" not in detail
    assert detail["defaultPrompts"] == []
    assert "defaultPrompt" not in detail


def test_codex_plugin_detail_uses_unified_error_envelope(tmp_path) -> None:
    client, _resolver = _client(tmp_path)

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins/missing@local")

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "errorCode": "PLUGIN_NOT_FOUND",
        "message": "missing@local",
    }


def test_codex_plugin_toggle_revision_conflict(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."demo@local"]\nenabled = true\n', encoding="utf-8")

    response = client.patch(
        "/api/v1/workspaces/ws-1/codex/plugins/demo@local",
        json={"scope": "user", "enabled": False, "revision": "stale"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["errorCode"] == "REVISION_CONFLICT"
    assert (
        user_config.read_text(encoding="utf-8")
        == '[plugins."demo@local"]\nenabled = true\n'
    )

    old_layer = client.patch(
        "/api/v1/workspaces/ws-1/codex/plugins/demo@local",
        json={"layer": "user", "enabled": False},
    )
    assert old_layer.status_code == 422


def test_codex_plugins_report_scope_state_and_project_override(tmp_path) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"name":"demo","version":"1.2.3"}', encoding="utf-8")
    user_config = resolver.resolve("user", "config")
    project_config = resolver.resolve("project", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."demo@local"]\nenabled = true\n', encoding="utf-8")
    project_config.write_text(
        '[plugins."demo@local"]\nenabled = false\n', encoding="utf-8"
    )

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")

    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["effectiveEnabled"] is False
    assert "layers" not in plugin
    assert plugin["scopes"] == [
        {"scope": "user", "configured": True, "enabled": True},
        {"scope": "project", "configured": True, "enabled": False},
    ]


def test_codex_plugins_effective_enabled_defaults_to_false_without_config(
    tmp_path,
) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, _resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"name":"demo","version":"1.2.3"}', encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")

    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["effectiveEnabled"] is False
    assert "layers" not in plugin
    assert plugin["scopes"] == [
        {"scope": "user", "configured": False, "enabled": None},
        {"scope": "project", "configured": False, "enabled": None},
    ]


def test_codex_file_resources_manage_editable_files_and_read_only_sources(
    tmp_path,
) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    plugin_skill = package_root / "skills" / "review" / "SKILL.md"
    plugin_skill.parent.mkdir(parents=True, exist_ok=True)
    plugin_skill.write_text("# Review\n", encoding="utf-8")
    manifest = plugin_skill.parents[2] / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"demo","version":"1.2.3","skills":"./skills"}',
        encoding="utf-8",
    )
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."demo@local"]\nenabled = true\n', encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/subagents/files?scope=project")
    assert response.status_code == 404

    old_layer_response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/files?layer=user"
    )
    assert old_layer_response.status_code == 422

    response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?scope=project")
    assert response.status_code == 200
    assert response.json()["scope"] == "project"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "scope": "project",
            "definition": {
                "name": "worker",
                "description": "Project worker",
                "developer_instructions": "Use project instructions.",
            },
        },
    )

    assert response.status_code == 200
    assert resolver.resolve("project", "subagents").joinpath("worker.toml").is_file()

    response = client.get("/api/v1/workspaces/ws-1/codex/subagents")
    assert response.status_code == 200
    files = response.json()["items"]
    built_in = {file["name"]: file for file in files if file["source"] == "built_in"}
    assert built_in["worker"]["overridden"] is True
    assert built_in["worker"]["content"] == ""

    response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?scope=user")
    assert response.status_code == 200
    assert [
        file for file in response.json()["files"] if file["source"] == "plugin"
    ] == []

    response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?scope=plugin")
    assert response.status_code == 200
    plugin_file = next(
        file
        for file in response.json()["files"]
        if file["source"] == "plugin" and file["readOnly"]
    )
    assert plugin_file["metadata"]["pluginId"] == "demo@local"
    assert plugin_file["metadata"]["pluginName"] == "demo"

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=plugin&path=review%2FSKILL.md&pluginId=demo%40local&raw=false"
    )
    assert response.status_code == 200
    assert response.json()["scope"] == "plugin"
    assert "layer" not in response.json()
    assert response.json()["content"] == "# Review\n"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=plugin",
        json={"path": "review/SKILL.md", "content": "# Changed\n"},
    )
    assert response.status_code == 422

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=user&path=../escape.md"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == {
        "errorCode": "INVALID_FILE_PATH",
        "message": "../escape.md",
    }

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/subagents/file?scope=user&path=../escape.toml"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == {
        "error": "INVALID_FILE_PATH",
        "message": "../escape.toml",
    }


@pytest.mark.parametrize("scope", ["project", "user"])
def test_codex_raw_skill_files_return_png_bytes_for_managed_scopes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, scope: str
) -> None:
    threadpool_calls = []

    async def inline_threadpool(operation, *args, **kwargs):
        threadpool_calls.append((operation, args, kwargs))
        return operation(*args, **kwargs)

    monkeypatch.setattr(codex_router_module, "run_in_threadpool", inline_threadpool)
    client, resolver = _client(tmp_path)
    image = resolver.resolve(scope, "skills") / "review" / "assets" / "logo.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\n")

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": scope,
            "path": "review/assets/logo.png",
            "raw": "true",
        },
    )

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\n"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'inline; filename="logo.png"'
    documented_content = client.app.openapi()["paths"][
        "/api/v1/workspaces/{workspace_id}/codex/{resource}/file"
    ]["get"]["responses"]["200"]["content"]
    assert response.headers["content-type"] in documented_content
    assert len(threadpool_calls) == 1


def test_codex_file_openapi_advertises_json_and_binary_content(tmp_path) -> None:
    client, _resolver = _client(tmp_path)

    operation = client.app.openapi()["paths"][
        "/api/v1/workspaces/{workspace_id}/codex/{resource}/file"
    ]["get"]
    success_content = operation["responses"]["200"]["content"]

    assert success_content["application/json"]["schema"] == {
        "$ref": "#/components/schemas/CodexTextFileResponse"
    }
    assert success_content["application/octet-stream"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert success_content["image/png"]["schema"] == {
        "type": "string",
        "format": "binary",
    }
    assert operation["responses"]["413"]["description"] == (
        "Raw preview exceeds the configured size limit."
    )
    assert operation["responses"]["413"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/APIErrorDetail"
    }


@pytest.mark.parametrize("scope", ["project", "user", "plugin"])
def test_codex_raw_preview_accepts_exact_limit_and_rejects_one_byte_over(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    scope: str,
) -> None:
    limit = 8
    monkeypatch.setattr(codex_settings_module, "_RAW_PREVIEW_MAX_BYTES", limit)
    plugin_inventory = None
    if scope == "plugin":
        package_root = _plugin_cache_root(tmp_path)
        plugin_inventory = _plugin_cli_inventory(package_root)
    client, resolver = _client(tmp_path, plugin_inventory=plugin_inventory)
    params = {"scope": scope, "raw": "true"}
    if scope == "plugin":
        target = package_root / "skills" / "review" / "SKILL.md"
        params.update({"path": "review/SKILL.md", "pluginId": "demo@local"})
        manifest = package_root / ".codex-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(
            '{"name":"demo","version":"1.2.3","skills":"./skills"}',
            encoding="utf-8",
        )
    else:
        target = resolver.resolve(scope, "skills") / "review" / "preview.bin"
        params["path"] = "review/preview.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * limit)

    exact = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params=params,
    )
    target.write_bytes(b"x" * (limit + 1))
    oversized = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params=params,
    )

    assert exact.status_code == 200
    assert exact.content == b"x" * limit
    assert oversized.status_code == 413
    assert oversized.json()["detail"] == {
        "errorCode": "FILE_TOO_LARGE",
        "message": "Raw preview exceeds the configured size limit",
    }
    assert str(tmp_path) not in oversized.text
    assert str(target) not in oversized.text


def test_codex_raw_preview_reads_only_limit_plus_one(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    limit = 8
    monkeypatch.setattr(codex_settings_module, "_RAW_PREVIEW_MAX_BYTES", limit)
    client, resolver = _client(tmp_path)
    target = resolver.resolve("project", "skills") / "review" / "large.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * (limit + 20))
    original_read = raw_file_module._read_descriptor
    requested_sizes: list[int] = []

    def guarded_read(descriptor: int, size: int) -> bytes:
        requested_sizes.append(size)
        return original_read(descriptor, size)

    monkeypatch.setattr(raw_file_module, "_read_descriptor", guarded_read)

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={"scope": "project", "path": "review/large.bin", "raw": "true"},
    )

    assert response.status_code == 413
    assert requested_sizes == [limit + 1]


def test_codex_raw_preview_maps_read_error_without_paths(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, resolver = _client(tmp_path)
    target = resolver.resolve("project", "skills") / "review" / "broken.bin"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"data")

    def failed_read(_descriptor: int, _size: int) -> bytes:
        raise OSError(errno.EIO, f"sensitive backend path: {target}")

    monkeypatch.setattr(raw_file_module, "_read_descriptor", failed_read)

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={"scope": "project", "path": "review/broken.bin", "raw": "true"},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "errorCode": "FILE_READ_FAILED",
        "message": "Unable to read requested file",
    }
    assert str(tmp_path) not in response.text
    assert str(target) not in response.text


def test_codex_raw_skill_files_map_missing_and_traversal_without_path_leakage(
    tmp_path,
) -> None:
    client, _resolver = _client(tmp_path)

    missing = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={"scope": "project", "path": "missing.png", "raw": "true"},
    )
    traversal = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={"scope": "user", "path": "../private.png", "raw": "true"},
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == {
        "errorCode": "FILE_NOT_FOUND",
        "message": "missing.png",
    }
    assert traversal.status_code == 400
    assert traversal.json()["detail"] == {
        "errorCode": "INVALID_FILE_PATH",
        "message": "../private.png",
    }
    assert str(tmp_path) not in missing.text
    assert str(tmp_path) not in traversal.text


def test_codex_raw_preview_rejects_static_symlink_ancestors(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    outside = tmp_path / "private-assets"
    outside.mkdir()
    (outside / "logo.png").write_bytes(b"private")
    skills_root = resolver.resolve("project", "skills")
    skills_root.mkdir(parents=True)
    (skills_root / "review").symlink_to(outside, target_is_directory=True)

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "project",
            "path": "review/logo.png",
            "raw": "true",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == {
        "errorCode": "FILE_NOT_FOUND",
        "message": "review/logo.png",
    }
    assert b"private" not in response.content
    assert str(outside) not in response.text


def test_codex_plugin_raw_resolution_error_is_redacted(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, _resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    sensitive_path = package_root / "sensitive-inventory.json"

    def failed_skills(_resolver):
        raise OSError(errno.EIO, f"failed to resolve {sensitive_path}")

    monkeypatch.setattr(
        codex_settings_module.CodexPluginResourceResolver,
        "skills",
        failed_skills,
    )

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/assets/logo.png",
            "pluginId": "demo@local",
            "raw": "true",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "errorCode": "FILE_READ_FAILED",
        "message": "Unable to read requested file",
    }
    assert str(package_root) not in response.text
    assert str(sensitive_path) not in response.text


def test_codex_plugin_raw_read_supports_inventory_skill_children_only(
    tmp_path,
) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, _resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(package_root),
    )
    plugin_skill = package_root / "skills" / "review" / "SKILL.md"
    plugin_skill.parent.mkdir(parents=True, exist_ok=True)
    plugin_skill.write_text("# Review\n", encoding="utf-8")
    hidden_asset = plugin_skill.parent / "assets" / "logo.png"
    hidden_asset.parent.mkdir(parents=True)
    hidden_asset.write_bytes(b"\x89PNG\r\n\x1a\n")
    outside = package_root.parent / "private.png"
    outside.write_bytes(b"private")
    (plugin_skill.parent / "escape.png").symlink_to(outside)
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"demo","version":"1.2.3","skills":"./skills"}',
        encoding="utf-8",
    )

    resolved = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/SKILL.md",
            "pluginId": "demo@local",
            "raw": "true",
        },
    )
    child_asset = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/assets/logo.png",
            "pluginId": "demo@local",
            "raw": "true",
        },
    )
    wrong_plugin = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/SKILL.md",
            "pluginId": "other@local",
            "raw": "true",
        },
    )
    missing_plugin = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/assets/logo.png",
            "raw": "true",
        },
    )
    traversal = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/../private.png",
            "pluginId": "demo@local",
            "raw": "true",
        },
    )
    symlink = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file",
        params={
            "scope": "plugin",
            "path": "review/escape.png",
            "pluginId": "demo@local",
            "raw": "true",
        },
    )

    assert resolved.status_code == 200
    assert resolved.content == b"# Review\n"
    assert resolved.headers["content-type"].startswith("text/markdown")
    assert child_asset.status_code == 200
    assert child_asset.content == b"\x89PNG\r\n\x1a\n"
    assert child_asset.headers["content-type"] == "image/png"
    assert wrong_plugin.status_code == 404
    assert wrong_plugin.json()["detail"]["errorCode"] == "PLUGIN_FILE_NOT_FOUND"
    assert missing_plugin.status_code == 404
    assert missing_plugin.json()["detail"]["errorCode"] == "PLUGIN_FILE_NOT_FOUND"
    assert traversal.status_code == 400
    assert traversal.json()["detail"]["errorCode"] == "INVALID_FILE_PATH"
    assert symlink.status_code == 404
    assert symlink.json()["detail"]["errorCode"] == "PLUGIN_FILE_NOT_FOUND"
    for response in (wrong_plugin, missing_plugin, traversal, symlink):
        assert str(package_root) not in response.text
        assert str(outside) not in response.text


def test_codex_skills_file_requires_revision_and_rejects_stale_writes(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    skill_path = resolver.resolve("user", "skills") / "review" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text("# Review\n", encoding="utf-8")

    got = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=user&path=review%2FSKILL.md"
    )

    assert got.status_code == 200
    assert got.json()["revision"] == compute_revision("# Review\n")

    missing_revision = client.put(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=user",
        json={"path": "review/SKILL.md", "content": "# Missing revision\n"},
    )

    assert missing_revision.status_code == 422
    assert skill_path.read_text(encoding="utf-8") == "# Review\n"

    stale = client.put(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=user",
        json={"path": "review/SKILL.md", "content": "# Stale\n", "revision": "stale"},
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["errorCode"] == "REVISION_CONFLICT"
    assert skill_path.read_text(encoding="utf-8") == "# Review\n"

    updated = client.put(
        "/api/v1/workspaces/ws-1/codex/skills/file?scope=user",
        json={
            "path": "review/SKILL.md",
            "content": "# Updated\n",
            "revision": compute_revision("# Review\n"),
        },
    )

    assert updated.status_code == 200
    assert updated.json()["revision"] == compute_revision("# Updated\n")
    assert skill_path.read_text(encoding="utf-8") == "# Updated\n"


def test_codex_prompts_file_writes_do_not_require_revision(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    prompt = client.put(
        "/api/v1/workspaces/ws-1/codex/prompts/file?scope=user",
        json={"path": "daily.md", "content": "# Daily\n"},
    )

    assert prompt.status_code == 200
    assert "revision" not in prompt.json()
    assert (resolver.resolve("user", "prompts") / "daily.md").read_text(
        encoding="utf-8"
    ) == "# Daily\n"


def test_codex_plugin_inventory_keeps_disabled_read_only_resources(
    tmp_path,
    monkeypatch,
) -> None:
    package_root = _plugin_cache_root(tmp_path)
    client, resolver = _client(
        tmp_path,
        plugin_inventory=_plugin_cli_inventory(
            package_root,
            enabled=False,
        ),
    )
    skill = package_root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")
    hooks = package_root / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(
        '{"SessionStart":[{"hooks":[{"type":"command","command":"echo plugin"}]}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "app.modules.cli_settings.codex.app_server_hooks.CodexHooksListClient.list_hooks",
        lambda _self, _cwd: (
            SimpleNamespace(
                plugin_id="demo@local",
                source_path=hooks.resolve(strict=False),
                key="demo-hook",
                current_hash="demo-hash",
                enabled=True,
                trust_status="untrusted",
            ),
        ),
    )
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"name":"demo","version":"1.2.3","skills":"./skills","hooks":"./hooks/hooks.json"}',
        encoding="utf-8",
    )
    config = resolver.resolve("user", "config")
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[plugins."demo@local"]\nenabled = false\n', encoding="utf-8")

    skills_response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/files?scope=plugin"
    )
    hooks_response = client.get("/api/v1/workspaces/ws-1/codex/hooks-scopes")

    assert skills_response.status_code == 200
    plugin_skills = [
        item for item in skills_response.json()["files"] if item["source"] == "plugin"
    ]
    assert len(plugin_skills) == 1
    assert plugin_skills[0]["metadata"]["enabled"] is False
    assert package_root.as_posix() not in json.dumps(plugin_skills[0])
    assert hooks_response.status_code == 200
    plugin_documents = [
        document
        for document in hooks_response.json()["scopes"]
        if document["source"] == "plugin"
    ]
    assert len(plugin_documents) == 1
    plugin_entry = plugin_documents[0]["entries"][0]
    assert plugin_entry["readOnly"] is True
    assert plugin_entry["sourcePath"] == "hooks/hooks.json"
    assert package_root.as_posix() not in json.dumps(plugin_entry)
