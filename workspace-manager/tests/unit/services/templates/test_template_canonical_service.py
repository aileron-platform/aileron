"""Template canonical filesystem service tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.template_canonical_service import (
    CanonicalTemplateValidationError,
    TemplateCanonicalService,
)


@pytest.fixture
def canonical_service(tmp_path):
    with patch("app.services.template_base_service.get_settings") as mock_settings:
        mock_settings.return_value.TEMPLATE_STORAGE_PATH = str(tmp_path)
        service = TemplateCanonicalService(MagicMock())
        service.storage_path = tmp_path
        return service


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_load_from_root_reads_default_canonical_structure(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
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
            ]
        ),
    )
    _write(template_root / "agents.md", "# Rules\n")
    _write(
        template_root / "output-style.yaml",
        "id: concise\nverbosity: low\nfallbackInstruction: Keep it short.\n",
    )
    _write(
        template_root / "skills" / "audit" / "SKILL.md",
        "---\nname: audit\ndescription: Audit skill\n---\nUse this skill.\n",
    )
    _write(
        template_root / "commands" / "review-ui.md",
        "---\nname: review-ui\n---\nReview current UI changes.\n",
    )
    _write(
        template_root / "agents" / "ui-investigator.md",
        "---\nname: ui-investigator\nmode: subagent\n---\nInvestigate UI changes.\n",
    )
    _write(
        template_root / "hooks" / "pre-tool-use.yaml",
        "id: pre-tool-use\nevent: PreToolUse\nmatcher:\n  tool: shell\naction:\n  type: command\n",
    )
    _write(
        template_root / "mcp" / "context7.yaml",
        "id: context7\ntransport: stdio\ncommand: npx\nargs:\n  - -y\n",
    )
    _write(template_root / "resources" / "examples" / "sample.md", "example\n")

    result = canonical_service.load_from_root(template_root)

    assert result.index.id == "demo-template"
    assert result.agents_md_content == "# Rules\n"
    assert result.output_style is not None
    assert result.output_style.fallback_instruction == "Keep it short."
    assert [skill.id for skill in result.skills] == ["audit"]
    assert [command.name for command in result.commands] == ["review-ui"]
    assert [agent.name for agent in result.agents] == ["ui-investigator"]
    assert [hook.id for hook in result.hooks] == ["pre-tool-use"]
    assert [server.id for server in result.mcp_servers] == ["context7"]
    assert result.resources[0].type == "directory"


@pytest.mark.unit
def test_validate_root_rejects_template_id_mismatch(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    _write(
        template_root / "template.yaml",
        "id: other-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n",
    )

    with pytest.raises(CanonicalTemplateValidationError, match="does not match root directory"):
        canonical_service.load_from_root(template_root)


@pytest.mark.unit
def test_validate_root_rejects_path_escape(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    _write(
        template_root / "template.yaml",
        "\n".join(
            [
                "id: demo-template",
                "name: Demo",
                "version: 1.0.0",
                "schemaVersion: v0",
                "features:",
                "  commands:",
                "    path: ../outside",
            ]
        ),
    )

    with pytest.raises(CanonicalTemplateValidationError, match="escapes template root"):
        canonical_service.load_from_root(template_root)


@pytest.mark.unit
def test_load_from_template_id_uses_existing_template_storage(canonical_service, tmp_path):
    template_root = tmp_path / "templates" / "demo-template"
    _write(
        template_root / "template.yaml",
        "id: demo-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n",
    )

    result = canonical_service.load_from_template_id("demo-template")

    assert result.index.id == "demo-template"
    assert result.root_path.endswith("templates/demo-template")


@pytest.mark.unit
def test_load_from_template_id_prefers_registry_templates_dir(canonical_service, tmp_path):
    template_root = tmp_path / "templates" / "demo-template"
    _write(
        template_root / "template.yaml",
        "id: demo-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n",
    )

    result = canonical_service.load_from_template_id("demo-template")

    assert result.index.id == "demo-template"
    assert result.root_path.endswith("templates/demo-template")


@pytest.mark.unit
def test_invalid_frontmatter_is_rejected(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    _write(
        template_root / "template.yaml",
        "id: demo-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n",
    )
    _write(
        template_root / "commands" / "broken.md",
        "---\n- invalid\n---\ncontent\n",
    )

    with pytest.raises(CanonicalTemplateValidationError, match="frontmatter"):
        canonical_service.load_from_root(template_root)


@pytest.mark.unit
def test_missing_template_yaml_is_rejected(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    template_root.mkdir(parents=True)

    with pytest.raises(CanonicalTemplateValidationError, match="Missing template.yaml"):
        canonical_service.load_from_root(template_root)


@pytest.mark.unit
def test_invalid_template_yaml_is_rejected(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    _write(template_root / "template.yaml", "id: demo-template\nname: [broken\n")

    with pytest.raises(CanonicalTemplateValidationError, match="Invalid YAML"):
        canonical_service.load_from_root(template_root)


@pytest.mark.unit
def test_hook_missing_event_is_rejected(canonical_service, tmp_path):
    template_root = tmp_path / "demo-template"
    _write(
        template_root / "template.yaml",
        "id: demo-template\nname: Demo\nversion: 1.0.0\nschemaVersion: v0\n",
    )
    _write(
        template_root / "hooks" / "broken.yaml",
        "id: broken-hook\nmatcher:\n  tool: shell\n",
    )

    with pytest.raises(CanonicalTemplateValidationError, match="missing event"):
        canonical_service.load_from_root(template_root)
