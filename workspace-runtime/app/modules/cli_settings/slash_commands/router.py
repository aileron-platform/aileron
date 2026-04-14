"""CLI Slash Commands API 路由

工廠函數，為每個 CLI 工具產生 slash commands 端點集合。
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
    CliSlashCommandService,
)


# === 錯誤轉換 helpers ===================================================


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


# === 路由工廠 ============================================================


def create_slash_commands_router(tool: SlashCommandTool) -> APIRouter:
    """為指定的 CLI 工具建立 slash commands 路由"""

    router = APIRouter(
        prefix=f"/{tool.value}/slash-commands",
        tags=[f"{tool.value} - Slash Commands"],
    )

    get_service = make_slash_command_service_dependency(tool)

    # ----- LIST ----------------------------------------------------------

    @router.get(
        "",
        response_model=CliSlashCommandScopesResponse,
        summary="列出所有命令",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_commands(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope | None = Query(
            None, description="若指定則僅回傳該範圍"
        ),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandScopesResponse:
        return service.list_scopes(workspace_id, scope)

    # ----- GET SCOPE -----------------------------------------------------

    @router.get(
        "/{scope}",
        response_model=CliSlashCommandScopeResponse,
        summary="取得指定範圍命令",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope_commands(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="命令範圍"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandScopeResponse:
        return service.get_scope(workspace_id, scope)

    # ----- GET DOCUMENT --------------------------------------------------

    @router.get(
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDocumentResponse,
        summary="取得命令內容",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="命令範圍"),
        file_name: str = Path(..., description="檔案名稱"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.get_document(workspace_id, scope, file_name)
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

    # ----- CREATE --------------------------------------------------------

    @router.post(
        "/{scope}",
        response_model=CliSlashCommandDocumentResponse,
        status_code=status.HTTP_201_CREATED,
        summary="新增命令",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def create_command(
        payload: CliSlashCommandCreateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="命令範圍"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.create_document(workspace_id, scope, payload)
        except CliSlashCommandDuplicateError as error:
            raise _duplicate(error) from error

    # ----- UPDATE --------------------------------------------------------

    @router.put(
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDocumentResponse,
        summary="更新命令",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_command(
        payload: CliSlashCommandUpdateRequest,
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="命令範圍"),
        file_name: str = Path(..., description="檔案名稱"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDocumentResponse:
        try:
            return service.update_document(workspace_id, scope, file_name, payload)
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

    # ----- DELETE --------------------------------------------------------

    @router.delete(
        "/{scope}/{file_name}",
        response_model=CliSlashCommandDeleteResponse,
        summary="刪除命令",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_command(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: SlashCommandScope = Path(..., description="命令範圍"),
        file_name: str = Path(..., description="檔案名稱"),
        service: CliSlashCommandService = Depends(get_service),
    ) -> CliSlashCommandDeleteResponse:
        try:
            return service.delete_document(workspace_id, scope, file_name)
        except CliSlashCommandAmbiguousError as error:
            raise _ambiguous(error) from error
        except CliSlashCommandNotFoundError:
            raise _not_found(file_name)

    return router
