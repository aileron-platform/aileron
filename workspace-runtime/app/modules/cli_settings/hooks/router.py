"""CLI Hooks API 路由

工廠函數，為每個 CLI 工具產生相同的 Hooks 端點集合。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from app.core.openapi import build_responses

from .config import HookTool
from .dependencies import make_hooks_service_dependency
from .models import (
    CliHookDeleteResponse,
    CliHookExportResponse,
    CliHookImportRequest,
    CliHookImportResponse,
    CliHookScope,
    CliHookScopeResponse,
    CliHookScopeUpsertRequest,
    CliHookScopesResponse,
)
from .service import CliHookService


def create_hooks_router(tool: HookTool) -> APIRouter:
    """為指定的 CLI 工具建立 Hooks 路由"""

    router = APIRouter(
        prefix=f"/{tool.value}",
        tags=[f"{tool.value} - Hooks"],
    )

    get_service = make_hooks_service_dependency(tool)

    @router.get(
        "/hooks",
        response_model=CliHookScopesResponse,
        summary="取得所有 Hook 範圍",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope | None = Query(
            None, description="可指定僅回傳某範圍"
        ),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopesResponse:
        return service.list_scopes(workspace_id, scope)

    @router.get(
        "/hooks/export",
        response_model=CliHookExportResponse,
        summary="匯出 Hook 設定",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def export_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope | None = Query(
            None, description="若提供則僅匯出指定範圍"
        ),
        service: CliHookService = Depends(get_service),
    ) -> CliHookExportResponse:
        scope_filter = [scope] if scope else None
        return service.export_scopes(workspace_id, scope_filter)

    @router.get(
        "/hooks/{scope}",
        response_model=CliHookScopeResponse,
        summary="取得指定範圍 Hook",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook 範圍"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopeResponse:
        return service.get_scope(workspace_id, scope)

    @router.put(
        "/hooks/{scope}",
        response_model=CliHookScopeResponse,
        summary="更新 Hook 範圍",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def update_scope_hooks(
        payload: CliHookScopeUpsertRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook 範圍"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopeResponse:
        return service.update_scope(workspace_id, scope, payload)

    @router.delete(
        "/hooks/{scope}",
        response_model=CliHookDeleteResponse,
        summary="刪除 Hook 範圍",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_scope_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook 範圍"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookDeleteResponse:
        return service.delete_scope(workspace_id, scope)

    @router.post(
        "/hooks/import",
        response_model=CliHookImportResponse,
        summary="匯入 Hook 設定",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def import_hooks(
        payload: CliHookImportRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookImportResponse:
        return service.import_scopes(workspace_id, payload)

    return router
