from __future__ import annotations

import base64
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import os
from pathlib import Path
import posixpath
import shutil
import tempfile
from typing import BinaryIO, Optional, Sequence
import zipfile

from .adapters import FileOperationAdapter
from .errors import FileCoreError, VersionConflictError
from .hooks import FileMutationHooks, NoopMutationHooks
from .models import (
    ArchiveBuildResult,
    ArchiveBytesResult,
    ArchiveEntry,
    BatchDeleteRequest,
    BatchItemResult,
    BatchMutationResult,
    BatchWriteRequest,
    BuildArchiveRequest,
    CopyEntriesRequest,
    CopyEntryRequest,
    CreateEntryRequest,
    DeleteEntryRequest,
    ExtractArchiveRequest,
    ExtractArchiveStreamRequest,
    FileConflictItem,
    FileConflictPreflight,
    FileConflictResolution,
    FileBytes,
    FileContent,
    FileList,
    FileListItem,
    FileLocator,
    FileMutationResult,
    FileTree,
    FileTreeNode,
    ListFilesRequest,
    MoveEntryRequest,
    ReadBytesRequest,
    ReadTextRequest,
    SearchMatch,
    SearchRequest,
    SearchResult,
    SyncTreeRequest,
    TreeRequest,
    UploadBatchResult,
    WriteTextRequest,
    WriteBytesRequest,
    UploadFilesRequest,
    UploadItem,
    UploadItemResult,
    UploadStreamItem,
    iso_from_timestamp,
)
from .path_guard import SafePath
from .policies import FilePolicy
from .versioning import compare_and_write_text
from .write_lock import ResourceWriteLockManager


