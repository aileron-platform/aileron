"""Knowledge base file service."""

from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import (
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileContentResponse,
    FileManagementException,
    FileNode,
    FileNotFoundException,
    FileTooLargeException,
    FileTreeResponse,
    InvalidPathException,
)
from app.db import models as db_models
from app.models import FileUploadResponse, UploadedFileInfo
from app.services.knowledge_base_service import KnowledgeBaseAccessDeniedError, KnowledgeBaseService

logger = logging.getLogger(__name__)

KB_CONTENT_CONFLICT_MESSAGE = "File content version conflict"
KB_TOO_MANY_UPLOADS_MESSAGE = "Number of uploaded files exceeds limit"
KB_UPLOAD_SUCCESS_MESSAGE = "File upload complete"
KB_MISSING_FILENAME_REASON = "Missing filename"
KB_NOT_A_FILE_REASON = "Not a file"
KB_PATH_TRAVERSAL_REASON = "Invalid path detected"
KB_INVALID_FILE_TYPE_MESSAGE = "Unsupported file extension"
KB_QUOTA_EXCEEDED_MESSAGE = "Knowledge base storage quota exceeded"
KB_OWNER_QUOTA_EXCEEDED_MESSAGE = "User knowledge base total storage quota exceeded"


class KnowledgeBaseFileService:
    """Handle knowledge base file and folder operations."""

    SKIP_DIRECTORIES = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        ".next",
    }
    MAX_UPLOAD_FILES = 50

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.kb_service = KnowledgeBaseService(db)
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def get_tree(
        self,
        *,
        user_id: str,
        kb_id: str,
        path: str = "/",
        include_hidden: bool = False,
        max_depth: int = 1,
    ) -> FileTreeResponse:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        fs_path = self._resolve_path(kb.id, path)
        if not fs_path.exists():
            fs_path.mkdir(parents=True, exist_ok=True)
        nodes = self._scan_directory(
            fs_path,
            base_path=self._kb_root(kb.id),
            include_hidden=include_hidden,
            max_depth=max_depth,
        )
        return FileTreeResponse(path=path, scope=self._scope(kb.id), nodes=nodes, total=len(nodes))

    def read_file(self, *, user_id: str, kb_id: str, path: str) -> FileContentResponse:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        fs_path = self._resolve_path(kb.id, path)
        if not fs_path.exists():
            raise FileNotFoundException(path, self._scope(kb.id))
        if not fs_path.is_file():
            raise InvalidPathException(path, KB_NOT_A_FILE_REASON)

        file_size = fs_path.stat().st_size
        if file_size > self.settings.KB_SINGLE_FILE_SIZE_LIMIT:
            raise FileTooLargeException(path, file_size, self.settings.KB_SINGLE_FILE_SIZE_LIMIT)

        try:
            content = fs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = fs_path.read_text(encoding="latin-1")

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return FileContentResponse(
            path=path,
            scope=self._scope(kb.id),
            content=content,
            size=file_size,
            updatedAt=datetime.fromtimestamp(fs_path.stat().st_mtime, tz=timezone.utc).isoformat(),
            versionId=content_hash[:16],
            contentHash=content_hash,
        )

    def write_file(
        self,
        *,
        user_id: str,
        kb_id: str,
        path: str,
        content: str,
        expected_version_id: Optional[str] = None,
    ) -> dict:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, path)
        self._validate_file_extension(path)
        size_bytes = len(content.encode("utf-8"))
        self._check_file_size(path, size_bytes)

        fs_path = self._resolve_path(kb.id, path)
        current_size = fs_path.stat().st_size if fs_path.exists() and fs_path.is_file() else 0
        delta = size_bytes - current_size
        self._check_quota(kb, delta)

        if fs_path.exists() and expected_version_id:
            current_content = fs_path.read_text(encoding="utf-8")
            current_version = hashlib.sha256(current_content.encode("utf-8")).hexdigest()[:16]
            if current_version != expected_version_id:
                raise FileManagementException(
                    code="CONTENT_CONFLICT",
                    message=KB_CONTENT_CONFLICT_MESSAGE,
                    details={
                        "path": path,
                        "expectedVersion": expected_version_id,
                        "actualVersion": current_version,
                    },
                    status_code=409,
                )

        fs_path.parent.mkdir(parents=True, exist_ok=True)
        fs_path.write_text(content, encoding="utf-8")
        self._update_kb_size(kb, delta)

        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return {
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "versionId": content_hash[:16],
            "size": size_bytes,
        }

    def create_entry(
        self,
        *,
        user_id: str,
        kb_id: str,
        path: str,
        entry_type: str,
        content: str = "",
    ) -> dict:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, path)
        fs_path = self._resolve_path(kb.id, path)
        if fs_path.exists():
            raise FileAlreadyExistsException(path, self._scope(kb.id))

        if entry_type == "directory":
            fs_path.mkdir(parents=True, exist_ok=True)
            return {"createdAt": datetime.now(timezone.utc).isoformat(), "type": "directory"}

        self._validate_file_extension(path)
        size_bytes = len(content.encode("utf-8"))
        self._check_file_size(path, size_bytes)
        self._check_quota(kb, size_bytes)
        fs_path.parent.mkdir(parents=True, exist_ok=True)
        fs_path.write_text(content, encoding="utf-8")
        self._update_kb_size(kb, size_bytes)
        return {
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "type": "file",
            "size": size_bytes,
        }

    def delete_entry(
        self,
        *,
        user_id: str,
        kb_id: str,
        path: str,
        recursive: bool = False,
    ) -> dict:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, path)
        fs_path = self._resolve_path(kb.id, path)
        if not fs_path.exists():
            raise FileNotFoundException(path, self._scope(kb.id))

        removed_size = self._calculate_size(fs_path)
        entry_type = "directory" if fs_path.is_dir() else "file"
        if fs_path.is_dir():
            if not recursive and any(fs_path.iterdir()):
                raise DirectoryNotEmptyException(path)
            shutil.rmtree(fs_path)
        else:
            fs_path.unlink()

        self._update_kb_size(kb, -removed_size)
        return {"type": entry_type}

    def move_entry(
        self,
        *,
        user_id: str,
        kb_id: str,
        source_path: str,
        dest_path: str,
        overwrite: bool = False,
    ) -> dict:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, source_path)
        source_fs_path = self._resolve_path(kb.id, source_path)
        dest_fs_path = self._resolve_path(kb.id, dest_path)
        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, self._scope(kb.id))
        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, self._scope(kb.id))
        if source_fs_path.is_file():
            self._validate_file_extension(dest_path)
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_fs_path.exists() and overwrite:
            if dest_fs_path.is_dir():
                shutil.rmtree(dest_fs_path)
            else:
                dest_fs_path.unlink()
        shutil.move(str(source_fs_path), str(dest_fs_path))
        return {
            "type": "directory" if dest_fs_path.is_dir() else "file",
            "size": dest_fs_path.stat().st_size if dest_fs_path.is_file() else 0,
        }

    def copy_entry(
        self,
        *,
        user_id: str,
        kb_id: str,
        source_path: str,
        dest_path: str,
        overwrite: bool = False,
    ) -> dict:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, dest_path)
        source_fs_path = self._resolve_path(kb.id, source_path)
        dest_fs_path = self._resolve_path(kb.id, dest_path)

        if not source_fs_path.exists():
            raise FileNotFoundException(source_path, self._scope(kb.id))

        source_size = self._calculate_size(source_fs_path)
        replaced_size = self._calculate_size(dest_fs_path) if dest_fs_path.exists() else 0
        delta = source_size - replaced_size

        if source_fs_path.is_file():
            self._validate_file_extension(dest_path)
            self._check_file_size(dest_path, source_fs_path.stat().st_size)

        if dest_fs_path.exists() and not overwrite:
            raise FileAlreadyExistsException(dest_path, self._scope(kb.id))

        self._check_quota(kb, delta)
        dest_fs_path.parent.mkdir(parents=True, exist_ok=True)

        if dest_fs_path.exists() and overwrite:
            if dest_fs_path.is_dir():
                shutil.rmtree(dest_fs_path)
            else:
                dest_fs_path.unlink()

        if source_fs_path.is_dir():
            shutil.copytree(source_fs_path, dest_fs_path)
        else:
            shutil.copy2(source_fs_path, dest_fs_path)

        self._update_kb_size(kb, delta)
        return {
            "type": "directory" if dest_fs_path.is_dir() else "file",
            "size": dest_fs_path.stat().st_size if dest_fs_path.is_file() else source_size,
        }

    async def upload_files(
        self,
        *,
        user_id: str,
        kb_id: str,
        target_path: str,
        files: list[UploadFile],
        overwrite: bool = False,
    ) -> FileUploadResponse:
        kb, access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        self._ensure_write_access(access.access_role, target_path)
        if len(files) > self.MAX_UPLOAD_FILES:
            return FileUploadResponse(
                success=False,
                uploaded=[],
                total=len(files),
                succeeded=0,
                failed=len(files),
                message=f"{KB_TOO_MANY_UPLOADS_MESSAGE} (max {self.MAX_UPLOAD_FILES} files)",
            )

        target_dir = self._resolve_path(kb.id, target_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        results: list[UploadedFileInfo] = []
        succeeded = 0
        failed = 0
        for upload_file in files:
            try:
                if not upload_file.filename:
                    raise InvalidPathException("", KB_MISSING_FILENAME_REASON)
                self._validate_file_extension(upload_file.filename)
                file_path = target_dir / upload_file.filename
                relative_path = "/" + str(file_path.relative_to(self._kb_root(kb.id))).replace("\\", "/")
                if file_path.exists() and not overwrite:
                    raise FileAlreadyExistsException(relative_path, self._scope(kb.id))

                content = await upload_file.read()
                self._check_file_size(relative_path, len(content))
                current_size = file_path.stat().st_size if file_path.exists() else 0
                delta = len(content) - current_size
                self._check_quota(kb, delta)
                file_path.write_bytes(content)
                self._update_kb_size(kb, delta)

                results.append(
                    UploadedFileInfo(
                        filename=upload_file.filename,
                        path=relative_path,
                        size=len(content),
                        success=True,
                    )
                )
                succeeded += 1
            except Exception as exc:
                results.append(
                    UploadedFileInfo(
                        filename=upload_file.filename or "",
                        path="",
                        size=0,
                        success=False,
                        error=str(exc),
                    )
                )
                failed += 1

        return FileUploadResponse(
            success=failed == 0,
            uploaded=results,
            total=len(files),
            succeeded=succeeded,
            failed=failed,
            message=f"{KB_UPLOAD_SUCCESS_MESSAGE}（{succeeded}/{len(files)}）",
        )

    def _scope(self, kb_id: str) -> str:
        return f"kb:{kb_id}"

    def _kb_root(self, kb_id: str) -> Path:
        root = self.storage_root / kb_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_path(self, kb_id: str, relative_path: str) -> Path:
        root = self._kb_root(kb_id)
        normalized = self._validate_path(relative_path)
        target = root / normalized if normalized else root
        resolved = target.resolve()
        if root.resolve() not in (resolved, *resolved.parents):
            raise InvalidPathException(relative_path, KB_PATH_TRAVERSAL_REASON)
        return resolved

    def _validate_path(self, path: str) -> str:
        normalized = (path or "").strip().lstrip("/")
        if normalized.startswith("/") or ".." in Path(normalized).parts:
            raise InvalidPathException(path, KB_PATH_TRAVERSAL_REASON)
        return normalized

    def _scan_directory(
        self,
        directory: Path,
        *,
        base_path: Path,
        include_hidden: bool,
        max_depth: int,
        current_depth: int = 0,
    ) -> list[FileNode]:
        if not directory.exists() or not directory.is_dir():
            return []

        nodes: list[FileNode] = []
        for entry in sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            if not include_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir() and entry.name in self.SKIP_DIRECTORIES:
                continue

            rel_path = "/" + str(entry.relative_to(base_path)).replace("\\", "/")
            stat_info = entry.stat()
            node = FileNode(
                id=rel_path,
                name=entry.name,
                path=rel_path,
                type="directory" if entry.is_dir() else "file",
                scope=None,
                size=stat_info.st_size if entry.is_file() else 0,
                updatedAt=datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc).isoformat(),
                depth=current_depth,
                children=[],
                hasChildren=False,
                extension=entry.suffix.lower() or None,
            )
            if entry.is_dir():
                if current_depth < max_depth:
                    node.children = self._scan_directory(
                        entry,
                        base_path=base_path,
                        include_hidden=include_hidden,
                        max_depth=max_depth,
                        current_depth=current_depth + 1,
                    )
                node.hasChildren = any(entry.iterdir())
            nodes.append(node)
        return nodes

    def _validate_file_extension(self, path: str) -> None:
        extension = Path(path).suffix.lower()
        if extension and extension not in self.settings.KB_ALLOWED_EXTENSIONS:
            raise FileManagementException(
                code="INVALID_FILE_TYPE",
                message=f"{KB_INVALID_FILE_TYPE_MESSAGE}: {extension}",
                details={
                    "path": path,
                    "extension": extension,
                    "allowedExtensions": self.settings.KB_ALLOWED_EXTENSIONS,
                },
                status_code=400,
            )

    def _check_file_size(self, path: str, size_bytes: int) -> None:
        if size_bytes > self.settings.KB_SINGLE_FILE_SIZE_LIMIT:
            raise FileTooLargeException(path, size_bytes, self.settings.KB_SINGLE_FILE_SIZE_LIMIT)

    def _check_quota(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        if delta_bytes <= 0:
            return
        per_kb_quota = kb.quota_bytes or self.settings.DEFAULT_KB_QUOTA_BYTES
        if kb.current_size_bytes + delta_bytes > per_kb_quota:
            raise FileManagementException(
                code="KB_QUOTA_EXCEEDED",
                message=KB_QUOTA_EXCEEDED_MESSAGE,
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
                message=KB_OWNER_QUOTA_EXCEEDED_MESSAGE,
                details={
                    "ownerId": kb.owner_id,
                    "currentTotalBytes": owner_total,
                    "deltaBytes": delta_bytes,
                    "quotaBytes": self.settings.DEFAULT_USER_KB_QUOTA_BYTES,
                },
                status_code=409,
            )

    def _ensure_write_access(self, access_role: str, path: str) -> None:
        if access_role not in {"owner", "manager", "editor"}:
            raise KnowledgeBaseAccessDeniedError(f"Knowledge base does not have write permission: {path}")

    def _update_kb_size(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        kb.current_size_bytes = max(0, kb.current_size_bytes + delta_bytes)
        kb.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(kb)

    def _calculate_size(self, path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        total = 0
        for entry in path.rglob("*"):
            if entry.is_file():
                total += entry.stat().st_size
        return total
