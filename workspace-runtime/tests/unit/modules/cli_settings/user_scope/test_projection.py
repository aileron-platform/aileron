from __future__ import annotations

from hashlib import sha256

from aileron_marketplace_core import (
    PluginPackageFormat,
    TargetClient,
    UserCopyResourceType,
    UserCopySourceKind,
    UserCopySourceResource,
    extract_user_copy_source_profile,
    PluginReleaseIdentity,
)

from app.modules.cli_settings.user_scope.projection import (
    UserCopyProjectionRegistry,
)
from app.modules.cli_settings.user_scope.models import UserScopeAgent, UserScopeResource
from app.modules.cli_settings.user_scope.paths import (
    UserScopePathResolver,
    target_client_state_root_id,
)
from app.modules.cli_settings.user_scope.planner import (
    UserCopyInventory,
    UserCopyPlanStatus,
    UserCopyPlanner,
)


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _resource(
    resource_type: UserCopyResourceType,
    resource_id: str,
    source_locator: str,
    *,
    structured_value: object | None = None,
) -> UserCopySourceResource:
    return UserCopySourceResource(
        resource_type=resource_type,
        resource_id=resource_id,
        source_locator=source_locator,
        source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
        source_digest=_digest(resource_id),
        structured_value=structured_value,
    )


def test_agent_plugin_projection_maps_codex_portable_resources() -> None:
    projection = UserCopyProjectionRegistry().resolve(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        TargetClient.CODEX,
    )

    skill = projection.project(
        _resource(UserCopyResourceType.SKILL, "deploy", "skills/deploy")
    )
    mcp = projection.project(
        _resource(
            UserCopyResourceType.MCP,
            "validator",
            "mcp.json",
            structured_value={
                "type": "stdio",
                "command": "node",
                "args": ["${PLUGIN_ROOT}/bin/server.js"],
            },
        )
    )

    assert skill.projected is not None
    assert skill.projected.target_resource == "skills"
    assert skill.projected.copy_semantics == "create-directory"
    assert skill.projected.relative_target == "deploy"
    assert mcp.projected is not None
    assert mcp.projected.target_resource == "mcp"
    assert mcp.projected.copy_semantics == "merge-config-entry"
    assert mcp.projected.structured_value == {
        "command": "node",
        "args": ["${PLUGIN_ROOT}/bin/server.js"],
    }


def test_agent_plugin_projection_skips_data_lifecycle_and_sse_entries() -> None:
    projection = UserCopyProjectionRegistry().resolve(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        TargetClient.CODEX,
    )

    plugin_data = projection.project(
        _resource(
            UserCopyResourceType.MCP,
            "stateful",
            "mcp.json",
            structured_value={
                "type": "stdio",
                "command": "node",
                "args": ["${PLUGIN_DATA}/state.json"],
            },
        )
    )
    sse = projection.project(
        _resource(
            UserCopyResourceType.MCP,
            "legacy",
            "mcp.json",
            structured_value={"type": "sse", "url": "https://example.com/mcp"},
        )
    )

    assert plugin_data.skipped is not None
    assert plugin_data.skipped.code == "plugin-data-lifecycle-unsupported"
    assert sse.skipped is not None
    assert sse.skipped.code == "mcp-transport-unsupported"


