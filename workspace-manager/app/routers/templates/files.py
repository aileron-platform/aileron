"""Template file management routes (Commands, Agents, Output Style, AGENTS.md, general file management)"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.core.file_management import (
    BatchOperationResponse,
    FileContentResponse,
    FileManagementException,
    FileOperationResponse,
    FileSearchRequest,
    FileSearchResponse,
    FileTreeResponse,
    FileUploadResponse,
)
from app.db.database import get_db
from app.modules.auth import get_current_user_id
from app.models.template_config import (
    TemplateOutputStyleCreateRequest,
    TemplateOutputStyleListResponse,
    TemplateOutputStyleResponse,
    TemplateOutputStyleUpdateRequest,
    TemplateCommandCreateRequest,
    TemplateCommandListResponse,
    TemplateCommandResponse,
    TemplateCommandUpdateRequest,
    TemplateAgentCreateRequest,
    TemplateAgentListResponse,
    TemplateAgentResponse,
    TemplateAgentUpdateRequest,
)
from app.services.template_file_service import TemplateFileService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)
router = APIRouter()


def _translate_template_service_error(translate, error: str) -> str:
    if "Template not found" in error:
        return translate("templates.not_found")
    if "Invalid filename" in error:
        return translate("templates.file.invalid_filename")
    if "already exists" in error:
        return translate("templates.file.already_exists")
    if "too large" in error:
        return translate("templates.file.too_large")
    return translate("templates.file.operation_failed_simple")


def _raise_template_service_error(result, translate) -> None:
    error = result.error or ""
    if "Template not found" in error or "not found" in error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_translate_template_service_error(translate, error))
    if "Invalid filename" in error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_translate_template_service_error(translate, error))
    if "already exists" in error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=_translate_template_service_error(translate, error))
    if "too large" in error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_translate_template_service_error(translate, error),
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=_translate_template_service_error(translate, error),
    )


def _localize_file_management_exception(translate, exc: FileManagementException) -> dict:
    details = dict(exc.details)
    code = exc.code
    message = exc.message

    if code == "FILE_NOT_FOUND":
        message = translate("templates.file.not_found", path=details.get("path", ""))
    elif code == "FILE_ALREADY_EXISTS":
        message = translate("templates.file.exists", path=details.get("path", ""))
    elif code == "INVALID_PATH":
        message = translate("templates.file.invalid_path")
        reason = details.get("reason")
        if reason == "Path traversal detected":
            details["reason"] = translate("templates.file.path_traversal")
    elif code == "INVALID_SCOPE":
        message = translate("templates.file.invalid_scope", scope=details.get("scope", ""))
    elif code == "READONLY_SCOPE":
        message = translate("templates.file.readonly_scope", scope=details.get("scope", ""))
    elif code == "PERMISSION_DENIED":
        message = translate(
            "templates.file.permission_denied",
            operation=details.get("operation", ""),
            path=details.get("path", ""),
        )
    elif code == "FILE_TOO_LARGE":
        message = translate("templates.file.too_large_generic")
    elif code == "CONTENT_CONFLICT":
        message = translate("templates.file.content_conflict")
    elif code == "DIRECTORY_NOT_EMPTY":
        message = translate("templates.file.directory_not_empty")
    elif code == "INVALID_FILE_TYPE":
        message = translate("templates.file.invalid_type", file_type=details.get("fileType", ""))

    return {
        "code": code,
        "message": message,
        "details": details,
    }


def get_template_service(db: Session = Depends(get_db)) -> TemplateService:
    """Get template service instance"""
    return TemplateService(db)


def get_template_file_service(db: Session = Depends(get_db)) -> TemplateFileService:
    """Get template file service instance"""
    return TemplateFileService(db)


# ============ Commands file management =============


@router.get(
    "/{template_id}/commands",
    response_model=TemplateCommandListResponse,
    summary="Get template commands file list",
    responses=build_responses(401, 404, 500),
)
async def get_template_commands_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandListResponse:
    """Get all files in commands directory of specified template"""
    result = service.get_commands_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/commands/{file_name}",
    response_model=TemplateCommandResponse,
    summary="Get Command FileContent",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_command_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandResponse:
    """Get content of specific command file in specified template"""
    result = service.get_command_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/commands",
    response_model=TemplateCommandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Command File",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_command_file(
    request: Request,
    template_id: str,
    payload: TemplateCommandCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandResponse:
    """Add new file in commands directory of specified template"""
    result = service.create_command_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/commands/{file_name}",
    response_model=TemplateCommandResponse,
    summary="Update Command File",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_template_command_file(
    request: Request,
    template_id: str,
    file_name: str,
    payload: TemplateCommandUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandResponse:
    """Update command file content in specified template"""
    result = service.update_command_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/commands/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Command File",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_command_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """Delete command file from specified template"""
    result = service.delete_command_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ AGENTS.md file management =============


@router.get(
    "/{template_id}/agents-md",
    summary="Get AGENTS.md Content",
    responses=build_responses(401, 404, 500),
)
async def get_template_agents_md(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> dict:
    """Get AGENTS.md content of template"""
    try:
        translate = request.state.translate
        agents_md = service.get_agents_md(template_id)
        if agents_md is None:
            return {
                "success": False,
                "error": "AGENTS.md not found",
                "message": translate("templates.agents_md_empty")
            }
        return {
            "success": True,
            "data": {
                "content": agents_md
            }
        }
    except Exception as e:
        translate = request.state.translate
        return {
            "success": False,
            "error": "Failed to load AGENTS.md",
            "message": translate("templates.agents_md_load_failed_simple")
        }


@router.put(
    "/{template_id}/agents-md",
    summary="Update AGENTS.md Content",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_template_agents_md(
    request: Request,
    template_id: str,
    payload: dict,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> dict:
    """Update AGENTS.md content of template"""
    try:
        translate = request.state.translate
        content = payload.get("content", "")
        if not content.strip():
            return {
                "success": False,
                "error": "Content cannot be empty",
                "message": translate("templates.agents_md_content_empty")
            }

        # Call service method to actually save file
        service.update_agents_md(template_id, content)

        return {
            "success": True,
            "data": {
                "content": content
            },
            "message": translate("templates.agents_md_updated")
        }
    except ValueError as e:
        translate = request.state.translate
        return {
            "success": False,
            "error": "Invalid template or content",
            "message": translate("templates.agents_md_update_failed_simple")
        }
    except Exception as e:
        translate = request.state.translate
        return {
            "success": False,
            "error": "Failed to update AGENTS.md",
            "message": translate("templates.agents_md_update_failed_simple")
        }


# ============ Agents File Management ============


@router.get(
    "/{template_id}/agents",
    response_model=TemplateAgentListResponse,
    summary="Get template agents file list",
    responses=build_responses(401, 404, 500),
)
async def get_template_agents_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentListResponse:
    """Get all files in agents directory of specified template"""
    result = service.get_agents_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/agents/{file_name}",
    response_model=TemplateAgentResponse,
    summary="Get Agent FileContent",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_agent_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentResponse:
    """Get content of specific agent file in specified template"""
    result = service.get_agent_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/agents",
    response_model=TemplateAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Agent File",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_agent_file(
    request: Request,
    template_id: str,
    payload: TemplateAgentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentResponse:
    """Add new file in agents directory of specified template"""
    result = service.create_agent_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/agents/{file_name}",
    response_model=TemplateAgentResponse,
    summary="Update Agent File",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_template_agent_file(
    request: Request,
    template_id: str,
    file_name: str,
    payload: TemplateAgentUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentResponse:
    """Update agent file content in specified template"""
    result = service.update_agent_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/agents/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Agent File",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_agent_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """Delete agent file in specified template"""
    result = service.delete_agent_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ Output Style File Management ============


@router.get(
    "/{template_id}/output-style",
    response_model=TemplateOutputStyleListResponse,
    summary="Get template output style file list",
    responses=build_responses(401, 404, 500),
)
async def get_template_output_style_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleListResponse:
    """Get all files in output-style directory of specified template"""
    result = service.get_output_style_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/output-style/{file_name}",
    response_model=TemplateOutputStyleResponse,
    summary="Get Output Style FileContent",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_output_style_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleResponse:
    """Get content of specific output-style file in specified template"""
    result = service.get_output_style_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/output-style",
    response_model=TemplateOutputStyleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Output Style File",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_output_style_file(
    request: Request,
    template_id: str,
    payload: TemplateOutputStyleCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleResponse:
    """Add new file in output-style directory of specified template"""
    result = service.create_output_style_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/output-style/{file_name}",
    response_model=TemplateOutputStyleResponse,
    summary="Update Output Style File",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_template_output_style_file(
    request: Request,
    template_id: str,
    file_name: str,
    payload: TemplateOutputStyleUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleResponse:
    """Update output-style file content in specified template"""
    result = service.update_output_style_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/output-style/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Output Style File",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_output_style_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """Delete output-style file in specified template"""
    result = service.delete_output_style_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ General File Management API ============


@router.get(
    "/{template_id}/files/tree",
    response_model=FileTreeResponse,
    summary="Get file tree",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_file_tree(
    request: Request,
    template_id: str,
    path: str = Query(default="/", description="Target path"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    include_hidden: bool = Query(default=False, description="Include hidden files"),
    max_depth: Optional[int] = Query(default=None, ge=0, description="Maximum depth (default uses FILE_TREE_MAX_DEPTH from settings file)"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileTreeResponse:
    """Get file tree"""
    try:
        # If max_depth not provided, use default value from settings file
        if max_depth is None:
            settings = get_settings()
            max_depth = settings.FILE_TREE_MAX_DEPTH
        return service.get_tree(template_id, path, scope, include_hidden, max_depth)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.get(
    "/{template_id}/files/content",
    response_model=FileContentResponse,
    summary="ReadFileContent",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def read_file(
    request: Request,
    template_id: str,
    path: str = Query(..., description="File path"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileContentResponse:
    """Read file content"""
    try:
        return service.read_file(template_id, path, scope)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files",
    response_model=FileOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create file or directory",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_entry(
    request: Request,
    template_id: str,
    path: str = Query(..., description="Path"),
    entry_type: str = Query(..., pattern="^(file|directory)$", description="Type: file or directory"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    content: Optional[str] = Query(default="", description="File content (files only)"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """Create file or directory"""
    try:
        result = service.create_entry(template_id, path, entry_type, scope, content)
        return FileOperationResponse(
            success=True,
            path=path,
            scope=scope,
            data=result
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.put(
    "/{template_id}/files/content",
    response_model=FileOperationResponse,
    summary="Write file content",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def write_file(
    request: Request,
    template_id: str,
    path: str = Query(..., description="File path"),
    content: str = Query(..., description="File content"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    expected_version_id: Optional[str] = Query(default=None, description="Expected version ID (conflict detection)"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """Write file content"""
    try:
        result = service.write_file(template_id, path, content, scope, expected_version_id)
        return FileOperationResponse(
            success=True,
            path=path,
            scope=scope,
            data=result
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files/upload",
    response_model=FileUploadResponse,
    summary="Upload files",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def upload_files(
    request: Request,
    template_id: str,
    target_path: str = Form(default="", description="Target directory path"),
    files: List[UploadFile] = File(..., description="Files to upload"),
    overwrite: bool = Form(default=False, description="Whether to overwrite existing files"),
    scope: str = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileUploadResponse:
    """Upload single or multiple files to template"""
    try:
        return await service.upload_files(template_id, target_path, files, overwrite, scope)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.delete(
    "/{template_id}/files",
    response_model=FileOperationResponse,
    summary="Delete file or directory",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def delete_entry(
    request: Request,
    template_id: str,
    path: str = Query(..., description="Path"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    recursive: bool = Query(default=False, description="Whether to recursively delete directory"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """Delete file or directory"""
    try:
        result = service.delete_entry(template_id, path, scope, recursive)
        return FileOperationResponse(
            success=True,
            path=path,
            scope=scope,
            data=result
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files/copy",
    response_model=FileOperationResponse,
    summary="Copy file or directory",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def copy_entry(
    request: Request,
    template_id: str,
    source_path: str = Query(..., description="Source path"),
    dest_path: str = Query(..., description="Destination path"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    overwrite: bool = Query(default=False, description="Whether to overwrite"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """Copy file or directory"""
    try:
        result = service.copy_entry(template_id, source_path, dest_path, scope, overwrite)
        return FileOperationResponse(
            success=True,
            path=dest_path,
            scope=scope,
            data=result
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files/move",
    response_model=FileOperationResponse,
    summary="Move file or directory",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def move_entry(
    request: Request,
    template_id: str,
    source_path: str = Query(..., description="Source path"),
    dest_path: str = Query(..., description="Destination path"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    overwrite: bool = Query(default=False, description="Whether to overwrite"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """Move file or directory"""
    try:
        result = service.move_entry(template_id, source_path, dest_path, scope, overwrite)
        return FileOperationResponse(
            success=True,
            path=dest_path,
            scope=scope,
            data=result
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files/batch-delete",
    response_model=BatchOperationResponse,
    summary="Batch delete",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def batch_delete(
    request: Request,
    template_id: str,
    paths: list[str] = Query(..., description="List of paths"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    recursive: bool = Query(default=False, description="Whether to recursively delete directory"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> BatchOperationResponse:
    """Batch delete"""
    try:
        return service.batch_delete(template_id, paths, scope, recursive)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


@router.post(
    "/{template_id}/files/search",
    response_model=FileSearchResponse,
    summary="SearchFile",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def search_files(
    request: Request,
    template_id: str,
    payload: FileSearchRequest,
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="Scope: scripts or skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileSearchResponse:
    """Search files in template"""
    try:
        return service.search_files(template_id, payload, scope)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


__all__ = ["router"]
