"""Refactored file API routes"""

from datetime import datetime, timedelta, timezone
import mimetypes
import posixpath
import re
import tempfile
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from aileron_file_core import BackgroundFileOperation, BackgroundFileOperationStore
from pydantic import TypeAdapter, ValidationError

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Path as ApiPath,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.version_control.dependencies import get_working_tree_operations
from app.modules.resource_telemetry.triggers import notify_capacity_changed
from app.modules.version_control.working_tree_operations import (
    WorkingTreeContextError,
    resolve_working_tree_context,
)
from .exceptions import (
    ContentConflictException,
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileManagementException,
    FileNotFoundException,
    InvalidPathException,
    ReadonlyScopeException,
)
from .dependencies import get_file_service_sync, get_workspace_local_history
from .models import (
    ArchiveDownloadAcceptedResponse,
    ArchiveDownloadRequest,
    ArchiveDownloadResult,
    ArchiveDownloadStatusResponse,
    BatchDeleteRequest,
    BatchOperationResponse,
    BatchWriteRequest,
    FileContentResponse,
    ConflictStrategy,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileExtractExecutionRequest,
    FileCreateRequest,
    FileMoveRequest,
    FileOperationResponse,
    FileSearchResponse,
    FileTreeResponse,
    FileWriteRequest,
    LocalHistoryListResponse,
    LocalHistoryEntryResponse,
    LocalHistoryRestoreRequest,
    LocalHistoryRestoreResponse,
)
from .operations import FileService

router = APIRouter(prefix="/files", tags=["File Management"])

ARCHIVE_DOWNLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "aileron-archive-downloads"
WORKSPACE_OPERATION_SCOPE = "workspace"
_FILE_CONFLICT_RESOLUTIONS = TypeAdapter(list[FileConflictResolution])


def _upload_size(file: UploadFile) -> int:
    if file.size is not None:
        return file.size
    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


_archive_operation_store: BackgroundFileOperationStore[ArchiveDownloadResult] = (
    BackgroundFileOperationStore(operation_prefix="archive")
)


def _archive_operation_response(
    operation: BackgroundFileOperation[ArchiveDownloadResult],
) -> ArchiveDownloadStatusResponse:
    return ArchiveDownloadStatusResponse(
        operationId=operation.operation_id,
        status=operation.status,
        progress=operation.progress,
        message=operation.message,
        startedAt=operation.started_at,
        completedAt=operation.completed_at,
        error=operation.error,
        result=operation.result,
    )


def _resolve_file_service_root(context_id: str | None) -> Path:
    settings = get_settings()
    workspace_root = Path(settings.AILERON_WORKSPACE_PATH).resolve()

    if not context_id or context_id == "primary":
        return workspace_root

    try:
        return resolve_working_tree_context(workspace_root, context_id)
    except WorkingTreeContextError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


def get_new_file_service(
    context_id: str | None = Query(
        None, alias="contextId", description="Git context ID"
    ),
) -> FileService:
    if context_id is None:
        service = get_file_service_sync()
        return service
    settings = get_settings()
    return FileService(
        root_path=_resolve_file_service_root(context_id),
        working_tree_operations=get_working_tree_operations(),
        local_history=get_workspace_local_history(),
        workspace_id=settings.AILERON_WORKSPACE_ID,
        context_id=context_id,
    )


def _file_management_status(exc: FileManagementException) -> int:
    if exc.status_code == FileManagementException.status_code:
        return status.HTTP_400_BAD_REQUEST
    return exc.status_code


def _inline_content_disposition(filename: str) -> str:
    encoded_filename = quote(filename)
    if encoded_filename != filename:
        return f"inline; filename*=utf-8''{encoded_filename}"
    return f'inline; filename="{filename}"'


