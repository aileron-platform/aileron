"""CLI Slash Commands API router

Factory function to generate slash commands endpoint sets for each CLI tool.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses

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
from .service import (
    CliSlashCommandAmbiguousError,
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
    CliSlashCommandReadOnlyScopeError,
    CliSlashCommandService,
)


# === Error conversion helpers ==============================================


def _not_found(file_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "404_NOT_FOUND",
            "message": f"Slash command '{file_name}' not found",
        },
    )


def _duplicate(error: CliSlashCommandDuplicateError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "DUPLICATE_FILE_NAME", "message": str(error)},
    )


def _ambiguous(error: CliSlashCommandAmbiguousError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "AMBIGUOUS_DOCUMENT", "message": str(error)},
    )


def _read_only(error: CliSlashCommandReadOnlyScopeError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error": "READ_ONLY_SCOPE",
            "messageKey": "workspace.agentSettings.common.errors.readOnlyScope",
            "message": str(error),
        },
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
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDocumentResponse,
        summary="Get command content",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        file_name: str = Path(..., description="File name"),
        namespace: str | None = Query(None, description="Command namespace"),
        extension_name: str | None = Query(None, alias="extensionName", description="Gemini extension name"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.get_document(
                workspace_id,
                scope,
                file_name,
                namespace=namespace,
                extension_name=extension_name,
            )
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

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
        except CliSlashCommandReadOnlyScopeError as error:
            raise _read_only(error) from error
        except CliSlashCommandDuplicateError as error:
            raise _duplicate(error) from error

    # ----- UPDATE --------------------------------------------------------

    @router.put(
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDocumentResponse,
        summary="Update command",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_command(
        payload: CliSlashCommandUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        file_name: str = Path(..., description="File name"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.update_document(workspace_id, scope, file_name, payload)
        except CliSlashCommandReadOnlyScopeError as error:
            raise _read_only(error) from error
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

    # ----- DELETE --------------------------------------------------------

    @router.delete(
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDeleteResponse,
        summary="Delete command",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="Command scope"),
        file_name: str = Path(..., description="File name"),
        namespace: str | None = Query(None, description="Command namespace"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDeleteResponse:
        try:
            return service.delete_document(workspace_id, scope, file_name, namespace=namespace)
        except CliSlashCommandReadOnlyScopeError as error:
            raise _read_only(error) from error
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

    return router
