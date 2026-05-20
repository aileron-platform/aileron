from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import subprocess

from app.modules.cli_settings import router
from app.modules.cli_settings.codex.service import CodexSettingsService, get_codex_settings_service
from app.modules.cli_settings.codex_paths import CodexPathResolver


def _client(tmp_path):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    resolver = CodexPathResolver(
        user_home=tmp_path / "home" / "developer",
        workspace_root=tmp_path / "workspace",
    )
    app.dependency_overrides[get_codex_settings_service] = lambda: CodexSettingsService(resolver)
    return TestClient(app), resolver


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


def test_codex_overview_reads_trust_plugins_requirements_and_memories(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.codex_home / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
model = "gpt-5.1-codex"
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
model = "gpt-5.2"
""".strip().format(workspace_path=str(resolver.workspace_root)),
        encoding="utf-8",
    )
    (resolver.resolve("project", "managed_requirements")).parent.mkdir(parents=True, exist_ok=True)
    resolver.resolve("project", "managed_requirements").write_text("version = 1\n", encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/overview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["activeModel"] == "gpt-5.2"
    assert payload["activeProfile"] == "work"
    assert payload["trust"]["trusted"] is True
    assert payload["plugins"] == {"configured": 2, "enabled": 1, "disabled": 1}
    assert payload["managedRequirements"]["present"] is True
    assert payload["memories"] == {"use": True, "generate": False}


def test_codex_trust_update_writes_user_config(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.patch("/api/v1/workspaces/ws-1/codex/overview/trust", json={"trusted": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["trust"]["trusted"] is True
    assert f'[projects."{resolver.workspace_root}"]' in resolver.resolve("user", "config").read_text(encoding="utf-8")


def test_codex_agents_md_reports_override_fallback_and_size_caveats(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    workspace = resolver.workspace_root
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / ".codex").mkdir(parents=True, exist_ok=True)
    (workspace / ".codex" / "config.toml").write_text(
        'project_doc_fallback_filenames = ["TEAM_GUIDE.md"]\nproject_doc_max_bytes = 10\n',
        encoding="utf-8",
    )
    (workspace / "AGENTS.md").write_text("0123456789", encoding="utf-8")
    (workspace / "AGENTS.override.md").write_text("override", encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/agents-md?scope=project")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "0123456789"
    assert payload["activePath"].endswith("AGENTS.override.md")
    assert {caveat["type"] for caveat in payload["caveats"]} == {"override", "size_limit"}

    (workspace / "AGENTS.md").unlink()
    (workspace / "TEAM_GUIDE.md").write_text("team", encoding="utf-8")
    response = client.get("/api/v1/workspaces/ws-1/codex/agents-md?scope=project")
    assert response.status_code == 200
    payload = response.json()
    assert payload["activePath"].endswith("AGENTS.override.md")
    assert "override" in {caveat["type"] for caveat in payload["caveats"]}


def test_codex_agents_md_writes_user_and_project_documents(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/agents-md",
        json={"scope": "user", "content": "User instructions"},
    )

    assert response.status_code == 200
    assert resolver.resolve("user", "agents_md").read_text(encoding="utf-8") == "User instructions"


def test_codex_managed_requirements_are_read_only_sources(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    resolver.resolve("user", "managed_requirements").parent.mkdir(parents=True, exist_ok=True)
    resolver.resolve("user", "managed_requirements").write_text("user = true\n", encoding="utf-8")
    resolver.resolve("project", "managed_requirements").parent.mkdir(parents=True, exist_ok=True)
    resolver.resolve("project", "managed_requirements").write_text("project = true\n", encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/managed-requirements")

    assert response.status_code == 200
    payload = response.json()
    assert [source["layer"] for source in payload["sources"]] == ["user", "project"]
    assert all("content" in source for source in payload["sources"])


def test_codex_config_raw_update_validates_toml(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config?layer=user",
        json={"content": 'model = "gpt-5.2"\n'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == 'model = "gpt-5.2"\n'
    assert payload["layer"] == "user"
    assert payload["exists"] is True
    assert resolver.resolve("user", "config").read_text(encoding="utf-8") == 'model = "gpt-5.2"\n'

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config?layer=user",
        json={"content": "model = ["},
    )

    assert response.status_code == 400


def test_codex_config_sections_preserve_unknown_keys(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    config_path = resolver.resolve("project", "config")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
unknown = "keep"
model = "old"

[profiles.default]
model = "gpt-5.1"
""".strip(),
        encoding="utf-8",
    )

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config/structured?layer=project",
        json={"data": {"model": "gpt-5.2", "unknown_update": "ignored"}},
    )

    assert response.status_code == 200
    content = config_path.read_text(encoding="utf-8")
    assert 'unknown = "keep"' in content
    assert 'model = "gpt-5.2"' in content
    assert "unknown_update" not in content

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/config/profiles?layer=project",
        json={"data": {"default": {"model": "gpt-5.3"}, "explorer": {"model": "gpt-5.2"}}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["default"]["model"] == "gpt-5.3"
    assert payload["data"]["explorer"]["model"] == "gpt-5.2"


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
    resolver.resolve("user", "config").write_text("[agents]\nmax_threads = 4\nmax_depth = 1\n", encoding="utf-8")
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
    assert all(item["source"] != "managed" for item in payload["items"])
    worker_items = [item for item in payload["items"] if item["name"] == "worker"]
    assert {item["source"] for item in worker_items} == {"project", "user", "built_in"}
    assert next(item for item in worker_items if item["source"] == "project")["effective"] is True
    assert next(item for item in worker_items if item["source"] == "user")["overridden"] is True
    assert next(item for item in worker_items if item["source"] == "built_in")["readOnly"] is True
    requirements_item = next(item for item in payload["items"] if item["name"] == "requirements_worker")
    assert requirements_item["source"] == "project"
    assert requirements_item["readOnly"] is True
    assert all(item["content"] == "" for item in payload["items"])
    assert payload["registry"][0]["settings"]["max_threads"] == 4

    response = client.get("/api/v1/workspaces/ws-1/codex/subagents/detail?source=project&path=worker.toml")
    assert response.status_code == 200
    detail = response.json()
    assert detail["content"].startswith('name = "worker"')
    assert detail["definition"]["developer_instructions"] == "Use project worker instructions."


def test_codex_subagents_save_raw_toml_preserves_advanced_fields_and_renames(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.post(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "layer": "project",
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
    assert response.json()["relativePath"] == "reviewer.toml"
    content = (resolver.resolve("project", "subagents") / "reviewer.toml").read_text(encoding="utf-8")
    assert 'custom_key = "keep"' in content
    assert "[mcp_servers.docs]" in content

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "layer": "project",
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
    assert response.json()["relativePath"] == "security-reviewer.toml"
    assert not (resolver.resolve("project", "subagents") / "reviewer.toml").exists()
    assert (resolver.resolve("project", "subagents") / "security-reviewer.toml").is_file()


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
        json={"layer": "user", "path": "missing.toml", "content": 'name = "missing"\ndescription = "Missing"\n'},
    )
    assert response.status_code == 400

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "layer": "user",
            "path": "existing.toml",
            "content": 'name = "existing"\ndescription = "Duplicate"\ndeveloper_instructions = "Duplicate."\n',
        },
    )
    assert response.status_code == 409


    invalid = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={"layer": "user", "path": "../escape.toml", "content": 'name = "escape"\ndescription = "Escape"\ndeveloper_instructions = "No."\n'},
    )
    assert invalid.status_code == 400
    assert not (agents_dir.parent / "escape.toml").exists()

    invalid_toml = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={"layer": "user", "path": "broken.toml", "content": "name = ["},
    )
    assert invalid_toml.status_code == 400
    assert not (agents_dir / "broken.toml").exists()

    response = client.delete("/api/v1/workspaces/ws-1/codex/subagents?layer=user&path=existing.toml")
    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert not (agents_dir / "existing.toml").exists()


