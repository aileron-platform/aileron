"""Slash Command 服務"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, status

from ..common import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    format_file_size,
    iter_requested_scopes,
)
from .models import (
    SlashCommandCreateRequest,
    SlashCommandDocumentDetail,
    SlashCommandDocumentResponse,
    SlashCommandDocumentSummary,
    SlashCommandScopeGroup,
    SlashCommandScopeResponse,
    SlashCommandScopesResponse,
    SlashCommandUpdateRequest,
)

logger = logging.getLogger(__name__)


class SlashCommandService:
    """管理 Slash Commands 的檔案服務"""

    def __init__(self) -> None:
        self._repository = ScopedMarkdownRepository("commands", supports_namespace=True)

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> SlashCommandScopesResponse:
        """
        列出所有 slash commands

        修改：自動整合 plugin commands
        """
        groups = []

        # 1. 載入檔案系統的 commands（project/user/local）
        # 如果查詢的是 PLUGIN scope，跳過檔案系統載入
        if scope != DocumentScope.PLUGIN:
            for scope_item in iter_requested_scopes(scope, allow_local=False, allow_plugin=False):
                records = self._repository.list_records(workspace_id, scope_item)
                documents = [self._to_summary(record) for record in records]
                documents.sort(key=lambda item: item.file_name)
                groups.append(SlashCommandScopeGroup(scope=scope_item, documents=documents))

        # 2. 載入 plugin commands（從 plugin loader）
        if scope is None or scope == DocumentScope.PLUGIN:
            try:
                plugin_commands = self._load_plugin_commands(workspace_id)
                if plugin_commands:
                    groups.append(
                        SlashCommandScopeGroup(
                            scope=DocumentScope.PLUGIN,
                            documents=plugin_commands
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to load plugin commands: {e}")

        return SlashCommandScopesResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> SlashCommandScopeResponse:
        records = self._repository.list_records(workspace_id, scope)
        documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.file_name)
        return SlashCommandScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            documents=documents,
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> SlashCommandDocumentResponse:
        # 如果是 PLUGIN scope，從 plugin 載入
        if scope == DocumentScope.PLUGIN:
            return self._get_plugin_document(workspace_id, file_name)

        # 否則從檔案系統載入
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
        detail = SlashCommandDocumentDetail(**summary.model_dump(), content=record.content)
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SlashCommandCreateRequest,
    ) -> SlashCommandDocumentResponse:
        try:
            record = self._repository.create_record(
                workspace_id,
                scope,
                payload.file_name,
                payload.content,
                namespace=payload.namespace,
            )
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_FILE_NAME", "message": str(error)},
            ) from error
        summary = self._to_summary(
            record,
            fallback_namespace=payload.namespace,
        )
        detail = SlashCommandDocumentDetail(**summary.model_dump(), content=record.content)
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: SlashCommandUpdateRequest,
    ) -> SlashCommandDocumentResponse:
        try:
            record = self._repository.update_record(
                workspace_id,
                scope,
                file_name,
                payload.content,
                namespace=payload.namespace,
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
            fallback_namespace=payload.namespace,
        )
        detail = SlashCommandDocumentDetail(**summary.model_dump(), content=record.content)
        return SlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def delete_document(self, workspace_id: str, scope: DocumentScope, file_name: str) -> None:
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

    def _load_plugin_commands(
        self,
        workspace_id: str
    ) -> list[SlashCommandDocumentSummary]:
        """載入 plugin commands

        Returns:
            List[SlashCommandDocumentSummary]: 包含 pluginName 和 marketplaceName 的文檔
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
                        fileName=cmd.file_name,
                        namespace=None,
                        description=cmd.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        pluginName=cmd.plugin_name,
                        marketplaceName=cmd.marketplace_name
                    )
                )
            except (OSError, IOError) as e:
                logger.error(f"Failed to read plugin command {cmd.file_path}: {e}")

        return documents

    def _get_plugin_document(
        self, workspace_id: str, file_name: str
    ) -> SlashCommandDocumentResponse:
        """從 plugin 載入單個文檔"""
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        plugin_commands = loader.load_plugin_commands(workspace_id)

        for cmd in plugin_commands:
            if cmd.file_name == file_name:
                try:
                    content = Path(cmd.file_path).read_text(encoding="utf-8")
                    file_size = Path(cmd.file_path).stat().st_size
                    size_str = format_file_size(file_size)

                    detail = SlashCommandDocumentDetail(
                        fileName=cmd.file_name,
                        namespace=None,
                        description=cmd.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        content=content,
                        pluginName=cmd.plugin_name,
                        marketplaceName=cmd.marketplace_name
                    )

                    return SlashCommandDocumentResponse(
                        workspaceId=workspace_id,
                        scope=DocumentScope.PLUGIN,
                        document=detail,
                    )
                except (OSError, IOError) as e:
                    logger.error(f"Failed to read plugin command {cmd.file_path}: {e}")
                    raise HTTPException(
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail={"error": "PLUGIN_READ_ERROR", "message": str(e)},
                    ) from e

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"error": "404_NOT_FOUND", "message": file_name},
        )

    def _to_summary(
        self,
        record: MarkdownDocumentRecord,
        *,
        fallback_description: str | None = None,
        fallback_namespace: str | None = None,
    ) -> SlashCommandDocumentSummary:
        metadata = record.metadata_with_fallbacks(
            fallback_description=fallback_description,
            fallback_namespace=fallback_namespace,
        )
        namespace = metadata.get("namespace") or metadata.get("category")
        if namespace is None:
            namespace = fallback_namespace or record.namespace or None
        description = metadata.get("description") or fallback_description
        return SlashCommandDocumentSummary(
            fileName=record.file_name,
            namespace=namespace or None,
            description=description,
            scope=record.scope,
            size=record.size_label,
        )
