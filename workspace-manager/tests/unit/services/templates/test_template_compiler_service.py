"""Template compiler service tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.template_canonical import CanonicalTarget
from app.services.template_compiler_service import TemplateCompilerService


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def compiler_service(tmp_path):
    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateCompilerService(MagicMock())
        service.canonical_service.storage_path = tmp_path
        return service


def _seed_canonical_template(tmp_path: Path) -> None:
    template_root = tmp_path / "templates" / "demo-template"
    _write(
        template_root / "template.yaml",
        "\n".join(
            [
                "id: demo-template",
                "name: Demo Template",
                "version: 1.0.0",
                "schemaVersion: v0",
                "supportedTargets:",
                "  - claude-code",
                "  - codex",
                "  - gemini",
                "  - opencode",
            ]
        ),
    )
    _write(template_root / "agents.md", "# Canonical rules\n")
    _write(
        template_root / "commands" / "review-ui.md",
        "---\nname: review-ui\ndescription: Review UI changes\n---\nReview UI changes.\n",
    )
    _write(
        template_root / "agents" / "ui-investigator.md",
        "---\nname: ui-investigator\nmode: subagent\n---\nInvestigate UI.\n",
    )
    _write(
        template_root / "output-style.yaml",
        "id: concise\nfallbackInstruction: Keep responses concise.\n",
    )


@pytest.mark.unit
def test_compile_claude_template_generates_expected_paths(compiler_service, tmp_path):
    _seed_canonical_template(tmp_path)

    plan = compiler_service.compile_template("demo-template", CanonicalTarget.CLAUDE_CODE.value)

    assert plan.target == CanonicalTarget.CLAUDE_CODE.value
    assert [item.path for item in plan.files][:3] == [
        "CLAUDE.md",
        ".claude/commands/review-ui.md",
        ".claude/agents/user/ui-investigator.md",
    ]
    assert plan.install_hints["agentsMdContent"] == "# Canonical rules\n"


@pytest.mark.unit
def test_compile_gemini_template_generates_gemini_specific_files(compiler_service, tmp_path):
    _seed_canonical_template(tmp_path)

    plan = compiler_service.compile_template("demo-template", CanonicalTarget.GEMINI.value)

    assert any(item.path == "GEMINI.md" for item in plan.files)
    assert any(item.path == ".gemini/commands/review-ui.toml" for item in plan.files)
    assert any(issue.feature == "outputStyle" for issue in plan.degradation_notes)


@pytest.mark.unit
def test_compile_codex_template_generates_codex_specific_files(compiler_service, tmp_path):
    _seed_canonical_template(tmp_path)

    plan = compiler_service.compile_template("demo-template", CanonicalTarget.CODEX.value)

    assert plan.target == CanonicalTarget.CODEX.value
    assert [item.path for item in plan.files][:3] == [
        "AGENTS.md",
        ".codex/commands/review-ui.md",
        ".codex/agents/ui-investigator.md",
    ]
    assert any(issue.feature == "outputStyle" for issue in plan.warnings)
    assert plan.install_hints["commands"][0]["fileName"] == "review-ui.md"


@pytest.mark.unit
def test_compile_opencode_template_generates_opencode_specific_files(compiler_service, tmp_path):
    _seed_canonical_template(tmp_path)

    plan = compiler_service.compile_template("demo-template", CanonicalTarget.OPENCODE.value)

    assert plan.target == CanonicalTarget.OPENCODE.value
    assert [item.path for item in plan.files][:3] == [
        "AGENTS.md",
        ".opencode/commands/review-ui.md",
        ".opencode/agents/ui-investigator.md",
    ]
    assert any(issue.feature == "outputStyle" for issue in plan.degradation_notes)


@pytest.mark.unit
def test_compile_template_uses_cache_for_same_source_hash(compiler_service, tmp_path):
    _seed_canonical_template(tmp_path)

    first_plan = compiler_service.compile_template("demo-template", CanonicalTarget.CLAUDE_CODE.value)
    cached_plan = compiler_service.compile_template("demo-template", CanonicalTarget.CLAUDE_CODE.value)

    assert first_plan.source_hash is not None
    assert cached_plan.source_hash == first_plan.source_hash
    assert cached_plan.cache_key == first_plan.cache_key
