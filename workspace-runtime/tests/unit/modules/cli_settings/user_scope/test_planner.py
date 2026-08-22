from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from aileron_marketplace_core import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopySourceDiagnostic,
    UserCopySourceProfile,
    extract_user_copy_source_profile,
)

from app.modules.cli_settings.user_scope.adapter import UserCopyAdapterError
from app.modules.cli_settings.user_scope.paths import UserScopePathResolver
from app.modules.cli_settings.user_scope.planner import (
    UserCopyAction,
    UserCopyInventory,
    UserCopyPlanStatus,
    UserCopyPlanner,
    UserCopyTargetKind,
    validate_overwrite_approvals,
)

from .fixtures import plan_codex_package, write_full_codex_package, write_text


def _planner(runtime_home: Path) -> UserCopyPlanner:
    runtime_home.mkdir(parents=True, exist_ok=True)
    return UserCopyPlanner(
        package_id="demo",
        release_revision="a" * 64,
        paths=UserScopePathResolver(user_home=runtime_home),
    )


def _preview_plan(package: Path, runtime_home: Path):
    profile = extract_user_copy_source_profile(
        "codex-native",
        package,
        release=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
    )
    return _planner(runtime_home).plan_source_profile(
        profile,
        target_client="codex",
        package_root=None,
        inventory=UserCopyInventory(complete=True),
    )


