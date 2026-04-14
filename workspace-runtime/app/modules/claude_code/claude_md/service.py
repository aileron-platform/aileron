"""Claude.md 服務"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from ..common import DocumentScope, ensure_directory, resolve_scope_root
from .models import ClaudeMdDocument, ClaudeMdScope, ClaudeMdUpdateRequest, ClaudeMdUpdateResponse


class ClaudeMdService:
    """管理 Claude.md 檔案的服務"""

    _FILE_NAME = "CLAUDE.md"

    def get_document(self, workspace_id: str, scope: ClaudeMdScope) -> ClaudeMdDocument:
        file_path = self._resolve_path(workspace_id, scope)
        if not file_path.exists():
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": "Claude.md not found"},
            )
        content = file_path.read_text(encoding="utf-8")
        return ClaudeMdDocument(
            workspaceId=workspace_id,
            scope=scope,
            content=content,
        )

    def update_document(
        self,
        workspace_id: str,
        request: ClaudeMdUpdateRequest,
    ) -> ClaudeMdUpdateResponse:
        file_path = self._resolve_path(workspace_id, request.scope)
        ensure_directory(file_path.parent)
        file_path.write_text(request.content, encoding="utf-8")
        return ClaudeMdUpdateResponse(
            workspaceId=workspace_id,
            scope=request.scope,
        )

    def _resolve_path(self, workspace_id: str, scope: ClaudeMdScope) -> Path:
        if scope == ClaudeMdScope.PROJECT:
            root = resolve_scope_root(workspace_id, DocumentScope.PROJECT)
            return root / self._FILE_NAME
        if scope == ClaudeMdScope.USER:
            root = resolve_scope_root(workspace_id, DocumentScope.USER)
            return root / self._FILE_NAME
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported scope")

