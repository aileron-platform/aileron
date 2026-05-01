"""Knowledge base wiki index builder unit tests."""

from __future__ import annotations

import json

import pytest

from app.services.knowledge_base_wiki_browse_service import WikiIndexBuilder


def _write_page(root, path: str, content: str) -> None:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_wiki_index_builder_reconstructs_slug_map_and_groups(tmp_path):
    _write_page(
        tmp_path,
        "wiki/entities/openai.md",
        """---
title: OpenAI
type: entity
tags: [ai]
origin: raw
description: Lab
---

# OpenAI
""",
    )
    _write_page(
        tmp_path,
        "wiki/index.md",
        """---
title: Index
type: overview
---

# Index
""",
    )

    index = WikiIndexBuilder().write(tmp_path)

    assert index.slug_to_path["entities/openai"] == "wiki/entities/openai.md"
    assert index.slug_to_path["openai"] == "wiki/entities/openai.md"
    assert [item["title"] for item in index.by_type["entity"]] == ["OpenAI"]
    assert "overview" not in index.by_type

    payload = json.loads((tmp_path / ".aileron-kb/wiki-index.json").read_text(encoding="utf-8"))
    assert payload["slugToPath"]["openai"] == "wiki/entities/openai.md"