@dataclass
class FileOperationEngine:
    adapter: FileOperationAdapter
    policy: FilePolicy
    hooks: Optional[FileMutationHooks] = None
    write_locks: Optional[ResourceWriteLockManager] = None

    def __post_init__(self) -> None:
        if self.hooks is None:
            self.hooks = NoopMutationHooks()
        if self.write_locks is None:
            self.write_locks = ResourceWriteLockManager()

    def get_tree(self, request: TreeRequest) -> FileTree:
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        root = safe_path.absolute_path
        if not root.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"Path not found: {request.path}",
                {"path": request.path},
                404,
            )
        if not root.is_dir():
            raise FileCoreError(
                "NOT_A_DIRECTORY",
                f"Not a directory: {request.path}",
                {"path": request.path},
                400,
            )
        nodes = self._scan_directory(
            locator=request.locator,
            base_root=self.adapter.root_for(request.locator),
            current=root,
            depth=0,
            max_depth=request.max_depth,
            include_hidden=request.include_hidden,
        )
        tree_path = "/" if safe_path.relative_path == "." else safe_path.relative_path
        return FileTree(path=tree_path, nodes=nodes, total=len(nodes))

    def read_text(self, request: ReadTextRequest) -> FileContent:
        self.adapter.can_read(request.locator, request.path)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        path = safe_path.absolute_path
        self._require_file(path, request.path)
        size = path.stat().st_size
        if size > self.policy.max_read_bytes:
            return self._handle_large_text(safe_path.relative_path, path, size)

        try:
            raw = path.read_bytes()
            if self._looks_binary(raw):
                return self._handle_binary_text(
                    safe_path.relative_path,
                    path,
                    size,
                    reason="binary",
                )
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = self._decode_with_fallbacks(raw)
            if content is None:
                return self._handle_binary_text(
                    safe_path.relative_path,
                    path,
                    size,
                    reason="decode-error",
                )

        content, truncate_metadata = self._truncate_if_needed(content)
        digest = sha256(raw).hexdigest()
        version_id = self.policy.version_strategy.read_version(path)
        return FileContent(
            path=safe_path.relative_path,
            content=content,
            size=size,
            updated_at=iso_from_timestamp(path.stat().st_mtime),
            version_id=version_id,
            content_hash=version_id if version_id == digest else digest,
            readable=True,
            metadata=truncate_metadata,
        )

    def read_bytes(self, request: ReadBytesRequest) -> FileBytes:
        self.adapter.can_read(request.locator, request.path)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        path = safe_path.absolute_path
        self._require_file(path, request.path)
        content = path.read_bytes()
        return FileBytes(
            path=safe_path.relative_path,
            content=content,
            size=len(content),
            updated_at=iso_from_timestamp(path.stat().st_mtime),
        )

    def list_files(self, request: ListFilesRequest) -> FileList:
        self.adapter.can_read(request.locator, request.path)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        root = safe_path.absolute_path
        if not root.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"Path not found: {request.path}",
                {"path": request.path},
                404,
            )
        if not root.is_dir():
            raise FileCoreError(
                "NOT_A_DIRECTORY",
                f"Not a directory: {request.path}",
                {"path": request.path},
                400,
            )

        base_root = self.adapter.root_for(request.locator).resolve()
        items: list[FileListItem] = []
        for path in self._iter_list_files(base_root, root, request.include_hidden):
            relative_path = path.relative_to(base_root).as_posix()
            stat = path.stat()
            content: str | None = None
            content_encoding: str | None = None
            binary = False
            if request.include_content:
                raw = path.read_bytes()
                if self._looks_binary(raw):
                    content = base64.b64encode(raw).decode("ascii")
                    content_encoding = "base64"
                    binary = True
                else:
                    try:
                        content = raw.decode("utf-8")
                        content_encoding = "utf-8"
                    except UnicodeDecodeError:
                        content = base64.b64encode(raw).decode("ascii")
                        content_encoding = "base64"
                        binary = True
            items.append(
                FileListItem(
                    path=relative_path,
                    name=path.name,
                    size=stat.st_size,
                    updated_at=iso_from_timestamp(stat.st_mtime),
                    content=content,
                    content_encoding=content_encoding,
                    binary=binary,
                )
            )

        return FileList(items=items, total=len(items))

    def write_text(self, request: WriteTextRequest) -> FileMutationResult:
        operation = "write"
        content_size = len(request.content.encode(request.encoding))
        if content_size > self.policy.max_write_bytes:
            raise FileCoreError(
                "FILE_TOO_LARGE",
                f"File too large: {request.path}",
                {
                    "path": request.path,
                    "size": content_size,
                    "limit": self.policy.max_write_bytes,
                },
                413,
            )

        self.adapter.can_write(request.locator, request.path, operation)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        path = safe_path.absolute_path
        if path.exists() and path.is_dir():
            raise FileCoreError(
                "NOT_A_FILE",
                f"Not a file: {request.path}",
                {"path": request.path},
                400,
            )
        lock_key = self.adapter.lock_key_for(
            request.locator,
            safe_path.relative_path,
            operation,
        )

        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(request.locator, operation):
                if path.exists() and path.is_dir():
                    raise FileCoreError(
                        "NOT_A_FILE",
                        f"Not a file: {request.path}",
                        {"path": request.path},
                        400,
                    )
                previous_size = (
                    path.stat().st_size if path.exists() and path.is_file() else 0
                )
                delta = content_size - previous_size
                self.hooks.check_quota(request.locator, delta)
                if path.exists() and path.is_file():
                    self.hooks.snapshot_existing(
                        request.locator,
                        path,
                        safe_path.relative_path,
                        operation,
                    )
                self._ensure_parent_directory(path, request.path)
                write_result = compare_and_write_text(
                    path,
                    request.content,
                    expected_version_id=request.expected_version_id,
                    strategy=self.policy.version_strategy,
                    encoding=request.encoding,
                )
                self.hooks.after_size_change(request.locator, delta)
                self.hooks.validate_after_mutation(
                    request.locator,
                    operation,
                    [safe_path.relative_path],
                )
                result = FileMutationResult(
                    path=safe_path.relative_path,
                    operation=operation,
                    entry_type="file",
                    size=write_result.size,
                    version_id=write_result.version_id,
                    updated_at=iso_from_timestamp(path.stat().st_mtime),
                )
            self.hooks.after_mutation(
                request.locator,
                operation,
                [safe_path.relative_path],
            )

        return result

    def write_bytes(self, request: WriteBytesRequest) -> FileMutationResult:
        return self._write_bytes_mutation(
            locator=request.locator,
            relative_path=request.path,
            content=request.content,
            operation=request.operation,
            expected_version_id=request.expected_version_id,
        )

    def create_entry(self, request: CreateEntryRequest) -> FileMutationResult:
        operation = "create"
        self.adapter.can_write(request.locator, request.path, operation)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        path = safe_path.absolute_path
        if request.entry_type not in {"file", "directory"}:
            raise FileCoreError(
                "INVALID_ENTRY_TYPE",
                f"Invalid entry type: {request.entry_type}",
                {"entryType": request.entry_type},
                400,
            )
        if path.exists():
            raise FileCoreError(
                "FILE_ALREADY_EXISTS",
                f"Path already exists: {request.path}",
                {"path": request.path},
                409,
            )

        file_content: bytes | None = None
        if request.entry_type == "file":
            if request.encoding == "base64":
                file_content = base64.b64decode(request.content)
            else:
                file_content = request.content.encode(request.encoding)
        content_size = len(file_content) if file_content is not None else 0
        if content_size > self.policy.max_write_bytes:
            raise FileCoreError(
                "FILE_TOO_LARGE",
                f"File too large: {request.path}",
                {
                    "path": request.path,
                    "size": content_size,
                    "limit": self.policy.max_write_bytes,
                },
                413,
            )
        lock_key = self.adapter.lock_key_for(
            request.locator,
            safe_path.relative_path,
            operation,
        )

        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(request.locator, operation):
                self.hooks.check_quota(request.locator, content_size)
                if request.entry_type == "file":
                    self._ensure_parent_directory(path, request.path)
                    if file_content is None:
                        file_content = b""
                    path.write_bytes(file_content)
                else:
                    self._ensure_parent_directory(path, request.path)
                    path.mkdir(parents=True, exist_ok=False)
                self.hooks.after_size_change(request.locator, content_size)
                self.hooks.validate_after_mutation(
                    request.locator,
                    operation,
                    [safe_path.relative_path],
                )
            self.hooks.after_mutation(
                request.locator,
                operation,
                [safe_path.relative_path],
            )

        return FileMutationResult(
            path=safe_path.relative_path,
            operation=operation,
            entry_type=request.entry_type,
            size=content_size,
            updated_at=iso_from_timestamp(path.stat().st_mtime),
        )

    def delete_entry(self, request: DeleteEntryRequest) -> FileMutationResult:
        operation = "delete"
        self.adapter.can_write(request.locator, request.path, operation)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        path = safe_path.absolute_path
        if not path.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"Path not found: {request.path}",
                {"path": request.path},
                404,
            )
        if path.is_dir() and not request.recursive and any(path.iterdir()):
            raise FileCoreError(
                "DIRECTORY_NOT_EMPTY",
                f"Directory is not empty: {request.path}",
                {"path": request.path},
                409,
            )

        entry_type = "directory" if path.is_dir() else "file"
        removed_size = self._calculate_size(path)
        delta = -removed_size
        lock_key = self.adapter.lock_key_for(
            request.locator,
            safe_path.relative_path,
            operation,
        )

        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(request.locator, operation):
                self.hooks.check_quota(request.locator, delta)
                self._snapshot_existing_paths(
                    request.locator,
                    path,
                    safe_path.relative_path,
                    operation,
                )
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                if self.policy.cleanup_empty_parents:
                    self._cleanup_empty_parents(
                        path.parent,
                        self.adapter.root_for(request.locator).resolve(),
                    )
                self.hooks.after_size_change(request.locator, delta)
                self.hooks.validate_after_mutation(
                    request.locator,
                    operation,
                    [safe_path.relative_path],
                )
            self.hooks.after_mutation(
                request.locator,
                operation,
                [safe_path.relative_path],
            )

        return FileMutationResult(
            path=safe_path.relative_path,
            operation=operation,
            entry_type=entry_type,
            size=0,
        )

    def move_entry(self, request: MoveEntryRequest) -> FileMutationResult:
        return self._copy_or_move(
            operation="move",
            locator=request.locator,
            source_path=request.source_path,
            dest_path=request.dest_path,
            overwrite=False,
            source_locator=request.source_locator,
            dest_locator=request.dest_locator,
        )

    def copy_entry(self, request: CopyEntryRequest) -> FileMutationResult:
        return self._copy_or_move(
            operation="copy",
            locator=request.locator,
            source_path=request.source_path,
            dest_path=request.dest_path,
            overwrite=False,
            source_locator=request.source_locator,
            dest_locator=request.dest_locator,
        )

    def preflight_upload_files(
        self, request: UploadFilesRequest
    ) -> FileConflictPreflight:
        target_safe_path = self.adapter.resolve_path(
            request.locator, request.target_path
        )
        self.adapter.can_write(
            request.locator, target_safe_path.relative_path, "upload"
        )
        entries = tuple((item.filename, "file") for item in request.files)
        return self._preflight_target_entries(
            locator=request.locator,
            target_path=target_safe_path.relative_path,
            entries=entries,
        )

    def preflight_upload_streams(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        files: Sequence[UploadStreamItem],
    ) -> FileConflictPreflight:
        target_safe_path = self.adapter.resolve_path(locator, target_path)
        self.adapter.can_write(locator, target_safe_path.relative_path, "upload")
        return self._preflight_target_entries(
            locator=locator,
            target_path=target_safe_path.relative_path,
            entries=tuple((item.filename, "file") for item in files),
        )

    def preflight_copy_entries(
        self, request: CopyEntriesRequest
    ) -> FileConflictPreflight:
        source_locator = request.source_locator or request.locator
        dest_locator = request.dest_locator or request.locator
        target_safe_path = self.adapter.resolve_path(dest_locator, request.target_path)
        self.adapter.can_write(dest_locator, target_safe_path.relative_path, "copy")
        entries: list[tuple[str, str]] = []
        for source_path in request.source_paths:
            self.adapter.can_read(source_locator, source_path)
            source_safe_path = self.adapter.resolve_path(source_locator, source_path)
            source = source_safe_path.absolute_path
            if not source.exists():
                raise FileCoreError(
                    "FILE_NOT_FOUND",
                    f"Path not found: {source_path}",
                    {"path": source_path},
                    404,
                )
            entries.append(
                (source_safe_path.relative_path, "directory" if source.is_dir() else "file")
            )
        return self._preflight_target_entries(
            locator=dest_locator,
            target_path=target_safe_path.relative_path,
            entries=entries,
        )

    def copy_entries(self, request: CopyEntriesRequest) -> UploadBatchResult:
        operation = "copy"
        self._validate_conflict_strategy(request.default_strategy)
        resolution_map = self._resolution_map(request.resolutions)
        source_locator = request.source_locator or request.locator
        dest_locator = request.dest_locator or request.locator
        target_safe_path = self.adapter.resolve_path(dest_locator, request.target_path)
        self.adapter.can_write(dest_locator, target_safe_path.relative_path, operation)
        parent_lock_key = self.adapter.lock_key_for(
            dest_locator, target_safe_path.relative_path, operation
        )

        with self.write_locks.lock(parent_lock_key):
            plan: list[tuple[str, str, str, str]] = []
            planned_paths: dict[str, str] = {}
            cancelled = False
            self._validate_unique_sources(request.source_paths)
            for source_path in request.source_paths:
                self.adapter.can_read(source_locator, source_path)
                source_safe_path = self.adapter.resolve_path(source_locator, source_path)
                source = source_safe_path.absolute_path
                if not source.exists():
                    raise FileCoreError(
                        "FILE_NOT_FOUND",
                        f"Path not found: {source_path}",
                        {"path": source_path},
                        404,
                    )
                source_type = "directory" if source.is_dir() else "file"
                desired_path = self._join_path(
                    target_safe_path.relative_path, source.name
                )
                final_path, status = self._plan_conflict_destination(
                    locator=dest_locator,
                    source_path=source_safe_path.relative_path,
                    desired_path=desired_path,
                    source_type=source_type,
                    strategy=resolution_map.get(
                        source_safe_path.relative_path, request.default_strategy
                    ),
                    planned_paths=planned_paths,
                )
                cancelled = cancelled or status == "cancelled"
                plan.append((source_safe_path.relative_path, final_path, source_type, status))

            if cancelled:
                return self._cancelled_batch(tuple(path for path, _, _, _ in plan))

            results: list[UploadItemResult] = []
            for source_path, final_path, source_type, status in plan:
                if status == "skipped":
                    results.append(
                        UploadItemResult(
                            source_path=source_path,
                            final_path=None,
                            status="skipped",
                            size=0,
                            entry_type=source_type,
                        )
                    )
                    continue
                try:
                    if status == "merged":
                        result = self._merge_copy_directory(
                            locator=request.locator,
                            source_locator=source_locator,
                            dest_locator=dest_locator,
                            source_path=source_path,
                            dest_path=final_path,
                        )
                    else:
                        result = self._copy_or_move(
                            operation=operation,
                            locator=request.locator,
                            source_path=source_path,
                            dest_path=final_path,
                            overwrite=status == "replaced",
                            source_locator=source_locator,
                            dest_locator=dest_locator,
                        )
                    results.append(
                        UploadItemResult(
                            source_path=source_path,
                            final_path=result.path,
                            status=status,
                            size=result.size,
                            updated_at=result.updated_at,
                            entry_type=result.entry_type,
                        )
                    )
                except Exception as exc:
                    results.append(
                        UploadItemResult(
                            source_path=source_path,
                            final_path=None,
                            status="failed",
                            size=0,
                            error=str(exc),
                            entry_type=source_type,
                        )
                    )
            return self._file_transfer_result(results)

    def upload_files(self, request: UploadFilesRequest) -> UploadBatchResult:
        operation = "upload"
        self._validate_conflict_strategy(request.default_strategy)
        resolution_map = self._resolution_map(request.resolutions)
        if len(request.files) > self.policy.max_upload_files:
            raise FileCoreError(
                "UPLOAD_LIMIT_EXCEEDED",
                "Upload file count exceeds limit",
                {
                    "fileCount": len(request.files),
                    "maxFileCount": self.policy.max_upload_files,
                },
                400,
            )

        target_safe_path = self.adapter.resolve_path(
            request.locator, request.target_path
        )
        self.adapter.can_write(
            request.locator, target_safe_path.relative_path, operation
        )
        parent_lock_key = self.adapter.lock_key_for(
            request.locator, target_safe_path.relative_path, operation
        )
        with self.write_locks.lock(parent_lock_key):
            planned_paths: dict[str, str] = {}
            plan: list[tuple[UploadItem, str, str]] = []
            cancelled = False
            self._validate_unique_sources(tuple(item.filename for item in request.files))
            for item in request.files:
                if not item.filename:
                    raise FileCoreError(
                        "INVALID_FILENAME",
                        "Filename is required",
                        {"filename": item.filename},
                        400,
                    )
                filename = Path(item.filename).name
                desired_path = self._join_path(target_safe_path.relative_path, filename)
                final_path, status = self._plan_conflict_destination(
                    locator=request.locator,
                    source_path=item.filename,
                    desired_path=desired_path,
                    source_type="file",
                    strategy=resolution_map.get(item.filename, request.default_strategy),
                    planned_paths=planned_paths,
                )
                cancelled = cancelled or status == "cancelled"
                plan.append((item, final_path, status))

            if cancelled:
                return self._cancelled_batch(tuple(item.filename for item, _, _ in plan))

            results: list[UploadItemResult] = []
            for item, final_path, status in plan:
                if status == "skipped":
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=None,
                            status="skipped",
                            size=0,
                        )
                    )
                    continue
                try:
                    result = self._write_bytes_mutation(
                        locator=request.locator,
                        relative_path=final_path,
                        content=item.content,
                        operation=operation,
                    )
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=result.path,
                            status=status,
                            size=result.size,
                            updated_at=result.updated_at,
                            entry_type=result.entry_type,
                        )
                    )
                except Exception as exc:
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=None,
                            status="failed",
                            size=0,
                            error=str(exc),
                        )
                    )
            return self._file_transfer_result(results)

    def upload_streams(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        files: Sequence[UploadStreamItem],
        default_strategy: str = "cancel",
        resolutions: Sequence[FileConflictResolution] = (),
    ) -> UploadBatchResult:
        operation = "upload"
        self._validate_conflict_strategy(default_strategy)
        resolution_map = self._resolution_map(resolutions)
        if len(files) > self.policy.max_upload_files:
            raise FileCoreError(
                "UPLOAD_LIMIT_EXCEEDED",
                "Upload file count exceeds limit",
                {
                    "fileCount": len(files),
                    "maxFileCount": self.policy.max_upload_files,
                },
                400,
            )

        target_safe_path = self.adapter.resolve_path(locator, target_path)
        self.adapter.can_write(locator, target_safe_path.relative_path, operation)
        parent_lock_key = self.adapter.lock_key_for(
            locator, target_safe_path.relative_path, operation
        )
        with self.write_locks.lock(parent_lock_key):
            planned_paths: dict[str, str] = {}
            plan: list[tuple[UploadStreamItem, str, str]] = []
            cancelled = False
            self._validate_unique_sources(tuple(item.filename for item in files))
            for item in files:
                if not item.filename:
                    raise FileCoreError(
                        "INVALID_FILENAME",
                        "Filename is required",
                        {"filename": item.filename},
                        400,
                    )
                filename = Path(item.filename).name
                desired_path = self._join_path(target_safe_path.relative_path, filename)
                final_path, status = self._plan_conflict_destination(
                    locator=locator,
                    source_path=item.filename,
                    desired_path=desired_path,
                    source_type="file",
                    strategy=resolution_map.get(item.filename, default_strategy),
                    planned_paths=planned_paths,
                )
                cancelled = cancelled or status == "cancelled"
                plan.append((item, final_path, status))

            if cancelled:
                return self._cancelled_batch(tuple(item.filename for item, _, _ in plan))

            results: list[UploadItemResult] = []
            for item, final_path, status in plan:
                if status == "skipped":
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=None,
                            status="skipped",
                            size=0,
                        )
                    )
                    continue
                try:
                    item.stream.seek(0)
                    result = self._write_stream_mutation(
                        locator=locator,
                        relative_path=final_path,
                        source=item.stream,
                        size=item.size,
                        operation=operation,
                    )
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=result.path,
                            status=status,
                            size=result.size,
                            updated_at=result.updated_at,
                            entry_type=result.entry_type,
                        )
                    )
                except Exception as exc:
                    results.append(
                        UploadItemResult(
                            source_path=item.filename,
                            final_path=None,
                            status="failed",
                            size=0,
                            error=str(exc),
                        )
                    )
            return self._file_transfer_result(results)

    def extract_archive(self, request: ExtractArchiveRequest) -> UploadBatchResult:
        return self._extract_archive_content(
            locator=request.locator,
            target_path=request.target_path,
            archive_name=request.archive_name,
            archive_stream=BytesIO(request.archive_bytes),
            archive_size=len(request.archive_bytes),
            default_strategy=request.default_strategy,
            resolutions=request.resolutions,
        )

    def preflight_extract_archive(
        self, request: ExtractArchiveRequest
    ) -> FileConflictPreflight:
        return self._preflight_archive_content(
            locator=request.locator,
            target_path=request.target_path,
            archive_name=request.archive_name,
            archive_stream=BytesIO(request.archive_bytes),
        )

    def extract_archive_stream(
        self,
        request: ExtractArchiveStreamRequest,
    ) -> UploadBatchResult:
        return self._extract_archive_content(
            locator=request.locator,
            target_path=request.target_path,
            archive_name=request.archive_name,
            archive_stream=request.archive_stream,
            archive_size=request.archive_size,
            default_strategy=request.default_strategy,
            resolutions=request.resolutions,
        )

    def _preflight_archive_content(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        archive_name: str,
        archive_stream: BinaryIO,
    ) -> FileConflictPreflight:
        target_safe_path = self.adapter.resolve_path(locator, target_path)
        self.adapter.can_write(locator, target_safe_path.relative_path, "extract")
        entries = self._validated_archive_entries(archive_stream, archive_name)
        return self._preflight_relative_target_entries(
            locator=locator,
            target_path=target_safe_path.relative_path,
            entries=tuple((source, relative, "file") for source, relative, _ in entries),
        )

    def _extract_archive_content(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        archive_name: str,
        archive_stream: BinaryIO,
        archive_size: int,
        default_strategy: str,
        resolutions: Sequence[FileConflictResolution],
    ) -> UploadBatchResult:
        operation = "extract"
        self._validate_conflict_strategy(default_strategy)
        resolution_map = self._resolution_map(resolutions)
        if archive_size > self.policy.max_write_bytes:
            raise FileCoreError(
                "FILE_TOO_LARGE",
                f"File too large: {archive_name}",
                {"path": archive_name, "size": archive_size, "limit": self.policy.max_write_bytes},
                413,
            )
        target_safe_path = self.adapter.resolve_path(locator, target_path)
        self.adapter.can_write(locator, target_safe_path.relative_path, operation)
        entries = self._validated_archive_entries(archive_stream, archive_name)
        parent_lock_key = self.adapter.lock_key_for(
            locator, target_safe_path.relative_path, operation
        )
        with self.write_locks.lock(parent_lock_key):
            planned_paths: dict[str, str] = {}
            plan: list[tuple[str, str, int, str]] = []
            cancelled = False
            self._validate_unique_sources(tuple(source for source, _, _ in entries))
            for source_path, relative_path, size in entries:
                desired_path = self._join_path(
                    target_safe_path.relative_path, relative_path
                )
                final_path, status = self._plan_conflict_destination(
                    locator=locator,
                    source_path=source_path,
                    desired_path=desired_path,
                    source_type="file",
                    strategy=resolution_map.get(source_path, default_strategy),
                    planned_paths=planned_paths,
                )
                cancelled = cancelled or status == "cancelled"
                plan.append((source_path, final_path, size, status))
            if cancelled:
                return self._cancelled_batch(
                    tuple(source for source, _, _, _ in plan)
                )

            results: list[UploadItemResult] = []
            archive_stream.seek(0)
            with zipfile.ZipFile(archive_stream) as archive:
                for source_path, final_path, size, status in plan:
                    if status == "skipped":
                        results.append(
                            UploadItemResult(
                                source_path=source_path,
                                final_path=None,
                                status="skipped",
                                size=0,
                            )
                        )
                        continue
                    try:
                        with archive.open(source_path, "r") as source:
                            result = self._write_stream_mutation(
                                locator=locator,
                                relative_path=final_path,
                                source=source,
                                size=size,
                                operation=operation,
                            )
                        results.append(
                            UploadItemResult(
                                source_path=source_path,
                                final_path=result.path,
                                status=status,
                                size=result.size,
                                updated_at=result.updated_at,
                                entry_type=result.entry_type,
                            )
                        )
                    except Exception as exc:
                        results.append(
                            UploadItemResult(
                                source_path=source_path,
                                final_path=None,
                                status="failed",
                                size=0,
                                error=str(exc),
                            )
                        )
        return self._file_transfer_result(results)

    def _validated_archive_entries(
        self, archive_stream: BinaryIO, archive_name: str
    ) -> list[tuple[str, str, int]]:
        try:
            archive_stream.seek(0)
            archive = zipfile.ZipFile(archive_stream)
        except (OSError, zipfile.BadZipFile) as exc:
            raise FileCoreError(
                "INVALID_ARCHIVE",
                f"Invalid ZIP archive: {archive_name}",
                {"filename": archive_name},
                400,
            ) from exc
        entries: list[tuple[str, str, int]] = []
        total_size = 0
        with archive:
            infos = archive.infolist()
            if len(infos) > self.policy.max_extract_entries:
                raise FileCoreError(
                    "ARCHIVE_LIMIT_EXCEEDED",
                    "Archive entry count exceeds limit",
                    {
                        "filename": archive_name,
                        "entryCount": len(infos),
                        "maxEntryCount": self.policy.max_extract_entries,
                    },
                    400,
                )
            for info in infos:
                if info.is_dir():
                    self._normalize_archive_entry(info.filename.rstrip("/"))
                    continue
                normalized_entry = self._normalize_archive_entry(info.filename)
                if info.file_size > self.policy.max_extract_entry_bytes:
                    raise FileCoreError(
                        "ARCHIVE_LIMIT_EXCEEDED",
                        "Archive entry size exceeds limit",
                        {
                            "filename": archive_name,
                            "entry": info.filename,
                            "entrySize": info.file_size,
                            "maxEntrySize": self.policy.max_extract_entry_bytes,
                        },
                        400,
                    )
                total_size += info.file_size
                if total_size > self.policy.max_extract_total_bytes:
                    raise FileCoreError(
                        "ARCHIVE_LIMIT_EXCEEDED",
                        "Archive total extracted size exceeds limit",
                        {
                            "filename": archive_name,
                            "totalSize": total_size,
                            "maxTotalSize": self.policy.max_extract_total_bytes,
                        },
                        400,
                    )
                entries.append((info.filename, normalized_entry, info.file_size))
        return entries

    def build_archive(self, request: BuildArchiveRequest) -> ArchiveBuildResult:
        archive_policy = self.policy.archive_policy
        if archive_policy is None:
            raise FileCoreError(
                "CONFIGURATION_ERROR",
                "Archive policy is not configured",
                {},
                500,
            )
        if len(request.paths) > archive_policy.max_selected_roots:
            raise FileCoreError(
                "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
                "Archive selected root count exceeds limit",
                {
                    "selectedRootCount": len(request.paths),
                    "maxSelectedRootCount": archive_policy.max_selected_roots,
                },
                400,
            )

        root_path = self.adapter.root_for(request.locator).resolve()
        resolved_roots: list[Path] = []
        selected_paths: list[str] = []
        seen_roots: set[str] = set()

        for raw_path in request.paths:
            self.adapter.can_read(request.locator, raw_path)
            safe_path = self.adapter.resolve_path(request.locator, raw_path)
            unresolved_path = safe_path.root / safe_path.relative_path
            if request.reject_symlinks and unresolved_path.is_symlink():
                raise FileCoreError(
                    "SYMLINK_REJECTED",
                    f"Symlink rejected: {unresolved_path}",
                    {"path": safe_path.relative_path},
                    400,
                )
            fs_path = safe_path.absolute_path
            if not fs_path.exists():
                raise FileCoreError(
                    "FILE_NOT_FOUND",
                    f"Path not found: {raw_path}",
                    {"path": raw_path},
                    404,
                )
            key = str(fs_path.resolve())
            if key in seen_roots:
                continue
            seen_roots.add(key)
            resolved_roots.append(fs_path)
            selected_paths.append(safe_path.relative_path)

        selected_roots = self._remove_redundant_roots(resolved_roots)
        if not selected_roots:
            return ArchiveBuildResult(
                entries=(), selected_paths=selected_paths, total_size=0
            )
        base_path = self._common_archive_base(selected_roots)
        entries: list[ArchiveEntry] = []
        seen_entries: set[str] = set()
        total_size = 0

        for root in selected_roots:
            if root.is_symlink():
                if request.reject_symlinks:
                    raise FileCoreError(
                        "SYMLINK_REJECTED",
                        f"Symlink rejected: {root}",
                        {"path": self.adapter.canonical_path(request.locator, root)},
                        400,
                    )
                continue
            candidates: list[Path]
            if root.is_file():
                candidates = [root]
            elif root.is_dir():
                candidates = []
                for current_dir, dirnames, filenames in os.walk(
                    root, followlinks=False
                ):
                    current_path = Path(current_dir)
                    dirnames[:] = [
                        dirname
                        for dirname in dirnames
                        if not self._archive_should_skip_symlink_directory(
                            current_path / dirname,
                            request,
                        )
                        and not self.policy.path_exclusion.is_excluded(
                            (current_path / dirname).relative_to(root_path)
                        )
                    ]
                    for filename in filenames:
                        candidate = current_path / filename
                        if self.policy.path_exclusion.is_excluded(
                            candidate.relative_to(root_path)
                        ):
                            continue
                        candidates.append(candidate)
            else:
                continue

            for candidate in candidates:
                if candidate.is_symlink():
                    if request.reject_symlinks:
                        raise FileCoreError(
                            "SYMLINK_REJECTED",
                            f"Symlink rejected: {candidate}",
                            {
                                "path": self.adapter.canonical_path(
                                    request.locator, candidate
                                )
                            },
                            400,
                        )
                    continue
                if not candidate.is_file():
                    continue
                resolved_candidate = candidate.resolve()
                try:
                    resolved_candidate.relative_to(root_path)
                except ValueError as exc:
                    raise FileCoreError(
                        "PATH_OUTSIDE_ROOT",
                        f"Path escapes root: {candidate}",
                        {"path": str(candidate)},
                        400,
                    ) from exc
                stat = resolved_candidate.stat()
                total_size += stat.st_size
                if len(entries) + 1 > archive_policy.max_entries:
                    raise FileCoreError(
                        "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
                        "Archive file entry count exceeds limit",
                        {
                            "entryCount": len(entries) + 1,
                            "maxEntryCount": archive_policy.max_entries,
                        },
                        400,
                    )
                if total_size > archive_policy.max_total_bytes:
                    raise FileCoreError(
                        "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
                        "Archive total size exceeds limit",
                        {
                            "totalSize": total_size,
                            "maxTotalSize": archive_policy.max_total_bytes,
                        },
                        400,
                    )
                archive_path = self._zip_entry_name(
                    resolved_candidate,
                    base_path,
                    archive_root=request.archive_root,
                )
                if archive_path in seen_entries:
                    continue
                seen_entries.add(archive_path)
                entries.append(
                    ArchiveEntry(
                        fs_path=str(resolved_candidate),
                        archive_path=archive_path,
                        size=stat.st_size,
                    )
                )

        return ArchiveBuildResult(
            entries=entries,
            selected_paths=selected_paths,
            total_size=total_size,
        )

    def build_archive_bytes(self, request: BuildArchiveRequest) -> ArchiveBytesResult:
        plan = self.build_archive(request)
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for extra_entry in request.extra_entries:
                archive.writestr(
                    self._normalize_zip_output_path(extra_entry.archive_path),
                    extra_entry.content,
                )
            for entry in plan.entries:
                archive.write(entry.fs_path, entry.archive_path)
        return ArchiveBytesResult(
            content=buffer.getvalue(),
            entries=plan.entries,
            selected_paths=plan.selected_paths,
            total_size=plan.total_size
            + sum(len(entry.content) for entry in request.extra_entries),
        )

    def search(self, request: SearchRequest) -> SearchResult:
        query = request.query if request.case_sensitive else request.query.lower()
        if not query:
            return SearchResult(matches=(), total=0)
        max_results = request.max_results or self.policy.max_search_results
        self.adapter.can_read(request.locator, request.path)
        safe_path = self.adapter.resolve_path(request.locator, request.path)
        root = safe_path.absolute_path
        if not root.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"Path not found: {request.path}",
                {"path": request.path},
                404,
            )

        candidates = [root] if root.is_file() else self._iter_search_files(root)
        matches: list[SearchMatch] = []
        for candidate in candidates:
            if len(matches) >= max_results:
                break
            relative_path = self.adapter.canonical_path(request.locator, candidate)
            relative_obj = Path(relative_path)
            if self.policy.path_exclusion.is_excluded(relative_obj):
                continue
            stat = candidate.stat()
            candidate_name = (
                candidate.name if request.case_sensitive else candidate.name.lower()
            )
            if query in candidate_name:
                matches.append(
                    SearchMatch(
                        path=relative_path,
                        name=candidate.name,
                        entry_type="file",
                        size=stat.st_size,
                        updated_at=iso_from_timestamp(stat.st_mtime),
                        match_type="name",
                    )
                )
                continue
            if (
                not request.include_content
                or stat.st_size > self.policy.max_search_file_bytes
            ):
                continue
            content_match = self._search_file_content(
                candidate, query, request.case_sensitive
            )
            if content_match is None:
                continue
            line_number, preview = content_match
            matches.append(
                SearchMatch(
                    path=relative_path,
                    name=candidate.name,
                    entry_type="file",
                    size=stat.st_size,
                    updated_at=iso_from_timestamp(stat.st_mtime),
                    match_type="content",
                    line=line_number,
                    preview=preview,
                )
            )

        return SearchResult(matches=matches, total=len(matches))

    def batch_delete(self, request: BatchDeleteRequest) -> BatchMutationResult:
        results: list[BatchItemResult] = []
        for path in request.paths:
            try:
                self.delete_entry(
                    DeleteEntryRequest(
                        locator=request.locator,
                        path=path,
                        recursive=request.recursive,
                    )
                )
                results.append(BatchItemResult(path=path, status="success"))
            except Exception as exc:
                results.append(
                    BatchItemResult(path=path, status="failed", error=str(exc))
                )
        return self._batch_result(results)

    def batch_write(self, request: BatchWriteRequest) -> BatchMutationResult:
        results: list[BatchItemResult] = []
        for item in request.files:
            try:
                result = self.write_text(
                    WriteTextRequest(
                        locator=request.locator,
                        path=item.path,
                        content=item.content,
                        expected_version_id=item.expected_version_id,
                        encoding=item.encoding,
                    )
                )
                results.append(
                    BatchItemResult(
                        path=item.path,
                        status="success",
                        size=result.size,
                    )
                )
            except Exception as exc:
                results.append(
                    BatchItemResult(path=item.path, status="failed", error=str(exc))
                )
        return self._batch_result(results)

    def sync_tree(self, request: SyncTreeRequest) -> BatchMutationResult:
        operation = "sync"
        requested_paths: set[str] = set()
        results: list[BatchItemResult] = []
        planned_writes: list[tuple[str, Path, bytes]] = []
        planned_deletes: list[tuple[str, Path]] = []
        changed_paths: list[str] = []
        total_delta = 0

        for item in request.files:
            try:
                if len(item.content) > self.policy.max_write_bytes:
                    raise FileCoreError(
                        "FILE_TOO_LARGE",
                        f"File too large: {item.path}",
                        {
                            "path": item.path,
                            "size": len(item.content),
                            "limit": self.policy.max_write_bytes,
                        },
                        413,
                    )
                self.adapter.can_write(request.locator, item.path, operation)
                safe_path = self.adapter.resolve_path(request.locator, item.path)
                path = safe_path.absolute_path
                if path.exists() and path.is_dir():
                    raise FileCoreError(
                        "NOT_A_FILE",
                        f"Not a file: {item.path}",
                        {"path": item.path},
                        400,
                    )
                previous_size = (
                    path.stat().st_size if path.exists() and path.is_file() else 0
                )
                total_delta += len(item.content) - previous_size
                requested_paths.add(path.resolve().as_posix())
                planned_writes.append((safe_path.relative_path, path, item.content))
                changed_paths.append(safe_path.relative_path)
            except Exception as exc:
                results.append(
                    BatchItemResult(path=item.path, status="failed", error=str(exc))
                )

        if results:
            return self._batch_result(results)

        if request.delete_missing:
            root = self.adapter.root_for(request.locator).resolve()
            for path in sorted(
                (item for item in root.rglob("*") if item.is_file()),
                reverse=True,
            ):
                relative_path = path.relative_to(root).as_posix()
                try:
                    self.adapter.resolve_path(request.locator, relative_path)
                except FileCoreError:
                    continue
                if path.resolve().as_posix() in requested_paths:
                    continue
                try:
                    self.adapter.can_write(request.locator, relative_path, operation)
                    total_delta -= path.stat().st_size
                    planned_deletes.append((relative_path, path))
                    changed_paths.append(relative_path)
                except Exception as exc:
                    results.append(
                        BatchItemResult(
                            path=relative_path,
                            status="failed",
                            error=str(exc),
                        )
                    )

        if results:
            return self._batch_result(results)

        lock_key = self.adapter.lock_key_for(request.locator, ".", operation)
        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(request.locator, operation):
                self.hooks.check_quota(request.locator, total_delta)
                for relative_path, path, _content in planned_writes:
                    if path.exists() and path.is_file():
                        self.hooks.snapshot_existing(
                            request.locator,
                            path,
                            relative_path,
                            operation,
                        )
                for relative_path, path in planned_deletes:
                    self.hooks.snapshot_existing(
                        request.locator,
                        path,
                        relative_path,
                        operation,
                    )
                for relative_path, path, content in planned_writes:
                    self._ensure_parent_directory(path, relative_path)
                    path.write_bytes(content)
                    results.append(
                        BatchItemResult(
                            path=relative_path,
                            status="success",
                            size=len(content),
                        )
                    )
                for relative_path, path in planned_deletes:
                    path.unlink()
                    results.append(BatchItemResult(path=relative_path, status="success"))
                if request.delete_missing:
                    root = self.adapter.root_for(request.locator).resolve()
                    for path in sorted(
                        (item for item in root.rglob("*") if item.is_dir()),
                        reverse=True,
                    ):
                        relative_path = path.relative_to(root).as_posix()
                        try:
                            self.adapter.resolve_path(request.locator, relative_path)
                        except FileCoreError:
                            continue
                        try:
                            path.rmdir()
                        except OSError:
                            continue
                self.hooks.after_size_change(request.locator, total_delta)
                self.hooks.validate_after_mutation(
                    request.locator,
                    operation,
                    changed_paths,
                )
            self.hooks.after_mutation(request.locator, operation, changed_paths)

        return self._batch_result(results)

    def _copy_or_move(
        self,
        *,
        operation: str,
        locator: FileLocator,
        source_path: str,
        dest_path: str,
        overwrite: bool,
        source_locator: Optional[FileLocator] = None,
        dest_locator: Optional[FileLocator] = None,
    ) -> FileMutationResult:
        source_locator = source_locator or locator
        dest_locator = dest_locator or locator
        if operation == "copy":
            self.adapter.can_read(source_locator, source_path)
        else:
            self.adapter.can_write(source_locator, source_path, operation)
        self.adapter.can_write(dest_locator, dest_path, operation)
        source_raw_path = self._raw_path_for(source_locator, source_path)
        dest_raw_path = self._raw_path_for(dest_locator, dest_path)
        self._ensure_no_symlink_tree(source_raw_path, source_path)
        if dest_raw_path.exists():
            self._ensure_no_symlink_tree(dest_raw_path, dest_path)
        source_safe_path = self.adapter.resolve_path(source_locator, source_path)
        dest_safe_path = self.adapter.resolve_path(dest_locator, dest_path)
        source = source_safe_path.absolute_path
        dest = dest_safe_path.absolute_path

        if not source.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"Path not found: {source_path}",
                {"path": source_path},
                404,
            )
        if (
            dest.exists()
            and dest.is_dir()
            and self.policy.directory_destination_mode == "append-source-name"
        ):
            dest_path = f"{dest_safe_path.relative_path.rstrip('/')}/{source.name}"
            self.adapter.can_write(dest_locator, dest_path, operation)
            dest_raw_path = self._raw_path_for(dest_locator, dest_path)
            if dest_raw_path.exists():
                self._ensure_no_symlink_tree(dest_raw_path, dest_path)
            dest_safe_path = self.adapter.resolve_path(dest_locator, dest_path)
            dest = dest_safe_path.absolute_path
        if dest.exists() and not overwrite:
            raise FileCoreError(
                "FILE_ALREADY_EXISTS",
                f"Path already exists: {dest_path}",
                {"path": dest_path},
                409,
            )
        self._reject_unsafe_copy_or_move_paths(
            source,
            dest,
            source_path=source_path,
            dest_path=dest_path,
        )

        entry_type = "directory" if source.is_dir() else "file"
        source_size = self._calculate_size(source)
        replaced_size = self._calculate_size(dest) if dest.exists() else 0
        delta = source_size - replaced_size if operation == "copy" else -replaced_size
        source_lock_key = self.adapter.lock_key_for(
            source_locator,
            source_safe_path.relative_path,
            operation,
        )
        dest_lock_key = self.adapter.lock_key_for(
            dest_locator,
            dest_safe_path.relative_path,
            operation,
        )

        with ExitStack() as lock_stack:
            for lock_key in sorted(
                {source_lock_key, dest_lock_key},
                key=lambda key: repr(key),
            ):
                lock_stack.enter_context(self.write_locks.lock(lock_key))
            with self.hooks.write_barrier(locator, operation):
                self.hooks.check_quota(locator, delta)
                self._snapshot_existing_paths(
                    dest_locator,
                    dest,
                    dest_safe_path.relative_path,
                    operation,
                )
                if operation == "move":
                    self._snapshot_existing_paths(
                        source_locator,
                        source,
                        source_safe_path.relative_path,
                        operation,
                    )
                self._ensure_parent_directory(dest, dest_path)
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                if operation == "copy":
                    self._copy_path(
                        source,
                        dest,
                        preserve_metadata=self.policy.preserve_copy_metadata,
                    )
                else:
                    source_parent = source.parent
                    self._move_path(
                        source,
                        dest,
                        preserve_metadata=self.policy.preserve_copy_metadata,
                    )
                    if self.policy.cleanup_empty_parents:
                        self._cleanup_empty_parents(
                            source_parent,
                            self.adapter.root_for(source_locator).resolve(),
                        )
                dest_size = self._calculate_size(dest)
                self.hooks.after_size_change(locator, delta)
                self.hooks.validate_after_mutation(
                    locator,
                    operation,
                    [source_safe_path.relative_path, dest_safe_path.relative_path],
                )
            self.hooks.after_mutation(
                locator,
                operation,
                [source_safe_path.relative_path, dest_safe_path.relative_path],
            )

        return FileMutationResult(
            path=dest_safe_path.relative_path,
            operation=operation,
            entry_type=entry_type,
            size=dest_size,
            updated_at=iso_from_timestamp(dest.stat().st_mtime),
            metadata={"sourcePath": source_safe_path.relative_path},
        )

    def _calculate_size(self, path: Path) -> int:
        if path.is_file():
            return path.stat().st_size
        if path.is_dir():
            return sum(self._calculate_size(child) for child in path.iterdir())
        return 0

    def _write_bytes_mutation(
        self,
        *,
        locator: FileLocator,
        relative_path: str,
        content: bytes,
        operation: str,
        expected_version_id: str | None = None,
    ) -> FileMutationResult:
        if len(content) > self.policy.max_write_bytes:
            raise FileCoreError(
                "FILE_TOO_LARGE",
                f"File too large: {relative_path}",
                {
                    "path": relative_path,
                    "size": len(content),
                    "limit": self.policy.max_write_bytes,
                },
                413,
            )
        self.adapter.can_write(locator, relative_path, operation)
        safe_path = self.adapter.resolve_path(locator, relative_path)
        path = safe_path.absolute_path
        if path.exists() and path.is_dir():
            raise FileCoreError(
                "NOT_A_FILE",
                f"Not a file: {relative_path}",
                {"path": relative_path},
                400,
            )
        lock_key = self.adapter.lock_key_for(
            locator, safe_path.relative_path, operation
        )

        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(locator, operation):
                if path.exists() and path.is_dir():
                    raise FileCoreError(
                        "NOT_A_FILE",
                        f"Not a file: {relative_path}",
                        {"path": relative_path},
                        400,
                    )
                previous_size = (
                    path.stat().st_size if path.exists() and path.is_file() else 0
                )
                if path.exists() and expected_version_id is not None:
                    actual_version = self.policy.version_strategy.read_version(path)
                    if actual_version != expected_version_id:
                        raise VersionConflictError(
                            safe_path.relative_path,
                            expected_version_id,
                            actual_version,
                        )
                delta = len(content) - previous_size
                self.hooks.check_quota(locator, delta)
                if path.exists() and path.is_file():
                    self.hooks.snapshot_existing(
                        locator,
                        path,
                        safe_path.relative_path,
                        operation,
                    )
                self._ensure_parent_directory(path, relative_path)
                path.write_bytes(content)
                self.hooks.after_size_change(locator, delta)
                self.hooks.validate_after_mutation(
                    locator,
                    operation,
                    [safe_path.relative_path],
                )
                result = FileMutationResult(
                    path=safe_path.relative_path,
                    operation=operation,
                    entry_type="file",
                    size=len(content),
                    version_id=self.policy.version_strategy.read_version(path),
                    updated_at=iso_from_timestamp(path.stat().st_mtime),
                )
            self.hooks.after_mutation(locator, operation, [safe_path.relative_path])

        return result

    def _write_stream_mutation(
        self,
        *,
        locator: FileLocator,
        relative_path: str,
        source: BinaryIO,
        size: int,
        operation: str,
        expected_version_id: str | None = None,
    ) -> FileMutationResult:
        if size < 0 or size > self.policy.max_write_bytes:
            raise FileCoreError(
                "FILE_TOO_LARGE",
                f"File too large: {relative_path}",
                {
                    "path": relative_path,
                    "size": size,
                    "limit": self.policy.max_write_bytes,
                },
                413,
            )
        self.adapter.can_write(locator, relative_path, operation)
        safe_path = self.adapter.resolve_path(locator, relative_path)
        path = safe_path.absolute_path
        if path.exists() and path.is_dir():
            raise FileCoreError(
                "NOT_A_FILE",
                f"Not a file: {relative_path}",
                {"path": relative_path},
                400,
            )
        lock_key = self.adapter.lock_key_for(
            locator, safe_path.relative_path, operation
        )

        with self.write_locks.lock(lock_key):
            with self.hooks.write_barrier(locator, operation):
                if path.exists() and path.is_dir():
                    raise FileCoreError(
                        "NOT_A_FILE",
                        f"Not a file: {relative_path}",
                        {"path": relative_path},
                        400,
                    )
                previous_size = (
                    path.stat().st_size if path.exists() and path.is_file() else 0
                )
                if path.exists() and expected_version_id is not None:
                    actual_version = self.policy.version_strategy.read_version(path)
                    if actual_version != expected_version_id:
                        raise VersionConflictError(
                            safe_path.relative_path,
                            expected_version_id,
                            actual_version,
                        )
                delta = size - previous_size
                self.hooks.check_quota(locator, delta)
                if path.exists() and path.is_file():
                    self.hooks.snapshot_existing(
                        locator,
                        path,
                        safe_path.relative_path,
                        operation,
                    )
                self._ensure_parent_directory(path, relative_path)
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{path.name}.upload-",
                    dir=path.parent,
                )
                temporary_path = Path(temporary_name)
                written = 0
                try:
                    with os.fdopen(descriptor, "wb") as destination:
                        while chunk := source.read(1024 * 1024):
                            written += len(chunk)
                            if written > size or written > self.policy.max_write_bytes:
                                raise FileCoreError(
                                    "INVALID_UPLOAD_SIZE",
                                    f"Upload size mismatch: {relative_path}",
                                    {
                                        "path": relative_path,
                                        "expectedSize": size,
                                        "actualSize": written,
                                    },
                                    400,
                                )
                            destination.write(chunk)
                    if written != size:
                        raise FileCoreError(
                            "INVALID_UPLOAD_SIZE",
                            f"Upload size mismatch: {relative_path}",
                            {
                                "path": relative_path,
                                "expectedSize": size,
                                "actualSize": written,
                            },
                            400,
                        )
                    os.replace(temporary_path, path)
                finally:
                    temporary_path.unlink(missing_ok=True)
                self.hooks.after_size_change(locator, delta)
                self.hooks.validate_after_mutation(
                    locator,
                    operation,
                    [safe_path.relative_path],
                )
                result = FileMutationResult(
                    path=safe_path.relative_path,
                    operation=operation,
                    entry_type="file",
                    size=written,
                    version_id=self.policy.version_strategy.read_version(path),
                    updated_at=iso_from_timestamp(path.stat().st_mtime),
                )
            self.hooks.after_mutation(locator, operation, [safe_path.relative_path])

        return result

    def _preflight_target_entries(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        entries: Sequence[tuple[str, str]],
    ) -> FileConflictPreflight:
        relative_entries: list[tuple[str, str, str]] = []
        for source_path, source_type in entries:
            filename = Path(source_path).name
            if not filename:
                raise FileCoreError(
                    "INVALID_FILENAME", "Filename is required", {"filename": source_path}, 400
                )
            relative_entries.append((source_path, filename, source_type))
        return self._preflight_relative_target_entries(
            locator=locator, target_path=target_path, entries=relative_entries
        )

    def _preflight_relative_target_entries(
        self,
        *,
        locator: FileLocator,
        target_path: str,
        entries: Sequence[tuple[str, str, str]],
    ) -> FileConflictPreflight:
        conflicts: list[FileConflictItem] = []
        planned_paths: dict[str, str] = {}
        self._validate_unique_sources(tuple(source for source, _, _ in entries))
        for source_path, relative_path, source_type in entries:
            target = self._join_path(target_path, relative_path)
            safe_target = self.adapter.resolve_path(locator, target)
            collision = self._find_target_collision(locator, safe_target, planned_paths)
            if collision is not None:
                collision_path, target_type, _ = collision
                conflicts.append(
                    FileConflictItem(
                        source_path=source_path,
                        target_path=collision_path,
                        source_type=source_type,
                        target_type=target_type,
                        can_replace=(
                            collision_path == safe_target.relative_path
                            and source_type == target_type
                        ),
                    )
                )
            self._record_planned_path(locator, safe_target, source_type, planned_paths)
        return FileConflictPreflight(conflicts=conflicts, total=len(entries))

    def _resolution_map(
        self, resolutions: Sequence[FileConflictResolution]
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for resolution in resolutions:
            self._validate_conflict_strategy(resolution.strategy)
            if resolution.source_path in result:
                raise FileCoreError(
                    "DUPLICATE_CONFLICT_RESOLUTION",
                    f"Duplicate conflict resolution: {resolution.source_path}",
                    {"sourcePath": resolution.source_path},
                    400,
                )
            result[resolution.source_path] = resolution.strategy
        return result

    def _validate_unique_sources(self, source_paths: Sequence[str]) -> None:
        seen: set[str] = set()
        for source_path in source_paths:
            if source_path in seen:
                raise FileCoreError(
                    "DUPLICATE_SOURCE_PATH",
                    f"Duplicate source path: {source_path}",
                    {"sourcePath": source_path},
                    400,
                )
            seen.add(source_path)

    def _plan_conflict_destination(
        self,
        *,
        locator: FileLocator,
        source_path: str,
        desired_path: str,
        source_type: str,
        strategy: str,
        planned_paths: dict[str, str],
    ) -> tuple[str, str]:
        self._validate_conflict_strategy(strategy)
        safe_path = self.adapter.resolve_path(locator, desired_path)
        collision = self._find_target_collision(locator, safe_path, planned_paths)
        if collision is None:
            self._record_planned_path(locator, safe_path, source_type, planned_paths)
            return safe_path.relative_path, "created"
        collision_path, target_type, exact = collision
        if strategy == "cancel":
            return safe_path.relative_path, "cancelled"
        if strategy == "skip":
            return safe_path.relative_path, "skipped"
        if strategy == "replace":
            if not exact or source_type != target_type:
                raise FileCoreError(
                    "FILE_TYPE_CONFLICT",
                    f"Cannot replace a different entry type: {desired_path}",
                    {
                        "sourcePath": source_path,
                        "targetPath": collision_path,
                        "sourceType": source_type,
                        "targetType": target_type,
                    },
                    409,
                )
            self._record_planned_path(locator, safe_path, source_type, planned_paths)
            return safe_path.relative_path, (
                "merged" if source_type == "directory" else "replaced"
            )
        if strategy != "keep-both":
            raise FileCoreError(
                "INVALID_CONFLICT_STRATEGY",
                f"Unsupported conflict strategy: {strategy}",
                {"defaultStrategy": strategy},
                400,
            )
        if exact:
            final_path = self._generate_nonconflicting_path(
                locator, safe_path.relative_path, planned_paths
            )
        else:
            replacement_ancestor = self._generate_nonconflicting_path(
                locator, collision_path, planned_paths
            )
            suffix = posixpath.relpath(safe_path.relative_path, collision_path)
            final_path = self._join_path(replacement_ancestor, suffix)
        final_safe_path = self.adapter.resolve_path(locator, final_path)
        self._record_planned_path(locator, final_safe_path, source_type, planned_paths)
        return final_path, "kept-both"

    def _find_target_collision(
        self,
        locator: FileLocator,
        safe_path: SafePath,
        planned_paths: dict[str, str],
    ) -> Optional[tuple[str, str, bool]]:
        key = str(safe_path.absolute_path)
        target_type = planned_paths.get(key)
        if target_type is None and safe_path.absolute_path.exists():
            target_type = "directory" if safe_path.absolute_path.is_dir() else "file"
        if target_type is not None:
            return safe_path.relative_path, target_type, True
        root = self.adapter.root_for(locator).resolve()
        current = safe_path.absolute_path.parent
        while current != root and self._is_relative_to(current, root):
            current_type = planned_paths.get(str(current))
            if current_type is None and current.exists():
                current_type = "directory" if current.is_dir() else "file"
            if current_type == "file":
                return current.relative_to(root).as_posix(), "file", False
            current = current.parent
        return None

    def _record_planned_path(
        self,
        locator: FileLocator,
        safe_path: SafePath,
        source_type: str,
        planned_paths: dict[str, str],
    ) -> None:
        planned_paths[str(safe_path.absolute_path)] = source_type
        root = self.adapter.root_for(locator).resolve()
        current = safe_path.absolute_path.parent
        while current != root and self._is_relative_to(current, root):
            planned_paths.setdefault(str(current), "directory")
            current = current.parent

    def _generate_nonconflicting_path(
        self,
        locator: FileLocator,
        desired_path: str,
        planned_paths: dict[str, str],
    ) -> str:
        directory = posixpath.dirname(desired_path)
        filename = posixpath.basename(desired_path)
        stem, suffix = posixpath.splitext(filename)
        counter = 1
        while True:
            candidate = self._join_path(directory, f"{stem}_{counter}{suffix}")
            safe_candidate = self.adapter.resolve_path(locator, candidate)
            key = str(safe_candidate.absolute_path)
            if key not in planned_paths and not safe_candidate.absolute_path.exists():
                return safe_candidate.relative_path
            counter += 1

    def _validate_conflict_strategy(self, conflict_strategy: str) -> None:
        if conflict_strategy not in {"keep-both", "replace", "skip", "cancel"}:
            raise FileCoreError(
                "INVALID_CONFLICT_STRATEGY",
                f"Unsupported conflict strategy: {conflict_strategy}",
                {"defaultStrategy": conflict_strategy},
                400,
            )

    def _file_transfer_result(
        self, results: Sequence[UploadItemResult]
    ) -> UploadBatchResult:
        succeeded = sum(
            item.status in {"created", "kept-both", "replaced", "merged"}
            for item in results
        )
        skipped = sum(item.status in {"skipped", "cancelled"} for item in results)
        failed = sum(item.status == "failed" for item in results)
        return UploadBatchResult(
            items=results,
            total=len(results),
            succeeded=succeeded,
            skipped=skipped,
            failed=failed,
        )

    def _cancelled_batch(self, source_paths: Sequence[str]) -> UploadBatchResult:
        return self._file_transfer_result(
            tuple(
                UploadItemResult(
                    source_path=source_path,
                    final_path=None,
                    status="cancelled",
                    size=0,
                )
                for source_path in source_paths
            )
        )

    def _normalize_archive_entry(self, entry_name: str) -> str:
        normalized_name = entry_name.replace("\\", "/")
        if normalized_name.startswith("/") or (
            len(normalized_name) >= 2 and normalized_name[1] == ":"
        ):
            raise FileCoreError(
                "INVALID_ARCHIVE_ENTRY",
                f"Archive entry has an absolute path: {entry_name}",
                {"entry": entry_name},
                400,
            )
        normalized_path = posixpath.normpath(normalized_name)
        if (
            normalized_path in {"", ".", ".."}
            or normalized_path.startswith("../")
            or normalized_path.startswith("/")
        ):
            raise FileCoreError(
                "INVALID_ARCHIVE_ENTRY",
                f"Archive entry escapes target path: {entry_name}",
                {"entry": entry_name},
                400,
            )
        return normalized_path

    def _join_path(self, base_path: str, child_path: str) -> str:
        normalized_base = base_path.strip("/")
        normalized_child = child_path.strip("/")
        if not normalized_base:
            return normalized_child
        if not normalized_child:
            return normalized_base
        return f"{normalized_base}/{normalized_child}"

    def _remove_redundant_roots(self, paths: list[Path]) -> list[Path]:
        selected: list[Path] = []
        for path in sorted(paths, key=lambda item: len(item.parts)):
            if any(self._is_relative_to(path, parent) for parent in selected):
                continue
            selected.append(path)
        return selected

    def _is_relative_to(self, path: Path, parent: Path) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False

    def _common_archive_base(self, paths: list[Path]) -> Path:
        parent_paths = [path.parent for path in paths]
        return Path(os.path.commonpath([str(path) for path in parent_paths]))

    def _zip_entry_name(
        self,
        file_path: Path,
        base_path: Path,
        *,
        archive_root: str = "",
    ) -> str:
        entry_name = file_path.relative_to(base_path).as_posix()
        if archive_root:
            entry_name = posixpath.join(archive_root, entry_name)
        return self._normalize_zip_output_path(entry_name)

    def _archive_should_skip_symlink_directory(
        self,
        directory: Path,
        request: BuildArchiveRequest,
    ) -> bool:
        if not directory.is_symlink():
            return False
        if request.reject_symlinks:
            raise FileCoreError(
                "SYMLINK_REJECTED",
                f"Symlink rejected: {directory}",
                {"path": self.adapter.canonical_path(request.locator, directory)},
                400,
            )
        return True

    def _normalize_zip_output_path(self, entry_name: str) -> str:
        normalized = posixpath.normpath(entry_name)
        if (
            normalized in {"", ".", ".."}
            or normalized.startswith("../")
            or normalized.startswith("/")
        ):
            raise FileCoreError(
                "INVALID_ARCHIVE_ENTRY",
                "Invalid archive entry path",
                {"path": entry_name},
                400,
            )
        return normalized

    def _iter_search_files(self, root: Path) -> list[Path]:
        candidates: list[Path] = []
        for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
            current_path = Path(current_dir)
            relative_dir = current_path.relative_to(root)
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not (current_path / dirname).is_symlink()
                and not self.policy.path_exclusion.is_excluded(relative_dir / dirname)
            ]
            for filename in filenames:
                candidate = current_path / filename
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                candidates.append(candidate)
        return candidates

    def _iter_list_files(
        self,
        base_root: Path,
        root: Path,
        include_hidden: bool,
    ) -> list[Path]:
        candidates: list[Path] = []
        for current_dir, dirnames, filenames in os.walk(root, followlinks=False):
            current_path = Path(current_dir)
            relative_dir = current_path.relative_to(base_root)
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not (current_path / dirname).is_symlink()
                and (include_hidden or not dirname.startswith("."))
                and not self.policy.path_exclusion.is_excluded(relative_dir / dirname)
            ]
            for filename in filenames:
                candidate = current_path / filename
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                relative_path = candidate.relative_to(base_root)
                if not include_hidden and filename.startswith("."):
                    continue
                if self.policy.path_exclusion.is_excluded(relative_path):
                    continue
                candidates.append(candidate)
        return sorted(candidates)

    def _search_file_content(
        self,
        path: Path,
        query: str,
        case_sensitive: bool,
    ) -> Optional[tuple[int, str]]:
        try:
            raw = path.read_bytes()
            if self._looks_binary(raw):
                return None
            content = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        for index, line in enumerate(content.splitlines(), start=1):
            haystack = line if case_sensitive else line.lower()
            if query in haystack:
                return index, line.strip()
        return None

    def _batch_result(self, results: list[BatchItemResult]) -> BatchMutationResult:
        succeeded = sum(1 for result in results if result.status == "success")
        return BatchMutationResult(
            results=results,
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
        )

    def _reject_unsafe_copy_or_move_paths(
        self,
        source: Path,
        dest: Path,
        *,
        source_path: str,
        dest_path: str,
    ) -> None:
        resolved_source = source.resolve()
        resolved_dest = dest.resolve()
        if resolved_source == resolved_dest:
            raise FileCoreError(
                "INVALID_OPERATION",
                "Source and destination must be different",
                {"sourcePath": source_path, "destPath": dest_path},
                400,
            )
        if resolved_source in resolved_dest.parents:
            raise FileCoreError(
                "INVALID_OPERATION",
                "Destination cannot be inside source",
                {"sourcePath": source_path, "destPath": dest_path},
                400,
            )
        if dest.exists() and resolved_dest in resolved_source.parents:
            raise FileCoreError(
                "INVALID_OPERATION",
                "Source cannot be inside overwritten destination",
                {"sourcePath": source_path, "destPath": dest_path},
                400,
            )

    def _raw_path_for(self, locator: FileLocator, relative_path: str) -> Path:
        safe_path = self.adapter.resolve_path(locator, relative_path)
        return safe_path.root / safe_path.relative_path

    def _ensure_no_symlink_tree(self, path: Path, requested_path: str) -> None:
        if path.is_symlink():
            raise FileCoreError(
                "UNSUPPORTED_SYMLINK",
                f"Symlink is not supported for this operation: {requested_path}",
                {"path": requested_path},
                400,
            )
        if not path.is_dir():
            return
        for child in path.iterdir():
            child_requested_path = f"{requested_path.rstrip('/')}/{child.name}"
            self._ensure_no_symlink_tree(child, child_requested_path)

    def _snapshot_existing_paths(
        self,
        locator: FileLocator,
        path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        if not path.exists():
            return
        if path.is_file():
            self.hooks.snapshot_existing(locator, path, relative_path, operation)
            return
        if not path.is_dir():
            return
        root = self.adapter.root_for(locator).resolve()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            self.hooks.snapshot_existing(
                locator,
                child,
                child.relative_to(root).as_posix(),
                operation,
            )

    def _ensure_parent_directory(self, path: Path, requested_path: str) -> None:
        parent = path.parent
        if parent.exists() and not parent.is_dir():
            raise FileCoreError(
                "FILE_ALREADY_EXISTS",
                f"Parent path is not a directory: {requested_path}",
                {"path": requested_path, "parent": str(parent)},
                409,
            )
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError) as exc:
            raise FileCoreError(
                "FILE_ALREADY_EXISTS",
                f"Parent path is not a directory: {requested_path}",
                {"path": requested_path, "parent": str(parent)},
                409,
            ) from exc

    def _cleanup_empty_parents(self, parent_path: Path, root: Path) -> None:
        current = parent_path
        while current != root and self._is_relative_to(current, root) and current.exists():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _copy_path(
        self,
        source: Path,
        dest: Path,
        *,
        preserve_metadata: bool,
    ) -> None:
        if source.is_dir():
            if preserve_metadata:
                shutil.copytree(source, dest, copy_function=shutil.copy2)
            else:
                self._copy_directory_without_metadata(source, dest)
            return
        if preserve_metadata:
            shutil.copy2(source, dest)
        else:
            shutil.copyfile(source, dest)

    def _merge_copy_directory(
        self,
        *,
        locator: FileLocator,
        source_locator: FileLocator,
        dest_locator: FileLocator,
        source_path: str,
        dest_path: str,
    ) -> FileMutationResult:
        operation = "copy"
        self.adapter.can_read(source_locator, source_path)
        self.adapter.can_write(dest_locator, dest_path, operation)
        source_safe_path = self.adapter.resolve_path(source_locator, source_path)
        dest_safe_path = self.adapter.resolve_path(dest_locator, dest_path)
        source = source_safe_path.absolute_path
        dest = dest_safe_path.absolute_path
        self._ensure_no_symlink_tree(source, source_path)
        self._ensure_no_symlink_tree(dest, dest_path)
        if not source.is_dir() or not dest.is_dir():
            raise FileCoreError(
                "FILE_TYPE_CONFLICT",
                f"Directory merge requires two directories: {dest_path}",
                {
                    "sourcePath": source_path,
                    "targetPath": dest_path,
                    "sourceType": "directory" if source.is_dir() else "file",
                    "targetType": "directory" if dest.is_dir() else "file",
                },
                409,
            )
        self._reject_unsafe_copy_or_move_paths(
            source,
            dest,
            source_path=source_path,
            dest_path=dest_path,
        )
        source_size = self._calculate_size(source)
        replaced_size = sum(
            child.stat().st_size
            for child in source.rglob("*")
            if child.is_file() and (dest / child.relative_to(source)).is_file()
        )
        delta = source_size - replaced_size
        source_lock_key = self.adapter.lock_key_for(
            source_locator, source_safe_path.relative_path, operation
        )
        dest_lock_key = self.adapter.lock_key_for(
            dest_locator, dest_safe_path.relative_path, operation
        )
        with ExitStack() as lock_stack:
            for lock_key in sorted(
                {source_lock_key, dest_lock_key}, key=lambda key: repr(key)
            ):
                lock_stack.enter_context(self.write_locks.lock(lock_key))
            with self.hooks.write_barrier(locator, operation):
                self.hooks.check_quota(locator, delta)
                self._snapshot_existing_paths(
                    dest_locator,
                    dest,
                    dest_safe_path.relative_path,
                    operation,
                )
                shutil.copytree(
                    source,
                    dest,
                    dirs_exist_ok=True,
                    copy_function=(
                        shutil.copy2
                        if self.policy.preserve_copy_metadata
                        else shutil.copyfile
                    ),
                )
                self.hooks.after_size_change(locator, delta)
                self.hooks.validate_after_mutation(
                    locator, operation, [dest_safe_path.relative_path]
                )
            self.hooks.after_mutation(
                locator, operation, [dest_safe_path.relative_path]
            )
        return FileMutationResult(
            path=dest_safe_path.relative_path,
            operation=operation,
            entry_type="directory",
            size=self._calculate_size(dest),
            updated_at=iso_from_timestamp(dest.stat().st_mtime),
            metadata={"sourcePath": source_safe_path.relative_path},
        )

    def _move_path(
        self,
        source: Path,
        dest: Path,
        *,
        preserve_metadata: bool,
    ) -> None:
        if preserve_metadata:
            shutil.move(str(source), str(dest))
            return
        self._copy_path(source, dest, preserve_metadata=False)
        if source.is_dir():
            shutil.rmtree(source)
        else:
            source.unlink()

    def _copy_directory_without_metadata(self, source: Path, dest: Path) -> None:
        dest.mkdir()
        for child in source.iterdir():
            target = dest / child.name
            if child.is_dir():
                self._copy_directory_without_metadata(child, target)
            else:
                shutil.copyfile(child, target)

    def _scan_directory(
        self,
        *,
        locator: FileLocator,
        base_root: Path,
        current: Path,
        depth: int,
        max_depth: int,
        include_hidden: bool,
    ) -> list[FileTreeNode]:
        if depth > max_depth:
            return []

        nodes: list[FileTreeNode] = []
        try:
            children = list(current.iterdir())
        except (OSError, PermissionError):
            return []

        for child in sorted(children, key=self._tree_sort_key):
            relative_path = self._visible_relative_path(
                locator=locator,
                child=child,
                include_hidden=include_hidden,
            )
            if relative_path is None:
                continue

            is_directory = self._is_directory(child)
            try:
                stat = child.stat()
            except (OSError, PermissionError):
                continue

            child_nodes: list[FileTreeNode] = []
            if is_directory and depth + 1 <= max_depth:
                child_nodes = self._scan_directory(
                    locator=locator,
                    base_root=base_root,
                    current=child,
                    depth=depth + 1,
                    max_depth=max_depth,
                    include_hidden=include_hidden,
                )

            nodes.append(
                FileTreeNode(
                    name=child.name,
                    path=relative_path,
                    type="directory" if is_directory else "file",
                    size=0 if is_directory else stat.st_size,
                    updated_at=iso_from_timestamp(stat.st_mtime),
                    depth=depth,
                    children=child_nodes,
                    has_children=bool(child_nodes)
                    or depth >= max_depth
                    or self._has_visible_children(
                        locator=locator,
                        directory=child,
                        include_hidden=include_hidden,
                    ),
                    extension="" if is_directory else child.suffix,
                )
            )
        return nodes

    def _tree_sort_key(self, item: Path) -> tuple[bool, str]:
        return (not self._is_directory(item), item.name.lower())

    def _is_directory(self, path: Path) -> bool:
        try:
            return path.is_dir()
        except (OSError, PermissionError):
            return False

    def _visible_relative_path(
        self,
        *,
        locator: FileLocator,
        child: Path,
        include_hidden: bool,
    ) -> Optional[str]:
        if not include_hidden and child.name.startswith("."):
            return None
        try:
            relative_path = self.adapter.canonical_path(locator, child)
            self.adapter.can_read(locator, relative_path)
        except FileCoreError:
            return None
        if self.policy.path_exclusion.is_excluded(Path(relative_path)):
            return None
        return relative_path

    def _has_visible_children(
        self,
        *,
        locator: FileLocator,
        directory: Path,
        include_hidden: bool,
    ) -> bool:
        if not directory.is_dir():
            return False
        try:
            children = list(directory.iterdir())
        except (OSError, PermissionError):
            return False
        return any(
            self._visible_relative_path(
                locator=locator,
                child=child,
                include_hidden=include_hidden,
            )
            is not None
            for child in children
        )

    def _require_file(self, path: Path, requested_path: str) -> None:
        if not path.exists():
            raise FileCoreError(
                "FILE_NOT_FOUND",
                f"File not found: {requested_path}",
                {"path": requested_path},
                404,
            )
        if not path.is_file():
            raise FileCoreError(
                "NOT_A_FILE",
                f"Not a file: {requested_path}",
                {"path": requested_path},
                400,
            )

    def _handle_binary_text(
        self,
        requested_path: str,
        path: Path,
        size: int,
        reason: str = "binary",
    ) -> FileContent:
        if self.policy.read_policy.binary_mode == "friendly-text":
            friendly_message = self.policy.read_policy.friendly_binary_message
            return FileContent(
                path=requested_path,
                content=(
                    friendly_message
                    if friendly_message is not None
                    else "Binary file cannot be displayed"
                ),
                size=size,
                updated_at=iso_from_timestamp(path.stat().st_mtime),
                version_id=self.policy.version_strategy.read_version(path),
                readable=False,
                metadata={"reason": reason},
            )
        raise FileCoreError(
            "BINARY_FILE",
            f"Binary file cannot be displayed: {requested_path}",
            {"path": requested_path},
            400,
        )

    def _decode_with_fallbacks(self, content: bytes) -> Optional[str]:
        for encoding in self.policy.read_policy.fallback_encodings:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return None

    def _handle_large_text(
        self,
        requested_path: str,
        path: Path,
        size: int,
    ) -> FileContent:
        if self.policy.read_policy.large_file_mode == "friendly-text":
            return FileContent(
                path=requested_path,
                content=(
                    self.policy.read_policy.friendly_large_message
                    or "File too large to display"
                ),
                size=size,
                updated_at=iso_from_timestamp(path.stat().st_mtime),
                version_id=self.policy.version_strategy.read_version(path),
                readable=False,
                metadata={"reason": "large"},
            )
        raise FileCoreError(
            "FILE_TOO_LARGE",
            f"File too large: {requested_path}",
            {"path": requested_path, "size": size, "limit": self.policy.max_read_bytes},
            413,
        )

    def _truncate_if_needed(self, content: str) -> tuple[str, dict[str, int | bool]]:
        line_limit = self.policy.read_policy.truncate_after_lines
        if line_limit is None:
            return content, {}
        lines = content.split("\n")
        if len(lines) <= line_limit:
            return content, {}
        return "\n".join(lines[:line_limit]), {
            "truncated": True,
            "omittedLines": len(lines) - line_limit,
        }

    def _looks_binary(self, content: bytes) -> bool:
        return b"\x00" in content
