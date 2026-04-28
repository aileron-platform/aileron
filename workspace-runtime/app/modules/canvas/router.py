"""Canvas module router"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import Response

from app.core.openapi import build_responses

from .dependencies import get_canvas_service
from .models import (
    CanvasActionResponse,
    CanvasDetectResponse,
    CanvasHealthResponse,
    CanvasLogsResponse,
    CanvasReviewNote,
    CanvasReviewNoteCreate,
    CanvasReviewNotesResponse,
    CanvasReviewReplyCreate,
    CanvasReviewStatus,
    CanvasReviewStatusUpdate,
    CanvasRoutesResponse,
)
from .service import CanvasService

router = APIRouter(prefix="/workspaces/{workspace_id}/canvas", tags=["Canvas"])


@router.get(
    "/detect",
    response_model=CanvasDetectResponse,
    summary="Detect Canvas type",
    responses=build_responses(401, 404, 500),
)
async def detect_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasDetectResponse:
    return service.detect(workspace_id)


@router.get(
    "/routes",
    response_model=CanvasRoutesResponse,
    summary="Get Canvas route list",
    responses=build_responses(401, 404, 500),
)
async def get_canvas_routes(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasRoutesResponse:
    return service.routes(workspace_id)


@router.get(
    "/health",
    response_model=CanvasHealthResponse,
    summary="Check Canvas health status",
    responses=build_responses(401, 404, 500),
)
async def check_canvas_health(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasHealthResponse:
    return service.health(workspace_id)


@router.get(
    "/logs",
    response_model=CanvasLogsResponse,
    summary="Get Canvas logs",
    responses=build_responses(401, 404, 500),
)
async def get_canvas_logs(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasLogsResponse:
    return service.logs(workspace_id)


@router.post(
    "/sync",
    response_model=CanvasActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sync workspace to Canvas snapshot",
    responses=build_responses(401, 404, 422, 500),
)
async def sync_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasActionResponse:
    return service.sync(workspace_id)


@router.post(
    "/reset",
    response_model=CanvasActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reset Canvas snapshot",
    responses=build_responses(401, 404, 422, 500),
)
async def reset_canvas(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasActionResponse:
    return service.reset(workspace_id)


@router.get(
    "/review-notes",
    response_model=CanvasReviewNotesResponse,
    summary="List Canvas review notes",
    responses=build_responses(401, 404, 500),
)
async def list_canvas_review_notes(
    workspace_id: str = Path(..., description="Workspace ID"),
    status_filter: CanvasReviewStatus | None = Query(default=None, alias="status"),
    route_path: str | None = Query(default=None, alias="routePath"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasReviewNotesResponse:
    return service.list_review_notes(
        workspace_id,
        status=status_filter,
        route_path=route_path,
    )


@router.post(
    "/review-notes",
    response_model=CanvasReviewNote,
    status_code=status.HTTP_201_CREATED,
    summary="Create Canvas review note",
    responses=build_responses(401, 404, 422, 500),
)
async def create_canvas_review_note(
    payload: CanvasReviewNoteCreate,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasReviewNote:
    return service.create_review_note(workspace_id, payload)


@router.patch(
    "/review-notes/{note_id}/status",
    response_model=CanvasReviewNote,
    summary="Update Canvas review note status",
    responses=build_responses(401, 404, 422, 500),
)
async def update_canvas_review_note_status(
    payload: CanvasReviewStatusUpdate,
    workspace_id: str = Path(..., description="Workspace ID"),
    note_id: str = Path(..., description="Review note ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasReviewNote:
    return service.update_review_note_status(workspace_id, note_id, payload.status)


@router.post(
    "/review-notes/{note_id}/replies",
    response_model=CanvasReviewNote,
    status_code=status.HTTP_201_CREATED,
    summary="Append Canvas review note reply",
    responses=build_responses(401, 404, 422, 500),
)
async def append_canvas_review_note_reply(
    payload: CanvasReviewReplyCreate,
    workspace_id: str = Path(..., description="Workspace ID"),
    note_id: str = Path(..., description="Review note ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> CanvasReviewNote:
    return service.append_review_note_reply(workspace_id, note_id, payload)


@router.delete(
    "/review-notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Canvas review note",
    responses=build_responses(401, 404, 500),
)
async def delete_canvas_review_note(
    workspace_id: str = Path(..., description="Workspace ID"),
    note_id: str = Path(..., description="Review note ID"),
    service: CanvasService = Depends(get_canvas_service),
) -> Response:
    service.delete_review_note(workspace_id, note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
