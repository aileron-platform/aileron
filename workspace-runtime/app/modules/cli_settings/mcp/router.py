"""CLI MCP API 路由

工廠函數，為每個 CLI 工具產生相同的 MCP 端點集合。
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    Query,
    UploadFile,
    status,
)

from app.core.openapi import build_responses

from .dependencies import make_mcp_service_dependency
from .models import (
    CliMcpImportResponse,
    CliMcpImportUploadRequest,
    CliMcpScope,
    CliMcpScopeResponse,
    CliMcpServerCollectionResponse,
    CliMcpServerCreateRequest,
    CliMcpServerDeleteResponse,
    CliMcpServerExportResponse,
    CliMcpServerUpdateRequest,
)
from .service import (
    CliMcpScopeNotSupportedError,
    CliMcpServerAlreadyExistsError,
    CliMcpServerNotFoundError,
    CliMcpToggleNotSupportedError,
    CliMcpService,
    McpTool,
)


# === 錯誤轉換 helpers ===================================================


def _scope_error(error: CliMcpScopeNotSupportedError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "SCOPE_NOT_SUPPORTED", "message": str(error)},
    )


def _server_missing(server_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "SERVER_NOT_FOUND",
            "message": f"Server '{server_name}' not found",
            "serverName": server_name,
        },
    )


def _duplicate_error(error: CliMcpServerAlreadyExistsError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"error": "409_DUPLICATE_NAME", "message": str(error)},
    )


def _invalid_payload(error: ValueError) -> HTTPException:
    message = str(error) or "Invalid payload"
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": "400_INVALID_PAYLOAD", "message": message},
    )


def _toggle_not_supported(error: CliMcpToggleNotSupportedError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "TOGGLE_NOT_SUPPORTED", "message": str(error)},
    )


# === 路由工廠 ============================================================


def create_mcp_router(tool: McpTool) -> APIRouter:
    """為指定的 CLI 工具建立 MCP 路由"""

    router = APIRouter(
        prefix=f"/{tool.value}",
        tags=[f"{tool.value} - MCP 伺服器"],
    )

    get_service = make_mcp_service_dependency(tool)

    # ----- LIST ----------------------------------------------------------

    @router.get(
        "/mcp-servers",
        response_model=CliMcpServerCollectionResponse,
        summary="列出 MCP 伺服器",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_servers(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliMcpScope | None = Query(
            None, description="若指定則僅回傳該範圍設定"
        ),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpServerCollectionResponse:
        try:
            return service.list_servers(workspace_id, scope)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error

    # ----- GET SCOPE -----------------------------------------------------

    @router.get(
        "/mcp-servers/{scope}",
        response_model=CliMcpScopeResponse,
        summary="取得指定範圍的 MCP 伺服器",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope(
        scope: CliMcpScope = Path(..., description="設定範圍"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.get_scope(workspace_id, scope)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error

    # ----- GET SERVER ----------------------------------------------------

    @router.get(
        "/mcp-servers/{scope}/{server_name}",
        response_model=CliMcpScopeResponse,
        summary="取得單一 MCP 伺服器",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_server(
        scope: CliMcpScope = Path(..., description="設定範圍"),
        server_name: str = Path(..., description="伺服器名稱"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.get_server(workspace_id, scope, server_name)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)

    # ----- CREATE --------------------------------------------------------

    @router.post(
        "/mcp-servers/{scope}",
        response_model=CliMcpScopeResponse,
        summary="建立 MCP 伺服器",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def create_server(
        payload: CliMcpServerCreateRequest,
        scope: CliMcpScope = Path(..., description="設定範圍"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.create_servers(workspace_id, scope, payload)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerAlreadyExistsError as error:
            raise _duplicate_error(error) from error
        except ValueError as error:
            raise _invalid_payload(error) from error

    # ----- UPDATE --------------------------------------------------------

    @router.put(
        "/mcp-servers/{scope}/{server_name}",
        response_model=CliMcpScopeResponse,
        summary="更新 MCP 伺服器",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_server(
        payload: CliMcpServerUpdateRequest,
        scope: CliMcpScope = Path(..., description="設定範圍"),
        server_name: str = Path(..., description="伺服器名稱"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.update_server(
                workspace_id, scope, server_name, payload
            )
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)
        except CliMcpServerAlreadyExistsError as error:
            raise _duplicate_error(error) from error
        except ValueError as error:
            raise _invalid_payload(error) from error

    # ----- DELETE --------------------------------------------------------

    @router.delete(
        "/mcp-servers/{scope}/{server_name}",
        response_model=CliMcpServerDeleteResponse,
        summary="刪除 MCP 伺服器",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_server(
        scope: CliMcpScope = Path(..., description="設定範圍"),
        server_name: str = Path(..., description="伺服器名稱"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpServerDeleteResponse:
        try:
            return service.delete_server(workspace_id, scope, server_name)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)

    # ----- TOGGLE --------------------------------------------------------

    @router.patch(
        "/mcp-servers/{scope}/{server_name}/toggle",
        response_model=CliMcpScopeResponse,
        summary="切換 MCP 伺服器啟用狀態",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def toggle_server_status(
        scope: CliMcpScope = Path(..., description="設定範圍"),
        server_name: str = Path(..., description="伺服器名稱"),
        enabled: bool = Query(..., description="是否啟用"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.toggle_server_status(
                workspace_id, scope, server_name, enabled
            )
        except CliMcpToggleNotSupportedError as error:
            raise _toggle_not_supported(error) from error
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)

    # ----- EXPORT --------------------------------------------------------

    @router.get(
        "/mcp-servers/{scope}/{server_name}/export",
        response_model=CliMcpServerExportResponse,
        summary="匯出 MCP 伺服器設定",
        responses=build_responses(400, 401, 404, 500),
    )
    async def export_server(
        scope: CliMcpScope = Path(..., description="設定範圍"),
        server_name: str = Path(..., description="伺服器名稱"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpServerExportResponse:
        try:
            return service.export_server(workspace_id, scope, server_name)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)

    # ----- IMPORT (file upload) ------------------------------------------

    @router.post(
        "/mcp-import",
        response_model=CliMcpImportResponse,
        summary="匯入 MCP 設定",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def import_servers(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliMcpScope = Form(..., description="匯入目標範圍"),
        file: UploadFile = File(..., description="MCP 配置檔案 (JSON)"),
        overwrite: bool = Form(False, description="是否覆寫既有設定"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpImportResponse:
        try:
            file_content = await file.read()
            payload = CliMcpImportUploadRequest(
                scope=scope, file=file_content, overwrite=overwrite
            )
            return service.import_servers_from_file(workspace_id, payload)
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except ValueError as error:
            raise _invalid_payload(error) from error

    return router
