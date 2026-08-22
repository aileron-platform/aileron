"""Codex settings service."""

from __future__ import annotations

import json
import re
import subprocess
from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Iterable, Literal, Mapping, Never, overload

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.cache import ProcessTTLCache
from app.modules.cli_settings.raw_file import (
    RawFileError,
    RawFileFailure,
    raw_file_parts,
    read_raw_file,
)
from app.modules.cli_settings.toml_codec import (
    dump_toml,
    merge_known_values,
    parse_toml,
)
from app.modules.cli_settings.user_scope.codecs import (
    TomlDocumentCodec,
    read_text,
    remove_file_exact,
    write_text_atomic,
)
from app.modules.cli_settings.user_scope.models import (
    CodexLayer,
    CodexResource,
)
from app.modules.cli_settings.user_scope.paths import (
    CodexPathResolver,
    get_codex_path_resolver,
    logical_runtime_locator,
)
from app.modules.marketplace_operations.gate import get_marketplace_target_client_gate
from app.modules.marketplace_operations.plugin_resources import (
    plugin_resource_provenance,
    sanitize_plugin_definition,
)

from .models import (
    CodexAppResource,
    CodexAppResponse,
    CodexAppsResponse,
    CodexConfigDocument,
    CodexConfigSectionResponse,
    CodexConfigSectionUpdateResponse,
    CodexFeatureEnableResponse,
    CodexFileListResponse,
    CodexFileSummary,
    CodexHookCommandAction,
    CodexHookEntry,
    CodexHookEventMetadata,
    CodexHooksDocumentResponse,
    CodexHooksScopesResponse,
    CodexManagedRequirementsResponse,
    CodexManagedRequirementsSource,
    CodexOverviewManagedRequirementsState,
    CodexOverviewMemoryState,
    CodexOverviewPluginState,
    CodexOverviewResponse,
    CodexOverviewTrustState,
    CodexPluginAppDetail,
    CodexPluginDetail,
    CodexPluginDetailResponse,
    CodexPluginHookDetail,
    CodexPluginHookTrustUpdateResponse,
    CodexPluginMcpPolicy,
    CodexPluginMcpPolicyUpdateResponse,
    CodexPluginMcpServerDetail,
    CodexPluginScopeState,
    CodexPluginSkillDetail,
    CodexPluginsResponse,
    CodexPluginSummary,
    CodexPluginToggleResponse,
    CodexRulesFileSummary,
    CodexRulesListResponse,
    CodexRulesValidationResponse,
    CodexScopedTextFileResponse,
    CodexSubagentDefinition,
    CodexSubagentDeleteResponse,
    CodexSubagentItem,
    CodexSubagentRegistrySettings,
    CodexSubagentRegistrySource,
    CodexSubagentSaveRequest,
    CodexSubagentsResponse,
    CodexTextFileResponse,
    CodexTrustUpdateResponse,
)
from .plugin_controls import CodexPluginControlStore
from .plugin_resources import CodexPluginResourceResolver, CodexPluginSkill

_TOML_CODEC = TomlDocumentCodec(invalid_as_empty=False)
_RAW_PREVIEW_MAX_BYTES = 10 * 1024 * 1024
_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}
_CodexCollectionCacheKey = tuple[str, str, str, str, str]
_rules_cache: ProcessTTLCache[_CodexCollectionCacheKey, CodexRulesListResponse] = (
    ProcessTTLCache()
)
_subagents_cache: ProcessTTLCache[_CodexCollectionCacheKey, CodexSubagentsResponse] = (
    ProcessTTLCache()
)
_files_cache: ProcessTTLCache[_CodexCollectionCacheKey, CodexFileListResponse] = (
    ProcessTTLCache()
)


def _clear_codex_collection_cache(
    *,
    workspace_id: str | None = None,
    capability: str | None = None,
    scope: str | None = None,
) -> None:
    """Clear cached Codex collection summaries."""

    def matches(key: _CodexCollectionCacheKey) -> bool:
        return (
            (workspace_id is None or key[2] == workspace_id)
            and (capability is None or key[3] == capability)
            and (scope is None or key[4] in {scope, "all"})
        )

    _rules_cache.clear(matches)
    _subagents_cache.clear(matches)
    _files_cache.clear(matches)


ROOT_STRUCTURED_KEYS = {
    "model",
    "model_provider",
    "model_reasoning_effort",
    "model_reasoning_summary",
    "model_verbosity",
    "service_tier",
    "web_search",
    "personality",
    "plan_mode_reasoning_effort",
    "approval_policy",
    "sandbox_mode",
    "environment_policy",
    "commit_attribution",
    "notify",
    "default_permissions",
}

SECTION_KEYS = {
    "structured": None,
    "profiles": "profiles",
    "permissions-profiles": "permissions",
    "features": "features",
    "apps-connectors": "apps",
    "model-providers": "model_providers",
    "memories": "memories",
}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


FILE_RESOURCES = {
    "skills": CodexResource.SKILLS,
    "prompts": CodexResource.PROMPTS,
}

SUBAGENT_STRUCTURED_KEYS = {
    "name",
    "description",
    "developer_instructions",
    "nickname_candidates",
    "model",
    "model_reasoning_effort",
    "sandbox_mode",
    "mcp_servers",
    "skills",
}

BUILT_IN_SUBAGENTS = [
    {
        "name": "default",
        "description": "General-purpose fallback agent.",
        "developer_instructions": "Use the default Codex behavior inherited from the parent session.",
    },
    {
        "name": "worker",
        "description": "Execution-focused agent for implementation and fixes.",
        "developer_instructions": "Own implementation tasks, make focused edits, and report changed files.",
    },
    {
        "name": "explorer",
        "description": "Read-heavy codebase exploration agent.",
        "developer_instructions": "Trace code paths, cite files and symbols, and avoid code changes.",
    },
]

HOOK_EVENT_METADATA = [
    CodexHookEventMetadata(
        event="SessionStart",
        scope="start",
        matcherSupported=True,
        matcherTarget="source",
        matcherExamples=["startup", "resume", "clear"],
    ),
    CodexHookEventMetadata(
        event="SubagentStart",
        scope="start",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="PreToolUse",
        scope="turn",
        matcherSupported=True,
        matcherTarget="tool_name",
        matcherExamples=["Bash", "apply_patch", "Edit", "Write", "mcp__filesystem__.*"],
    ),
    CodexHookEventMetadata(
        event="PermissionRequest",
        scope="turn",
        matcherSupported=True,
        matcherTarget="tool_name",
        matcherExamples=["Bash", "apply_patch", "Edit", "Write", "mcp__filesystem__.*"],
    ),
    CodexHookEventMetadata(
        event="PostToolUse",
        scope="turn",
        matcherSupported=True,
        matcherTarget="tool_name",
        matcherExamples=["Bash", "apply_patch", "Edit", "Write", "mcp__filesystem__.*"],
    ),
    CodexHookEventMetadata(
        event="PreCompact",
        scope="turn",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="PostCompact",
        scope="turn",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="UserPromptSubmit",
        scope="turn",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="Stop",
        scope="turn",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="SubagentStop",
        scope="turn",
        matcherSupported=False,
        matcherTarget="none",
    ),
    CodexHookEventMetadata(
        event="SessionEnd",
        scope="end",
        matcherSupported=False,
        matcherTarget="none",
    ),
]


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return _TOML_CODEC.read(path)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_TOML"},
        ) from exc


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    _TOML_CODEC.write(path, data)


def _as_table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_json_document(content: str) -> Any:
    try:
        return json.loads(content or "{}")
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_JSON", "message": str(exc)},
        ) from exc


def _raise_invalid_hooks(error: str, message: str) -> Never:
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail={"error": error, "message": message},
    )


class CodexSettingsIntent(StrEnum):
    """User intentions supported by the Codex agent settings module."""

    GET_OVERVIEW = "get_overview"
    UPDATE_TRUST = "update_trust"
    GET_MANAGED_REQUIREMENTS = "get_managed_requirements"
    GET_CONFIG_DOCUMENT = "get_config_document"
    UPDATE_CONFIG_DOCUMENT = "update_config_document"
    GET_CONFIG_SECTION = "get_config_section"
    UPDATE_CONFIG_SECTION = "update_config_section"
    LIST_RULES = "list_rules"
    GET_RULES_FILE = "get_rules_file"
    UPDATE_RULES_FILE = "update_rules_file"
    DELETE_RULES_FILE = "delete_rules_file"
    VALIDATE_RULES_FILE = "validate_rules_file"
    GET_HOOKS_DOCUMENT = "get_hooks_document"
    LIST_HOOKS_DOCUMENTS = "list_hooks_documents"
    UPDATE_HOOKS_DOCUMENT = "update_hooks_document"
    UPSERT_HOOK_ENTRY = "upsert_hook_entry"
    DELETE_HOOK_ENTRY = "delete_hook_entry"
    ENABLE_CODEX_HOOKS = "enable_codex_hooks"
    DISABLE_CODEX_HOOKS = "disable_codex_hooks"
    LIST_APPS = "list_apps"
    GET_APP = "get_app"
    LIST_PLUGINS = "list_plugins"
    GET_PLUGIN_DETAIL = "get_plugin_detail"
    SET_PLUGIN_ENABLED = "set_plugin_enabled"
    UPDATE_PLUGIN_MCP_POLICY = "update_plugin_mcp_policy"
    UPDATE_PLUGIN_HOOK_TRUST = "update_plugin_hook_trust"
    LIST_SUBAGENTS = "list_subagents"
    SAVE_SUBAGENT = "save_subagent"
    DELETE_SUBAGENT = "delete_subagent"
    GET_SUBAGENT = "get_subagent"
    LIST_FILES = "list_files"
    GET_FILE = "get_file"
    GET_FILE_BINARY = "get_file_binary"
    UPDATE_FILE = "update_file"
    DELETE_FILE = "delete_file"
    REFRESH_CACHE = "refresh_cache"


CodexSettingsResult = (
    CodexOverviewResponse
    | CodexTrustUpdateResponse
    | CodexManagedRequirementsResponse
    | CodexConfigDocument
    | CodexConfigSectionResponse
    | CodexConfigSectionUpdateResponse
    | CodexRulesListResponse
    | CodexScopedTextFileResponse
    | CodexRulesValidationResponse
    | CodexHooksDocumentResponse
    | CodexHooksScopesResponse
    | CodexFeatureEnableResponse
    | CodexAppsResponse
    | CodexAppResponse
    | CodexPluginsResponse
    | CodexPluginMcpPolicyUpdateResponse
    | CodexPluginHookTrustUpdateResponse
    | CodexPluginDetailResponse
    | CodexPluginToggleResponse
    | CodexSubagentsResponse
    | CodexSubagentItem
    | CodexSubagentDeleteResponse
    | CodexFileListResponse
    | CodexTextFileResponse
    | bytes
    | dict[str, str]
    | None
)


