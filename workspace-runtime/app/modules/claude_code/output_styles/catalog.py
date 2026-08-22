"""Output Styles Service"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from threading import Lock
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.codecs import (
    read_text,
    remove_file_exact,
)
from app.modules.cli_settings.user_scope.models import (
    UserScopeAgent,
    UserScopeResource,
)
from app.modules.cli_settings.user_scope.paths import get_user_scope_path_resolver
from app.modules.marketplace_operations.gate import get_marketplace_target_client_gate
from app.modules.marketplace_operations.plugin_resources import (
    plugin_resource_provenance,
)

from ..documents import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    format_file_size,
    iter_requested_scopes,
    parse_front_matter,
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

if TYPE_CHECKING:
    from ..plugins.loader import ComponentFileInfo, PluginComponentsLoader

_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


class OutputStyleService:
    """Service for managing output style settings"""

    def __init__(
        self,
        *,
        plugin_loader: PluginComponentsLoader | None = None,
    ) -> None:
        self._repository = ScopedMarkdownRepository("output-styles")
        self._plugin_loader = plugin_loader

    def list_scopes(
        self,
        workspace_id: str,
        scope: DocumentScope | None = None,
        *,
        plugin_id: str | None = None,
    ) -> OutputStyleCollectionResponse:
        groups = []
        if scope is not DocumentScope.PLUGIN:
            for scope_item in iter_requested_scopes(
                scope,
                allow_local=False,
                allow_plugin=False,
            ):
                records = self._repository.list_records(workspace_id, scope_item)
                documents = [self._to_summary(record) for record in records]
                documents.sort(key=lambda item: item.file_name)
                groups.append(
                    OutputStyleScopeGroup(
                        scope=scope_item,
                        revision=self._scope_revision(records),
                        documents=documents,
                    )
                )
        generation = None
        if self._plugin_loader is not None and (
            scope is None or scope is DocumentScope.PLUGIN
        ):
            plugin_styles = self._plugin_styles(workspace_id, plugin_id=plugin_id)
            generation = self._provider_generation()
            documents = [
                self._plugin_summary(item, generation=generation)
                for item in plugin_styles
            ]
            groups.append(
                OutputStyleScopeGroup(
                    scope=DocumentScope.PLUGIN,
                    revision=self._plugin_scope_revision(plugin_styles),
                    documents=documents,
                )
            )
        return OutputStyleCollectionResponse(
            workspaceId=workspace_id,
            scopes=groups,
            providerResourceGeneration=generation,
        )

    def get_scope(
        self,
        workspace_id: str,
        scope: DocumentScope,
        *,
        plugin_id: str | None = None,
    ) -> OutputStyleScopeResponse:
        if scope is DocumentScope.PLUGIN:
            plugin_styles = self._plugin_styles(workspace_id, plugin_id=plugin_id)
            generation = self._provider_generation()
            return OutputStyleScopeResponse(
                workspaceId=workspace_id,
                scope=scope,
                revision=self._plugin_scope_revision(plugin_styles),
                documents=[
                    self._plugin_summary(item, generation=generation)
                    for item in plugin_styles
                ],
                providerResourceGeneration=generation,
            )
        records = self._repository.list_records(workspace_id, scope)
        documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.file_name)
        return OutputStyleScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._scope_revision(records),
            documents=documents,
        )

    def get_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        *,
        plugin_id: str | None = None,
    ) -> OutputStyleDocumentResponse:
        if scope is DocumentScope.PLUGIN:
            return self._get_plugin_document(
                workspace_id,
                file_name,
                plugin_id=plugin_id,
            )
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
            revision=self._record_revision(record),
            document=detail,
        )

    def _plugin_styles(
        self,
        workspace_id: str,
        *,
        plugin_id: str | None,
    ) -> list[ComponentFileInfo]:
        if self._plugin_loader is None:
            return []
        styles = self._plugin_loader.load_plugin_output_styles(workspace_id)
        filtered = [
            item for item in styles if plugin_id is None or item.plugin_id == plugin_id
        ]
        return sorted(
            filtered,
            key=lambda item: (
                item.plugin_id or "",
                item.relative_source_path or item.file_name,
            ),
        )

    def _get_plugin_document(
        self,
        workspace_id: str,
        file_name: str,
        *,
        plugin_id: str | None,
    ) -> OutputStyleDocumentResponse:
        matches = [
            item
            for item in self._plugin_styles(workspace_id, plugin_id=plugin_id)
            if file_name == self._plugin_locator(item)
        ]
        if not matches:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={
                    "errorCode": "marketplace.settings.plugin_resource_not_found",
                },
            )
        if len(matches) > 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "errorCode": "marketplace.settings.plugin_resource_ambiguous",
                },
            )
        item = matches[0]
        content = self._read_plugin_content(item)
        generation = self._provider_generation()
        summary = self._plugin_summary(
            item,
            content=content,
            generation=generation,
        )
        return OutputStyleDocumentResponse(
            workspaceId=workspace_id,
            scope=DocumentScope.PLUGIN,
            revision=compute_revision(content),
            document=OutputStyleDocument(
                **summary.model_dump(),
                content=content,
            ),
            providerResourceGeneration=generation,
        )

    @staticmethod
    def _read_plugin_content(item: ComponentFileInfo) -> str:
        try:
            return read_text(Path(item.file_path))
        except (OSError, UnicodeError) as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={
                    "errorCode": "marketplace.settings.plugin_resource_not_found",
                },
            ) from error

    def _plugin_summary(
        self,
        item: ComponentFileInfo,
        *,
        content: str | None = None,
        generation: int,
    ) -> OutputStyleSummary:
        resolved_content = (
            content if content is not None else self._read_plugin_content(item)
        )
        metadata, _body = parse_front_matter(resolved_content)
        if not isinstance(metadata, dict):
            metadata = {}
        path = Path(item.file_path)
        try:
            size = format_file_size(path.stat().st_size)
        except OSError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={
                    "errorCode": "marketplace.settings.plugin_resource_not_found",
                },
            ) from error
        if not item.plugin_id or not item.marketplace_name:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "errorCode": "marketplace.settings.plugin_provenance_missing",
                },
            )
        return OutputStyleSummary(
            fileName=self._plugin_locator(item),
            name=str(metadata.get("name") or item.file_name),
            description=(
                str(metadata["description"])
                if metadata.get("description") is not None
                else item.description
            ),
            scope=DocumentScope.PLUGIN,
            size=size,
            readOnly=True,
            editable=False,
            pluginId=item.plugin_id,
            pluginName=item.plugin_name,
            marketplaceId=item.marketplace_name,
            enabled=item.enabled,
            relativeSourcePath=self._plugin_locator(item),
            generation=generation,
            provenance=plugin_resource_provenance(
                target_client="claude-code",
                plugin_id=item.plugin_id,
                marketplace_id=item.marketplace_name,
            ),
        )

    def _provider_generation(self) -> int:
        return get_marketplace_target_client_gate().generation("claude-code")

    @staticmethod
    def _plugin_locator(item: ComponentFileInfo) -> str:
        """Return the stable package-relative locator exposed by plugin APIs."""

        raw_locator = item.relative_source_path or item.file_name
        locator = PurePosixPath(raw_locator)
        if (
            not raw_locator
            or "\\" in raw_locator
            or locator.is_absolute()
            or locator.as_posix() in {"", "."}
            or any(part in {"", ".", ".."} for part in locator.parts)
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "errorCode": "marketplace.settings.plugin_resource_parse_failed",
                },
            )
        return locator.as_posix()

    def _plugin_scope_revision(
        self,
        styles: list[ComponentFileInfo],
    ) -> str:
        content_by_identity = {
            f"{item.plugin_id or ''}:{self._plugin_locator(item)}": (
                self._read_plugin_content(item)
            )
            for item in styles
        }
        return compute_revision(
            json.dumps(
                content_by_identity,
                sort_keys=True,
                separators=(",", ":"),
            )
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: OutputStyleCreateRequest,
    ) -> OutputStyleDocumentResponse:
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                assert_revision(
                    self._scope_revision(
                        self._repository.list_records(workspace_id, scope)
                    ),
                    payload.revision,
                )
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
            revision=self._record_revision(record),
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: OutputStyleUpdateRequest,
    ) -> OutputStyleDocumentResponse:
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                existing = self._repository.get_record(workspace_id, scope, file_name)
                assert_revision(self._record_revision(existing), payload.revision)
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
            revision=self._record_revision(record),
            document=detail,
        )

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str, *, revision: str
    ) -> OutputStyleDeleteResponse:
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                existing = self._repository.get_record(workspace_id, scope, file_name)
                assert_revision(self._record_revision(existing), revision)
                self._repository.delete_record(workspace_id, scope, file_name)
                scope_revision = self._scope_revision(
                    self._repository.list_records(workspace_id, scope)
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
        self._clear_default_selection(workspace_id, scope, file_name)
        return OutputStyleDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            fileName=file_name,
            revision=scope_revision,
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

    @staticmethod
    def _record_revision(record: MarkdownDocumentRecord) -> str:
        return compute_revision(record.content)

    @staticmethod
    def _scope_revision(records: list[MarkdownDocumentRecord]) -> str:
        content_by_path = {
            record.file_path.relative_to(record.root_path).as_posix(): record.content
            for record in records
        }
        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    def _settings_file(self, workspace_id: str, scope: DocumentScope) -> Path | None:
        if scope == DocumentScope.USER:
            return (
                get_user_scope_path_resolver()
                .resolve(
                    UserScopeAgent.CLAUDE_CODE,
                    UserScopeResource.SETTINGS,
                )
                .runtime_path
            )
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
            remove_file_exact(settings_path)
