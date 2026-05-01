"""Snapshot tests for the kb-wiki-index skill structure."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# The skill lives in workspace-runtime which may not be mounted in the test container.
# Resolve from the source tree root when available; skip gracefully otherwise.
_CANDIDATES = [
    Path(__file__).parent.parent.parent.parent.parent
    / "workspace-runtime"
    / "agent-defaults"
    / "skills"
    / "kb-wiki-index",
    Path("/workspace-runtime/agent-defaults/skills/kb-wiki-index"),
    Path(os.environ.get("WORKSPACE_RUNTIME_ROOT", "/nonexistent"))
    / "agent-defaults/skills/kb-wiki-index",
]

SKILL_ROOT = next((p for p in _CANDIDATES if (p / "SKILL.md").is_file()), _CANDIDATES[0])
_SKILL_AVAILABLE = (SKILL_ROOT / "SKILL.md").is_file()
skip_no_skill = pytest.mark.skipif(not _SKILL_AVAILABLE, reason="kb-wiki-index skill not accessible in this environment")


@pytest.mark.unit
@skip_no_skill
def test_skill_md_exists():
    assert (SKILL_ROOT / "SKILL.md").is_file()


@pytest.mark.unit
@skip_no_skill
def test_skill_md_has_name_and_description():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "name: kb-wiki-index" in content
    assert "description:" in content


@pytest.mark.unit
@skip_no_skill
def test_skill_md_references_stage1():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "stage1-analysis.md" in content


@pytest.mark.unit
@skip_no_skill
def test_skill_md_references_stage2():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "stage2-generation.md" in content


@pytest.mark.unit
@skip_no_skill
def test_skill_md_references_review_blocks():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "review-blocks.md" in content


@pytest.mark.unit
@skip_no_skill
def test_skill_md_defines_output_contract():
    content = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    assert "Output Contract" in content
    assert "Use Write or Edit" in content
    assert "Do not output `---FILE:---` blocks as the final result" in content


@pytest.mark.unit
@skip_no_skill
def test_all_reference_files_exist():
    required = [
        "references/stage1-analysis.md",
        "references/stage2-generation.md",
        "references/safe-paths.md",
        "references/frontmatter.md",
        "references/review-blocks.md",
    ]
    for rel in required:
        assert (SKILL_ROOT / rel).is_file(), f"Missing: {rel}"


@pytest.mark.unit
@skip_no_skill
def test_stage2_generation_requires_file_writes():
    content = (SKILL_ROOT / "references/stage2-generation.md").read_text(encoding="utf-8")
    assert "Use Write or Edit" in content
    assert "Only print generated pages without writing them" in content
    assert "Emit `---FILE:---` blocks as the final result" in content


@pytest.mark.unit
def test_automation_service_uses_skill_prompt():
    from unittest.mock import MagicMock
    from app.services.automation_service import AutomationService

    svc = AutomationService.__new__(AutomationService)
    svc.db = MagicMock()
    prompt = svc.build_knowledge_base_wiki_index_prompt(mount_alias="my-kb")
    assert "kb-wiki-index" in prompt
    assert "my-kb" in prompt
    assert len(prompt) < 200
