"""MCP API 路由"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)

from app.core.openapi import build_responses
from ..common import DocumentScope
from .dependencies import get_mcp_service
from .models import (
    McpImportRequest,
    McpImportResponse,
    McpImportUploadRequest,
    McpScopeResponse,
    McpServerCollectionResponse,
    McpServerCreateRequest,
    McpServerDeleteResponse,
    McpServerExportResponse,
    McpServerUpdateRequest,
)
from .service import (
    McpScopeNotSupportedError,
    McpServerAlreadyExistsError,
    McpServerNotFoundError,
    McpService,
)

router = APIRouter(tags=["Claude Code - MCP 伺服器"])


def _scope_error(error: McpScopeNotSupportedError) -> HTTPException:
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


def _duplicate_error(error: McpServerAlreadyExistsError) -> HTTPException:
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


@router.get(
    "/mcp-servers",
    response_model=McpServerCollectionResponse,
    summary="列出 MCP 伺服器",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_servers(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="若指定則僅回傳該範圍設定"
    ),
    service: McpService = Depends(get_mcp_service),
) -> McpServerCollectionResponse:
    try:
        return service.list_servers(workspace_id, scope)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error


@router.get(
    "/mcp-servers/{scope}",
    response_model=McpScopeResponse,
    summary="取得指定範圍的 MCP 伺服器",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope(
    scope: DocumentScope = Path(..., description="設定範圍"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    try:
        return service.get_scope(workspace_id, scope)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error


@router.get(
    "/mcp-servers/{scope}/{server_name}",
    response_model=McpScopeResponse,
    summary="取得單一 MCP 伺服器",
    responses=build_responses(400, 401, 404, 500),
)
async def get_server(
    scope: DocumentScope = Path(..., description="設定範圍"),
    server_name: str = Path(..., description="伺服器名稱"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    try:
        return service.get_server(workspace_id, scope, server_name)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerNotFoundError:
        raise _server_missing(server_name)


@router.post(
    "/mcp-servers/{scope}",
    response_model=McpScopeResponse,
    summary="建立 MCP 伺服器",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_server(
    payload: McpServerCreateRequest,
    scope: DocumentScope = Path(..., description="設定範圍"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    try:
        return service.create_servers(workspace_id, scope, payload)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerAlreadyExistsError as error:
        raise _duplicate_error(error) from error
    except ValueError as error:
        raise _invalid_payload(error) from error


@router.put(
    "/mcp-servers/{scope}/{server_name}",
    response_model=McpScopeResponse,
    summary="更新 MCP 伺服器",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_server(
    payload: McpServerUpdateRequest,
    scope: DocumentScope = Path(..., description="設定範圍"),
    server_name: str = Path(..., description="伺服器名稱"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    try:
        return service.update_server(
            workspace_id, scope, server_name, payload
        )
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerNotFoundError:
        raise _server_missing(server_name)
    except McpServerAlreadyExistsError as error:
        raise _duplicate_error(error) from error
    except ValueError as error:
        raise _invalid_payload(error) from error


@router.delete(
    "/mcp-servers/{scope}/{server_name}",
    response_model=McpServerDeleteResponse,
    summary="刪除 MCP 伺服器",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_server(
    scope: DocumentScope = Path(..., description="設定範圍"),
    server_name: str = Path(..., description="伺服器名稱"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpServerDeleteResponse:
    try:
        return service.delete_server(workspace_id, scope, server_name)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerNotFoundError:
        raise _server_missing(server_name)


@router.patch(
    "/mcp-servers/{scope}/{server_name}/toggle",
    response_model=McpScopeResponse,
    summary="切換 MCP 伺服器啟用狀態",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def toggle_server_status(
    scope: DocumentScope = Path(..., description="設定範圍"),
    server_name: str = Path(..., description="伺服器名稱"),
    enabled: bool = Query(..., description="是否啟用"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    """切換 MCP 伺服器的啟用/停用狀態

    此操作會更新 ~/.claude.json 中的 projects./workspace.disabledMcpServers 陣列
    """
    try:
        return service.toggle_server_status(workspace_id, scope, server_name, enabled)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerNotFoundError:
        raise _server_missing(server_name)


@router.get(
    "/mcp-servers/{scope}/{server_name}/export",
    response_model=McpServerExportResponse,
    summary="匯出 MCP 伺服器設定",
    responses=build_responses(400, 401, 404, 500),
)
async def export_server(
    scope: DocumentScope = Path(..., description="設定範圍"),
    server_name: str = Path(..., description="伺服器名稱"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpServerExportResponse:
    try:
        return service.export_server(workspace_id, scope, server_name)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except McpServerNotFoundError:
        raise _server_missing(server_name)




@router.post(
    "/mcp-import",
    response_model=McpImportResponse,
    summary="匯入 MCP 設定",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def import_servers(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Form(..., description="匯入目標範圍"),
    file: UploadFile = File(..., description="Claude Desktop 配置檔案 (JSON)"),
    overwrite: bool = Form(False, description="是否覆寫既有設定"),
    service: McpService = Depends(get_mcp_service),
) -> McpImportResponse:
    try:
        # 讀取上傳檔案內容
        file_content = await file.read()

        # 建立匯入請求物件
        payload = McpImportUploadRequest(
            scope=scope,
            file=file_content,
            overwrite=overwrite
        )

        return service.import_servers_from_file(workspace_id, payload)
    except McpScopeNotSupportedError as error:
        raise _scope_error(error) from error
    except ValueError as error:
        raise _invalid_payload(error) from error
