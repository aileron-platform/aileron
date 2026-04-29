"""Knowledge base source import and normalization service."""

from __future__ import annotations

import csv
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


@dataclass(frozen=True)
class KnowledgeBaseNormalizationResult:
    source_path: str
    normalized_text_path: str
    metadata_path: str
    source_hash: str
    normalized_hash: str
    skipped: bool
    extractor: str


class KnowledgeBaseSourceService:
    """Import raw sources and normalize them into text and metadata."""

    RAW_ROOT = "raw"
    RAW_SUBDIRECTORIES = {"sources", "uploads", "clipped", "assets"}
    TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".rst"}
    CSV_EXTENSIONS = {".csv"}
    PDF_EXTENSIONS = {".pdf"}
    OFFICE_EXTENSIONS = {".docx", ".pptx", ".xlsx"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}

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
        target_subdir: str = "uploads",
        target_name: str | None = None,
        overwrite: bool = False,
    ) -> KnowledgeBaseSourceImportResult:
        """Copy a local file into the KB raw source area."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        if not source_file.is_file():
            raise FileManagementException(
                code="FILE_NOT_FOUND",
                message="Source file does not exist",
                details={"path": str(source_file)},
                status_code=404,
            )

        raw_path = self._raw_relative_path(target_subdir, target_name or source_file.name)
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
        source_relative_path = f"raw/clipped/{safe_slug}.md"
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

        return KnowledgeBaseWebClipImportResult(
            path="/" + source_relative_path,
            asset_paths=["/" + relative_path for _, _, relative_path in asset_targets],
            size=after_size,
            source_hash=self._hash_file(source_target),
        )

    def normalize_source(
        self,
        *,
        user_id: str,
        kb_id: str,
        source_path: str,
        force: bool = False,
    ) -> KnowledgeBaseNormalizationResult:
        """Normalize a raw source into text plus metadata files."""
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="editor")
        self._ensure_wiki(kb)
        raw_relative_path = self._validate_raw_source_path(source_path)
        source = self._resolve_path(kb.id, raw_relative_path)
        if not source.is_file():
            raise FileManagementException(
                code="FILE_NOT_FOUND",
                message="Source file does not exist",
                details={"path": "/" + raw_relative_path},
                status_code=404,
            )

        source_hash = self._hash_file(source)
        cache = self._read_cache(kb.id)
        cache_key = raw_relative_path
        cached = cache.get(cache_key)
        normalized_text_path = self._normalized_text_path(raw_relative_path)
        metadata_path = self._metadata_path(raw_relative_path)
        if not force and cached and cached.get("sourceHash") == source_hash:
            return KnowledgeBaseNormalizationResult(
                source_path="/" + raw_relative_path,
                normalized_text_path="/" + normalized_text_path,
                metadata_path="/" + metadata_path,
                source_hash=source_hash,
                normalized_hash=cached.get("normalizedHash", ""),
                skipped=True,
                extractor=cached.get("extractor", "cache"),
            )

        text, metadata = self._extract(source, raw_relative_path)
        normalized_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        metadata.update(
            {
                "sourcePath": "/" + raw_relative_path,
                "sourceHash": source_hash,
                "normalizedHash": normalized_hash,
                "normalizedTextPath": "/" + normalized_text_path,
                "normalizedAt": datetime.now(timezone.utc).isoformat(),
            }
        )

        delta = self._write_normalized_files(
            kb,
            normalized_text_path=normalized_text_path,
            text=text,
            metadata_path=metadata_path,
            metadata=metadata,
        )
        if delta:
            self._update_kb_size(kb, delta)

        cache[cache_key] = {
            "sourceHash": source_hash,
            "normalizedHash": normalized_hash,
            "normalizedTextPath": "/" + normalized_text_path,
            "metadataPath": "/" + metadata_path,
            "extractor": metadata.get("extractor", "unknown"),
            "updatedAt": metadata["normalizedAt"],
        }
        self._write_cache(kb.id, cache)

        return KnowledgeBaseNormalizationResult(
            source_path="/" + raw_relative_path,
            normalized_text_path="/" + normalized_text_path,
            metadata_path="/" + metadata_path,
            source_hash=source_hash,
            normalized_hash=normalized_hash,
            skipped=False,
            extractor=metadata.get("extractor", "unknown"),
        )

    def _extract(self, source: Path, raw_relative_path: str) -> tuple[str, dict[str, Any]]:
        extension = source.suffix.lower()
        if extension in self.TEXT_EXTENSIONS:
            return self._extract_text(source), self._metadata(raw_relative_path, extractor="text")
        if extension in self.CSV_EXTENSIONS:
            return self._extract_csv(source), self._metadata(raw_relative_path, extractor="csv")
        if extension in self.PDF_EXTENSIONS:
            return self._extract_pdf(source), self._metadata(raw_relative_path, extractor="pdf")
        if extension in self.OFFICE_EXTENSIONS:
            metadata = self._metadata(raw_relative_path, extractor="office-placeholder")
            metadata["status"] = "unsupported"
            metadata["note"] = "Office document normalization is not available in this runtime."
            return "", metadata
        if extension in self.IMAGE_EXTENSIONS:
            metadata = self._metadata(raw_relative_path, extractor="image-placeholder")
            metadata["status"] = "metadata-only"
            metadata["note"] = "Image OCR and caption extraction are reserved for a later extractor."
            return "", metadata
        raise FileManagementException(
            code="INVALID_FILE_TYPE",
            message=f"{KB_SOURCE_UNSUPPORTED_EXTENSION_MESSAGE}: {extension}",
            details={"path": "/" + raw_relative_path, "extension": extension},
            status_code=400,
        )

    def _extract_text(self, source: Path) -> str:
        try:
            return source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return source.read_text(encoding="latin-1")

    def _extract_csv(self, source: Path) -> str:
        rows: list[str] = []
        with source.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            for row in reader:
                rows.append(" | ".join(cell.strip() for cell in row))
        return "\n".join(rows) + ("\n" if rows else "")

    def _extract_pdf(self, source: Path) -> str:
        try:
            from pypdf import PdfReader  # type: ignore
        except ImportError:
            return ""

        reader = PdfReader(str(source))
        pages: list[str] = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append(f"# Page {index}\n\n{page_text.strip()}")
        return "\n\n".join(pages).strip() + ("\n" if pages else "")

    def _metadata(self, raw_relative_path: str, *, extractor: str) -> dict[str, Any]:
        return {
            "extractor": extractor,
            "sourceType": Path(raw_relative_path).suffix.lower().lstrip(".") or "unknown",
            "sourceName": Path(raw_relative_path).name,
        }

    def _write_normalized_files(
        self,
        kb: db_models.KnowledgeBase,
        *,
        normalized_text_path: str,
        text: str,
        metadata_path: str,
        metadata: dict[str, Any],
    ) -> int:
        text_target = self._resolve_path(kb.id, normalized_text_path)
        metadata_target = self._resolve_path(kb.id, metadata_path)
        before_size = self._path_size(text_target) + self._path_size(metadata_target)
        metadata_content = json.dumps(metadata, ensure_ascii=False, indent=2) + "\n"
        after_size = len(text.encode("utf-8")) + len(metadata_content.encode("utf-8"))
        delta = after_size - before_size
        self._check_quota(kb, delta)

        text_target.parent.mkdir(parents=True, exist_ok=True)
        metadata_target.parent.mkdir(parents=True, exist_ok=True)
        text_target.write_text(text, encoding="utf-8")
        metadata_target.write_text(metadata_content, encoding="utf-8")

        return delta

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

    def _normalized_text_path(self, raw_relative_path: str) -> str:
        return "normalized/text/" + self._normalized_stem(raw_relative_path) + ".md"

    def _metadata_path(self, raw_relative_path: str) -> str:
        return "normalized/metadata/" + self._normalized_stem(raw_relative_path) + ".json"

    def _normalized_stem(self, raw_relative_path: str) -> str:
        source = Path(raw_relative_path)
        digest = hashlib.sha256(raw_relative_path.encode("utf-8")).hexdigest()[:12]
        return f"{source.stem}-{digest}"

    def _cache_path(self, kb_id: str) -> Path:
        return self._kb_root(kb_id) / ".aileron-kb" / "ingest-cache.json"

    def _read_cache(self, kb_id: str) -> dict[str, Any]:
        path = self._cache_path(kb_id)
        if not path.exists():
            return {}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _write_cache(self, kb_id: str, cache: dict[str, Any]) -> None:
        path = self._cache_path(kb_id)
        before_size = self._path_size(path)
        content = json.dumps(cache, ensure_ascii=False, indent=2) + "\n"
        after_size = len(content.encode("utf-8"))
        delta = after_size - before_size
        kb = self.db.get(db_models.KnowledgeBase, kb_id)
        if kb is not None:
            self._check_quota(kb, delta)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if kb is not None:
            self._update_kb_size(kb, delta)

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