def _sanitize_archive_name(archive_name: Optional[str], paths: List[str]) -> str:
    if archive_name:
        candidate = Path(archive_name).name.strip()
    else:
        candidate = ""

    if not candidate:
        if len(paths) == 1:
            base = posixpath.basename(paths[0].rstrip("/")) or "workspace"
            candidate = f"{base}.zip"
        else:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            candidate = f"workspace-selection-{timestamp}.zip"

    candidate = re.sub(r"[^A-Za-z0-9._ -]+", "_", candidate).strip(" .")
    if not candidate:
        candidate = "archive.zip"
    if not candidate.lower().endswith(".zip"):
        candidate = f"{candidate}.zip"
    return candidate


def _normalize_archive_request_path(path: str) -> str:
    normalized = path.strip()
    if not normalized:
        raise InvalidPathException(path, "Archive path is required")
    return normalized if normalized.startswith("/") else f"/{normalized}"


def _ensure_path_within_root(root_path: Path, fs_path: Path, request_path: str) -> Path:
    resolved_root = root_path.resolve()
    resolved_path = fs_path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise InvalidPathException(request_path, "Path escapes workspace root") from exc
    return resolved_path


def _create_archive_download_operation(
    message: str = "Preparing ZIP download...",
) -> BackgroundFileOperation[ArchiveDownloadResult]:
    _cleanup_expired_archive_operations()
    return _archive_operation_store.create(
        scope_key=WORKSPACE_OPERATION_SCOPE,
        message=message,
    )


def _update_archive_download_operation(
    operation_id: str,
    *,
    status_value: Optional[str] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    result: Optional[ArchiveDownloadResult] = None,
    temp_path: Optional[Path] = None,
    expires_at: Optional[datetime] = None,
) -> None:
    _archive_operation_store.update(
        scope_key=WORKSPACE_OPERATION_SCOPE,
        operation_id=operation_id,
        status=status_value,
        progress=progress,
        message=message,
        error=error,
        result=result,
        artifact_path=temp_path,
        expires_at=expires_at,
    )


def _cleanup_expired_archive_operations() -> None:
    ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    _archive_operation_store.cleanup_expired()


def _run_archive_download_operation(
    operation_id: str,
    service: FileService,
    paths: List[str],
    archive_name: str,
) -> None:
    try:
        _update_archive_download_operation(
            operation_id,
            status_value="running",
            progress=0.02,
            message="Scanning selected files...",
        )

        archive_result = service.build_archive_bytes(paths=paths)
        if not archive_result.entries:
            raise FileManagementException(
                "ARCHIVE_DOWNLOAD_EMPTY",
                "No files are available to package",
                {"paths": paths},
                400,
            )

        _update_archive_download_operation(
            operation_id,
            status_value="running",
            progress=0.1,
            message=f"Packaging {len(archive_result.entries)}/{len(archive_result.entries)} files...",
        )

        ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = ARCHIVE_DOWNLOAD_TEMP_DIR / f"{operation_id}.zip"
        temp_path.write_bytes(archive_result.content)

        settings = get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=settings.ARCHIVE_DOWNLOAD_TTL_SECONDS
        )
        result = ArchiveDownloadResult(
            archiveName=archive_name,
            size=temp_path.stat().st_size,
            downloadUrl=f"/api/v1/files/archive/{operation_id}/download",
            expiresAt=expires_at,
        )
        _update_archive_download_operation(
            operation_id,
            status_value="completed",
            progress=1.0,
            message=f"Archive ready, {len(archive_result.entries)} files packaged",
            result=result,
            temp_path=temp_path,
            expires_at=expires_at,
        )
    except FileManagementException as exc:
        _update_archive_download_operation(
            operation_id,
            status_value="failed",
            message=exc.message,
            error=exc.message,
        )
    except Exception as exc:  # pragma: no cover - guarded by integration tests
        _update_archive_download_operation(
            operation_id,
            status_value="failed",
            message=f"Archive packaging failed: {exc}",
            error=str(exc),
        )