def test_full_profile_is_deterministic_and_contains_dependency_payload(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_full_codex_package(package)

    first = plan_codex_package(package, runtime_home)
    second = plan_codex_package(package, runtime_home)

    assert first.status is UserCopyPlanStatus.READY
    assert first.canonical_dict() == second.canonical_dict()
    assert {
        (resource.resource_type, resource.target_kind) for resource in first.resources
    } == {
        ("instructions", UserCopyTargetKind.FILE),
        ("skill", UserCopyTargetKind.DIRECTORY),
        ("subagent", UserCopyTargetKind.FILE),
        ("prompt", UserCopyTargetKind.FILE),
        ("rule", UserCopyTargetKind.FILE),
        ("mcp", UserCopyTargetKind.CONFIG_ENTRY),
        ("hook", UserCopyTargetKind.CONFIG_ENTRY),
        ("dependency-payload", UserCopyTargetKind.FILE),
    }
    payload = next(
        item for item in first.resources if item.resource_type == "dependency-payload"
    )
    assert payload.source_locator == "bin/server"
    assert payload.target_locator == (
        "~/.aileron/user-copy-payloads/codex/demo/" f"{'a' * 64}/bin/server"
    )
    assert str(tmp_path) not in json.dumps(
        first.canonical_dict(),
        sort_keys=True,
    )


def test_checkout_free_preview_matches_full_plan(tmp_path: Path) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_full_codex_package(package)

    full = plan_codex_package(package, runtime_home)
    preview = _preview_plan(package, runtime_home)

    assert preview.canonical_dict() == full.canonical_dict()
    assert all(not resource.source_path.is_absolute() for resource in preview.resources)


def test_directory_payload_covers_directory_and_descendant_template_references(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(
        package / ".codex-plugin" / "plugin.json",
        json.dumps(
            {
                "name": "demo",
                "mcpServers": {
                    "local": {
                        "command": "${CODEX_PLUGIN_ROOT}/bin",
                        "args": ["${CODEX_PLUGIN_ROOT}/bin/server.js"],
                    }
                },
            }
        ),
    )
    write_text(package / "bin" / "server.js", "console.log('ready')\n")

    full = plan_codex_package(package, runtime_home)
    preview = _preview_plan(package, runtime_home)
    payloads = [
        resource
        for resource in full.resources
        if resource.resource_type == "dependency-payload"
    ]

    assert preview.canonical_dict() == full.canonical_dict()
    assert len(payloads) == 1
    assert payloads[0].source_locator == "bin"
    assert payloads[0].target_kind is UserCopyTargetKind.DIRECTORY


def test_identical_target_is_unchanged_and_different_target_needs_approval(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(package / "AGENTS.md", "# Instructions\n")
    target = runtime_home / ".codex" / "AGENTS.md"
    write_text(target, "# Instructions\n")

    unchanged = plan_codex_package(package, runtime_home)
    assert unchanged.status is UserCopyPlanStatus.READY
    assert unchanged.resources[0].action is UserCopyAction.UNCHANGED

    write_text(target, "# User value\n")
    conflict = plan_codex_package(package, runtime_home)
    assert conflict.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED
    assert conflict.resources[0].action is UserCopyAction.OVERWRITE
    with pytest.raises(UserCopyAdapterError):
        validate_overwrite_approvals(conflict, ())


def test_dependency_executable_mode_difference_is_a_conflict(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_full_codex_package(package)
    initial = plan_codex_package(package, runtime_home)
    payload_target = next(
        item.runtime_path
        for item in initial.resources
        if item.resource_type == "dependency-payload"
    )
    write_text(payload_target, "#!/bin/sh\nexit 0\n")
    payload_target.chmod(0o600)

    plan = plan_codex_package(package, runtime_home)
    payload = next(
        item for item in plan.resources if item.resource_type == "dependency-payload"
    )

    assert payload.action is UserCopyAction.OVERWRITE
    assert plan.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED


def test_special_entry_in_existing_directory_is_bounded_target_unsafe(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(package / "skills" / "review" / "SKILL.md", "# Review\n")
    target = runtime_home / ".codex" / "skills" / "review"
    target.mkdir(parents=True)
    os.mkfifo(target / "unsafe.fifo")

    plan = plan_codex_package(package, runtime_home)

    assert plan.status is UserCopyPlanStatus.BLOCKED
    assert any(
        issue.code == "marketplace.user_copy.target_unsafe"
        for issue in plan.blocking_issues
    )


def test_non_public_blocked_resource_uses_opaque_safe_metadata(
    tmp_path: Path,
) -> None:
    runtime_home = tmp_path / "home"
    profile = UserCopySourceProfile(
        package_format=PluginPackageFormat.CODEX_NATIVE,
        release_identity=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
        resources=(),
        diagnostics=(
            UserCopySourceDiagnostic(
                code="unsupported-resource",
                source_locator=f"invalid-source/{'0' * 64}",
            ),
        ),
    )

    plan = _planner(runtime_home).plan_source_profile(
        profile,
        target_client="codex",
        package_root=None,
        inventory=UserCopyInventory(complete=True),
    )

    issue = next(
        item
        for item in plan.blocking_issues
        if item.code == "marketplace.user_copy.unsupported_resource"
    )
    assert issue.resource_type is None
    assert issue.source_locator == f"invalid-source/{'0' * 64}"


def test_nonempty_profile_blocked_during_projection_is_not_reported_as_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(package / "skills" / "review" / "SKILL.md", "# Review\n")
    profile = extract_user_copy_source_profile(
        "codex-native",
        package,
        release=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
    )
    planner = _planner(runtime_home)

    def reject_target(*_args: object, **_kwargs: object) -> object:
        raise UserCopyAdapterError("target-root-escape", "skills/review")

    monkeypatch.setattr(planner, "_plan_source_resource", reject_target)

    plan = planner.plan_source_profile(
        profile,
        target_client="codex",
        package_root=None,
        inventory=UserCopyInventory(complete=True),
    )

    assert [issue.code for issue in plan.blocking_issues] == [
        "marketplace.user_copy.target_not_writable"
    ]


def test_codex_native_portability_diagnostics_require_partial_confirmation(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(
        package / ".codex-plugin" / "plugin.json",
        '{"name":"demo","apps":"./.app.json"}',
    )
    write_text(package / ".app.json", '{"apps":{"demo":{"id":"connector"}}}')
    write_text(package / "skills" / "review" / "SKILL.md", "# Review\n")

    plan = plan_codex_package(package, runtime_home)

    assert plan.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED
    assert [item.code for item in plan.skipped_resources] == [
        "unsupported-resource"
    ]
    assert [item.resource_type for item in plan.resources] == ["skill"]
    assert plan.blocking_issues == ()


def test_codex_home_override_produces_a_valid_logical_target(
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "home"
    write_text(package / "skills" / "review" / "SKILL.md", "# Review\n")
    profile = extract_user_copy_source_profile(
        "codex-native",
        package,
        release=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
    )
    planner = UserCopyPlanner(
        package_id="demo",
        release_revision="a" * 64,
        paths=UserScopePathResolver(
            user_home=runtime_home,
            codex_home=runtime_home / ".codex",
        ),
    )

    plan = planner.plan_source_profile(
        profile,
        target_client="codex",
        package_root=None,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.status is UserCopyPlanStatus.READY
    assert plan.resources[0].target_locator == "$CODEX_HOME/skills/review"


def test_agent_plugin_unsupported_component_requires_confirmation(
    tmp_path: Path,
) -> None:
    profile = UserCopySourceProfile(
        package_format=PluginPackageFormat.AGENT_PLUGIN_V1,
        release_identity=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
        resources=(),
        diagnostics=(
            UserCopySourceDiagnostic(
                code="extension-unsupported",
                source_locator="plugin.json",
                resource_type="extension",
                resource_id="com.example.review",
            ),
        ),
    )

    plan = _planner(tmp_path / "home").plan_source_profile(
        profile,
        target_client="codex",
        package_root=None,
        inventory=UserCopyInventory(complete=True),
    )

    assert plan.status is UserCopyPlanStatus.CONFIRMATION_REQUIRED
    assert [item.canonical_dict() for item in plan.skipped_resources] == [
        {
            "code": "extension-unsupported",
            "resourceType": "extension",
            "resourceId": "com.example.review",
            "sourceLocator": "plugin.json",
        }
    ]


def test_dynamic_runtime_home_is_resolved_at_planner_creation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = tmp_path / "package"
    runtime_home = tmp_path / "dynamic-home"
    write_text(package / "AGENTS.md", "# Instructions\n")
    runtime_home.mkdir()
    monkeypatch.setenv("HOME", str(runtime_home))
    profile = extract_user_copy_source_profile(
        "codex-native",
        package,
        release=PluginReleaseIdentity(
            catalog_plugin_id="test/demo",
            revision="a" * 64,
        ),
    )

    plan = UserCopyPlanner(
        package_id="demo", release_revision="a" * 64
    ).plan_source_profile(
        profile,
        target_client="codex",
        package_root=package,
        inventory=UserCopyInventory(complete=True),
    )

    instructions = plan.resources[0]
    assert instructions.runtime_path == runtime_home / ".codex" / "AGENTS.md"
