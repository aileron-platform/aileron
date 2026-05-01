"""Tests for REVIEW block parser in KnowledgeBaseIngestService."""

from __future__ import annotations

import pytest

from app.services.knowledge_base_ingest_service import KnowledgeBaseIngestService, KB_REVIEW_MAX_ITEMS


def _make_service():
    from unittest.mock import MagicMock
    db = MagicMock()
    svc = KnowledgeBaseIngestService.__new__(KnowledgeBaseIngestService)
    svc.db = db
    return svc


@pytest.mark.unit
def test_parse_single_contradiction():
    svc = _make_service()
    output = (
        "---REVIEW: contradiction, wiki/concepts/scaling.md, Source A contradicts Source B---\n"
        "Source A says X. Source B says Y.\n"
        "---END REVIEW---\n"
    )
    blocks = svc.parse_review_blocks(output)
    assert len(blocks) == 1
    assert blocks[0].type == "contradiction"
    assert blocks[0].page_path == "wiki/concepts/scaling.md"
    assert "Source A says X" in blocks[0].context


@pytest.mark.unit
def test_parse_all_six_types():
    svc = _make_service()
    lines = []
    for t in ["contradiction", "duplicate", "missing_page", "suggestion", "confirm", "unreadable_source"]:
        lines.append(f"---REVIEW: {t}, wiki/x.md, detail text---")
        lines.append("---END REVIEW---")
    blocks = svc.parse_review_blocks("\n".join(lines))
    assert len(blocks) == 6
    types = {b.type for b in blocks}
    assert types == {"contradiction", "duplicate", "missing_page", "suggestion", "confirm", "unreadable_source"}


@pytest.mark.unit
def test_parse_unreadable_source_with_raw_path():
    svc = _make_service()
    output = (
        "---REVIEW: unreadable_source, raw/sources/encrypted.pdf, file could not be read---\n"
        "---END REVIEW---\n"
    )
    blocks = svc.parse_review_blocks(output)
    assert len(blocks) == 1
    assert blocks[0].page_path == "raw/sources/encrypted.pdf"


@pytest.mark.unit
def test_parse_ignores_unknown_type():
    svc = _make_service()
    output = (
        "---REVIEW: invalid_type, wiki/x.md, should be ignored---\n"
        "---END REVIEW---\n"
    )
    blocks = svc.parse_review_blocks(output)
    assert len(blocks) == 0


@pytest.mark.unit
def test_parse_empty_output():
    svc = _make_service()
    blocks = svc.parse_review_blocks("")
    assert blocks == []


@pytest.mark.unit
def test_parse_caps_at_max_items():
    svc = _make_service()
    lines = []
    for i in range(KB_REVIEW_MAX_ITEMS + 10):
        lines.append(f"---REVIEW: suggestion, wiki/x{i}.md, suggestion {i}---")
        lines.append("---END REVIEW---")
    blocks = svc.parse_review_blocks("\n".join(lines))
    assert len(blocks) == KB_REVIEW_MAX_ITEMS


@pytest.mark.unit
def test_parse_mixed_with_file_blocks():
    svc = _make_service()
    output = (
        "---FILE: wiki/overview.md---\n# Overview\n---END FILE---\n"
        "---REVIEW: missing_page, wiki/entities/foo.md, missing entity page---\n"
        "---END REVIEW---\n"
        "---FILE: wiki/index.md---\n# Index\n---END FILE---\n"
    )
    blocks = svc.parse_review_blocks(output)
    assert len(blocks) == 1
    assert blocks[0].type == "missing_page"
