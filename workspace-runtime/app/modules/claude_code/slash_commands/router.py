"""Slash Commands Routes"""

from __future__ import annotations

from typing import Callable, TypeVar

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error
from ..documents import DocumentScope, check_scope_writable
from .dependencies import get_slash_command_service
from .models import (
    SlashCommandCreateRequest,
    SlashCommandDeleteResponse,
    SlashCommandDocumentResponse,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)
from .catalog import SlashCommandService

router = APIRouter(prefix="/slash-commands", tags=["Claude Code - Slash Commands"])

T = TypeVar("T")


def _call_service(operation: Callable[[], T]) -> T:
    return operation()


def _validate_slash_command_scope(
    scope: DocumentScope, *, check_writable: bool = False
) -> None:
    """Validate Slash Commands scope

    Args:
        scope: Scope to validate
        check_writable: Whether to check writability (for POST/PUT/DELETE operations)
    """
    if scope == DocumentScope.LOCAL:
        raise_resource_error(
            "INVALID_SCOPE",
            "Slash Commands does not support LOCAL scope",
            status.HTTP_400_BAD_REQUEST,
        )

    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as e:
            raise_resource_error("SCOPE_READ_ONLY", str(e), status.HTTP_403_FORBIDDEN)


@router.get(
    "",
    response_model=SlashCommandScopesResponse,
    summary="List all commands",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_slash_commands(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="Optionally return only specified scope"
    ),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandScopesResponse:
    return _call_service(lambda: service.list_scopes(workspace_id, scope))


@router.get(
    "/{scope}",
    response_model=SlashCommandScopeResponse,
    summary="Get commands for specified scope",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope_commands(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandScopeResponse:
    _validate_slash_command_scope(scope, check_writable=False)
    return _call_service(lambda: service.get_scope(workspace_id, scope))


@router.get(
    "/{scope}/content",
    response_model=SlashCommandDocumentResponse,
    summary="Get command content",
    responses=build_responses(400, 401, 404, 500),
)
async def get_slash_command(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    path: str = Query(..., description="File path"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDocumentResponse:
    _validate_slash_command_scope(scope, check_writable=False)
    return _call_service(lambda: service.get_document(workspace_id, scope, path))


@router.post(
    "/{scope}",
    response_model=SlashCommandDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create command",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_slash_command(
    payload: SlashCommandCreateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDocumentResponse:
    _validate_slash_command_scope(scope, check_writable=True)
    return _call_service(lambda: service.create_document(workspace_id, scope, payload))


@router.put(
    "/{scope}/content",
    response_model=SlashCommandDocumentResponse,
    summary="Update command",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_slash_command(
    payload: SlashCommandUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDocumentResponse:
    _validate_slash_command_scope(scope, check_writable=True)
    return _call_service(lambda: service.update_document(workspace_id, scope, payload))


@router.delete(
    "/{scope}/content",
    response_model=SlashCommandDeleteResponse,
    summary="Delete command",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_slash_command(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    path: str = Query(..., description="File path"),
    revision: str = Query(..., description="Expected document revision token"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDeleteResponse:
    _validate_slash_command_scope(scope, check_writable=True)
    return _call_service(
        lambda: service.delete_document(workspace_id, scope, path, revision)
    )
