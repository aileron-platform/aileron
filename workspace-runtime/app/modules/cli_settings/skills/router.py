"""CLI Skills API routes

Factory function that generates skills endpoint collections for each CLI tool.
Endpoint structure is identical to the original claude_code/file_collections/skills_router.py,
ensuring no frontend API call modifications needed.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.openapi import build_responses
from app.modules.file_system import (
    FileTreeResponse,
    FileContentResponse,
    FileOperationResponse,
    BatchOperationResponse,
    FileManagementException,
)
from .config import SkillTool
from .dependencies import make_skill_service_dependency
from .service import CliSkillService


def create_skills_router(tool: SkillTool) -> APIRouter:
    """Create skills router for specified CLI tool"""

    from .config import get_skill_config

    config = get_skill_config(tool)

    router = APIRouter(
        prefix=f"/{config.api_prefix}/skills",
        tags=[f"{config.api_prefix} - Skills"],
    )

    _get_service = make_skill_service_dependency(tool)

    def get_service(workspace_id: str = Path(...)) -> CliSkillService:
        return _get_service(workspace_id)

    # ----- GET TREE --------------------------------------------------------

    @router.get(
        "/tree",
        response_model=FileTreeResponse,
        summary="Get skills file tree",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_skills_tree(
        path: str = Query(default="/", description="Target path"),
        scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
        includeHidden: bool = Query(default=False, description="Include hidden files"),
        maxDepth: Optional[int] = Query(default=None, ge=1, description="Maximum depth"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            return service.get_tree(path, scope, includeHidden, maxDepth)
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- GET TREE CHILDREN -----------------------------------------------

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
        maxDepth: Optional[int] = Query(default=None, ge=1, description="Maximum depth"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            return service.get_tree(path, scope, includeHidden, maxDepth)
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- READ CONTENT ----------------------------------------------------

    @router.get(
        "/content",
        response_model=FileContentResponse,
        summary="Read skill file",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def read_skill(
        path: str = Query(description="File path"),
        scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            return service.read_file(path, scope)
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- WRITE CONTENT ---------------------------------------------------

    @router.put(
        "/content",
        response_model=FileOperationResponse,
        summary="Write skill file",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def write_skill(
        path: str = Query(description="File path"),
        content: str = Query(description="File content"),
        scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
        expectedVersionId: Optional[str] = Query(default=None, description="Expected version ID"),
        service: CliSkillService = Depends(get_service),
    ):
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
                },
            )
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- CREATE ----------------------------------------------------------

    @router.post(
        "",
        response_model=FileOperationResponse,
        status_code=status.HTTP_201_CREATED,
        summary="Create skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def create_skill(
        path: str = Query(description="Path"),
        type: str = Query(description="Type (file/directory)"),
        scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
        content: Optional[str] = Query(default="", description="File content"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            result = service.create_entry(path, type, scope, content)
            return FileOperationResponse(
                success=True,
                data={"path": path, "scope": scope, "type": type, **result},
            )
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- DELETE ----------------------------------------------------------

    @router.delete(
        "",
        response_model=FileOperationResponse,
        summary="Delete skill",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def delete_skill(
        path: str = Query(description="Path"),
        scope: Optional[str] = Query(default=None, description="Scope (project/user/plugin)"),
        recursive: bool = Query(default=False, description="Delete recursively"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            result = service.delete_entry(path, scope, recursive)
            return FileOperationResponse(
                success=True,
                data={
                    "path": path,
                    "scope": scope,
                    "type": result.get("type", "file"),
                },
            )
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- COPY ------------------------------------------------------------

    @router.post(
        "/copy",
        response_model=FileOperationResponse,
        summary="Copy skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def copy_skill(
        sourcePath: str = Query(description="Source path"),
        destPath: str = Query(description="Destination path"),
        sourceScope: Optional[str] = Query(default=None, description="Source scope"),
        destScope: Optional[str] = Query(default=None, description="Destination scope"),
        overwrite: bool = Query(default=False, description="Overwrite"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            result = service.copy_entry(sourcePath, destPath, sourceScope, destScope, overwrite)
            return FileOperationResponse(
                success=True,
                data={
                    "sourcePath": sourcePath,
                    "destPath": destPath,
                    "sourceScope": sourceScope,
                    "destScope": destScope,
                    "type": result.get("type", "file"),
                },
            )
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- MOVE ------------------------------------------------------------

    @router.post(
        "/move",
        response_model=FileOperationResponse,
        summary="Move skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def move_skill(
        sourcePath: str = Query(description="Source path"),
        destPath: str = Query(description="Destination path"),
        sourceScope: Optional[str] = Query(default=None, description="Source scope"),
        destScope: Optional[str] = Query(default=None, description="Destination scope"),
        overwrite: bool = Query(default=False, description="Overwrite"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            result = service.move_entry(sourcePath, destPath, sourceScope, destScope, overwrite)
            return FileOperationResponse(
                success=True,
                data={
                    "sourcePath": sourcePath,
                    "destPath": destPath,
                    "sourceScope": sourceScope,
                    "destScope": destScope,
                    "type": result.get("type", "file"),
                },
            )
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- BATCH DELETE ----------------------------------------------------

    @router.post(
        "/batch-delete",
        response_model=BatchOperationResponse,
        summary="Batch delete skills",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def batch_delete_skills(
        paths: List[str] = Query(description="Path list"),
        scope: Optional[str] = Query(default=None, description="Scope"),
        recursive: bool = Query(default=False, description="Delete recursively"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            return service.batch_delete(paths, scope, recursive)
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
