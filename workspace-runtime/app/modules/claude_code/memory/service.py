"""Claude Code Memory Service"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from ..common import format_file_size, parse_front_matter
from .models import (
    MemoryCollectionResponse,
    MemoryCreateRequest,
    MemoryDeleteResponse,
    MemoryDocumentDetail,
    MemoryDocumentResponse,
    MemoryDocumentSummary,
    MemoryUpdateRequest,
)


class MemoryService:
    """Manage single-level Markdown files in a fixed Claude Memory directory"""

    DEFAULT_MEMORY_DIR = Path("/home/developer/.claude/projects/-workspace/memory")

    def __init__(self, memory_dir: Path | None = None) -> None:
        self._memory_dir = memory_dir or self.DEFAULT_MEMORY_DIR

    def list_documents(self, workspace_id: str) -> MemoryCollectionResponse:
        if not self._memory_dir.exists():
            return MemoryCollectionResponse(workspaceId=workspace_id, documents=[])

        documents = [
            self._to_summary(file_path)
            for file_path in sorted(self._memory_dir.iterdir(), key=lambda path: path.name.lower())
            if file_path.is_file() and file_path.suffix.lower() == ".md"
        ]
        return MemoryCollectionResponse(workspaceId=workspace_id, documents=documents)

    def get_document(self, workspace_id: str, file_name: str) -> MemoryDocumentResponse:
        file_path = self._resolve_existing_file(file_name)
        return MemoryDocumentResponse(
            workspaceId=workspace_id,
            document=self._to_detail(file_path),
        )

    def create_document(
        self, workspace_id: str, payload: MemoryCreateRequest
    ) -> MemoryDocumentResponse:
        file_name = self._normalize_file_name(payload.file_name)
        self._memory_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._memory_dir / file_name
        if file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_FILE_NAME", "message": f"Memory file already exists: {file_name}"},
            )
        file_path.write_text(payload.content, encoding="utf-8")
        return MemoryDocumentResponse(
            workspaceId=workspace_id,
            document=self._to_detail(file_path),
        )

    def update_document(
        self, workspace_id: str, file_name: str, payload: MemoryUpdateRequest
    ) -> MemoryDocumentResponse:
        file_path = self._resolve_existing_file(file_name)
        file_path.write_text(payload.content, encoding="utf-8")
        return MemoryDocumentResponse(
            workspaceId=workspace_id,
            document=self._to_detail(file_path),
        )

    def delete_document(self, workspace_id: str, file_name: str) -> MemoryDeleteResponse:
        file_path = self._resolve_existing_file(file_name)
        file_path.unlink()
        return MemoryDeleteResponse(
            workspaceId=workspace_id,
            fileName=file_path.name,
            deleted=True,
        )

    def _normalize_file_name(self, file_name: str) -> str:
        normalized = (file_name or "").strip()
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_NAME", "message": "Memory file name cannot be empty"},
            )
        if normalized.startswith("/") or "/" in normalized or "\\" in normalized or Path(normalized).name != normalized:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_NAME", "message": "Memory file name cannot contain path"},
            )
        if not normalized.lower().endswith(".md"):
            normalized = f"{normalized}.md"
        return normalized

    def _resolve_existing_file(self, file_name: str) -> Path:
        normalized = self._normalize_file_name(file_name)
        file_path = self._memory_dir / normalized
        if not file_path.exists() or not file_path.is_file() or file_path.suffix.lower() != ".md":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": f"Memory file not found: {normalized}"},
            )
        return file_path

    def _to_summary(self, file_path: Path) -> MemoryDocumentSummary:
        content = file_path.read_text(encoding="utf-8")
        metadata, _ = parse_front_matter(content)
        stat = file_path.stat()
        return MemoryDocumentSummary(
            fileName=file_path.name,
            name=metadata.get("name") or file_path.stem,
            description=metadata.get("description"),
            size=format_file_size(stat.st_size),
        )

    def _to_detail(self, file_path: Path) -> MemoryDocumentDetail:
        summary = self._to_summary(file_path)
        return MemoryDocumentDetail(**summary.model_dump(), content=file_path.read_text(encoding="utf-8"))
