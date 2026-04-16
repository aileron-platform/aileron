"""重構後的檔案 API 路由"""

from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
import mimetypes
import posixpath
from pathlib import Path
from typing import Callable, List, Optional
from uuid import uuid4
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Path as ApiPath, Query, UploadFile, status
from fastapi.responses import Response

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.version_control.utils import GitUtils, VersionControlError
from .exceptions import (
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileManagementException,
    FileNotFoundException,
    InvalidPathException,
    ReadonlyScopeException,
)
from .dependencies import get_file_service_sync
from .models import (
    BatchDeleteRequest,
    BatchOperationResponse,
    ExtractArchiveAcceptedResponse,
    ExtractArchiveRequest,
    ExtractArchiveResult,
    ExtractArchiveStatusResponse,
    BatchWriteRequest,
    FileContentResponse,
    FileCopyRequest,
    FileCreateRequest,
    FileMoveRequest,
    FileOperationResponse,
    FileTreeResponse,
    FileWriteRequest,
    UploadResponse,
    UploadResult,
)
from .service import FileService

router = APIRouter(prefix="/files", tags=["檔案管理"])

ARCHIVE_ACTIONS = {"store", "extract"}
CONFLICT_STRATEGIES = {"rename", "overwrite", "reject"}


@dataclass
class ExtractArchiveOperation:
    operation_id: str
    status: str
    progress: float
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[ExtractArchiveResult] = None

    def to_response(self) -> ExtractArchiveStatusResponse:
        return ExtractArchiveStatusResponse(
            operationId=self.operation_id,
            status=self.status,
            progress=self.progress,
            message=self.message,
            startedAt=self.started_at,
            completedAt=self.completed_at,
            error=self.error,
            result=self.result,
        )


_extract_operations: dict[str, ExtractArchiveOperation] = {}


def _resolve_file_service_root(context_id: str | None) -> Path:
    settings = get_settings()
    workspace_root = Path(settings.WORKSPACE_PATH).resolve()

    if not context_id:
        return workspace_root

    utils = GitUtils(workspace_root.parent)
    workspace_id = workspace_root.name

    try:
        return utils.resolve_context_path(workspace_id, context_id)
    except VersionControlError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.error_code, "message": str(exc)},
        ) from exc


def get_new_file_service(
    context_id: str | None = Query(None, alias="contextId", description="Git context ID"),
) -> FileService:
    if context_id is None:
        service = get_file_service_sync()
        return service
    return FileService(root_path=_resolve_file_service_root(context_id))


def _normalize_target_path(target_path: str) -> str:
    if not target_path or target_path == "/":
        return ""
    return target_path.rstrip("/")


def _join_upload_path(base_path: str, child_path: str) -> str:
    normalized_base = _normalize_target_path(base_path)
    normalized_child = child_path.lstrip("/")
    if not normalized_base:
        return normalized_child
    if not normalized_child:
        return normalized_base
    return f"{normalized_base}/{normalized_child}"


def _path_exists(service: FileService, file_path: str) -> bool:
    return service.resolve_scope_path(None, file_path).exists()


def _build_upload_result(file_path: str, fs_path: Path, entry_type: str = "file") -> UploadResult:
    stat = fs_path.stat()
    return UploadResult(
        path=file_path,
        size=0 if entry_type == "directory" else stat.st_size,
        lastModified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        type=entry_type,
    )


def _get_archive_parent_path(file_path: str) -> str:
    parent = posixpath.dirname(file_path)
    return parent or "/"


def _validate_upload_options(archive_action: str, conflict_strategy: str) -> None:
    if archive_action not in ARCHIVE_ACTIONS:
        raise FileManagementException(
            "INVALID_ARCHIVE_ACTION",
            f"Unsupported archive action: {archive_action}",
            {"archiveAction": archive_action},
            400,
        )
    if conflict_strategy not in CONFLICT_STRATEGIES:
        raise FileManagementException(
            "INVALID_CONFLICT_STRATEGY",
            f"Unsupported conflict strategy: {conflict_strategy}",
            {"conflictStrategy": conflict_strategy},
            400,
        )


