"""模板文件管理路由（Commands、Agents、Output Style、AGENTS.md、通用文件管理）"""

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
    """取得模板服務實例"""
    return TemplateService(db)


def get_template_file_service(db: Session = Depends(get_db)) -> TemplateFileService:
    """取得模板檔案服務實例"""
    return TemplateFileService(db)


# ============ Commands 檔案管理 ============


@router.get(
    "/{template_id}/commands",
    response_model=TemplateCommandListResponse,
    summary="取得模板 Commands 檔案列表",
    responses=build_responses(401, 404, 500),
)
async def get_template_commands_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandListResponse:
    """取得指定模板的 commands 目錄下所有檔案列表"""
    result = service.get_commands_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/commands/{file_name}",
    response_model=TemplateCommandResponse,
    summary="取得 Command 檔案內容",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_command_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandResponse:
    """取得指定模板中特定 command 檔案的內容"""
    result = service.get_command_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/commands",
    response_model=TemplateCommandResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 Command 檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_command_file(
    request: Request,
    template_id: str,
    payload: TemplateCommandCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateCommandResponse:
    """在指定模板的 commands 目錄中新增新檔案"""
    result = service.create_command_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/commands/{file_name}",
    response_model=TemplateCommandResponse,
    summary="更新 Command 檔案",
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
    """更新指定模板中的 command 檔案內容"""
    result = service.update_command_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/commands/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除 Command 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_command_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """刪除指定模板中的 command 檔案"""
    result = service.delete_command_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ AGENTS.md 檔案管理 ============


@router.get(
    "/{template_id}/agents-md",
    summary="取得 AGENTS.md 內容",
    responses=build_responses(401, 404, 500),
)
async def get_template_agents_md(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> dict:
    """取得模板的 AGENTS.md 內容"""
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
    summary="更新 AGENTS.md 內容",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def update_template_agents_md(
    request: Request,
    template_id: str,
    payload: dict,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> dict:
    """更新模板的 AGENTS.md 內容"""
    try:
        translate = request.state.translate
        content = payload.get("content", "")
        if not content.strip():
            return {
                "success": False,
                "error": "Content cannot be empty",
                "message": translate("templates.agents_md_content_empty")
            }

        # 呼叫 service 方法實際保存檔案
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


# ============ Agents 檔案管理 ============


@router.get(
    "/{template_id}/agents",
    response_model=TemplateAgentListResponse,
    summary="取得模板 Agents 檔案列表",
    responses=build_responses(401, 404, 500),
)
async def get_template_agents_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentListResponse:
    """取得指定模板的 agents 目錄下所有檔案列表"""
    result = service.get_agents_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/agents/{file_name}",
    response_model=TemplateAgentResponse,
    summary="取得 Agent 檔案內容",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_agent_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentResponse:
    """取得指定模板中特定 agent 檔案的內容"""
    result = service.get_agent_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/agents",
    response_model=TemplateAgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 Agent 檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_agent_file(
    request: Request,
    template_id: str,
    payload: TemplateAgentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateAgentResponse:
    """在指定模板的 agents 目錄中新增新檔案"""
    result = service.create_agent_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/agents/{file_name}",
    response_model=TemplateAgentResponse,
    summary="更新 Agent 檔案",
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
    """更新指定模板中的 agent 檔案內容"""
    result = service.update_agent_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/agents/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除 Agent 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_agent_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """刪除指定模板中的 agent 檔案"""
    result = service.delete_agent_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ Output Style 檔案管理 ============


@router.get(
    "/{template_id}/output-style",
    response_model=TemplateOutputStyleListResponse,
    summary="取得模板 Output Style 檔案列表",
    responses=build_responses(401, 404, 500),
)
async def get_template_output_style_files(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleListResponse:
    """取得指定模板的 output-style 目錄下所有檔案列表"""
    result = service.get_output_style_files(template_id)
    translate = request.state.translate
    if not result.success:
        _raise_template_service_error(result, translate)
    return result


@router.get(
    "/{template_id}/output-style/{file_name}",
    response_model=TemplateOutputStyleResponse,
    summary="取得 Output Style 檔案內容",
    responses=build_responses(400, 401, 404, 500),
)
async def get_template_output_style_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleResponse:
    """取得指定模板中特定 output-style 檔案的內容"""
    result = service.get_output_style_file_content(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.post(
    "/{template_id}/output-style",
    response_model=TemplateOutputStyleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="新增 Output Style 檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_template_output_style_file(
    request: Request,
    template_id: str,
    payload: TemplateOutputStyleCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> TemplateOutputStyleResponse:
    """在指定模板的 output-style 目錄中新增新檔案"""
    result = service.create_output_style_file(template_id, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.put(
    "/{template_id}/output-style/{file_name}",
    response_model=TemplateOutputStyleResponse,
    summary="更新 Output Style 檔案",
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
    """更新指定模板中的 output-style 檔案內容"""
    result = service.update_output_style_file(template_id, file_name, payload)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)
    return result


@router.delete(
    "/{template_id}/output-style/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除 Output Style 檔案",
    responses=build_responses(400, 401, 404, 500),
)
async def delete_template_output_style_file(
    request: Request,
    template_id: str,
    file_name: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """刪除指定模板中的 output-style 檔案"""
    result = service.delete_output_style_file(template_id, file_name)
    if not result.success:
        _raise_template_service_error(result, request.state.translate)


# ============ 通用檔案管理 API ============


@router.get(
    "/{template_id}/files/tree",
    response_model=FileTreeResponse,
    summary="取得檔案樹",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_file_tree(
    request: Request,
    template_id: str,
    path: str = Query(default="/", description="目標路徑"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    include_hidden: bool = Query(default=False, description="是否包含隱藏檔"),
    max_depth: Optional[int] = Query(default=None, ge=0, description="最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileTreeResponse:
    """取得檔案樹"""
    try:
        # 如果未提供 max_depth，使用設定檔中的預設值
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
    summary="讀取檔案內容",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def read_file(
    request: Request,
    template_id: str,
    path: str = Query(..., description="檔案路徑"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileContentResponse:
    """讀取檔案內容"""
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
    summary="建立檔案或目錄",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_entry(
    request: Request,
    template_id: str,
    path: str = Query(..., description="路徑"),
    entry_type: str = Query(..., pattern="^(file|directory)$", description="類型: file 或 directory"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    content: Optional[str] = Query(default="", description="檔案內容（僅檔案）"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """建立檔案或目錄"""
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
    summary="寫入檔案內容",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def write_file(
    request: Request,
    template_id: str,
    path: str = Query(..., description="檔案路徑"),
    content: str = Query(..., description="檔案內容"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    expected_version_id: Optional[str] = Query(default=None, description="預期版本ID（衝突檢測）"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """寫入檔案內容"""
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
    summary="上傳檔案",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def upload_files(
    request: Request,
    template_id: str,
    target_path: str = Form(default="", description="目標目錄路徑"),
    files: List[UploadFile] = File(..., description="要上傳的檔案"),
    overwrite: bool = Form(default=False, description="是否覆蓋已存在的檔案"),
    scope: str = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileUploadResponse:
    """上傳單個或多個檔案到模板"""
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
    summary="刪除檔案或目錄",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def delete_entry(
    request: Request,
    template_id: str,
    path: str = Query(..., description="路徑"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    recursive: bool = Query(default=False, description="是否遞迴刪除目錄"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """刪除檔案或目錄"""
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
    summary="複製檔案或目錄",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def copy_entry(
    request: Request,
    template_id: str,
    source_path: str = Query(..., description="來源路徑"),
    dest_path: str = Query(..., description="目標路徑"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    overwrite: bool = Query(default=False, description="是否覆蓋"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """複製檔案或目錄"""
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
    summary="移動檔案或目錄",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def move_entry(
    request: Request,
    template_id: str,
    source_path: str = Query(..., description="來源路徑"),
    dest_path: str = Query(..., description="目標路徑"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    overwrite: bool = Query(default=False, description="是否覆蓋"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileOperationResponse:
    """移動檔案或目錄"""
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
    summary="批次刪除",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def batch_delete(
    request: Request,
    template_id: str,
    paths: list[str] = Query(..., description="路徑列表"),
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    recursive: bool = Query(default=False, description="是否遞迴刪除目錄"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> BatchOperationResponse:
    """批次刪除"""
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
    summary="搜尋檔案",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def search_files(
    request: Request,
    template_id: str,
    payload: FileSearchRequest,
    scope: Optional[str] = Query(default="scripts", pattern="^(scripts|skills)$", description="範圍: scripts 或 skills"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateFileService = Depends(get_template_file_service)
) -> FileSearchResponse:
    """在模板中搜尋檔案"""
    try:
        return service.search_files(template_id, payload, scope)
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=_localize_file_management_exception(request.state.translate, e),
        )


__all__ = ["router"]
