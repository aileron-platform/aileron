"""Knowledge base query retrieval service."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.models import (
    KnowledgeBaseQueryCitation,
    KnowledgeBaseQueryContextItem,
    KnowledgeBaseQueryResponse,
)
from app.modules.knowledge_base.access import KnowledgeBaseService
from app.modules.knowledge_base.storage import ensure_knowledge_base_storage_root


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
    """Assemble retrieval context for KB queries."""

    TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
    MAX_CONTEXT_CHARS = 24_000
    MAX_DOCUMENT_CHARS = 6_000

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)

    def query(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        query: str,
        limit: int = 8,
    ) -> KnowledgeBaseQueryResponse:
        """Return retrieval context and citations for a KB query."""
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )

        documents = self._load_documents(kb.id)
        scored = self._score_documents(query, documents)
        context_docs = self._assemble_context(scored, limit=limit)
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

    def _load_documents(self, kb_id: str) -> list[_QueryDocument]:
        root = self._kb_root(kb_id)
        documents: list[_QueryDocument] = []
        for base, doc_type in (
            (root / "normalized", "normalized"),
            (root / "raw", "source"),
        ):
            if not base.exists():
                continue
            for path in sorted(base.rglob("*.md")):
                if path.is_file():
                    documents.append(
                        self._parse_document(root, path, default_type=doc_type)
                    )
        return documents

    def _score_documents(
        self, query: str, documents: list[_QueryDocument]
    ) -> list[_QueryDocument]:
        tokens = self._tokens(query)
        for document in documents:
            document.score = self._lexical_score(tokens, document)
            if document.score > 0:
                document.reasons.add("lexical_match")
        return [document for document in documents if document.score > 0]

    def _assemble_context(
        self, documents: list[_QueryDocument], *, limit: int
    ) -> list[_QueryDocument]:
        ordered = sorted(
            documents,
            key=lambda document: (
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

    def _parse_document(
        self, root: Path, path: Path, *, default_type: str
    ) -> _QueryDocument:
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
    def _snippet(body: str, *, max_chars: int = 240) -> str:
        collapsed = " ".join(line.strip() for line in body.splitlines() if line.strip())
        return collapsed[:max_chars]

    @staticmethod
    def _truncate(content: str, max_chars: int) -> str:
        return content if len(content) <= max_chars else content[:max_chars]

    def _kb_root(self, kb_id: str) -> Path:
        return ensure_knowledge_base_storage_root(self.storage_root, kb_id)
