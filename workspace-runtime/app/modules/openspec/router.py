"""OpenSpec runtime API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, Request

from app.core.openapi import build_responses

from .dependencies import get_openspec_service
from .models import OpenSpecActionContextSubview, OpenSpecWorkspaceResponse
from .service import OpenSpecService

router = APIRouter(
    prefix="/workspaces/{workspace_id}/openspec",
    tags=["OpenSpec"],
)


@router.get(
    "",
    response_model=OpenSpecWorkspaceResponse,
    summary="取得 OpenSpec workspace 狀態與 actions",
    responses=build_responses(401, 404, 500),
)
async def get_openspec_workspace_state(
    request: Request,
    workspace_id: str = Path(..., description="Workspace ID"),
    subview: OpenSpecActionContextSubview | None = Query(
        default=None,
        description="Current OpenSpec subview context",
    ),
    focused_change_name: str | None = Query(
        default=None,
        alias="focusedChangeName",
        description="Currently focused OpenSpec change name",
    ),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecWorkspaceResponse:
    return service.get_workspace_state(
        workspace_id,
        translate=request.state.translate,
        language=request.state.language,
        subview=subview,
        focused_change_name=focused_change_name,
    )
