"""CLI Slash Command service

Provides CRUD operations for slash commands for Codex and OpenCode.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from threading import Lock
from typing import List

from app.config.settings import get_workspace_path
from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.codecs import remove_file_exact

from .config import (
    DocumentFormat,
    SlashCommandScope,
    SlashCommandToolConfig,
)
from .format_strategies import (
    DocumentFormatStrategy,
    MarkdownFormatStrategy,
    TomlFormatStrategy,
)
from .models import (
    CliSlashCommandAvailableScope,
    CliSlashCommandCreateRequest,
    CliSlashCommandDeleteResponse,
    CliSlashCommandDocumentDetail,
    CliSlashCommandDocumentResponse,
    CliSlashCommandDocumentSummary,
    CliSlashCommandScopeResponse,
    CliSlashCommandScopesResponse,
    CliSlashCommandUpdateRequest,
)

logger = logging.getLogger(__name__)
_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


# === Exceptions ==========================================================


class CliSlashCommandNotFoundError(FileNotFoundError):
    """The specified slash command does not exist"""


class CliSlashCommandDuplicateError(FileExistsError):
    """Slash command already exists"""


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

    def __init__(
        self,
        config: SlashCommandToolConfig,
    ) -> None:
        self._config = config
        self._strategy = _get_format_strategy(config.format)

    # --- Directory resolution ----------------------------------------------

    def _scope_dir(self, workspace_id: str, scope: SlashCommandScope) -> Path:
        self._validate_scope(scope)
        if scope == SlashCommandScope.USER:
            return self._config.user_root
        # PROJECT: workspace_root / tool-specific commands directory.
        return (
            Path(get_workspace_path())
            / self._config.project_dot_dir
            / self._config.dir_name
        )

    def _normalize_path(self, raw_path: str) -> Path:
        clean_path = raw_path.strip()
        if not clean_path or "\\" in clean_path:
            raise ValueError(f"Invalid path: {raw_path}")
        path = Path(clean_path)
        if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
            raise ValueError(f"Invalid path: {raw_path}")
        ext = self._config.file_extension
        if path.suffix and path.suffix != ext:
            raise ValueError(f"Invalid path extension: {raw_path}")
        if not path.suffix:
            path = path.with_name(f"{path.name}{ext}")
        return path

    def _resolve_file_path(self, directory: Path, raw_path: str) -> Path:
        return directory / self._normalize_path(raw_path)

    @staticmethod
    def _relative_path(directory: Path, file_path: Path) -> str:
        return file_path.relative_to(directory).as_posix()

    # --- Public CRUD ------------------------------------------------------

    def list_scopes(
        self, workspace_id: str, scope: SlashCommandScope | None = None
    ) -> CliSlashCommandScopesResponse:
        scopes = (
            [scope] if scope else [SlashCommandScope.PROJECT, SlashCommandScope.USER]
        )
        items: List[CliSlashCommandDocumentSummary] = []
        for s in scopes:
            documents = self._list_documents(workspace_id, s)
            documents.sort(key=lambda d: d.path)
            items.extend(documents)
        items.sort(key=lambda item: (item.scope.value, item.path))
        return CliSlashCommandScopesResponse(
            workspaceId=workspace_id,
            items=items,
            availableScopes=[
                CliSlashCommandAvailableScope(scope=s, readOnly=False) for s in scopes
            ],
        )

    def get_scope(
        self, workspace_id: str, scope: SlashCommandScope
    ) -> CliSlashCommandScopeResponse:
        documents = self._list_documents(workspace_id, scope)
        documents.sort(key=lambda d: d.path)
        return CliSlashCommandScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._scope_revision(self._scope_dir(workspace_id, scope)),
            documents=documents,
        )

    def get_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        path: str,
    ) -> CliSlashCommandDocumentResponse:
        directory = self._scope_dir(workspace_id, scope)
        file_path = self._resolve_file_path(directory, path)
        if not file_path.exists():
            raise CliSlashCommandNotFoundError(path)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            path=self._relative_path(directory, file_path),
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._file_revision(file_path),
            document=detail,
        )

    def create_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        payload: CliSlashCommandCreateRequest,
    ) -> CliSlashCommandDocumentResponse:
        self._ensure_mutable_scope(scope)
        directory = self._scope_dir(workspace_id, scope)
        with _write_lock(directory):
            assert_revision(self._scope_revision(directory), payload.revision)
            file_path = self._resolve_file_path(directory, payload.path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            if file_path.exists():
                raise CliSlashCommandDuplicateError(payload.path)

            self._strategy.write(file_path, payload.content)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            path=self._relative_path(directory, file_path),
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._file_revision(file_path),
            document=detail,
        )

    def update_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        payload: CliSlashCommandUpdateRequest,
    ) -> CliSlashCommandDocumentResponse:
        self._ensure_mutable_scope(scope)
        directory = self._scope_dir(workspace_id, scope)
        with _write_lock(directory):
            file_path = self._resolve_file_path(directory, payload.path)
            if not file_path.exists():
                raise CliSlashCommandNotFoundError(payload.path)
            assert_revision(self._file_revision(file_path), payload.revision)
            self._strategy.write(file_path, payload.content)

        parsed = self._strategy.parse(file_path, directory)
        stat = file_path.stat()
        summary = CliSlashCommandDocumentSummary(
            path=self._relative_path(directory, file_path),
            description=parsed.description,
            scope=scope,
            size=_humanize_size(stat.st_size),
            format=self._config.format,
        )
        detail = CliSlashCommandDocumentDetail(
            **summary.model_dump(), content=parsed.content
        )
        return CliSlashCommandDocumentResponse(
            workspaceId=workspace_id,
            scope=scope,
            revision=self._file_revision(file_path),
            document=detail,
        )

    def delete_document(
        self,
        workspace_id: str,
        scope: SlashCommandScope,
        path: str,
        *,
        revision: str,
    ) -> CliSlashCommandDeleteResponse:
        self._ensure_mutable_scope(scope)
        directory = self._scope_dir(workspace_id, scope)
        with _write_lock(directory):
            file_path = self._resolve_file_path(directory, path)
            if not file_path.exists():
                raise CliSlashCommandNotFoundError(path)
            assert_revision(self._file_revision(file_path), revision)
            remove_file_exact(file_path)
            scope_revision = self._scope_revision(directory)
        return CliSlashCommandDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            path=self._normalize_path(path).as_posix(),
            revision=scope_revision,
            deleted=True,
        )

    # --- Internal utilities -----------------------------------------------

    @staticmethod
    def _ensure_mutable_scope(scope: SlashCommandScope) -> None:
        CliSlashCommandService._validate_scope(scope)

    @staticmethod
    def _validate_scope(scope: SlashCommandScope) -> None:
        if scope not in (SlashCommandScope.PROJECT, SlashCommandScope.USER):
            raise ValueError(f"Unsupported slash command scope: {scope}")

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
                        path=self._relative_path(directory, file_path),
                        description=parsed.description,
                        scope=scope,
                        size=_humanize_size(stat.st_size),
                        format=self._config.format,
                    )
                )
            except Exception:
                logger.warning("Failed to parse slash command: %s", file_path)

        return documents

    def _scope_revision(self, directory: Path) -> str:
        ext = self._config.file_extension
        if not directory.exists():
            return compute_revision("{}")
        content_by_path = {
            file_path.relative_to(directory).as_posix(): file_path.read_text(
                encoding="utf-8"
            )
            for file_path in sorted(directory.rglob(f"*{ext}"))
            if file_path.is_file()
        }
        content = json.dumps(content_by_path, sort_keys=True, separators=(",", ":"))
        return compute_revision(content)

    @staticmethod
    def _file_revision(file_path: Path) -> str:
        return compute_revision(file_path.read_text(encoding="utf-8"))
