"""Tests for KnowledgeBaseReviewItemService."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
import yaml

from app.db import models as db_models
from app.services.knowledge_base_review_item_service import KnowledgeBaseReviewItemService


@pytest.fixture
def kb():
    return db_models.KnowledgeBase(
        id="kb-1",
        owner_id="owner-1",
        slug="docs",
        name="Docs",
        current_size_bytes=0,
    )


@pytest.fixture
def review_service(tmp_path, kb):
    db = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    svc = KnowledgeBaseReviewItemService(db)
    svc.storage_root = tmp_path
    svc.wiki_service.storage_root = tmp_path
    access = type("Access", (), {"access_role": "editor"})()
    svc.kb_service.get_kb = MagicMock(return_value=(kb, access))
    svc.wiki_service.initialize = MagicMock(return_value=kb)
    return svc


def _init_kb(svc: KnowledgeBaseReviewItemService, kb_id: str):
    reviews_path = svc.storage_root / kb_id / ".aileron-kb" / "reviews.json"
    reviews_path.parent.mkdir(parents=True, exist_ok=True)
    reviews_path.write_text("[]\n", encoding="utf-8")


@pytest.mark.unit
def test_list_items_empty(review_service, kb):
    _init_kb(review_service, kb.id)
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    assert items == []


@pytest.mark.unit
def test_append_and_list_items(review_service, kb):
    _init_kb(review_service, kb.id)

    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    blocks = [
        ParsedReviewBlock(type="contradiction", page_path="wiki/x.md", detail="conflict", context="ctx"),
        ParsedReviewBlock(type="suggestion", page_path="wiki/y.md", detail="add cross-ref"),
    ]
    review_service.append_from_ingest(kb_id=kb.id, review_blocks=blocks)

    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    assert len(items) == 2
    types = {it["type"] for it in items}
    assert types == {"contradiction", "suggestion"}


@pytest.mark.unit
def test_resolve_item(review_service, kb):
    _init_kb(review_service, kb.id)
    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[ParsedReviewBlock(type="suggestion", page_path="wiki/x.md", detail="text")],
    )
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    item_id = items[0]["id"]

    resolved = review_service.resolve(user_id="owner-1", kb_id=kb.id, item_id=item_id)
    assert resolved["status"] == "resolved"
    assert resolved["resolvedBy"] == "owner-1"


@pytest.mark.unit
def test_dismiss_item(review_service, kb):
    _init_kb(review_service, kb.id)
    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[ParsedReviewBlock(type="confirm", page_path="wiki/x.md", detail="verify")],
    )
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    dismissed = review_service.dismiss(user_id="owner-1", kb_id=kb.id, item_id=items[0]["id"])
    assert dismissed["status"] == "dismissed"


@pytest.mark.unit
def test_convert_to_query_page(review_service, kb, tmp_path):
    _init_kb(review_service, kb.id)
    review_service.wiki_service.storage_root = tmp_path
    wiki_queries = tmp_path / kb.id / "wiki" / "queries"
    wiki_queries.mkdir(parents=True, exist_ok=True)

    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[ParsedReviewBlock(type="contradiction", page_path="wiki/x.md", detail="conflict")],
    )
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    result = review_service.convert_to_query(
        user_id="owner-1",
        kb_id=kb.id,
        item_id=items[0]["id"],
        title="Open Question",
        slug="open-question",
    )

    query_file = tmp_path / kb.id / "wiki" / "queries" / "open-question.md"
    assert query_file.is_file()
    assert result["status"] == "resolved"
    assert result["queryPage"] == "wiki/queries/open-question.md"


@pytest.mark.unit
def test_convert_to_query_page_escapes_frontmatter_title(review_service, kb, tmp_path):
    _init_kb(review_service, kb.id)
    review_service.wiki_service.storage_root = tmp_path

    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[
            ParsedReviewBlock(
                type="suggestion",
                page_path="wiki/x.md",
                detail="confirm: ownership\nbefore publishing",
            )
        ],
    )
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)

    review_service.convert_to_query(
        user_id="owner-1",
        kb_id=kb.id,
        item_id=items[0]["id"],
        title="Open: Question\nNext",
        slug="open-question-next",
    )

    query_file = tmp_path / kb.id / "wiki" / "queries" / "open-question-next.md"
    raw = query_file.read_text(encoding="utf-8")
    frontmatter_raw = raw.split("---\n", 2)[1]
    assert yaml.safe_load(frontmatter_raw)["title"] == "Open: Question\nNext"
    assert "# Open: Question Next" in raw
    assert "confirm: ownership before publishing" in raw


@pytest.mark.unit
def test_write_is_atomic(review_service, kb):
    _init_kb(review_service, kb.id)
    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[ParsedReviewBlock(type="suggestion", page_path="wiki/x.md", detail="d")],
    )
    reviews_path = review_service.storage_root / kb.id / ".aileron-kb" / "reviews.json"
    data = json.loads(reviews_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 1
    tmp_files = list((review_service.storage_root / kb.id / ".aileron-kb").glob(".reviews-tmp-*"))
    assert tmp_files == []


@pytest.mark.unit
def test_count_by_status(review_service, kb):
    _init_kb(review_service, kb.id)
    from app.services.knowledge_base_ingest_service import ParsedReviewBlock
    review_service.append_from_ingest(
        kb_id=kb.id,
        review_blocks=[
            ParsedReviewBlock(type="suggestion", page_path="wiki/a.md", detail="a"),
            ParsedReviewBlock(type="contradiction", page_path="wiki/b.md", detail="b"),
        ],
    )
    items = review_service.list_items(user_id="owner-1", kb_id=kb.id)
    review_service.resolve(user_id="owner-1", kb_id=kb.id, item_id=items[0]["id"])

    counts = review_service.count_by_status(kb_id=kb.id)
    assert counts["open"] == 1
    assert counts["resolved"] == 1
    assert counts["dismissed"] == 0
