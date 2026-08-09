"""Knowledge base archive background operations."""

from __future__ import annotations

import posixpath
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aileron_file_core import (
    BackgroundFileOperation,
    BackgroundFileOperationStore,
)
from sqlalchemy.orm import Session

from app.core.file_management import (
    FileManagementException,
)
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import OperationId
from app.modules.knowledge_base.files import KnowledgeBaseFileService
from app.modules.knowledge_base.models import (
    ArchiveDownloadResult,
    ArchiveDownloadStatusResponse,
)

ARCHIVE_DOWNLOAD_TEMP_DIR = Path(tempfile.gettempdir()) / "aileron-kb-archive-downloads"
ARCHIVE_DOWNLOAD_TTL_SECONDS = 15 * 60


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


class KnowledgeBaseArchiveService:
    """Create and track knowledge base archive operations."""

    def __init__(self, db: Session) -> None:
        self.file_service = KnowledgeBaseFileService(db)

    def create_archive_operation(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        paths: list[str],
        archive_name: str | None,
    ) -> tuple[BackgroundFileOperation[ArchiveDownloadResult], str]:
        self.file_service.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._cleanup_expired_archive_operations()
        operation = _archive_operation_store.create(
            scope_key=kb_id,
            message="Preparing ZIP download...",
        )
        operation_archive_name = self._sanitize_archive_name(archive_name, paths)
        return operation, operation_archive_name

    def run_archive_operation(
        self, *, kb_id: str, operation_id: str, paths: list[str], archive_name: str
    ) -> None:
        try:
            self._update_archive_operation(
                kb_id,
                operation_id,
                status_value="running",
                progress=0.02,
                message="Scanning selected files...",
            )
            archive_result = self.file_service.build_archive_bytes(
                kb_id=kb_id, paths=paths
            )
            if not archive_result.entries:
                raise FileManagementException(
                    "ARCHIVE_DOWNLOAD_EMPTY",
                    "No files are available to package",
                    {"paths": paths},
                    400,
                )

            ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
            temp_path = ARCHIVE_DOWNLOAD_TEMP_DIR / f"{operation_id}.zip"
            temp_path.write_bytes(archive_result.content)
            self._update_archive_operation(
                kb_id,
                operation_id,
                status_value="running",
                progress=0.95,
                message=f"Packaging {len(archive_result.entries)}/{len(archive_result.entries)} files...",
            )

            expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=ARCHIVE_DOWNLOAD_TTL_SECONDS
            )
            result = ArchiveDownloadResult(
                archiveName=archive_name,
                size=temp_path.stat().st_size,
                downloadUrl=f"/api/v1/knowledge-bases/{kb_id}/files/archive/{operation_id}/download",
                expiresAt=expires_at,
            )
            self._update_archive_operation(
                kb_id,
                operation_id,
                status_value="completed",
                progress=1.0,
                message=f"Archive ready, {len(archive_result.entries)} files packaged",
                result=result,
                temp_path=temp_path,
                expires_at=expires_at,
            )
        except FileManagementException as exc:
            self._update_archive_operation(
                kb_id,
                operation_id,
                status_value="failed",
                message=exc.message,
                error=exc.message,
            )
        except Exception as exc:  # pragma: no cover - guarded by integration tests
            self._update_archive_operation(
                kb_id,
                operation_id,
                status_value="failed",
                message=f"Archive packaging failed: {exc}",
                error=str(exc),
            )

    def get_archive_status(
        self, *, actor: AuthorizationActor, kb_id: str, operation_id: str
    ) -> ArchiveDownloadStatusResponse:
        self.file_service.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._cleanup_expired_archive_operations()
        operation = _archive_operation_store.get(
            scope_key=kb_id,
            operation_id=operation_id,
        )
        if operation is None:
            raise FileManagementException(
                "ARCHIVE_OPERATION_NOT_FOUND",
                f"Archive operation not found: {operation_id}",
                {"operationId": operation_id},
                404,
            )
        return _archive_operation_response(operation)

    def resolve_archive_download(
        self, *, actor: AuthorizationActor, kb_id: str, operation_id: str
    ) -> tuple[Path, str]:
        self.file_service.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        self._cleanup_expired_archive_operations()
        operation = _archive_operation_store.get(
            scope_key=kb_id,
            operation_id=operation_id,
        )
        if operation is None:
            raise FileManagementException(
                "ARCHIVE_OPERATION_NOT_FOUND",
                f"Archive operation not found: {operation_id}",
                {"operationId": operation_id},
                404,
            )
        if (
            operation.status != "completed"
            or not operation.result
            or not operation.artifact_path
        ):
            raise FileManagementException(
                "ARCHIVE_OPERATION_NOT_READY",
                f"Archive operation is not ready: {operation_id}",
                {"operationId": operation_id, "status": operation.status},
                409,
            )
        if not operation.artifact_path.exists():
            raise FileManagementException(
                "ARCHIVE_FILE_NOT_FOUND",
                f"Archive file not found: {operation_id}",
                {"operationId": operation_id},
                404,
            )
        return operation.artifact_path, operation.result.archive_name

    def _update_archive_operation(
        self,
        kb_id: str,
        operation_id: str,
        *,
        status_value: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        error: str | None = None,
        result: ArchiveDownloadResult | None = None,
        temp_path: Path | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        _archive_operation_store.update(
            scope_key=kb_id,
            operation_id=operation_id,
            status=status_value,
            progress=progress,
            message=message,
            error=error,
            result=result,
            artifact_path=temp_path,
            expires_at=expires_at,
        )

    def _cleanup_expired_archive_operations(self) -> None:
        ARCHIVE_DOWNLOAD_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        _archive_operation_store.cleanup_expired()

    def _sanitize_archive_name(self, archive_name: str | None, paths: list[str]) -> str:
        candidate = Path(archive_name).name.strip() if archive_name else ""
        if not candidate:
            if len(paths) == 1:
                base = posixpath.basename(paths[0].rstrip("/")) or "knowledge-base"
                candidate = f"{base}.zip"
            else:
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
                candidate = f"knowledge-base-selection-{timestamp}.zip"
        candidate = re.sub(r"[^A-Za-z0-9._ -]+", "_", candidate).strip(" .")
        if not candidate:
            candidate = "archive.zip"
        if not candidate.lower().endswith(".zip"):
            candidate = f"{candidate}.zip"
        return candidate
