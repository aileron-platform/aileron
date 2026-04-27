"""Output Styles Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from ..common import DocumentScope, check_scope_writable
from .dependencies import get_output_style_service
from .models import (
    OutputStyleCollectionResponse,
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleDocumentResponse,
    OutputStyleScopeResponse,
    OutputStyleUpdateRequest,
)
from .service import OutputStyleService

router = APIRouter(prefix="/output-styles", tags=["Claude Code - Output Styles"])


def _check_output_style_writable(scope: DocumentScope) -> None:
    """Check if Output Style scope is writable"""
    try:
        check_scope_writable(scope)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "SCOPE_READ_ONLY", "message": str(e)},
        ) from e


@router.get(
    "",
    response_model=OutputStyleCollectionResponse,
    summary="List all styles",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_output_styles(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="Optionally return only specified scope"
    ),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleCollectionResponse:
    return service.list_scopes(workspace_id, scope)


@router.get(
    "/{scope}",
    response_model=OutputStyleScopeResponse,
    summary="Get styles for specified scope",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_output_styles(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleScopeResponse:
    return service.get_scope(workspace_id, scope)


@router.get(
    "/{scope}/{file_name}",
    response_model=OutputStyleDocumentResponse,
    summary="Get style content",
    responses=build_responses(400, 401, 404, 500),
)
async def get_output_style(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    file_name: str = Path(..., description="File name"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDocumentResponse:
    return service.get_document(workspace_id, scope, file_name)


@router.post(
    "/{scope}",
    response_model=OutputStyleDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create style",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_output_style(
    payload: OutputStyleCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDocumentResponse:
    _check_output_style_writable(scope)
    return service.create_document(workspace_id, scope, payload)


@router.put(
    "/{scope}/{file_name}",
    response_model=OutputStyleDocumentResponse,
    summary="Update style",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_output_style(
    payload: OutputStyleUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    file_name: str = Path(..., description="File name"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDocumentResponse:
    _check_output_style_writable(scope)
    return service.update_document(workspace_id, scope, file_name, payload)


@router.delete(
    "/{scope}/{file_name}",
    response_model=OutputStyleDeleteResponse,
    summary="Delete style",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_output_style(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    file_name: str = Path(..., description="File name"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDeleteResponse:
    _check_output_style_writable(scope)
    service.delete_document(workspace_id, scope, file_name)
    return OutputStyleDeleteResponse(
        workspaceId=workspace_id,
        scope=scope,
        fileName=file_name,
        deleted=True,
    )
