"""CLI Slash Commands API router

Factory function to generate slash commands endpoint sets for each CLI tool.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error

from .config import SlashCommandScope, SlashCommandTool
from .dependencies import make_slash_command_service_dependency
from .models import (
    CliSlashCommandCreateRequest,
    CliSlashCommandDeleteResponse,
    CliSlashCommandDocumentResponse,
    CliSlashCommandScopeResponse,
    CliSlashCommandScopesResponse,
    CliSlashCommandUpdateRequest,
)
from .catalog import (
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
    CliSlashCommandService,
)


# === Error conversion helpers ==============================================


def _not_found(path: str) -> NoReturn:
    raise_resource_error(
        "404_NOT_FOUND",
        f"Slash command '{path}' not found",
        status.HTTP_404_NOT_FOUND,
    )


def _duplicate(error: CliSlashCommandDuplicateError) -> NoReturn:
    raise_resource_error(
        "DUPLICATE_FILE_NAME",
        str(error),
        status.HTTP_409_CONFLICT,
    )


# === Router factory ========================================================


def create_slash_commands_router(tool: SlashCommandTool) -> APIRouter:
    """Create slash commands router for specified CLI tool"""

    router = APIRouter(
        prefix=f"/{tool.value}/slash-commands",
        tags=[f"{tool.value} - Slash Commands"],
    )

    get_service = make_slash_command_service_dependency(tool)

    # ----- LIST ----------------------------------------------------------

    @router.get(
        "",
        response_model=CliSlashCommandScopesResponse,
        summary="List all commands",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_commands(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope | None = Query(
            None, description="If specified, only return this scope"
        ),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandScopesResponse:
        return service.list_scopes(workspace_id, scope)

    # ----- GET SCOPE -----------------------------------------------------

    @router.get(
        "/{scope}",
        response_model=CliSlashCommandScopeResponse,
        summary="Get commands for specified scope",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope_commands(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandScopeResponse:
        return service.get_scope(workspace_id, scope)

    # ----- GET DOCUMENT --------------------------------------------------

    @router.get(
        "/{scope}/content",
        response_model=CliSlashCommandDocumentResponse,
        summary="Get command content",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        path: str = Query(..., description="File path"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.get_document(
                workspace_id,
                scope,
                path,
            )
        except CliSlashCommandNotFoundError:
            raise _not_found(path)

    # ----- CREATE --------------------------------------------------------

    @router.post(
        "/{scope}",
        response_model=CliSlashCommandDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create command",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def create_command(
        payload: CliSlashCommandCreateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.create_document(workspace_id, scope, payload)
        except CliSlashCommandDuplicateError as error:
            raise _duplicate(error) from error

    # ----- UPDATE --------------------------------------------------------

    @router.put(
        "/{scope}/content",
        response_model=CliSlashCommandDocumentResponse,
        summary="Update command",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_command(
        payload: CliSlashCommandUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.update_document(workspace_id, scope, payload)
        except CliSlashCommandNotFoundError:
            raise _not_found(payload.path)

    # ----- DELETE --------------------------------------------------------

    @router.delete(
        "/{scope}/content",
        response_model=CliSlashCommandDeleteResponse,
        summary="Delete command",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        path: str = Query(..., description="File path"),
        revision: str = Query(..., description="Expected document revision token"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDeleteResponse:
        try:
            return service.delete_document(
                workspace_id,
                scope,
                path,
                revision=revision,
            )
        except CliSlashCommandNotFoundError:
            raise _not_found(path)

    return router
