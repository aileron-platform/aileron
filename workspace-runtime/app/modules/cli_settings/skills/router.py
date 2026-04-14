"""CLI Skills API 路由

工廠函數，為每個 CLI 工具產生 skills 端點集合。
端點結構與原 claude_code/file_collections/skills_router.py 完全相同，
以確保前端 API 呼叫無需修改。
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
from app.modules.claude_code.file_collections.models import PluginSkillInfo

from .config import SkillTool
from .dependencies import make_skill_service_dependency
from .service import CliSkillService


def create_skills_router(tool: SkillTool) -> APIRouter:
    """為指定的 CLI 工具建立 skills 路由"""

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
        summary="取得 Skills 檔案樹",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_skills_tree(
        path: str = Query(default="/", description="目標路徑"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
        includeHidden: bool = Query(default=False, description="是否包含隱藏檔"),
        maxDepth: Optional[int] = Query(default=None, ge=1, description="最大深度"),
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
        summary="懶載入子節點",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_skills_children(
        path: str = Query(description="父節點路徑"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
        includeHidden: bool = Query(default=False, description="是否包含隱藏檔"),
        maxDepth: Optional[int] = Query(default=None, ge=1, description="最大深度"),
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
        summary="讀取 Skill 檔案",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def read_skill(
        path: str = Query(description="檔案路徑"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
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
        summary="寫入 Skill 檔案",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def write_skill(
        path: str = Query(description="檔案路徑"),
        content: str = Query(description="檔案內容"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
        expectedVersionId: Optional[str] = Query(default=None, description="預期版本ID"),
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
        summary="建立 Skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def create_skill(
        path: str = Query(description="路徑"),
        type: str = Query(description="類型 (file/directory)"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
        content: Optional[str] = Query(default="", description="檔案內容"),
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
        summary="刪除 Skill",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def delete_skill(
        path: str = Query(description="路徑"),
        scope: Optional[str] = Query(default=None, description="範圍 (project/user/plugin)"),
        recursive: bool = Query(default=False, description="是否遞迴刪除"),
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
        summary="複製 Skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def copy_skill(
        sourcePath: str = Query(description="源路徑"),
        destPath: str = Query(description="目標路徑"),
        sourceScope: Optional[str] = Query(default=None, description="源範圍"),
        destScope: Optional[str] = Query(default=None, description="目標範圍"),
        overwrite: bool = Query(default=False, description="是否覆蓋"),
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
        summary="移動 Skill",
        responses=build_responses(400, 401, 404, 409, 422, 500),
    )
    async def move_skill(
        sourcePath: str = Query(description="源路徑"),
        destPath: str = Query(description="目標路徑"),
        sourceScope: Optional[str] = Query(default=None, description="源範圍"),
        destScope: Optional[str] = Query(default=None, description="目標範圍"),
        overwrite: bool = Query(default=False, description="是否覆蓋"),
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
        summary="批次刪除 Skills",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def batch_delete_skills(
        paths: List[str] = Query(description="路徑列表"),
        scope: Optional[str] = Query(default=None, description="範圍"),
        recursive: bool = Query(default=False, description="是否遞迴刪除"),
        service: CliSkillService = Depends(get_service),
    ):
        try:
            return service.batch_delete(paths, scope, recursive)
        except FileManagementException as e:
            raise HTTPException(status_code=e.status_code, detail=e.to_dict())
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # ----- PLUGIN SKILLS (Claude only) -------------------------------------

    if config.supports_plugin:

        @router.get(
            "/plugins",
            response_model=List[PluginSkillInfo],
            summary="取得插件 Skills",
            responses=build_responses(401, 500),
        )
        async def get_plugin_skills(
            service: CliSkillService = Depends(get_service),
        ):
            try:
                return service.get_plugin_skills()
            except Exception:
                return []

    return router
