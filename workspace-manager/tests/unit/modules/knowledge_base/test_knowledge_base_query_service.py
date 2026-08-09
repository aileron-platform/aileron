"""Knowledge base query service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.query import KnowledgeBaseQueryService

OWNER_ACTOR = AuthorizationActor(user_id="owner-1", platform_role="member")


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
    with patch("app.modules.knowledge_base.query.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        service = KnowledgeBaseQueryService(mock_db_session)
    service.storage_root = tmp_path
    access = type("Access", (), {"access_role": "reader"})()
    service.kb_service.get_kb_for_operation = MagicMock(return_value=(kb, access))
    return service


def _write_file(
    query_service: KnowledgeBaseQueryService, kb_id: str, path: str, content: str
) -> None:
    target = query_service.storage_root / kb_id / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_query_uses_normalized_and_raw_documents(query_service):
    _write_file(
        query_service,
        "kb-1",
        "normalized/uploads/research.md",
        """# Research

Vector databases support retrieval augmented generation.
""",
    )
    _write_file(
        query_service,
        "kb-1",
        "raw/sources/python.md",
        """---
title: Python
---

# Python

Python has packaging and async runtime notes.
""",
    )

    result = query_service.query(
        actor=OWNER_ACTOR, kb_id="kb-1", query="python packaging"
    )

    query_service.kb_service.get_kb_for_operation.assert_called_once_with(
        actor=OWNER_ACTOR,
        kb_id="kb-1",
        operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
    )
    assert result.status == "context_ready"
    assert [item.path for item in result.context] == ["raw/sources/python.md"]
    assert result.context[0].citation_index == 0
    assert result.context[0].reasons == ["lexical_match"]
    assert result.citations[0].path == "raw/sources/python.md"
    assert result.citations[0].title == "Python"
    assert result.citations[0].type == "source"


@pytest.mark.unit
def test_query_defaults_raw_markdown_without_frontmatter_to_source(query_service):
    _write_file(
        query_service,
        "kb-1",
        "raw/sources/plain.md",
        """# Plain Source

Plain markdown source mentions durable retrieval behavior.
""",
    )

    result = query_service.query(
        actor=OWNER_ACTOR, kb_id="kb-1", query="durable retrieval"
    )

    assert result.status == "context_ready"
    assert result.context[0].path == "raw/sources/plain.md"
    assert result.context[0].title == "Plain Source"
    assert result.context[0].type == "source"
    assert result.citations[0].type == "source"


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

    result = query_service.query(
        actor=OWNER_ACTOR, kb_id="kb-1", query="vector retrieval"
    )

    assert result.status == "context_ready"
    assert [item.path for item in result.context] == ["normalized/uploads/research.md"]
    assert result.context[0].type == "normalized"
    assert result.citations[0].title == "Research"


@pytest.mark.unit
def test_query_returns_no_context_without_matches(query_service):
    result = query_service.query(actor=OWNER_ACTOR, kb_id="kb-1", query="missing topic")

    assert result.status == "no_context"
    assert result.answer == ""
    assert result.citations == []
    assert result.context == []