def test_planner_requires_confirmation_for_partial_agent_plugin_copy(
    tmp_path,
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    skill = package_root / "skills" / "deploy"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Deploy\n", encoding="utf-8")
    (package_root / "mcp.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'mcp.schema.json","mcpServers":{"legacy":{"type":"sse",'
        '"url":"https://example.com/mcp"}}}',
        encoding="utf-8",
    )
    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision="c" * 64,
        ),
    )

    plan = UserCopyPlanner(
        package_id="demo",
        paths=UserScopePathResolver(tmp_path / "home"),
    ).plan_source_profile(
        profile,
        target_client=TargetClient.CODEX,
        package_root=package_root,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED
    assert [resource.resource_id for resource in plan.resources] == ["deploy"]
    assert [(item.resource_id, item.code) for item in plan.skipped_resources] == [
        ("legacy", "mcp-transport-unsupported")
    ]
    assert plan.blocking_issues == ()
    assert len(plan.projection_digest) == 64
    assert plan.canonical_dict()["packageFormat"] == "agent-plugin/1.0.0"
    assert plan.canonical_dict()["targetClient"] == "codex"
    assert "provider" not in plan.canonical_dict()


def test_codex_home_override_controls_targets_and_root_proof(tmp_path) -> None:
    codex_home = tmp_path / "effective-codex-home"
    paths = UserScopePathResolver(
        tmp_path / "runtime-home",
        codex_home=codex_home,
    )

    assert paths.resolve_root(UserScopeAgent.CODEX).runtime_path == codex_home
    assert (
        paths.resolve(UserScopeAgent.CODEX, UserScopeResource.MCP).runtime_path
        == codex_home / "config.toml"
    )
    proof = target_client_state_root_id(TargetClient.CODEX, paths=paths)
    assert proof.startswith("tcsr_")
    assert len(proof) == len("tcsr_") + 64


def test_claude_config_override_controls_directory_and_global_config(tmp_path) -> None:
    config_dir = tmp_path / "effective-claude-config"
    paths = UserScopePathResolver(
        tmp_path / "runtime-home",
        claude_config_dir=config_dir,
    )

    assert paths.resolve_root(UserScopeAgent.CLAUDE_CODE).runtime_path == config_dir
    assert (
        paths.resolve(UserScopeAgent.CLAUDE_CODE, UserScopeResource.SKILLS)
        .runtime_path
        == config_dir / "skills"
    )
    assert (
        paths.resolve(UserScopeAgent.CLAUDE_CODE, UserScopeResource.MCP)
        .runtime_path
        == config_dir / ".claude.json"
    )


def test_agent_plugin_root_reference_is_release_scoped_payload(tmp_path) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    (package_root / "bin").mkdir()
    (package_root / "bin" / "server.js").write_text("server\n", encoding="utf-8")
    (package_root / "mcp.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'mcp.schema.json","mcpServers":{"server":{"type":"stdio",'
        '"command":"node","args":["${PLUGIN_ROOT}/bin/server.js"]}}}',
        encoding="utf-8",
    )
    revision = "c" * 64
    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision=revision,
        ),
    )

    plan = UserCopyPlanner(
        package_id="catalog-digest",
        release_revision=revision,
        paths=UserScopePathResolver(tmp_path / "home"),
    ).plan_source_profile(
        profile,
        target_client=TargetClient.CODEX,
        package_root=package_root,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.blocking_issues == ()
    payload = next(
        resource
        for resource in plan.resources
        if resource.resource_type == "dependency-payload"
    )
    assert payload.target_locator == (
        "~/.aileron/user-copy-payloads/codex/catalog-digest/"
        f"{revision}/bin/server.js"
    )


def test_unsupported_projection_pair_is_a_blocked_plan(tmp_path) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision="d" * 64,
        ),
    )

    plan = UserCopyPlanner(
        package_id="demo",
        paths=UserScopePathResolver(tmp_path / "home"),
    ).plan_source_profile(
        profile,
        target_client=TargetClient.CLAUDE_CODE,
        package_root=package_root,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.status is UserCopyPlanStatus.BLOCKED
    assert [issue.code for issue in plan.blocking_issues] == [
        "marketplace.user_copy.projection_not_supported"
    ]
    assert plan.resources == ()


def test_invalid_agent_plugin_component_requires_partial_copy_confirmation(
    tmp_path,
) -> None:
    package_root = tmp_path / "package"
    package_root.mkdir()
    (package_root / "plugin.json").write_text(
        '{"$schema":"https://agent-plugins.org/schemas/1.0.0/'
        'plugin.schema.json","name":"demo"}',
        encoding="utf-8",
    )
    (package_root / "skills" / "valid").mkdir(parents=True)
    (package_root / "skills" / "valid" / "SKILL.md").write_text(
        "# Valid\n", encoding="utf-8"
    )
    (package_root / "skills" / "broken").mkdir()
    profile = extract_user_copy_source_profile(
        PluginPackageFormat.AGENT_PLUGIN_V1,
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision="e" * 64,
        ),
    )

    plan = UserCopyPlanner(
        package_id="demo",
        paths=UserScopePathResolver(tmp_path / "home"),
    ).plan_source_profile(
        profile,
        target_client=TargetClient.CODEX,
        package_root=package_root,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED
    assert [(item.resource_id, item.code) for item in plan.skipped_resources] == [
        ("broken", "skill-invalid")
    ]
    assert [resource.resource_id for resource in plan.resources] == ["valid"]