@router.get(
    "/history",
    response_model=LocalHistoryListResponse,
    summary="List local history entries",
    responses=build_responses(422, 500),
)
async def list_file_history(
    path: Optional[str] = Query(None, description="File path"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of records"),
    service: FileService = Depends(get_new_file_service),
) -> LocalHistoryListResponse:
    """List local history entries."""
    if service.local_history is None:
        return LocalHistoryListResponse(items=[])
    return LocalHistoryListResponse(
        items=[
            LocalHistoryEntryResponse(**item)
            for item in service.local_history.list_entries(path=path, limit=limit)
        ]
    )


@router.post(
    "/history/{entry_id}/restore",
    response_model=LocalHistoryRestoreResponse,
    summary="Restore local history entry",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def restore_file_history(
    entry_id: str,
    payload: LocalHistoryRestoreRequest,
    service: FileService = Depends(get_new_file_service),
) -> LocalHistoryRestoreResponse:
    """Restore a file from a local history entry."""
    try:
        result = service.restore_history_entry(entry_id, payload.revision)
        return LocalHistoryRestoreResponse(**result)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "LOCAL_HISTORY_ENTRY_NOT_FOUND",
                "message": f"Local history entry not found: {entry_id}",
                "details": {"entryId": entry_id},
            },
        ) from exc
    except ContentConflictException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    except FileNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.to_dict())
    except FileManagementException as exc:
        raise HTTPException(
            status_code=_file_management_status(exc), detail=exc.to_dict()
        )
@router.get(
    "/tree",
    response_model=FileTreeResponse,
    summary="Get file tree",
    responses=build_responses(400, 404, 422, 500),
)
async def get_file_tree(
    path: str = Query("/", description="Target path"),
    scope: Optional[str] = Query(
        None, description="Scope identifier (not used for Files)"
    ),
    include_hidden: bool = Query(
        False, alias="includeHidden", description="Whether to include hidden files"
    ),
    max_depth: Optional[int] = Query(
        None,
        alias="maxDepth",
        ge=1,
        description="Maximum depth (defaults to FILE_TREE_MAX_DEPTH in config)",
    ),
    service: FileService = Depends(get_new_file_service),
) -> FileTreeResponse:
    """Get file tree structure

    If max_depth is not provided, uses FILE_TREE_MAX_DEPTH from environment configuration
    """
    try:
        result = service.get_tree(
            path=path, scope=scope, include_hidden=include_hidden, max_depth=max_depth
        )
        return FileTreeResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=_file_management_status(e), detail=e.to_dict())


@router.get(
    "/tree/children",
    response_model=FileTreeResponse,
    summary="Lazy load child nodes",
    responses=build_responses(400, 404, 422, 500),
)
async def get_directory_children(
    path: str = Query(..., description="Target directory path"),
    scope: Optional[str] = Query(
        None, description="Scope identifier (not used for Files)"
    ),
    include_hidden: bool = Query(
        False, alias="includeHidden", description="Whether to include hidden files"
    ),
    max_depth: Optional[int] = Query(
        None,
        alias="maxDepth",
        ge=1,
        description="Maximum depth (defaults to FILE_TREE_MAX_DEPTH in config)",
    ),
    service: FileService = Depends(get_new_file_service),
) -> FileTreeResponse:
    """Lazy load: dynamically get child nodes of specified directory

    If max_depth is not provided, uses FILE_TREE_MAX_DEPTH from environment configuration
    """
    try:
        result = service.get_tree(
            path=path, scope=scope, include_hidden=include_hidden, max_depth=max_depth
        )
        return FileTreeResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=_file_management_status(e), detail=e.to_dict())


@router.get(
    "/search",
    response_model=FileSearchResponse,
    summary="Search files",
    responses=build_responses(400, 404, 422, 500),
)
async def search_files(
    query: str = Query(..., min_length=1, description="Search query"),
    path: str = Query("/", description="Search root path"),
    scope: Optional[str] = Query(
        None, description="Scope identifier (not used for Files)"
    ),
    include_content: bool = Query(
        True, alias="includeContent", description="Whether to search file content"
    ),
    case_sensitive: bool = Query(
        False, alias="caseSensitive", description="Whether search is case-sensitive"
    ),
    max_results: Optional[int] = Query(
        None, alias="maxResults", ge=1, description="Maximum result count"
    ),
    service: FileService = Depends(get_new_file_service),
) -> FileSearchResponse:
    """Search files by name and optionally by content."""
    try:
        result = service.search_entries(
            query=query,
            path=path,
            scope=scope,
            include_content=include_content,
            case_sensitive=case_sensitive,
            max_results=max_results,
        )
        return FileSearchResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=_file_management_status(e), detail=e.to_dict())


