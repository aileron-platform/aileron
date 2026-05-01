"""Knowledge base wiki browse and index service."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import FileManagementException, InvalidPathException
from app.models import (
    KnowledgeBaseWikiGroup,
    KnowledgeBaseWikiPageRef,
    KnowledgeBaseWikiPageResolved,
    KnowledgeBaseWikiPageResponse,
    KnowledgeBaseWikiPagesResponse,
    KnowledgeBaseWikiPageSummary,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

KB_WIKI_PAGE_PATH_INVALID_REASON = "Invalid wiki page path"
KB_WIKI_PAGE_PATH_INVALID_CODE = "KB_WIKI_PAGE_PATH_INVALID"

_BASE_TYPES = ("overview", "entity", "concept", "source", "query", "synthesis", "comparison")
_EXCLUDED_LIST_PATHS = {"wiki/index.md", "wiki/log.md"}
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class WikiIndex:
    generated_at: str
    slug_to_path: dict[str, str]
    by_type: dict[str, list[dict[str, Any]]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generatedAt": self.generated_at,
            "slugToPath": self.slug_to_path,
            "byType": self.by_type,
        }


class WikiIndexBuilder:
    """Build the reverse map used by wiki browse endpoints."""

    def build(self, kb_root: Path) -> WikiIndex:
        wiki_root = kb_root / "wiki"
        pages = []
        slug_to_path: dict[str, str] = {}
        if wiki_root.exists():
            for path in sorted(wiki_root.rglob("*.md")):
                if not path.is_file():
                    continue
                page = self._summarize_page(kb_root, path)
                pages.append(page)
                relative_path = page["path"]
                for alias in self._aliases(relative_path):
                    slug_to_path.setdefault(alias, relative_path)

        by_type: dict[str, list[dict[str, Any]]] = {}
        for page in pages:
            if page["path"] in _EXCLUDED_LIST_PATHS:
                continue
            by_type.setdefault(page["type"], []).append(page)
        for items in by_type.values():
            items.sort(key=lambda item: (str(item.get("title", "")).casefold(), str(item.get("path", ""))))

        return WikiIndex(
            generated_at=datetime.now(timezone.utc).isoformat(),
            slug_to_path=slug_to_path,
            by_type=by_type,
        )

    def write(self, kb_root: Path) -> WikiIndex:
        index = self.build(kb_root)
        target = kb_root / ".aileron-kb" / "wiki-index.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".wiki-index-", suffix=".json", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(index.to_dict(), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return index

    def _summarize_page(self, kb_root: Path, path: Path) -> dict[str, Any]:
        frontmatter, body = _parse_markdown(path.read_text(encoding="utf-8"))
        title = str(frontmatter.get("title") or _first_heading(body) or path.stem)
        page_type = str(frontmatter.get("type") or _type_from_path(path))
        relative_path = path.relative_to(kb_root).as_posix()
        return {
            "path": relative_path,
            "title": title,
            "type": page_type,
            "tags": _string_list(frontmatter.get("tags")),
            "origin": _optional_string(frontmatter.get("origin")),
            "description": _optional_string(frontmatter.get("description")),
        }

    @staticmethod
    def _aliases(relative_path: str) -> list[str]:
        path = relative_path.strip("/")
        stem_path = path[:-3] if path.endswith(".md") else path
        without_wiki = stem_path.removeprefix("wiki/")
        basename = Path(stem_path).name
        return list(dict.fromkeys([path, stem_path, without_wiki, basename]))


class KnowledgeBaseWikiBrowseService:
    """Read wiki pages and resolved references for a KB."""

    INDEX_PATH = ".aileron-kb/wiki-index.json"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)
        self.index_builder = WikiIndexBuilder()

    def list_pages(self, *, user_id: str, kb_id: str) -> KnowledgeBaseWikiPagesResponse:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_wiki(kb)
        root = self._kb_root(kb.id)
        index = self._read_fresh_index(root) or self.index_builder.write(root)
        group_types = list(dict.fromkeys([*_BASE_TYPES, *sorted(index.by_type)]))
        groups = [
            KnowledgeBaseWikiGroup(
                type=page_type,
                labelKey=f"knowledgeBase.wiki.types.{page_type}",
                items=[
                    KnowledgeBaseWikiPageSummary(
                        path=item["path"],
                        title=item["title"],
                        type=item["type"],
                        tags=_string_list(item.get("tags")),
                        origin=_optional_string(item.get("origin")),
                        description=_optional_string(item.get("description")),
                    )
                    for item in index.by_type.get(page_type, [])
                    if item.get("path") not in _EXCLUDED_LIST_PATHS
                ],
            )
            for page_type in group_types
        ]
        return KnowledgeBaseWikiPagesResponse(groups=groups)

    def get_page(self, *, user_id: str, kb_id: str, path: str) -> KnowledgeBaseWikiPageResponse:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_wiki(kb)
        root = self._kb_root(kb.id)
        normalized = self._validate_wiki_page_path(path)
        target = root / normalized
        if not target.exists() or not target.is_file():
            raise FileManagementException(
                code="FILE_NOT_FOUND",
                message="Wiki page does not exist",
                details={"path": normalized},
                status_code=404,
            )
        frontmatter, body = _parse_markdown(target.read_text(encoding="utf-8"))
        index = self._read_fresh_index(root) or self.index_builder.write(root)
        return KnowledgeBaseWikiPageResponse(
            frontmatter=frontmatter,
            body=body,
            resolved=KnowledgeBaseWikiPageResolved(
                sources=self._resolve_sources(root, frontmatter.get("sources")),
                related=self._resolve_related(index, body),
            ),
        )

    def rebuild_index(self, *, kb_id: str) -> WikiIndex:
        return self.index_builder.write(self._kb_root(kb_id))

    def _read_fresh_index(self, root: Path) -> WikiIndex | None:
        path = root / self.INDEX_PATH
        if not path.exists() or self._index_is_stale(root, path):
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        slug_to_path = payload.get("slugToPath")
        by_type = payload.get("byType")
        if not isinstance(slug_to_path, dict) or not isinstance(by_type, dict):
            return None
        return WikiIndex(
            generated_at=str(payload.get("generatedAt") or ""),
            slug_to_path={str(key): str(value) for key, value in slug_to_path.items()},
            by_type={
                str(key): [item for item in value if isinstance(item, dict)]
                for key, value in by_type.items()
                if isinstance(value, list)
            },
        )

    @staticmethod
    def _index_is_stale(root: Path, index_path: Path) -> bool:
        index_mtime = index_path.stat().st_mtime
        wiki_root = root / "wiki"
        if not wiki_root.exists():
            return False
        return any(path.is_file() and path.stat().st_mtime > index_mtime for path in wiki_root.rglob("*.md"))

    def _resolve_related(self, index: WikiIndex, body: str) -> list[KnowledgeBaseWikiPageRef]:
        related = []
        seen = set()
        titles = self._title_by_path(index)
        for match in _WIKILINK_RE.finditer(body):
            raw = match.group(1).strip()
            slug = _normalize_wikilink(raw)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            path = index.slug_to_path.get(slug)
            related.append(
                KnowledgeBaseWikiPageRef(
                    slug=slug,
                    path=path,
                    title=titles.get(path or ""),
                    exists=path is not None,
                )
            )
        return related

    @staticmethod
    def _title_by_path(index: WikiIndex) -> dict[str, str]:
        titles = {}
        for items in index.by_type.values():
            for item in items:
                path = item.get("path")
                title = item.get("title")
                if isinstance(path, str) and isinstance(title, str):
                    titles[path] = title
        return titles

    def _resolve_sources(self, root: Path, value: Any) -> list[KnowledgeBaseWikiPageRef]:
        refs = []
        for source in _string_list(value):
            normalized = source.strip().lstrip("/")
            if normalized.startswith("raw/sources/"):
                relative = normalized
            else:
                relative = f"raw/sources/{normalized}"
            exists = self._safe_child(root, relative).is_file() if self._is_safe_relative(relative) else False
            refs.append(KnowledgeBaseWikiPageRef(name=source, path=relative, exists=exists))
        return refs

    def _validate_wiki_page_path(self, path: str) -> str:
        normalized = (path or "").strip().lstrip("/")
        if (
            not normalized
            or not normalized.startswith("wiki/")
            or not normalized.endswith(".md")
            or ".." in Path(normalized).parts
        ):
            raise FileManagementException(
                code=KB_WIKI_PAGE_PATH_INVALID_CODE,
                message=KB_WIKI_PAGE_PATH_INVALID_REASON,
                details={"path": path},
                status_code=400,
            )
        return normalized

    @staticmethod
    def _is_safe_relative(relative_path: str) -> bool:
        return bool(relative_path) and not relative_path.startswith("/") and ".." not in Path(relative_path).parts

    @staticmethod
    def _safe_child(root: Path, relative_path: str) -> Path:
        target = root / relative_path
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise InvalidPathException(relative_path, KB_WIKI_PAGE_PATH_INVALID_REASON)
        return target

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ensure_wiki(self, kb: Any) -> None:
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)


def _parse_markdown(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw
    frontmatter_raw, separator, body = raw[4:].partition("\n---\n")
    if not separator:
        return {}, raw
    parsed = yaml.safe_load(frontmatter_raw) or {}
    return (parsed if isinstance(parsed, dict) else {}), body.lstrip("\n")


def _first_heading(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _type_from_path(path: Path) -> str:
    parent = path.parent.name
    return parent[:-1] if parent.endswith("s") and parent != "sources" else parent


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _optional_string(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _normalize_wikilink(value: str) -> str:
    target = value.split("|", 1)[0].split("#", 1)[0].strip().strip("/")
    if target.endswith(".md"):
        target = target[:-3]
    if target.startswith("wiki/"):
        target = target[5:]
    return target
