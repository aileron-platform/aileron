"""Claude.md 模組路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses
from .dependencies import get_claude_md_service
from .models import (
    ClaudeMdDocument,
    ClaudeMdScope,
    ClaudeMdUpdateRequest,
    ClaudeMdUpdateResponse,
)
from .service import ClaudeMdService

router = APIRouter(prefix="/claude-md", tags=["Claude Code - CLAUDE.md"])


@router.get(
    "",
    response_model=ClaudeMdDocument,
    summary="取得 Claude.md 內容",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_claude_md(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: ClaudeMdScope = Query(..., description="檔案範圍"),
    service: ClaudeMdService = Depends(get_claude_md_service),
) -> ClaudeMdDocument:
    return service.get_document(workspace_id, scope)


@router.put(
    "",
    response_model=ClaudeMdUpdateResponse,
    summary="更新 Claude.md 內容",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_claude_md(
    payload: ClaudeMdUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: ClaudeMdService = Depends(get_claude_md_service),
) -> ClaudeMdUpdateResponse:
    return service.update_document(workspace_id, payload)
