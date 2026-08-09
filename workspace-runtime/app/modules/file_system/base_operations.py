"""Base file service abstract class"""

from abc import ABC, abstractmethod
from contextlib import nullcontext
from pathlib import Path
from typing import Any, BinaryIO, ContextManager, Dict, List, Optional, Sequence
from datetime import datetime, timezone

from aileron_file_core import (
    ArchiveBuildResult,
    ArchiveBytesResult,
    BatchDeleteRequest as CoreBatchDeleteRequest,
    BatchWriteItem,
    BatchWriteRequest as CoreBatchWriteRequest,
    BuildArchiveRequest,
    CopyEntriesRequest,
    CopyEntryRequest,
    ContentHashVersionStrategy,
    CreateEntryRequest,
    DeleteEntryRequest,
    DynamicRootResolver,
    ExtractArchiveRequest,
    ExtractArchiveStreamRequest,
    FileConflictResolution as CoreFileConflictResolution,
    FileContent,
    FileCoreError,
    FileLocator,
    FileOperationEngine,
    FilePolicy,
    FileReadPolicy,
    MoveEntryRequest,
    PathExclusionPolicy,
    ReadBytesRequest,
    ReadTextRequest,
    ResourceWriteLockManager,
    RootedFileAdapter,
    SearchRequest,
    TreeRequest,
    UploadFilesRequest,
    UploadBatchResult,
    UploadItem,
    UploadStreamItem,
    VersionConflictError,
    WriteBytesRequest,
    WriteTextRequest,
    to_file_conflict_preflight,
    to_upload_batch_result,
    to_tree_nodes,
)
from aileron_git_core import GitOperationInProgressError

from app.config.settings import get_settings
from app.modules.version_control.working_tree_operations import WorkingTreeOperationPort
from .local_history import WorkspaceLocalHistory
from .exceptions import (
    FileManagementException,
    FileNotFoundException,
    FileAlreadyExistsException,
    ReadonlyScopeException,
    InvalidPathException,
    DirectoryNotEmptyException,
    FileTooLargeException,
    ContentConflictException,
    VersionControlOperationInProgressException,
)


class WorkspaceContentVersionStrategy(ContentHashVersionStrategy):
    pass


_resource_write_locks = ResourceWriteLockManager()
_workspace_version_strategy = WorkspaceContentVersionStrategy()


def _is_runtime_local_history_path(relative_path: Path) -> bool:
    parts = relative_path.parts
    return len(parts) >= 2 and parts[0] == ".aileron" and parts[1] == "local-history"


FileSystemError = VersionControlOperationInProgressException


class _WorkspaceFileAdapter(RootedFileAdapter):
    def __init__(self, service: "BaseFileService", path_exclusion: PathExclusionPolicy):
        super().__init__(
            root_resolver=DynamicRootResolver(
                lambda locator: service.resolve_scope_path(locator.scope, "")
            ),
            path_exclusion=path_exclusion,
        )
        self._service = service

    def can_write(
        self, locator: FileLocator, relative_path: str, operation: str
    ) -> None:
        _ = (relative_path, operation)
        if self._service.is_readonly_scope(locator.scope):
            raise FileCoreError(
                "READONLY_SCOPE",
                f"Scope is read-only: {locator.scope}",
                {"scope": locator.scope},
                403,
            )
        self.resolve_path(locator, relative_path)


class _WorkspaceMutationHooks:
    def __init__(self, service: "BaseFileService") -> None:
        self._service = service

    def write_barrier(
        self, locator: FileLocator, operation: str
    ) -> ContextManager[None]:
        _ = locator
        return self._service._git_file_write_barrier(operation)

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        _ = locator
        self._service._snapshot_if_file_exists(absolute_path, relative_path, operation)

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = (locator, operation, paths)

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: Sequence[str],
    ) -> None:
        _ = (locator, operation, paths)


