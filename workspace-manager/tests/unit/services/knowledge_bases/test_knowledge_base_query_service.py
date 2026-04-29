"""Knowledge base query service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.models import KnowledgeBaseQueryCitation
from app.services.knowledge_base_query_service import KnowledgeBaseQueryService


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
    )


@pytest.fixture
def query_service(mock_db_session, kb, tmp_path):
    with patch("app.services.knowledge_base_query_service.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        service = KnowledgeBaseQueryService(mock_db_session)
    service.storage_root = tmp_path
    service.wiki_service.storage_root = tmp_path
    service.graph_service.storage_root = tmp_path
    service.graph_service.wiki_service.storage_root = tmp_path
    access = type("Access", (), {"access_role": "viewer"})()
    service.kb_service.get_kb = MagicMock(return_value=(kb, access))
    service.graph_service.kb_service.get_kb = MagicMock(return_value=(kb, access))
    return service


def _write_file(query_service: KnowledgeBaseQueryService, kb_id: str, path: str, content: str) -> None:
    target = query_service.storage_root / kb_id / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_query_uses_index_first_and_returns_citations(query_service):
    _write_file(
        query_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index

Start from [[concepts/python]].
""",
    )
    _write_file(
        query_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources: [raw/sources/python.md]
---

# Python

Python has packaging and async runtime notes.
""",
    )

    result = query_service.query(user_id="owner-1", kb_id="kb-1", query="python packaging")

    assert result.status == "context_ready"
    assert [item.path for item in result.context][:2] == ["wiki/index.md", "wiki/concepts/python.md"]
    assert result.context[0].citation_index == 0
    assert result.context[0].reasons == ["index_navigation", "lexical_match"]
    assert result.citations[1].path == "wiki/concepts/python.md"
    assert result.citations[1].title == "Python"
    assert result.citations[1].type == "concept"


@pytest.mark.unit
def test_query_searches_normalized_content(query_service):
    _write_file(
        query_service,
        "kb-1",
        "normalized/uploads/research.md",
        """# Research

Vector databases support retrieval augmented generation.
""",
    )

    result = query_service.query(user_id="owner-1", kb_id="kb-1", query="vector retrieval")

    assert result.status == "context_ready"
    assert result.context[0].path == "wiki/index.md"
    normalized = next(item for item in result.context if item.path == "normalized/uploads/research.md")
    assert normalized.type == "normalized"
    assert next(citation for citation in result.citations if citation.path == normalized.path).title == "Research"


@pytest.mark.unit
def test_query_expands_seed_pages_with_graph_relevance(query_service):
    _write_file(
        query_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources: [raw/sources/python.md]
---

# Python

Python packaging uses wheels. See [[entities/pypi]].
""",
    )
    _write_file(
        query_service,
        "kb-1",
        "wiki/entities/pypi.md",
        """---
title: PyPI
type: entity
sources: [raw/sources/python.md]
---

# PyPI

Package index details.
""",
    )

    result = query_service.query(user_id="owner-1", kb_id="kb-1", query="wheels")

    paths = [item.path for item in result.context]
    assert "wiki/concepts/python.md" in paths
    assert "wiki/entities/pypi.md" in paths
    expanded = next(item for item in result.context if item.path == "wiki/entities/pypi.md")
    assert "graph_expansion" in expanded.reasons


@pytest.mark.unit
def test_query_returns_no_context_without_matches(query_service):
    result = query_service.query(user_id="owner-1", kb_id="kb-1", query="missing topic")

    assert result.status == "no_context"
    assert result.answer == ""
    assert result.citations == []
    assert result.context == []


@pytest.mark.unit
def test_save_answer_to_wiki_writes_query_page_with_citations(query_service):
    response = query_service.save_answer_to_wiki(
        user_id="owner-1",
        kb_id="kb-1",
        query="How does Python packaging work?",
        answer="Python packaging uses wheels and package indexes.",
        citations=[
            KnowledgeBaseQueryCitation(
                path="wiki/concepts/python.md",
                title="Python",
                type="concept",
                score=2.5,
            )
        ],
    )

    assert response.commit_id is None
    assert response.path == "/wiki/queries/how-does-python-packaging-work.md"
    content = (query_service.storage_root / "kb-1" / response.path.lstrip("/")).read_text(encoding="utf-8")
    assert "type: query" in content
    assert "query: How does Python packaging work?" in content
    assert "- wiki/concepts/python.md" in content
    assert "Python packaging uses wheels and package indexes." in content
    assert "- [1] `wiki/concepts/python.md` - Python (concept)" in content
    query_service.kb_service.get_kb.assert_called_with(user_id="owner-1", kb_id="kb-1", minimum_role="editor")


@pytest.mark.unit
def test_save_answer_to_wiki_uses_unique_path(query_service):
    query_service.save_answer_to_wiki(
        user_id="owner-1",
        kb_id="kb-1",
        query="Repeated query",
        answer="First answer",
        citations=[],
    )

    second = query_service.save_answer_to_wiki(
        user_id="owner-1",
        kb_id="kb-1",
        query="Repeated query",
        answer="Second answer",
        citations=[],
    )

    assert second.path == "/wiki/queries/repeated-query-2.md"


@pytest.mark.unit
def test_save_answer_to_wiki_commits_when_git_enabled(query_service, kb):
    kb.version_control_enabled = True
    query_service.git_service = MagicMock()
    query_service.git_service.commit.return_value = type(
        "CommitResponse",
        (),
        {"commit": type("Commit", (), {"id": "commit-123"})()},
    )()

    response = query_service.save_answer_to_wiki(
        user_id="owner-1",
        kb_id="kb-1",
        query="Commit this answer",
        answer="Saved answer",
        citations=[],
        title="Saved Answer",
    )

    assert response.path == "/wiki/queries/saved-answer.md"
    assert response.commit_id == "commit-123"
    query_service.git_service.commit.assert_called_once_with(
        user_id="owner-1",
        kb_id="kb-1",
        message="Save query answer: Saved Answer",
        paths=["wiki/queries/saved-answer.md"],
    )


@pytest.mark.unit
def test_save_answer_to_wiki_requires_editor_access(query_service):
    query_service.kb_service.get_kb.side_effect = PermissionError("KB_ACCESS_DENIED")

    with pytest.raises(PermissionError, match="KB_ACCESS_DENIED"):
        query_service.save_answer_to_wiki(
            user_id="viewer-1",
            kb_id="kb-1",
            query="Cannot save",
            answer="No write access",
            citations=[],
        )
