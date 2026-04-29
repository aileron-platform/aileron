"""Knowledge base wiki graph service."""

from __future__ import annotations

import itertools
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models import (
    KnowledgeBaseGraphEdge,
    KnowledgeBaseGraphEdgeReason,
    KnowledgeBaseGraphNode,
    KnowledgeBaseGraphResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService


class KnowledgeBaseGraphService:
    """Build a graph model from Team Wiki Markdown pages."""

    WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
    TYPE_AFFINITY = {
        frozenset(("entity", "concept")),
        frozenset(("concept", "synthesis")),
        frozenset(("source", "concept")),
        frozenset(("decision", "project")),
        frozenset(("overview", "concept")),
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)

    def build_graph(self, *, user_id: str, kb_id: str) -> KnowledgeBaseGraphResponse:
        """Build graph nodes and relevance edges for a KB."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)
        root = self._kb_root(kb.id)
        wiki_root = root / "wiki"
        pages = [self._parse_page(root, path) for path in sorted(wiki_root.rglob("*.md")) if path.is_file()]
        pages_by_id = {page["id"]: page for page in pages}
        aliases = self._page_aliases(pages)
        direct_edges: set[tuple[str, str]] = set()
        outbound: dict[str, set[str]] = {page["id"]: set() for page in pages}
        inbound: dict[str, set[str]] = {page["id"]: set() for page in pages}
        edge_reasons: dict[tuple[str, str], list[KnowledgeBaseGraphEdgeReason]] = defaultdict(list)

        for page in pages:
            for raw_link in page["wikilinks"]:
                target = aliases.get(self._normalize_wikilink(raw_link))
                if not target or target == page["id"]:
                    continue
                edge_key = self._edge_key(page["id"], target)
                direct_edges.add(edge_key)
                outbound[page["id"]].add(target)
                inbound[target].add(page["id"])
                if not self._has_reason(edge_reasons[edge_key], "direct_wikilink"):
                    edge_reasons[edge_key].append(
                        KnowledgeBaseGraphEdgeReason(
                            type="direct_wikilink",
                            weight=1.0,
                            details={"from": page["id"], "to": target},
                        )
                    )

        self._add_source_overlap_edges(pages, edge_reasons)
        self._add_common_neighbor_edges(pages, direct_edges, outbound, inbound, edge_reasons)
        self._add_type_affinity_edges(pages, direct_edges, edge_reasons)

        adjacency: dict[str, set[str]] = {page["id"]: set() for page in pages}
        for source, target in edge_reasons:
            adjacency[source].add(target)
            adjacency[target].add(source)

        nodes = [
            KnowledgeBaseGraphNode(
                id=page["id"],
                label=page["label"],
                type=page["type"],
                path=page["path"],
                sources=page["sources"],
                outboundCount=len(outbound[page["id"]]),
                inboundCount=len(inbound[page["id"]]),
                degree=len(adjacency[page["id"]]),
                metadata={"title": page["title"]},
            )
            for page in pages
        ]
        edges = [
            KnowledgeBaseGraphEdge(
                id=f"{source}--{target}",
                source=source,
                target=target,
                weight=round(sum(reason.weight for reason in reasons), 3),
                reasons=reasons,
            )
            for (source, target), reasons in sorted(edge_reasons.items())
            if source in pages_by_id and target in pages_by_id
        ]
        return KnowledgeBaseGraphResponse(
            kbId=kb.id,
            generatedAt=datetime.now(timezone.utc),
            nodes=nodes,
            edges=edges,
        )

    def write_graph_snapshot(self, *, user_id: str, kb_id: str) -> KnowledgeBaseGraphResponse:
        """Build and persist a graph snapshot report."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        graph = self.build_graph(user_id=user_id, kb_id=kb.id)
        relative_path = f"reports/graph/graph-{graph.generated_at.strftime('%Y%m%dT%H%M%SZ')}.json"
        target = self._resolve_path(kb.id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        graph.report_path = "/" + relative_path
        target.write_text(
            json.dumps(graph.model_dump(by_alias=True, mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return graph

    def _add_source_overlap_edges(
        self,
        pages: list[dict[str, Any]],
        edge_reasons: dict[tuple[str, str], list[KnowledgeBaseGraphEdgeReason]],
    ) -> None:
        for left, right in itertools.combinations(pages, 2):
            shared = sorted(set(left["sources"]) & set(right["sources"]))
            if not shared:
                continue
            weight = min(0.75, 0.25 * len(shared))
            edge_reasons[self._edge_key(left["id"], right["id"])].append(
                KnowledgeBaseGraphEdgeReason(
                    type="source_overlap",
                    weight=weight,
                    details={"sources": shared},
                )
            )

    def _add_common_neighbor_edges(
        self,
        pages: list[dict[str, Any]],
        direct_edges: set[tuple[str, str]],
        outbound: dict[str, set[str]],
        inbound: dict[str, set[str]],
        edge_reasons: dict[tuple[str, str], list[KnowledgeBaseGraphEdgeReason]],
    ) -> None:
        neighbors = {page["id"]: outbound[page["id"]] | inbound[page["id"]] for page in pages}
        for left, right in itertools.combinations((page["id"] for page in pages), 2):
            shared = sorted(neighbors[left] & neighbors[right])
            if not shared:
                continue
            weight = min(0.6, 0.2 * len(shared))
            edge_reasons[self._edge_key(left, right)].append(
                KnowledgeBaseGraphEdgeReason(
                    type="common_neighbor",
                    weight=weight,
                    details={"neighbors": shared, "hasDirectLink": self._edge_key(left, right) in direct_edges},
                )
            )

    def _add_type_affinity_edges(
        self,
        pages: list[dict[str, Any]],
        direct_edges: set[tuple[str, str]],
        edge_reasons: dict[tuple[str, str], list[KnowledgeBaseGraphEdgeReason]],
    ) -> None:
        page_by_id = {page["id"]: page for page in pages}
        candidate_pairs = set(edge_reasons.keys()) | direct_edges
        for source, target in sorted(candidate_pairs):
            pair = frozenset((page_by_id[source]["type"], page_by_id[target]["type"]))
            if pair not in self.TYPE_AFFINITY:
                continue
            edge_reasons[self._edge_key(source, target)].append(
                KnowledgeBaseGraphEdgeReason(
                    type="type_affinity",
                    weight=0.15,
                    details={"sourceType": page_by_id[source]["type"], "targetType": page_by_id[target]["type"]},
                )
            )

    def _parse_page(self, root: Path, path: Path) -> dict[str, Any]:
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(raw)
        relative_path = path.relative_to(root).as_posix()
        page_id = self._page_id(relative_path)
        title = str(frontmatter.get("title") or self._first_heading(body) or path.stem)
        page_type = str(frontmatter.get("type") or "page")
        sources = self._normalize_sources(frontmatter.get("sources"))
        return {
            "id": page_id,
            "label": title,
            "title": title,
            "type": page_type,
            "path": relative_path,
            "sources": sources,
            "wikilinks": self._extract_wikilinks(body),
        }

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---\n"):
            return {}, raw
        frontmatter_raw, separator, body = raw[4:].partition("\n---\n")
        if not separator:
            return {}, raw
        parsed = yaml.safe_load(frontmatter_raw) or {}
        return (parsed if isinstance(parsed, dict) else {}), body

    @classmethod
    def _extract_wikilinks(cls, body: str) -> list[str]:
        return [match.group(1).strip() for match in cls.WIKILINK_RE.finditer(body)]

    @staticmethod
    def _first_heading(body: str) -> str | None:
        for line in body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return None

    @staticmethod
    def _normalize_sources(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return []

    @staticmethod
    def _normalize_wikilink(value: str) -> str:
        target = value.split("|", 1)[0].split("#", 1)[0].strip()
        target = target.strip("/")
        if target.endswith(".md"):
            target = target[:-3]
        if target.startswith("wiki/"):
            target = target[5:]
        return target

    @classmethod
    def _page_aliases(cls, pages: list[dict[str, Any]]) -> dict[str, str]:
        aliases = {}
        for page in pages:
            page_id = page["id"]
            aliases[page_id] = page_id
            aliases[page_id.removeprefix("wiki/")] = page_id
            aliases[Path(page_id).name] = page_id
        return aliases

    @staticmethod
    def _page_id(relative_path: str) -> str:
        return relative_path[:-3] if relative_path.endswith(".md") else relative_path

    @staticmethod
    def _edge_key(source: str, target: str) -> tuple[str, str]:
        return tuple(sorted((source, target)))

    @staticmethod
    def _has_reason(reasons: list[KnowledgeBaseGraphEdgeReason], reason_type: str) -> bool:
        return any(reason.type == reason_type for reason in reasons)

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        target = root / relative_path.strip().lstrip("/")
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise ValueError("KB_GRAPH_PATH_OUTSIDE_ROOT")
        return resolved