@router.get(
    "/content",
    response_model=FileContentResponse,
    summary="Read file content",
    responses={
        200: {
            "description": "Successfully read file. When `raw=true`, returns original file stream; otherwise returns JSON content.",
        },
        **build_responses(400, 404, 422, 500),
    },
)
async def read_file(
    path: str = Query(..., description="File path"),
    scope: Optional[str] = Query(
        None, description="Scope identifier (not used for Files)"
    ),
    raw: bool = Query(False, description="Whether to return raw binary content"),
    service: FileService = Depends(get_new_file_service),
) -> FileContentResponse | Response:
    """Read file content

    - When raw=false, returns JSON format text content (only applicable to text files)
    - When raw=true, returns raw binary content (applicable to binary files like images)
    """
    try:
        # If requesting raw binary content
        if raw:
            binary_content = service.read_file_binary(path=path, scope=scope)

            # Guess MIME type based on file extension
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type is None:
                mime_type = "application/octet-stream"

            return Response(
                content=binary_content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": _inline_content_disposition(
                        Path(path).name
                    )
                },
            )

        # Otherwise return JSON format text content
        result = service.read_file(path=path, scope=scope)
        return FileContentResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())


@router.get(
    "/download",
    summary="Download file",
    responses=build_responses(400, 404, 422, 500),
)
async def download_file(
    path: str = Query(..., description="File path"),
    service: FileService = Depends(get_new_file_service),
) -> FileResponse:
    """Download a single file as an attachment."""
    try:
        fs_path = service.resolve_scope_path(None, path).resolve()
        root_path = service.resolve_scope_path(None, "/").resolve()
        _ensure_path_within_root(root_path, fs_path, path)

        if not fs_path.exists():
            raise FileNotFoundException(path)
        if not fs_path.is_file():
            raise InvalidPathException(path, "Not a file")

        return FileResponse(
            path=fs_path,
            filename=fs_path.name,
            media_type="application/octet-stream",
        )
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=_file_management_status(e), detail=e.to_dict())


@router.put(
    "/content",
    response_model=FileOperationResponse,
    summary="Write file content",
    responses=build_responses(400, 403, 409, 422, 500),
)
async def write_file(
    request: FileWriteRequest, service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Write file content"""
    try:
        result = service.write_file(
            path=request.path,
            content=request.content,
            scope=request.scope,
            revision=request.revision,
        )
        return FileOperationResponse(success=True, data=result)
    except ReadonlyScopeException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=e.to_dict())
    except ContentConflictException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=_file_management_status(e), detail=e.to_dict())


@router.post(
    "/content/batch",
    response_model=BatchOperationResponse,
    summary="Batch write files",
    responses=build_responses(400, 403, 422, 500),
)
async def batch_write_files(
    request: BatchWriteRequest, service: FileService = Depends(get_new_file_service)
) -> BatchOperationResponse:
    """Batch write multiple files"""
    result = service.batch_write(files=request.files, scope=request.scope)
    return BatchOperationResponse(**result)


@router.post(
    "",
    response_model=FileOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create file or directory",
    responses=build_responses(400, 409, 422, 500),
)
async def create_entry(
    request: FileCreateRequest, service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Create file or directory"""
    try:
        result = service.create_entry(
            path=request.path,
            entry_type=request.type,
            scope=request.scope,
            content=request.content or "",
            encoding=request.encoding or "utf-8",
        )
        return FileOperationResponse(success=True, data=result)
    except FileAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())


