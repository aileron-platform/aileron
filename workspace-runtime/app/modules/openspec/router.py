"""OpenSpec runtime API router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Request

from app.core.openapi import build_responses

from .dependencies import get_openspec_service
from .models import (
    OpenSpecActionContextSubview,
    OpenSpecCustomizationActionResponse,
    OpenSpecCustomizationDebugResponse,
    OpenSpecCustomizationFileResponse,
    OpenSpecCustomizationFileUpdateRequest,
    OpenSpecCustomizationSchemaCreateRequest,
    OpenSpecCustomizationSchemaForkRequest,
    OpenSpecCustomizationStateResponse,
    OpenSpecCustomizationValidationRequest,
    OpenSpecCustomizationValidationResponse,
    OpenSpecWorkspaceResponse,
)
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


@router.get(
    "/customization",
    response_model=OpenSpecCustomizationStateResponse,
    summary="取得 OpenSpec customization explorer 狀態",
    responses=build_responses(401, 404, 500),
)
async def get_openspec_customization_state(
    workspace_id: str = Path(..., description="Workspace ID"),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationStateResponse:
    return service.get_customization_state(workspace_id)


@router.get(
    "/customization/file",
    response_model=OpenSpecCustomizationFileResponse,
    summary="讀取 customization 檔案內容",
    responses=build_responses(400, 401, 404, 500),
)
async def get_openspec_customization_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="Workspace-relative customization path"),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationFileResponse:
    try:
        return service.read_customization_file(workspace_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put(
    "/customization/file",
    response_model=OpenSpecCustomizationActionResponse,
    summary="儲存 customization 檔案內容",
    responses=build_responses(400, 401, 404, 500),
)
async def update_openspec_customization_file(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="Workspace-relative customization path"),
    payload: OpenSpecCustomizationFileUpdateRequest = Body(...),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationActionResponse:
    try:
        return service.update_customization_file(workspace_id, path, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/customization/schemas/fork",
    response_model=OpenSpecCustomizationActionResponse,
    summary="Fork built-in 或現有 schema 到 project-local",
    responses=build_responses(400, 401, 404, 500),
)
async def fork_openspec_customization_schema(
    workspace_id: str = Path(..., description="Workspace ID"),
    payload: OpenSpecCustomizationSchemaForkRequest = Body(...),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationActionResponse:
    try:
        return service.fork_customization_schema(
            workspace_id,
            source_schema=payload.sourceSchema,
            destination_schema=payload.destinationSchema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/customization/schemas",
    response_model=OpenSpecCustomizationActionResponse,
    summary="建立新的 project-local schema",
    responses=build_responses(400, 401, 404, 500),
)
async def init_openspec_customization_schema(
    workspace_id: str = Path(..., description="Workspace ID"),
    payload: OpenSpecCustomizationSchemaCreateRequest = Body(...),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationActionResponse:
    try:
        return service.init_customization_schema(
            workspace_id,
            name=payload.name,
            description=payload.description,
            artifacts=payload.artifacts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/customization/validate",
    response_model=OpenSpecCustomizationValidationResponse,
    summary="驗證目前 customization context",
    responses=build_responses(400, 401, 404, 500),
)
async def validate_openspec_customization(
    workspace_id: str = Path(..., description="Workspace ID"),
    payload: OpenSpecCustomizationValidationRequest = Body(...),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationValidationResponse:
    try:
        return service.validate_customization(workspace_id, path=payload.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/customization/debug",
    response_model=OpenSpecCustomizationDebugResponse,
    summary="顯示目前 customization context 的 schema resolution",
    responses=build_responses(400, 401, 404, 500),
)
async def debug_openspec_customization(
    workspace_id: str = Path(..., description="Workspace ID"),
    path: str = Query(..., description="Workspace-relative customization path"),
    service: OpenSpecService = Depends(get_openspec_service),
) -> OpenSpecCustomizationDebugResponse:
    try:
        return service.debug_customization(workspace_id, path=path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
