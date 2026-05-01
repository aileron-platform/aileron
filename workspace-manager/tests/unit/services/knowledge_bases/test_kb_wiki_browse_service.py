"""Knowledge base wiki browse service unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.services.knowledge_base_wiki_browse_service import KnowledgeBaseWikiBrowseService


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
        quota_bytes=None,
    )


@pytest.fixture
def service(tmp_path, kb):
    with patch("app.services.knowledge_base_wiki_browse_service.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        svc = KnowledgeBaseWikiBrowseService(MagicMock())
    svc.storage_root = tmp_path
    svc.wiki_service.storage_root = tmp_path
    svc.kb_service.get_kb = MagicMock(return_value=(kb, type("Access", (), {"access_role": "viewer"})()))
    return svc


def _write_page(service: KnowledgeBaseWikiBrowseService, path: str, content: str) -> None:
    target = service.storage_root / "kb-1" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_list_pages_groups_by_type_and_excludes_index(service):
    _write_page(service, "wiki/index.md", "---\ntitle: Index\ntype: overview\n---\n# Index\n")
    _write_page(service, "wiki/overview.md", "---\ntitle: Overview\ntype: overview\n---\n# Overview\n")
    _write_page(service, "wiki/entities/openai.md", "---\ntitle: OpenAI\ntype: entity\n---\n# OpenAI\n")

    response = service.list_pages(user_id="owner-1", kb_id="kb-1")

    groups = {group.type: group.items for group in response.groups}
    assert [item.path for item in groups["overview"]] == ["wiki/overview.md"]
    assert [item.path for item in groups["entity"]] == ["wiki/entities/openai.md"]
    assert groups["concept"] == []


@pytest.mark.unit
def test_get_page_resolves_wikilinks_and_sources(service):
    _write_page(service, "raw/sources/openai.md", "# Source\n")
    _write_page(
        service,
        "wiki/entities/openai.md",
        """---
title: OpenAI
type: entity
sources:
  - openai.md
---

# OpenAI

See [[concepts/llm|LLM]] and [[missing]].
""",
    )
    _write_page(service, "wiki/concepts/llm.md", "---\ntitle: LLM\ntype: concept\n---\n# LLM\n")

    response = service.get_page(user_id="owner-1", kb_id="kb-1", path="wiki/entities/openai.md")

    assert response.frontmatter["title"] == "OpenAI"
    assert response.body.startswith("# OpenAI")
    assert response.resolved.sources[0].path == "raw/sources/openai.md"
    assert response.resolved.sources[0].exists is True
    related = {item.slug: item for item in response.resolved.related}
    assert related["concepts/llm"].path == "wiki/concepts/llm.md"
    assert related["concepts/llm"].exists is True
    assert related["missing"].exists is False


@pytest.mark.unit
def test_get_page_rejects_path_traversal(service):
    with pytest.raises(Exception) as exc:
        service.get_page(user_id="owner-1", kb_id="kb-1", path="../../etc/passwd")

    assert getattr(exc.value, "code", "") == "KB_WIKI_PAGE_PATH_INVALID"
