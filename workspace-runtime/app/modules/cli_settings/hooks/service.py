"""CLI Hook 設定服務

為 Gemini 等 CLI 工具提供 Hooks 設定的 CRUD 操作。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from fastapi import HTTPException, status

from app.config.settings import get_workspace_path

from ...claude_code.hooks.models import HookRule
from .config import CliHookScope, CliHookToolConfig
from .models import (
    CliHookDeleteResponse,
    CliHookExportResponse,
    CliHookImportMode,
    CliHookImportRequest,
    CliHookImportResponse,
    CliHookScopeDocument,
    CliHookScopeResponse,
    CliHookScopeUpsertRequest,
    CliHookScopesResponse,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CliHookService:
    """管理 CLI 工具 Hooks 的檔案服務"""

    def __init__(self, config: CliHookToolConfig) -> None:
        self._config = config

    # --- 公開方法 ---------------------------------------------------------

    def list_scopes(
        self, workspace_id: str, scope: CliHookScope | None = None
    ) -> CliHookScopesResponse:
        scopes = [scope] if scope else list(self._config.supported_scopes)
        documents = [
            self._load_scope_document(workspace_id, s) for s in scopes
        ]
        return CliHookScopesResponse(workspaceId=workspace_id, scopes=documents)

    def get_scope(
        self, workspace_id: str, scope: CliHookScope
    ) -> CliHookScopeResponse:
        self._validate_scope(scope)
        document = self._load_scope_document(workspace_id, scope)
        return CliHookScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            hooks=document.hooks,
        )

    def update_scope(
        self,
        workspace_id: str,
        scope: CliHookScope,
        payload: CliHookScopeUpsertRequest,
    ) -> CliHookScopeResponse:
        self._validate_scope(scope)
        hooks_dict: Dict[str, List[HookRule]] = {}
        for event, rules in payload.hooks.items():
            converted_rules = []
            for rule in rules:
                if isinstance(rule, dict):
                    converted_rules.append(HookRule.model_validate(rule))
                else:
                    converted_rules.append(rule)
            hooks_dict[event] = converted_rules
        self._write_hooks(workspace_id, scope, hooks_dict)
        document = self._load_scope_document(workspace_id, scope)
        return CliHookScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            hooks=document.hooks,
        )

    def delete_scope(
        self, workspace_id: str, scope: CliHookScope
    ) -> CliHookDeleteResponse:
        self._validate_scope(scope)
        file_path = self._scope_file(workspace_id, scope)
        data = self._config.strategy.read(file_path)
        if data:
            data.pop(self._config.hooks_key, None)
            if not data:
                if file_path.exists():
                    file_path.unlink()
            else:
                self._config.strategy.write(file_path, data)
        elif file_path.exists():
            file_path.unlink()
        return CliHookDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            deleted=True,
            deletedAt=_utcnow(),
        )

    def export_scopes(
        self,
        workspace_id: str,
        scope_filter: Iterable[CliHookScope] | None = None,
    ) -> CliHookExportResponse:
        scopes = list(scope_filter) if scope_filter else list(self._config.supported_scopes)
        documents = [self._load_scope_document(workspace_id, s) for s in scopes]
        return CliHookExportResponse(
            workspaceId=workspace_id,
            exportedAt=_utcnow(),
            scopes=documents,
        )

    def import_scopes(
        self,
        workspace_id: str,
        request: CliHookImportRequest,
    ) -> CliHookImportResponse:
        imported = 0
        updated = 0
        skipped = 0
        for document in request.scopes:
            self._validate_scope(document.scope)
            existing = self._load_scope_document(workspace_id, document.scope)
            if request.mode == CliHookImportMode.MERGE:
                merged = self._merge_hooks(existing.hooks, document.hooks)
                if merged == existing.hooks:
                    skipped += 1
                    continue
                hooks_to_write = merged
                updated += 1 if existing.hooks else 0
                if not existing.hooks:
                    imported += 1
            else:  # REPLACE
                hooks_to_write = document.hooks
                if existing.hooks:
                    updated += 1
                else:
                    imported += 1
            self._write_hooks(workspace_id, document.scope, hooks_to_write)
        return CliHookImportResponse(
            workspaceId=workspace_id,
            mode=request.mode,
            imported=imported,
            updated=updated,
            skipped=skipped,
        )

    # --- 內部方法 ---------------------------------------------------------

    def _validate_scope(self, scope: CliHookScope) -> None:
        if scope not in self._config.supported_scopes:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "UNSUPPORTED_SCOPE",
                    "message": f"Unsupported scope: {scope}",
                },
            )

    def _scope_file(self, workspace_id: str, scope: CliHookScope) -> Path:
        if scope == CliHookScope.PROJECT:
            return Path(get_workspace_path()) / self._config.project_file
        return self._config.user_file_path

    def _load_scope_document(
        self, workspace_id: str, scope: CliHookScope
    ) -> CliHookScopeDocument:
        file_path = self._scope_file(workspace_id, scope)
        data = self._config.strategy.read(file_path)
        if not data:
            return CliHookScopeDocument(scope=scope, hooks={})

        hooks_data: Dict[str, Any] = data.get(self._config.hooks_key, {})
        if not isinstance(hooks_data, dict):
            return CliHookScopeDocument(scope=scope, hooks={})

        hooks = {
            event: [HookRule.model_validate(rule) for rule in rules]
            for event, rules in hooks_data.items()
            if isinstance(rules, list)
        }
        return CliHookScopeDocument(scope=scope, hooks=hooks)

    def _write_hooks(
        self,
        workspace_id: str,
        scope: CliHookScope,
        hooks: Dict[str, List[HookRule]],
    ) -> None:
        file_path = self._scope_file(workspace_id, scope)
        data = self._config.strategy.read(file_path)
        if not data:
            data = {}
        data[self._config.hooks_key] = self._encode_hooks(hooks)
        self._config.strategy.write(file_path, data)

    def _encode_hooks(
        self, hooks: Dict[str, List[HookRule]]
    ) -> Dict[str, List[Dict]]:
        encoded: Dict[str, List[Dict]] = {}
        for event, rules in hooks.items():
            encoded[event] = [rule.model_dump() for rule in rules]
        return encoded

    def _merge_hooks(
        self,
        current: Dict[str, List[HookRule]],
        incoming: Dict[str, List[HookRule]],
    ) -> Dict[str, List[HookRule]]:
        merged = {event: list(rules) for event, rules in current.items()}
        for event, rules in incoming.items():
            merged[event] = list(rules)
        return merged