def _generate_nonconflicting_path(
    service: FileService,
    desired_path: str,
    planned_paths: set[str],
) -> str:
    directory = posixpath.dirname(desired_path)
    filename = posixpath.basename(desired_path)
    stem, suffix = posixpath.splitext(filename)
    counter = 1

    while True:
        candidate = _join_upload_path(directory, f"{stem}_{counter}{suffix}")
        candidate_fs_path = str(service.resolve_scope_path(None, candidate))
        if candidate_fs_path not in planned_paths and not _path_exists(service, candidate):
            return candidate
        counter += 1


def _resolve_conflict_path(
    service: FileService,
    desired_path: str,
    conflict_strategy: str,
    planned_paths: set[str],
) -> str:
    desired_fs_path = str(service.resolve_scope_path(None, desired_path))
    path_taken = desired_fs_path in planned_paths or _path_exists(service, desired_path)

    if not path_taken or conflict_strategy == "overwrite":
        planned_paths.add(desired_fs_path)
        return desired_path

    if conflict_strategy == "reject":
        raise FileAlreadyExistsException(desired_path)

    renamed_path = _generate_nonconflicting_path(service, desired_path, planned_paths)
    planned_paths.add(str(service.resolve_scope_path(None, renamed_path)))
    return renamed_path


def _normalize_archive_entry(entry_name: str) -> str:
    normalized_name = entry_name.replace("\\", "/")
    if normalized_name.startswith("/") or (len(normalized_name) >= 2 and normalized_name[1] == ":"):
        raise FileManagementException(
            "INVALID_ARCHIVE_ENTRY",
            f"Archive entry has an absolute path: {entry_name}",
            {"entry": entry_name},
            400,
        )

    normalized_path = posixpath.normpath(normalized_name)
    if normalized_path in {"", ".", ".."} or normalized_path.startswith("../"):
        raise FileManagementException(
            "INVALID_ARCHIVE_ENTRY",
            f"Archive entry escapes target path: {entry_name}",
            {"entry": entry_name},
            400,
        )

    return normalized_path


async def _store_uploaded_file(
    service: FileService,
    target_path: str,
    upload_file: UploadFile,
    conflict_strategy: str,
) -> UploadResult:
    filename = Path(upload_file.filename or "").name
    desired_path = _join_upload_path(target_path, filename)
    final_path = _resolve_conflict_path(service, desired_path, conflict_strategy, set())
    content = await upload_file.read()

    fs_path = service.resolve_scope_path(None, final_path)
    fs_path.parent.mkdir(parents=True, exist_ok=True)
    fs_path.write_bytes(content)
    return _build_upload_result(final_path, fs_path)


def _build_extraction_plan(
    service: FileService,
    target_path: str,
    archive_name: str,
    archive_bytes: bytes,
    conflict_strategy: str,
) -> List[tuple[zipfile.ZipInfo, str]]:
    settings = get_settings()

    try:
        archive = zipfile.ZipFile(BytesIO(archive_bytes))
    except zipfile.BadZipFile as exc:
        raise FileManagementException(
            "INVALID_ARCHIVE",
            f"Invalid ZIP archive: {archive_name}",
            {"filename": archive_name},
            400,
        ) from exc

    planned_paths: set[str] = set()
    extraction_plan: List[tuple[zipfile.ZipInfo, str]] = []
    total_size = 0

    with archive:
        infos = archive.infolist()
        if len(infos) > settings.ARCHIVE_MAX_ENTRY_COUNT:
            raise FileManagementException(
                "ARCHIVE_LIMIT_EXCEEDED",
                "Archive entry count exceeds limit",
                {
                    "filename": archive_name,
                    "entryCount": len(infos),
                    "maxEntryCount": settings.ARCHIVE_MAX_ENTRY_COUNT,
                },
                400,
            )

        for info in infos:
            if info.is_dir():
                continue

            normalized_entry = _normalize_archive_entry(info.filename)
            if info.file_size > settings.ARCHIVE_MAX_ENTRY_SIZE_BYTES:
                raise FileManagementException(
                    "ARCHIVE_LIMIT_EXCEEDED",
                    "Archive entry size exceeds limit",
                    {
                        "filename": archive_name,
                        "entry": info.filename,
                        "entrySize": info.file_size,
                        "maxEntrySize": settings.ARCHIVE_MAX_ENTRY_SIZE_BYTES,
                    },
                    400,
                )

            total_size += info.file_size
            if total_size > settings.ARCHIVE_MAX_TOTAL_SIZE_BYTES:
                raise FileManagementException(
                    "ARCHIVE_LIMIT_EXCEEDED",
                    "Archive total extracted size exceeds limit",
                    {
                        "filename": archive_name,
                        "totalSize": total_size,
                        "maxTotalSize": settings.ARCHIVE_MAX_TOTAL_SIZE_BYTES,
                    },
                    400,
                )

            desired_path = _join_upload_path(target_path, normalized_entry)
            final_path = _resolve_conflict_path(service, desired_path, conflict_strategy, planned_paths)
            extraction_plan.append((info, final_path))

    return extraction_plan


