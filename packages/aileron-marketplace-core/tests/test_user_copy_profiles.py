import os
import json
from hashlib import sha256
from pathlib import Path

import aileron_marketplace_core.user_copy_profiles as user_copy_profiles_module
import pytest
from aileron_marketplace_core.resource_resolution import PackageSourceError
from aileron_marketplace_core.user_copy_profiles import (
    UserCopyBlockReason,
    UserCopyResource,
    UserCopyResourceType,
    UserCopySemantics,
    UserCopySourceKind,
    UserCopyTargetResource,
    build_user_copy_profile_preview,
    build_user_copy_source_snapshot,
    resolve_user_copy_dependency_payloads,
    resolve_user_copy_profile,
    resolve_user_copy_profile_with_dependency_payloads,
    user_copy_source_digest_from_preview,
    user_copy_source_allowlist,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _resource_locators(profile, resource_type: UserCopyResourceType) -> set[str]:
    return {
        resource.source_locator
        for resource in profile.resources
        if resource.resource_type is resource_type
    }


def test_combined_source_resolvers_validate_each_tree_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        json.dumps(
            {
                "name": "demo",
                "mcpServers": {
                    "demo": {
                        "command": "node",
                        "args": ["PLUGIN_ROOT/bin/server.js"],
                    }
                },
            }
        ),
    )
    _write(tmp_path / "bin" / "server.js", "console.log('ready')\n")

    expected_profile = resolve_user_copy_profile("codex-native", tmp_path)
    expected_payloads = resolve_user_copy_dependency_payloads(
        tmp_path,
        expected_profile,
    )
    expected_preview = build_user_copy_profile_preview(tmp_path, expected_profile)
    expected_tree_digest = user_copy_profiles_module.package_tree_digest(tmp_path)

    digest_calls = 0
    original_package_tree_digest = user_copy_profiles_module.package_tree_digest

    def counted_package_tree_digest(package_root: Path) -> str:
        nonlocal digest_calls
        digest_calls += 1
        return original_package_tree_digest(package_root)

    monkeypatch.setattr(
        user_copy_profiles_module,
        "package_tree_digest",
        counted_package_tree_digest,
    )

    profile, payloads = resolve_user_copy_profile_with_dependency_payloads(
        "codex-native",
        tmp_path,
    )
    snapshot = build_user_copy_source_snapshot("codex-native", tmp_path)

    assert profile == expected_profile
    assert payloads == expected_payloads
    assert snapshot.profile == expected_profile
    assert snapshot.preview == expected_preview
    assert snapshot.package_tree_digest == expected_tree_digest
    assert digest_calls == 2


@pytest.mark.parametrize(
    ("resource_id", "source_locator"),
    [
        ("review\nhelper", "skills/review"),
        ("review", "skills/review\n"),
        ("review", "C:foo"),
    ],
)
def test_profile_resource_rejects_noncanonical_wire_fields(
    resource_id: str,
    source_locator: str,
) -> None:
    with pytest.raises(PackageSourceError, match="source-reference-invalid"):
        UserCopyResource(
            resource_type=UserCopyResourceType.SKILL,
            resource_id=resource_id,
            source_kind=UserCopySourceKind.COPY_CONVENTION,
            source_locator=source_locator,
            target_resource=UserCopyTargetResource.SKILLS,
            copy_semantics=UserCopySemantics.CREATE_DIRECTORY,
            relative_target="review",
        )