class CodexAgentSettings:
    """Execute user intentions while hiding paths, caching, and plugin controls."""

    def __init__(
        self,
        *,
        user_home: Path | None = None,
        workspace_root: Path | None = None,
        plugin_inventory: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._resolver = (
            CodexPathResolver(user_home=user_home, workspace_root=workspace_root)
            if user_home is not None and workspace_root is not None
            else get_codex_path_resolver()
        )
        self._plugin_resolver = CodexPluginResourceResolver(
            self._resolver,
            inventory_loader=plugin_inventory,
        )
        self._plugin_controls = CodexPluginControlStore(
            self._resolver,
            self._plugin_resolver,
        )

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_OVERVIEW],
        workspace_id: str,
    ) -> CodexOverviewResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_TRUST],
        workspace_id: str,
        trusted: bool,
    ) -> CodexTrustUpdateResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_MANAGED_REQUIREMENTS],
        workspace_id: str,
    ) -> CodexManagedRequirementsResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_CONFIG_DOCUMENT],
        workspace_id: str,
        layer: CodexLayer | str,
    ) -> CodexConfigDocument: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_CONFIG_DOCUMENT],
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
        revision: str | None = None,
    ) -> CodexConfigDocument: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_CONFIG_SECTION],
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
    ) -> CodexConfigSectionResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_CONFIG_SECTION],
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
        data: dict[str, Any],
        revision: str | None = None,
    ) -> CodexConfigSectionUpdateResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_RULES],
        workspace_id: str,
        layer: CodexLayer | str,
    ) -> CodexRulesListResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_RULES_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
    ) -> CodexScopedTextFileResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_RULES_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
        content: str,
        revision: str | None = None,
    ) -> CodexScopedTextFileResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.DELETE_RULES_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
    ) -> dict[str, str]: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.VALIDATE_RULES_FILE],
        layer: CodexLayer | str,
        relative_path: str,
        command: list[str],
    ) -> CodexRulesValidationResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_HOOKS_DOCUMENT],
        workspace_id: str,
        layer: CodexLayer | str,
    ) -> CodexHooksDocumentResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_HOOKS_DOCUMENTS],
        workspace_id: str,
    ) -> CodexHooksScopesResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_HOOKS_DOCUMENT],
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
        revision: str,
    ) -> CodexHooksDocumentResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPSERT_HOOK_ENTRY],
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
        previous: CodexHookEntry | None = None,
    ) -> CodexHooksDocumentResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.DELETE_HOOK_ENTRY],
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
    ) -> CodexHooksDocumentResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.ENABLE_CODEX_HOOKS],
        workspace_id: str,
        layer: CodexLayer | str,
    ) -> CodexFeatureEnableResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_APPS],
        workspace_id: str,
        *,
        plugin_id: str | None = None,
    ) -> CodexAppsResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_APP],
        workspace_id: str,
        app_name: str,
        *,
        plugin_id: str | None = None,
    ) -> CodexAppResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_PLUGINS],
        workspace_id: str,
    ) -> CodexPluginsResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_PLUGIN_MCP_POLICY],
        workspace_id: str,
        plugin_id: str,
        server_id: str,
        policy: CodexPluginMcpPolicy,
        revision: str,
    ) -> CodexPluginMcpPolicyUpdateResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_PLUGIN_HOOK_TRUST],
        workspace_id: str,
        plugin_id: str,
        trusted: bool,
        revision: str,
    ) -> CodexPluginHookTrustUpdateResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_PLUGIN_DETAIL],
        workspace_id: str,
        plugin_id: str,
    ) -> CodexPluginDetailResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.SET_PLUGIN_ENABLED],
        workspace_id: str,
        plugin_id: str,
        scope: CodexLayer | str,
        enabled: bool,
        revision: str | None = None,
    ) -> CodexPluginToggleResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_SUBAGENTS],
        workspace_id: str,
    ) -> CodexSubagentsResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.SAVE_SUBAGENT],
        workspace_id: str,
        request: CodexSubagentSaveRequest,
    ) -> CodexSubagentItem: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.DELETE_SUBAGENT],
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
    ) -> CodexSubagentDeleteResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_SUBAGENT],
        workspace_id: str,
        source: str,
        relative_path: str,
    ) -> CodexSubagentItem: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.LIST_FILES],
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
    ) -> CodexFileListResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        *,
        plugin_id: str | None = None,
    ) -> CodexTextFileResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.GET_FILE_BINARY],
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        *,
        plugin_id: str | None = None,
    ) -> bytes: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.UPDATE_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        content: str,
        revision: str | None = None,
    ) -> CodexTextFileResponse: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.DELETE_FILE],
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
    ) -> dict[str, str]: ...

    @overload
    def execute(
        self,
        intent: Literal[CodexSettingsIntent.REFRESH_CACHE],
        *,
        workspace_id: str | None = None,
        capability: str | None = None,
        scope: str | None = None,
    ) -> None: ...

    def execute(
        self,
        intent: CodexSettingsIntent,
        *arguments: Any,
        **options: Any,
    ) -> CodexSettingsResult:
        """Execute one supported Codex settings intention."""

        if intent is CodexSettingsIntent.GET_OVERVIEW:
            return self._get_overview(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_TRUST:
            return self._update_trust(*arguments, **options)
        if intent is CodexSettingsIntent.GET_MANAGED_REQUIREMENTS:
            return self._get_managed_requirements(*arguments, **options)
        if intent is CodexSettingsIntent.GET_CONFIG_DOCUMENT:
            return self._get_config_document(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_CONFIG_DOCUMENT:
            return self._update_config_document(*arguments, **options)
        if intent is CodexSettingsIntent.GET_CONFIG_SECTION:
            return self._get_config_section(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_CONFIG_SECTION:
            return self._update_config_section(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_RULES:
            return self._list_rules(*arguments, **options)
        if intent is CodexSettingsIntent.GET_RULES_FILE:
            return self._get_rules_file(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_RULES_FILE:
            return self._update_rules_file(*arguments, **options)
        if intent is CodexSettingsIntent.DELETE_RULES_FILE:
            return self._delete_rules_file(*arguments, **options)
        if intent is CodexSettingsIntent.VALIDATE_RULES_FILE:
            return self._validate_rules_file(*arguments, **options)
        if intent is CodexSettingsIntent.GET_HOOKS_DOCUMENT:
            return self._get_hooks_document(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_HOOKS_DOCUMENTS:
            return self._list_hooks_documents(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_HOOKS_DOCUMENT:
            return self._update_hooks_document(*arguments, **options)
        if intent is CodexSettingsIntent.UPSERT_HOOK_ENTRY:
            return self._upsert_hook_entry(*arguments, **options)
        if intent is CodexSettingsIntent.DELETE_HOOK_ENTRY:
            return self._delete_hook_entry(*arguments, **options)
        if intent is CodexSettingsIntent.ENABLE_CODEX_HOOKS:
            return self._enable_codex_hooks(*arguments, **options)
        if intent is CodexSettingsIntent.DISABLE_CODEX_HOOKS:
            return self._disable_codex_hooks(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_APPS:
            return self._list_apps(*arguments, **options)
        if intent is CodexSettingsIntent.GET_APP:
            return self._get_app(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_PLUGINS:
            return self._list_plugins(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_PLUGIN_MCP_POLICY:
            return self._update_plugin_mcp_policy(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_PLUGIN_HOOK_TRUST:
            return self._update_plugin_hook_trust(*arguments, **options)
        if intent is CodexSettingsIntent.GET_PLUGIN_DETAIL:
            return self._get_plugin_detail(*arguments, **options)
        if intent is CodexSettingsIntent.SET_PLUGIN_ENABLED:
            return self._set_plugin_enabled(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_SUBAGENTS:
            return self._list_subagents(*arguments, **options)
        if intent is CodexSettingsIntent.SAVE_SUBAGENT:
            return self._save_subagent(*arguments, **options)
        if intent is CodexSettingsIntent.DELETE_SUBAGENT:
            return self._delete_subagent(*arguments, **options)
        if intent is CodexSettingsIntent.GET_SUBAGENT:
            return self._get_subagent(*arguments, **options)
        if intent is CodexSettingsIntent.LIST_FILES:
            return self._list_files(*arguments, **options)
        if intent is CodexSettingsIntent.GET_FILE:
            return self._get_file(*arguments, **options)
        if intent is CodexSettingsIntent.GET_FILE_BINARY:
            return self._get_file_binary(*arguments, **options)
        if intent is CodexSettingsIntent.UPDATE_FILE:
            return self._update_file(*arguments, **options)
        if intent is CodexSettingsIntent.DELETE_FILE:
            return self._delete_file(*arguments, **options)
        if intent is CodexSettingsIntent.REFRESH_CACHE:
            self._refresh_cache(*arguments, **options)
            return None
        raise ValueError(f"Unsupported Codex settings intent: {intent}")

    def _logical_locator(self, path: Path) -> str:
        """Map a runtime path to a stable user or workspace logical locator."""

        locator = logical_runtime_locator(
            path,
            user_home=self._resolver.user_home,
            workspace_root=self._resolver.workspace_root,
        )
        if locator is None:
            raise ValueError("Runtime path is outside logical locator roots")
        return locator

    def _refresh_cache(
        self,
        *,
        workspace_id: str | None = None,
        capability: str | None = None,
        scope: str | None = None,
    ) -> None:
        """Refresh cached Codex settings resources selected by user intent."""

        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability=capability,
            scope=scope,
        )

    def _get_overview(self, workspace_id: str) -> CodexOverviewResponse:
        user_config_path = self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG)
        user_config = _read_toml(user_config_path)
        profile_name = (
            user_config.get("profile")
            if isinstance(user_config.get("profile"), str)
            else None
        )
        active_profile = (
            _as_table(_as_table(user_config.get("profiles")).get(profile_name))
            if profile_name
            else {}
        )
        active_model = active_profile.get("model") or user_config.get("model")
        plugins = _as_table(user_config.get("plugins"))
        enabled_plugins = [
            plugin
            for plugin in plugins.values()
            if isinstance(plugin, dict) and plugin.get("enabled") is True
        ]
        disabled_plugins = [
            plugin
            for plugin in plugins.values()
            if isinstance(plugin, dict) and plugin.get("enabled") is False
        ]
        memory_config = _as_table(user_config.get("memories"))
        requirements = self._get_managed_requirements(workspace_id)

        return CodexOverviewResponse(
            workspaceId=workspace_id,
            setupReady=self._resolver.codex_home.exists(),
            codexHome=self._logical_locator(self._resolver.codex_home),
            activeModel=active_model if isinstance(active_model, str) else None,
            activeProfile=profile_name,
            trust=self._build_trust_state(user_config, user_config_path),
            plugins=CodexOverviewPluginState(
                configured=len(plugins),
                enabled=len(enabled_plugins),
                disabled=len(disabled_plugins),
            ),
            managedRequirements=CodexOverviewManagedRequirementsState(
                present=len(requirements.sources) > 0,
                count=len(requirements.sources),
                sources=[source.path for source in requirements.sources],
            ),
            memories=CodexOverviewMemoryState(
                use=(
                    memory_config.get("use")
                    if isinstance(memory_config.get("use"), bool)
                    else None
                ),
                generate=(
                    memory_config.get("generate")
                    if isinstance(memory_config.get("generate"), bool)
                    else None
                ),
            ),
        )

    def _update_trust(
        self, workspace_id: str, trusted: bool
    ) -> CodexTrustUpdateResponse:
        user_config_path = self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG)
        user_config = _read_toml(user_config_path)
        projects = _as_table(user_config.get("projects"))
        workspace_path = str(self._resolver.workspace_root)
        project_config = _as_table(projects.get(workspace_path))
        project_config["trust_level"] = "trusted" if trusted else "untrusted"
        projects[workspace_path] = project_config
        user_config["projects"] = projects
        _write_toml(user_config_path, user_config)
        return CodexTrustUpdateResponse(
            workspaceId=workspace_id,
            trust=self._build_trust_state(user_config, user_config_path),
        )

    def _get_managed_requirements(
        self, workspace_id: str
    ) -> CodexManagedRequirementsResponse:
        sources: list[CodexManagedRequirementsSource] = []
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            path = self._resolver.resolve(layer, CodexResource.MANAGED_REQUIREMENTS)
            if path.is_file():
                content = read_text(path)
                sources.append(
                    CodexManagedRequirementsSource(
                        layer=layer.value,
                        path=self._logical_locator(path),
                        content=content,
                        sizeBytes=len(content.encode("utf-8")),
                    ),
                )
        return CodexManagedRequirementsResponse(
            workspaceId=workspace_id, sources=sources
        )

    def _get_config_document(
        self, workspace_id: str, layer: CodexLayer | str
    ) -> CodexConfigDocument:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        content = read_text(path)
        return CodexConfigDocument(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=path.is_file(),
            revision=compute_revision(content),
        )

    def _update_config_document(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
        revision: str | None = None,
    ) -> CodexConfigDocument:
        try:
            parse_toml(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_TOML", "message": str(exc)},
            ) from exc
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        with _write_lock(path):
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
            write_text_atomic(path, content)
        self._advance_and_clear_cache(
            workspace_id,
            scope=codex_layer.value,
        )
        return CodexConfigDocument(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=True,
            revision=compute_revision(content),
        )

    def _get_config_section(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
    ) -> CodexConfigSectionResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        data = self._section_data(config, section)
        content = read_text(path)
        return CodexConfigSectionResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            section=section,
            path=self._logical_locator(path),
            data=data,
            revision=compute_revision(content),
        )

    def _update_config_section(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
        data: dict[str, Any],
        revision: str | None = None,
    ) -> CodexConfigSectionUpdateResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        with _write_lock(path):
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
            config = parse_toml(current_content) if current_content else {}
            if section == "structured":
                updates = {
                    key: value
                    for key, value in data.items()
                    if key in ROOT_STRUCTURED_KEYS
                }
                next_config = merge_known_values(config, updates)
                next_data = {
                    key: next_config[key]
                    for key in ROOT_STRUCTURED_KEYS
                    if key in next_config
                }
            else:
                section_key = self._section_key(section)
                next_config = merge_known_values(config, {section_key: data})
                next_data = _as_table(next_config.get(section_key))
            _write_toml(path, next_config)
            next_content = read_text(path)
        self._advance_and_clear_cache(
            workspace_id,
            scope=codex_layer.value,
        )
        return CodexConfigSectionUpdateResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            section=section,
            path=self._logical_locator(path),
            data=next_data,
            revision=compute_revision(next_content),
        )

    def _list_rules(
        self, workspace_id: str, layer: CodexLayer | str
    ) -> CodexRulesListResponse:
        codex_layer = CodexLayer(layer)
        key = self._collection_cache_key(
            workspace_id,
            "rules",
            codex_layer.value,
        )
        return deepcopy(
            _rules_cache.get_or_load(
                key,
                lambda: self._list_rules_uncached(workspace_id, codex_layer),
            )
        )

    def _list_rules_uncached(
        self,
        workspace_id: str,
        codex_layer: CodexLayer,
    ) -> CodexRulesListResponse:
        directory = self._resolver.resolve(codex_layer, CodexResource.RULES)
        files = (
            [
                CodexRulesFileSummary(
                    name=path.name,
                    path=path.name,
                    sizeBytes=path.stat().st_size,
                    scope=codex_layer.value,
                )
                for path in sorted(directory.glob("*.rules"))
                if path.is_file()
            ]
            if directory.is_dir()
            else []
        )
        return CodexRulesListResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            directory=self._logical_locator(directory),
            files=files,
        )

    def _get_rules_file(
        self, workspace_id: str, layer: CodexLayer | str, relative_path: str
    ) -> CodexScopedTextFileResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        content = read_text(path)
        return CodexScopedTextFileResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=path.is_file(),
            revision=compute_revision(content),
        )

    def _update_rules_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
        content: str,
        revision: str | None = None,
    ) -> CodexScopedTextFileResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        with _write_lock(path):
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
            write_text_atomic(path, content)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability="rules",
            scope=codex_layer.value,
        )
        return self._get_rules_file(workspace_id, codex_layer, relative_path)

    def _delete_rules_file(
        self, workspace_id: str, layer: CodexLayer | str, relative_path: str
    ) -> dict[str, str]:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        if path.exists():
            remove_file_exact(path)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability="rules",
            scope=codex_layer.value,
        )
        return {
            "workspaceId": workspace_id,
            "scope": codex_layer.value,
            "path": self._logical_locator(path),
        }

    def _validate_rules_file(
        self,
        layer: CodexLayer | str,
        relative_path: str,
        command: list[str],
    ) -> CodexRulesValidationResponse:
        if not command:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "EMPTY_COMMAND",
                    "message": "Command must not be empty",
                },
            )
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        try:
            result = subprocess.run(
                ["codex", "execpolicy", "check", "--rules", str(path), *command],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except FileNotFoundError:
            return CodexRulesValidationResponse(
                valid=False,
                exitCode=127,
                stderr="codex CLI is not available in this runtime",
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout or ""
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else exc.stderr or "codex execpolicy check timed out"
            )
            return CodexRulesValidationResponse(
                valid=False,
                exitCode=124,
                stdout=stdout,
                stderr=stderr,
            )
        return CodexRulesValidationResponse(
            valid=result.returncode == 0,
            exitCode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def _get_hooks_document(
        self, workspace_id: str, layer: CodexLayer | str
    ) -> CodexHooksDocumentResponse:
        shared = self._shared_hook_sources()
        return self._get_hooks_document_with_shared_sources(workspace_id, layer, shared)

    def _list_hooks_documents(self, workspace_id: str) -> CodexHooksScopesResponse:
        shared = self._shared_hook_sources()
        documents = [
            self._get_hooks_document_with_shared_sources(
                workspace_id, CodexLayer.PROJECT, shared
            ),
            self._get_hooks_document_with_shared_sources(
                workspace_id, CodexLayer.USER, shared
            ),
        ]
        for layer in (CodexLayer.PROJECT, CodexLayer.USER):
            inline_document = self._get_inline_hooks_document(
                workspace_id, layer, shared
            )
            if inline_document is not None:
                documents.append(inline_document)
        plugin_entries = shared["plugin_entries"]
        if plugin_entries:
            documents.append(
                CodexHooksDocumentResponse(
                    workspaceId=workspace_id,
                    scope="plugin",
                    path="",
                    content="",
                    exists=False,
                    revision=compute_revision(
                        json.dumps(
                            [entry.model_dump(mode="json") for entry in plugin_entries],
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    ),
                    featureEnabled=shared["effective_feature_enabled"],
                    effectiveFeatureEnabled=shared["effective_feature_enabled"],
                    readOnly=True,
                    editable=False,
                    source="plugin",
                    inlineHooks=[],
                    entries=plugin_entries,
                    eventMetadata=HOOK_EVENT_METADATA,
                    providerResourceGeneration=shared["provider_generation"],
                )
            )
        return CodexHooksScopesResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=shared["provider_generation"],
            scopes=documents,
        )

    def _get_hooks_document_with_shared_sources(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        shared: dict[str, Any],
    ) -> CodexHooksDocumentResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        content = read_text(path)
        structured_entries = self._structured_hooks(
            codex_layer,
            content,
            path,
        )
        return CodexHooksDocumentResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=path.is_file(),
            revision=compute_revision(content),
            featureEnabled=shared["feature_enabled_by_layer"][codex_layer.value],
            effectiveFeatureEnabled=shared["effective_feature_enabled"],
            readOnly=False,
            editable=True,
            source="hooks_json",
            inlineHooks=[],
            entries=structured_entries,
            eventMetadata=HOOK_EVENT_METADATA,
            providerResourceGeneration=shared["provider_generation"],
        )

    def _get_inline_hooks_document(
        self,
        workspace_id: str,
        layer: CodexLayer,
        shared: dict[str, Any],
    ) -> CodexHooksDocumentResponse | None:
        path = self._resolver.resolve(layer, CodexResource.CONFIG)
        content = read_text(path)
        config = _read_toml(path)
        hooks_value = config.get("hooks")
        if not isinstance(hooks_value, dict):
            return None
        return CodexHooksDocumentResponse(
            workspaceId=workspace_id,
            scope=layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=path.is_file(),
            revision=compute_revision(content),
            featureEnabled=shared["feature_enabled_by_layer"][layer.value],
            effectiveFeatureEnabled=shared["effective_feature_enabled"],
            readOnly=False,
            editable=True,
            source="inline_config",
            inlineHooks=[hooks_value],
            entries=shared["inline_entries_by_layer"].get(layer.value, []),
            eventMetadata=HOOK_EVENT_METADATA,
            providerResourceGeneration=shared["provider_generation"],
        )

    def _shared_hook_sources(self) -> dict[str, Any]:
        provider_generation = self._provider_generation()
        inline_entries = self._inline_hook_entries(self._inline_hooks())
        inline_entries_by_layer = {
            layer: [item for item in inline_entries if item.layer == layer]
            for layer in ("project", "user")
        }
        return {
            "effective_feature_enabled": self._codex_hooks_enabled(),
            "feature_enabled_by_layer": {
                "project": self._codex_hooks_enabled(CodexLayer.PROJECT),
                "user": self._codex_hooks_enabled(CodexLayer.USER),
            },
            "inline_entries_by_layer": inline_entries_by_layer,
            "plugin_entries": self._plugin_hook_entries(provider_generation),
            "provider_generation": provider_generation,
        }

    def _update_hooks_document(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
        revision: str,
    ) -> CodexHooksDocumentResponse:
        self._validate_hooks_document(content)
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        with _write_lock(path):
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
            write_text_atomic(path, content)
        self._advance_and_clear_cache(
            workspace_id,
            capability="hooks",
            scope=codex_layer.value,
        )
        return self._get_hooks_document(workspace_id, codex_layer)

    def _upsert_hook_entry(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
        previous: CodexHookEntry | None = None,
    ) -> CodexHooksDocumentResponse:
        if entry.source == "inline_config":
            return self._upsert_inline_hook_entry(
                workspace_id, layer, entry, revision, previous
            )
        if entry.source != "hooks_json":
            _raise_invalid_hooks(
                "READ_ONLY_HOOK_ENTRY",
                "Only user and project hook sources are editable",
            )
        if previous is not None and previous.source != "hooks_json":
            _raise_invalid_hooks(
                "READ_ONLY_HOOK_ENTRY", "Only hooks.json entries are editable"
            )

        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        entries = self._structured_hooks(
            codex_layer,
            read_text(path),
            path,
        )
        entries = [
            current
            for current in entries
            if not self._same_hook_entry(current, entry)
            and (previous is None or not self._same_hook_entry(current, previous))
        ]
        entries.append(
            entry.model_copy(
                update={
                    "layer": codex_layer.value,
                    "source": "hooks_json",
                    "readOnly": False,
                }
            )
        )
        content = json.dumps({"hooks": self._event_map_from_entries(entries)}, indent=2)
        return self._update_hooks_document(workspace_id, codex_layer, content, revision)

    def _delete_hook_entry(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
    ) -> CodexHooksDocumentResponse:
        if entry.source == "inline_config":
            return self._delete_inline_hook_entry(workspace_id, layer, entry, revision)
        if entry.source != "hooks_json":
            _raise_invalid_hooks(
                "READ_ONLY_HOOK_ENTRY",
                "Only user and project hook sources are editable",
            )

        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        entries = self._structured_hooks(
            codex_layer,
            read_text(path),
            path,
        )
        entries = [
            current for current in entries if not self._same_hook_entry(current, entry)
        ]
        content = json.dumps({"hooks": self._event_map_from_entries(entries)}, indent=2)
        return self._update_hooks_document(workspace_id, codex_layer, content, revision)

    def _inline_hook_entries_for_layer(
        self,
        layer: CodexLayer,
        config: dict[str, Any],
    ) -> list[CodexHookEntry]:
        entries = self._inline_hook_entries_from_value(
            layer,
            config.get("hooks"),
        )
        return [entry for entry in entries if entry.layer == layer.value]

    def _inline_hook_entries_from_value(
        self,
        layer: CodexLayer,
        value: Any,
    ) -> list[CodexHookEntry]:
        inline_items: list[dict[str, Any]] = []
        if isinstance(value, dict):
            for event, event_hooks in value.items():
                if not isinstance(event_hooks, list):
                    continue
                for item in event_hooks:
                    if isinstance(item, dict):
                        inline_items.append(
                            {"layer": layer.value, "event": event, "hook": item}
                        )
        return self._inline_hook_entries(inline_items) if inline_items else []

    def _write_inline_hook_entries(
        self,
        workspace_id: str,
        layer: CodexLayer,
        entries: list[CodexHookEntry],
        revision: str,
    ) -> CodexHooksDocumentResponse:
        path = self._resolver.resolve(layer, CodexResource.CONFIG)
        with _write_lock(path):
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
            config = parse_toml(current_content) if current_content else {}
            hooks_table = _as_table(config.get("hooks"))
            event_map = self._event_map_from_entries(entries)
            self._validate_hooks_document(json.dumps(event_map))
            for event in list(hooks_table):
                if event in HOOK_EVENT_METADATA or event in event_map:
                    hooks_table.pop(event, None)
            hooks_table.update(event_map)
            config["hooks"] = hooks_table
            _write_toml(path, config)
        self._advance_and_clear_cache(
            workspace_id,
            capability="hooks",
            scope=layer.value,
        )
        shared = self._shared_hook_sources()
        return self._get_inline_hooks_document(
            workspace_id, layer, shared
        ) or CodexHooksDocumentResponse(
            workspaceId=workspace_id,
            scope=layer.value,
            path=self._logical_locator(path),
            content=read_text(path),
            exists=path.is_file(),
            revision=compute_revision(read_text(path)),
            featureEnabled=shared["feature_enabled_by_layer"][layer.value],
            effectiveFeatureEnabled=shared["effective_feature_enabled"],
            readOnly=False,
            editable=True,
            source="inline_config",
            inlineHooks=[],
            entries=entries,
            eventMetadata=HOOK_EVENT_METADATA,
            providerResourceGeneration=shared["provider_generation"],
        )

    def _upsert_inline_hook_entry(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
        previous: CodexHookEntry | None,
    ) -> CodexHooksDocumentResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        entries = self._inline_hook_entries_for_layer(codex_layer, config)
        entries = [
            current
            for current in entries
            if not self._same_hook_entry(current, entry)
            and (previous is None or not self._same_hook_entry(current, previous))
        ]
        entries.append(
            entry.model_copy(
                update={
                    "layer": codex_layer.value,
                    "source": "inline_config",
                    "readOnly": False,
                    "editable": True,
                }
            )
        )
        return self._write_inline_hook_entries(
            workspace_id, codex_layer, entries, revision
        )

    def _delete_inline_hook_entry(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        entry: CodexHookEntry,
        revision: str,
    ) -> CodexHooksDocumentResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        entries = [
            current
            for current in self._inline_hook_entries_for_layer(codex_layer, config)
            if not self._same_hook_entry(current, entry)
        ]
        return self._write_inline_hook_entries(
            workspace_id, codex_layer, entries, revision
        )

    def _enable_codex_hooks(
        self, workspace_id: str, layer: CodexLayer | str
    ) -> CodexFeatureEnableResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        features = _as_table(config.get("features"))
        features["hooks"] = True
        config["features"] = features
        _write_toml(path, config)
        self._advance_and_clear_cache(
            workspace_id,
            capability="hooks",
            scope=codex_layer.value,
        )
        return CodexFeatureEnableResponse(workspaceId=workspace_id, featureEnabled=True)

    def _disable_codex_hooks(
        self, workspace_id: str, layer: CodexLayer | str
    ) -> CodexFeatureEnableResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        features = _as_table(config.get("features"))
        features["hooks"] = False
        config["features"] = features
        _write_toml(path, config)
        self._advance_and_clear_cache(
            workspace_id,
            capability="hooks",
            scope=codex_layer.value,
        )
        return CodexFeatureEnableResponse(
            workspaceId=workspace_id, featureEnabled=False
        )

    def _list_apps(
        self,
        workspace_id: str,
        *,
        plugin_id: str | None = None,
    ) -> CodexAppsResponse:
        """Return read-only apps and connectors from installed plugin roots."""

        generation = self._provider_generation()
        self._plugin_resolver.start_request_snapshot()
        resources = [
            item
            for item in self._plugin_resolver.apps()
            if plugin_id is None or item.plugin.plugin_id == plugin_id
        ]
        return CodexAppsResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=generation,
            apps=[
                self._codex_app_resource(item, generation=generation)
                for item in resources
            ],
        )

    def _get_app(
        self,
        workspace_id: str,
        app_name: str,
        *,
        plugin_id: str | None = None,
    ) -> CodexAppResponse:
        """Return one unambiguous installed plugin app definition."""

        generation = self._provider_generation()
        self._plugin_resolver.start_request_snapshot()
        matches = [
            item
            for item in self._plugin_resolver.apps()
            if item.name == app_name
            and (plugin_id is None or item.plugin.plugin_id == plugin_id)
        ]
        if not matches:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "marketplace.settings.plugin_resource_not_found"},
            )
        if len(matches) > 1:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"errorCode": "marketplace.settings.plugin_resource_ambiguous"},
            )
        return CodexAppResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=generation,
            app=self._codex_app_resource(matches[0], generation=generation),
        )

    def _list_plugins(self, workspace_id: str) -> CodexPluginsResponse:
        self._plugin_resolver.start_request_snapshot()
        configured = self._configured_plugins()
        configured_by_layer = self._configured_plugins_by_layer()
        discovered = self._discovered_plugins()
        all_ids = sorted(set(configured) | set(discovered))
        plugins = [
            CodexPluginSummary(
                id=plugin_id,
                name=str(
                    self._plugin_data(discovered, plugin_id).get("name")
                    or plugin_id.split("@", 1)[0]
                ),
                displayName=str(
                    self._plugin_data(discovered, plugin_id).get("displayName")
                    or self._plugin_data(discovered, plugin_id).get("name")
                    or plugin_id.split("@", 1)[0]
                ),
                shortDescription=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("shortDescription")
                ),
                version=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("version")
                ),
                authorName=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("authorName")
                ),
                category=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("category")
                ),
                capabilities=self._string_list(
                    self._plugin_data(discovered, plugin_id).get("capabilities")
                ),
                brandColor=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("brandColor")
                ),
                homepage=self._optional_str(
                    self._plugin_data(discovered, plugin_id).get("homepage")
                ),
                marketplace=(
                    str(
                        self._plugin_data(discovered, plugin_id).get("marketplace")
                        or plugin_id.split("@", 1)[1]
                    )
                    if "@" in plugin_id
                    else None
                ),
                listed=bool(self._plugin_data(discovered, plugin_id).get("listed")),
                installed=bool(
                    self._plugin_data(discovered, plugin_id).get("installed")
                ),
                effectiveEnabled=self._effective_plugin_enabled(
                    plugin_id, configured_by_layer
                ),
                scopes=self._plugin_scope_states(plugin_id, configured_by_layer),
                resourceCounts=self._resource_counts(
                    self._plugin_data(discovered, plugin_id)
                ),
            )
            for plugin_id in all_ids
        ]
        generation = self._provider_generation()
        return CodexPluginsResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=generation,
            plugins=plugins,
        )

    @staticmethod
    def _plugin_data(
        discovered: dict[str, dict[str, Any]], plugin_id: str
    ) -> dict[str, Any]:
        return discovered.get(plugin_id, {})

    def _get_plugin_detail(
        self, workspace_id: str, plugin_id: str
    ) -> CodexPluginDetailResponse:
        self._validate_plugin_id(plugin_id)
        self._plugin_resolver.start_request_snapshot()
        package = next(
            (
                item
                for item in self._plugin_resolver.packages()
                if item.plugin_id == plugin_id
            ),
            None,
        )
        if package is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id},
            )

        manifest = package.manifest
        resolved_resources = self._plugin_resolver._resources(package)
        metadata = sanitize_plugin_definition(
            self._codex_plugin_metadata(
                manifest,
                package.plugin_id,
                package.name,
                package.marketplace_name,
            ),
            installed_root=package.package_root,
        )
        sanitized_manifest = sanitize_plugin_definition(
            manifest,
            installed_root=package.package_root,
        )
        sanitized_interface = _as_table(sanitized_manifest.get("interface"))
        configured_by_layer = self._configured_plugins_by_layer()
        readme_path = package.package_root / "README.md"
        skills = self._codex_plugin_skill_details(package)
        policy_revision = self._plugin_controls.user_revision()
        generation = self._provider_generation()
        mcp_servers = self._codex_plugin_mcp_details(
            package,
            policy_revision=policy_revision,
            generation=generation,
        )
        apps = self._codex_plugin_app_details(package)
        hooks = self._codex_plugin_hook_details(
            package,
            generation=generation,
        )
        detail = CodexPluginDetail(
            id=package.plugin_id,
            name=package.name,
            displayName=metadata["displayName"],
            marketplace=package.marketplace_name,
            version=metadata.get("version"),
            authorName=metadata.get("authorName"),
            shortDescription=metadata.get("shortDescription"),
            longDescription=self._optional_str(
                sanitized_interface.get("longDescription")
                or sanitized_manifest.get("longDescription")
            ),
            category=metadata.get("category"),
            capabilities=self._string_list(metadata.get("capabilities")),
            brandColor=metadata.get("brandColor"),
            homepage=metadata.get("homepage"),
            keywords=self._string_list(
                sanitized_interface.get("keywords")
                or sanitized_manifest.get("keywords")
            ),
            license=self._optional_str(sanitized_manifest.get("license")),
            repository=self._optional_str(sanitized_manifest.get("repository")),
            websiteURL=self._optional_str(
                sanitized_manifest.get("websiteURL")
                or sanitized_manifest.get("websiteUrl")
            ),
            privacyPolicyURL=self._optional_str(
                sanitized_manifest.get("privacyPolicyURL")
                or sanitized_manifest.get("privacyPolicyUrl")
            ),
            termsOfServiceURL=self._optional_str(
                sanitized_manifest.get("termsOfServiceURL")
                or sanitized_manifest.get("termsOfServiceUrl")
            ),
            defaultPrompts=list(resolved_resources.default_prompts),
            readme=(read_text(readme_path) if readme_path.is_file() else None),
            skills=skills,
            mcpServers=mcp_servers,
            apps=apps,
            hooks=hooks,
            effectiveEnabled=self._effective_plugin_enabled(
                package.plugin_id, configured_by_layer
            ),
            scopes=self._plugin_scope_states(package.plugin_id, configured_by_layer),
        )
        return CodexPluginDetailResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=generation,
            plugin=detail,
        )

    def _set_plugin_enabled(
        self,
        workspace_id: str,
        plugin_id: str,
        scope: CodexLayer | str,
        enabled: bool,
        revision: str | None = None,
    ) -> CodexPluginToggleResponse:
        gate = get_marketplace_target_client_gate()
        self._validate_plugin_id(plugin_id)
        codex_layer = CodexLayer(scope)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)

        def mutate() -> str:
            with _write_lock(path):
                current_content = read_text(path)
                assert_revision(compute_revision(current_content), revision)
                config = parse_toml(current_content) if current_content else {}
                plugins = _as_table(config.get("plugins"))
                plugin_config = _as_table(plugins.get(plugin_id))
                plugin_config["enabled"] = enabled
                plugins[plugin_id] = plugin_config
                config["plugins"] = plugins
                _write_toml(path, config)
                next_content = read_text(path)
            self._plugin_resolver.clear_cache()
            return compute_revision(next_content)

        next_revision, generation = gate.run_settings_mutation(
            "codex",
            mutate,
        )
        self._clear_process_cache(workspace_id)
        return CodexPluginToggleResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            pluginId=plugin_id,
            enabled=enabled,
            revision=next_revision,
            providerResourceGeneration=generation,
        )

    def _update_plugin_mcp_policy(
        self,
        workspace_id: str,
        plugin_id: str,
        server_id: str,
        policy: CodexPluginMcpPolicy,
        revision: str,
    ) -> CodexPluginMcpPolicyUpdateResponse:
        """Replace one installed plugin MCP server policy."""

        self._validate_plugin_id(plugin_id)
        self._validate_plugin_resource_id(server_id)
        verified, effective, next_revision, generation = (
            self._plugin_controls.update_mcp_policy(
                plugin_id=plugin_id,
                server_id=server_id,
                policy=policy,
                revision=revision,
            )
        )
        self._clear_process_cache(workspace_id, capability="mcp")
        return CodexPluginMcpPolicyUpdateResponse(
            workspaceId=workspace_id,
            pluginId=plugin_id,
            serverId=server_id,
            policy=verified,
            effective=effective,
            revision=next_revision,
            providerResourceGeneration=generation,
        )

    def _update_plugin_hook_trust(
        self,
        workspace_id: str,
        plugin_id: str,
        trusted: bool,
        revision: str,
    ) -> CodexPluginHookTrustUpdateResponse:
        """Approve or revoke all command hooks contributed by one plugin."""

        self._validate_plugin_id(plugin_id)
        verified, next_revision, generation = (
            self._plugin_controls.update_plugin_hook_trust(
                plugin_id=plugin_id,
                trusted=trusted,
                revision=revision,
            )
        )
        self._clear_process_cache(workspace_id, capability="hooks")
        return CodexPluginHookTrustUpdateResponse(
            workspaceId=workspace_id,
            pluginId=plugin_id,
            trusted=verified.trusted,
            trustState=verified.trust_state,
            revision=next_revision,
            providerResourceGeneration=generation,
        )

    def _list_subagents(self, workspace_id: str) -> CodexSubagentsResponse:
        key = self._collection_cache_key(workspace_id, "subagents", "all")
        return deepcopy(
            _subagents_cache.get_or_load(
                key,
                lambda: self._list_subagents_uncached(workspace_id),
            )
        )

    def _list_subagents_uncached(self, workspace_id: str) -> CodexSubagentsResponse:
        items = [
            *self._editable_subagent_items(CodexLayer.USER),
            *self._editable_subagent_items(CodexLayer.PROJECT),
            *self._built_in_subagent_items(),
            *self._requirements_subagent_items(),
        ]
        self._apply_subagent_precedence(items)
        for item in items:
            if item.readOnly:
                item.content = ""
            elif item.definition is not None:
                item.content = ""
        items.sort(
            key=lambda item: (
                item.name,
                self._subagent_source_order(item),
                item.relativePath or item.path or "",
            )
        )
        return CodexSubagentsResponse(
            workspaceId=workspace_id,
            items=items,
            registry=self._subagent_registry_sources(),
        )

    def _save_subagent(
        self, workspace_id: str, request: CodexSubagentSaveRequest
    ) -> CodexSubagentItem:
        layer = CodexLayer(request.scope)
        if request.content is not None:
            content = request.content
            parsed = self._parse_subagent_toml(content)
            definition = self._definition_from_subagent_data(parsed)
        elif request.definition is not None:
            definition = self._validated_subagent_definition(request.definition)
            content = dump_toml(self._subagent_data_from_definition(definition))
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "MISSING_SUBAGENT_CONTENT",
                    "message": "content or definition is required",
                },
            )

        target_relative_path = request.path or self._subagent_filename(definition.name)
        previous_path = (
            self._resolve_subagent_file(layer, request.previousPath)
            if request.previousPath
            else None
        )
        target_path = self._resolve_subagent_file(layer, target_relative_path)
        if (
            target_path.exists()
            and previous_path != target_path
            and not request.overwrite
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "SUBAGENT_CONFLICT", "message": target_relative_path},
            )

        write_text_atomic(
            target_path,
            content if content.endswith("\n") else f"{content}\n",
        )
        if (
            previous_path is not None
            and previous_path != target_path
            and previous_path.exists()
        ):
            remove_file_exact(previous_path)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability="subagents",
        )
        return self._subagent_item_from_file(layer, target_path)

    def _delete_subagent(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
    ) -> CodexSubagentDeleteResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_subagent_file(codex_layer, relative_path)
        deleted = False
        if path.exists():
            deleted = remove_file_exact(path)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability="subagents",
            scope=codex_layer.value,
        )
        return CodexSubagentDeleteResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=relative_path,
            deleted=deleted,
        )

    def _get_subagent(
        self,
        workspace_id: str,
        source: str,
        relative_path: str,
    ) -> CodexSubagentItem:
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_SUBAGENT_PATH", "message": relative_path},
            )
        if source in {"project", "user"}:
            return self._subagent_item_from_file(
                CodexLayer(source),
                self._resolve_subagent_file(
                    CodexLayer(source),
                    relative_path,
                ),
            )
        if source == "built_in":
            item = next(
                (
                    item
                    for item in self._built_in_subagent_items()
                    if item.relativePath == relative_path or item.path == relative_path
                ),
                None,
            )
            if item is not None:
                return item
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"error": "SUBAGENT_NOT_FOUND", "message": relative_path},
        )

    def _list_files(
        self, workspace_id: str, layer: CodexLayer | str, resource: str
    ) -> CodexFileListResponse:
        scope_identity = layer.value if isinstance(layer, CodexLayer) else str(layer)
        key = self._collection_cache_key(
            workspace_id,
            resource,
            scope_identity,
        )
        return deepcopy(
            _files_cache.get_or_load(
                key,
                lambda: self._list_files_uncached(workspace_id, layer, resource),
            )
        )

    def _list_files_uncached(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
    ) -> CodexFileListResponse:
        if str(layer) == "all":
            scopes = ["project", "user"]
            if resource == "skills":
                scopes.append("plugin")
            responses = [
                self._list_files(workspace_id, scope, resource) for scope in scopes
            ]
            return CodexFileListResponse(
                workspaceId=workspace_id,
                scope="all",
                resource=resource,
                directory="",
                files=[item for response in responses for item in response.files],
                config=self._resource_config(resource),
            )
        if str(layer) == "plugin":
            if resource != "skills":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "errorCode": "marketplace.settings.plugin_scope_not_supported"
                    },
                )
            files = self._plugin_skill_summaries()
            return CodexFileListResponse(
                workspaceId=workspace_id,
                scope="plugin",
                resource=resource,
                directory="",
                files=files,
                config=self._resource_config(resource),
            )

        codex_layer = CodexLayer(layer)
        directory = self._file_resource_path(codex_layer, resource)
        files = (
            [
                CodexFileSummary(
                    name=path.name,
                    path=str(path.relative_to(directory)),
                    sizeBytes=path.stat().st_size,
                    source=codex_layer.value,
                    scope=codex_layer.value,
                    metadata=self._file_metadata(
                        resource, path.relative_to(directory), path.stat().st_size
                    ),
                )
                for path in sorted(directory.rglob("*"))
                if path.is_file()
            ]
            if directory.is_dir()
            else []
        )
        return CodexFileListResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            resource=resource,
            directory=self._logical_locator(directory),
            files=files,
            config=self._resource_config(resource),
        )

    def _get_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        plugin_id: str | None = None,
    ) -> CodexTextFileResponse:
        if str(layer) == "plugin":
            return self._get_plugin_file(
                workspace_id, resource, relative_path, plugin_id
            )
        codex_layer = CodexLayer(layer)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        content = read_text(path)
        return CodexTextFileResponse(
            workspaceId=workspace_id,
            scope=codex_layer.value,
            path=self._logical_locator(path),
            content=content,
            exists=path.is_file(),
            revision=compute_revision(content) if resource == "skills" else None,
        )

    def _get_file_binary(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        plugin_id: str | None = None,
    ) -> bytes:
        _ = workspace_id
        not_found_code = (
            "PLUGIN_FILE_NOT_FOUND" if str(layer) == "plugin" else "FILE_NOT_FOUND"
        )
        try:
            if str(layer) == "plugin":
                root, target_path = self._resolve_plugin_binary_file(
                    resource,
                    relative_path,
                    plugin_id,
                )
            else:
                root = self._file_resource_path(CodexLayer(layer), resource)
                target_path = relative_path
            return read_raw_file(root, target_path, _RAW_PREVIEW_MAX_BYTES)
        except HTTPException:
            raise
        except RawFileError as exc:
            self._raise_raw_file_error(exc, relative_path, not_found_code)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "FILE_READ_FAILED",
                    "message": "Unable to read requested file",
                },
            ) from exc

    @staticmethod
    def _raise_raw_file_error(
        error: RawFileError,
        relative_path: str,
        not_found_code: str,
    ) -> Never:
        if error.failure is RawFileFailure.INVALID_PATH:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_PATH", "message": relative_path},
            ) from error
        if error.failure is RawFileFailure.NOT_FOUND:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": not_found_code, "message": relative_path},
            ) from error
        if error.failure is RawFileFailure.TOO_LARGE:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "error": "FILE_TOO_LARGE",
                    "message": "Raw preview exceeds the configured size limit",
                },
            ) from error
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "FILE_READ_FAILED",
                "message": "Unable to read requested file",
            },
        ) from error

    def _update_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        content: str,
        revision: str | None = None,
    ) -> CodexTextFileResponse:
        codex_layer = CodexLayer(layer)
        self._validate_managed_file(resource, relative_path, content)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        if resource == "skills":
            current_content = read_text(path)
            assert_revision(compute_revision(current_content), revision)
        write_text_atomic(path, content)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability=resource,
            scope=codex_layer.value,
        )
        if resource == "skills":
            from app.modules.cli_settings.skills.catalog import clear_skill_tree_cache

            clear_skill_tree_cache(
                tool="codex",
                workspace_id=workspace_id,
                scope=codex_layer.value,
            )
        return self._get_file(workspace_id, codex_layer, resource, relative_path)

    def _delete_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
    ) -> dict[str, str]:
        codex_layer = CodexLayer(layer)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        if path.exists():
            remove_file_exact(path)
        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability=resource,
            scope=codex_layer.value,
        )
        if resource == "skills":
            from app.modules.cli_settings.skills.catalog import clear_skill_tree_cache

            clear_skill_tree_cache(
                tool="codex",
                workspace_id=workspace_id,
                scope=codex_layer.value,
            )
        return {
            "workspaceId": workspace_id,
            "scope": codex_layer.value,
            "resource": resource,
            "path": self._logical_locator(path),
        }

    def _build_trust_state(
        self, user_config: dict[str, Any], user_config_path: Path
    ) -> CodexOverviewTrustState:
        workspace_path = str(self._resolver.workspace_root)
        project_config = _as_table(
            _as_table(user_config.get("projects")).get(workspace_path)
        )
        trust_level = project_config.get("trust_level")
        return CodexOverviewTrustState(
            workspacePath=self._logical_locator(self._resolver.workspace_root),
            trustLevel=trust_level if isinstance(trust_level, str) else None,
            trusted=trust_level == "trusted",
            sourcePath=self._logical_locator(user_config_path),
            mutable=True,
        )

    def _section_key(self, section: str) -> str:
        if section not in SECTION_KEYS or SECTION_KEYS[section] is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "UNKNOWN_CONFIG_SECTION", "message": section},
            )
        return str(SECTION_KEYS[section])

    def _section_data(self, config: dict[str, Any], section: str) -> dict[str, Any]:
        if section == "structured":
            return {key: config[key] for key in ROOT_STRUCTURED_KEYS if key in config}
        section_key = self._section_key(section)
        return _as_table(config.get(section_key))

    def _resolve_rules_file(self, layer: CodexLayer, relative_path: str) -> Path:
        clean_path = Path(relative_path)
        if (
            clean_path.is_absolute()
            or ".." in clean_path.parts
            or clean_path.suffix != ".rules"
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_RULES_PATH", "message": relative_path},
            )
        return self._resolver.resolve(layer, CodexResource.RULES) / clean_path

    def _file_resource_path(self, layer: CodexLayer, resource: str) -> Path:
        if resource not in FILE_RESOURCES:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "UNKNOWN_FILE_RESOURCE", "message": resource},
            )
        return self._resolver.resolve(layer, FILE_RESOURCES[resource])

    def _resolve_managed_file(
        self, layer: CodexLayer, resource: str, relative_path: str
    ) -> Path:
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_PATH", "message": relative_path},
            )
        return self._file_resource_path(layer, resource) / clean_path

    def _get_plugin_file(
        self,
        workspace_id: str,
        resource: str,
        relative_path: str,
        plugin_id: str | None,
    ) -> CodexTextFileResponse:
        skill = self._resolve_plugin_skill(resource, relative_path, plugin_id)
        return CodexTextFileResponse(
            workspaceId=workspace_id,
            scope="plugin",
            path=skill.relative_source_path or skill.relative_path,
            content=read_text(skill.path),
            exists=True,
        )

    def _resolve_plugin_skill(
        self,
        resource: str,
        relative_path: str,
        plugin_id: str | None,
    ) -> CodexPluginSkill:
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_PATH", "message": relative_path},
            )
        if resource != "skills":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": "marketplace.settings.plugin_scope_not_supported"},
            )
        skill = self._plugin_resolver.find_skill(
            plugin_id,
            str(clean_path),
        )
        if skill is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "PLUGIN_FILE_NOT_FOUND", "message": relative_path},
            )
        return skill

    def _resolve_plugin_binary_file(
        self,
        resource: str,
        relative_path: str,
        plugin_id: str | None,
    ) -> tuple[Path, str]:
        if resource != "skills":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"errorCode": "marketplace.settings.plugin_scope_not_supported"},
            )
        requested_parts = raw_file_parts(relative_path)
        if plugin_id is None:
            raise RawFileError(RawFileFailure.NOT_FOUND)

        matches: dict[tuple[Path, str], int] = {}
        for skill in self._plugin_resolver.skills():
            if skill.plugin.plugin_id != plugin_id:
                continue
            package_root = skill.plugin.package_root
            try:
                source_relative = skill.path.relative_to(package_root)
            except ValueError:
                continue
            if (
                source_relative.is_absolute()
                or ".." in source_relative.parts
                or not source_relative.parts
            ):
                continue
            skill_root_relative = source_relative.parent
            for locator in (skill.relative_path, skill.relative_source_path):
                if not locator:
                    continue
                try:
                    logical_parts = raw_file_parts(locator)
                except RawFileError as exc:
                    raise RuntimeError("Invalid plugin skill inventory") from exc
                logical_root = logical_parts[:-1]
                if (
                    len(requested_parts) <= len(logical_root)
                    or requested_parts[: len(logical_root)] != logical_root
                ):
                    continue
                tail = requested_parts[len(logical_root) :]
                descriptor_path = (skill_root_relative / Path(*tail)).as_posix()
                key = (package_root, descriptor_path)
                matches[key] = max(matches.get(key, -1), len(logical_root))

        if not matches:
            raise RawFileError(RawFileFailure.NOT_FOUND)
        specificity = max(matches.values())
        selected = [target for target, score in matches.items() if score == specificity]
        if len(selected) != 1:
            raise RawFileError(RawFileFailure.NOT_FOUND)
        return selected[0]

    def _resolve_subagent_file(self, layer: CodexLayer, relative_path: str) -> Path:
        if not relative_path or not relative_path.strip():
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_SUBAGENT_PATH",
                    "target": "fileName",
                    "message": relative_path,
                },
            )
        clean_path = Path(relative_path)
        if (
            clean_path.is_absolute()
            or ".." in clean_path.parts
            or clean_path.suffix.lower() != ".toml"
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_SUBAGENT_PATH",
                    "target": "fileName",
                    "message": relative_path,
                },
            )
        return self._resolver.resolve(layer, CodexResource.SUBAGENTS) / clean_path

    def _editable_subagent_items(self, layer: CodexLayer) -> list[CodexSubagentItem]:
        directory = self._resolver.resolve(layer, CodexResource.SUBAGENTS)
        if not directory.is_dir():
            return []
        return [
            self._subagent_item_from_file(layer, path)
            for path in sorted(directory.glob("*.toml"))
            if path.is_file()
        ]

    def _subagent_item_from_file(
        self, layer: CodexLayer, path: Path
    ) -> CodexSubagentItem:
        directory = self._resolver.resolve(layer, CodexResource.SUBAGENTS)
        relative_path = str(path.relative_to(directory))
        content = read_text(path)
        data = self._parse_subagent_toml(content, path)
        definition = self._definition_from_subagent_data(data)
        return CodexSubagentItem(
            id=f"{layer.value}:{relative_path}",
            name=definition.name,
            source=layer.value,
            editable=True,
            readOnly=False,
            scope=layer.value,
            path=self._logical_locator(path),
            relativePath=relative_path,
            sourcePath=self._logical_locator(path),
            content=content,
            definition=definition,
            metadata={"sizeBytes": path.stat().st_size, "format": "toml"},
        )

    def _built_in_subagent_items(self) -> list[CodexSubagentItem]:
        return [
            CodexSubagentItem(
                id=f"built_in:{definition['name']}",
                name=definition["name"],
                source="built_in",
                editable=False,
                readOnly=True,
                path=f"{definition['name']}.toml",
                relativePath=f"{definition['name']}.toml",
                content=dump_toml(definition),
                definition=CodexSubagentDefinition(
                    name=definition["name"],
                    description=definition["description"],
                    developer_instructions=definition["developer_instructions"],
                ),
                metadata={"format": "toml"},
            )
            for definition in BUILT_IN_SUBAGENTS
        ]

    def _requirements_subagent_items(self) -> list[CodexSubagentItem]:
        items: list[CodexSubagentItem] = []
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            path = self._resolver.resolve(layer, CodexResource.MANAGED_REQUIREMENTS)
            config = _read_toml(path)
            agents = config.get("agents")
            if not isinstance(agents, dict):
                continue
            for name, value in agents.items():
                if not isinstance(name, str) or not isinstance(value, dict):
                    continue
                data = {"name": name, **value}
                definition = self._definition_from_subagent_data(data)
                items.append(
                    CodexSubagentItem(
                        id=f"{layer.value}:requirements:{name}",
                        name=definition.name,
                        source=layer.value,
                        editable=False,
                        readOnly=True,
                        scope=layer.value,
                        sourcePath=self._logical_locator(path),
                        content=dump_toml(data),
                        definition=definition,
                        metadata={"format": "toml"},
                    ),
                )
        return items

    def _subagent_registry_sources(self) -> list[CodexSubagentRegistrySource]:
        sources: list[CodexSubagentRegistrySource] = []
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            path = self._resolver.resolve(layer, CodexResource.CONFIG)
            agents = _as_table(_read_toml(path).get("agents"))
            settings = CodexSubagentRegistrySettings(
                max_threads=(
                    agents.get("max_threads")
                    if isinstance(agents.get("max_threads"), int)
                    else None
                ),
                max_depth=(
                    agents.get("max_depth")
                    if isinstance(agents.get("max_depth"), int)
                    else None
                ),
                job_max_runtime_seconds=(
                    agents.get("job_max_runtime_seconds")
                    if isinstance(agents.get("job_max_runtime_seconds"), int)
                    else None
                ),
            )
            if settings.model_dump(exclude_none=True):
                sources.append(
                    CodexSubagentRegistrySource(
                        scope=layer.value,
                        path=self._logical_locator(path),
                        settings=settings.model_dump(exclude_none=True),
                    )
                )
        return sources

    @staticmethod
    def _subagent_source_order(item: CodexSubagentItem) -> int:
        return {"project": 0, "user": 1, "built_in": 2, "plugin": 3}.get(item.source, 9)

    def _apply_subagent_precedence(self, items: list[CodexSubagentItem]) -> None:
        by_name: dict[str, list[CodexSubagentItem]] = {}
        for item in items:
            by_name.setdefault(item.name, []).append(item)
        for name_items in by_name.values():
            known = [
                item
                for item in name_items
                if item.source in {"project", "user", "built_in"}
            ]
            effective = min(known, key=self._subagent_source_order) if known else None
            for item in name_items:
                item.effective = item is effective
                item.overridden = (
                    item in known and effective is not None and item is not effective
                )

    def _parse_subagent_toml(
        self, content: str, path: Path | None = None
    ) -> dict[str, Any]:
        try:
            parsed = parse_toml(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_TOML",
                    "target": "content",
                    "message": str(exc),
                    "path": self._logical_locator(path) if path else None,
                },
            ) from exc
        return parsed

    def _definition_from_subagent_data(
        self, data: dict[str, Any]
    ) -> CodexSubagentDefinition:
        missing = [
            key
            for key in ("name", "description", "developer_instructions")
            if not isinstance(data.get(key), str) or not data.get(key, "").strip()
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
        definition_data = {
            key: data[key] for key in SUBAGENT_STRUCTURED_KEYS if key in data
        }
        return self._validated_subagent_definition(
            CodexSubagentDefinition(**definition_data)
        )

    def _validated_subagent_definition(
        self, definition: CodexSubagentDefinition
    ) -> CodexSubagentDefinition:
        missing = [
            key
            for key in ("name", "description", "developer_instructions")
            if not getattr(definition, key).strip()
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
        candidates = definition.nickname_candidates
        if candidates is not None:
            cleaned = [
                candidate.strip() for candidate in candidates if candidate.strip()
            ]
            if (
                not cleaned
                or len(cleaned) != len(candidates)
                or len(set(cleaned)) != len(cleaned)
            ):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_NICKNAME_CANDIDATES",
                        "target": "content",
                    },
                )
            definition.nickname_candidates = cleaned
        return definition

    @staticmethod
    def _subagent_data_from_definition(
        definition: CodexSubagentDefinition,
    ) -> dict[str, Any]:
        return definition.model_dump(exclude_none=True)

    @staticmethod
    def _subagent_filename(name: str) -> str:
        stem = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not stem:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "INVALID_SUBAGENT_NAME",
                    "target": "content",
                    "message": name,
                },
            )
        return f"{stem}.toml"

    def _configured_plugins(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for config in (self._user_config(), self._project_config()):
            merged.update(_as_table(config.get("plugins")))
        return merged

    def _configured_plugins_by_layer(self) -> dict[CodexLayer, dict[str, Any]]:
        return {
            CodexLayer.USER: _as_table(self._user_config().get("plugins")),
            CodexLayer.PROJECT: _as_table(self._project_config().get("plugins")),
        }

    def _plugin_scope_states(
        self,
        plugin_id: str,
        configured_by_layer: dict[CodexLayer, dict[str, Any]],
    ) -> list[CodexPluginScopeState]:
        states: list[CodexPluginScopeState] = []
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            layer_plugins = configured_by_layer.get(layer, {})
            config = _as_table(layer_plugins.get(plugin_id))
            has_enabled = "enabled" in config
            states.append(
                CodexPluginScopeState(
                    scope=layer.value,
                    configured=plugin_id in layer_plugins,
                    enabled=bool(config.get("enabled")) if has_enabled else None,
                )
            )
        return states

    def _effective_plugin_enabled(
        self,
        plugin_id: str,
        configured_by_layer: dict[CodexLayer, dict[str, Any]],
    ) -> bool:
        enabled = False
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            config = _as_table(configured_by_layer.get(layer, {}).get(plugin_id))
            if "enabled" in config:
                enabled = config.get("enabled") is True
        return enabled

    def _enabled_plugin_ids(self) -> set[str]:
        return {
            plugin_id
            for plugin_id, config in self._configured_plugins().items()
            if isinstance(plugin_id, str) and _as_table(config).get("enabled") is True
        }

    def _discovered_plugins(self) -> dict[str, dict[str, Any]]:
        discovered: dict[str, dict[str, Any]] = {}
        packages = self._plugin_resolver.packages()
        resource_counts_by_plugin = self._codex_plugin_resource_counts_by_plugin(
            packages
        )
        for package in packages:
            metadata = sanitize_plugin_definition(
                self._codex_plugin_metadata(
                    package.manifest,
                    package.plugin_id,
                    package.name,
                    package.marketplace_name,
                ),
                installed_root=package.package_root,
            )
            current = discovered.setdefault(package.plugin_id, {})
            current.update(
                {
                    "name": package.name,
                    **metadata,
                    "marketplace": package.marketplace_name,
                    "listed": True,
                    "installed": True,
                    "resourceCounts": resource_counts_by_plugin.get(
                        package.plugin_id, self._empty_codex_plugin_resource_counts()
                    ),
                },
            )
        return discovered

    @staticmethod
    def _validate_plugin_id(plugin_id: str) -> None:
        if not plugin_id or "\x00" in plugin_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_PLUGIN_ID", "message": plugin_id},
            )

    @staticmethod
    def _validate_plugin_resource_id(resource_id: str) -> None:
        if not resource_id or "\x00" in resource_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_PLUGIN_RESOURCE_ID", "message": resource_id},
            )

    @classmethod
    def _codex_plugin_metadata(
        cls,
        manifest: dict[str, Any],
        plugin_id: str,
        fallback_name: str,
        fallback_marketplace: str | None,
    ) -> dict[str, Any]:
        interface = _as_table(manifest.get("interface"))
        author = _as_table(manifest.get("author"))
        raw_capabilities = interface.get("capabilities") or manifest.get("capabilities")
        return {
            "displayName": cls._optional_str(interface.get("displayName"))
            or fallback_name
            or plugin_id.split("@", 1)[0],
            "shortDescription": cls._optional_str(
                interface.get("shortDescription") or manifest.get("description")
            ),
            "version": cls._optional_str(
                interface.get("version") or manifest.get("version")
            ),
            "authorName": cls._optional_str(
                author.get("name") or manifest.get("authorName")
            ),
            "category": cls._optional_str(
                interface.get("category") or manifest.get("category")
            ),
            "capabilities": cls._string_list(raw_capabilities),
            "brandColor": cls._optional_str(
                interface.get("brandColor") or manifest.get("brandColor")
            ),
            "homepage": cls._optional_str(
                interface.get("homepage")
                or manifest.get("homepage")
                or manifest.get("websiteURL")
            ),
            "marketplace": fallback_marketplace,
        }

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item]
        if isinstance(value, str) and value:
            return [value]
        return []

    @staticmethod
    def _resource_counts(data: dict[str, Any]) -> dict[str, int]:
        counts = _as_table(data.get("resourceCounts"))
        return {
            "skills": int(counts.get("skills") or 0),
            "mcpServers": int(counts.get("mcpServers") or 0),
            "apps": int(counts.get("apps") or 0),
            "hooks": int(counts.get("hooks") or 0),
        }

    @staticmethod
    def _empty_codex_plugin_resource_counts() -> dict[str, int]:
        return {"skills": 0, "mcpServers": 0, "apps": 0, "hooks": 0}

    def _codex_plugin_resource_counts_by_plugin(
        self, packages: list[Any]
    ) -> dict[str, dict[str, int]]:
        counts = {
            package.plugin_id: self._empty_codex_plugin_resource_counts()
            for package in packages
        }

        def plugin_counts(plugin_id: str) -> dict[str, int]:
            return counts.setdefault(
                plugin_id, self._empty_codex_plugin_resource_counts()
            )

        for skill in self._plugin_resolver.skills():
            plugin_counts(skill.plugin.plugin_id)["skills"] += 1
        for server in self._plugin_resolver.mcp_servers():
            plugin_counts(server.plugin.plugin_id)["mcpServers"] += 1
        for document in self._plugin_resolver.hook_documents():
            plugin_counts(document.plugin.plugin_id)["hooks"] += len(document.content)
        for app in self._plugin_resolver.apps():
            plugin_counts(app.plugin.plugin_id)["apps"] += 1
        return counts

    def _codex_plugin_skill_details(self, package: Any) -> list[CodexPluginSkillDetail]:
        details: list[CodexPluginSkillDetail] = []
        for skill in self._plugin_resolver.skills():
            if skill.plugin.plugin_id != package.plugin_id:
                continue
            content = read_text(skill.path)
            frontmatter = self._markdown_frontmatter(content)
            details.append(
                CodexPluginSkillDetail(
                    name=str(frontmatter.get("name") or skill.name),
                    description=self._optional_str(frontmatter.get("description")),
                    path=skill.relative_path,
                ),
            )
        return sorted(details, key=lambda item: item.path)

    def _codex_plugin_mcp_details(
        self,
        package: Any,
        *,
        policy_revision: str,
        generation: int,
    ) -> list[CodexPluginMcpServerDetail]:
        details: list[CodexPluginMcpServerDetail] = []
        for server in self._plugin_resolver.mcp_servers():
            if server.plugin.plugin_id != package.plugin_id:
                continue
            policy = self._plugin_controls.mcp_policy(
                package.plugin_id,
                server.name,
            )
            sanitized = sanitize_plugin_definition(
                server.config,
                installed_root=package.package_root,
            )
            details.append(
                CodexPluginMcpServerDetail(
                    name=server.name,
                    serverId=server.name,
                    command=self._optional_str(sanitized.get("command")),
                    url=self._optional_str(sanitized.get("url")),
                    config=sanitized,
                    policy=policy,
                    policyRevision=policy_revision,
                    effective=self._plugin_controls.mcp_effective(server, policy),
                    generation=generation,
                ),
            )
        return sorted(details, key=lambda item: item.name)

    def _codex_plugin_app_details(self, package: Any) -> list[CodexPluginAppDetail]:
        return [
            CodexPluginAppDetail(
                name=item.name,
                config=sanitize_plugin_definition(
                    item.config,
                    installed_root=package.package_root,
                ),
            )
            for item in self._plugin_resolver.apps()
            if item.plugin.plugin_id == package.plugin_id
        ]

    def _codex_app_resource(
        self,
        item: Any,
        *,
        generation: int,
    ) -> CodexAppResource:
        marketplace_id = item.plugin.marketplace_name
        return CodexAppResource(
            name=item.name,
            definition=sanitize_plugin_definition(
                item.config,
                installed_root=item.plugin.package_root,
            ),
            pluginId=item.plugin.plugin_id,
            pluginName=item.plugin.name,
            marketplaceId=marketplace_id,
            enabled=item.plugin.enabled,
            relativeSourcePath=item.relative_source_path,
            generation=generation,
            provenance=plugin_resource_provenance(
                target_client="codex",
                plugin_id=item.plugin.plugin_id,
                marketplace_id=marketplace_id,
            ),
        )

    @staticmethod
    def _provider_generation() -> int:
        return get_marketplace_target_client_gate().generation("codex")

    @staticmethod
    def _clear_process_cache(
        workspace_id: str,
        *,
        capability: str | None = None,
        scope: str | None = None,
    ) -> None:
        from app.modules.cli_settings.cache_api import clear_agent_settings_cache

        _clear_codex_collection_cache(
            workspace_id=workspace_id,
            capability=capability,
            scope=scope,
        )
        clear_agent_settings_cache(
            provider="codex",
            workspace_id=workspace_id,
            capability=capability,
            scope=scope,
        )

    @classmethod
    def _advance_and_clear_cache(
        cls,
        workspace_id: str,
        *,
        capability: str | None = None,
        scope: str | None = None,
    ) -> None:
        get_marketplace_target_client_gate().advance_generation("codex")
        cls._clear_process_cache(
            workspace_id,
            capability=capability,
            scope=scope,
        )

    def _collection_cache_key(
        self,
        workspace_id: str,
        capability: str,
        scope: str,
    ) -> tuple[str, str, str, str, str]:
        return (
            str(self._resolver.user_home),
            str(self._resolver.workspace_root),
            workspace_id,
            capability,
            scope,
        )

    def _codex_plugin_hook_details(
        self,
        package: Any,
        *,
        generation: int,
    ) -> list[CodexPluginHookDetail]:
        details: list[CodexPluginHookDetail] = []
        documents = [
            document
            for document in self._plugin_resolver.hook_documents()
            if document.plugin.plugin_id == package.plugin_id
        ]
        if not documents:
            return details
        summary = self._plugin_controls.plugin_hook_summary(package.plugin_id)
        for document in documents:
            for name, config in sorted(document.content.items()):
                sanitized = sanitize_plugin_definition(
                    (dict(config) if isinstance(config, dict) else {"value": config}),
                    installed_root=package.package_root,
                )
                details.append(
                    CodexPluginHookDetail(
                        name=str(name),
                        path=str(
                            document.source_path.relative_to(package.package_root)
                        ),
                        config=sanitized,
                        trustState=summary.trust_state,
                        trusted=summary.trusted,
                        effective=summary.effective,
                        trustRevision=summary.revision,
                        generation=generation,
                    ),
                )
        return details

    @staticmethod
    def _markdown_frontmatter(content: str) -> dict[str, Any]:
        if not content.startswith("---\n"):
            return {}
        end = content.find("\n---", 4)
        if end == -1:
            return {}
        result: dict[str, Any] = {}
        for line in content[4:end].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            clean_value = value.strip().strip('"').strip("'")
            result[key.strip()] = clean_value
        return result

    def _plugin_skill_summaries(self) -> list[CodexFileSummary]:
        summaries: list[CodexFileSummary] = []
        for skill in self._plugin_resolver.skills():
            summaries.append(
                CodexFileSummary(
                    name=skill.name,
                    path=skill.relative_path,
                    sizeBytes=skill.path.stat().st_size,
                    source="plugin",
                    scope="plugin",
                    readOnly=True,
                    metadata={
                        "pluginId": skill.plugin.plugin_id,
                        "pluginName": skill.plugin.name,
                        "marketplaceName": skill.plugin.marketplace_name,
                        "enabled": skill.plugin.enabled,
                        "sourcePath": (
                            skill.relative_source_path or skill.relative_path
                        ),
                    },
                ),
            )
        return summaries

    def _resource_config(self, resource: str) -> dict[str, Any]:
        user_config = self._user_config()
        project_config = self._project_config()
        if resource == "skills":
            return {
                "skills": _as_table(user_config.get("skills"))
                | _as_table(project_config.get("skills"))
            }
        return {}

    @staticmethod
    def _file_metadata(
        resource: str, relative_path: Path, size_bytes: int
    ) -> dict[str, Any]:
        suffix = relative_path.suffix.lower()
        if resource == "skills":
            return {
                "format": "markdown" if suffix == ".md" else "text",
                "sizeBytes": size_bytes,
            }
        if resource == "prompts":
            return {
                "format": "markdown" if suffix in {"", ".md"} else suffix.lstrip("."),
                "fileName": str(relative_path),
                "sizeBytes": size_bytes,
            }
        return {"sizeBytes": size_bytes}

    @staticmethod
    def _validate_managed_file(resource: str, relative_path: str, content: str) -> None:
        clean_path = Path(relative_path)
        if resource == "prompts":
            if clean_path.suffix and clean_path.suffix.lower() != ".md":
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_FILE_EXTENSION",
                        "message": relative_path,
                    },
                )
            if not content.strip():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"error": "EMPTY_CONTENT", "message": resource},
                )

    def _structured_hooks(
        self, layer: CodexLayer | str, content: str, path: Path
    ) -> list[CodexHookEntry]:
        parsed = _parse_json_document(content)
        if not isinstance(parsed, dict):
            return []
        codex_layer = CodexLayer(layer)
        return self._hook_entries_from_event_map(
            parsed,
            source="hooks_json",
            read_only=False,
            layer=codex_layer.value,
            source_path=self._logical_locator(path),
        )

    @staticmethod
    def _validate_hooks_document(content: str) -> None:
        parsed = _parse_json_document(content)
        if not isinstance(parsed, dict):
            _raise_invalid_hooks(
                "INVALID_HOOKS_DOCUMENT", "hooks.json must contain an object"
            )
        hook_map = CodexAgentSettings._normalize_hooks_root(parsed)
        if not hook_map and parsed:
            _raise_invalid_hooks(
                "INVALID_HOOKS_DOCUMENT", "hooks.json must contain hook events"
            )
        for event, event_hooks in hook_map.items():
            for hook_entry in event_hooks:
                actions = hook_entry.get("hooks")
                if not isinstance(actions, list) or len(actions) == 0:
                    _raise_invalid_hooks("INVALID_HOOK_ACTIONS", event)
                for action in actions:
                    if not isinstance(action, dict):
                        _raise_invalid_hooks("INVALID_HOOK_ACTION", event)
                    hook_type = action.get("type", "command")
                    if hook_type not in {"command", "prompt", "agent"}:
                        _raise_invalid_hooks("INVALID_HOOK_TYPE", event)
                    command = action.get("command")
                    if hook_type == "command" and (
                        not isinstance(command, str) or not command.strip()
                    ):
                        _raise_invalid_hooks("MISSING_HOOK_COMMAND", event)
                    status_message = action.get("statusMessage")
                    if status_message is not None and not isinstance(
                        status_message, str
                    ):
                        _raise_invalid_hooks("INVALID_HOOK_STATUS_MESSAGE", event)
                    timeout = action.get("timeout")
                    if timeout is not None and not isinstance(timeout, int):
                        _raise_invalid_hooks("INVALID_HOOK_TIMEOUT", event)
                    additional_context_limit = action.get("additionalContextLimit")
                    if additional_context_limit is not None and (
                        isinstance(additional_context_limit, bool)
                        or not isinstance(additional_context_limit, int)
                        or additional_context_limit < 0
                    ):
                        _raise_invalid_hooks(
                            "INVALID_HOOK_ADDITIONAL_CONTEXT_LIMIT", event
                        )
                    async_value = action.get("async")
                    if async_value is not None and not isinstance(async_value, bool):
                        _raise_invalid_hooks("INVALID_HOOK_ASYNC", event)
                    command_windows = action.get(
                        "commandWindows", action.get("command_windows")
                    )
                    if command_windows is not None and not isinstance(
                        command_windows, str
                    ):
                        _raise_invalid_hooks("INVALID_HOOK_COMMAND_WINDOWS", event)

    def _codex_hooks_enabled(self, layer: CodexLayer | str | None = None) -> bool:
        if layer is not None:
            config = (
                self._project_config()
                if CodexLayer(layer) is CodexLayer.PROJECT
                else self._user_config()
            )
            features = _as_table(config.get("features"))
            return features.get("hooks") is True

        # Project configuration overrides the user configuration when it
        # explicitly sets the canonical feature flag.
        for config in (self._project_config(), self._user_config()):
            features = _as_table(config.get("features"))
            if "hooks" in features:
                return features.get("hooks") is True
        return False

    def _inline_hooks(self) -> list[dict[str, Any]]:
        hooks: list[dict[str, Any]] = []
        for layer, config in (
            ("project", self._project_config()),
            ("user", self._user_config()),
        ):
            value = config.get("hooks")
            if isinstance(value, list):
                hooks.extend(
                    {"layer": layer, "event": item.get("event"), "hook": item}
                    for item in value
                    if isinstance(item, dict)
                )
            elif isinstance(value, dict):
                for event, event_hooks in value.items():
                    if isinstance(event_hooks, list):
                        hooks.extend(
                            {"layer": layer, "event": event, "hook": item}
                            for item in event_hooks
                            if isinstance(item, dict)
                        )
                    elif isinstance(event_hooks, dict):
                        hooks.append(
                            {"layer": layer, "event": event, "hook": event_hooks}
                        )
        return hooks

    def _inline_hook_entries(
        self, inline_hooks: list[dict[str, Any]]
    ) -> list[CodexHookEntry]:
        entries: list[CodexHookEntry] = []
        for index, hook in enumerate(inline_hooks):
            event = hook.get("event")
            config = hook.get("hook")
            layer = (
                hook.get("layer") if hook.get("layer") in {"project", "user"} else None
            )
            if not isinstance(event, str) or not isinstance(config, dict):
                continue
            entries.extend(
                self._hook_entries_from_event_map(
                    {event: [config]},
                    source="inline_config",
                    read_only=False,
                    layer=layer,
                    source_path=(
                        self._logical_locator(
                            self._resolver.resolve(str(layer), CodexResource.CONFIG)
                        )
                        if layer
                        else None
                    ),
                    id_prefix=f"inline:{layer or 'unknown'}:{index}",
                ),
            )
        return entries

    def _plugin_hook_entries(self, generation: int) -> list[CodexHookEntry]:
        entries: list[CodexHookEntry] = []
        summaries: dict[str, Any] = {}
        for document in self._plugin_resolver.hook_documents():
            summary = summaries.get(document.plugin.plugin_id)
            if summary is None:
                summary = self._plugin_controls.plugin_hook_summary(
                    document.plugin.plugin_id
                )
                summaries[document.plugin.plugin_id] = summary
            hook_map = self._normalize_hooks_root(
                sanitize_plugin_definition(
                    document.content,
                    installed_root=document.plugin.package_root,
                )
            )
            if not hook_map:
                continue
            entries.extend(
                self._hook_entries_from_event_map(
                    hook_map,
                    source="plugin",
                    read_only=True,
                    source_path=document.relative_source_path,
                    plugin_id=document.plugin.plugin_id,
                    plugin_name=document.plugin.name,
                    marketplace_name=document.plugin.marketplace_name,
                    trust_state=summary.trust_state,
                    trusted=summary.trusted,
                    effective=summary.effective,
                    trust_revision=summary.revision,
                    generation=generation,
                    id_prefix=f"plugin:{document.plugin.plugin_id}",
                ),
            )
        return entries

    def _hook_entries_from_event_map(
        self,
        value: Any,
        *,
        source: str,
        read_only: bool,
        layer: str | None = None,
        source_path: str | None = None,
        plugin_id: str | None = None,
        plugin_name: str | None = None,
        marketplace_name: str | None = None,
        trust_state: str | None = None,
        trusted: bool | None = None,
        effective: bool | None = None,
        trust_revision: str | None = None,
        generation: int | None = None,
        id_prefix: str | None = None,
    ) -> list[CodexHookEntry]:
        hook_map = self._normalize_hooks_root(value)
        entries: list[CodexHookEntry] = []
        for event, event_hooks in hook_map.items():
            for index, hook_entry in enumerate(event_hooks):
                raw_actions = (
                    hook_entry.get("hooks") if "hooks" in hook_entry else [hook_entry]
                )
                actions = self._hook_actions(raw_actions)
                first_action: CodexHookCommandAction | dict[str, Any] = (
                    actions[0] if actions else {}
                )
                entry_id = ":".join(
                    part
                    for part in [
                        id_prefix,
                        str(layer) if not id_prefix else None,
                        event,
                        str(index),
                    ]
                    if part
                )
                entries.append(
                    CodexHookEntry(
                        id=entry_id,
                        event=event,
                        index=index,
                        matcher=(
                            hook_entry.get("matcher")
                            if isinstance(hook_entry.get("matcher"), str)
                            else None
                        ),
                        actions=actions,
                        action=first_action,
                        source=source,  # type: ignore[arg-type]
                        layer=layer,  # type: ignore[arg-type]
                        hookScope=(
                            source if source in {"plugin", "session"} else layer
                        ),  # type: ignore[arg-type]
                        readOnly=read_only,
                        editable=not read_only,
                        sourcePath=source_path,
                        pluginId=plugin_id,
                        pluginName=plugin_name,
                        marketplaceName=marketplace_name,
                        trustState=trust_state,  # type: ignore[arg-type]
                        trusted=trusted,
                        effective=effective,
                        trustRevision=trust_revision,
                        generation=generation,
                        raw=dict(hook_entry),
                    ),
                )
        return entries

    @staticmethod
    def _same_hook_entry(left: CodexHookEntry, right: CodexHookEntry) -> bool:
        if left.id and right.id:
            return left.id == right.id
        return (
            left.event == right.event
            and left.matcher == right.matcher
            and left.layer == right.layer
        )

    @staticmethod
    def _event_map_from_entries(
        entries: list[CodexHookEntry],
    ) -> dict[str, list[dict[str, Any]]]:
        event_map: dict[str, list[dict[str, Any]]] = {}
        for entry in entries:
            actions: list[dict[str, Any]] = []
            for action in entry.actions:
                if isinstance(action, dict):
                    actions.append(dict(action))
                    continue
                if action.raw:
                    actions.append(dict(action.raw))
                    continue
                rebuilt: dict[str, Any] = {
                    "type": action.type,
                    "command": action.command,
                }
                if action.timeout is not None:
                    rebuilt["timeout"] = action.timeout
                if action.statusMessage is not None:
                    rebuilt["statusMessage"] = action.statusMessage
                if action.async_ is not None:
                    rebuilt["async"] = action.async_
                if action.commandWindows is not None:
                    rebuilt["commandWindows"] = action.commandWindows
                if action.additionalContextLimit is not None:
                    rebuilt["additionalContextLimit"] = action.additionalContextLimit
                actions.append(rebuilt)

            raw_entry = dict(entry.raw) if entry.raw else {}
            raw_entry["hooks"] = actions
            if entry.matcher is None:
                raw_entry.pop("matcher", None)
            else:
                raw_entry["matcher"] = entry.matcher
            event_map.setdefault(entry.event, []).append(raw_entry)
        return event_map

    @staticmethod
    def _normalize_hooks_root(value: Any) -> dict[str, list[dict[str, Any]]]:
        root = _as_table(value)
        if "hooks" in root and isinstance(root.get("hooks"), dict):
            root = _as_table(root.get("hooks"))
        normalized: dict[str, list[dict[str, Any]]] = {}
        for event, event_hooks in root.items():
            if isinstance(event_hooks, list):
                normalized[event] = [
                    item for item in event_hooks if isinstance(item, dict)
                ]
            elif isinstance(event_hooks, dict):
                normalized[event] = [event_hooks]
        return normalized

    @staticmethod
    def _hook_actions(value: Any) -> list[CodexHookCommandAction | dict[str, Any]]:
        if not isinstance(value, list):
            return []
        actions: list[CodexHookCommandAction | dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("type", "command") != "command":
                actions.append(dict(item))
                continue
            status_message = item.get("statusMessage")
            command = item.get("command")
            actions.append(
                CodexHookCommandAction(
                    type="command",
                    command=command if isinstance(command, str) else "",
                    timeout=(
                        item.get("timeout")
                        if isinstance(item.get("timeout"), int)
                        else None
                    ),
                    statusMessage=(
                        status_message if isinstance(status_message, str) else None
                    ),
                    async_=(
                        item.get("async")
                        if isinstance(item.get("async"), bool)
                        else None
                    ),
                    commandWindows=(
                        item.get("commandWindows", item.get("command_windows"))
                        if isinstance(
                            item.get("commandWindows", item.get("command_windows")),
                            str,
                        )
                        else None
                    ),
                    additionalContextLimit=(
                        item.get("additionalContextLimit")
                        if isinstance(item.get("additionalContextLimit"), int)
                        else None
                    ),
                    raw=dict(item),
                ),
            )
        return actions

    def _project_config(self) -> dict[str, Any]:
        return _read_toml(
            self._resolver.resolve(CodexLayer.PROJECT, CodexResource.CONFIG)
        )

    def _user_config(self) -> dict[str, Any]:
        return _read_toml(self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG))


def get_codex_agent_settings() -> CodexAgentSettings:
    """Return the Codex agent settings interface."""

    return CodexAgentSettings()
