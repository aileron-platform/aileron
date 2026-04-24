from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.template_canonical import CanonicalTarget
from app.services.template_compiler_service import TemplateCompilerService
from app.services.template_import_service import (
    TemplateImportError,
    TemplateImportService,
    TemplateMigrationService,
)


@pytest.fixture
def import_service(mock_db_session):
    from unittest.mock import patch

    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = "/tmp/template-import-tests"
        yield TemplateImportService(mock_db_session)


@pytest.fixture
def migration_service(mock_db_session):
    from unittest.mock import patch

    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = "/tmp/template-import-tests"
        yield TemplateMigrationService(mock_db_session)


@pytest.mark.unit
def test_import_claude_template_to_intermediate_model(import_service, tmp_path):
    source_root = tmp_path / "claude-template"
    (source_root / ".claude-plugin").mkdir(parents=True)
    (source_root / "commands").mkdir()
    (source_root / "agents").mkdir()
    (source_root / "skills" / "review-ui").mkdir(parents=True)
    (source_root / "hooks" / "scripts").mkdir(parents=True)

    (source_root / ".claude-plugin" / "manifest.json").write_text(
        json.dumps(
            {
                "id": "frontend-review",
                "name": "Frontend Review",
                "description": "Review UI changes",
                "version": "1.2.3",
                "author": {"name": "Team"},
                "keywords": ["ui", "review"],
            }
        ),
        encoding="utf-8",
    )
    (source_root / "CLAUDE.md").write_text("# Claude rules", encoding="utf-8")
    (source_root / "commands" / "review-ui.md").write_text(
        "---\nname: review-ui\ndescription: Review UI\n---\nDo review",
        encoding="utf-8",
    )
    (source_root / "agents" / "ui-investigator.md").write_text(
        "---\nname: ui-investigator\nmode: subagent\n---\nInvestigate UI",
        encoding="utf-8",
    )
    (source_root / "skills" / "review-ui" / "SKILL.md").write_text(
        "---\nname: review-ui\n---\nUse this skill",
        encoding="utf-8",
    )
    (source_root / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "@upstash/context7-mcp"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (source_root / "hooks" / "scripts" / "validate.sh").write_text("echo ok", encoding="utf-8")
    (source_root / "hooks" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": {"tool": "shell"},
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "./hooks/scripts/validate.sh",
                                    "path": "scripts/validate.sh",
                                }
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    imported = import_service.import_from_root(source_root)

    assert imported.metadata.id == "frontend-review"
    assert imported.metadata.source_type == "claude-code"
    assert imported.agents_md_content == "# Claude rules"
    assert imported.commands[0].name == "review-ui"
    assert imported.agents[0].frontmatter["mode"] == "subagent"
    assert imported.skills[0].id == "review-ui"
    assert imported.mcp_servers[0].id == "context7"
    assert imported.hooks[0].event == "PreToolUse"


@pytest.mark.unit
def test_import_claude_template_rejects_legacy_marketplace_json_only(import_service, tmp_path):
    source_root = tmp_path / "claude-template"
    (source_root / ".claude-plugin").mkdir(parents=True)
    (source_root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"id": "legacy-template"}),
        encoding="utf-8",
    )

    with pytest.raises(TemplateImportError, match="missing_template_package_manifest"):
        import_service.import_from_root(source_root)


@pytest.mark.unit
def test_import_claude_template_prefers_manifest_json_when_legacy_file_also_exists(
    import_service, tmp_path
):
    source_root = tmp_path / "claude-template"
    (source_root / ".claude-plugin").mkdir(parents=True)
    (source_root / ".claude-plugin" / "manifest.json").write_text(
        json.dumps({"id": "manifest-template", "name": "Manifest Template"}),
        encoding="utf-8",
    )
    (source_root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"id": "legacy-template", "name": "Legacy Template"}),
        encoding="utf-8",
    )

    imported = import_service.import_from_root(source_root)

    assert imported.metadata.id == "manifest-template"
    assert imported.metadata.name == "Manifest Template"


