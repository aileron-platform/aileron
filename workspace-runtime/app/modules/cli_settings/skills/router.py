"""CLI Skills API routes

Factory function that generates skills endpoint collections for each CLI tool
(Claude Code, Codex, OpenCode) so response shapes and URL paths stay identical
across tools; the /plugins endpoint only registers for tools that set
supports_plugin=True.
"""

from __future__ import annotations

from pathlib import Path as FilePath
from typing import List, NoReturn, Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    Path,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from starlette.concurrency import run_in_threadpool

from app.core.openapi import build_responses
from app.core.resource_envelope import raise_resource_error
from app.modules.file_system.exceptions import FileManagementException
from app.modules.file_system.models import (
    BatchOperationResponse,
    ConflictStrategy,
    FileConflictBatchResult,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileOperationResponse,
)
from .config import SkillTool
from .dependencies import make_skill_service_dependency
from .models import PluginSkillsResponse
from .models import SkillFileContentResponse, SkillFileTreeResponse
from .catalog import CliSkillService


class SkillWriteRequest(BaseModel):
    content: str
    revision: Optional[str] = None


class SkillCreateRequest(BaseModel):
    content: Optional[str] = ""
    revision: Optional[str] = None


class SkillExtractArchiveRequest(BaseModel):
    archivePath: str
    targetPath: str
    scope: Optional[str] = None
    defaultStrategy: ConflictStrategy
    resolutions: List[FileConflictResolution]

    model_config = ConfigDict(extra="forbid")


_FILE_CONFLICT_RESOLUTIONS = TypeAdapter(list[FileConflictResolution])


def _raise_file_management_error(error: FileManagementException) -> NoReturn:
    raise_resource_error(error.code, error.message, error.status_code)