def test_codex_full_profile_includes_all_supported_user_resources(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        """
        {
          "name": "demo",
          "mcpServers": {"local": {"command": "node"}},
          "hooks": {"SessionStart": [{"command": "echo"}]},
          "interface": {"defaultPrompt": ["metadata only"]}
        }
        """,
    )
    _write(tmp_path / "AGENTS.md", "# Instructions\n")
    _write(tmp_path / "README.md", "# Not instructions\n")
    _write(tmp_path / "skills" / "review" / "SKILL.md", "# Review\n")
    _write(tmp_path / "agents" / "reviewer.toml", 'name = "reviewer"\n')
    _write(tmp_path / "prompts" / "nested" / "review.md", "# Review\n")
    _write(tmp_path / "rules" / "safe.rules", "allow prefix git\n")

    profile = resolve_user_copy_profile("codex-native", tmp_path)

    assert profile.compatible is True
    assert len(profile.profile_digest) == 64
    assert _resource_locators(profile, UserCopyResourceType.INSTRUCTIONS) == {
        "AGENTS.md"
    }
    assert _resource_locators(profile, UserCopyResourceType.SKILL) == {"skills/review"}
    assert _resource_locators(profile, UserCopyResourceType.SUBAGENT) == {
        "agents/reviewer.toml"
    }
    assert _resource_locators(profile, UserCopyResourceType.PROMPT) == {
        "prompts/nested/review.md"
    }
    assert _resource_locators(profile, UserCopyResourceType.RULE) == {
        "rules/safe.rules"
    }
    assert _resource_locators(profile, UserCopyResourceType.MCP) == {
        ".codex-plugin/plugin.json"
    }
    assert _resource_locators(profile, UserCopyResourceType.HOOK) == {
        ".codex-plugin/plugin.json"
    }
    assert "README.md" not in {
        resource.source_locator for resource in profile.resources
    }


def test_claude_full_profile_includes_target_client_copy_conventions(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".claude-plugin" / "plugin.json",
        '{"name":"demo",'
        '"mcpServers":{"local":{"command":"node"}},'
        '"hooks":{"Stop":[{}]}}',
    )
    _write(tmp_path / "CLAUDE.md", "# Instructions\n")
    _write(tmp_path / "skills" / "review" / "SKILL.md", "# Review\n")
    _write(tmp_path / "agents" / "nested" / "reviewer.md", "# Reviewer\n")
    _write(tmp_path / "commands" / "nested" / "review.md", "# Review\n")
    _write(tmp_path / "output-styles" / "concise.md", "# Concise\n")

    profile = resolve_user_copy_profile("claude-native", tmp_path)

    assert profile.compatible is True
    assert _resource_locators(profile, UserCopyResourceType.INSTRUCTIONS) == {
        "CLAUDE.md"
    }
    assert _resource_locators(profile, UserCopyResourceType.SUBAGENT) == {
        "agents/nested/reviewer.md"
    }
    assert _resource_locators(profile, UserCopyResourceType.COMMAND) == {
        "commands/nested/review.md"
    }
    assert _resource_locators(profile, UserCopyResourceType.OUTPUT_STYLE) == {
        "output-styles/concise.md"
    }


def test_claude_explicit_skill_selector_accepts_non_default_root(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".claude-plugin" / "plugin.json",
        '{"name":"demo","skills":"./components/skills/review"}',
    )
    _write(
        tmp_path / "components" / "skills" / "review" / "SKILL.md",
        "# Review\n",
    )
    _write(tmp_path / "skills" / "ignored" / "SKILL.md", "# Ignored\n")

    profile = resolve_user_copy_profile("claude-native", tmp_path)

    assert profile.compatible is True
    assert [
        (
            resource.resource_id,
            resource.source_kind,
            resource.source_locator,
            resource.relative_target,
        )
        for resource in profile.resources
        if resource.resource_type is UserCopyResourceType.SKILL
    ] == [
        (
            "review",
            UserCopySourceKind.PLUGIN_COMPONENT,
            "components/skills/review",
            "review",
        )
    ]


def test_claude_explicit_skill_selectors_reject_casefold_target_collision(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".claude-plugin" / "plugin.json",
        '{"name":"demo","skills":["./one/Review","./two/review"]}',
    )
    _write(tmp_path / "one" / "Review" / "SKILL.md", "# One\n")
    _write(tmp_path / "two" / "review" / "SKILL.md", "# Two\n")

    profile = resolve_user_copy_profile("claude-native", tmp_path)

    assert profile.compatible is False
    assert any(
        blocked.reason is UserCopyBlockReason.DUPLICATE_RESOURCE_ID
        for blocked in profile.blocked_resources
    )


