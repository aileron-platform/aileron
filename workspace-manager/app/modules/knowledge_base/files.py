"""Knowledge base file service."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, Sequence
from uuid import uuid4

from aileron_file_core import (
    ArchiveBytesResult,
    BuildArchiveRequest,
    ContentHashVersionStrategy,
    CopyEntriesRequest,
    CreateEntryRequest,
    DeleteEntryRequest,
    DynamicRootResolver,
    ExtractArchiveRequest,
    FileContent,
    FileCoreError,
    FileLocator,
    FileOperationEngine,
    FilePolicy,
    FileReadPolicy,
    FileTreeNode,
    MoveEntryRequest,
    PathExclusionPolicy,
    ReadBytesRequest,
    ReadTextRequest,
    ResourceWriteLockManager,
    RootedFileAdapter,
    SafePath,
    SearchRequest,
    TreeRequest,
    UploadFilesRequest,
    UploadItem,
    VersionConflictError,
    WriteBytesRequest,
    WriteTextRequest,
    to_file_conflict_preflight,
    to_upload_batch_result,
)
from aileron_file_core import (
    FileConflictResolution as CoreFileConflictResolution,
)
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.core.file_management import (
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileContentResponse,
    FileExtractExecutionRequest,
    FileManagementException,
    FileNode,
    FileNotFoundException,
    FileTooLargeException,
    FileTreeResponse,
    InvalidPathException,
    PermissionDeniedException,
)
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.access import KnowledgeBaseService
from app.modules.knowledge_base.git_operations import kb_file_write_barrier
from app.modules.knowledge_base.quota import enforce_knowledge_base_storage_quota
from app.modules.knowledge_base.storage import ensure_knowledge_base_storage_root
from app.modules.platform_resource_analytics.analytics import PlatformResourceActivityLedger
from app.modules.version_control.local_history import ManagerLocalHistoryService

logger = logging.getLogger(__name__)

KB_CONTENT_CONFLICT_MESSAGE = "File content version conflict"
KB_TOO_MANY_UPLOADS_MESSAGE = "Number of uploaded files exceeds limit"
KB_UPLOAD_SUCCESS_MESSAGE = "File upload complete"
KB_NOT_A_FILE_REASON = "Not a file"
KB_PATH_TRAVERSAL_REASON = "Invalid path detected"
KB_QUOTA_EXCEEDED_MESSAGE = "Knowledge base storage quota exceeded"
KB_OWNER_QUOTA_EXCEEDED_MESSAGE = "User knowledge base total storage quota exceeded"

_resource_write_locks = ResourceWriteLockManager()
_current_kb: ContextVar[Optional[db_models.KnowledgeBase]] = ContextVar(
    "knowledge_base_file_current_kb",
    default=None,
)
_current_kb_access_role: ContextVar[Optional[str]] = ContextVar(
    "knowledge_base_file_current_access_role",
    default=None,
)


class _KnowledgeBaseFileAdapter(RootedFileAdapter):
    _WRITE_ROLES = {"manager", "owner"}

    def lock_key_for(
        self,
        locator: FileLocator,
        relative_path: str,
        operation: str,
    ) -> tuple[str, str, str]:
        _ = operation
        safe_path: SafePath = self.resolve_path(locator, relative_path)
        return (locator.domain, locator.resource_id, safe_path.relative_path)

    def can_write(
        self, locator: FileLocator, relative_path: str, operation: str
    ) -> None:
        role = _current_kb_access_role.get()
        if role not in self._WRITE_ROLES:
            raise FileCoreError(
                "READONLY",
                "Knowledge base role cannot write files",
                {"kbId": locator.resource_id, "role": role, "operation": operation},
                403,
            )
        super().can_write(locator, relative_path, operation)


class _KnowledgeBaseMutationHooks:
    def __init__(self, service: "KnowledgeBaseFileService") -> None:
        self._service = service

    def write_barrier(self, locator: FileLocator, operation: str):
        return kb_file_write_barrier(
            locator.resource_id,
            operation_name=(
                f"{operation}_entry" if operation != "write" else "write_file"
            ),
        )

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = locator
        self._service._check_quota(self._require_kb(), delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        if not absolute_path.exists() or not absolute_path.is_file():
            return
        version_id = self._service._file_policy().version_strategy.read_version(
            absolute_path
        )
        content_hash = ContentHashVersionStrategy().read_version(absolute_path)
        self._service.local_history.snapshot_file(
            domain="knowledge-base",
            resource_id=locator.resource_id,
            source_path=absolute_path,
            relative_path=relative_path,
            operation=operation,
            version_id_before=version_id,
            content_hash_before=content_hash,
        )

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = locator
        self._service._pending_capacity_transition = self._service._update_kb_size(
            self._require_kb(), delta_bytes
        )

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
        _ = paths
        event_type = {
            "write": "file_written",
            "create": "file_created",
            "delete": "file_deleted",
            "upload": "file_uploaded",
            "move": "file_moved",
            "copy": "file_copied",
        }.get(operation, "content_mutated")
        PlatformResourceActivityLedger(self._service.db).record_manager_activity(
            event_id=f"manager:{uuid4()}",
            resource_type="knowledge_base",
            resource_id=locator.resource_id,
            event_type=event_type,
        )
        kb = self._require_kb()
        try:
            self._service.db.commit()
        except Exception:
            self._service.db.rollback()
            raise
        if self._service._pending_capacity_transition is not None:
            PlatformResourceActivityLedger(self._service.db).count_capacity_transition(
                self._service._pending_capacity_transition,
                "knowledge_base",
                "quota",
            )
            self._service._pending_capacity_transition = None
        self._service.db.refresh(kb)

    def _require_kb(self) -> db_models.KnowledgeBase:
        kb = _current_kb.get()
        if kb is None:
            raise RuntimeError("Knowledge base mutation context is not set")
        return kb


class KnowledgeBaseFileService:
    """Handle knowledge base file and folder operations."""

    MAX_UPLOAD_FILES = 50

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.kb_service = KnowledgeBaseService(db)
        self.storage_root = Path(self.settings.MANAGER_KNOWLEDGE_BASES_DIR)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self.local_history = ManagerLocalHistoryService(
            history_root=Path(self.settings.MANAGER_LOCAL_HISTORY_DIR)
        )
        self._pending_capacity_transition: str | None = None
        self._file_engine = FileOperationEngine(
            adapter=_KnowledgeBaseFileAdapter(
                root_resolver=DynamicRootResolver(
                    lambda locator: self._kb_root(locator.resource_id)
                ),
            ),
            policy=self._file_policy(),
            hooks=_KnowledgeBaseMutationHooks(self),
            write_locks=_resource_write_locks,
        )

    def _file_policy(self) -> FilePolicy:
        return FilePolicy(
            max_read_bytes=self.settings.KB_SINGLE_FILE_SIZE_LIMIT,
            max_write_bytes=max(
                self.settings.DEFAULT_KB_QUOTA_BYTES,
                self.settings.DEFAULT_USER_KB_QUOTA_BYTES,
                self.settings.KB_SINGLE_FILE_SIZE_LIMIT,
            ),
            max_upload_files=self.MAX_UPLOAD_FILES,
            max_extract_entries=10000,
            max_extract_entry_bytes=1024 * 1024 * 1024,
            max_extract_total_bytes=1024 * 1024 * 1024,
            max_archive_selected_roots=100,
            max_archive_entries=10000,
            max_archive_total_bytes=1024 * 1024 * 1024,
            preserve_copy_metadata=True,
            directory_destination_mode="treat-as-target",
            read_policy=FileReadPolicy(
                binary_mode="friendly-text",
                fallback_encodings=("latin-1",),
                friendly_binary_message="",
            ),
            version_strategy=ContentHashVersionStrategy(),
            path_exclusion=PathExclusionPolicy.defaults(),
        )

    def _engine(self) -> FileOperationEngine:
        self._file_engine.policy = self._file_policy()
        self._file_engine.write_locks = _resource_write_locks
        return self._file_engine

    def _locator(self, kb_id: str) -> FileLocator:
        return FileLocator(domain="knowledge-base", resource_id=kb_id)

    @contextmanager
    def _kb_context(
        self,
        kb: db_models.KnowledgeBase,
        access_role: str | None = None,
    ) -> Iterator[None]:
        token = _current_kb.set(kb)
        role_token = _current_kb_access_role.set(access_role)
        try:
            yield
        finally:
            _current_kb.reset(token)
            _current_kb_access_role.reset(role_token)

    def _map_core_error(
        self, exc: FileCoreError, path: str, kb_id: str
    ) -> FileManagementException:
        if exc.code == "CONTENT_CONFLICT":
            return FileManagementException(
                code="CONTENT_CONFLICT",
                message=KB_CONTENT_CONFLICT_MESSAGE,
                details={
                    "path": path,
                    "expectedRevision": exc.details.get("expectedVersion"),
                    "actualRevision": exc.details.get("actualVersion"),
                },
                status_code=409,
            )
        if exc.code == "FILE_NOT_FOUND":
            return FileNotFoundException(path, self._scope(kb_id))
        if exc.code == "FILE_ALREADY_EXISTS":
            return FileAlreadyExistsException(path, self._scope(kb_id))
        if exc.code == "DIRECTORY_NOT_EMPTY":
            return DirectoryNotEmptyException(path)
        if exc.code == "FILE_TOO_LARGE":
            return FileTooLargeException(
                path,
                int(exc.details.get("size", 0)),
                int(exc.details.get("limit", self.settings.KB_SINGLE_FILE_SIZE_LIMIT)),
            )
        if exc.code == "READONLY":
            return PermissionDeniedException(
                path,
                str(exc.details.get("operation", "write")),
            )
        return InvalidPathException(path, exc.code)

    def _to_api_path(self, path: str) -> str:
        return "/" if path in {"", "."} else f"/{path.lstrip('/')}"

    def _to_file_node(self, node: FileTreeNode) -> FileNode:
        return FileNode(
            id=self._to_api_path(node.path),
            name=node.name,
            path=self._to_api_path(node.path),
            type=node.type,
            scope=None,
            size=node.size,
            updatedAt=node.updated_at,
            depth=node.depth,
            children=[self._to_file_node(child) for child in node.children],
            hasChildren=node.has_children,
            writable=True,
            extension=node.extension.lower() if node.extension else None,
        )

    def _to_file_content(
        self,
        *,
        kb_id: str,
        path: str,
        content: FileContent,
    ) -> FileContentResponse:
        return FileContentResponse(
            path=path,
            scope=self._scope(kb_id),
            content=content.content,
            size=content.size,
            updatedAt=content.updated_at,
            revision=content.version_id,
            readable=content.readable,
            unreadableReason=None if content.readable else "binary",
        )

    def get_tree(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str = "/",
        include_hidden: bool = False,
        max_depth: int = 1,
    ) -> FileTreeResponse:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        try:
            tree = self._engine().get_tree(
                TreeRequest(
                    locator=self._locator(kb.id),
                    path=path,
                    include_hidden=include_hidden,
                    max_depth=max_depth,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc
        nodes = [self._to_file_node(node) for node in tree.nodes]
        return FileTreeResponse(
            path=path, scope=self._scope(kb.id), nodes=nodes, total=len(nodes)
        )

    def read_file(
        self, *, actor: AuthorizationActor, kb_id: str, path: str
    ) -> FileContentResponse:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        try:
            content = self._engine().read_text(
                ReadTextRequest(locator=self._locator(kb.id), path=path)
            )
        except FileCoreError as exc:
            if exc.code == "NOT_A_FILE":
                raise InvalidPathException(path, KB_NOT_A_FILE_REASON) from exc
            raise self._map_core_error(exc, path, kb.id) from exc
        return self._to_file_content(kb_id=kb.id, path=path, content=content)

    def read_file_bytes(
        self, *, actor: AuthorizationActor, kb_id: str, path: str
    ) -> tuple[bytes, int]:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        try:
            content = self._engine().read_bytes(
                ReadBytesRequest(locator=self._locator(kb.id), path=path)
            )
        except FileCoreError as exc:
            if exc.code == "NOT_A_FILE":
                raise InvalidPathException(path, KB_NOT_A_FILE_REASON) from exc
            raise self._map_core_error(exc, path, kb.id) from exc

        if content.size > self.settings.KB_SINGLE_FILE_SIZE_LIMIT:
            raise FileTooLargeException(
                path, content.size, self.settings.KB_SINGLE_FILE_SIZE_LIMIT
            )
        return content.content, content.size

    def resolve_download_path(
        self, *, actor: AuthorizationActor, kb_id: str, path: str
    ) -> Path:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        try:
            safe_path = self._engine().adapter.resolve_path(self._locator(kb.id), path)
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc
        fs_path = safe_path.absolute_path
        if not fs_path.exists():
            raise FileNotFoundException(path, self._scope(kb.id))
        if not fs_path.is_file():
            raise InvalidPathException(path, KB_NOT_A_FILE_REASON)
        return fs_path

    def write_file(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str,
        content: str,
        revision: Optional[str] = None,
    ) -> dict:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        try:
            with self._kb_context(kb, access.access_role):
                result = self._engine().write_text(
                    WriteTextRequest(
                        locator=self._locator(kb.id),
                        path=path,
                        content=content,
                        expected_version_id=revision,
                    )
                )
        except VersionConflictError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc

        return {
            "updatedAt": result.updated_at,
            "revision": result.version_id,
            "size": result.size,
        }

    def create_entry(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str,
        entry_type: str,
        content: str = "",
    ) -> dict:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        try:
            with self._kb_context(kb, access.access_role):
                result = self._engine().create_entry(
                    CreateEntryRequest(
                        locator=self._locator(kb.id),
                        path=path,
                        entry_type=entry_type,
                        content=content,
                    )
                )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc

        response = {
            "createdAt": result.updated_at or datetime.now(timezone.utc).isoformat(),
            "type": result.entry_type,
        }
        if result.entry_type == "file":
            response["size"] = result.size
        return response

    def delete_entry(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: str,
        recursive: bool = False,
    ) -> dict:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        try:
            with self._kb_context(kb, access.access_role):
                result = self._engine().delete_entry(
                    DeleteEntryRequest(
                        locator=self._locator(kb.id),
                        path=path,
                        recursive=recursive,
                    )
                )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb.id) from exc

        return {"type": result.entry_type}

    def move_entry(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        source_path: str,
        dest_path: str,
    ) -> dict:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        try:
            with self._kb_context(kb, access.access_role):
                result = self._engine().move_entry(
                    MoveEntryRequest(
                        locator=self._locator(kb.id),
                        source_path=source_path,
                        dest_path=dest_path,
                    )
                )
        except FileCoreError as exc:
            error_path = dest_path if exc.code == "FILE_ALREADY_EXISTS" else source_path
            raise self._map_core_error(exc, error_path, kb.id) from exc

        return {"type": result.entry_type, "size": result.size}

    @staticmethod
    def _core_resolutions(
        resolutions: Sequence[FileConflictResolution],
    ) -> tuple[CoreFileConflictResolution, ...]:
        return tuple(
            CoreFileConflictResolution(
                source_path=resolution.sourcePath,
                strategy=resolution.strategy,
            )
            for resolution in resolutions
        )

    @staticmethod
    def _preflight_response(result) -> FileConflictPreflightResponse:
        return FileConflictPreflightResponse.model_validate(
            to_file_conflict_preflight(result)
        )

    @staticmethod
    def _batch_response(result) -> FileConflictBatchResult:
        return FileConflictBatchResult.model_validate(to_upload_batch_result(result))

    def preflight_conflicts(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        payload: FileConflictPreflightRequest,
    ) -> FileConflictPreflightResponse:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        sources = payload.sources or []
        with self._kb_context(kb, access.access_role):
            try:
                if payload.operation == "upload":
                    result = self._engine().preflight_upload_files(
                        UploadFilesRequest(
                            locator=self._locator(kb.id),
                            target_path=payload.targetPath,
                            files=[
                                UploadItem(filename=item.sourcePath, content=b"")
                                for item in sources
                            ],
                        )
                    )
                elif payload.operation == "paste":
                    result = self._engine().preflight_copy_entries(
                        CopyEntriesRequest(
                            locator=self._locator(kb.id),
                            source_paths=[item.sourcePath for item in sources],
                            target_path=payload.targetPath,
                        )
                    )
                else:
                    if not payload.archivePath:
                        raise FileManagementException(
                            "INVALID_ARCHIVE",
                            "archivePath is required for extract preflight",
                            {},
                            400,
                        )
                    archive = self._engine().read_bytes(
                        ReadBytesRequest(
                            locator=self._locator(kb.id),
                            path=payload.archivePath,
                        )
                    )
                    result = self._engine().preflight_extract_archive(
                        ExtractArchiveRequest(
                            locator=self._locator(kb.id),
                            target_path=payload.targetPath,
                            archive_name=Path(payload.archivePath).name,
                            archive_bytes=archive.content,
                        )
                    )
            except FileCoreError as exc:
                raise self._map_core_error(exc, payload.targetPath, kb.id) from exc
        return self._preflight_response(result)

    async def upload_files(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        target_path: str,
        files: list[UploadFile],
        default_strategy: str,
        resolutions: Sequence[FileConflictResolution],
    ) -> FileConflictBatchResult:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        upload_items: list[UploadItem] = []
        for upload_file in files:
            upload_items.append(
                UploadItem(
                    filename=upload_file.filename or "",
                    content=await upload_file.read(),
                )
            )

        with self._kb_context(kb, access.access_role), kb_file_write_barrier(
            kb.id, operation_name="upload_files"
        ):
            try:
                result = self._engine().upload_files(
                    UploadFilesRequest(
                        locator=self._locator(kb.id),
                        target_path=target_path,
                        files=upload_items,
                        default_strategy=default_strategy,
                        resolutions=self._core_resolutions(resolutions),
                    )
                )
            except FileCoreError as exc:
                raise self._map_core_error(exc, target_path, kb.id) from exc

        return self._batch_response(result)

    def paste_entries(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        payload: FileConflictExecutionRequest,
    ) -> FileConflictBatchResult:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        with self._kb_context(kb, access.access_role), kb_file_write_barrier(
            kb.id, operation_name="paste_entries"
        ):
            try:
                result = self._engine().copy_entries(
                    CopyEntriesRequest(
                        locator=self._locator(kb.id),
                        source_paths=[item.sourcePath for item in payload.sources],
                        target_path=payload.targetPath,
                        default_strategy=payload.defaultStrategy,
                        resolutions=self._core_resolutions(payload.resolutions),
                    )
                )
            except FileCoreError as exc:
                raise self._map_core_error(exc, payload.targetPath, kb.id) from exc
        return self._batch_response(result)

    def extract_archive(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        payload: FileExtractExecutionRequest,
    ) -> FileConflictBatchResult:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        with self._kb_context(kb, access.access_role), kb_file_write_barrier(
            kb.id, operation_name="extract_archive"
        ):
            try:
                archive = self._engine().read_bytes(
                    ReadBytesRequest(
                        locator=self._locator(kb.id), path=payload.archivePath
                    )
                )
                result = self._engine().extract_archive(
                    ExtractArchiveRequest(
                        locator=self._locator(kb.id),
                        target_path=payload.targetPath,
                        archive_name=Path(payload.archivePath).name,
                        archive_bytes=archive.content,
                        default_strategy=payload.defaultStrategy,
                        resolutions=self._core_resolutions(payload.resolutions),
                    )
                )
            except FileCoreError as exc:
                raise self._map_core_error(exc, payload.targetPath, kb.id) from exc
        return self._batch_response(result)

    def build_archive_bytes(
        self, *, kb_id: str, paths: list[str]
    ) -> ArchiveBytesResult:
        try:
            return self._engine().build_archive_bytes(
                BuildArchiveRequest(locator=self._locator(kb_id), paths=paths)
            )
        except FileCoreError as exc:
            error_path = paths[0] if paths else "/"
            raise self._map_core_error(exc, error_path, kb_id) from exc

    def search_entries(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        query: str,
        path: str = "/",
        include_content: bool = True,
        case_sensitive: bool = False,
        max_results: Optional[int] = None,
    ) -> dict:
        self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        try:
            result = self._engine().search(
                SearchRequest(
                    locator=self._locator(kb_id),
                    query=query,
                    path=path,
                    include_content=include_content,
                    case_sensitive=case_sensitive,
                    max_results=max_results,
                )
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, path, kb_id) from exc
        return {
            "query": query,
            "path": path,
            "scope": self._scope(kb_id),
            "results": [
                {
                    "path": self._to_api_path(match.path),
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

    def list_history(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        path: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        normalized_path = None
        if path is not None:
            try:
                normalized_path = (
                    self._engine()
                    .adapter.resolve_path(
                        self._locator(kb.id),
                        path,
                    )
                    .relative_path
                )
            except FileCoreError as exc:
                raise self._map_core_error(exc, path, kb.id) from exc
        return {
            "items": self.local_history.list_entries(
                domain="knowledge-base",
                resource_id=kb.id,
                path=normalized_path,
                limit=limit,
            )
        }

    def restore_history(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        entry_id: str,
        revision: Optional[str] = None,
    ) -> dict:
        kb, access = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_CONTENT_WRITE,
        )
        try:
            entry = self.local_history.get_entry(
                domain="knowledge-base",
                resource_id=kb.id,
                entry_id=entry_id,
            )
        except KeyError as exc:
            raise FileManagementException(
                code="LOCAL_HISTORY_ENTRY_NOT_FOUND",
                message="Local history entry not found",
                details={"entryId": entry_id},
                status_code=404,
            ) from exc
        if not entry.snapshot_path:
            raise FileNotFoundException(entry.path, self._scope(kb.id))
        snapshot_path = Path(entry.snapshot_path)
        if not snapshot_path.exists() or not snapshot_path.is_file():
            raise FileNotFoundException(entry.path, self._scope(kb.id))

        try:
            target = (
                self._engine()
                .adapter.resolve_path(
                    self._locator(kb.id),
                    entry.path,
                )
                .absolute_path
            )
        except FileCoreError as exc:
            raise self._map_core_error(exc, entry.path, kb.id) from exc
        if target.exists() and revision is None:
            current = self.read_file(
                actor=actor,
                kb_id=kb.id,
                path=entry.path,
            )
            raise FileManagementException(
                code="CONTENT_CONFLICT",
                message=KB_CONTENT_CONFLICT_MESSAGE,
                details={
                    "path": entry.path,
                    "expectedRevision": None,
                    "actualRevision": current.revision,
                },
                status_code=409,
            )

        content = snapshot_path.read_bytes()
        try:
            with self._kb_context(kb, access.access_role):
                write_result = self._engine().write_bytes(
                    WriteBytesRequest(
                        locator=self._locator(kb.id),
                        path=entry.path,
                        content=content,
                        operation="restore",
                        expected_version_id=revision,
                    )
                )
        except VersionConflictError as exc:
            raise self._map_core_error(exc, entry.path, kb.id) from exc
        except FileCoreError as exc:
            raise self._map_core_error(exc, entry.path, kb.id) from exc

        return {
            "path": entry.path,
            "restoredFrom": entry.id,
            "revision": write_result.version_id,
        }

    def _scope(self, kb_id: str) -> str:
        return f"kb:{kb_id}"

    def _get_kb_by_id(self, kb_id: str) -> db_models.KnowledgeBase:
        kb = self.db.execute(
            select(db_models.KnowledgeBase).where(db_models.KnowledgeBase.id == kb_id)
        ).scalar_one_or_none()
        if kb is None:
            raise FileManagementException(
                code="KNOWLEDGE_BASE_NOT_FOUND",
                message="Knowledge base not found",
                details={"kbId": kb_id},
                status_code=404,
            )
        return kb

    def _kb_root(self, kb_id: str) -> Path:
        return ensure_knowledge_base_storage_root(self.storage_root, kb_id)

    def _check_quota(self, kb: db_models.KnowledgeBase, delta_bytes: int) -> None:
        enforce_knowledge_base_storage_quota(
            db=self.db,
            knowledge_base=kb,
            delta_bytes=delta_bytes,
            default_knowledge_base_quota_bytes=self.settings.DEFAULT_KB_QUOTA_BYTES,
            default_owner_quota_bytes=self.settings.DEFAULT_USER_KB_QUOTA_BYTES,
            knowledge_base_quota_message=KB_QUOTA_EXCEEDED_MESSAGE,
            owner_quota_message=KB_OWNER_QUOTA_EXCEEDED_MESSAGE,
        )

    def _update_kb_size(
        self, kb: db_models.KnowledgeBase, delta_bytes: int
    ) -> str | None:
        previous_size = kb.current_size_bytes
        current_size = max(0, previous_size + delta_bytes)
        kb.current_size_bytes = current_size
        occurred_at = datetime.now(timezone.utc)
        kb.updated_at = occurred_at
        effective_quota = (
            kb.quota_bytes
            if kb.quota_bytes is not None
            else self.settings.DEFAULT_KB_QUOTA_BYTES
        )
        return PlatformResourceActivityLedger(self.db).record_capacity_transition(
            resource_type="knowledge_base",
            resource_id=kb.id,
            storage_kind="knowledge_base",
            previous_used_bytes=previous_size,
            current_used_bytes=current_size,
            allocated_bytes=effective_quota,
            source="manager",
            occurred_at=occurred_at,
        )
