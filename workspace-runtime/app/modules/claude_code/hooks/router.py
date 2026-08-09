"""Hooks Routes"""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error
from ..documents import DocumentScope
from .dependencies import get_hook_service
from .models import (
    HookDeleteResponse,
    HookExportResponse,
    HookImportRequest,
    HookImportResponse,
    HookScopeResponse,
    HookScopeUpsertRequest,
    HookScopesResponse,
)
from .configuration import HookService

router = APIRouter(prefix="/hooks", tags=["Claude Code - Hooks"])

T = TypeVar("T")


def _call_service(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException as error:
        detail = vars(error).get("detail")
        if isinstance(detail, dict) and "error" in detail:
            raise_resource_error(
                str(detail["error"]),
                str(detail.get("message") or detail["error"]),
                error.status_code,
            )
        raise


@router.get(
    "",
    response_model=HookScopesResponse,
    summary="Get all hook scopes",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="Optionally return only specified scope"
    ),
    service: HookService = Depends(get_hook_service),
) -> HookScopesResponse:
    return _call_service(lambda: service.list_scopes(workspace_id, scope))


@router.get(
    "/export",
    response_model=HookExportResponse,
    summary="Export hook settings",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def export_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="If provided, export only specified scope"
    ),
    service: HookService = Depends(get_hook_service),
) -> HookExportResponse:
    scope_filter = [scope] if scope else None
    return _call_service(lambda: service.export_scopes(workspace_id, scope_filter))


@router.get(
    "/{scope}",
    response_model=HookScopeResponse,
    summary="Get hooks for specified scope",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook scope"),
    service: HookService = Depends(get_hook_service),
) -> HookScopeResponse:
    return _call_service(lambda: service.get_scope(workspace_id, scope))


@router.put(
    "/{scope}",
    response_model=HookScopeResponse,
    summary="Update hook scope",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_scope_hooks(
    payload: HookScopeUpsertRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook scope"),
    service: HookService = Depends(get_hook_service),
) -> HookScopeResponse:
    return _call_service(lambda: service.update_scope(workspace_id, scope, payload))


@router.delete(
    "/{scope}",
    response_model=HookDeleteResponse,
    summary="Delete hook scope",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_scope_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook scope"),
    service: HookService = Depends(get_hook_service),
) -> HookDeleteResponse:
    return _call_service(lambda: service.delete_scope(workspace_id, scope))


@router.post(
    "/import",
    response_model=HookImportResponse,
    summary="Import hook settings",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def import_hooks(
    payload: HookImportRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: HookService = Depends(get_hook_service),
) -> HookImportResponse:
    return _call_service(lambda: service.import_scopes(workspace_id, payload))
