"""Claude Code Memory Service"""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.paths import runtime_user_home

from ..documents import (
    DocumentScope,
    format_file_size,
    parse_front_matter,
    workspace_root,
)
from .models import (
    MemoryAvailableScope,
    MemoryCollectionResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryDocumentDetail,
    MemoryDocumentResponse,
    MemoryDocumentSummary,
    MemoryUpdateRequest,
)


_write_locks_guard = Lock()
_write_locks: dict[str, Lock] = {}


def _write_lock(key: str) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(key, Lock())


class MemoryService:
    """Manage Markdown files in Claude Memory directories"""

    def __init__(self, memory_dir: Path | None = None) -> None:
        self._memory_dir = (
            memory_dir
            or runtime_user_home() / ".claude" / "projects" / "-workspace" / "memory"
        )
        self._custom_memory_dir = memory_dir is not None

    def list_documents(self, workspace_id: str) -> MemoryCollectionResponse:
        documents: list[MemoryDocumentSummary] = []
        for scope in self._supported_scopes():
            root = self._scope_root(scope)
            if not root.exists():
                continue
            documents.extend(
                self._to_summary(file_path, scope)
                for file_path in sorted(
                    root.rglob("*.md"),
                    key=lambda path: path.relative_to(root).as_posix().lower(),
                )
                if file_path.is_file()
            )
        documents.sort(key=lambda item: (item.scope.value, item.path.lower()))
        return MemoryCollectionResponse(
            workspaceId=workspace_id,
            revision=self._collection_revision(),
            items=documents,
            availableScopes=[
                MemoryAvailableScope(scope=DocumentScope.PROJECT, readOnly=False),
                MemoryAvailableScope(scope=DocumentScope.USER, readOnly=False),
            ],
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, path: str
    ) -> MemoryDocumentResponse:
        file_path = self._resolve_existing_file(scope, path)
        detail = self._to_detail(file_path, scope)
        return MemoryDocumentResponse(
            revision=compute_revision(detail.content),
            resource=detail.model_dump(by_alias=True, mode="json"),
        )

    def create_document(
        self, workspace_id: str, scope: DocumentScope, payload: MemoryCreateRequest
    ) -> MemoryDocumentResponse:
        try:
            with _write_lock(f"{workspace_id}:memory"):
                assert_revision(self._collection_revision(), payload.revision)
                root, file_path = self._path_for(scope, payload.path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if file_path.exists():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "errorCode": "DUPLICATE_PATH",
                            "message": f"Memory file already exists: {self._normalize_path(payload.path).as_posix()}",
                        },
                    )
                file_path.write_text(payload.content, encoding="utf-8")
                detail = self._to_detail(file_path, scope)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": "INVALID_MEMORY_PATH", "message": str(error)},
            ) from error
        return MemoryDocumentResponse(
            revision=compute_revision(detail.content),
            resource=detail.model_dump(by_alias=True, mode="json"),
        )

    def update_document(
        self, workspace_id: str, scope: DocumentScope, payload: MemoryUpdateRequest
    ) -> MemoryDocumentResponse:
        try:
            with _write_lock(f"{workspace_id}:memory"):
                file_path = self._resolve_existing_file(scope, payload.path)
                current_content = file_path.read_text(encoding="utf-8")
                assert_revision(compute_revision(current_content), payload.revision)
                file_path.write_text(payload.content, encoding="utf-8")
                detail = self._to_detail(file_path, scope)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": "INVALID_MEMORY_PATH", "message": str(error)},
            ) from error
        return MemoryDocumentResponse(
            revision=compute_revision(detail.content),
            resource=detail.model_dump(by_alias=True, mode="json"),
        )

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, path: str, revision: str
    ) -> MemoryDeleteResponse:
        try:
            with _write_lock(f"{workspace_id}:memory"):
                file_path = self._resolve_existing_file(scope, path)
                assert_revision(
                    compute_revision(file_path.read_text(encoding="utf-8")), revision
                )
                normalized = self._normalize_path(path).as_posix()
                file_path.unlink()
                collection_revision = self._collection_revision()
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": "INVALID_MEMORY_PATH", "message": str(error)},
            ) from error
        return MemoryDeleteResponse(
            revision=collection_revision,
            resource={"path": normalized, "scope": scope.value, "deleted": True},
        )

    @staticmethod
    def _supported_scopes() -> tuple[DocumentScope, ...]:
        return (DocumentScope.PROJECT, DocumentScope.USER)

    def _scope_root(self, scope: DocumentScope) -> Path:
        if scope not in self._supported_scopes():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": "INVALID_SCOPE",
                    "message": f"Memory does not support {scope.value} scope",
                },
            )
        if self._custom_memory_dir:
            return self._memory_dir / scope.value
        if scope == DocumentScope.USER:
            return self._memory_dir
        return workspace_root() / ".claude" / "memory"

    @staticmethod
    def _normalize_path(raw_path: str) -> Path:
        clean_path = (raw_path or "").strip()
        if not clean_path or "\\" in clean_path:
            raise ValueError("Memory path cannot be empty or contain backslashes")
        path = Path(clean_path)
        if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
            raise ValueError(
                "Memory path cannot be absolute or contain traversal segments"
            )
        if path.suffix and path.suffix.lower() != ".md":
            raise ValueError("Memory path must be a Markdown file")
        if not path.suffix:
            path = path.with_name(f"{path.name}.md")
        return path

    def _path_for(self, scope: DocumentScope, raw_path: str) -> tuple[Path, Path]:
        root = self._scope_root(scope)
        return root, root / self._normalize_path(raw_path)

    def _resolve_existing_file(self, scope: DocumentScope, path: str) -> Path:
        normalized = self._normalize_path(path)
        file_path = self._scope_root(scope) / normalized
        if (
            not file_path.exists()
            or not file_path.is_file()
            or file_path.suffix.lower() != ".md"
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "errorCode": "404_NOT_FOUND",
                    "message": f"Memory file not found: {normalized.as_posix()}",
                },
            )
        return file_path

    def _to_summary(
        self, file_path: Path, scope: DocumentScope
    ) -> MemoryDocumentSummary:
        content = file_path.read_text(encoding="utf-8")
        metadata, _ = parse_front_matter(content)
        stat = file_path.stat()
        return MemoryDocumentSummary(
            path=file_path.relative_to(self._scope_root(scope)).as_posix(),
            scope=scope,
            name=metadata.get("name") or file_path.stem,
            description=metadata.get("description"),
            size=format_file_size(stat.st_size),
        )

    def _to_detail(self, file_path: Path, scope: DocumentScope) -> MemoryDocumentDetail:
        summary = self._to_summary(file_path, scope)
        return MemoryDocumentDetail(
            **summary.model_dump(), content=file_path.read_text(encoding="utf-8")
        )

    def _collection_revision(self) -> str:
        content_by_path: dict[str, str] = {}
        for scope in self._supported_scopes():
            root = self._scope_root(scope)
            if not root.exists():
                continue
            for file_path in sorted(
                root.rglob("*.md"), key=lambda path: path.relative_to(root).as_posix()
            ):
                if file_path.is_file():
                    key = f"{scope.value}:{file_path.relative_to(root).as_posix()}"
                    content_by_path[key] = file_path.read_text(encoding="utf-8")
        import json

        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)