@pytest.mark.unit
def test_import_gemini_template_parses_settings_and_commands(import_service, tmp_path):
    source_root = tmp_path / "gemini-template"
    (source_root / ".gemini" / "commands").mkdir(parents=True)
    (source_root / ".gemini" / "agents").mkdir(parents=True)
    (source_root / ".gemini" / "skills" / "debugger").mkdir(parents=True)

    (source_root / "GEMINI.md").write_text("# Gemini rules", encoding="utf-8")
    (source_root / ".gemini" / "commands" / "review.toml").write_text(
        'name = "review"\ndescription = "Review changes"\n\n[prompt]\ntemplate = """Check changes"""\n',
        encoding="utf-8",
    )
    (source_root / ".gemini" / "agents" / "perf.md").write_text(
        "---\nname: perf\nmode: subagent\n---\nPerf agent",
        encoding="utf-8",
    )
    (source_root / ".gemini" / "skills" / "debugger" / "SKILL.md").write_text(
        "# Debugger",
        encoding="utf-8",
    )
    (source_root / ".gemini" / "settings.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {
                        "command": "npx",
                        "args": ["-y", "@upstash/context7-mcp"],
                    }
                },
                "hooks": [
                    {"event": "SessionStart", "command": "./bootstrap.sh"},
                ],
                "output": {"format": "json"},
            }
        ),
        encoding="utf-8",
    )

    imported = import_service.import_from_root(source_root)

    assert imported.metadata.source_type == "gemini"
    assert imported.agents_md_content == "# Gemini rules"
    assert imported.commands[0].name == "review"
    assert imported.commands[0].content == "Check changes"
    assert imported.mcp_servers[0].command == "npx"
    assert imported.hooks[0].event == "SessionStart"
    assert "gemini_output_settings_mapped_to_output_style" in imported.warnings


