"""Slash Command Service"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.codecs import (
    MarkdownDirectoryCodec,
    read_text,
)

from ..documents import (
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    InvalidDocumentFileNameError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    format_file_size,
    iter_requested_scopes,
)
from .models import (
    SlashCommandCreateRequest,
    SlashCommandAvailableScope,
    SlashCommandDeleteResponse,
    SlashCommandDocumentDetail,
    SlashCommandDocumentResponse,
    SlashCommandDocumentSummary,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)

logger = logging.getLogger(__name__)
_MARKDOWN_CODEC = MarkdownDirectoryCodec()
_write_locks_guard = Lock()
_write_locks: dict[str, Lock] = {}


def _write_lock(key: str) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(key, Lock())


class SlashCommandService:
    """File service for managing Slash Commands"""

    def __init__(self) -> None:
        self._repository = ScopedMarkdownRepository("commands")

    def list_scopes(
        self,
        workspace_id: str,
        scope: DocumentScope | None = None,
        *,
        strict_plugin_errors: bool = False,
    ) -> SlashCommandScopesResponse:
        """List slash commands, including plugin commands when requested."""
        items: list[SlashCommandDocumentSummary] = []
        available_scopes: list[SlashCommandAvailableScope] = []

        # Load commands from file system (project/user/local).
        if scope != DocumentScope.PLUGIN:
            for scope_item in iter_requested_scopes(
                scope, allow_local=False, allow_plugin=False
            ):
                records = self._repository.list_records(workspace_id, scope_item)
                documents = [self._to_summary(record) for record in records]
                documents.sort(key=lambda item: item.path)
                items.extend(documents)
                available_scopes.append(
                    SlashCommandAvailableScope(scope=scope_item, readOnly=False)
                )

        # Load plugin commands from the plugin inventory.
        if scope is None or scope == DocumentScope.PLUGIN:
            available_scopes.append(
                SlashCommandAvailableScope(scope=DocumentScope.PLUGIN, readOnly=True)
            )
            try:
                plugin_commands = self._load_plugin_commands(
                    workspace_id,
                    strict_errors=strict_plugin_errors,
                )
                if plugin_commands:
                    items.extend(plugin_commands)
            except Exception as e:
                if strict_plugin_errors:
                    raise
                logger.error(f"Failed to load plugin commands: {e}")

        items.sort(key=lambda item: (item.scope.value, item.path))
        return SlashCommandScopesResponse(
            workspaceId=workspace_id,
            items=items,
            availableScopes=available_scopes,
        )

    def get_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> SlashCommandScopeResponse:
        records = self._repository.list_records(workspace_id, scope)
        documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.path)
        return SlashCommandScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._scope_revision(records),
            documents=documents,
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, path: str
    ) -> SlashCommandDocumentResponse:
        # If PLUGIN scope, load from plugin
        if scope == DocumentScope.PLUGIN:
            return self._get_plugin_document(workspace_id, path)

        # Otherwise load from file system
        try:
            record = self._load_record_by_path(workspace_id, scope, path)
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "404_NOT_FOUND", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = SlashCommandDocumentDetail(
            **summary.model_dump(), content=record.content
        )
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._record_revision(record),
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SlashCommandCreateRequest,
    ) -> SlashCommandDocumentResponse:
        try:
            with _write_lock(f"{workspace_id}:{scope.value}:slash-commands"):
                records = self._repository.list_records(workspace_id, scope)
                assert_revision(self._scope_revision(records), payload.revision)
                record = self._create_record_by_path(
                    workspace_id, scope, payload.path, payload.content
                )
        except InvalidDocumentFileNameError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": "INVALID_SLASH_COMMAND_PATH",
                    "message": str(error),
                },
            ) from error
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"errorCode": "DUPLICATE_PATH", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = SlashCommandDocumentDetail(
            **summary.model_dump(), content=record.content
        )
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._record_revision(record),
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SlashCommandUpdateRequest,
    ) -> SlashCommandDocumentResponse:
        try:
            with _write_lock(f"{workspace_id}:{scope.value}:slash-commands"):
                current = self._load_record_by_path(workspace_id, scope, payload.path)
                assert_revision(self._record_revision(current), payload.revision)
                record = self._update_record_by_path(
                    workspace_id, scope, payload.path, payload.content
                )
        except InvalidDocumentFileNameError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": "INVALID_SLASH_COMMAND_PATH",
                    "message": str(error),
                },
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "404_NOT_FOUND", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = SlashCommandDocumentDetail(
            **summary.model_dump(), content=record.content
        )
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._record_revision(record),
            document=detail,
        )

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, path: str, revision: str
    ) -> SlashCommandDeleteResponse:
        try:
            with _write_lock(f"{workspace_id}:{scope.value}:slash-commands"):
                current = self._load_record_by_path(workspace_id, scope, path)
                assert_revision(self._record_revision(current), revision)
                self._delete_record_by_path(workspace_id, scope, path)
                records = self._repository.list_records(workspace_id, scope)
        except InvalidDocumentFileNameError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": "INVALID_SLASH_COMMAND_PATH",
                    "message": str(error),
                },
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "404_NOT_FOUND", "message": str(error)},
            ) from error
        return SlashCommandDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            path=self._normalize_path(path).as_posix(),
            revision=self._scope_revision(records),
            deleted=True,
        )

    def _load_plugin_commands(
        self,
        workspace_id: str,
        *,
        strict_errors: bool = False,
    ) -> list[SlashCommandDocumentSummary]:
        """Load plugin commands

        Returns:
            List[SlashCommandDocumentSummary]: Documents with pluginName and marketplaceName
        """
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        plugin_commands = loader.load_plugin_commands(workspace_id)

        documents = []
        for cmd in plugin_commands:
            try:
                file_size = Path(cmd.file_path).stat().st_size
                size_str = format_file_size(file_size)

                documents.append(
                    SlashCommandDocumentSummary(
                        path=cmd.file_name,
                        description=cmd.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        pluginName=cmd.plugin_name,
                        marketplaceName=cmd.marketplace_name,
                    )
                )
            except (OSError, IOError) as e:
                if strict_errors:
                    raise
                logger.error(f"Failed to read plugin command {cmd.file_path}: {e}")

        return documents

    def _get_plugin_document(
        self, workspace_id: str, path: str
    ) -> SlashCommandDocumentResponse:
        """Load single document from plugin"""
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        plugin_commands = loader.load_plugin_commands(workspace_id)

        for cmd in plugin_commands:
            if cmd.file_name == path:
                try:
                    content = read_text(Path(cmd.file_path))
                    file_size = Path(cmd.file_path).stat().st_size
                    size_str = format_file_size(file_size)

                    detail = SlashCommandDocumentDetail(
                        path=cmd.file_name,
                        description=cmd.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        content=content,
                        pluginName=cmd.plugin_name,
                        marketplaceName=cmd.marketplace_name,
                    )

                    return SlashCommandDocumentResponse(
                        workspaceId=workspace_id,
                        scope=DocumentScope.PLUGIN,
                        revision=compute_revision(content),
                        document=detail,
                    )
                except (OSError, IOError) as e:
                    logger.error(f"Failed to read plugin command {cmd.file_path}: {e}")
                    raise HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"errorCode": "PLUGIN_READ_ERROR", "message": str(e)},
                    ) from e

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"errorCode": "404_NOT_FOUND", "message": path},
        )

    def _to_summary(
        self,
        record: MarkdownDocumentRecord,
        *,
        fallback_description: str | None = None,
    ) -> SlashCommandDocumentSummary:
        metadata = record.metadata_with_fallbacks(
            fallback_description=fallback_description,
        )
        description = metadata.get("description") or fallback_description
        return SlashCommandDocumentSummary(
            path=self._record_path(record),
            description=description,
            scope=record.scope,
            size=record.size_label,
            pluginName=None,
            marketplaceName=None,
        )

    @staticmethod
    def _normalize_path(raw_path: str) -> Path:
        clean_path = raw_path.strip()
        if not clean_path or "\\" in clean_path:
            raise InvalidDocumentFileNameError(raw_path)
        path = Path(clean_path)
        if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
            raise InvalidDocumentFileNameError(raw_path)
        if path.suffix and path.suffix.lower() != ".md":
            raise InvalidDocumentFileNameError(raw_path)
        if not path.suffix:
            path = path.with_name(f"{path.name}.md")
        return path

    @staticmethod
    def _record_path(record: MarkdownDocumentRecord) -> str:
        return record.file_path.relative_to(record.root_path).as_posix()

    def _path_for(
        self, workspace_id: str, scope: DocumentScope, raw_path: str
    ) -> tuple[Path, Path]:
        directory = self._repository._directory(workspace_id, scope)
        return directory, directory / self._normalize_path(raw_path)

    def _load_record_by_path(
        self, workspace_id: str, scope: DocumentScope, raw_path: str
    ) -> MarkdownDocumentRecord:
        directory, file_path = self._path_for(workspace_id, scope, raw_path)
        if not file_path.exists():
            raise DocumentNotFoundError(raw_path)
        return self._repository._load_record(file_path, scope, directory)

    def _create_record_by_path(
        self, workspace_id: str, scope: DocumentScope, raw_path: str, content: str
    ) -> MarkdownDocumentRecord:
        directory, file_path = self._path_for(workspace_id, scope, raw_path)
        if file_path.exists():
            raise DuplicateDocumentError(raw_path)
        _MARKDOWN_CODEC.write(file_path, content)
        return self._repository._load_record(file_path, scope, directory)

    def _update_record_by_path(
        self, workspace_id: str, scope: DocumentScope, raw_path: str, content: str
    ) -> MarkdownDocumentRecord:
        directory, file_path = self._path_for(workspace_id, scope, raw_path)
        if not file_path.exists():
            raise DocumentNotFoundError(raw_path)
        _MARKDOWN_CODEC.write(file_path, content)
        return self._repository._load_record(file_path, scope, directory)

    def _delete_record_by_path(
        self, workspace_id: str, scope: DocumentScope, raw_path: str
    ) -> None:
        _directory, file_path = self._path_for(workspace_id, scope, raw_path)
        if not file_path.exists():
            raise DocumentNotFoundError(raw_path)
        _MARKDOWN_CODEC.remove(file_path)

    @staticmethod
    def _record_revision(record: MarkdownDocumentRecord) -> str:
        return compute_revision(record.content)

    def _scope_revision(self, records: list[MarkdownDocumentRecord]) -> str:
        content_by_path = {
            self._record_key(record): record.content
            for record in sorted(records, key=self._record_key)
        }
        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    @staticmethod
    def _record_key(record: MarkdownDocumentRecord) -> str:
        return record.file_path.relative_to(record.root_path).as_posix()
