"""Slash Commands Routes"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from ..common import DocumentScope, check_scope_writable
from .dependencies import get_slash_command_service
from .models import (
    SlashCommandCreateRequest,
    SlashCommandDeleteResponse,
    SlashCommandDocumentResponse,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)
from .service import SlashCommandService

router = APIRouter(prefix="/slash-commands", tags=["Claude Code - Slash Commands"])


def _validate_slash_command_scope(scope: DocumentScope, *, check_writable: bool = False) -> None:
    """Validate Slash Commands scope

    Args:
        scope: Scope to validate
        check_writable: Whether to check writability (for POST/PUT/DELETE operations)
    """
    if scope == DocumentScope.LOCAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCOPE", "message": "Slash Commands does not support LOCAL scope"},
        )

    if check_writable:
        try:
            check_scope_writable(scope)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": "SCOPE_READ_ONLY", "message": str(e)},
            ) from e


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
    return service.list_scopes(workspace_id, scope)


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
    return service.get_scope(workspace_id, scope)


@router.get(
    "/{scope}/{file_name}",
    response_model=SlashCommandDocumentResponse,
    summary="Get command content",
    responses=build_responses(400, 401, 404, 500),
)
async def get_slash_command(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    file_name: str = Path(..., description="File name"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDocumentResponse:
    _validate_slash_command_scope(scope, check_writable=False)
    return service.get_document(workspace_id, scope, file_name)


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
    return service.create_document(workspace_id, scope, payload)


@router.put(
    "/{scope}/{file_name}",
    response_model=SlashCommandDocumentResponse,
    summary="Update command",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_slash_command(
    payload: SlashCommandUpdateRequest,
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    file_name: str = Path(..., description="File name"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDocumentResponse:
    _validate_slash_command_scope(scope, check_writable=True)
    return service.update_document(workspace_id, scope, file_name, payload)


@router.delete(
    "/{scope}/{file_name}",
    response_model=SlashCommandDeleteResponse,
    summary="Delete command",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_slash_command(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Path(..., description="Command scope"),
    file_name: str = Path(..., description="File name"),
    service: SlashCommandService = Depends(get_slash_command_service),
) -> SlashCommandDeleteResponse:
    _validate_slash_command_scope(scope, check_writable=True)
    service.delete_document(workspace_id, scope, file_name)
    return SlashCommandDeleteResponse(
        workspaceId=workspace_id,
        scope=scope,
        fileName=file_name,
        deleted=True,
    )
