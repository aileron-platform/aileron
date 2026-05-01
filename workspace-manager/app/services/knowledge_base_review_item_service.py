"""Knowledge base review item CRUD service."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

import yaml
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import FileManagementException
from app.db import models as db_models
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

ReviewItemStatus = Literal["open", "resolved", "dismissed"]

_VALID_REVIEW_TYPES = frozenset(
    ["contradiction", "duplicate", "missing_page", "suggestion", "confirm", "unreadable_source"]
)


class KnowledgeBaseReviewItemService:
    """CRUD for .aileron-kb/reviews.json review items."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)

    # ── public API ───────────────────────────────────────────────────────────

    def list_items(
        self,
        *,
        user_id: str,
        kb_id: str,
        status: ReviewItemStatus | None = None,
    ) -> list[dict]:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)
        items = self._read_items(kb_id)
        if status is not None:
            items = [it for it in items if it.get("status") == status]
        return sorted(items, key=lambda x: x.get("createdAt", ""), reverse=True)

    def get_item(self, *, user_id: str, kb_id: str, item_id: str) -> dict:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_wiki(kb)
        return self._get_item(kb_id, item_id)

    def resolve(self, *, user_id: str, kb_id: str, item_id: str) -> dict:
        return self._set_status(user_id=user_id, kb_id=kb_id, item_id=item_id, new_status="resolved")

    def dismiss(self, *, user_id: str, kb_id: str, item_id: str) -> dict:
        return self._set_status(user_id=user_id, kb_id=kb_id, item_id=item_id, new_status="dismissed")

    def convert_to_query(
        self,
        *,
        user_id: str,
        kb_id: str,
        item_id: str,
        title: str,
        slug: str | None = None,
    ) -> dict:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        item = self._get_item(kb_id, item_id)

        safe_slug = self._slugify(slug or title)
        query_path = f"wiki/queries/{safe_slug}.md"
        target = self._resolve_path(kb_id, query_path)
        if target.exists():
            raise FileManagementException(
                code="FILE_ALREADY_EXISTS",
                message="A query page with this slug already exists",
                details={"path": query_path},
                status_code=409,
            )

        context = item.get("context", "")
        frontmatter = yaml.safe_dump(
            {"title": title, "type": "query", "sources": []},
            allow_unicode=True,
            sort_keys=False,
        ).strip()
        heading = self._single_line(title)
        detail = self._single_line(str(item.get("detail", "")))
        content = (
            f"---\n{frontmatter}\n---\n\n"
            f"# {heading}\n\n"
            f"*Converted from review item: {detail}*\n\n"
        )
        if context:
            content += f"{context}\n\n"
        content += f"**Related page:** [[{item.get('pagePath', '')}]]\n"

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        items = self._read_items(kb_id)
        now = datetime.now(timezone.utc).isoformat()
        for it in items:
            if it.get("id") == item_id:
                it["status"] = "resolved"
                it["resolvedAt"] = now
                it["resolvedBy"] = user_id
                it["queryPage"] = query_path
                break
        self._write_items(kb_id, items)
        return next((it for it in items if it.get("id") == item_id), item)

    def append_from_ingest(
        self,
        *,
        kb_id: str,
        review_blocks: list,
    ) -> list[dict]:
        """Append parsed review blocks from an ingest run to reviews.json."""
        items = self._read_items(kb_id)
        now = datetime.now(timezone.utc).isoformat()
        new_items: list[dict] = []
        for block in review_blocks:
            if hasattr(block, "type"):
                review_type = block.type
                page_path = block.page_path
                detail = block.detail
                context = getattr(block, "context", "")
            else:
                review_type = block.get("type", "")
                page_path = block.get("page_path", "")
                detail = block.get("detail", "")
                context = block.get("context", "")
            if review_type not in _VALID_REVIEW_TYPES:
                continue
            item: dict = {
                "id": str(uuid4()),
                "type": review_type,
                "pagePath": page_path,
                "detail": detail,
                "context": context,
                "status": "open",
                "createdAt": now,
                "resolvedAt": None,
                "resolvedBy": None,
            }
            items.append(item)
            new_items.append(item)
        self._write_items(kb_id, items)
        return new_items

    def count_by_status(self, *, kb_id: str) -> dict[str, int]:
        items = self._read_items(kb_id)
        counts: dict[str, int] = {"open": 0, "resolved": 0, "dismissed": 0}
        for it in items:
            s = it.get("status", "open")
            if s in counts:
                counts[s] += 1
        return counts

    # ── private helpers ──────────────────────────────────────────────────────

    def _set_status(
        self,
        *,
        user_id: str,
        kb_id: str,
        item_id: str,
        new_status: ReviewItemStatus,
    ) -> dict:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        items = self._read_items(kb_id)
        now = datetime.now(timezone.utc).isoformat()
        found: dict | None = None
        for it in items:
            if it.get("id") == item_id:
                it["status"] = new_status
                it["resolvedAt"] = now
                it["resolvedBy"] = user_id
                found = it
                break
        if found is None:
            raise FileManagementException(
                code="REVIEW_ITEM_NOT_FOUND",
                message="Review item not found",
                details={"itemId": item_id},
                status_code=404,
            )
        self._write_items(kb_id, items)
        return found

    def _get_item(self, kb_id: str, item_id: str) -> dict:
        items = self._read_items(kb_id)
        for it in items:
            if it.get("id") == item_id:
                return it
        raise FileManagementException(
            code="REVIEW_ITEM_NOT_FOUND",
            message="Review item not found",
            details={"itemId": item_id},
            status_code=404,
        )

    def _reviews_path(self, kb_id: str) -> Path:
        return self._kb_root(kb_id) / ".aileron-kb" / "reviews.json"

    def _read_items(self, kb_id: str) -> list[dict]:
        path = self._reviews_path(kb_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def _write_items(self, kb_id: str, items: list[dict]) -> None:
        path = self._reviews_path(kb_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(items, ensure_ascii=False, indent=2) + "\n"
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".reviews-tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _ensure_wiki(self, kb: db_models.KnowledgeBase) -> None:
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        target = root / relative_path.strip().lstrip("/")
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise FileManagementException(
                code="REVIEW_ITEM_PATH_INVALID",
                message="Path is outside KB root",
                details={"path": relative_path},
                status_code=400,
            )
        return resolved

    @staticmethod
    def _slugify(value: str) -> str:
        import re as _re
        slug = _re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
        return slug[:96] or "query"

    @staticmethod
    def _single_line(value: str) -> str:
        return " ".join(value.split())