def _extract_archive(
    service: FileService,
    target_path: str,
    archive_name: str,
    archive_bytes: bytes,
    conflict_strategy: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> List[UploadResult]:
    extraction_plan = _build_extraction_plan(
        service=service,
        target_path=target_path,
        archive_name=archive_name,
        archive_bytes=archive_bytes,
        conflict_strategy=conflict_strategy,
    )

    if progress_callback:
        progress_callback(0.1, "正在掃描壓縮檔內容...")

    extracted_results: List[UploadResult] = []
    total_entries = len(extraction_plan)

    if total_entries == 0:
        if progress_callback:
            progress_callback(1.0, "壓縮檔沒有可解壓的檔案")
        return extracted_results

    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        for index, (info, final_path) in enumerate(extraction_plan, start=1):
            fs_path = service.resolve_scope_path(None, final_path)
            fs_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source:
                fs_path.write_bytes(source.read())
            extracted_results.append(_build_upload_result(final_path, fs_path))

            if progress_callback:
                progress_callback(
                    index / total_entries,
                    f"正在解壓 {index}/{total_entries}: {info.filename}",
                )

    return extracted_results


def _create_extract_operation(message: str = "準備解壓縮 ZIP 檔案...") -> ExtractArchiveOperation:
    operation_id = f"extract-{uuid4().hex[:12]}"
    operation = ExtractArchiveOperation(
        operation_id=operation_id,
        status="pending",
        progress=0.0,
        message=message,
        started_at=datetime.now(timezone.utc),
    )
    _extract_operations[operation_id] = operation
    return operation


def _update_extract_operation(
    operation_id: str,
    *,
    status_value: Optional[str] = None,
    progress: Optional[float] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
    result: Optional[ExtractArchiveResult] = None,
) -> None:
    operation = _extract_operations.get(operation_id)
    if operation is None:
        return

    if status_value is not None:
        operation.status = status_value
    if progress is not None:
        operation.progress = min(1.0, max(0.0, progress))
    if message is not None:
        operation.message = message
    if error is not None:
        operation.error = error
    if result is not None:
        operation.result = result
    if status_value in {"completed", "failed"}:
        operation.completed_at = datetime.now(timezone.utc)


def _run_extract_archive_operation(
    operation_id: str,
    service: FileService,
    archive_path: str,
    target_path: str,
    conflict_strategy: str,
) -> None:
    try:
        _update_extract_operation(
            operation_id,
            status_value="running",
            progress=0.02,
            message="正在讀取 ZIP 檔案...",
        )

        archive_fs_path = service.resolve_scope_path(None, archive_path)
        if not archive_fs_path.exists() or not archive_fs_path.is_file():
            raise FileNotFoundException(archive_path)
        if archive_fs_path.suffix.lower() != ".zip":
            raise FileManagementException(
                "INVALID_ARCHIVE",
                "Only ZIP archives are supported",
                {"archivePath": archive_path},
                400,
            )

        archive_bytes = archive_fs_path.read_bytes()
        extracted = _extract_archive(
            service=service,
            target_path=target_path,
            archive_name=archive_fs_path.name,
            archive_bytes=archive_bytes,
            conflict_strategy=conflict_strategy,
            progress_callback=lambda progress, message: _update_extract_operation(
                operation_id,
                status_value="running",
                progress=progress,
                message=message,
            ),
        )
        result = ExtractArchiveResult(
            extracted=extracted,
            extractedPaths=[item.path for item in extracted],
        )
        _update_extract_operation(
            operation_id,
            status_value="completed",
            progress=1.0,
            message=f"解壓完成，共 {len(extracted)} 個項目",
            result=result,
        )
    except FileManagementException as exc:
        _update_extract_operation(
            operation_id,
            status_value="failed",
            message=exc.message,
            error=exc.message,
        )
    except Exception as exc:  # pragma: no cover - guarded by integration tests
        _update_extract_operation(
            operation_id,
            status_value="failed",
            message=f"解壓失敗: {exc}",
            error=str(exc),
        )


def _resolve_extract_target_path(archive_path: str, target_path: Optional[str]) -> str:
    if target_path:
        return target_path
    return _get_archive_parent_path(archive_path)

@router.get(
    "/tree",
    response_model=FileTreeResponse,
    summary="取得檔案樹",
    responses=build_responses(400, 404, 422, 500),
)
async def get_file_tree(
    path: str = Query("/", description="目標路徑"),
    scope: Optional[str] = Query(None, description="範圍識別（Files 不使用）"),
    include_hidden: bool = Query(False, alias="includeHidden", description="是否包含隱藏檔"),
    max_depth: Optional[int] = Query(None, alias="maxDepth", ge=1, description="最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）"),
    service: FileService = Depends(get_new_file_service)
) -> FileTreeResponse:
    """取得檔案樹結構

    如果未提供 max_depth，將使用環境設定檔中的 FILE_TREE_MAX_DEPTH
    """
    try:
        result = service.get_tree(
            path=path,
            scope=scope,
            include_hidden=include_hidden,
            max_depth=max_depth
        )
        return FileTreeResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.get(
    "/tree/children",
    response_model=FileTreeResponse,
    summary="懶載入子節點",
    responses=build_responses(400, 404, 422, 500),
)
async def get_directory_children(
    path: str = Query(..., description="目標目錄路徑"),
    scope: Optional[str] = Query(None, description="範圍識別（Files 不使用）"),
    include_hidden: bool = Query(False, alias="includeHidden", description="是否包含隱藏檔"),
    max_depth: Optional[int] = Query(None, alias="maxDepth", ge=1, description="最大深度（預設使用設定檔中的 FILE_TREE_MAX_DEPTH）"),
    service: FileService = Depends(get_new_file_service)
) -> FileTreeResponse:
    """懶載入：動態取得指定目錄的子節點

    如果未提供 max_depth，將使用環境設定檔中的 FILE_TREE_MAX_DEPTH
    """
    try:
        result = service.get_tree(
            path=path,
            scope=scope,
            include_hidden=include_hidden,
            max_depth=max_depth
        )
        return FileTreeResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.get(
    "/content",
    response_model=FileContentResponse,
    summary="讀取檔案內容",
    responses={
        200: {
            "description": "成功讀取檔案。當 `raw=true` 時回傳原始檔案串流；否則回傳 JSON 內容。",
        },
        **build_responses(400, 404, 422, 500),
    },
)
async def read_file(
    path: str = Query(..., description="檔案路徑"),
    scope: Optional[str] = Query(None, description="範圍識別（Files 不使用）"),
    raw: bool = Query(False, description="是否返回原始二進制內容"),
    service: FileService = Depends(get_new_file_service)
):
    """讀取檔案內容

    - 當 raw=false 時，返回 JSON 格式的文本內容（僅適用於文本檔案）
    - 當 raw=true 時，返回原始二進制內容（適用於圖片等二進制檔案）
    """
    try:
        # 如果請求原始二進制內容
        if raw:
            binary_content = service.read_file_binary(path=path, scope=scope)

            # 根據檔案副檔名猜測 MIME 類型
            mime_type, _ = mimetypes.guess_type(path)
            if mime_type is None:
                mime_type = "application/octet-stream"

            return Response(
                content=binary_content,
                media_type=mime_type,
                headers={
                    "Content-Disposition": f'inline; filename="{path.split("/")[-1]}"'
                }
            )

        # 否則返回 JSON 格式的文本內容
        result = service.read_file(path=path, scope=scope)
        return FileContentResponse(**result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.put(
    "/content",
    response_model=FileOperationResponse,
    summary="寫入檔案內容",
    responses=build_responses(400, 403, 422, 500),
)
async def write_file(
    request: FileWriteRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """寫入檔案內容"""
    try:
        result = service.write_file(
            path=request.path,
            content=request.content,
            scope=request.scope,
            expected_version_id=request.expectedVersionId
        )
        return FileOperationResponse(success=True, data=result)
    except ReadonlyScopeException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.post(
    "/content/batch",
    response_model=BatchOperationResponse,
    summary="批次寫入檔案",
    responses=build_responses(400, 403, 422, 500),
)
async def batch_write_files(
    request: BatchWriteRequest,
    service: FileService = Depends(get_new_file_service)
) -> BatchOperationResponse:
    """批次寫入多個檔案"""
    result = service.batch_write(files=request.files, scope=request.scope)
    return BatchOperationResponse(**result)


@router.post(
    "",
    response_model=FileOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建立檔案或目錄",
    responses=build_responses(400, 409, 422, 500),
)
async def create_entry(
    request: FileCreateRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """建立檔案或目錄"""
    try:
        result = service.create_entry(
            path=request.path,
            entry_type=request.type,
            scope=request.scope,
            content=request.content or "",
            encoding=request.encoding or "utf-8"
        )
        return FileOperationResponse(success=True, data=result)
    except FileAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.delete(
    "",
    response_model=FileOperationResponse,
    summary="刪除檔案或目錄",
    responses=build_responses(400, 404, 422, 500),
)
async def delete_entry(
    path: str = Query(..., description="路徑"),
    scope: Optional[str] = Query(None, description="範圍識別（Files 不使用）"),
    recursive: bool = Query(False, description="是否遞迴刪除目錄"),
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """刪除檔案或目錄"""
    try:
        result = service.delete_entry(path=path, scope=scope, recursive=recursive)
        return FileOperationResponse(success=True, data=result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except DirectoryNotEmptyException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.post(
    "/batch-delete",
    response_model=BatchOperationResponse,
    summary="批次刪除",
    responses=build_responses(400, 422, 500),
)
async def batch_delete_entries(
    request: BatchDeleteRequest,
    service: FileService = Depends(get_new_file_service)
) -> BatchOperationResponse:
    """批次刪除檔案或目錄"""
    result = service.batch_delete(
        paths=request.paths,
        scope=request.scope,
        recursive=request.recursive
    )
    return BatchOperationResponse(**result)


@router.post(
    "/copy",
    response_model=FileOperationResponse,
    summary="複製檔案或目錄",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def copy_entry(
    request: FileCopyRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """複製檔案或目錄（支援資料夾複製）"""
    try:
        result = service.copy_entry(
            source_path=request.sourcePath,
            dest_path=request.destPath,
            source_scope=request.sourceScope,
            dest_scope=request.destScope,
            overwrite=request.overwrite
        )
        return FileOperationResponse(success=True, data=result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.post(
    "/move",
    response_model=FileOperationResponse,
    summary="移動或重命名",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def move_entry(
    request: FileMoveRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """移動或重命名檔案或目錄"""
    try:
        result = service.move_entry(
            source_path=request.sourcePath,
            dest_path=request.destPath,
            source_scope=request.sourceScope,
            dest_scope=request.destScope,
            overwrite=request.overwrite
        )
        return FileOperationResponse(success=True, data=result)
    except FileNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileAlreadyExistsException as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )


@router.post(
    "/extract",
    response_model=ExtractArchiveAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="背景解壓既有 ZIP 檔案",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def extract_archive(
    payload: ExtractArchiveRequest,
    background_tasks: BackgroundTasks,
    service: FileService = Depends(get_new_file_service),
) -> ExtractArchiveAcceptedResponse:
    """將既有 ZIP 檔案加入背景解壓任務。"""
    try:
        _validate_upload_options("extract", payload.conflictStrategy)
        archive_path = payload.archivePath if payload.archivePath.startswith("/") else f"/{payload.archivePath}"
        target_path = _resolve_extract_target_path(archive_path, payload.targetPath)
        operation = _create_extract_operation()
        background_tasks.add_task(
            _run_extract_archive_operation,
            operation.operation_id,
            service,
            archive_path,
            target_path,
            payload.conflictStrategy,
        )
        return ExtractArchiveAcceptedResponse(
            operationId=operation.operation_id,
            status=operation.status,
            message=operation.message,
            startedAt=operation.started_at,
        )
    except FileAlreadyExistsException as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.to_dict())
    except FileManagementException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.to_dict())


@router.get(
    "/extract/{operation_id}",
    response_model=ExtractArchiveStatusResponse,
    summary="查詢背景 ZIP 解壓狀態",
    responses=build_responses(404, 500),
)
async def get_extract_archive_status(
    operation_id: str = ApiPath(..., description="背景解壓 operation ID"),
) -> ExtractArchiveStatusResponse:
    """查詢背景 ZIP 解壓任務進度。"""
    operation = _extract_operations.get(operation_id)
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "EXTRACT_OPERATION_NOT_FOUND",
                "message": f"Extract operation not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    return operation.to_response()


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="上傳檔案",
    responses=build_responses(400, 409, 422, 500),
)
async def upload_files(
    targetPath: str = Form(..., description="目標目錄路徑"),
    conflictStrategy: str = Form(default="rename", description="衝突處理策略: overwrite、rename 或 reject"),
    archiveAction: str = Form(default="store", description="壓縮檔處理策略: store 或 extract"),
    keepArchive: bool = Form(default=False, description="解壓時是否保留原始 ZIP"),
    files: List[UploadFile] = File(..., description="要上傳的檔案"),
    service: FileService = Depends(get_new_file_service)
) -> UploadResponse:
    """使用 multipart/form-data 上傳一個或多個檔案

    自動處理所有類型的檔案（文本、二進制），無需手動判斷或編碼
    """
    uploaded: List[UploadResult] = []
    extracted: List[UploadResult] = []
    skipped: List[str] = []

    try:
        _validate_upload_options(archiveAction, conflictStrategy)

        for file in files:
            try:
                filename = Path(file.filename or "").name
                if not filename:
                    raise FileManagementException(
                        "INVALID_UPLOAD_FILENAME",
                        "Upload filename is required",
                        {},
                        400,
                    )

                if archiveAction == "extract" and filename.lower().endswith(".zip"):
                    archive_bytes = await file.read()
                    if keepArchive:
                        archive_path = _resolve_conflict_path(
                            service,
                            _join_upload_path(targetPath, filename),
                            conflictStrategy,
                            set(),
                        )
                        archive_fs_path = service.resolve_scope_path(None, archive_path)
                        archive_fs_path.parent.mkdir(parents=True, exist_ok=True)
                        archive_fs_path.write_bytes(archive_bytes)
                        uploaded.append(_build_upload_result(archive_path, archive_fs_path))

                    extracted.extend(
                        _extract_archive(
                            service=service,
                            target_path=targetPath,
                            archive_name=filename,
                            archive_bytes=archive_bytes,
                            conflict_strategy=conflictStrategy,
                        )
                    )
                    continue

                uploaded.append(
                    await _store_uploaded_file(
                        service=service,
                        target_path=targetPath,
                        upload_file=file,
                        conflict_strategy=conflictStrategy,
                    )
                )
            except FileManagementException:
                raise
            except Exception:
                skipped.append(file.filename or "")

        return UploadResponse(uploaded=uploaded, extracted=extracted, skipped=skipped)
    except FileAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.to_dict())
    except FileManagementException as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())
