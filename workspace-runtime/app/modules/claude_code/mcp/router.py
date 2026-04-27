"""MCP API Routes"""

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

router = APIRouter(tags=["Claude Code - MCP Servers"])


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
    summary="List MCP servers",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def list_servers(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope | None = Query(
        None, description="If specified, only return settings for that scope"
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
    summary="Get MCP servers for specified scope",
    responses=build_responses(400, 401, 404, 500),
)
async def get_scope(
    scope: DocumentScope = Path(..., description="Configuration scope"),
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
    summary="Get single MCP server",
    responses=build_responses(400, 401, 404, 500),
)
async def get_server(
    scope: DocumentScope = Path(..., description="Configuration scope"),
    server_name: str = Path(..., description="Server name"),
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
    summary="Create MCP server",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_server(
    payload: McpServerCreateRequest,
    scope: DocumentScope = Path(..., description="Configuration scope"),
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
    summary="Update MCP server",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_server(
    payload: McpServerUpdateRequest,
    scope: DocumentScope = Path(..., description="Configuration scope"),
    server_name: str = Path(..., description="Server name"),
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
    summary="Delete MCP server",
    responses=build_responses(400, 401, 403, 404, 500),
)
async def delete_server(
    scope: DocumentScope = Path(..., description="Configuration scope"),
    server_name: str = Path(..., description="Server name"),
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
    summary="Toggle MCP server enabled status",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def toggle_server_status(
    scope: DocumentScope = Path(..., description="Configuration scope"),
    server_name: str = Path(..., description="Server name"),
    enabled: bool = Query(..., description="Whether enabled"),
    workspace_id: str = Path(..., description="Workspace ID"),
    service: McpService = Depends(get_mcp_service),
) -> McpScopeResponse:
    """Toggle MCP server enabled/disabled status

    This operation updates the projects./workspace.disabledMcpServers array in ~/.claude.json
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
    summary="Export MCP server configuration",
    responses=build_responses(400, 401, 404, 500),
)
async def export_server(
    scope: DocumentScope = Path(..., description="Configuration scope"),
    server_name: str = Path(..., description="Server name"),
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
    summary="Import MCP configuration",
    responses=build_responses(400, 401, 403, 404, 422, 500),
)
async def import_servers(
    workspace_id: str = Path(..., description="Workspace ID"),
    scope: DocumentScope = Form(..., description="Import target scope"),
    file: UploadFile = File(..., description="Claude Desktop configuration file (JSON)"),
    overwrite: bool = Form(False, description="Whether to overwrite existing configuration"),
    service: McpService = Depends(get_mcp_service),
) -> McpImportResponse:
    try:
        # Read uploaded file content
        file_content = await file.read()

        # Create import request object
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
