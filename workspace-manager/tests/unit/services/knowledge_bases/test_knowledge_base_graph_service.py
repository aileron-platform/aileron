"""Knowledge base graph service unit tests."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.db import models as db_models
from app.services.knowledge_base_graph_service import KnowledgeBaseGraphService


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
def graph_service(mock_db_session, kb, tmp_path):
    with patch("app.services.knowledge_base_graph_service.get_settings") as mock_settings:
        mock_settings.return_value.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path)
        service = KnowledgeBaseGraphService(mock_db_session)
    service.storage_root = tmp_path
    service.wiki_service.storage_root = tmp_path
    service.kb_service.get_kb = MagicMock(
        return_value=(kb, type("Access", (), {"access_role": "viewer"})())
    )
    return service


def _write_page(graph_service: KnowledgeBaseGraphService, kb_id: str, path: str, content: str) -> None:
    target = graph_service.storage_root / kb_id / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.mark.unit
def test_build_graph_returns_nodes_for_wiki_pages(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources:
  - raw/sources/python.md
---

# Python

See [[entities/guido]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/entities/guido.md",
        """---
title: Guido van Rossum
type: entity
sources:
  - raw/sources/python.md
---

# Guido
""",
    )

    graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")

    nodes = {node.id: node for node in graph.nodes}
    assert set(nodes) >= {"wiki/concepts/python", "wiki/entities/guido"}
    assert nodes["wiki/concepts/python"].label == "Python"
    assert nodes["wiki/concepts/python"].type == "concept"
    assert nodes["wiki/concepts/python"].sources == ["raw/sources/python.md"]
    assert nodes["wiki/concepts/python"].outbound_count == 1
    assert nodes["wiki/entities/guido"].inbound_count == 1


@pytest.mark.unit
def test_build_graph_combines_direct_source_common_neighbor_and_type_reasons(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources: [raw/sources/shared.md]
---

# Python

See [[entities/guido]] and [[overview]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/entities/guido.md",
        """---
title: Guido
type: entity
sources: [raw/sources/shared.md]
---

# Guido

See [[overview]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/overview.md",
        """---
title: Overview
type: overview
sources: []
---

# Overview
""",
    )

    graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")
    edge = next(
        item
        for item in graph.edges
        if {item.source, item.target} == {"wiki/concepts/python", "wiki/entities/guido"}
    )

    reason_types = {reason.type for reason in edge.reasons}
    assert reason_types == {"direct_wikilink", "source_overlap", "common_neighbor", "type_affinity"}
    assert edge.weight == 1.6
    assert next(reason for reason in edge.reasons if reason.type == "source_overlap").details["sources"] == [
        "raw/sources/shared.md"
    ]
    assert next(reason for reason in edge.reasons if reason.type == "common_neighbor").details["neighbors"] == [
        "wiki/overview"
    ]


@pytest.mark.unit
def test_build_graph_ignores_broken_wikilinks(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index

See [[missing/page]].
""",
    )

    graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")

    assert {node.id for node in graph.nodes} >= {"wiki/index"}
    assert all("missing/page" not in {edge.source, edge.target} for edge in graph.edges)


@pytest.mark.unit
def test_build_graph_reuses_cached_graph_for_matching_fingerprint(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index
""",
    )

    first_graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")

    with patch.object(graph_service, "_parse_page", side_effect=AssertionError("cache miss")):
        cached_graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")

    assert cached_graph.kb_id == first_graph.kb_id
    assert [node.id for node in cached_graph.nodes] == [node.id for node in first_graph.nodes]
    assert graph_service.kb_service.get_kb.call_count == 2


