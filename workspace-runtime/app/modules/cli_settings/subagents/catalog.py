"""CLI subagents service."""

from __future__ import annotations

import logging
import json
from copy import deepcopy
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.claude_code.documents import (
    DocumentNotFoundError,
    DocumentScope,
    DuplicateDocumentError,
    InvalidDocumentFileNameError,
    MarkdownDocumentRecord,
    ScopedMarkdownRepository,
    format_file_size,
    iter_requested_scopes,
    parse_front_matter,
)
from app.modules.cli_settings.user_scope.codecs import MarkdownDirectoryCodec
from app.modules.cli_settings.cache import ProcessTTLCache

from .config import SubagentToolConfig
from .models import (
    AvailableSubagentScope,
    SubagentCollectionResponse,
    SubagentCreateRequest,
    SubagentDeleteResponse,
    SubagentDocument,
    SubagentDocumentResponse,
    SubagentScopeResponse,
    SubagentSummary,
    SubagentUpdateRequest,
)

logger = logging.getLogger(__name__)
_MARKDOWN_CODEC = MarkdownDirectoryCodec()
_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


class SubagentService:
    """Service for managing CLI subagent markdown files."""

    def __init__(
        self,
        config: SubagentToolConfig,
    ) -> None:
        self._config = config
        self._repository = ScopedMarkdownRepository(
            config.agents_dir,
            scope_root_resolver=config.scope_root,
        )
        self._collection_cache: ProcessTTLCache[
            tuple[str, str, str],
            SubagentCollectionResponse | SubagentScopeResponse,
        ] = ProcessTTLCache()

    def clear_cache(
        self,
        workspace_id: str | None = None,
        scope: DocumentScope | str | None = None,
    ) -> None:
        """Clear cached subagent summaries."""

        scope_value = scope.value if isinstance(scope, DocumentScope) else scope
        self._collection_cache.clear(
            lambda key: (workspace_id is None or key[0] == workspace_id)
            and (scope_value is None or key[2] in {scope_value, "all"})
        )

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> SubagentCollectionResponse:
        scope_value = scope.value if scope is not None else "all"
        return deepcopy(
            self._collection_cache.get_or_load(
                (workspace_id, "collection", scope_value),
                lambda: self._list_scopes_uncached(workspace_id, scope),
            )
        )

    def _list_scopes_uncached(
        self,
        workspace_id: str,
        scope: DocumentScope | None,
    ) -> SubagentCollectionResponse:
        items: list[SubagentSummary] = []
        available_scopes: list[AvailableSubagentScope] = []
        for scope_item in iter_requested_scopes(scope, allow_local=False):
            if scope_item == DocumentScope.PLUGIN:
                continue
            records = self._repository.list_records(workspace_id, scope_item)
            documents = [self._to_summary(record) for record in records]
            documents.sort(key=lambda item: item.path)
            items.extend(documents)
            available_scopes.append(
                AvailableSubagentScope(scope=scope_item, readOnly=False)
            )

        if self._config.supports_plugin and (
            scope is None or scope == DocumentScope.PLUGIN
        ):
            available_scopes.append(
                AvailableSubagentScope(scope=DocumentScope.PLUGIN, readOnly=True)
            )
            try:
                plugin_agents = self._load_plugin_agents(workspace_id)
                if plugin_agents:
                    items.extend(plugin_agents)
            except Exception:
                logger.error("Failed to load plugin agents", exc_info=True)

        items.sort(key=lambda item: (item.scope.value, item.path))
        return SubagentCollectionResponse(
            workspaceId=workspace_id,
            items=items,
            availableScopes=available_scopes,
        )

    def get_scope(
        self, workspace_id: str, scope: DocumentScope
    ) -> SubagentScopeResponse:
        return deepcopy(
            self._collection_cache.get_or_load(
                (workspace_id, "scope", scope.value),
                lambda: self._get_scope_uncached(workspace_id, scope),
            )
        )

    def _get_scope_uncached(
        self,
        workspace_id: str,
        scope: DocumentScope,
    ) -> SubagentScopeResponse:
        if scope == DocumentScope.PLUGIN and self._config.supports_plugin:
            documents = self._load_plugin_agents(workspace_id)
            revision = self._plugin_scope_revision(documents)
        else:
            records = self._repository.list_records(workspace_id, scope)
            documents = [self._to_summary(record) for record in records]
            revision = self._scope_revision(records)
        documents.sort(key=lambda item: item.path)
        return SubagentScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=revision,
            documents=documents,
        )

    def get_document(
        self, workspace_id: str, scope: DocumentScope, path: str
    ) -> SubagentDocumentResponse:
        if scope == DocumentScope.PLUGIN and self._config.supports_plugin:
            return self._get_plugin_document(workspace_id, path)

        try:
            record = self._load_record_by_path(workspace_id, scope, path)
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
            revision=self._record_revision(record),
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SubagentCreateRequest,
    ) -> SubagentDocumentResponse:
        self._validate_markdown_subagent_content(payload.content)
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                assert_revision(
                    self._scope_revision(
                        self._repository.list_records(workspace_id, scope)
                    ),
                    payload.revision,
                )
                record = self._create_record_by_path(
                    workspace_id, scope, payload.path, payload.content
                )
        except InvalidDocumentFileNameError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_SUBAGENT_PATH",
                    "target": "path",
                    "message": str(error),
                },
            ) from error
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_PATH", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        self.clear_cache(workspace_id, scope)
        return SubagentDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._record_revision(record),
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: SubagentUpdateRequest,
    ) -> SubagentDocumentResponse:
        self._validate_markdown_subagent_content(payload.content)
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                existing = self._load_record_by_path(workspace_id, scope, payload.path)
                assert_revision(self._record_revision(existing), payload.revision)
                record = self._update_record_by_path(
                    workspace_id, scope, payload.path, payload.content
                )
        except InvalidDocumentFileNameError as error:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_SUBAGENT_PATH",
                    "target": "path",
                    "message": str(error),
                },
            ) from error
        except DuplicateDocumentError as error:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "DUPLICATE_PATH", "message": str(error)},
            ) from error
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": str(error)},
            ) from error
        summary = self._to_summary(record)
        detail = SubagentDocument(**summary.model_dump(), content=record.content)
        self.clear_cache(workspace_id, scope)
        return SubagentDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._record_revision(record),
            document=detail,
        )

    def delete_document(
        self, workspace_id: str, scope: DocumentScope, path: str, *, revision: str
    ) -> SubagentDeleteResponse:
        directory = self._repository._directory(workspace_id, scope)
        try:
            with _write_lock(directory):
                existing = self._load_record_by_path(workspace_id, scope, path)
                assert_revision(self._record_revision(existing), revision)
                self._delete_record_by_path(workspace_id, scope, path)
                scope_revision = self._scope_revision(
                    self._repository.list_records(workspace_id, scope)
                )
        except DocumentNotFoundError as error:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "404_NOT_FOUND", "message": str(error)},
            ) from error
        self.clear_cache(workspace_id, scope)
        return SubagentDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            path=self._normalize_path(path).as_posix(),
            revision=scope_revision,
            deleted=True,
        )

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
                    path=agent.file_name,
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
        self, workspace_id: str, path: str
    ) -> SubagentDocumentResponse:
        from app.modules.claude_code.plugins.loader import get_plugin_loader
        from app.modules.claude_code.settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        for agent in loader.load_plugin_agents(workspace_id):
            if agent.file_name != path:
                continue
            try:
                agent_path = Path(agent.file_path)
                content = agent_path.read_text(encoding="utf-8")
                detail = SubagentDocument(
                    path=agent.file_name,
                    name=agent.file_name,
                    description=agent.description,
                    scope=DocumentScope.PLUGIN,
                    size=format_file_size(agent_path.stat().st_size),
                    content=content,
                    pluginName=agent.plugin_name,
                    marketplaceName=agent.marketplace_name,
                )
                return SubagentDocumentResponse(
                    workspaceId=workspace_id,
                    scope=DocumentScope.PLUGIN,
                    revision=compute_revision(content),
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
            detail={"error": "404_NOT_FOUND", "message": path},
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
            path=self._record_path(record),
            name=str(name),
            description=str(description) if description is not None else None,
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

    @classmethod
    def _scope_revision(cls, records: list[MarkdownDocumentRecord]) -> str:
        content_by_path = {
            record.file_path.relative_to(record.root_path).as_posix(): record.content
            for record in records
        }
        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    @staticmethod
    def _plugin_scope_revision(documents: list[SubagentSummary]) -> str:
        content_by_path = {
            document.path: {
                "description": document.description,
                "marketplaceName": document.marketplace_name,
                "pluginName": document.plugin_name,
            }
            for document in documents
        }
        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    @staticmethod
    def _validate_markdown_subagent_content(content: str) -> None:
        metadata, _body = parse_front_matter(content)
        missing = [
            key
            for key in ("name", "description")
            if not isinstance(metadata.get(key), str)
            or not metadata.get(key, "").strip()
        ]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "MISSING_SUBAGENT_FIELD",
                    "target": "content",
                    "fields": missing,
                },
            )
