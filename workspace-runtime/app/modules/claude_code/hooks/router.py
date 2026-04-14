"""Hooks 路由"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses
from ..common import DocumentScope
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
from .service import HookService

router = APIRouter(prefix="/hooks", tags=["Claude Code - Hooks"])


@router.get(
    "",
    response_model=HookScopesResponse,
    summary="取得所有 Hook 範圍",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="可指定僅回傳某範圍"
    ),
    service: HookService = Depends(get_hook_service),
) -> HookScopesResponse:
    return service.list_scopes(workspace_id, scope)


@router.get(
    "/export",
    response_model=HookExportResponse,
    summary="匯出 Hook 設定",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def export_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="若提供則僅匯出指定範圍"
    ),
    service: HookService = Depends(get_hook_service),
) -> HookExportResponse:
    scope_filter = [scope] if scope else None
    return service.export_scopes(workspace_id, scope_filter)


@router.get(
    "/{scope}",
    response_model=HookScopeResponse,
    summary="取得指定範圍 Hook",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook 範圍"),
    service: HookService = Depends(get_hook_service),
) -> HookScopeResponse:
    return service.get_scope(workspace_id, scope)


@router.put(
    "/{scope}",
    response_model=HookScopeResponse,
    summary="更新 Hook 範圍",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def update_scope_hooks(
    payload: HookScopeUpsertRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook 範圍"),
    service: HookService = Depends(get_hook_service),
) -> HookScopeResponse:
    return service.update_scope(workspace_id, scope, payload)


@router.delete(
    "/{scope}",
    response_model=HookDeleteResponse,
    summary="刪除 Hook 範圍",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_scope_hooks(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Hook 範圍"),
    service: HookService = Depends(get_hook_service),
) -> HookDeleteResponse:
    return service.delete_scope(workspace_id, scope)


@router.post(
    "/import",
    response_model=HookImportResponse,
    summary="匯入 Hook 設定",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def import_hooks(
    payload: HookImportRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    service: HookService = Depends(get_hook_service),
) -> HookImportResponse:
    return service.import_scopes(workspace_id, payload)
