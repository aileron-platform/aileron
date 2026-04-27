"""Output Styles Service"""

from __future__ import annotations

from fastapi import HTTPException, status

from pathlib import Path

from ..common import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    iter_requested_scopes,
    read_json_file,
    resolve_scope_root,
    write_json_file,
)
from .models import (
    OutputStyleCollectionResponse,
    OutputStyleCreateRequest,
    OutputStyleDeleteResponse,
    OutputStyleDocument,
    OutputStyleDocumentResponse,
    OutputStyleScopeGroup,
    OutputStyleScopeResponse,
    OutputStyleSummary,
    OutputStyleUpdateRequest,
)


class OutputStyleService:
    """Service for managing output style settings"""

    def __init__(self) -> None:
        self._repository = ScopedMarkdownRepository("output-styles")

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> OutputStyleCollectionResponse:
        groups = []
        for scope_item in iter_requested_scopes(scope, allow_local=False):
            records = self._repository.list_records(workspace_id, scope_item)
            documents = [self._to_summary(record) for record in records]
            documents.sort(key=lambda item: item.file_name)
            groups.append(OutputStyleScopeGroup(scope=scope_item, documents=documents))
        return OutputStyleCollectionResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> OutputStyleScopeResponse:
        records = self._repository.list_records(workspace_id, scope)
        documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.file_name)
        return OutputStyleScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            documents=documents,
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> OutputStyleDocumentResponse:
        try:
            record = self._repository.get_record(workspace_id, scope, file_name)
        except AmbiguousDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "AMBIGUOUS_DOCUMENT", "message": str(error)},
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = OutputStyleDocument(**summary.model_dump(), content=record.content)
        return OutputStyleDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: OutputStyleCreateRequest,
    ) -> OutputStyleDocumentResponse:
        try:
            record = self._repository.create_record(
                workspace_id,
                scope,
                payload.file_name,
                payload.content,
            )
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_FILE_NAME", "message": str(error)},
            ) from error
        self._ensure_default_selection(workspace_id, scope, record.file_name)
        summary = self._to_summary(
            record,
            fallback_name=payload.name,
            fallback_description=payload.description,
        )
        detail = OutputStyleDocument(**summary.model_dump(), content=record.content)
        return OutputStyleDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: OutputStyleUpdateRequest,
    ) -> OutputStyleDocumentResponse:
        try:
            record = self._repository.update_record(
                workspace_id,
                scope,
                file_name,
                payload.content,
            )
        except AmbiguousDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "AMBIGUOUS_DOCUMENT", "message": str(error)},
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": str(error)},
            ) from error
        summary = self._to_summary(
            record,
            fallback_name=payload.name,
            fallback_description=payload.description,
        )
        detail = OutputStyleDocument(**summary.model_dump(), content=record.content)
        return OutputStyleDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> OutputStyleDeleteResponse:
        try:
            self._repository.delete_record(workspace_id, scope, file_name)
        except AmbiguousDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "AMBIGUOUS_DOCUMENT", "message": str(error)},
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": str(error)},
            ) from error
        self._clear_default_selection(workspace_id, scope, file_name)
        return OutputStyleDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            fileName=file_name,
            deleted=True,
        )

    def _to_summary(
        self,
        record: MarkdownDocumentRecord,
        *,
        fallback_name: str | None = None,
        fallback_description: str | None = None,
    ) -> OutputStyleSummary:
        metadata = record.metadata_with_fallbacks(
            fallback_name=fallback_name,
            fallback_description=fallback_description,
        )
        name = metadata.get("name")
        if not name:
            name = record.file_name
        description = metadata.get("description") or fallback_description
        return OutputStyleSummary(
            fileName=record.file_name,
            name=name,
            description=description,
            scope=record.scope,
            size=record.size_label,
        )

    def _settings_file(self, workspace_id: str, scope: DocumentScope) -> Path | None:
        if scope == DocumentScope.USER:
            return resolve_scope_root(workspace_id, DocumentScope.USER) / "settings.json"
        project_root = resolve_scope_root(workspace_id, DocumentScope.PROJECT)
        if scope == DocumentScope.PROJECT:
            return project_root / "settings.json"
        if scope == DocumentScope.LOCAL:
            return project_root / "settings.local.json"
        return None

    def _ensure_default_selection(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> None:
        settings_path = self._settings_file(workspace_id, scope)
        if settings_path is None:
            return
        data = read_json_file(settings_path)
        if data.get("outputStyle"):
            return
        data["outputStyle"] = file_name
        write_json_file(settings_path, data)

    def _clear_default_selection(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> None:
        settings_path = self._settings_file(workspace_id, scope)
        if settings_path is None:
            return
        data = read_json_file(settings_path)
        if data.get("outputStyle") != file_name:
            return
        data.pop("outputStyle", None)
        if data:
            write_json_file(settings_path, data)
        elif settings_path.exists():
            settings_path.unlink()