@router.delete(
    "",
    response_model=FileOperationResponse,
    summary="Delete file or directory",
    responses=build_responses(400, 404, 422, 500),
)
async def delete_entry(
    path: str = Query(..., description="Path"),
    scope: Optional[str] = Query(
        None, description="Scope identifier (not used for Files)"
    ),
    recursive: bool = Query(
        False, description="Whether to recursively delete directory"
    ),
    service: FileService = Depends(get_new_file_service),
) -> FileOperationResponse:
    """Delete file or directory"""
    try:
        result = service.delete_entry(path=path, scope=scope, recursive=recursive)
        notify_capacity_changed()
        return FileOperationResponse(success=True, data=result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except DirectoryNotEmptyException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())


@router.post(
    "/batch-delete",
    response_model=BatchOperationResponse,
    summary="Batch delete",
    responses=build_responses(400, 422, 500),
)
async def batch_delete_entries(
    request: BatchDeleteRequest, service: FileService = Depends(get_new_file_service)
) -> BatchOperationResponse:
    """Batch delete files or directories"""
    result = service.batch_delete(
        paths=request.paths, scope=request.scope, recursive=request.recursive
    )
    notify_capacity_changed()
    return BatchOperationResponse(**result)


@router.post(
    "/conflicts/preflight",
    response_model=FileConflictPreflightResponse,
    summary="Preflight workspace file conflicts",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def preflight_file_conflicts(
    payload: FileConflictPreflightRequest,
    service: FileService = Depends(get_new_file_service),
) -> FileConflictPreflightResponse:
    try:
        sources = payload.sources or []
        if payload.operation == "upload":
            result = service.preflight_upload_files(
                target_path=payload.targetPath,
                filenames=[source.sourcePath for source in sources],
            )
        elif payload.operation == "paste":
            result = service.preflight_copy_entries(
                source_paths=[source.sourcePath for source in sources],
                target_path=payload.targetPath,
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
            )
        return FileConflictPreflightResponse(**result)
    except FileNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.to_dict()
        )
    except FileManagementException as exc:
        raise HTTPException(
            status_code=_file_management_status(exc), detail=exc.to_dict()
        )


@router.post(
    "/paste",
    response_model=FileConflictBatchResult,
    summary="Paste workspace files",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def paste_entries(
    payload: FileConflictExecutionRequest,
    service: FileService = Depends(get_new_file_service),
) -> FileConflictBatchResult:
    try:
        result = service.paste_entries(
            source_paths=[source.sourcePath for source in payload.sources],
            target_path=payload.targetPath,
            default_strategy=payload.defaultStrategy,
            resolutions=payload.resolutions,
        )
        if result["succeeded"]:
            notify_capacity_changed()
        return FileConflictBatchResult(**result)
    except FileNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.to_dict()
        )
    except FileManagementException as exc:
        raise HTTPException(
            status_code=_file_management_status(exc), detail=exc.to_dict()
        )


