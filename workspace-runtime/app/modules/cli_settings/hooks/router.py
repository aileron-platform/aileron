"""CLI Hooks API router

Factory function to generate identical Hooks endpoint sets for each CLI tool.
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
    """Create Hooks router for specified CLI tool"""

    router = APIRouter(
        prefix=f"/{tool.value}",
        tags=[f"{tool.value} - Hooks"],
    )

    get_service = make_hooks_service_dependency(tool)

    @router.get(
        "/hooks",
        response_model=CliHookScopesResponse,
        summary="Get all Hook scopes",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope | None = Query(
            None, description="Optionally specify to return only one scope"
        ),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopesResponse:
        return service.list_scopes(workspace_id, scope)

    @router.get(
        "/hooks/export",
        response_model=CliHookExportResponse,
        summary="Export Hook configuration",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def export_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope | None = Query(
            None, description="If provided, export only specified scope"
        ),
        service: CliHookService = Depends(get_service),
    ) -> CliHookExportResponse:
        scope_filter = [scope] if scope else None
        return service.export_scopes(workspace_id, scope_filter)

    @router.get(
        "/hooks/{scope}",
        response_model=CliHookScopeResponse,
        summary="Get specified scope Hooks",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook scope"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopeResponse:
        return service.get_scope(workspace_id, scope)

    @router.put(
        "/hooks/{scope}",
        response_model=CliHookScopeResponse,
        summary="Update Hook scope",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def update_scope_hooks(
        payload: CliHookScopeUpsertRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook scope"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookScopeResponse:
        return service.update_scope(workspace_id, scope, payload)

    @router.delete(
        "/hooks/{scope}",
        response_model=CliHookDeleteResponse,
        summary="Delete Hook scope",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_scope_hooks(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliHookScope = Path(..., description="Hook scope"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookDeleteResponse:
        return service.delete_scope(workspace_id, scope)

    @router.post(
        "/hooks/import",
        response_model=CliHookImportResponse,
        summary="Import Hook configuration",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def import_hooks(
        payload: CliHookImportRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliHookService = Depends(get_service),
    ) -> CliHookImportResponse:
        return service.import_scopes(workspace_id, payload)

    return router
