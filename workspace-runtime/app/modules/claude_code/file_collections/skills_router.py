"""Skills API Router - Refactored Version

Using unified file management API structure
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
from .models import FileCollectionType, PluginSkillInfo
from .service import FileCollectionService
from .dependencies import get_workspace_id


router = APIRouter(prefix="/skills", tags=["Claude Code - Skills"])


def get_skills_service(workspace_id: str = Depends(get_workspace_id)) -> FileCollectionService:
    """Get Skills service instance"""
    return FileCollectionService(FileCollectionType.SKILLS, workspace_id)


@router.get(
    "/tree",
    response_model=FileTreeResponse,
    summary="Get Skills file tree",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_skills_tree(
    path: str = Query(default="/", description="Target path"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    includeHidden: bool = Query(default=False, description="Include hidden files"),
    maxDepth: Optional[int] = Query(default=None, ge=1, description="Max depth (defaults to FILE_TREE_MAX_DEPTH in settings)"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Get Skills file tree"""
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
    summary="Lazy load child nodes",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def get_skills_children(
    path: str = Query(description="Parent node path"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    includeHidden: bool = Query(default=False, description="Include hidden files"),
    maxDepth: Optional[int] = Query(default=None, ge=1, description="Max depth (defaults to FILE_TREE_MAX_DEPTH in settings)"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Lazy load child nodes"""
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
    summary="Read Skill file",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def read_skill(
    path: str = Query(description="File path"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Read Skill file content"""
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
    summary="Write Skill file",
    responses=build_responses(400, 401, 403, 404, 409, 422, 500),
)
async def write_skill(
    path: str = Query(description="File path"),
    content: str = Query(description="File content"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    expectedVersionId: Optional[str] = Query(default=None, description="Expected version ID"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Write Skill file content"""
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
    summary="Create Skill",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def create_skill(
    path: str = Query(description="Path"),
    type: str = Query(description="Type (file/directory)"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    content: Optional[str] = Query(default="", description="File content"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Create Skill file or directory"""
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
    summary="Delete Skill",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def delete_skill(
    path: str = Query(description="Path"),
    scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
    recursive: bool = Query(default=False, description="Recursive delete"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Delete Skill file or directory"""
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
    summary="Copy Skill",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def copy_skill(
    sourcePath: str = Query(description="Source path"),
    destPath: str = Query(description="Target path"),
    sourceScope: Optional[str] = Query(default=None, description="Source scope"),
    destScope: Optional[str] = Query(default=None, description="Destination scope"),
    overwrite: bool = Query(default=False, description="Overwrite"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Copy Skill file or directory"""
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
    summary="Move Skill",
    responses=build_responses(400, 401, 404, 409, 422, 500),
)
async def move_skill(
    sourcePath: str = Query(description="Source path"),
    destPath: str = Query(description="Target path"),
    sourceScope: Optional[str] = Query(default=None, description="Source scope"),
    destScope: Optional[str] = Query(default=None, description="Destination scope"),
    overwrite: bool = Query(default=False, description="Overwrite"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Move or rename Skill"""
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
    summary="Batch delete Skills",
    responses=build_responses(400, 401, 404, 422, 500),
)
async def batch_delete_skills(
    paths: List[str] = Query(description="Path list"),
    scope: Optional[str] = Query(default=None, description="Scope"),
    recursive: bool = Query(default=False, description="Recursive delete"),
    service: FileCollectionService = Depends(get_skills_service),
):
    """Batch delete Skills"""
    try:
        result = service.batch_delete(paths, scope, recursive)
        return result
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/plugins",
    response_model=List[PluginSkillInfo],
    summary="Get plugin Skills",
    responses=build_responses(401, 500),
)
async def get_plugin_skills(
    service: FileCollectionService = Depends(get_skills_service),
):
    """Get all plugin Skills"""
    try:
        return service.get_plugin_skills()
    except Exception:
        # Gracefully handle plugin loading errors, return empty list
        return []


__all__ = ["router"]