def test_codex_rules_crud_stays_inside_rules_directory(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/rules/file?layer=project&path=default.rules",
        json={
            "content": 'prefix_rule(pattern = ["git", "status"], decision = "allow", justification = "Read-only")\n'
        },
    )

    assert response.status_code == 200
    assert response.json()["exists"] is True
    assert (resolver.resolve("project", "rules") / "default.rules").is_file()

    response = client.get("/api/v1/workspaces/ws-1/codex/rules?layer=project")
    assert response.status_code == 200
    assert response.json()["files"][0]["name"] == "default.rules"

    response = client.get("/api/v1/workspaces/ws-1/codex/rules/file?layer=project&path=../escape.rules")
    assert response.status_code == 400

    response = client.delete("/api/v1/workspaces/ws-1/codex/rules/file?layer=project&path=default.rules")
    assert response.status_code == 200
    assert not (resolver.resolve("project", "rules") / "default.rules").exists()


def test_codex_rules_validation_normalizes_execpolicy_result(tmp_path, monkeypatch) -> None:
    client, resolver = _client(tmp_path)
    rules_path = resolver.resolve("user", "rules") / "default.rules"
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text('prefix_rule(pattern = ["git"], decision = "allow")\n', encoding="utf-8")

    def fake_run(command, **kwargs):
        assert command == ["codex", "execpolicy", "check", "--rules", str(rules_path), "git", "status"]
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(command, 0, stdout='{"decision":"allow"}\n', stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response = client.post(
        "/api/v1/workspaces/ws-1/codex/rules/validate",
        json={"layer": "user", "path": "default.rules", "command": ["git", "status"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["exitCode"] == 0
    assert "allow" in payload["stdout"]


def test_codex_hooks_document_reads_writes_and_exposes_inline_hooks(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    project_config = resolver.resolve("project", "config")
    project_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.write_text(
        """
[features]
codex_hooks = true

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
    plugin_hooks = resolver.codex_home / "plugins" / "cache" / "local" / "hook-demo" / "abc" / "hooks" / "hooks.json"
    plugin_hooks.parent.mkdir(parents=True, exist_ok=True)
    plugin_hooks.write_text(
        '{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"echo plugin","statusMessage":"Loading plugin"}]}]}}',
        encoding="utf-8",
    )
    manifest = plugin_hooks.parents[1] / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"id":"hook-demo","marketplace":"local","name":"Hook Demo","hooks":"./hooks/hooks.json"}',
        encoding="utf-8",
    )
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."hook-demo@local"]\nenabled = true\n', encoding="utf-8")

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks?layer=project",
        json={
            "content": '{"PreToolUse":[{"matcher":"*","hooks":[{"type":"command","command":"echo json","timeout":600,"statusMessage":"Checking JSON","unknownField":true}]}]}'
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["featureEnabled"] is True
    assert payload["inlineHooks"][0]["event"] == "PreToolUse"
    assert {entry["source"] for entry in payload["entries"]} == {
        "hooks_json",
        "inline_config",
        "plugin",
        "project",
    }
    assert all(entry["source"] != "managed" for entry in payload["entries"])
    json_entry = next(entry for entry in payload["entries"] if entry["source"] == "hooks_json")
    assert json_entry["readOnly"] is False
    assert json_entry["layer"] == "project"
    assert json_entry["actions"][0]["statusMessage"] == "Checking JSON"
    assert json_entry["actions"][0]["raw"]["unknownField"] is True
    inline_entry = next(entry for entry in payload["entries"] if entry["source"] == "inline_config")
    assert inline_entry["readOnly"] is True
    assert inline_entry["actions"][0]["statusMessage"] == "Checking inline"
    plugin_entry = next(entry for entry in payload["entries"] if entry["source"] == "plugin")
    assert plugin_entry["pluginId"] == "hook-demo@local"
    assert plugin_entry["readOnly"] is True
    requirements_entry = next(entry for entry in payload["entries"] if entry["source"] == "project" and entry["readOnly"])
    assert requirements_entry["layer"] == "project"
    assert requirements_entry["actions"][0]["statusMessage"] == "Checking managed"
    session_metadata = next(item for item in payload["eventMetadata"] if item["event"] == "SessionStart")
    assert session_metadata["matcherTarget"] == "source"
    assert resolver.resolve("project", "hooks").read_text(encoding="utf-8").startswith('{"PreToolUse"')

    response = client.get("/api/v1/workspaces/ws-1/codex/hooks-scopes")
    assert response.status_code == 200
    scopes = {scope["layer"]: scope for scope in response.json()["scopes"]}
    assert set(scopes) == {"project", "user"}
    assert scopes["project"]["entries"]
    assert scopes["user"]["entries"]

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks?layer=project",
        json={"content": '{"PreToolUse": ['},
    )
    assert response.status_code == 400

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks?layer=project",
        json={"content": '["PreToolUse"]'},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_HOOKS_DOCUMENT"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks?layer=project",
        json={"content": '{"PreToolUse":[{"hooks":[{"type":"command"}]}]}'},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "MISSING_HOOK_COMMAND"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/hooks?layer=project",
        json={"content": '{"PreToolUse":[{"hooks":[{"type":"command","command":"echo bad","statusMessage":123}]}]}'},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "INVALID_HOOK_STATUS_MESSAGE"


def test_codex_hooks_enable_writes_selected_layer(tmp_path) -> None:
    client, resolver = _client(tmp_path)

    response = client.post("/api/v1/workspaces/ws-1/codex/hooks/enable?layer=project")

    assert response.status_code == 200
    assert response.json()["featureEnabled"] is True
    assert "codex_hooks = true" in resolver.resolve("project", "config").read_text(encoding="utf-8")


def test_codex_plugins_parse_registry_cache_and_toggle_config(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    marketplace = resolver.codex_home / ".tmp" / "plugins" / ".agents" / "plugins" / "marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        '{"plugins":[{"id":"demo","marketplace":"local","name":"Demo Plugin"}]}',
        encoding="utf-8",
    )
    manifest = resolver.codex_home / "plugins" / "cache" / "local" / "demo" / "abc" / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","skills":["review"],"mcp_servers":{"demo":{}}}', encoding="utf-8")

    response = client.patch(
        "/api/v1/workspaces/ws-1/codex/plugins/demo@local",
        json={"layer": "user", "enabled": True},
    )

    assert response.status_code == 200
    assert response.json()["newThreadRequired"] is True
    assert '[plugins."demo@local"]' in resolver.resolve("user", "config").read_text(encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")
    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["id"] == "demo@local"
    assert plugin["listed"] is True
    assert plugin["installed"] is True
    assert plugin["effectiveEnabled"] is True
    assert "enabled" not in plugin
    assert plugin["layers"] == [
        {"layer": "user", "configured": True, "enabled": True},
        {"layer": "project", "configured": False, "enabled": None},
    ]
    assert plugin["resourceCounts"]["skills"] == 0
    assert "bundled" not in plugin

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins/demo@local")
    assert response.status_code == 200
    detail = response.json()["plugin"]
    assert detail["effectiveEnabled"] is True
    assert detail["layers"] == plugin["layers"]


def test_codex_plugins_report_layer_state_and_project_override(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    manifest = resolver.codex_home / "plugins" / "cache" / "local" / "demo" / "abc" / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","name":"Demo"}', encoding="utf-8")
    user_config = resolver.resolve("user", "config")
    project_config = resolver.resolve("project", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    project_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."demo@local"]\nenabled = true\n', encoding="utf-8")
    project_config.write_text('[plugins."demo@local"]\nenabled = false\n', encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")

    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["effectiveEnabled"] is False
    assert plugin["layers"] == [
        {"layer": "user", "configured": True, "enabled": True},
        {"layer": "project", "configured": True, "enabled": False},
    ]


def test_codex_plugins_effective_enabled_defaults_to_false_without_config(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    manifest = resolver.codex_home / "plugins" / "cache" / "local" / "demo" / "abc" / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","name":"Demo"}', encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/plugins")

    assert response.status_code == 200
    plugin = response.json()["plugins"][0]
    assert plugin["effectiveEnabled"] is False
    assert plugin["layers"] == [
        {"layer": "user", "configured": False, "enabled": None},
        {"layer": "project", "configured": False, "enabled": None},
    ]


def test_codex_file_resources_manage_editable_files_and_read_only_sources(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    plugin_skill = resolver.codex_home / "plugins" / "cache" / "local" / "demo" / "abc" / "skills" / "review" / "SKILL.md"
    plugin_skill.parent.mkdir(parents=True, exist_ok=True)
    plugin_skill.write_text("# Review\n", encoding="utf-8")
    manifest = plugin_skill.parents[2] / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"id":"demo","marketplace":"local","skills":"./skills"}', encoding="utf-8")
    user_config = resolver.resolve("user", "config")
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_config.write_text('[plugins."demo@local"]\nenabled = true\n', encoding="utf-8")

    response = client.get("/api/v1/workspaces/ws-1/codex/subagents/files?layer=project")
    assert response.status_code == 404

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/subagents",
        json={
            "layer": "project",
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

    response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?layer=user")
    assert response.status_code == 200
    assert [file for file in response.json()["files"] if file["source"] == "plugin"] == []

    response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?layer=plugin")
    assert response.status_code == 200
    plugin_file = next(file for file in response.json()["files"] if file["source"] == "plugin" and file["readOnly"])
    assert plugin_file["metadata"]["pluginId"] == "demo@local"
    assert plugin_file["metadata"]["pluginName"] == "demo"

    response = client.get(
        "/api/v1/workspaces/ws-1/codex/skills/file?layer=plugin&path=review%2FSKILL.md&pluginId=demo%40local"
    )
    assert response.status_code == 200
    assert response.json()["layer"] == "plugin"
    assert response.json()["content"] == "# Review\n"

    response = client.put(
        "/api/v1/workspaces/ws-1/codex/skills/file?layer=plugin",
        json={"path": "review/SKILL.md", "content": "# Changed\n"},
    )
    assert response.status_code == 422


def test_codex_plugin_resources_hide_disabled_plugin_entries(tmp_path) -> None:
    client, resolver = _client(tmp_path)
    package_root = resolver.codex_home / "plugins" / "cache" / "local" / "demo" / "abc"
    skill = package_root / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("# Review\n", encoding="utf-8")
    hooks = package_root / "hooks" / "hooks.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text('{"SessionStart":[{"hooks":[{"type":"command","command":"echo plugin"}]}]}', encoding="utf-8")
    manifest = package_root / ".codex-plugin" / "plugin.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        '{"id":"demo","marketplace":"local","name":"Demo","skills":"./skills","hooks":"./hooks/hooks.json"}',
        encoding="utf-8",
    )
    config = resolver.resolve("user", "config")
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('[plugins."demo@local"]\nenabled = false\n', encoding="utf-8")

    skills_response = client.get("/api/v1/workspaces/ws-1/codex/skills/files?layer=plugin")
    hooks_response = client.get("/api/v1/workspaces/ws-1/codex/hooks?layer=user")

    assert skills_response.status_code == 200
    assert [item for item in skills_response.json()["files"] if item["source"] == "plugin"] == []
    assert hooks_response.status_code == 200
    assert [item for item in hooks_response.json()["entries"] if item["source"] == "plugin"] == []
