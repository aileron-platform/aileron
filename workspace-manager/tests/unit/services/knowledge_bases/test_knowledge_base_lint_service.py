"""Knowledge base lint service unit tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.services.knowledge_base_lint_service import KnowledgeBaseLintService


@pytest.fixture
def mock_db_session():
    session = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        description=None,
        current_size_bytes=0,
        quota_bytes=None,
        version_control_enabled=False,
    )


@pytest.fixture
def lint_service(mock_db_session, kb, tmp_path):
    with patch("app.services.knowledge_base_lint_service.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        service = KnowledgeBaseLintService(mock_db_session)
    service.storage_root = tmp_path
    service.wiki_service.storage_root = tmp_path
    access = type("Access", (), {"access_role": "editor"})()
    service.kb_service.get_kb = MagicMock(return_value=(kb, access))
    return service


def _write_file(lint_service: KnowledgeBaseLintService, kb_id: str, path: str, content: str) -> None:
    target = lint_service.storage_root / kb_id / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_structural_lint_reports_all_issue_types_and_persists_report(lint_service):
    _write_file(lint_service, "kb-1", "raw/sources/existing.md", "# Source\n")
    _write_file(
        lint_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index

See [[concepts/python]] and [[missing/page]].
""",
    )
    _write_file(
        lint_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources:
  - raw/sources/missing.md
---

# Python
""",
    )
    _write_file(
        lint_service,
        "kb-1",
        "wiki/entities/python.md",
        """---
title: Python
type: entity
sources:
  - raw/sources/existing.md
---

# Python entity
""",
    )
    _write_file(
        lint_service,
        "kb-1",
        "wiki/notes/no-frontmatter.md",
        "# Missing Frontmatter\n",
    )

    report = lint_service.run_structural_lint(user_id="owner-1", kb_id="kb-1")

    issue_types = {issue.issue_type for issue in report.issues}
    assert issue_types >= {
        "broken_wikilink",
        "orphan_page",
        "no_outbound_links",
        "missing_frontmatter",
        "missing_source",
        "duplicate_title",
        "duplicate_slug",
    }
    assert report.issue_counts["broken_wikilink"] == 1
    assert report.report_path.startswith("/reports/lint/lint-")
    payload = json.loads((lint_service.storage_root / "kb-1" / report.report_path.lstrip("/")).read_text(encoding="utf-8"))
    assert payload["kbId"] == "kb-1"
    assert payload["issueCounts"]["missing_source"] == 1
    assert any(issue["details"].get("target") == "missing/page" for issue in payload["issues"])
    lint_service.kb_service.get_kb.assert_called_with(user_id="owner-1", kb_id="kb-1", minimum_role="editor")


@pytest.mark.unit
def test_structural_lint_commits_report_when_git_enabled(lint_service, kb):
    kb.version_control_enabled = True
    lint_service.git_service = MagicMock()
    lint_service.git_service.commit.return_value = type(
        "CommitResponse",
        (),
        {"commit": type("Commit", (), {"id": "commit-123"})()},
    )()

    report = lint_service.run_structural_lint(user_id="owner-1", kb_id="kb-1")

    assert report.commit_id == "commit-123"
    lint_service.git_service.commit.assert_called_once()
    call_kwargs = lint_service.git_service.commit.call_args.kwargs
    assert call_kwargs["user_id"] == "owner-1"
    assert call_kwargs["kb_id"] == "kb-1"
    assert call_kwargs["message"] == "Write knowledge base lint report"
    assert call_kwargs["paths"] == [report.report_path.lstrip("/")]


@pytest.mark.unit
def test_structural_lint_requires_editor_access(lint_service):
    lint_service.kb_service.get_kb.side_effect = PermissionError("KB_ACCESS_DENIED")

    with pytest.raises(PermissionError, match="KB_ACCESS_DENIED"):
        lint_service.run_structural_lint(user_id="viewer-1", kb_id="kb-1")