def _raise_internal_error(error: Exception) -> NoReturn:
    raise_resource_error(
        "INTERNAL_ERROR", str(error), status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _upload_size(file: UploadFile) -> int:
    if file.size is not None:
        return file.size
    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


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
        response_model=SkillFileTreeResponse,
        summary="Get skills file tree",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_skills_tree(
        path: str = Query(default="/", description="Target path"),
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        includeHidden: bool = Query(default=False, description="Include hidden files"),
        maxDepth: Optional[int] = Query(
            default=None, ge=1, description="Maximum depth"
        ),
        service: CliSkillService = Depends(get_service),
    ) -> SkillFileTreeResponse:
        try:
            return SkillFileTreeResponse.model_validate(
                service.get_tree(path, scope, includeHidden, maxDepth)
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- GET TREE CHILDREN -----------------------------------------------

    @router.get(
        "/tree/children",
        response_model=SkillFileTreeResponse,
        summary="Lazy load child nodes",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def get_skills_children(
        path: str = Query(description="Parent node path"),
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        includeHidden: bool = Query(default=False, description="Include hidden files"),
        maxDepth: Optional[int] = Query(
            default=None, ge=1, description="Maximum depth"
        ),
        service: CliSkillService = Depends(get_service),
    ) -> SkillFileTreeResponse:
        try:
            return SkillFileTreeResponse.model_validate(
                service.get_tree(path, scope, includeHidden, maxDepth)
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- READ CONTENT ----------------------------------------------------

    @router.get(
        "/content",
        response_model=SkillFileContentResponse,
        summary="Read skill file",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def read_skill(
        path: str = Query(description="File path"),
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        service: CliSkillService = Depends(get_service),
    ) -> SkillFileContentResponse:
        try:
            return SkillFileContentResponse.model_validate(
                service.read_file(path, scope)
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- WRITE CONTENT ---------------------------------------------------

    @router.put(
        "/content",
        response_model=FileOperationResponse,
        summary="Write skill file",
        responses=build_responses(400, 401, 403, 404, 409, 422, 500),
    )
    async def write_skill(
        path: str = Query(description="File path"),
        payload: SkillWriteRequest = Body(...),
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        service: CliSkillService = Depends(get_service),
    ) -> FileOperationResponse:
        try:
            result = service.write_file(path, payload.content, scope, payload.revision)
            service.clear_tree_cache(scope)
            return FileOperationResponse(
                success=True,
                data={
                    "path": path,
                    "scope": scope,
                    "size": len(payload.content.encode("utf-8")),
                    "updatedAt": result["updatedAt"],
                    "revision": result.get("revision"),
                },
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

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
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        payload: SkillCreateRequest | None = Body(default=None),
        service: CliSkillService = Depends(get_service),
    ) -> FileOperationResponse:
        try:
            content = payload.content or "" if payload is not None else ""
            result = service.create_entry(path, type, scope, content)
            service.clear_tree_cache(scope)
            return FileOperationResponse(
                success=True,
                data={"path": path, "scope": scope, "type": type, **result},
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- DELETE ----------------------------------------------------------

    @router.delete(
        "",
        response_model=FileOperationResponse,
        summary="Delete skill",
        responses=build_responses(400, 401, 404, 422, 500),
    )
    async def delete_skill(
        path: str = Query(description="Path"),
        scope: Optional[str] = Query(
            default=None, description="Scope (project/user/plugin)"
        ),
        recursive: bool = Query(default=False, description="Delete recursively"),
        service: CliSkillService = Depends(get_service),
    ) -> FileOperationResponse:
        try:
            result = service.delete_entry(path, scope, recursive)
            service.clear_tree_cache(scope)
            return FileOperationResponse(
                success=True,
                data={
                    "path": path,
                    "scope": scope,
                    "type": result.get("type", "file"),
                },
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

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
        service: CliSkillService = Depends(get_service),
    ) -> FileOperationResponse:
        try:
            result = service.move_entry(sourcePath, destPath, sourceScope, destScope)
            service.clear_tree_cache()
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
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

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
    ) -> BatchOperationResponse:
        try:
            result = service.batch_delete(paths, scope, recursive)
            service.clear_tree_cache(scope)
            return BatchOperationResponse.model_validate(result)
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    @router.post(
        "/conflicts/preflight",
        response_model=FileConflictPreflightResponse,
        summary="Preflight skill file conflicts",
        responses=build_responses(400, 403, 404, 409, 422, 500),
    )
    async def preflight_skill_file_conflicts(
        payload: FileConflictPreflightRequest,
        scope: Optional[str] = Query(default=None, description="Scope"),
        service: CliSkillService = Depends(get_service),
    ) -> FileConflictPreflightResponse:
        if service.is_readonly_scope(scope):
            raise_resource_error(
                "READONLY_SCOPE",
                f"Scope is read-only: {scope}",
                status.HTTP_403_FORBIDDEN,
            )

        try:
            sources = payload.sources or []
            if payload.operation == "upload":
                result = service.preflight_upload_files(
                    target_path=payload.targetPath,
                    filenames=[source.sourcePath for source in sources],
                    scope=scope,
                )
            elif payload.operation == "paste":
                result = service.preflight_copy_entries(
                    source_paths=[source.sourcePath for source in sources],
                    target_path=payload.targetPath,
                    source_scope=scope,
                    dest_scope=scope,
                )
            else:
                if not payload.archivePath:
                    raise FileManagementException(
                        "INVALID_ARCHIVE",
                        "archivePath is required for extract preflight",
                        {},
                        400,
                    )
                result = service.preflight_extract_archive(
                    archive_path=payload.archivePath,
                    target_path=payload.targetPath,
                    scope=scope,
                )
            return FileConflictPreflightResponse(**result)
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- UPLOAD ----------------------------------------------------------

    @router.post(
        "/upload",
        response_model=FileConflictBatchResult,
        summary="Upload skill files",
        responses=build_responses(400, 401, 403, 409, 413, 422, 500),
    )
    async def upload_skill_files(
        target_path: str = Form(..., alias="targetPath"),
        scope: Optional[str] = Form(default=None, description="Scope (project/user)"),
        default_strategy: ConflictStrategy = Form(..., alias="defaultStrategy"),
        resolutions: str = Form(...),
        files: List[UploadFile] = File(..., description="Files to upload"),
        service: CliSkillService = Depends(get_service),
    ) -> FileConflictBatchResult:
        if service.is_readonly_scope(scope):
            raise_resource_error(
                "READONLY_SCOPE",
                f"Scope is read-only: {scope}",
                status.HTTP_403_FORBIDDEN,
            )

        try:
            streams = []
            for file in files:
                filename = FilePath(file.filename or "").name
                if not filename:
                    raise FileManagementException(
                        "INVALID_UPLOAD_FILENAME",
                        "Upload filename is required",
                        {},
                        400,
                    )
                file_size = _upload_size(file)
                streams.append((filename, file.file, file_size))
            result = await run_in_threadpool(
                service.upload_file_streams,
                target_path=target_path,
                files=streams,
                default_strategy=default_strategy,
                resolutions=_FILE_CONFLICT_RESOLUTIONS.validate_json(resolutions),
                scope=scope,
            )
            service.clear_tree_cache(scope)
            return FileConflictBatchResult(**result)
        except ValidationError as e:
            raise_resource_error(
                "INVALID_CONFLICT_RESOLUTIONS",
                str(e),
                status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    @router.post(
        "/extract",
        response_model=FileConflictBatchResult,
        summary="Extract an uploaded skill ZIP archive",
        responses=build_responses(400, 401, 403, 404, 409, 413, 422, 500),
    )
    async def extract_skill_archive(
        payload: SkillExtractArchiveRequest,
        service: CliSkillService = Depends(get_service),
    ) -> FileConflictBatchResult:
        if service.is_readonly_scope(payload.scope):
            raise_resource_error(
                "READONLY_SCOPE",
                f"Scope is read-only: {payload.scope}",
                status.HTTP_403_FORBIDDEN,
            )
        try:
            result = await run_in_threadpool(
                service.extract_archive_path,
                archive_path=payload.archivePath,
                target_path=payload.targetPath,
                default_strategy=payload.defaultStrategy,
                resolutions=payload.resolutions,
                scope=payload.scope,
            )
            service.clear_tree_cache(payload.scope)
            return FileConflictBatchResult(**result)
        except FileManagementException as e:
            raise _raise_file_management_error(e) from e
        except Exception as e:
            raise _raise_internal_error(e) from e

    # ----- PLUGIN SKILLS (only for tools with plugin support) --------------

    if config.supports_plugin:

        @router.get(
            "/plugins",
            response_model=PluginSkillsResponse,
            summary="Get plugin skills",
            responses=build_responses(401, 500),
        )
        async def get_plugin_skills(
            workspace_id: str = Path(...),
            service: CliSkillService = Depends(get_service),
        ) -> PluginSkillsResponse:
            try:
                return PluginSkillsResponse(
                    workspaceId=workspace_id, plugins=service.get_plugin_skills()
                )
            except Exception:
                # Gracefully handle plugin loading errors, return empty list
                return PluginSkillsResponse(workspaceId=workspace_id, plugins=[])

    return router
