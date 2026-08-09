"""CLI MCP API routes

Factory function that generates identical MCP endpoint collections for each CLI tool.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Path,
    Query,
    UploadFile,
)

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error

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
from .configuration import (
    CliMcpScopeNotSupportedError,
    CliMcpServerAlreadyExistsError,
    CliMcpServerNotFoundError,
    CliMcpReadOnlyScopeError,
    CliMcpToggleNotSupportedError,
    CliMcpService,
    McpTool,
)


# === Error conversion helpers ==============================================


def _scope_error(error: CliMcpScopeNotSupportedError) -> NoReturn:
    raise_resource_error("SCOPE_NOT_SUPPORTED", str(error), 404)


def _server_missing(server_name: str) -> NoReturn:
    raise_resource_error(
        "SERVER_NOT_FOUND",
        f"Server '{server_name}' not found",
        404,
    )


def _duplicate_error(error: CliMcpServerAlreadyExistsError) -> NoReturn:
    raise_resource_error("409_DUPLICATE_NAME", str(error), 409)


def _invalid_payload(error: ValueError) -> NoReturn:
    message = str(error) or "Invalid payload"
    raise_resource_error("400_INVALID_PAYLOAD", message, 400)


def _toggle_not_supported(error: CliMcpToggleNotSupportedError) -> NoReturn:
    raise_resource_error("TOGGLE_NOT_SUPPORTED", str(error), 404)


def _read_only_scope(error: CliMcpReadOnlyScopeError) -> NoReturn:
    raise_resource_error("READ_ONLY_SCOPE", str(error), 400)


# === Router Factory ====================================================


def create_mcp_router(tool: McpTool) -> APIRouter:
    """Create MCP routes for specified CLI tool"""

    router = APIRouter(
        prefix=f"/{tool.value}",
        tags=[f"{tool.value} - MCP Servers"],
    )

    get_service = make_mcp_service_dependency(tool)

    # ----- LIST ----------------------------------------------------------

    @router.get(
        "/mcp-servers",
        response_model=CliMcpServerCollectionResponse,
        summary="List MCP servers",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def list_servers(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliMcpScope | None = Query(
            None, description="If specified, only return configuration for that scope"
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
        summary="Get MCP servers for specified scope",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_scope(
        scope: CliMcpScope = Path(..., description="Configuration scope"),
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
        summary="Get single MCP server",
        responses=build_responses(400, 401, 404, 500),
    )
    async def get_server(
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        server_name: str = Path(..., description="Server name"),
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
        summary="Create MCP servers",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def create_server(
        payload: CliMcpServerCreateRequest,
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.create_servers(workspace_id, scope, payload)
        except CliMcpReadOnlyScopeError as error:
            raise _read_only_scope(error) from error
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
        summary="Update MCP server",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def update_server(
        payload: CliMcpServerUpdateRequest,
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        server_name: str = Path(..., description="Server name"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.update_server(workspace_id, scope, server_name, payload)
        except CliMcpReadOnlyScopeError as error:
            raise _read_only_scope(error) from error
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
        summary="Delete MCP server",
        responses=build_responses(400, 401, 403, 404, 500),
    )
    async def delete_server(
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        server_name: str = Path(..., description="Server name"),
        revision: str = Query(..., description="Expected content revision token"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpServerDeleteResponse:
        try:
            return service.delete_server(workspace_id, scope, server_name, revision)
        except CliMcpReadOnlyScopeError as error:
            raise _read_only_scope(error) from error
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except CliMcpServerNotFoundError:
            raise _server_missing(server_name)

    # ----- TOGGLE --------------------------------------------------------

    @router.patch(
        "/mcp-servers/{scope}/{server_name}/toggle",
        response_model=CliMcpScopeResponse,
        summary="Toggle MCP server enabled status",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def toggle_server_status(
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        server_name: str = Path(..., description="Server name"),
        enabled: bool = Query(..., description="Whether to enable"),
        revision: str = Query(..., description="Expected content revision token"),
        workspace_id: str = Path(..., description="Workspace ID"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpScopeResponse:
        try:
            return service.toggle_server_status(
                workspace_id, scope, server_name, enabled, revision
            )
        except CliMcpReadOnlyScopeError as error:
            raise _read_only_scope(error) from error
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
        summary="Export MCP server configuration",
        responses=build_responses(400, 401, 404, 500),
    )
    async def export_server(
        scope: CliMcpScope = Path(..., description="Configuration scope"),
        server_name: str = Path(..., description="Server name"),
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
        summary="Import MCP configuration",
        responses=build_responses(400, 401, 403, 404, 422, 500),
    )
    async def import_servers(
        workspace_id: str = Path(..., description="Workspace ID"),
        scope: CliMcpScope = Form(..., description="Import target scope"),
        file: UploadFile = File(..., description="MCP configuration file (JSON)"),
        overwrite: bool = Form(
            False, description="Whether to overwrite existing configuration"
        ),
        revision: str = Form(..., description="Expected content revision token"),
        service: CliMcpService = Depends(get_service),
    ) -> CliMcpImportResponse:
        try:
            file_content = await file.read()
            payload = CliMcpImportUploadRequest(
                scope=scope,
                revision=revision,
                file=file_content,
                overwrite=overwrite,
            )
            return service.import_servers_from_file(workspace_id, payload)
        except CliMcpReadOnlyScopeError as error:
            raise _read_only_scope(error) from error
        except CliMcpScopeNotSupportedError as error:
            raise _scope_error(error) from error
        except ValueError as error:
            raise _invalid_payload(error) from error

    return router