@router.post(
    "/move",
    response_model=FileOperationResponse,
    summary="Move or rename",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def move_entry(
    request: FileMoveRequest, service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Move or rename file or directory"""
    try:
        result = service.move_entry(
            source_path=request.sourcePath,
            dest_path=request.destPath,
            source_scope=request.sourceScope,
            dest_scope=request.destScope,
        )
        return FileOperationResponse(success=True, data=result)
    except FileNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
    except FileAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())


@router.post(
    "/extract",
    response_model=FileConflictBatchResult,
    summary="Extract a workspace ZIP archive",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def extract_archive(
    payload: FileExtractExecutionRequest,
    service: FileService = Depends(get_new_file_service),
) -> FileConflictBatchResult:
    try:
        result = service.extract_archive_path(
            archive_path=payload.archivePath,
            target_path=payload.targetPath,
            default_strategy=payload.defaultStrategy,
            resolutions=payload.resolutions,
        )
        if result["succeeded"]:
            notify_capacity_changed()
        return FileConflictBatchResult(**result)
    except FileNotFoundException as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.to_dict()
        )
    except FileManagementException as exc:
        raise HTTPException(
            status_code=_file_management_status(exc), detail=exc.to_dict()
        )


@router.post(
    "/archive",
    response_model=ArchiveDownloadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Background package selected files as ZIP",
    responses=build_responses(400, 404, 422, 500),
)
async def create_archive_download(
    payload: ArchiveDownloadRequest,
    background_tasks: BackgroundTasks,
    service: FileService = Depends(get_new_file_service),
) -> ArchiveDownloadAcceptedResponse:
    """Create a background archive download task."""
    try:
        archive_name = _sanitize_archive_name(payload.archiveName, payload.paths)
        operation = _create_archive_download_operation()
        background_tasks.add_task(
            _run_archive_download_operation,
            operation.operation_id,
            service,
            payload.paths,
            archive_name,
        )
        return ArchiveDownloadAcceptedResponse(
            operationId=operation.operation_id,
            status="pending",
            message=operation.message,
            startedAt=operation.started_at,
        )
    except FileManagementException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())


@router.get(
    "/archive/{operation_id}",
    response_model=ArchiveDownloadStatusResponse,
    summary="Query background ZIP packaging status",
    responses=build_responses(404, 500),
)
async def get_archive_download_status(
    operation_id: str = ApiPath(..., description="Background archive operation ID"),
) -> ArchiveDownloadStatusResponse:
    """Query background archive packaging task progress."""
    _cleanup_expired_archive_operations()
    operation = _archive_operation_store.get(
        scope_key=WORKSPACE_OPERATION_SCOPE,
        operation_id=operation_id,
    )
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_FOUND",
                "message": f"Archive operation not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    return _archive_operation_response(operation)


@router.get(
    "/archive/{operation_id}/download",
    summary="Download completed ZIP archive",
    responses=build_responses(400, 404, 409, 500),
)
async def download_archive(
    operation_id: str = ApiPath(..., description="Background archive operation ID"),
) -> FileResponse:
    """Download a completed archive operation result."""
    _cleanup_expired_archive_operations()
    operation = _archive_operation_store.get(
        scope_key=WORKSPACE_OPERATION_SCOPE,
        operation_id=operation_id,
    )
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_FOUND",
                "message": f"Archive operation not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    if (
        operation.status != "completed"
        or not operation.result
        or not operation.artifact_path
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_READY",
                "message": f"Archive operation is not ready: {operation_id}",
                "details": {"operationId": operation_id, "status": operation.status},
            },
        )
    if not operation.artifact_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_FILE_NOT_FOUND",
                "message": f"Archive file not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    return FileResponse(
        path=operation.artifact_path,
        filename=operation.result.archiveName,
        media_type="application/zip",
    )


@router.post(
    "/upload",
    response_model=FileConflictBatchResult,
    summary="Upload files",
    responses=build_responses(400, 409, 422, 500),
)
async def upload_files(
    target_path: str = Form(..., alias="targetPath"),
    default_strategy: ConflictStrategy = Form(..., alias="defaultStrategy"),
    resolutions: str = Form(...),
    files: List[UploadFile] = File(..., description="Files to upload"),
    service: FileService = Depends(get_new_file_service),
) -> FileConflictBatchResult:
    try:
        streams = []
        for file in files:
            filename = Path(file.filename or "").name
            if not filename:
                raise FileManagementException(
                    "INVALID_UPLOAD_FILENAME",
                    "Upload filename is required",
                    {},
                    400,
                )
            streams.append((filename, file.file, _upload_size(file)))
        result = await run_in_threadpool(
            service.upload_file_streams,
            target_path=target_path,
            files=streams,
            default_strategy=default_strategy,
            resolutions=_FILE_CONFLICT_RESOLUTIONS.validate_json(resolutions),
        )
        if result["succeeded"]:
            notify_capacity_changed()
        return FileConflictBatchResult(**result)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(),
        ) from exc
    except FileManagementException as exc:
        raise HTTPException(
            status_code=_file_management_status(exc), detail=exc.to_dict()
        )
