"""CLI subagents routes."""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error
from app.modules.claude_code.documents import DocumentScope, check_scope_writable

from .config import SubagentTool
from .dependencies import get_claude_subagent_service, get_subagent_service
from .models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentUpdateRequest,
)
from .catalog import SubagentService

T = TypeVar("T")


def _call_service(operation: Callable[[], T]) -> T:
    try:
        return operation()
    except HTTPException as error:
        detail: object = error.detail
        if isinstance(detail, dict) and "error" in detail:
            raise_resource_error(
                str(detail["error"]),
                str(detail.get("message") or detail["error"]),
                error.status_code,
            )
        raise


def _validate_subagent_scope(
    scope: DocumentScope,
    *,
    tool: SubagentTool,
    check_writable: bool = False,
) -> None:
    if scope == DocumentScope.LOCAL:
        raise_resource_error(
            "INVALID_SCOPE",
            "Subagents does not support LOCAL scope",
            status.HTTP_400_BAD_REQUEST,
        )
    if scope == DocumentScope.PLUGIN and tool != SubagentTool.CLAUDE:
        raise_resource_error(
            "INVALID_SCOPE",
            "Subagents does not support PLUGIN scope",
            status.HTTP_400_BAD_REQUEST,
        )

    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as error:
            raise_resource_error(
                "SCOPE_READ_ONLY", str(error), status.HTTP_403_FORBIDDEN
            )


def create_subagents_router(tool: SubagentTool) -> APIRouter:
    router = APIRouter(
        prefix=f"/{tool.value}/subagents", tags=[f"{tool.value} - Subagents"]
    )

    def _service() -> SubagentService:
        return get_subagent_service(tool)

    service_dependency = (
        get_claude_subagent_service if tool == SubagentTool.CLAUDE else _service
    )

    @router.get(
        "",
        response_model=SubagentCollectionResponse,
        summary="List all subagents",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_subagents(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope | None = Query(
            None, description="Optionally return only specified scope"
        ),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentCollectionResponse:
        if scope is not None:
            _validate_subagent_scope(scope, tool=tool)
        return _call_service(lambda: service.list_scopes(workspace_id, scope))

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
        return _call_service(lambda: service.get_scope(workspace_id, scope))

    @router.get(
        "/{scope}/content",
        response_model=SubagentDocumentResponse,
        summary="Get subagent content",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_subagent(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        path: str = Query(..., description="File path"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDocumentResponse:
        _validate_subagent_scope(scope, tool=tool)
        return _call_service(lambda: service.get_document(workspace_id, scope, path))

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
        return _call_service(
            lambda: service.create_document(workspace_id, scope, payload)
        )

    @router.put(
        "/{scope}/content",
        response_model=SubagentDocumentResponse,
        summary="Update subagent",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_subagent(
        payload: SubagentUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDocumentResponse:
        _validate_subagent_scope(scope, tool=tool, check_writable=True)
        return _call_service(
            lambda: service.update_document(workspace_id, scope, payload)
        )

    @router.delete(
        "/{scope}/content",
        response_model=SubagentDeleteResponse,
        summary="Delete subagent",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_subagent(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: DocumentScope = Path(..., description="Subagent scope"),
        path: str = Query(..., description="File path"),
        revision: str = Query(..., description="Expected document revision token"),
        service: SubagentService = Depends(service_dependency),
    ) -> SubagentDeleteResponse:
        _validate_subagent_scope(scope, tool=tool, check_writable=True)
        return _call_service(
            lambda: service.delete_document(
                workspace_id,
                scope,
                path,
                revision=revision,
            )
        )

    return router
