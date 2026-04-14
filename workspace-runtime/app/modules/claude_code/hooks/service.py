"""Hook 設定服務"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

logger = logging.getLogger(__name__)

from fastapi import HTTPException, status

from ..common import (
    DocumentScope,
    iter_requested_scopes,
    read_json_file,
    resolve_scope_root,
    utcnow,
    write_json_file,
)
from .models import (
    HookDeleteResponse,
    HookExportResponse,
    HookImportMode,
    HookImportRequest,
    HookImportResponse,
    HookRule,
    HookScopeDocument,
    HookScopeResponse,
    HookScopeUpsertRequest,
    HookScopesResponse,
)


class HookService:
    """管理 Claude Code Hooks 的檔案服務"""

    _SETTINGS_FILE = {
        DocumentScope.USER: "settings.json",
        DocumentScope.PROJECT: "settings.json",
        DocumentScope.LOCAL: "settings.local.json",
    }

    def list_scopes(
        self, workspace_id: str, scope: DocumentScope | None = None
    ) -> HookScopesResponse:
        """
        列出所有 hooks

        修改：自動整合 plugin hooks
        """
        # 如果指定了 PLUGIN scope，只返回 plugin hooks
        if scope == DocumentScope.PLUGIN:
            try:
                plugin_hooks = self._load_plugin_hooks(workspace_id)
                documents = [
                    HookScopeDocument(
                        scope=DocumentScope.PLUGIN,
                        hooks=plugin_hooks,
                        pluginSources=self._build_plugin_sources(plugin_hooks)
                    )
                ]
            except Exception as e:
                logger.error(f"Failed to load plugin hooks: {e}")
                documents = [
                    HookScopeDocument(
                        scope=DocumentScope.PLUGIN,
                        hooks={},
                        pluginSources={}
                    )
                ]
            return HookScopesResponse(workspaceId=workspace_id, scopes=documents)

        # 載入一般 scopes（project/user/local）
        documents = [
            self._load_scope_document(workspace_id, scope_item)
            for scope_item in iter_requested_scopes(scope)
        ]

        # 如果沒有指定 scope，也載入 plugin hooks
        if scope is None:
            try:
                plugin_hooks = self._load_plugin_hooks(workspace_id)
                if plugin_hooks:
                    documents.append(
                        HookScopeDocument(
                            scope=DocumentScope.PLUGIN,
                            hooks=plugin_hooks,
                            pluginSources=self._build_plugin_sources(plugin_hooks)
                        )
                    )
            except Exception as e:
                logger.error(f"Failed to load plugin hooks: {e}")

        return HookScopesResponse(workspaceId=workspace_id, scopes=documents)

    def get_scope(self, workspace_id: str, scope: DocumentScope) -> HookScopeResponse:
        # 如果是 PLUGIN scope，載入 plugin hooks
        if scope == DocumentScope.PLUGIN:
            plugin_hooks = self._load_plugin_hooks(workspace_id)
            return HookScopeResponse(
                workspaceId=workspace_id,
                scope=scope,
                hooks=plugin_hooks,
            )

        document = self._load_scope_document(workspace_id, scope)
        return HookScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            hooks=document.hooks,
        )

    def update_scope(
        self,
        workspace_id: str,
        scope: DocumentScope,
        payload: HookScopeUpsertRequest,
    ) -> HookScopeResponse:
        # 檢查 PLUGIN scope 不可寫入
        if scope == DocumentScope.PLUGIN:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "SCOPE_READ_ONLY",
                    "message": "Plugin scope is read-only. Plugins can only be managed through the marketplace."
                },
            )

        # Convert dict to HookRule objects for encoding
        hooks_dict = {}
        for event, rules in payload.hooks.items():
            converted_rules = []
            for rule in rules:
                if isinstance(rule, dict):
                    converted_rules.append(HookRule.model_validate(rule))
                else:
                    converted_rules.append(rule)
            hooks_dict[event] = converted_rules
        self._write_scope(workspace_id, scope, hooks_dict)
        document = self._load_scope_document(workspace_id, scope)
        return HookScopeResponse(
            workspaceId=workspace_id,
            scope=scope,
            hooks=document.hooks,
        )

    def delete_scope(self, workspace_id: str, scope: DocumentScope) -> HookDeleteResponse:
        # 檢查 PLUGIN scope 不可刪除
        if scope == DocumentScope.PLUGIN:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "SCOPE_READ_ONLY",
                    "message": "Plugin scope is read-only. Plugins can only be managed through the marketplace."
                },
            )

        file_path = self._scope_file(workspace_id, scope)
        data = read_json_file(file_path)
        if data:
            data.pop("hooks", None)
            if not data:
                if file_path.exists():
                    file_path.unlink()
            else:
                write_json_file(file_path, data)
        elif file_path.exists():
            file_path.unlink()
        deleted_at = utcnow()
        return HookDeleteResponse(
            workspaceId=workspace_id,
            scope=scope,
            deleted=True,
            deletedAt=deleted_at,
        )

    def export_scopes(
        self, workspace_id: str, scope_filter: Iterable[DocumentScope] | None = None
    ) -> HookExportResponse:
        scopes = scope_filter or iter_requested_scopes(None)
        documents = [self._load_scope_document(workspace_id, scope) for scope in scopes]
        return HookExportResponse(
            workspaceId=workspace_id,
            exportedAt=utcnow(),
            scopes=documents,
        )

    def import_scopes(
        self,
        workspace_id: str,
        request: HookImportRequest,
    ) -> HookImportResponse:
        imported = 0
        updated = 0
        skipped = 0
        for document in request.scopes:
            existing = self._load_scope_document(workspace_id, document.scope)
            if request.mode == HookImportMode.MERGE:
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
            self._write_scope(workspace_id, document.scope, hooks_to_write)
        return HookImportResponse(
            workspaceId=workspace_id,
            mode=request.mode,
            imported=imported,
            updated=updated,
            skipped=skipped,
        )

    # 內部工具 -------------------------------------------------------
    def _scope_file(self, workspace_id: str, scope: DocumentScope) -> Path:
        # PLUGIN scope 不使用檔案系統，應該透過 _load_plugin_hooks 載入
        if scope == DocumentScope.PLUGIN:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "UNSUPPORTED_SCOPE", "message": f"Plugin scope does not use file system"},
            )

        root = resolve_scope_root(workspace_id, scope)
        file_name = self._SETTINGS_FILE.get(scope)
        if file_name is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "UNSUPPORTED_SCOPE", "message": f"Unsupported scope: {scope}"},
            )
        return root / file_name

    def _load_scope_document(self, workspace_id: str, scope: DocumentScope) -> HookScopeDocument:
        file_path = self._scope_file(workspace_id, scope)
        data = read_json_file(file_path)
        if not data:
            return HookScopeDocument(scope=scope, hooks={})

        hooks_data: Dict[str, Any] = data.get("hooks", {})
        hooks = {
            event: [HookRule.model_validate(rule) for rule in rules]
            for event, rules in hooks_data.items()
        }
        return HookScopeDocument(
            scope=scope,
            hooks=hooks,
        )

    def _write_scope(
        self,
        workspace_id: str,
        scope: DocumentScope,
        hooks: Dict[str, List[HookRule]],
    ) -> None:
        file_path = self._scope_file(workspace_id, scope)
        # 讀取現有檔案內容，如果不存在則建立空字典
        data = read_json_file(file_path)
        if not data:
            data = {}
        # 將 hooks 寫入到 "hooks" 欄位
        data["hooks"] = self._encode_hooks(hooks)
        write_json_file(file_path, data)

    def _encode_hooks(self, hooks: Dict[str, List[HookRule]]) -> Dict[str, List[Dict]]:
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

    def _load_plugin_hooks(
        self,
        workspace_id: str
    ) -> Dict[str, List[HookRule]]:
        """
        載入 plugin hooks（新方法）

        Returns:
            Dict[event_name, List[HookRule]]: Hooks 配置
        """
        from ..plugins.loader import get_plugin_loader
        from ..settings.dependencies import get_settings_service

        settings_service = get_settings_service()
        loader = get_plugin_loader(settings_service)

        # 載入所有 plugin hooks（按 plugin 分組）
        plugin_hooks_dict = loader.load_plugin_hooks(workspace_id)

        # 合併為單一字典（event_name → List[HookRule]）
        all_hooks = {}

        for plugin_id, hooks_config in plugin_hooks_dict.items():
            plugin_name, marketplace_name = plugin_id.split("@")

            for event_name, rules in hooks_config.items():
                if event_name not in all_hooks:
                    all_hooks[event_name] = []

                # 為每個 rule 附加 plugin 來源資訊
                for rule in rules:
                    rule_with_source = {
                        **rule,
                        "pluginName": plugin_name,
                        "marketplaceName": marketplace_name
                    }
                    all_hooks[event_name].append(HookRule.model_validate(rule_with_source))

        return all_hooks

    def _build_plugin_sources(
        self,
        hooks: Dict[str, List[HookRule]]
    ) -> Dict[str, str]:
        """
        建構 plugin 來源映射表

        用於前端顯示每個 hook rule 的來源
        """
        sources = {}
        for event_name, rules in hooks.items():
            for i, rule in enumerate(rules):
                if hasattr(rule, 'plugin_name') and rule.plugin_name:
                    key = f"{event_name}:{i}"
                    sources[key] = f"{rule.plugin_name}@{rule.marketplace_name}"
        return sources

