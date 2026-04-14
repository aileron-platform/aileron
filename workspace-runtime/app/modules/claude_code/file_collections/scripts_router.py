"""Scripts API Router - 重構版本

使用統一的檔案管理 API 結構
"""

from __future__ import annotations

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.openapi import build_responses
from app.modules.file_system import (
    FileTreeRequest,
    FileContentRequest,
    FileWriteRequest,
    FileCreateRequest,
    FileDeleteRequest,
    FileCopyRequest,
    FileMoveRequest,
    BatchDeleteRequest,
    FileTreeResponse,
    FileContentResponse,
    FileOperationResponse,
    BatchOperationResponse,
    FileManagementException,
)
from ..common import DocumentScope
from .models import FileCollectionType
from .service import FileCollectionService
from .dependencies import get_workspace_id


router = APIRouter(prefix="/scripts", tags=["Claude Code - 腳本"])


def get_scripts_service(workspace_id: str = Depends(get_workspace_id)) -> FileCollectionService:
    """取得 Scripts 服務實例"""
    return FileCollectionService(FileCollectionType.SCRIPTS, workspace_id)


@router.get(
    "/tree",
    response_model=FileTreeResponse,
    summary="取得 Scripts 檔案樹",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_scripts_tree(
    path: str = Query(default="/", description="目標路徑"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    includeHidden: bool = Query(default=False, description="是否包含隱藏檔"),
    maxDepth: Optional[int] = Query(default=None, ge=1, description="最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """取得 Scripts 檔案樹"""
    try:
        result = service.get_tree(path, scope, includeHidden, maxDepth)
        return result
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/tree/children",
    response_model=FileTreeResponse,
    summary="懶載入子節點",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_scripts_children(
    path: str = Query(description="父節點路徑"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    includeHidden: bool = Query(default=False, description="是否包含隱藏檔"),
    maxDepth: Optional[int] = Query(default=None, ge=1, description="最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """懶載入子節點"""
    try:
        result = service.get_tree(path, scope, includeHidden, maxDepth)
        return result
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/content",
    response_model=FileContentResponse,
    summary="讀取 Script 檔案",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def read_script(
    path: str = Query(description="檔案路徑"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """讀取 Script 檔案內容"""
    try:
        result = service.read_file(path, scope)
        return result
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/content",
    response_model=FileOperationResponse,
    summary="寫入 Script 檔案",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def write_script(
    path: str = Query(description="檔案路徑"),
    content: str = Query(description="檔案內容"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    expectedVersionId: Optional[str] = Query(default=None, description="預期版本ID"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """寫入 Script 檔案內容"""
    try:
        result = service.write_file(path, content, scope, expectedVersionId)
        return FileOperationResponse(
            success=True,
            data={
                "path": path,
                "scope": scope,
                "size": len(content.encode("utf-8")),
                "updatedAt": result["updatedAt"],
                "versionId": result.get("versionId"),
            }
        )
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "",
    response_model=FileOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立 Script",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_script(
    path: str = Query(description="路徑"),
    type: str = Query(description="類型 (file/directory)"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    content: Optional[str] = Query(default="", description="檔案內容"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """建立 Script 檔案或目錄"""
    try:
        result = service.create_entry(path, type, scope, content)
        return FileOperationResponse(
            success=True,
            data={
                "path": path,
                "scope": scope,
                "type": type,
                **result
            }
        )
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "",
    response_model=FileOperationResponse,
    summary="刪除 Script",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def delete_script(
    path: str = Query(description="路徑"),
    scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
    recursive: bool = Query(default=False, description="是否遞迴刪除"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """刪除 Script 檔案或目錄"""
    try:
        result = service.delete_entry(path, scope, recursive)
        return FileOperationResponse(
            success=True,
            data={
                "path": path,
                "scope": scope,
                "type": result.get("type", "file")
            }
        )
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/copy",
    response_model=FileOperationResponse,
    summary="複製 Script",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def copy_script(
    sourcePath: str = Query(description="源路徑"),
    destPath: str = Query(description="目標路徑"),
    sourceScope: Optional[str] = Query(default=None, description="源範圍"),
    destScope: Optional[str] = Query(default=None, description="目標範圍"),
    overwrite: bool = Query(default=False, description="是否覆蓋"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """複製 Script 檔案或目錄"""
    try:
        result = service.copy_entry(sourcePath, destPath, sourceScope, destScope, overwrite)
        return FileOperationResponse(
            success=True,
            data={
                "sourcePath": sourcePath,
                "destPath": destPath,
                "sourceScope": sourceScope,
                "destScope": destScope,
                "type": result.get("type", "file")
            }
        )
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/move",
    response_model=FileOperationResponse,
    summary="移動 Script",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def move_script(
    sourcePath: str = Query(description="源路徑"),
    destPath: str = Query(description="目標路徑"),
    sourceScope: Optional[str] = Query(default=None, description="源範圍"),
    destScope: Optional[str] = Query(default=None, description="目標範圍"),
    overwrite: bool = Query(default=False, description="是否覆蓋"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """移動或重命名 Script"""
    try:
        result = service.move_entry(sourcePath, destPath, sourceScope, destScope, overwrite)
        return FileOperationResponse(
            success=True,
            data={
                "sourcePath": sourcePath,
                "destPath": destPath,
                "sourceScope": sourceScope,
                "destScope": destScope,
                "type": result.get("type", "file")
            }
        )
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/batch-delete",
    response_model=BatchOperationResponse,
    summary="批次刪除 Scripts",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def batch_delete_scripts(
    paths: List[str] = Query(description="路徑列表"),
    scope: Optional[str] = Query(default=None, description="範圍"),
    recursive: bool = Query(default=False, description="是否遞迴刪除"),
    service: FileCollectionService = Depends(get_scripts_service),
):
    """批次刪除 Scripts"""
    try:
        result = service.batch_delete(paths, scope, recursive)
        return result
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
