"""Output Styles Routes"""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error

from ..documents import DocumentScope, check_scope_writable
from .dependencies import get_output_style_service
from .models import (
    OutputStyleCollectionResponse,
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleDocumentResponse,
    OutputStyleScopeResponse,
    OutputStyleUpdateRequest,
)
from .catalog import OutputStyleService

router = APIRouter(prefix="/output-styles", tags=["Claude Code - Output Styles"])

T = TypeVar("T")


def _call_service(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException as error:
        detail = vars(error).get("detail")
        if isinstance(detail, dict) and ("error" in detail or "errorCode" in detail):
            code = str(detail.get("errorCode") or detail["error"])
            raise_resource_error(
                code,
                str(detail.get("message") or code),
                error.status_code,
            )
        raise


def _check_output_style_writable(scope: DocumentScope) -> None:
    """Check if Output Style scope is writable"""
    try:
        check_scope_writable(scope)
    except ValueError as e:
        raise_resource_error("SCOPE_READ_ONLY", str(e), status.HTTP_403_FORBIDDEN)


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
    plugin_id: str | None = Query(
        default=None,
        alias="pluginId",
        description="Optionally filter plugin resources by provider plugin ID",
    ),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleCollectionResponse:
    return _call_service(
        lambda: service.list_scopes(
            workspace_id,
            scope,
            plugin_id=plugin_id,
        )
    )


@router.get(
    "/{scope}",
    response_model=OutputStyleScopeResponse,
    summary="Get styles for specified scope",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_output_styles(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    plugin_id: str | None = Query(
        default=None,
        alias="pluginId",
        description="Optionally filter plugin resources by provider plugin ID",
    ),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleScopeResponse:
    return _call_service(
        lambda: service.get_scope(
            workspace_id,
            scope,
            plugin_id=plugin_id,
        )
    )


@router.get(
    "/{scope}/{file_name:path}",
    response_model=OutputStyleDocumentResponse,
    summary="Get style content",
    responses=build_responses(400, 401, 404, 409, 500),
)
async def get_output_style(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Style scope"),
    file_name: str = Path(..., description="File name"),
    plugin_id: str | None = Query(
        default=None,
        alias="pluginId",
        description="Provider plugin ID used to disambiguate plugin resources",
    ),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDocumentResponse:
    return _call_service(
        lambda: service.get_document(
            workspace_id,
            scope,
            file_name,
            plugin_id=plugin_id,
        )
    )


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
    return _call_service(lambda: service.create_document(workspace_id, scope, payload))


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
    return _call_service(
        lambda: service.update_document(workspace_id, scope, file_name, payload)
    )


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
    revision: str = Query(..., description="Expected document revision token"),
    service: OutputStyleService = Depends(get_output_style_service),
) -> OutputStyleDeleteResponse:
    _check_output_style_writable(scope)
    return _call_service(
        lambda: service.delete_document(
            workspace_id,
            scope,
            file_name,
            revision=revision,
        )
    )