@pytest.mark.unit
def test_write_graph_snapshot_uses_fresh_timestamp_for_cached_graph(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index
""",
    )

    first_snapshot = graph_service.write_graph_snapshot(user_id="owner-1", kb_id="kb-1")

    with patch.object(graph_service, "_parse_page", side_effect=AssertionError("cache miss")):
        second_snapshot = graph_service.write_graph_snapshot(user_id="owner-1", kb_id="kb-1")

    assert first_snapshot.report_path != second_snapshot.report_path
    assert first_snapshot.generated_at != second_snapshot.generated_at
    assert (graph_service.storage_root / "kb-1" / first_snapshot.report_path.lstrip("/")).exists()
    assert (graph_service.storage_root / "kb-1" / second_snapshot.report_path.lstrip("/")).exists()

    second_payload = json.loads(
        (graph_service.storage_root / "kb-1" / second_snapshot.report_path.lstrip("/")).read_text(encoding="utf-8")
    )
    assert datetime.fromisoformat(second_payload["generatedAt"].replace("Z", "+00:00")) == second_snapshot.generated_at


@pytest.mark.unit
def test_build_graph_rebuilds_when_wiki_content_changes(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index
""",
    )
    graph_service.build_graph(user_id="owner-1", kb_id="kb-1")
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Updated Index
type: overview
sources: []
---

# Updated Index
""",
    )

    graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")

    assert graph.nodes[0].label == "Updated Index"


@pytest.mark.unit
def test_build_graph_checks_access_before_returning_cached_graph(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index
""",
    )
    graph_service.build_graph(user_id="owner-1", kb_id="kb-1")
    graph_service.kb_service.get_kb.side_effect = PermissionError("denied")

    with pytest.raises(PermissionError):
        graph_service.build_graph(user_id="stranger-1", kb_id="kb-1")


@pytest.mark.unit
def test_graph_content_fingerprint_changes_when_graph_affecting_content_changes(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index
""",
    )
    root = graph_service.storage_root / "kb-1"
    wiki_paths = [root / "wiki/index.md"]
    first_fingerprint = graph_service._graph_content_fingerprint(root, wiki_paths)

    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: [raw/sources/new.md]
---

# Index
""",
    )

    assert graph_service._graph_content_fingerprint(root, wiki_paths) != first_fingerprint


@pytest.mark.unit
def test_indexed_relationship_generation_preserves_source_and_common_neighbor_reasons(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/a.md",
        """---
title: A
type: concept
sources: [raw/sources/shared.md]
---

# A

See [[hub]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/b.md",
        """---
title: B
type: entity
sources: [raw/sources/shared.md]
---

# B

See [[hub]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/hub.md",
        """---
title: Hub
type: overview
sources: []
---

# Hub
""",
    )

    graph = graph_service.build_graph(user_id="owner-1", kb_id="kb-1")
    edge = next(item for item in graph.edges if {item.source, item.target} == {"wiki/a", "wiki/b"})

    assert {reason.type for reason in edge.reasons} >= {"source_overlap", "common_neighbor", "type_affinity"}
    assert next(reason for reason in edge.reasons if reason.type == "source_overlap").details == {
        "sources": ["raw/sources/shared.md"]
    }
    assert next(reason for reason in edge.reasons if reason.type == "common_neighbor").details == {
        "neighbors": ["wiki/hub"],
        "hasDirectLink": False,
    }


@pytest.mark.unit
def test_write_graph_snapshot_persists_report(graph_service):
    _write_page(
        graph_service,
        "kb-1",
        "wiki/index.md",
        """---
title: Index
type: overview
sources: []
---

# Index

See [[concepts/python]].
""",
    )
    _write_page(
        graph_service,
        "kb-1",
        "wiki/concepts/python.md",
        """---
title: Python
type: concept
sources: []
---

# Python
""",
    )

    graph = graph_service.write_graph_snapshot(user_id="owner-1", kb_id="kb-1")

    assert graph.report_path is not None
    assert graph.report_path.startswith("/reports/graph/graph-")
    payload = json.loads((graph_service.storage_root / "kb-1" / graph.report_path.lstrip("/")).read_text(encoding="utf-8"))
    assert payload["kbId"] == "kb-1"
    assert payload["reportPath"] == graph.report_path
    assert {node["id"] for node in payload["nodes"]} >= {"wiki/index", "wiki/concepts/python"}
    assert payload["edges"][0]["reasons"][0]["type"] == "direct_wikilink"
    graph_service.kb_service.get_kb.assert_any_call(user_id="owner-1", kb_id="kb-1", minimum_role="editor")