class BaseFileService(ABC):
    """Base file service

    Provides unified file operation interface, subclasses must implement scope-related methods
    """

    # File size limit (10MB)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    MAX_TEXT_READ_SIZE = 1 * 1024 * 1024

    def __init__(
        self,
        root_path: Path,
        *,
        working_tree_operations: Optional[WorkingTreeOperationPort] = None,
        workspace_id: Optional[str] = None,
        context_id: Optional[str] = None,
        local_history: Optional[WorkspaceLocalHistory] = None,
    ):
        """Initialize

        Args:
            root_path: Root directory path
        """
        self._root_path = Path(root_path)
        self._root_path.mkdir(parents=True, exist_ok=True)
        self._working_tree_operations = working_tree_operations
        self._workspace_id = workspace_id
        self._context_id = context_id
        self._local_history = local_history
        settings = get_settings()
        default_path_exclusion = PathExclusionPolicy.defaults(extra_names=())
        path_exclusion = PathExclusionPolicy(
            excluded_names=default_path_exclusion.excluded_names,
            predicate=_is_runtime_local_history_path,
        )
        self._file_engine = FileOperationEngine(
            adapter=_WorkspaceFileAdapter(self, path_exclusion),
            policy=FilePolicy(
                max_read_bytes=self.MAX_TEXT_READ_SIZE,
                max_write_bytes=self.MAX_FILE_SIZE,
                max_extract_entries=settings.ARCHIVE_MAX_ENTRY_COUNT,
                max_extract_entry_bytes=settings.ARCHIVE_MAX_ENTRY_SIZE_BYTES,
                max_extract_total_bytes=settings.ARCHIVE_MAX_TOTAL_SIZE_BYTES,
                max_archive_selected_roots=settings.ARCHIVE_DOWNLOAD_MAX_SELECTED_ROOTS,
                max_archive_entries=settings.ARCHIVE_DOWNLOAD_MAX_ENTRY_COUNT,
                max_archive_total_bytes=settings.ARCHIVE_DOWNLOAD_MAX_TOTAL_SIZE_BYTES,
                read_policy=FileReadPolicy(
                    binary_mode="friendly-text",
                    large_file_mode="friendly-text",
                    truncate_after_lines=1000,
                    friendly_binary_message="binary",
                    friendly_large_message="large",
                ),
                cleanup_empty_parents=True,
                version_strategy=_workspace_version_strategy,
                path_exclusion=path_exclusion,
            ),
            hooks=_WorkspaceMutationHooks(self),
            write_locks=_resource_write_locks,
        )

    @property
    def local_history(self) -> Optional[WorkspaceLocalHistory]:
        return self._local_history

    def _engine(self) -> FileOperationEngine:
        self._file_engine.write_locks = _resource_write_locks
        return self._file_engine

    def _locator(self, scope: Optional[str]) -> FileLocator:
        return FileLocator(
            domain="workspace",
            resource_id=self._workspace_id or "local",
            scope=scope,
        )

    def _map_core_error(
        self, exc: FileCoreError, path: str, scope: Optional[str]
    ) -> FileManagementException:
        if exc.code == "CONTENT_CONFLICT":
            return ContentConflictException(
                path,
                exc.details.get("expectedRevision")
                or exc.details.get("expectedVersion", ""),
                exc.details.get("actualRevision")
                or exc.details.get("actualVersion", ""),
            )
        if exc.code == "FILE_NOT_FOUND":
            return FileNotFoundException(path, scope)
        if exc.code == "FILE_ALREADY_EXISTS":
            return FileAlreadyExistsException(path, scope)
        if exc.code == "DIRECTORY_NOT_EMPTY":
            return DirectoryNotEmptyException(path)
        if exc.code == "FILE_TOO_LARGE":
            return FileTooLargeException(
                path,
                int(exc.details.get("size", 0)),
                int(exc.details.get("limit", self.MAX_FILE_SIZE)),
            )
        if exc.code == "READONLY_SCOPE":
            return ReadonlyScopeException(scope or "")
        if exc.code in {
            "ARCHIVE_DOWNLOAD_LIMIT_EXCEEDED",
            "ARCHIVE_LIMIT_EXCEEDED",
            "DUPLICATE_CONFLICT_RESOLUTION",
            "DUPLICATE_SOURCE_PATH",
            "FILE_TYPE_CONFLICT",
            "INVALID_ARCHIVE_ENTRY",
            "INVALID_CONFLICT_STRATEGY",
            "INVALID_FILENAME",
        }:
            return FileManagementException(
                exc.code,
                str(exc),
                exc.details,
                exc.status_hint,
            )
        return InvalidPathException(path, exc.code)

    def _response_path(self, requested_path: str, normalized_path: str) -> str:
        if normalized_path in {"", "."}:
            return "/" if requested_path.startswith("/") else ""
        if requested_path.startswith("/"):
            return f"/{normalized_path.lstrip('/')}"
        return normalized_path.lstrip("/")

    def _tree_node_path(self, normalized_path: str) -> str:
        return (
            f"/{normalized_path.lstrip('/')}"
            if normalized_path not in {"", "."}
            else "/"
        )

    def _map_tree_nodes(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mapped = []
        for node in nodes:
            next_node = dict(node)
            next_node["path"] = self._tree_node_path(str(node["path"]))
            next_node["id"] = next_node.get("id") or next_node["path"]
            next_node["children"] = self._map_tree_nodes(list(node.get("children", [])))
            mapped.append(next_node)
        return mapped

    def _map_read_content(
        self,
        content: FileContent,
        requested_path: str,
        scope: Optional[str],
    ) -> Dict[str, Any]:
        _ = scope
        metadata = dict(content.metadata)
        response_content = content.content
        revision = content.version_id

        if metadata.get("reason") == "large":
            size_mb = content.size / (1024 * 1024)
            response_content = (
                f"Large text file: {requested_path}\n"
                f"Size: {size_mb:.2f} MB\n"
                "(File too large to display in editor)"
            )
        elif metadata.get("reason") == "binary":
            response_content = (
                f"Binary file: {requested_path}\n"
                "(Binary files cannot be displayed in text editor)"
            )
        elif metadata.get("reason") == "decode-error":
            response_content = (
                f"Binary file: {requested_path}\n(File encoding is not UTF-8)"
            )
        elif metadata.get("truncated"):
            response_content = (
                f"{content.content}\n\n"
                f"... (truncated, {metadata['omittedLines']} more lines)"
            )

        return {
            "path": requested_path,
            "scope": scope,
            "content": response_content,
            "size": content.size,
            "updatedAt": content.updated_at,
            "revision": revision,
        }

    # ============ Abstract Methods (Must Implement) ============

    @abstractmethod
    def resolve_scope_path(self, scope: Optional[str], relative_path: str) -> Path:
        """Resolve scope and relative path to actual file system path

        Args:
            scope: Scope identifier (e.g., project, user, plugin, skills, scripts, etc.)
            relative_path: Relative path

        Returns:
            Actual file system path
        """
        pass

    @abstractmethod
    def validate_scope(self, scope: Optional[str]) -> bool:
        """Validate if scope is valid

        Args:
            scope: Scope identifier

        Returns:
            Whether valid
        """
        pass

    @abstractmethod
    def is_readonly_scope(self, scope: Optional[str]) -> bool:
        """Check if scope is read-only

        Args:
            scope: Scope identifier

        Returns:
            Whether read-only
        """
        pass

    # ============ Core File Operations ============

    def get_tree(
        self,
        path: str = "/",
        scope: Optional[str] = None,
        include_hidden: bool = False,
        max_depth: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get file tree

        Args:
            path: Target path
            scope: Scope identifier
            include_hidden: Whether to include hidden files
            max_depth: Maximum depth (defaults to FILE_TREE_MAX_DEPTH in settings)

        Returns:
            File tree data
        """
        # Use default value from settings
        settings = get_settings()
        if max_depth is None:
            max_depth = settings.FILE_TREE_MAX_DEPTH

        # Limit max depth to settings value
        max_depth = min(max_depth, settings.FILE_TREE_MAX_DEPTH)

        fs_path = self.resolve_scope_path(scope, path)
        if not fs_path.exists() and path in {"/", ""}:
            fs_path.mkdir(parents=True, exist_ok=True)

        try:
            tree = self._engine().get_tree(
                TreeRequest(
                    locator=self._locator(scope),
                    path=path,
                    include_hidden=include_hidden,
                    max_depth=max_depth,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc

        nodes = self._map_tree_nodes(to_tree_nodes(tree.nodes))

        return {"path": path, "scope": scope, "nodes": nodes, "total": tree.total}

    def read_file(self, path: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """Read file content (text mode)

        Args:
            path: File path
            scope: Scope identifier

        Returns:
            File content data
        """
        try:
            content = self._engine().read_text(
                ReadTextRequest(locator=self._locator(scope), path=path)
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc

        return self._map_read_content(content, path, scope)

    def read_file_binary(self, path: str, scope: Optional[str] = None) -> bytes:
        """Read file content (binary mode)

        Args:
            path: File path
            scope: Scope identifier

        Returns:
            File binary content
        """
        try:
            return (
                self._engine()
                .read_bytes(ReadBytesRequest(locator=self._locator(scope), path=path))
                .content
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc

    def write_file(
        self,
        path: str,
        content: str,
        scope: Optional[str] = None,
        revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Write file content

        Args:
            path: File path
            content: File content
            scope: Scope identifier
            revision: Expected revision (for conflict detection)

        Returns:
            Write result
        """
        try:
            result = self._engine().write_text(
                WriteTextRequest(
                    locator=self._locator(scope),
                    path=path,
                    content=content,
                    expected_version_id=revision,
                )
            )
        except VersionConflictError as exc:
            raise ContentConflictException(
                path, exc.expected_version, exc.actual_version
            ) from exc
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        return {
            "path": path,
            "scope": scope,
            "size": result.size,
            "updatedAt": result.updated_at,
            "revision": result.version_id,
        }

    def _operation_key(self) -> Optional[str]:
        if not self._workspace_id:
            return None
        context_id = self._context_id or "primary"
        return f"workspace:{self._workspace_id}:context:{context_id}"

    def _git_file_write_barrier(
        self, operation_name: str = "write_file"
    ) -> ContextManager[None]:
        if self._working_tree_operations is None:
            return nullcontext()

        operation_key = self._operation_key()
        if operation_key is None:
            return nullcontext()

        return self._working_tree_operations.mutate(
            operation_key,
            operation_name=operation_name,
        )

    def create_entry(
        self,
        path: str,
        entry_type: str,
        scope: Optional[str] = None,
        content: str = "",
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Create file or directory

        Args:
            path: Path
            entry_type: Type (file or directory)
            scope: Scope identifier
            content: File content (files only)
            encoding: Content encoding (utf-8 or base64)

        Returns:
            Creation result
        """
        try:
            result = self._engine().create_entry(
                CreateEntryRequest(
                    locator=self._locator(scope),
                    path=path,
                    entry_type=entry_type,
                    content=content,
                    encoding=encoding,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        return {
            "path": path,
            "scope": scope,
            "type": result.entry_type,
            "size": result.size,
            "createdAt": result.updated_at or datetime.now(timezone.utc).isoformat(),
        }

    def delete_entry(
        self, path: str, scope: Optional[str] = None, recursive: bool = False
    ) -> Dict[str, Any]:
        """Delete file or directory

        Args:
            path: Path
            scope: Scope identifier
            recursive: Whether to recursively delete directory

        Returns:
            Deletion result
        """
        try:
            result = self._engine().delete_entry(
                DeleteEntryRequest(
                    locator=self._locator(scope),
                    path=path,
                    recursive=recursive,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        return {"path": path, "scope": scope, "type": result.entry_type}

    def copy_entry(
        self,
        source_path: str,
        dest_path: str,
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Copy file or directory (supports folder copy)

        Args:
            source_path: Source path
            dest_path: Destination path
            source_scope: Source scope
            dest_scope: Destination scope

        Returns:
            Copy result
        """
        try:
            result = self._engine().copy_entry(
                CopyEntryRequest(
                    locator=self._locator(dest_scope),
                    source_locator=self._locator(source_scope),
                    dest_locator=self._locator(dest_scope),
                    source_path=source_path,
                    dest_path=dest_path,
                )
            )
        except FileCoreError as exc:
            error_path = dest_path if exc.code == "FILE_ALREADY_EXISTS" else source_path
            error_scope = (
                dest_scope if exc.code == "FILE_ALREADY_EXISTS" else source_scope
            )
            raise self._map_core_error(exc, error_path, error_scope) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        final_dest_path = self._response_path(dest_path, result.path)

        return {
            "sourcePath": source_path,
            "destPath": final_dest_path,
            "sourceScope": source_scope,
            "destScope": dest_scope,
            "type": result.entry_type,
        }

    def move_entry(
        self,
        source_path: str,
        dest_path: str,
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Move or rename file or directory

        Args:
            source_path: Source path
            dest_path: Destination path
            source_scope: Source scope
            dest_scope: Destination scope

        Returns:
            Move result
        """
        try:
            result = self._engine().move_entry(
                MoveEntryRequest(
                    locator=self._locator(dest_scope),
                    source_locator=self._locator(source_scope),
                    dest_locator=self._locator(dest_scope),
                    source_path=source_path,
                    dest_path=dest_path,
                )
            )
        except FileCoreError as exc:
            if exc.code == "READONLY_SCOPE":
                error_path = source_path
                error_scope = (
                    source_scope if self.is_readonly_scope(source_scope) else dest_scope
                )
            else:
                error_path = (
                    dest_path if exc.code == "FILE_ALREADY_EXISTS" else source_path
                )
                error_scope = (
                    dest_scope if exc.code == "FILE_ALREADY_EXISTS" else source_scope
                )
            raise self._map_core_error(exc, error_path, error_scope) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        final_dest_path = self._response_path(dest_path, result.path)

        return {
            "sourcePath": source_path,
            "destPath": final_dest_path,
            "sourceScope": source_scope,
            "destScope": dest_scope,
            "type": result.entry_type,
        }

    def _snapshot_if_file_exists(
        self,
        fs_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        if self._local_history is None or not fs_path.exists() or not fs_path.is_file():
            return

        revision = _workspace_version_strategy.read_version(fs_path)

        self._local_history.snapshot_file(
            source_path=fs_path,
            relative_path=relative_path,
            operation=operation,
            revision_before=revision,
        )

    def restore_history_entry(
        self,
        entry_id: str,
        revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._local_history is None:
            raise FileManagementException(
                "LOCAL_HISTORY_DISABLED",
                "Local history is not enabled",
                {},
                400,
            )

        entry = self._local_history.get_entry(entry_id)
        if not entry.snapshot_path:
            raise FileNotFoundException(entry.path)

        snapshot_path = Path(entry.snapshot_path)
        if not snapshot_path.exists() or not snapshot_path.is_file():
            raise FileNotFoundException(entry.path)

        content = snapshot_path.read_bytes()
        current_path = self.resolve_scope_path(None, entry.path)
        if current_path.exists() and revision is None:
            current_version = _workspace_version_strategy.read_version(current_path)
            raise ContentConflictException(entry.path, None, current_version)

        try:
            result = self._engine().write_bytes(
                WriteBytesRequest(
                    locator=self._locator(None),
                    path=entry.path,
                    content=content,
                    operation="restore",
                    expected_version_id=revision,
                )
            )
        except VersionConflictError as exc:
            raise ContentConflictException(
                entry.path,
                exc.expected_version,
                exc.actual_version,
            ) from exc
        except FileCoreError as exc:
            raise self._map_core_error(exc, entry.path, None) from exc
        except GitOperationInProgressError as exc:
            raise VersionControlOperationInProgressException() from exc

        return {
            "path": entry.path,
            "restoredFrom": entry.id,
            "revision": result.version_id,
        }

    # ============ Upload / Archive / Search Operations ============

    @staticmethod
    def _core_conflict_resolutions(
        resolutions: Sequence[Any],
    ) -> tuple[CoreFileConflictResolution, ...]:
        return tuple(
            CoreFileConflictResolution(
                source_path=resolution.sourcePath,
                strategy=resolution.strategy,
            )
            for resolution in resolutions
        )

    @staticmethod
    def _preflight_result(result) -> Dict[str, Any]:
        return to_file_conflict_preflight(result)

    @staticmethod
    def _batch_result(result: UploadBatchResult) -> Dict[str, Any]:
        return to_upload_batch_result(result)

    def preflight_upload_files(
        self,
        *,
        target_path: str,
        filenames: Sequence[str],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().preflight_upload_files(
                UploadFilesRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    files=[UploadItem(filename=name, content=b"") for name in filenames],
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._preflight_result(result)

    def preflight_upload_streams(
        self,
        *,
        target_path: str,
        files: Sequence[tuple[str, BinaryIO, int]],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().preflight_upload_streams(
                locator=self._locator(scope),
                target_path=target_path,
                files=[
                    UploadStreamItem(filename=name, stream=stream, size=size)
                    for name, stream, size in files
                ],
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._preflight_result(result)

    def preflight_copy_entries(
        self,
        *,
        source_paths: Sequence[str],
        target_path: str,
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().preflight_copy_entries(
                CopyEntriesRequest(
                    locator=self._locator(dest_scope),
                    source_locator=self._locator(source_scope),
                    dest_locator=self._locator(dest_scope),
                    source_paths=source_paths,
                    target_path=target_path,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, dest_scope) from exc
        return self._preflight_result(result)

    def preflight_extract_archive(
        self,
        *,
        archive_path: str,
        target_path: str,
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            archive = self._engine().read_bytes(
                ReadBytesRequest(locator=self._locator(scope), path=archive_path)
            )
            result = self._engine().preflight_extract_archive(
                ExtractArchiveRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    archive_name=Path(archive_path).name,
                    archive_bytes=archive.content,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._preflight_result(result)

    def paste_entries(
        self,
        *,
        source_paths: Sequence[str],
        target_path: str,
        default_strategy: str,
        resolutions: Sequence[Any],
        source_scope: Optional[str] = None,
        dest_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().copy_entries(
                CopyEntriesRequest(
                    locator=self._locator(dest_scope),
                    source_locator=self._locator(source_scope),
                    dest_locator=self._locator(dest_scope),
                    source_paths=source_paths,
                    target_path=target_path,
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, dest_scope) from exc
        return self._batch_result(result)

    def upload_file_bytes(
        self,
        *,
        target_path: str,
        filename: str,
        content: bytes,
        default_strategy: str,
        resolutions: Sequence[Any],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().upload_files(
                UploadFilesRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    files=[UploadItem(filename=filename, content=content)],
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._batch_result(result)

    def upload_file_streams(
        self,
        *,
        target_path: str,
        files: Sequence[tuple[str, BinaryIO, int]],
        default_strategy: str,
        resolutions: Sequence[Any],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().upload_streams(
                locator=self._locator(scope),
                target_path=target_path,
                files=[
                    UploadStreamItem(filename=filename, stream=stream, size=size)
                    for filename, stream, size in files
                ],
                default_strategy=default_strategy,
                resolutions=self._core_conflict_resolutions(resolutions),
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._batch_result(result)

    def extract_archive_bytes(
        self,
        *,
        target_path: str,
        archive_name: str,
        archive_bytes: bytes,
        default_strategy: str,
        resolutions: Sequence[Any],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().extract_archive(
                ExtractArchiveRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    archive_name=archive_name,
                    archive_bytes=archive_bytes,
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._batch_result(result)

    def extract_archive_stream(
        self,
        *,
        target_path: str,
        archive_name: str,
        archive_stream: BinaryIO,
        archive_size: int,
        default_strategy: str,
        resolutions: Sequence[Any],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().extract_archive_stream(
                ExtractArchiveStreamRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    archive_name=archive_name,
                    archive_stream=archive_stream,
                    archive_size=archive_size,
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._batch_result(result)

    def extract_archive_path(
        self,
        *,
        archive_path: str,
        target_path: str,
        default_strategy: str,
        resolutions: Sequence[Any],
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            archive = self._engine().read_bytes(
                ReadBytesRequest(locator=self._locator(scope), path=archive_path)
            )
            result = self._engine().extract_archive(
                ExtractArchiveRequest(
                    locator=self._locator(scope),
                    target_path=target_path,
                    archive_name=Path(archive_path).name,
                    archive_bytes=archive.content,
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, target_path, scope) from exc
        return self._batch_result(result)

    def build_archive_plan(
        self,
        *,
        paths: List[str],
        scope: Optional[str] = None,
    ) -> ArchiveBuildResult:
        try:
            return self._engine().build_archive(
                BuildArchiveRequest(locator=self._locator(scope), paths=paths)
            )
        except FileCoreError as exc:
            error_path = paths[0] if paths else "/"
            raise self._map_core_error(exc, error_path, scope) from exc

    def build_archive_bytes(
        self,
        *,
        paths: List[str],
        scope: Optional[str] = None,
    ) -> ArchiveBytesResult:
        try:
            return self._engine().build_archive_bytes(
                BuildArchiveRequest(locator=self._locator(scope), paths=paths)
            )
        except FileCoreError as exc:
            error_path = paths[0] if paths else "/"
            raise self._map_core_error(exc, error_path, scope) from exc

    def search_entries(
        self,
        *,
        query: str,
        path: str = "/",
        include_content: bool = True,
        case_sensitive: bool = False,
        max_results: Optional[int] = None,
        scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            result = self._engine().search(
                SearchRequest(
                    locator=self._locator(scope),
                    query=query,
                    path=path,
                    include_content=include_content,
                    case_sensitive=case_sensitive,
                    max_results=max_results,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, scope) from exc
        return {
            "query": query,
            "path": path,
            "scope": scope,
            "results": [
                {
                    "path": self._response_path("/", match.path),
                    "name": match.name,
                    "type": match.entry_type,
                    "size": match.size,
                    "updatedAt": match.updated_at,
                    "matches": [match.preview] if match.preview else None,
                }
                for match in result.matches
            ],
            "total": result.total,
        }

    # ============ Batch Operations ============

    def batch_delete(
        self, paths: List[str], scope: Optional[str] = None, recursive: bool = False
    ) -> Dict[str, Any]:
        """Batch delete

        Args:
            paths: Path list
            scope: Scope identifier
            recursive: Whether to recursively delete directories

        Returns:
            Batch operation result
        """
        result = self._engine().batch_delete(
            CoreBatchDeleteRequest(
                locator=self._locator(scope),
                paths=paths,
                recursive=recursive,
            )
        )
        return {
            "total": result.total,
            "succeeded": result.succeeded,
            "failed": result.failed,
            "results": [
                {
                    "path": item.path,
                    "status": item.status,
                    **({"error": item.error} if item.error else {}),
                }
                for item in result.results
            ],
        }

    def batch_write(
        self, files: List[Dict[str, Any]], scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """Batch write files

        Args:
            files: File list [{"path": "...", "content": "..."}, ...]
            scope: Scope identifier

        Returns:
            Batch operation result
        """
        result = self._engine().batch_write(
            CoreBatchWriteRequest(
                locator=self._locator(scope),
                files=[
                    BatchWriteItem(
                        path=str(file_info["path"]),
                        content=str(file_info["content"]),
                    )
                    for file_info in files
                ],
            )
        )
        return {
            "results": [
                {
                    "path": item.path,
                    "status": item.status,
                    **({"size": item.size} if item.size is not None else {}),
                    **({"error": item.error} if item.error else {}),
                }
                for item in result.results
            ],
            "total": result.total,
            "succeeded": result.succeeded,
            "failed": result.failed,
        }

    # ============ Utility Methods ============
