"""Subagents Service"""

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
    """Service for managing Subagent configuration files"""

    def __init__(self) -> None:
        self._repository = ScopedMarkdownRepository("agents")

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> SubagentCollectionResponse:
        """
        List all subagents

        Modified: Auto-integrate plugin agents
        """
        groups = []

        # 1. Load existing agents (project/user)
        for scope_item in iter_requested_scopes(scope, allow_local=False):
            records = self._repository.list_records(workspace_id, scope_item)
            documents = [self._to_summary(record) for record in records]
            documents.sort(key=lambda item: item.file_name)
            groups.append(SubagentScopeGroup(scope=scope_item, documents=documents))

        # 2. Load plugin agents (added)
        if scope is None or scope == DocumentScope.PLUGIN:
            try:
                plugin_agents = self._load_plugin_agents(workspace_id)
                if plugin_agents:
                    groups.append(
                        SubagentScopeGroup(
                            scope=DocumentScope.PLUGIN,
                            documents=plugin_agents
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to load plugin agents: {e}")

        return SubagentCollectionResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> SubagentScopeResponse:
        records = self._repository.list_records(workspace_id, scope)
        documents = [self._to_summary(record) for record in records]
        documents.sort(key=lambda item: item.file_name)
        return SubagentScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            documents=documents,
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, file_name: str
    ) -> SubagentDocumentResponse:
        # If PLUGIN scope, load from plugin
        if scope == DocumentScope.PLUGIN:
            return self._get_plugin_document(workspace_id, file_name)

        # Otherwise load from file system
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
        return SubagentDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SubagentCreateRequest,
    ) -> SubagentDocumentResponse:
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
        summary = self._to_summary(
            record,
            fallback_name=payload.name,
            fallback_description=payload.description,
        )
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        return SubagentDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        file_name: str,
        payload: SubagentUpdateRequest,
    ) -> SubagentDocumentResponse:
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
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        return SubagentDocumentResponse(
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

    def _get_plugin_document(
        self, workspace_id: str, file_name: str
    ) -> SubagentDocumentResponse:
        """Load single document from plugin"""
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        plugin_agents = loader.load_plugin_agents(workspace_id)

        for agent in plugin_agents:
            if agent.file_name == file_name:
                try:
                    content = Path(agent.file_path).read_text(encoding="utf-8")
                    file_size = Path(agent.file_path).stat().st_size
                    size_str = format_file_size(file_size)

                    detail = SubagentDocument(
                        fileName=agent.file_name,
                        name=agent.file_name,
                        description=agent.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        content=content,
                        pluginName=agent.plugin_name,
                        marketplaceName=agent.marketplace_name
                    )

                    return SubagentDocumentResponse(
                        workspaceId=workspace_id,
                        scope=DocumentScope.PLUGIN,
                        document=detail,
                    )
                except (OSError, IOError) as e:
                    logger.error(f"Failed to read plugin agent {agent.file_path}: {e}")
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
        fallback_name: str | None = None,
        fallback_description: str | None = None,
    ) -> SubagentSummary:
        metadata = record.metadata_with_fallbacks(
            fallback_name=fallback_name,
            fallback_description=fallback_description,
        )
        name = metadata.get("name")
        if not name:
            name = record.file_name
        description = metadata.get("description") or fallback_description
        return SubagentSummary(
            fileName=record.file_name,
            name=name,
            description=description,
            scope=record.scope,
            size=record.size_label,
        )

    def _load_plugin_agents(
        self,
        workspace_id: str
    ) -> list[SubagentSummary]:
        """Load plugin agents

        Returns:
            List[SubagentSummary]: Documents with pluginName and marketplaceName
        """
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        plugin_agents = loader.load_plugin_agents(workspace_id)

        documents = []
        for agent in plugin_agents:
            try:
                file_size = Path(agent.file_path).stat().st_size
                size_str = format_file_size(file_size)

                documents.append(
                    SubagentSummary(
                        fileName=agent.file_name,
                        name=agent.file_name,
                        description=agent.description,
                        scope=DocumentScope.PLUGIN,
                        size=size_str,
                        pluginName=agent.plugin_name,
                        marketplaceName=agent.marketplace_name
                    )
                )
            except (OSError, IOError) as e:
                logger.error(f"Failed to read plugin agent {agent.file_path}: {e}")

        return documents

