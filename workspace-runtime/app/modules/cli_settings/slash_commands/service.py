"""CLI Slash Command service

Provides CRUD operations for slash commands for Gemini, Codex, OpenCode.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

from app.config.settings import get_workspace_path

from .config import DocumentFormat, SlashCommandScope, SlashCommandToolConfig
from .format_strategies import (
    DocumentFormatStrategy,
    MarkdownFormatStrategy,
    TomlFormatStrategy,
)
from .models import (
    CliSlashCommandCreateRequest,
    CliSlashCommandDeleteResponse,
    CliSlashCommandDocumentDetail,
    CliSlashCommandDocumentResponse,
    CliSlashCommandDocumentSummary,
    CliSlashCommandScopeGroup,
    CliSlashCommandScopeResponse,
    CliSlashCommandScopesResponse,
    CliSlashCommandUpdateRequest,
)

logger = logging.getLogger(__name__)


# === Exceptions ==========================================================


class CliSlashCommandNotFoundError(FileNotFoundError):
    """The specified slash command does not exist"""


class CliSlashCommandDuplicateError(FileExistsError):
    """Slash command already exists"""


class CliSlashCommandAmbiguousError(RuntimeError):
    """Found multiple slash commands with the same name"""


# === Utility functions ===================================================


BYTES_PER_KB = 1024


def _humanize_size(byte_count: int) -> str:
    if byte_count < BYTES_PER_KB:
        return f"{byte_count}B"
    kilobytes = byte_count / BYTES_PER_KB
    if kilobytes < BYTES_PER_KB:
        return f"{kilobytes:.0f}KB"
    megabytes = kilobytes / BYTES_PER_KB
    return f"{megabytes:.1f}MB"


def _get_format_strategy(fmt: DocumentFormat) -> DocumentFormatStrategy:
    if fmt == DocumentFormat.TOML:
        return TomlFormatStrategy()
    return MarkdownFormatStrategy()


# === Service ==============================================================


class CliSlashCommandService:
    """File service for managing CLI tool Slash Commands"""

    def __init__(self, config: SlashCommandToolConfig) -> None:
        self._config = config
        self._strategy = _get_format_strategy(config.format)

    # --- Directory resolution ----------------------------------------------

    def _scope_dir(self, workspace_id: str, scope: SlashCommandScope) -> Path:
        if scope == SlashCommandScope.USER:
            return self._config.user_root
        # PROJECT: workspace_root / .gemini/commands etc.
        return Path(get_workspace_path()) / self._config.project_dot_dir / self._config.dir_name

    def _normalize_file_name(self, file_name: str) -> str:
        # Prevent path traversal attacks: reject characters containing .. or path separators
        if ".." in file_name or "/" in file_name or "\\" in file_name:
            raise ValueError(f"Invalid file_name: path traversal not allowed: {file_name}")

        ext = self._config.file_extension
        if file_name.endswith(ext):
            return file_name
        return f"{file_name}{ext}"

    def _resolve_file_path(
        self, directory: Path, file_name: str, *, namespace: str | None
    ) -> Path | None:
        normalized = self._normalize_file_name(file_name)
        ext = self._config.file_extension

        if namespace:
            candidate = directory / namespace / normalized
            return candidate if candidate.exists() else None

        # Search all matching files
        pattern = f"*{ext}"
        candidates = [
            p for p in directory.rglob(pattern)
            if p.name == normalized
        ]
        if not candidates:
            return None
        if len(candidates) > 1:
            raise CliSlashCommandAmbiguousError(file_name)
        return candidates[0]

    # --- Public CRUD ------------------------------------------------------

    def list_scopes(
        self, workspace_id: str, scope: SlashCommandScope | None = None
    ) -> CliSlashCommandScopesResponse:
        scopes = [scope] if scope else list(SlashCommandScope)
        groups: List[CliSlashCommandScopeGroup] = []
        for s in scopes:
            documents = self._list_documents(workspace_id, s)
            documents.sort(key=lambda d: d.file_name)
            groups.append(CliSlashCommandScopeGroup(scope=s, documents=documents))
        return CliSlashCommandScopesResponse(workspaceId=workspace_id, scopes=groups)

    def get_scope(
        self, workspace_id: str, scope: SlashCommandScope
    ) -> CliSlashCommandScopeResponse:
        documents = self._list_documents(workspace_id, scope)
        documents.sort(key=lambda d: d.file_name)
        return CliSlashCommandScopeResponse(
            workspaceId=workspace_id, scope=scope, documents=documents
        )

    def get_document(
        self, workspace_id: str, scope: SlashCommandScope, file_name: str
    ) -> CliSlashCommandDocumentResponse:
        directory = self._scope_dir(workspace_id, scope)
        file_path = self._resolve_file_path(directory, file_name, namespace=None)
        if file_path is None or not file_path.exists():
            raise CliSlashCommandNotFoundError(file_name)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            fileName=file_path.name,
            namespace=parsed.namespace,
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id, scope=scope, document=detail
        )

    def create_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        payload: CliSlashCommandCreateRequest,
    ) -> CliSlashCommandDocumentResponse:
        directory = self._scope_dir(workspace_id, scope)
        normalized = self._normalize_file_name(payload.file_name)

        # Determine target directory
        if payload.namespace and self._config.supports_namespace:
            # Prevent path traversal attacks: verify namespace does not contain dangerous characters
            if ".." in payload.namespace or "/" in payload.namespace or "\\" in payload.namespace:
                raise ValueError(f"Invalid namespace: path traversal not allowed: {payload.namespace}")
            target_dir = directory / payload.namespace
        else:
            target_dir = directory

        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / normalized

        if file_path.exists():
            raise CliSlashCommandDuplicateError(payload.file_name)

        self._strategy.write(file_path, payload.content)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            fileName=file_path.name,
            namespace=parsed.namespace if self._config.supports_namespace else None,
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id, scope=scope, document=detail
        )

    def update_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        file_name: str,
        payload: CliSlashCommandUpdateRequest,
    ) -> CliSlashCommandDocumentResponse:
        directory = self._scope_dir(workspace_id, scope)
        file_path = self._resolve_file_path(
            directory, file_name, namespace=payload.namespace
        )
        if file_path is None or not file_path.exists():
            raise CliSlashCommandNotFoundError(file_name)

        self._strategy.write(file_path, payload.content)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            fileName=file_path.name,
            namespace=parsed.namespace,
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id, scope=scope, document=detail
        )

    def delete_document(
        self, workspace_id: str, scope: SlashCommandScope, file_name: str
    ) -> CliSlashCommandDeleteResponse:
        directory = self._scope_dir(workspace_id, scope)
        file_path = self._resolve_file_path(directory, file_name, namespace=None)
        if file_path is None or not file_path.exists():
            raise CliSlashCommandNotFoundError(file_name)

        file_path.unlink()
        return CliSlashCommandDeleteResponse(
            workspaceId=workspace_id, scope=scope, fileName=file_name, deleted=True
        )

    # --- Internal utilities -----------------------------------------------

    def _list_documents(
        self, workspace_id: str, scope: SlashCommandScope
    ) -> List[CliSlashCommandDocumentSummary]:
        directory = self._scope_dir(workspace_id, scope)
        if not directory.exists():
            return []

        ext = self._config.file_extension
        pattern = f"*{ext}"
        documents: List[CliSlashCommandDocumentSummary] = []

        for file_path in sorted(directory.rglob(pattern)):
            try:
                parsed = self._strategy.parse(file_path, directory)
                stat = file_path.stat()
                documents.append(
                    CliSlashCommandDocumentSummary(
                        fileName=file_path.name,
                        namespace=parsed.namespace if self._config.supports_namespace else None,
                        description=parsed.description,
                        scope=scope,
                        size=_humanize_size(stat.st_size),
                        format=self._config.format,
                    )
                )
            except Exception:
                logger.warning("Failed to parse slash command: %s", file_path)

        return documents
