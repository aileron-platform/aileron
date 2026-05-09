"""Refactored file API routes"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
import mimetypes
import os
import posixpath
import re
import tempfile
from pathlib import Path
from typing import Callable, List, Optional
from uuid import uuid4
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Path as ApiPath, Query, UploadFile, status
from fastapi.responses import FileResponse, Response

from app.config.settings import get_settings
from app.core.openapi import build_responses
from app.modules.version_control.utils import GitUtils, VersionControlError
from app.modules.version_control.worktree_config import get_worktree_subdir
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
    ArchiveDownloadAcceptedResponse,
    ArchiveDownloadRequest,
    ArchiveDownloadResult,
    ArchiveDownloadStatusResponse,
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

router = APIRouter(prefix="/files", tags=["File Management"])

ARCHIVE_ACTIONS = {"store", "extract"}
CONFLICT_STRATEGIES = {"rename", "overwrite", "reject"}
ARCHIVE_DOWNLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "aileron-archive-downloads"


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


@dataclass
class ArchiveFileEntry:
    fs_path: Path
    archive_path: str
    size: int


@dataclass
class ArchiveDownloadOperation:
    operation_id: str
    status: str
    progress: float
    message: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    result: Optional[ArchiveDownloadResult] = None
    temp_path: Optional[Path] = None
    expires_at: Optional[datetime] = None

    def to_response(self) -> ArchiveDownloadStatusResponse:
        return ArchiveDownloadStatusResponse(
            operationId=self.operation_id,
            status=self.status,
            progress=self.progress,
            message=self.message,
            startedAt=self.started_at,
            completedAt=self.completed_at,
            error=self.error,
            result=self.result,
        )


_archive_download_operations: dict[str, ArchiveDownloadOperation] = {}


def _resolve_file_service_root(context_id: str | None) -> Path:
    settings = get_settings()
    workspace_root = Path(settings.WORKSPACE_PATH).resolve()

    if not context_id or context_id == "primary":
        return workspace_root

    utils = GitUtils(workspace_root.parent, worktree_subdir=get_worktree_subdir())
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
        progress_callback(0.1, "Scanning archive content...")

    extracted_results: List[UploadResult] = []
    total_entries = len(extraction_plan)

    if total_entries == 0:
        if progress_callback:
            progress_callback(1.0, "Archive has no files to extract")
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
                    f"Extracting {index}/{total_entries}: {info.filename}",
                )

    return extracted_results


def _create_extract_operation(message: str = "Preparing to extract ZIP file...") -> ExtractArchiveOperation:
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
            message="Reading ZIP file...",
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
            message=f"Extraction completed, {len(extracted)} items total",
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
            message=f"Extraction failed: {exc}",
            error=str(exc),
        )


def _resolve_extract_target_path(archive_path: str, target_path: Optional[str]) -> str:
    if target_path:
        return target_path
    return _get_archive_parent_path(archive_path)


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


def _remove_redundant_archive_roots(paths: List[Path]) -> List[Path]:
    selected: List[Path] = []
    for path in sorted(paths, key=lambda item: len(item.parts)):
        if any(_is_relative_to(path, parent) for parent in selected):
            continue
        selected.append(path)
    return selected


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _common_archive_base(paths: List[Path]) -> Path:
    parent_paths = [path.parent for path in paths]
    return Path(os.path.commonpath([str(path) for path in parent_paths]))


def _zip_entry_name(file_path: Path, base_path: Path) -> str:
    entry_name = file_path.relative_to(base_path).as_posix()
    normalized = posixpath.normpath(entry_name)
    if normalized in {"", ".", ".."} or normalized.startswith("../") or normalized.startswith("/"):
        raise InvalidPathException(str(file_path), "Invalid archive entry path")
    return normalized


def _build_archive_download_plan(
    service: FileService,
    paths: List[str],
) -> tuple[List[ArchiveFileEntry], List[str]]:
    settings = get_settings()
    if len(paths) > settings.ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS:
        raise FileManagementException(
            "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
            "Archive selected root count exceeds limit",
            {
                "selectedRootCount": len(paths),
                "maxSelectedRootCount": settings.ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS,
            },
            400,
        )

    root_path = service.resolve_scope_path(None, "/").resolve()
    resolved_roots: List[Path] = []
    seen_roots: set[str] = set()
    normalized_request_paths: List[str] = []

    for raw_path in paths:
        request_path = _normalize_archive_request_path(raw_path)
        fs_path = _ensure_path_within_root(root_path, service.resolve_scope_path(None, request_path), request_path)
        if not fs_path.exists():
            raise FileNotFoundException(request_path)
        root_key = str(fs_path)
        if root_key in seen_roots:
            continue
        seen_roots.add(root_key)
        resolved_roots.append(fs_path)
        normalized_request_paths.append(request_path)

    selected_roots = _remove_redundant_archive_roots(resolved_roots)
    base_path = _common_archive_base(selected_roots)
    entries: List[ArchiveFileEntry] = []
    seen_entries: set[str] = set()
    total_size = 0

    for root in selected_roots:
        if root.is_symlink():
            continue

        if root.is_file():
            candidates = [root]
        elif root.is_dir():
            candidates = []
            for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
                dirnames[:] = [
                    dirname
                    for dirname in dirnames
                    if not (Path(current_dir) / dirname).is_symlink()
                ]
                for filename in filenames:
                    candidates.append(Path(current_dir) / filename)
        else:
            continue

        for candidate in candidates:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved_candidate = _ensure_path_within_root(root_path, candidate, str(candidate))
            stat = resolved_candidate.stat()
            total_size += stat.st_size

            if len(entries) + 1 > settings.ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT:
                raise FileManagementException(
                    "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
                    "Archive file entry count exceeds limit",
                    {
                        "entryCount": len(entries) + 1,
                        "maxEntryCount": settings.ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT,
                    },
                    400,
                )
            if total_size > settings.ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES:
                raise FileManagementException(
                    "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
                    "Archive total size exceeds limit",
                    {
                        "totalSize": total_size,
                        "maxTotalSize": settings.ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES,
                    },
                    400,
                )

            entry_name = _zip_entry_name(resolved_candidate, base_path)
            if entry_name in seen_entries:
                continue
            seen_entries.add(entry_name)
            entries.append(ArchiveFileEntry(fs_path=resolved_candidate, archive_path=entry_name, size=stat.st_size))

    return entries, normalized_request_paths


def _create_archive_download_operation(message: str = "Preparing ZIP download...") -> ArchiveDownloadOperation:
    _cleanup_expired_archive_operations()
    operation_id = f"archive-{uuid4().hex[:12]}"
    operation = ArchiveDownloadOperation(
        operation_id=operation_id,
        status="pending",
        progress=0.0,
        message=message,
        started_at=datetime.now(timezone.utc),
    )
    _archive_download_operations[operation_id] = operation
    return operation


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
    operation = _archive_download_operations.get(operation_id)
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
    if temp_path is not None:
        operation.temp_path = temp_path
    if expires_at is not None:
        operation.expires_at = expires_at
    if status_value in {"completed", "failed", "expired"}:
        operation.completed_at = datetime.now(timezone.utc)


def _cleanup_expired_archive_operations() -> None:
    now = datetime.now(timezone.utc)
    expired_ids: List[str] = []
    ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)

    for operation_id, operation in list(_archive_download_operations.items()):
        if operation.expires_at and operation.expires_at <= now:
            if operation.temp_path and operation.temp_path.exists():
                try:
                    operation.temp_path.unlink()
                except OSError:
                    pass
            expired_ids.append(operation_id)

    for operation_id in expired_ids:
        del _archive_download_operations[operation_id]


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

        entries, _ = _build_archive_download_plan(service, paths)
        if not entries:
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
            message=f"Packaging 0/{len(entries)} files...",
        )

        ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = ARCHIVE_DOWNLOAD_TEMP_DIR / f"{operation_id}.zip"

        with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for index, entry in enumerate(entries, start=1):
                archive.write(entry.fs_path, entry.archive_path)
                _update_archive_download_operation(
                    operation_id,
                    status_value="running",
                    progress=0.1 + (index / len(entries)) * 0.85,
                    message=f"Packaging {index}/{len(entries)} files...",
                )

        settings = get_settings()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.ARCHIVE_DOWNLOAD_TTL_SECONDS)
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
            message=f"Archive ready, {len(entries)} files packaged",
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
    "/tree",
    response_model=FileTreeResponse,
    summary="Get file tree",
    responses=build_responses(400, 404, 422, 500),
)
async def get_file_tree(
    path: str = Query("/", description="Target path"),
    scope: Optional[str] = Query(None, description="Scope identifier (not used for Files)"),
    include_hidden: bool = Query(False, alias="includeHidden", description="Whether to include hidden files"),
    max_depth: Optional[int] = Query(None, alias="maxDepth", ge=1, description="Maximum depth (defaults to FILE_TREE_MAX_DEPTH in config)"),
    service: FileService = Depends(get_new_file_service)
) -> FileTreeResponse:
    """Get file tree structure

    If max_depth is not provided, uses FILE_TREE_MAX_DEPTH from environment configuration
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
    summary="Lazy load child nodes",
    responses=build_responses(400, 404, 422, 500),
)
async def get_directory_children(
    path: str = Query(..., description="Target directory path"),
    scope: Optional[str] = Query(None, description="Scope identifier (not used for Files)"),
    include_hidden: bool = Query(False, alias="includeHidden", description="Whether to include hidden files"),
    max_depth: Optional[int] = Query(None, alias="maxDepth", ge=1, description="Maximum depth (defaults to FILE_TREE_MAX_DEPTH in config)"),
    service: FileService = Depends(get_new_file_service)
) -> FileTreeResponse:
    """Lazy load: dynamically get child nodes of specified directory

    If max_depth is not provided, uses FILE_TREE_MAX_DEPTH from environment configuration
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
    scope: Optional[str] = Query(None, description="Scope identifier (not used for Files)"),
    raw: bool = Query(False, description="Whether to return raw binary content"),
    service: FileService = Depends(get_new_file_service)
):
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
                    "Content-Disposition": f'inline; filename="{path.split("/")[-1]}"'
                }
            )

        # Otherwise return JSON format text content
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


@router.get(
    "/download",
    summary="Download file",
    responses=build_responses(400, 404, 422, 500),
)
async def download_file(
    path: str = Query(..., description="File path"),
    service: FileService = Depends(get_new_file_service),
):
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    except FileManagementException as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.to_dict()
        )


@router.put(
    "/content",
    response_model=FileOperationResponse,
    summary="Write file content",
    responses=build_responses(400, 403, 422, 500),
)
async def write_file(
    request: FileWriteRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Write file content"""
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
    summary="Batch write files",
    responses=build_responses(400, 403, 422, 500),
)
async def batch_write_files(
    request: BatchWriteRequest,
    service: FileService = Depends(get_new_file_service)
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
    request: FileCreateRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Create file or directory"""
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
    summary="Delete file or directory",
    responses=build_responses(400, 404, 422, 500),
)
async def delete_entry(
    path: str = Query(..., description="Path"),
    scope: Optional[str] = Query(None, description="Scope identifier (not used for Files)"),
    recursive: bool = Query(False, description="Whether to recursively delete directory"),
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Delete file or directory"""
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
    summary="Batch delete",
    responses=build_responses(400, 422, 500),
)
async def batch_delete_entries(
    request: BatchDeleteRequest,
    service: FileService = Depends(get_new_file_service)
) -> BatchOperationResponse:
    """Batch delete files or directories"""
    result = service.batch_delete(
        paths=request.paths,
        scope=request.scope,
        recursive=request.recursive
    )
    return BatchOperationResponse(**result)