@pytest.mark.parametrize("selected_count", [4, 12, 1])
def test_claude_explicit_skill_selector_counts_are_exact(
    tmp_path: Path,
    selected_count: int,
) -> None:
    selected = [
        f"./shared-skills/skill-{index:02d}"
        for index in range(selected_count)
    ]
    _write(
        tmp_path / ".claude-plugin" / "plugin.json",
        (
            '{"name":"demo","skills":'
            + json.dumps(selected)
            + "}"
        ),
    )
    for index in range(17):
        _write(
            tmp_path
            / "shared-skills"
            / f"skill-{index:02d}"
            / "SKILL.md",
            f"# Skill {index}\n",
        )
    _write(tmp_path / "skills" / "default" / "SKILL.md", "# Default\n")

    profile = resolve_user_copy_profile("claude-native", tmp_path)
    skills = [
        resource
        for resource in profile.resources
        if resource.resource_type is UserCopyResourceType.SKILL
    ]

    assert profile.compatible is True
    assert len(skills) == selected_count
    assert len({resource.resource_id.casefold() for resource in skills}) == (
        selected_count
    )
    assert all(
        resource.source_kind is UserCopySourceKind.PLUGIN_COMPONENT
        for resource in skills
    )


def test_profile_digest_is_independent_of_absolute_package_root(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    for root in (left, right):
        _write(root / ".codex-plugin" / "plugin.json", '{"name":"demo"}')
        _write(root / "AGENTS.md", "# Same\n")
        _write(root / "skills" / "review" / "SKILL.md", "# Same\n")

    assert (
        resolve_user_copy_profile("codex-native", left).profile_digest
        == resolve_user_copy_profile("codex-native", right).profile_digest
    )


def test_codex_readme_and_starter_prompt_are_not_instructions_or_prompt_files(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        '{"name":"demo","interface":{"defaultPrompt":["start here"]}}',
    )
    _write(tmp_path / "README.md", "# Readme\n")

    profile = resolve_user_copy_profile("codex-native", tmp_path)

    assert profile.resources == ()
    assert profile.compatible is False


def test_wrong_extensions_and_unsupported_components_are_explicitly_blocked(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        '{"name":"demo","apps":["./apps/demo.app"]}',
    )
    _write(tmp_path / "AGENTS.md", "# Instructions\n")
    _write(tmp_path / "agents" / "reviewer.md", "# Wrong\n")
    _write(tmp_path / "prompts" / "review.txt", "Wrong\n")
    _write(tmp_path / "rules" / "nested" / "safe.rules", "allow\n")
    _write(tmp_path / "requirements.toml", "[policy]\n")
    _write(tmp_path / "apps" / "demo.app", "{}")

    profile = resolve_user_copy_profile("codex-native", tmp_path)

    assert profile.compatible is False
    assert {resource.reason for resource in profile.blocked_resources} == {
        UserCopyBlockReason.FORMAT_UNSUPPORTED,
        UserCopyBlockReason.SOURCE_NOT_ALLOWED,
        UserCopyBlockReason.UNSUPPORTED_RESOURCE,
    }
    assert {resource.source_locator for resource in profile.blocked_resources} >= {
        "agents/reviewer.md",
        "prompts/review.txt",
        "rules/nested/safe.rules",
        "requirements.toml",
        "apps",
    }


def test_claude_default_lsp_document_blocks_user_copy_profile(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "CLAUDE.md", "# Instructions\n")
    _write(
        tmp_path / ".lsp.json",
        '{"python":{"command":"pyright"}}',
    )

    profile = resolve_user_copy_profile("claude-native", tmp_path)

    assert profile.compatible is False
    assert any(
        resource.resource_type == "lsp"
        and resource.source_locator == ".lsp.json"
        and resource.reason is UserCopyBlockReason.UNSUPPORTED_RESOURCE
        for resource in profile.blocked_resources
    )


def test_profile_blocks_symlink_escape(tmp_path: Path) -> None:
    package = tmp_path / "package"
    _write(package / ".claude-plugin" / "plugin.json", '{"name":"demo"}')
    _write(package / "CLAUDE.md", "# Instructions\n")
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    agents = package / "agents"
    agents.mkdir()
    os.symlink("../../outside.md", agents / "escape.md")

    profile = resolve_user_copy_profile("claude-native", package)

    assert profile.compatible is False
    assert profile.resources == ()
    assert any(
        resource.reason is UserCopyBlockReason.SOURCE_REFERENCE_INVALID
        for resource in profile.blocked_resources
    )


def test_source_allowlist_is_target_client_specific() -> None:
    codex_patterns = {
        rule.source_pattern for rule in user_copy_source_allowlist("codex-native")
    }
    claude_patterns = {
        rule.source_pattern for rule in user_copy_source_allowlist("claude-native")
    }

    assert "AGENTS.md" in codex_patterns
    assert "prompts/**/*.md" in codex_patterns
    assert "CLAUDE.md" in claude_patterns
    assert "commands/**/*.md" in claude_patterns


def test_target_resource_is_typed_and_serializes_to_contract_value(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "AGENTS.md", "# Instructions\n")

    profile = resolve_user_copy_profile("codex-native", tmp_path)
    resource = profile.resources[0]

    assert resource.target_resource is UserCopyTargetResource.AGENTS_MD
    assert resource.canonical_dict()["targetResource"] == "agents_md"
    assert profile.canonical_dict()["profileVersion"] == 1


def test_user_copy_resource_rejects_untyped_target_at_runtime() -> None:
    with pytest.raises(TypeError, match="target_resource"):
        UserCopyResource(
            resource_type=UserCopyResourceType.INSTRUCTIONS,
            resource_id="root-instructions",
            source_kind=UserCopySourceKind.COPY_CONVENTION,
            source_locator="AGENTS.md",
            target_resource="agents_md",  # type: ignore[arg-type]
            copy_semantics=UserCopySemantics.CREATE_FILE,
        )


def test_target_resource_enum_is_closed_to_shared_user_scope_targets() -> None:
    assert {target.value for target in UserCopyTargetResource} == {
        "agents_md",
        "claude_md",
        "skills",
        "subagents",
        "commands",
        "output_styles",
        "prompts",
        "rules",
        "mcp",
        "hooks",
    }


def test_copy_convention_extensions_are_case_sensitive(tmp_path: Path) -> None:
    _write(tmp_path / "AGENTS.md", "# Instructions\n")
    _write(tmp_path / "agents" / "reviewer.TOML", 'name = "reviewer"\n')
    _write(tmp_path / "prompts" / "review.MD", "# Review\n")
    _write(tmp_path / "rules" / "safe.RULES", "allow\n")

    profile = resolve_user_copy_profile("codex-native", tmp_path)

    assert profile.compatible is False
    assert {resource.source_locator for resource in profile.blocked_resources} == {
        "agents/reviewer.TOML",
        "prompts/review.MD",
        "rules/safe.RULES",
    }


def test_profile_preview_contains_sanitized_shared_source_proofs(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        """
        {
          "name": "demo",
          "mcpServers": {
            "local": {
              "command": "${CODEX_PLUGIN_ROOT}/bin/server.js"
            }
          },
          "hooks": {"SessionStart": [{"command": "echo ready"}]}
        }
        """,
    )
    _write(tmp_path / "bin" / "server.js", "console.log('ready')\n")
    _write(tmp_path / "AGENTS.md", "# Instructions\n")
    _write(tmp_path / "skills" / "review" / "SKILL.md", "# Review\n")

    profile = resolve_user_copy_profile("codex-native", tmp_path)
    preview = build_user_copy_profile_preview(tmp_path, profile)

    assert preview["profileDigest"] == profile.profile_digest
    assert preview["profileVersion"] == 1
    by_type = {
        (resource["resourceType"], resource["resourceId"]): resource
        for resource in preview["resources"]
    }
    instructions = by_type[("instructions", "root-instructions")]
    assert instructions["sourceDigest"] == sha256(b"# Instructions\n").hexdigest()
    assert instructions["dependencyPayloadRequired"] is False
    assert by_type[("mcp", "local")]["dependencyPayloadRequired"] is True
    assert (
        by_type[("hook", ".codex-plugin/plugin.json#/hooks/SessionStart/0")][
            "dependencyPayloadRequired"
        ]
        is False
    )
    assert all(
        len(resource["sourceDigest"]) == 64
        and type(resource["dependencyPayloadRequired"]) is bool
        for resource in preview["resources"]
    )
    assert "console.log" not in str(preview)
    assert "${CODEX_PLUGIN_ROOT}" not in str(preview)


def test_profile_preview_directory_digest_is_root_independent(
    tmp_path: Path,
) -> None:
    previews = []
    for name in ("left", "right"):
        root = tmp_path / name
        _write(root / "skills" / "review" / "SKILL.md", "# Review\n")
        _write(root / "skills" / "review" / "scripts" / "run.sh", "echo ok\n")
        profile = resolve_user_copy_profile("codex-native", root)
        previews.append(build_user_copy_profile_preview(root, profile))

    assert (
        previews[0]["resources"][0]["sourceDigest"]
        == previews[1]["resources"][0]["sourceDigest"]
    )


def test_profile_preview_rejects_stale_profile(tmp_path: Path) -> None:
    _write(tmp_path / "AGENTS.md", "# Instructions\n")
    profile = resolve_user_copy_profile("codex-native", tmp_path)
    _write(tmp_path / "prompts" / "review.md", "# Review\n")

    with pytest.raises(PackageSourceError, match="source-profile-mismatch"):
        build_user_copy_profile_preview(tmp_path, profile)


def test_profile_preview_marks_missing_dependency_payload_unprojectable(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".claude-plugin" / "plugin.json",
        """
        {
          "name": "demo",
          "mcpServers": {
            "local": {
              "command": "${CLAUDE_PLUGIN_ROOT}/missing/server.js"
            }
          }
        }
        """,
    )
    profile = resolve_user_copy_profile("claude-native", tmp_path)

    preview = build_user_copy_profile_preview(tmp_path, profile)
    resource = preview["resources"][0]

    assert resource["dependencyPayloadRequired"] is True
    assert resource["dependencyPayloadProjectable"] is False
    assert preview["dependencyPayloads"] == []


def test_directory_dependency_payload_covers_all_referenced_descendants(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        """
        {
          "name": "demo",
          "mcpServers": {
            "local": {
              "command": "${CODEX_PLUGIN_ROOT}/bin",
              "args": ["${CODEX_PLUGIN_ROOT}/bin/server.js"]
            }
          }
        }
        """,
    )
    _write(tmp_path / "bin" / "server.js", "console.log('ready')\n")
    profile = resolve_user_copy_profile("codex-native", tmp_path)

    preview = build_user_copy_profile_preview(tmp_path, profile)

    assert preview["dependencyPayloads"] == [
        {
            "sourceLocator": "bin",
            "sourceKind": "directory",
            "contentDigest": preview["dependencyPayloads"][0][
                "contentDigest"
            ],
        }
    ]
    assert len(user_copy_source_digest_from_preview(preview)) == 64


def test_source_digest_rejects_unreferenced_canonical_payload(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / ".codex-plugin" / "plugin.json",
        """
        {
          "name": "demo",
          "mcpServers": {
            "local": {
              "command": "${CODEX_PLUGIN_ROOT}/bin/server.js"
            }
          }
        }
        """,
    )
    _write(tmp_path / "bin" / "server.js", "console.log('ready')\n")
    profile = resolve_user_copy_profile("codex-native", tmp_path)
    preview = build_user_copy_profile_preview(tmp_path, profile)
    preview["dependencyPayloads"].append(
        {
            "sourceLocator": "unused",
            "sourceKind": "file",
            "contentDigest": "0" * 64,
        }
    )

    with pytest.raises(PackageSourceError, match="source-profile-mismatch"):
        user_copy_source_digest_from_preview(preview)