@pytest.mark.unit
def test_import_codex_template_parses_config_hooks_and_commands(import_service, tmp_path):
    source_root = tmp_path / "codex-template"
    (source_root / ".codex" / "commands").mkdir(parents=True)
    (source_root / ".codex" / "agents").mkdir(parents=True)
    (source_root / ".codex" / "skills" / "reviewer").mkdir(parents=True)

    (source_root / "AGENTS.md").write_text("# Codex rules", encoding="utf-8")
    (source_root / ".codex" / "commands" / "review.md").write_text(
        "---\nname: review\ndescription: Review changes\n---\nReview changes",
        encoding="utf-8",
    )
    (source_root / ".codex" / "agents" / "auditor.md").write_text(
        "---\nname: auditor\nmode: subagent\n---\nAudit code",
        encoding="utf-8",
    )
    (source_root / ".codex" / "skills" / "reviewer" / "SKILL.md").write_text(
        "---\nname: reviewer\n---\nUse this skill",
        encoding="utf-8",
    )
    (source_root / ".codex" / "config.toml").write_text(
        "\n".join(
            [
                "[mcp_servers.context7]",
                'command = "npx"',
                'args = ["-y", "@upstash/context7-mcp"]',
                "",
                "[hooks]",
                'config_path = ".codex/hooks.json"',
            ]
        ),
        encoding="utf-8",
    )
    (source_root / ".codex" / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "SessionStart": [
                        {
                            "matcher": {"workspace": ".*"},
                            "hooks": [{"type": "command", "command": "./bootstrap.sh"}],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    imported = import_service.import_from_root(source_root)

    assert imported.metadata.source_type == "codex"
    assert imported.agents_md_content == "# Codex rules"
    assert imported.commands[0].name == "review"
    assert imported.agents[0].name == "auditor"
    assert imported.skills[0].id == "reviewer"
    assert imported.mcp_servers[0].id == "context7"
    assert imported.hooks[0].event == "SessionStart"
    assert "codex_hooks_config_detected" in imported.warnings
    assert "codex_hooks_config_requires_manual_review" in imported.unresolved_items


@pytest.mark.unit
def test_import_opencode_template_collects_unresolved_items(import_service, tmp_path):
    source_root = tmp_path / "open-code"
    (source_root / ".opencode" / "commands").mkdir(parents=True)
    (source_root / ".opencode" / "agents").mkdir(parents=True)
    (source_root / ".opencode" / "skills" / "explore").mkdir(parents=True)

    (source_root / "AGENTS.md").write_text("# Agent rules", encoding="utf-8")
    (source_root / ".opencode" / "commands" / "review.md").write_text("# review", encoding="utf-8")
    (source_root / ".opencode" / "agents" / "explorer.md").write_text("# explorer", encoding="utf-8")
    (source_root / ".opencode" / "skills" / "explore" / "SKILL.md").write_text("# skill", encoding="utf-8")
    (source_root / "opencode.json").write_text(
        json.dumps(
            {
                "commands": {"inline-review": {"description": "inline"}},
                "agents": {"explore": {"mode": "subagent"}},
                "mcp": {"servers": {"context7": {"command": "npx"}}},
            }
        ),
        encoding="utf-8",
    )

    imported = import_service.import_from_root(source_root)

    assert imported.metadata.source_type == "opencode"
    assert imported.mcp_servers[0].id == "context7"
    assert "opencode_inline_commands_require_manual_review" in imported.unresolved_items
    assert "opencode_inline_agents_require_manual_review" in imported.unresolved_items


@pytest.mark.unit
def test_normalizer_writes_canonical_template_tree(import_service, tmp_path):
    source_root = tmp_path / "codex-template"
    (source_root / ".codex" / "commands").mkdir(parents=True)
    (source_root / ".codex" / "agents").mkdir(parents=True)
    (source_root / ".codex" / "skills" / "review").mkdir(parents=True)

    (source_root / "AGENTS.md").write_text("# AGENTS", encoding="utf-8")
    (source_root / ".codex" / "commands" / "review.md").write_text(
        "---\nname: review\n---\nReview changes",
        encoding="utf-8",
    )
    (source_root / ".codex" / "agents" / "reviewer.md").write_text("# reviewer", encoding="utf-8")
    (source_root / ".codex" / "skills" / "review" / "SKILL.md").write_text("# skill", encoding="utf-8")

    imported = import_service.import_from_root(source_root)
    target_root = tmp_path / "canonical" / imported.metadata.id
    import_service.normalizer.write_template(imported, target_root)

    assert (target_root / "template.yaml").exists()
    assert (target_root / "agents.md").read_text(encoding="utf-8") == "# AGENTS"
    assert (target_root / "commands" / "review.md").exists()
    assert (target_root / "agents" / "reviewer.md").exists()
    assert (target_root / "skills" / "review" / "SKILL.md").exists()


@pytest.mark.unit
def test_migration_service_migrates_multiple_source_directories(migration_service, tmp_path):
    source_root = tmp_path / "legacy"
    destination_root = tmp_path / "registry"
    source_root.mkdir()

    first = source_root / "first-template"
    first.mkdir()
    (first / "AGENTS.md").write_text("# First", encoding="utf-8")

    second = source_root / "second-template"
    second.mkdir()
    (second / "GEMINI.md").write_text("# Second", encoding="utf-8")
    (second / ".gemini").mkdir()

    migrated = migration_service.migrate_directory(source_root, destination_root)

    assert len(migrated) == 2
    assert (destination_root / "first-template" / "template.yaml").exists()
    assert (destination_root / "second-template" / "template.yaml").exists()


def _build_claude_source(root: Path) -> tuple[CanonicalTarget, str]:
    (root / ".claude-plugin").mkdir(parents=True)
    (root / "commands").mkdir()
    (root / "agents").mkdir()
    (root / "skills" / "review-ui").mkdir(parents=True)
    (root / ".claude-plugin" / "manifest.json").write_text(
        json.dumps(
            {
                "id": "frontend-review",
                "name": "Frontend Review",
                "version": "1.0.0",
            }
        ),
        encoding="utf-8",
    )
    (root / "CLAUDE.md").write_text("# Claude rules", encoding="utf-8")
    (root / "commands" / "review-ui.md").write_text(
        "---\nname: review-ui\n---\nReview UI",
        encoding="utf-8",
    )
    (root / "agents" / "ui-agent.md").write_text(
        "---\nname: ui-agent\nmode: subagent\n---\nAgent",
        encoding="utf-8",
    )
    (root / "skills" / "review-ui" / "SKILL.md").write_text("# Skill", encoding="utf-8")
    return CanonicalTarget.CLAUDE_CODE, "CLAUDE.md"


def _build_codex_source(root: Path) -> tuple[CanonicalTarget, str]:
    (root / ".codex" / "commands").mkdir(parents=True)
    (root / ".codex" / "agents").mkdir(parents=True)
    (root / ".codex" / "skills" / "review").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# Codex rules", encoding="utf-8")
    (root / ".codex" / "commands" / "review.md").write_text(
        "---\nname: review\n---\nReview changes",
        encoding="utf-8",
    )
    (root / ".codex" / "agents" / "reviewer.md").write_text("# reviewer", encoding="utf-8")
    (root / ".codex" / "skills" / "review" / "SKILL.md").write_text("# skill", encoding="utf-8")
    (root / ".codex" / "config.toml").write_text(
        "\n".join(
            [
                "[mcp_servers.context7]",
                'command = "npx"',
                'args = ["-y", "@upstash/context7-mcp"]',
            ]
        ),
        encoding="utf-8",
    )
    return CanonicalTarget.CODEX, "AGENTS.md"


def _build_gemini_source(root: Path) -> tuple[CanonicalTarget, str]:
    (root / ".gemini" / "commands").mkdir(parents=True)
    (root / ".gemini" / "agents").mkdir(parents=True)
    (root / ".gemini" / "skills" / "debugger").mkdir(parents=True)
    (root / "GEMINI.md").write_text("# Gemini rules", encoding="utf-8")
    (root / ".gemini" / "commands" / "review.toml").write_text(
        'name = "review"\ndescription = "Review changes"\n\n[prompt]\ntemplate = """Check changes"""\n',
        encoding="utf-8",
    )
    (root / ".gemini" / "agents" / "perf.md").write_text("# perf", encoding="utf-8")
    (root / ".gemini" / "skills" / "debugger" / "SKILL.md").write_text("# Debugger", encoding="utf-8")
    (root / ".gemini" / "settings.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "context7": {
                        "command": "npx",
                        "args": ["-y", "@upstash/context7-mcp"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return CanonicalTarget.GEMINI, "GEMINI.md"


def _build_opencode_source(root: Path) -> tuple[CanonicalTarget, str]:
    (root / ".opencode" / "commands").mkdir(parents=True)
    (root / ".opencode" / "agents").mkdir(parents=True)
    (root / ".opencode" / "skills" / "explore").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# OpenCode rules", encoding="utf-8")
    (root / ".opencode" / "commands" / "review.md").write_text("# review", encoding="utf-8")
    (root / ".opencode" / "agents" / "explorer.md").write_text("# explorer", encoding="utf-8")
    (root / ".opencode" / "skills" / "explore" / "SKILL.md").write_text("# skill", encoding="utf-8")
    (root / "opencode.json").write_text(
        json.dumps(
            {
                "mcp": {"servers": {"context7": {"command": "npx"}}},
            }
        ),
        encoding="utf-8",
    )
    return CanonicalTarget.OPENCODE, "AGENTS.md"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("builder", "source_name"),
    [
        (_build_claude_source, "claude"),
        (_build_codex_source, "codex"),
        (_build_gemini_source, "gemini"),
        (_build_opencode_source, "opencode"),
    ],
)
def test_imported_sources_can_normalize_to_canonical_tree_and_compile(builder, source_name, tmp_path):
    storage_root = tmp_path / "template-storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    source_root = tmp_path / f"{source_name}-source"
    source_root.mkdir(parents=True, exist_ok=True)
    target, expected_file = builder(source_root)

    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(storage_root)
        import_service = TemplateImportService(MagicMock())
        compiler_service = TemplateCompilerService(MagicMock())

        imported = import_service.import_from_root(source_root)
        canonical_root = storage_root / "templates" / imported.metadata.id
        import_service.normalizer.write_template(imported, canonical_root)
        plan = compiler_service.compile_template(imported.metadata.id, target.value)

    assert (canonical_root / "template.yaml").exists()
    assert (canonical_root / "agents.md").exists()
    assert any(file.path == expected_file for file in plan.files)
    assert len(plan.files) >= 1
