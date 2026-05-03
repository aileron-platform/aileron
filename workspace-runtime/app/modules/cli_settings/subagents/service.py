"""CLI subagents service."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, status

from app.modules.claude_code.common import (
    AmbiguousDocumentError,
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    format_file_size,
    iter_requested_scopes,
)

from .config import SubagentToolConfig
from .models import (
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDocument,
    SubagentDocumentResponse,
    SubagentScopeGroup,
    SubagentScopeResponse,
    SubagentSummary,
    SubagentUpdateRequest,
)

logger = logging.getLogger(__name__)


class SubagentService:
    """Service for managing CLI subagent markdown files."""

    def __init__(self, config: SubagentToolConfig) -> None:
        self._config = config
        self._repository = ScopedMarkdownRepository(
            config.agents_dir,
            scope_root_resolver=config.scope_root,
        )

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> SubagentCollectionResponse:
        groups = []
        for scope_item in iter_requested_scopes(scope, allow_local=False):
            if scope_item == DocumentScope.PLUGIN:
                continue
            records = self._repository.list_records(workspace_id, scope_item)
            documents = [self._to_summary(record) for record in records]
            documents.sort(key=lambda item: item.file_name)
            groups.append(SubagentScopeGroup(scope=scope_item, documents=documents))

        if self._config.supports_plugin and (scope is None or scope == DocumentScope.PLUGIN):
            try:
                plugin_agents = self._load_plugin_agents(workspace_id)
                if plugin_agents:
                    groups.append(SubagentScopeGroup(scope=DocumentScope.PLUGIN, documents=plugin_agents))
            except Exception:
                logger.error("Failed to load plugin agents", exc_info=True)

        return SubagentCollectionResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> SubagentScopeResponse:
        if scope == DocumentScope.PLUGIN and self._config.supports_plugin:
            documents = self._load_plugin_agents(workspace_id)
        else:
            records = self._repository.list_records(workspace_id, scope)
            documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.file_name)
        return SubagentScopeResponse(workspaceId=workspace_id, scope=scope, documents=documents)

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> SubagentDocumentResponse:
        if scope == DocumentScope.PLUGIN and self._config.supports_plugin:
            return self._get_plugin_document(workspace_id, file_name)

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
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        return SubagentDocumentResponse(workspaceId=workspace_id, scope=scope, document=detail)

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SubagentCreateRequest,
    ) -> SubagentDocumentResponse:
        try:
            record = self._repository.create_record(workspace_id, scope, payload.file_name, payload.content)
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_FILE_NAME", "message": str(error)},
            ) from error
        summary = self._to_summary(
            record,
            fallback_name=payload.name,
            fallback_description=payload.description,
        )
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        return SubagentDocumentResponse(workspaceId=workspace_id, scope=scope, document=detail)

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: SubagentUpdateRequest,
    ) -> SubagentDocumentResponse:
        try:
            record = self._repository.update_record(workspace_id, scope, file_name, payload.content)
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
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        return SubagentDocumentResponse(workspaceId=workspace_id, scope=scope, document=detail)

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

    def _load_plugin_agents(self, workspace_id: str) -> list[SubagentSummary]:
        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)
        plugin_agents = loader.load_plugin_agents(workspace_id)
        summaries: list[SubagentSummary] = []
        for agent in plugin_agents:
            size = getattr(agent, "size", None)
            if not size:
                try:
                    size = format_file_size(Path(agent.file_path).stat().st_size)
                except OSError:
                    size = "0B"
            summaries.append(
                SubagentSummary(
                    fileName=agent.file_name,
                    name=agent.file_name,
                    description=agent.description,
                    scope=DocumentScope.PLUGIN,
                    size=size,
                    pluginName=agent.plugin_name,
                    marketplaceName=agent.marketplace_name,
                )
            )
        return summaries

    def _get_plugin_document(
        self, workspace_id: str, file_name: str
    ) -> SubagentDocumentResponse:
        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        for agent in loader.load_plugin_agents(workspace_id):
            if agent.file_name != file_name:
                continue
            try:
                path = Path(agent.file_path)
                content = path.read_text(encoding="utf-8")
                detail = SubagentDocument(
                    fileName=agent.file_name,
                    name=agent.file_name,
                    description=agent.description,
                    scope=DocumentScope.PLUGIN,
                    size=format_file_size(path.stat().st_size),
                    content=content,
                    pluginName=agent.plugin_name,
                    marketplaceName=agent.marketplace_name,
                )
                return SubagentDocumentResponse(
                    workspaceId=workspace_id,
                    scope=DocumentScope.PLUGIN,
                    document=detail,
                )
            except OSError as error:
                logger.error("Failed to read plugin agent", exc_info=True)
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": "PLUGIN_READ_ERROR", "message": str(error)},
                ) from error

        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"error": "404_NOT_FOUND", "message": file_name},
        )

    def _to_summary(
        self,
        record: MarkdownDocumentRecord,
        *,
        fallback_name: str | None = None,
        fallback_description: str | None = None,
    ) -> SubagentSummary:
        metadata = record.metadata_with_fallbacks(
            fallback_name=fallback_name,
            fallback_description=fallback_description,
        )
        name = metadata.get("name") or record.file_name
        description = metadata.get("description") or fallback_description
        return SubagentSummary(
            fileName=record.file_name,
            name=str(name),
            description=str(description) if description is not None else None,
            scope=record.scope,
            size=record.size_label,
        )
