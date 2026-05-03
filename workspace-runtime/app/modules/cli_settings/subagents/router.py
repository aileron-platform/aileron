"""CLI subagents routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from app.modules.claude_code.common import DocumentScope, check_scope_writable

from .config import SubagentTool
from .dependencies import get_gemini_subagent_service, get_subagent_service
from .models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentUpdateRequest,
)
from .service import SubagentService


def _validate_subagent_scope(
    scope: DocumentScope,
    *,
    tool: SubagentTool,
    check_writable: bool = False,
) -> None:
    if scope == DocumentScope.LOCAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCOPE", "message": "Subagents does not support LOCAL scope"},
        )
    if scope == DocumentScope.PLUGIN and tool != SubagentTool.CLAUDE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCOPE", "message": "Subagents does not support PLUGIN scope"},
        )

    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "SCOPE_READ_ONLY", "message": str(error)},
            ) from error


def create_subagents_router(tool: SubagentTool) -> APIRouter:
    router = APIRouter(prefix=f"/{tool.value}/subagents", tags=[f"{tool.value} - Subagents"])

    service_dependency = get_subagent_service if tool == SubagentTool.CLAUDE else get_gemini_subagent_service

    @router.get(
        "",
        response_model=SubagentCollectionResponse,
        summary="List all subagents",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_subagents(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope | None = Query(None, description="Optionally return only specified scope"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentCollectionResponse:
        if scope is not None:
            _validate_subagent_scope(scope, tool=tool)
        return service.list_scopes(workspace_id, scope)

    @router.get(
        "/{scope}",
        response_model=SubagentScopeResponse,
        summary="Get subagents for specified scope",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope_subagents(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentScopeResponse:
        _validate_subagent_scope(scope, tool=tool)
        return service.get_scope(workspace_id, scope)

    @router.get(
        "/{scope}/{file_name}",
        response_model=SubagentDocumentResponse,
        summary="Get subagent content",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_subagent(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        file_name: str = Path(..., description="File name"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDocumentResponse:
        _validate_subagent_scope(scope, tool=tool)
        return service.get_document(workspace_id, scope, file_name)

    @router.post(
        "/{scope}",
        response_model=SubagentDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create subagent",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def create_subagent(
        payload: SubagentCreateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDocumentResponse:
        _validate_subagent_scope(scope, tool=tool, check_writable=True)
        return service.create_document(workspace_id, scope, payload)

    @router.put(
        "/{scope}/{file_name}",
        response_model=SubagentDocumentResponse,
        summary="Update subagent",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_subagent(
        payload: SubagentUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        file_name: str = Path(..., description="File name"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDocumentResponse:
        _validate_subagent_scope(scope, tool=tool, check_writable=True)
        return service.update_document(workspace_id, scope, file_name, payload)

    @router.delete(
        "/{scope}/{file_name}",
        response_model=SubagentDeleteResponse,
        summary="Delete subagent",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_subagent(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        file_name: str = Path(..., description="File name"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDeleteResponse:
        _validate_subagent_scope(scope, tool=tool, check_writable=True)
        service.delete_document(workspace_id, scope, file_name)
        return SubagentDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            fileName=file_name,
            deleted=True,
        )

    return router
