"""Knowledge base wiki-first query retrieval service."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models import (
    KnowledgeBaseQueryCitation,
    KnowledgeBaseQueryContextItem,
    KnowledgeBaseQueryResponse,
    KnowledgeBaseQuerySaveResponse,
)
from app.services.knowledge_base_graph_service import KnowledgeBaseGraphService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService


@dataclass
class _QueryDocument:
    path: str
    title: str
    type: str
    content: str
    body: str
    score: float = 0
    reasons: set[str] = field(default_factory=set)


class KnowledgeBaseQueryService:
    """Assemble wiki-first retrieval context for KB queries."""

    TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
    MAX_CONTEXT_CHARS = 24_000
    MAX_DOCUMENT_CHARS = 6_000

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)
        self.graph_service = KnowledgeBaseGraphService(db)
        self.git_service: Any | None = None

    def query(
        self,
        *,
        user_id: str,
        kb_id: str,
        query: str,
        limit: int = 8,
    ) -> KnowledgeBaseQueryResponse:
        """Return retrieval context and citations for a KB query."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self.wiki_service.storage_root = self.storage_root
        self.graph_service.storage_root = self.storage_root
        self.graph_service.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

        documents = self._load_documents(kb.id)
        scored = self._score_documents(query, documents)
        expanded = self._expand_with_graph(user_id=user_id, kb_id=kb.id, documents=scored)
        context_docs = self._assemble_context(expanded, limit=limit)
        if not context_docs:
            return KnowledgeBaseQueryResponse(
                kbId=kb.id,
                query=query,
                status="no_context",
                answer="",
                citations=[],
                context=[],
            )

        citations = [
            KnowledgeBaseQueryCitation(
                path=document.path,
                title=document.title,
                type=document.type,
                score=round(document.score, 3),
                snippet=self._snippet(document.body),
            )
            for document in context_docs
        ]
        context = [
            KnowledgeBaseQueryContextItem(
                path=document.path,
                title=document.title,
                type=document.type,
                score=round(document.score, 3),
                content=self._truncate(document.content, self.MAX_DOCUMENT_CHARS),
                citationIndex=index,
                reasons=sorted(document.reasons),
            )
            for index, document in enumerate(context_docs)
        ]
        return KnowledgeBaseQueryResponse(
            kbId=kb.id,
            query=query,
            status="context_ready",
            answer="",
            citations=citations,
            context=context,
        )

    def save_answer_to_wiki(
        self,
        *,
        user_id: str,
        kb_id: str,
        query: str,
        answer: str,
        citations: list[KnowledgeBaseQueryCitation],
        title: str | None = None,
    ) -> KnowledgeBaseQuerySaveResponse:
        """Persist a query answer as a wiki page."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

        page_title = title or self._answer_title(query)
        relative_path = self._unique_query_page_path(kb.id, page_title)
        target = self._resolve_path(kb.id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            self._answer_markdown(title=page_title, query=query, answer=answer, citations=citations),
            encoding="utf-8",
        )

        commit_id = None
        if kb.version_control_enabled:
            response = self._git_service().commit(
                user_id=user_id,
                kb_id=kb.id,
                message=f"Save query answer: {page_title}",
                paths=[relative_path],
            )
            commit_id = response.commit.id
        return KnowledgeBaseQuerySaveResponse(path="/" + relative_path, commitId=commit_id)

    def _load_documents(self, kb_id: str) -> list[_QueryDocument]:
        root = self._kb_root(kb_id)
        documents: list[_QueryDocument] = []
        for base, doc_type in ((root / "wiki", "wiki"), (root / "normalized", "normalized")):
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.md")):
                if path.is_file():
                    documents.append(self._parse_document(root, path, default_type=doc_type))
        return documents

    def _score_documents(self, query: str, documents: list[_QueryDocument]) -> list[_QueryDocument]:
        tokens = self._tokens(query)
        for document in documents:
            document.score = self._lexical_score(tokens, document)
            if document.score > 0:
                document.reasons.add("lexical_match")
        has_relevant_document = any(document.score > 0 and document.path != "wiki/index.md" for document in documents)
        if has_relevant_document:
            for document in documents:
                if document.path == "wiki/index.md":
                    document.score = max(document.score, 0.5)
                    document.reasons.add("index_navigation")
        return [document for document in documents if document.score > 0]

    def _expand_with_graph(
        self,
        *,
        user_id: str,
        kb_id: str,
        documents: list[_QueryDocument],
    ) -> list[_QueryDocument]:
        by_path = {document.path: document for document in documents}
        all_documents = {document.path: document for document in self._load_documents(kb_id)}
        seed_ids = {
            self._page_id(document.path)
            for document in documents
            if document.path.startswith("wiki/") and document.path.endswith(".md")
        }
        if not seed_ids:
            return documents

        graph = self.graph_service.build_graph(user_id=user_id, kb_id=kb_id)
        for edge in graph.edges:
            source_seed = edge.source in seed_ids
            target_seed = edge.target in seed_ids
            if source_seed == target_seed:
                continue
            related_id = edge.target if source_seed else edge.source
            related_path = f"{related_id}.md"
            related = by_path.get(related_path) or all_documents.get(related_path)
            if related is None:
                continue
            related.score = max(related.score, min(0.9, edge.weight * 0.4))
            related.reasons.add("graph_expansion")
            by_path[related.path] = related
        return list(by_path.values())

    def _assemble_context(self, documents: list[_QueryDocument], *, limit: int) -> list[_QueryDocument]:
        ordered = sorted(
            documents,
            key=lambda document: (
                0 if document.path == "wiki/index.md" else 1,
                -document.score,
                document.path,
            ),
        )
        selected: list[_QueryDocument] = []
        total_chars = 0
        for document in ordered:
            if len(selected) >= limit:
                break
            size = min(len(document.content), self.MAX_DOCUMENT_CHARS)
            if selected and total_chars + size > self.MAX_CONTEXT_CHARS:
                break
            selected.append(document)
            total_chars += size
        return selected

    def _parse_document(self, root: Path, path: Path, *, default_type: str) -> _QueryDocument:
        raw = path.read_text(encoding="utf-8")
        frontmatter, body = self._parse_frontmatter(raw)
        relative_path = path.relative_to(root).as_posix()
        title = str(frontmatter.get("title") or self._first_heading(body) or path.stem)
        page_type = str(frontmatter.get("type") or default_type)
        return _QueryDocument(
            path=relative_path,
            title=title,
            type=page_type,
            content=raw,
            body=body,
        )

    @classmethod
    def _lexical_score(cls, tokens: list[str], document: _QueryDocument) -> float:
        if not tokens:
            return 0
        title = document.title.lower()
        path = document.path.lower()
        body = document.body.lower()
        score = 0.0
        for token in tokens:
            score += 3.0 if token in title else 0
            score += 1.5 if token in path else 0
            score += min(4, body.count(token)) * 0.5
        return score / max(len(tokens), 1)

    @classmethod
    def _tokens(cls, query: str) -> list[str]:
        return [token.lower() for token in cls.TOKEN_RE.findall(query) if token.strip()]

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---\n"):
            return {}, raw
        frontmatter_raw, separator, body = raw[4:].partition("\n---\n")
        if not separator:
            return {}, raw
        parsed = yaml.safe_load(frontmatter_raw) or {}
        return (parsed if isinstance(parsed, dict) else {}), body

    @staticmethod
    def _first_heading(body: str) -> str | None:
        for line in body.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return None

    @staticmethod
    def _page_id(path: str) -> str:
        return path[:-3] if path.endswith(".md") else path

    @staticmethod
    def _snippet(body: str, *, max_chars: int = 240) -> str:
        collapsed = " ".join(line.strip() for line in body.splitlines() if line.strip())
        return collapsed[:max_chars]

    @staticmethod
    def _truncate(content: str, max_chars: int) -> str:
        return content if len(content) <= max_chars else content[:max_chars]

    def _answer_markdown(
        self,
        *,
        title: str,
        query: str,
        answer: str,
        citations: list[KnowledgeBaseQueryCitation],
    ) -> str:
        now = datetime.now(timezone.utc).isoformat()
        frontmatter = {
            "title": title,
            "type": "query",
            "query": query,
            "sources": [citation.path for citation in citations],
            "createdAt": now,
        }
        citation_lines = "\n".join(
            f"- [{index + 1}] `{citation.path}` - {citation.title} ({citation.type})"
            for index, citation in enumerate(citations)
        )
        return (
            "---\n"
            + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
            + "\n---\n\n"
            + f"# {title}\n\n"
            + f"## Query\n\n{query.strip()}\n\n"
            + f"## Answer\n\n{answer.strip()}\n\n"
            + "## Citations\n\n"
            + (citation_lines or "- No citations")
            + "\n"
        )

    def _unique_query_page_path(self, kb_id: str, title: str) -> str:
        queries_root = self._kb_root(kb_id) / "wiki" / "queries"
        slug = self._slug(title)
        candidate = queries_root / f"{slug}.md"
        counter = 2
        while candidate.exists():
            candidate = queries_root / f"{slug}-{counter}.md"
            counter += 1
        return candidate.relative_to(self._kb_root(kb_id)).as_posix()

    @staticmethod
    def _answer_title(query: str) -> str:
        trimmed = " ".join(query.strip().split())
        return trimmed[:80] or "Query Answer"

    @classmethod
    def _slug(cls, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "-", value.strip().lower()).strip("-")
        return slug or "query-answer"

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        target = root / relative_path.strip().lstrip("/")
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise ValueError("KB_QUERY_PATH_OUTSIDE_ROOT")
        return resolved

    def _git_service(self) -> Any:
        if self.git_service is not None:
            return self.git_service
        from app.services.knowledge_base_git_service import KnowledgeBaseGitService

        service = KnowledgeBaseGitService(self.db)
        service.storage_root = self.storage_root
        service.wiki_service.storage_root = self.storage_root
        self.git_service = service
        return service

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root
