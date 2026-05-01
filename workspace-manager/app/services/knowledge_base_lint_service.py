"""Knowledge base structural wiki lint service."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models import KnowledgeBaseLintIssue, KnowledgeBaseLintReportResponse
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService


@dataclass
class _LintPage:
    path: str
    page_id: str
    title: str
    slug: str
    raw: str
    body: str
    frontmatter: dict[str, Any]
    has_frontmatter: bool
    wikilinks: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)


class KnowledgeBaseLintService:
    """Run structural Team Wiki lint checks without LLM calls."""

    WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
    REQUIRED_FRONTMATTER = ("title", "type", "sources")

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)

    def run_structural_lint(self, *, user_id: str, kb_id: str) -> KnowledgeBaseLintReportResponse:
        """Run structural lint and return inline result (not persisted)."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)
        root = self._kb_root(kb.id)
        pages = self._load_pages(root)
        aliases = self._page_aliases(pages)
        inbound: dict[str, set[str]] = {page.page_id: set() for page in pages}
        outbound: dict[str, set[str]] = {page.page_id: set() for page in pages}
        issues: list[KnowledgeBaseLintIssue] = []

        self._lint_wikilinks(pages, aliases, inbound, outbound, issues)
        self._lint_graph_connectivity(pages, inbound, outbound, issues)
        self._lint_frontmatter(pages, issues)
        self._lint_sources(root, pages, issues)
        self._lint_duplicates(pages, issues)

        return KnowledgeBaseLintReportResponse(
            kbId=kb.id,
            generatedAt=datetime.now(timezone.utc),
            issueCounts=dict(Counter(issue.issue_type for issue in issues)),
            issues=issues,
        )

    def _load_pages(self, root: Path) -> list[_LintPage]:
        wiki_root = root / "wiki"
        if not wiki_root.exists():
            return []
        return [self._parse_page(root, path) for path in sorted(wiki_root.rglob("*.md")) if path.is_file()]

    def _lint_wikilinks(
        self,
        pages: list[_LintPage],
        aliases: dict[str, str],
        inbound: dict[str, set[str]],
        outbound: dict[str, set[str]],
        issues: list[KnowledgeBaseLintIssue],
    ) -> None:
        for page in pages:
            for raw_link in page.wikilinks:
                target = aliases.get(self._normalize_wikilink(raw_link))
                if not target:
                    issues.append(
                        KnowledgeBaseLintIssue(
                            issueType="broken_wikilink",
                            severity="error",
                            path=page.path,
                            details={"target": raw_link},
                        )
                    )
                    continue
                if target != page.page_id:
                    outbound[page.page_id].add(target)
                    inbound[target].add(page.page_id)

    @staticmethod
    def _lint_graph_connectivity(
        pages: list[_LintPage],
        inbound: dict[str, set[str]],
        outbound: dict[str, set[str]],
        issues: list[KnowledgeBaseLintIssue],
    ) -> None:
        for page in pages:
            if page.path == "wiki/index.md":
                continue
            if not inbound[page.page_id]:
                issues.append(
                    KnowledgeBaseLintIssue(
                        issueType="orphan_page",
                        severity="warning",
                        path=page.path,
                    )
                )
            if not outbound[page.page_id]:
                issues.append(
                    KnowledgeBaseLintIssue(
                        issueType="no_outbound_links",
                        severity="info",
                        path=page.path,
                    )
                )

    def _lint_frontmatter(self, pages: list[_LintPage], issues: list[KnowledgeBaseLintIssue]) -> None:
        for page in pages:
            missing = [key for key in self.REQUIRED_FRONTMATTER if key not in page.frontmatter]
            if not page.has_frontmatter or missing:
                issues.append(
                    KnowledgeBaseLintIssue(
                        issueType="missing_frontmatter",
                        severity="error",
                        path=page.path,
                        details={"missing": missing or list(self.REQUIRED_FRONTMATTER)},
                    )
                )

    def _lint_sources(self, root: Path, pages: list[_LintPage], issues: list[KnowledgeBaseLintIssue]) -> None:
        for page in pages:
            for source in page.sources:
                normalized = source.strip().lstrip("/")
                if not normalized or ".." in Path(normalized).parts:
                    issues.append(
                        KnowledgeBaseLintIssue(
                            issueType="missing_source",
                            severity="error",
                            path=page.path,
                            details={"source": source},
                        )
                    )
                    continue
                if not (root / normalized).exists():
                    issues.append(
                        KnowledgeBaseLintIssue(
                            issueType="missing_source",
                            severity="error",
                            path=page.path,
                            details={"source": source},
                        )
                    )

    @staticmethod
    def _lint_duplicates(pages: list[_LintPage], issues: list[KnowledgeBaseLintIssue]) -> None:
        by_title: dict[str, list[_LintPage]] = {}
        by_slug: dict[str, list[_LintPage]] = {}
        for page in pages:
            by_title.setdefault(page.title.strip().lower(), []).append(page)
            by_slug.setdefault(page.slug, []).append(page)
        for duplicate_pages in by_title.values():
            if len(duplicate_pages) > 1:
                paths = [page.path for page in duplicate_pages]
                for page in duplicate_pages:
                    issues.append(
                        KnowledgeBaseLintIssue(
                            issueType="duplicate_title",
                            severity="warning",
                            path=page.path,
                            details={"paths": paths},
                        )
                    )
        for duplicate_pages in by_slug.values():
            if len(duplicate_pages) > 1:
                paths = [page.path for page in duplicate_pages]
                for page in duplicate_pages:
                    issues.append(
                        KnowledgeBaseLintIssue(
                            issueType="duplicate_slug",
                            severity="warning",
                            path=page.path,
                            details={"paths": paths},
                        )
                    )

    def _parse_page(self, root: Path, path: Path) -> _LintPage:
        raw = path.read_text(encoding="utf-8")
        frontmatter, body, has_frontmatter = self._parse_frontmatter(raw)
        relative_path = path.relative_to(root).as_posix()
        page_id = self._page_id(relative_path)
        title = str(frontmatter.get("title") or self._first_heading(body) or path.stem)
        return _LintPage(
            path=relative_path,
            page_id=page_id,
            title=title,
            slug=Path(page_id).name,
            raw=raw,
            body=body,
            frontmatter=frontmatter,
            has_frontmatter=has_frontmatter,
            wikilinks=self._extract_wikilinks(body),
            sources=self._normalize_sources(frontmatter.get("sources")),
        )

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str, bool]:
        if not raw.startswith("---\n"):
            return {}, raw, False
        frontmatter_raw, separator, body = raw[4:].partition("\n---\n")
        if not separator:
            return {}, raw, False
        parsed = yaml.safe_load(frontmatter_raw) or {}
        return (parsed if isinstance(parsed, dict) else {}), body, isinstance(parsed, dict)

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
    def _page_aliases(cls, pages: list[_LintPage]) -> dict[str, str]:
        aliases = {}
        for page in pages:
            aliases[page.page_id] = page.page_id
            aliases[page.page_id.removeprefix("wiki/")] = page.page_id
            aliases[Path(page.page_id).name] = page.page_id
        return aliases

    @staticmethod
    def _page_id(relative_path: str) -> str:
        return relative_path[:-3] if relative_path.endswith(".md") else relative_path

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root
