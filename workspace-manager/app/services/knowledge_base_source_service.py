"""Knowledge base source import service."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import FileManagementException, InvalidPathException
from app.db import models as db_models
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.knowledge_base_wiki_service import KnowledgeBaseWikiService

KB_SOURCE_PATH_TRAVERSAL_REASON = "Invalid source path detected"
KB_SOURCE_UNSUPPORTED_EXTENSION_MESSAGE = "Unsupported source extension"
KB_SOURCE_QUOTA_EXCEEDED_MESSAGE = "Knowledge base storage quota exceeded"
KB_SOURCE_OWNER_QUOTA_EXCEEDED_MESSAGE = "User knowledge base total storage quota exceeded"
_CLIP_SLUG_SANITIZER = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class KnowledgeBaseSourceImportResult:
    path: str
    size: int
    source_hash: str


@dataclass(frozen=True)
class KnowledgeBaseWebClipImportResult:
    path: str
    asset_paths: list[str]
    size: int
    source_hash: str


class KnowledgeBaseSourceService:
    """Import raw sources into the KB raw source area."""

    RAW_ROOT = "raw"
    RAW_SUBDIRECTORIES = {"sources", "assets"}

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.kb_service = KnowledgeBaseService(db)
        self.wiki_service = KnowledgeBaseWikiService(db)
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def import_file(
        self,
        *,
        user_id: str,
        kb_id: str,
        source_file: Path,
        target_name: str | None = None,
        overwrite: bool = False,
        origin: str = "upload",
    ) -> KnowledgeBaseSourceImportResult:
        """Copy a local file into raw/sources/."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        if not source_file.is_file():
            raise FileManagementException(
                code="FILE_NOT_FOUND",
                message="Source file does not exist",
                details={"path": str(source_file)},
                status_code=404,
            )

        raw_path = self._raw_relative_path("sources", target_name or source_file.name)
        extension = Path(raw_path).suffix.lower()
        self._ensure_allowed_extension(extension, raw_path)
        target = self._resolve_path(kb.id, raw_path)
        if target.exists() and not overwrite:
            raise FileManagementException(
                code="FILE_ALREADY_EXISTS",
                message="Source file already exists",
                details={"path": raw_path},
                status_code=409,
            )

        source_size = source_file.stat().st_size
        replaced_size = target.stat().st_size if target.exists() else 0
        delta = source_size - replaced_size
        self._check_quota(kb, delta)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, target)
        self._update_kb_size(kb, delta)
        self._record_source_metadata(kb.id, raw_path, origin=origin)

        return KnowledgeBaseSourceImportResult(
            path="/" + raw_path,
            size=source_size,
            source_hash=self._hash_file(target),
        )

    def import_web_clip(
        self,
        *,
        user_id: str,
        kb_id: str,
        title: str,
        markdown: str,
        assets: dict[str, bytes] | None = None,
        clip_slug: str | None = None,
        overwrite: bool = False,
    ) -> KnowledgeBaseWebClipImportResult:
        """Import a clipped web page as Markdown with optional raw assets."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)

        safe_slug = self._clip_slug(clip_slug or title)
        source_relative_path = f"raw/sources/{safe_slug}.md"
        source_target = self._resolve_path(kb.id, source_relative_path)
        if source_target.exists() and not overwrite:
            raise FileManagementException(
                code="FILE_ALREADY_EXISTS",
                message="Web clip already exists",
                details={"path": "/" + source_relative_path},
                status_code=409,
            )

        asset_payloads = assets or {}
        asset_targets: list[tuple[Path, bytes, str]] = []
        for asset_name, content in asset_payloads.items():
            asset_relative_path = self._asset_relative_path(safe_slug, asset_name)
            extension = Path(asset_relative_path).suffix.lower()
            self._ensure_allowed_extension(extension, asset_relative_path)
            asset_target = self._resolve_path(kb.id, asset_relative_path)
            if asset_target.exists() and not overwrite:
                raise FileManagementException(
                    code="FILE_ALREADY_EXISTS",
                    message="Web clip asset already exists",
                    details={"path": "/" + asset_relative_path},
                    status_code=409,
                )
            asset_targets.append((asset_target, content, asset_relative_path))

        frontmatter = {
            "title": title,
            "type": "web-clip",
            "assets": ["/" + relative_path for _, _, relative_path in asset_targets],
        }
        content = self._web_clip_markdown(frontmatter, markdown)
        before_size = self._path_size(source_target) + sum(self._path_size(target) for target, _, _ in asset_targets)
        after_size = len(content.encode("utf-8")) + sum(len(payload) for _, payload, _ in asset_targets)
        delta = after_size - before_size
        self._check_quota(kb, delta)

        source_target.parent.mkdir(parents=True, exist_ok=True)
        source_target.write_text(content, encoding="utf-8")
        for asset_target, payload, _ in asset_targets:
            asset_target.parent.mkdir(parents=True, exist_ok=True)
            asset_target.write_bytes(payload)
        self._update_kb_size(kb, delta)
        self._record_source_metadata(kb.id, source_relative_path, origin="clipped")

        return KnowledgeBaseWebClipImportResult(
            path="/" + source_relative_path,
            asset_paths=["/" + relative_path for _, _, relative_path in asset_targets],
            size=after_size,
            source_hash=self._hash_file(source_target),
        )

    def _ensure_wiki(self, kb: db_models.KnowledgeBase) -> None:
        self.wiki_service.storage_root = self.storage_root
        self.wiki_service.initialize(kb)

    def _raw_relative_path(self, subdir: str, file_name: str) -> str:
        if subdir not in self.RAW_SUBDIRECTORIES:
            raise InvalidPathException(subdir, KB_SOURCE_PATH_TRAVERSAL_REASON)
        safe_name = self._validate_path(file_name)
        if "/" in safe_name:
            raise InvalidPathException(file_name, KB_SOURCE_PATH_TRAVERSAL_REASON)
        return f"{self.RAW_ROOT}/{subdir}/{safe_name}"

    def _asset_relative_path(self, clip_slug: str, asset_name: str) -> str:
        safe_name = self._validate_path(asset_name)
        if "/" in safe_name:
            raise InvalidPathException(asset_name, KB_SOURCE_PATH_TRAVERSAL_REASON)
        return f"{self.RAW_ROOT}/assets/{clip_slug}/{safe_name}"

    def _clip_slug(self, value: str) -> str:
        normalized = _CLIP_SLUG_SANITIZER.sub("-", value.strip().lower()).strip("-")
        if not normalized:
            normalized = "web-clip"
        return normalized[:96]

    def _web_clip_markdown(self, frontmatter: dict[str, Any], markdown: str) -> str:
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {json.dumps(item, ensure_ascii=False)}")
            else:
                lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        lines.extend(["---", "", markdown.rstrip(), ""])
        return "\n".join(lines)

    def _validate_raw_source_path(self, source_path: str) -> str:
        normalized = self._validate_path(source_path)
        parts = Path(normalized).parts
        if len(parts) < 3 or parts[0] != self.RAW_ROOT or parts[1] not in self.RAW_SUBDIRECTORIES:
            raise InvalidPathException(source_path, KB_SOURCE_PATH_TRAVERSAL_REASON)
        return normalized

    def _validate_path(self, path: str) -> str:
        normalized = (path or "").strip().lstrip("/")
        if not normalized or normalized.startswith("/") or ".." in Path(normalized).parts:
            raise InvalidPathException(path, KB_SOURCE_PATH_TRAVERSAL_REASON)
        return normalized

    def _ensure_allowed_extension(self, extension: str, path: str) -> None:
        if extension and extension not in self.settings.KB_ALLOWED_EXTENSIONS:
            raise FileManagementException(
                code="INVALID_FILE_TYPE",
                message=f"{KB_SOURCE_UNSUPPORTED_EXTENSION_MESSAGE}: {extension}",
                details={"path": "/" + path, "extension": extension},
                status_code=400,
            )

    def _sources_metadata_path(self, kb_id: str) -> Path:
        return self._kb_root(kb_id) / ".aileron-kb" / "sources-metadata.json"

    def _record_source_metadata(self, kb_id: str, relative_path: str, *, origin: str) -> None:
        meta_path = self._sources_metadata_path(kb_id)
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            if not isinstance(data, dict):
                data = {}
        except json.JSONDecodeError:
            data = {}
        data[relative_path] = {
            "origin": origin,
            "importedAt": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        target = root / self._validate_path(relative_path)
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise InvalidPathException(relative_path, KB_SOURCE_PATH_TRAVERSAL_REASON)
        return resolved

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _hash_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _path_size(self, path: Path) -> int:
        return path.stat().st_size if path.exists() and path.is_file() else 0

    def _check_quota(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        if delta_bytes <= 0:
            return
        per_kb_quota = kb.quota_bytes or self.settings.DEFAULT_KB_QUOTA_BYTES
        if kb.current_size_bytes + delta_bytes > per_kb_quota:
            raise FileManagementException(
                code="KB_QUOTA_EXCEEDED",
                message=KB_SOURCE_QUOTA_EXCEEDED_MESSAGE,
                details={
                    "kbId": kb.id,
                    "currentSizeBytes": kb.current_size_bytes,
                    "deltaBytes": delta_bytes,
                    "quotaBytes": per_kb_quota,
                },
                status_code=409,
            )

        owner_total = (
            self.db.scalar(
                select(func.coalesce(func.sum(db_models.KnowledgeBase.current_size_bytes), 0)).where(
                    db_models.KnowledgeBase.owner_id == kb.owner_id,
                    db_models.KnowledgeBase.tombstoned_at.is_(None),
                )
            )
            or 0
        )
        if owner_total + delta_bytes > self.settings.DEFAULT_USER_KB_QUOTA_BYTES:
            raise FileManagementException(
                code="USER_KB_QUOTA_EXCEEDED",
                message=KB_SOURCE_OWNER_QUOTA_EXCEEDED_MESSAGE,
                details={
                    "ownerId": kb.owner_id,
                    "currentTotalBytes": owner_total,
                    "deltaBytes": delta_bytes,
                    "quotaBytes": self.settings.DEFAULT_USER_KB_QUOTA_BYTES,
                },
                status_code=409,
            )

    def _update_kb_size(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        if delta_bytes == 0:
            return
        kb.current_size_bytes = max(0, (kb.current_size_bytes or 0) + delta_bytes)
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)