@router.post(
    "/copy",
    response_model=FileOperationResponse,
    summary="Copy file or directory",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def copy_entry(
    request: FileCopyRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Copy file or directory (supports folder copy)"""
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
    summary="Move or rename",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def move_entry(
    request: FileMoveRequest,
    service: FileService = Depends(get_new_file_service)
) -> FileOperationResponse:
    """Move or rename file or directory"""
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
    summary="Background extract existing ZIP file",
    responses=build_responses(400, 404, 409, 422, 500),
)
async def extract_archive(
    payload: ExtractArchiveRequest,
    background_tasks: BackgroundTasks,
    service: FileService = Depends(get_new_file_service),
) -> ExtractArchiveAcceptedResponse:
    """Add existing ZIP file to background extraction task."""
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
    summary="Query background ZIP extraction status",
    responses=build_responses(404, 500),
)
async def get_extract_archive_status(
    operation_id: str = ApiPath(..., description="Background extraction operation ID"),
) -> ExtractArchiveStatusResponse:
    """Query background ZIP extraction task progress."""
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
            status=operation.status,
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
    operation = _archive_download_operations.get(operation_id)
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_FOUND",
                "message": f"Archive operation not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    return operation.to_response()


@router.get(
    "/archive/{operation_id}/download",
    summary="Download completed ZIP archive",
    responses=build_responses(400, 404, 409, 500),
)
async def download_archive(
    operation_id: str = ApiPath(..., description="Background archive operation ID"),
):
    """Download a completed archive operation result."""
    _cleanup_expired_archive_operations()
    operation = _archive_download_operations.get(operation_id)
    if operation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_FOUND",
                "message": f"Archive operation not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    if operation.status != "completed" or not operation.result or not operation.temp_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ARCHIVE_OPERATION_NOT_READY",
                "message": f"Archive operation is not ready: {operation_id}",
                "details": {"operationId": operation_id, "status": operation.status},
            },
        )
    if not operation.temp_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ARCHIVE_FILE_NOT_FOUND",
                "message": f"Archive file not found: {operation_id}",
                "details": {"operationId": operation_id},
            },
        )
    return FileResponse(
        path=operation.temp_path,
        filename=operation.result.archiveName,
        media_type="application/zip",
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload files",
    responses=build_responses(400, 409, 422, 500),
)
async def upload_files(
    targetPath: str = Form(..., description="Target directory path"),
    conflictStrategy: str = Form(default="rename", description="Conflict handling strategy: overwrite, rename, or reject"),
    archiveAction: str = Form(default="store", description="Archive processing strategy: store or extract"),
    keepArchive: bool = Form(default=False, description="Whether to keep original ZIP when extracting"),
    files: List[UploadFile] = File(..., description="Files to upload"),
    service: FileService = Depends(get_new_file_service)
) -> UploadResponse:
    """Upload one or more files using multipart/form-data

    Automatically handles all file types (text, binary), no manual judgment or encoding needed
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
