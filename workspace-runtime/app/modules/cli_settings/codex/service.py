"""Codex settings service."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Any

from fastapi import HTTPException, status

from app.modules.cli_settings.codex_paths import CodexLayer, CodexPathResolver, CodexResource, get_codex_path_resolver
from app.modules.cli_settings.toml_utils import dump_toml, merge_known_values, parse_toml

from .models import (
    CodexAgentsMdCaveat,
    CodexAgentsMdDocument,
    CodexAgentsMdUpdateRequest,
    CodexAgentsMdUpdateResponse,
    CodexConfigDocument,
    CodexConfigSectionResponse,
    CodexConfigSectionUpdateResponse,
    CodexConfigUpdateResponse,
    CodexFeatureEnableResponse,
    CodexHookCommandAction,
    CodexHookEntry,
    CodexHookEventMetadata,
    CodexHooksDocumentResponse,
    CodexManagedRequirementsResponse,
    CodexManagedRequirementsSource,
    CodexOverviewManagedRequirementsState,
    CodexOverviewMemoryState,
    CodexOverviewPluginState,
    CodexOverviewResponse,
    CodexOverviewTrustState,
    CodexFileListResponse,
    CodexFileSummary,
    CodexPluginSummary,
    CodexPluginToggleResponse,
    CodexPluginsResponse,
    CodexRulesFileSummary,
    CodexRulesListResponse,
    CodexRulesValidationResponse,
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

DEFAULT_PROJECT_DOC_MAX_BYTES = 32 * 1024

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
        scope="session_start",
        matcherSupported=True,
        matcherTarget="source",
        matcherExamples=["startup", "resume", "clear"],
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
]


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return parse_toml(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_TOML", "message": str(exc), "path": str(path)},
        ) from exc


def _write_toml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(data), encoding="utf-8")


def _as_table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _parse_json_document(content: str) -> Any:
    try:
        return json.loads(content or "{}")
    except Exception as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_JSON", "message": str(exc)},
        ) from exc


def _raise_invalid_hooks(error: str, message: str) -> None:
    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail={"error": error, "message": message},
    )


class CodexSettingsService:
    """Service for Codex settings endpoints."""

    def __init__(self, resolver: CodexPathResolver | None = None) -> None:
        self._resolver = resolver or get_codex_path_resolver()

    def get_overview(self, workspace_id: str) -> CodexOverviewResponse:
        user_config_path = self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG)
        user_config = _read_toml(user_config_path)
        profile_name = user_config.get("profile") if isinstance(user_config.get("profile"), str) else None
        active_profile = _as_table(_as_table(user_config.get("profiles")).get(profile_name)) if profile_name else {}
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
        requirements = self.get_managed_requirements(workspace_id)

        return CodexOverviewResponse(
            workspaceId=workspace_id,
            setupReady=self._resolver.codex_home.exists(),
            codexHome=str(self._resolver.codex_home),
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
                use=memory_config.get("use") if isinstance(memory_config.get("use"), bool) else None,
                generate=memory_config.get("generate") if isinstance(memory_config.get("generate"), bool) else None,
            ),
        )

    def update_trust(self, workspace_id: str, trusted: bool) -> CodexTrustUpdateResponse:
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

    def get_agents_md(self, workspace_id: str, scope: CodexLayer | str) -> CodexAgentsMdDocument:
        layer = CodexLayer(scope)
        path = self._resolver.resolve(layer, CodexResource.AGENTS_MD)
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        max_bytes = self._project_doc_max_bytes()
        caveats = self._build_agents_md_caveats(layer, path, content, max_bytes)
        active_path = path
        override_path = path.with_name("AGENTS.override.md")
        if layer == CodexLayer.PROJECT and override_path.is_file():
            active_path = override_path
        elif layer == CodexLayer.PROJECT and not path.is_file():
            active_path = self._first_existing_fallback()

        return CodexAgentsMdDocument(
            workspaceId=workspace_id,
            scope=layer.value,
            content=content,
            path=str(path),
            exists=path.is_file(),
            activePath=str(active_path) if active_path is not None else None,
            maxBytes=max_bytes,
            sizeBytes=len(content.encode("utf-8")),
            caveats=caveats,
        )

    def update_agents_md(
        self,
        workspace_id: str,
        request: CodexAgentsMdUpdateRequest,
    ) -> CodexAgentsMdUpdateResponse:
        layer = CodexLayer(request.scope)
        path = self._resolver.resolve(layer, CodexResource.AGENTS_MD)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(request.content, encoding="utf-8")
        return CodexAgentsMdUpdateResponse(
            workspaceId=workspace_id,
            scope=layer.value,
            path=str(path),
        )

    def get_managed_requirements(self, workspace_id: str) -> CodexManagedRequirementsResponse:
        sources: list[CodexManagedRequirementsSource] = []
        for layer in (CodexLayer.USER, CodexLayer.PROJECT):
            path = self._resolver.resolve(layer, CodexResource.MANAGED_REQUIREMENTS)
            if path.is_file():
                content = path.read_text(encoding="utf-8")
                sources.append(
                    CodexManagedRequirementsSource(
                        layer=layer.value,
                        path=str(path),
                        content=content,
                        sizeBytes=len(content.encode("utf-8")),
                    ),
                )
        return CodexManagedRequirementsResponse(workspaceId=workspace_id, sources=sources)

    def get_config_document(self, workspace_id: str, layer: CodexLayer | str) -> CodexConfigDocument:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        return CodexConfigDocument(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            path=str(path),
            content=content,
            exists=path.is_file(),
        )

    def update_config_document(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
    ) -> CodexConfigUpdateResponse:
        try:
            parse_toml(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_TOML", "message": str(exc)},
            ) from exc
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return CodexConfigUpdateResponse(workspaceId=workspace_id, layer=codex_layer.value, path=str(path))

    def get_config_section(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
    ) -> CodexConfigSectionResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        data = self._section_data(config, section)
        return CodexConfigSectionResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            section=section,
            path=str(path),
            data=data,
        )

    def update_config_section(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        section: str,
        data: dict[str, Any],
    ) -> CodexConfigSectionUpdateResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        if section == "structured":
            updates = {key: value for key, value in data.items() if key in ROOT_STRUCTURED_KEYS}
            next_config = merge_known_values(config, updates)
            next_data = {key: next_config[key] for key in ROOT_STRUCTURED_KEYS if key in next_config}
        else:
            section_key = self._section_key(section)
            next_config = merge_known_values(config, {section_key: data})
            next_data = _as_table(next_config.get(section_key))
        _write_toml(path, next_config)
        return CodexConfigSectionUpdateResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            section=section,
            path=str(path),
            data=next_data,
        )

    def list_rules(self, workspace_id: str, layer: CodexLayer | str) -> CodexRulesListResponse:
        codex_layer = CodexLayer(layer)
        directory = self._resolver.resolve(codex_layer, CodexResource.RULES)
        files = [
            CodexRulesFileSummary(
                name=path.name,
                path=path.name,
                sizeBytes=path.stat().st_size,
            )
            for path in sorted(directory.glob("*.rules")) if path.is_file()
        ] if directory.is_dir() else []
        return CodexRulesListResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            directory=str(directory),
            files=files,
        )

    def get_rules_file(self, workspace_id: str, layer: CodexLayer | str, relative_path: str) -> CodexTextFileResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        return CodexTextFileResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            path=str(path),
            content=content,
            exists=path.is_file(),
        )

    def update_rules_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
        content: str,
    ) -> CodexTextFileResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self.get_rules_file(workspace_id, codex_layer, relative_path)

    def delete_rules_file(self, workspace_id: str, layer: CodexLayer | str, relative_path: str) -> dict[str, str]:
        codex_layer = CodexLayer(layer)
        path = self._resolve_rules_file(codex_layer, relative_path)
        if path.exists():
            path.unlink()
        return {"workspaceId": workspace_id, "layer": codex_layer.value, "path": str(path)}

    def validate_rules_file(
        self,
        layer: CodexLayer | str,
        relative_path: str,
        command: list[str],
    ) -> CodexRulesValidationResponse:
        if not command:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "EMPTY_COMMAND", "message": "Command must not be empty"},
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
            return CodexRulesValidationResponse(
                valid=False,
                exitCode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "codex execpolicy check timed out",
            )
        return CodexRulesValidationResponse(
            valid=result.returncode == 0,
            exitCode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    def get_hooks_document(self, workspace_id: str, layer: CodexLayer | str) -> CodexHooksDocumentResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        content = path.read_text(encoding="utf-8") if path.is_file() else ""
        inline_hooks = self._inline_hooks()
        return CodexHooksDocumentResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            path=str(path),
            content=content,
            exists=path.is_file(),
            featureEnabled=self._codex_hooks_enabled(),
            inlineHooks=inline_hooks,
            entries=[
                *self._structured_hooks(codex_layer, content, path),
                *self._inline_hook_entries(inline_hooks),
                *self._plugin_hook_entries(),
                *self._managed_hook_entries(),
            ],
            eventMetadata=HOOK_EVENT_METADATA,
        )

    def update_hooks_document(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        content: str,
    ) -> CodexHooksDocumentResponse:
        self._validate_hooks_document(content)
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.HOOKS)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self.get_hooks_document(workspace_id, codex_layer)

    def enable_codex_hooks(self, workspace_id: str, layer: CodexLayer | str) -> CodexFeatureEnableResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        features = _as_table(config.get("features"))
        features["codex_hooks"] = True
        config["features"] = features
        _write_toml(path, config)
        return CodexFeatureEnableResponse(workspaceId=workspace_id, featureEnabled=True)

    def list_plugins(self, workspace_id: str) -> CodexPluginsResponse:
        configured = self._configured_plugins()
        discovered = self._discovered_plugins()
        all_ids = sorted(set(configured) | set(discovered))
        plugins = [
            CodexPluginSummary(
                id=plugin_id,
                name=str(discovered.get(plugin_id, {}).get("name") or plugin_id.split("@", 1)[0]),
                marketplace=str(discovered.get(plugin_id, {}).get("marketplace") or plugin_id.split("@", 1)[1])
                if "@" in plugin_id
                else None,
                listed=bool(discovered.get(plugin_id, {}).get("listed")),
                installed=bool(discovered.get(plugin_id, {}).get("installed")),
                enabled=bool(_as_table(configured.get(plugin_id)).get("enabled")),
                path=discovered.get(plugin_id, {}).get("path"),
                sourcePath=discovered.get(plugin_id, {}).get("sourcePath"),
                bundled=_as_table(discovered.get(plugin_id, {}).get("bundled")),
            )
            for plugin_id in all_ids
        ]
        return CodexPluginsResponse(workspaceId=workspace_id, plugins=plugins)

    def set_plugin_enabled(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        plugin_id: str,
        enabled: bool,
    ) -> CodexPluginToggleResponse:
        if not plugin_id or "/" in plugin_id or ".." in plugin_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_PLUGIN_ID", "message": plugin_id},
            )
        codex_layer = CodexLayer(layer)
        path = self._resolver.resolve(codex_layer, CodexResource.CONFIG)
        config = _read_toml(path)
        plugins = _as_table(config.get("plugins"))
        plugin_config = _as_table(plugins.get(plugin_id))
        plugin_config["enabled"] = enabled
        plugins[plugin_id] = plugin_config
        config["plugins"] = plugins
        _write_toml(path, config)
        return CodexPluginToggleResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            pluginId=plugin_id,
            enabled=enabled,
        )

    def list_subagents(self, workspace_id: str) -> CodexSubagentsResponse:
        items = [
            *self._editable_subagent_items(CodexLayer.USER),
            *self._editable_subagent_items(CodexLayer.PROJECT),
            *self._built_in_subagent_items(),
            *self._plugin_subagent_items(),
            *self._managed_subagent_items(),
        ]
        self._apply_subagent_precedence(items)
        items.sort(key=lambda item: (item.name, self._subagent_source_order(item), item.relativePath or item.path or ""))
        return CodexSubagentsResponse(
            workspaceId=workspace_id,
            items=items,
            registry=self._subagent_registry_sources(),
        )

    def save_subagent(self, workspace_id: str, request: CodexSubagentSaveRequest) -> CodexSubagentItem:
        layer = CodexLayer(request.layer)
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
                detail={"error": "MISSING_SUBAGENT_CONTENT", "message": "content or definition is required"},
            )

        target_relative_path = self._subagent_filename(definition.name)
        previous_path = self._resolve_subagent_file(layer, request.path) if request.path else None
        target_path = self._resolve_subagent_file(layer, target_relative_path)
        if target_path.exists() and previous_path != target_path and not request.overwrite:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"error": "SUBAGENT_CONFLICT", "message": target_relative_path},
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content if content.endswith("\n") else f"{content}\n", encoding="utf-8")
        if previous_path is not None and previous_path != target_path and previous_path.exists():
            previous_path.unlink()
        return self._subagent_item_from_file(layer, target_path)

    def delete_subagent(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        relative_path: str,
    ) -> CodexSubagentDeleteResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_subagent_file(codex_layer, relative_path)
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        return CodexSubagentDeleteResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            path=relative_path,
            deleted=deleted,
        )

    def list_files(self, workspace_id: str, layer: CodexLayer | str, resource: str) -> CodexFileListResponse:
        codex_layer = CodexLayer(layer)
        directory = self._file_resource_path(codex_layer, resource)
        files = [
            CodexFileSummary(
                name=path.name,
                path=str(path.relative_to(directory)),
                sizeBytes=path.stat().st_size,
                source=codex_layer.value,
                metadata=self._file_metadata(resource, path.relative_to(directory), path.stat().st_size),
            )
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ] if directory.is_dir() else []
        if resource == "skills":
            files.extend(self._plugin_skill_summaries())
        return CodexFileListResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            resource=resource,
            directory=str(directory),
            files=files,
            config=self._resource_config(resource),
        )

    def get_file(self, workspace_id: str, layer: CodexLayer | str, resource: str, relative_path: str) -> CodexTextFileResponse:
        codex_layer = CodexLayer(layer)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        return CodexTextFileResponse(
            workspaceId=workspace_id,
            layer=codex_layer.value,
            path=str(path),
            content=path.read_text(encoding="utf-8") if path.is_file() else "",
            exists=path.is_file(),
        )

    def update_file(
        self,
        workspace_id: str,
        layer: CodexLayer | str,
        resource: str,
        relative_path: str,
        content: str,
    ) -> CodexTextFileResponse:
        codex_layer = CodexLayer(layer)
        self._validate_managed_file(resource, relative_path, content)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return self.get_file(workspace_id, codex_layer, resource, relative_path)

    def delete_file(self, workspace_id: str, layer: CodexLayer | str, resource: str, relative_path: str) -> dict[str, str]:
        codex_layer = CodexLayer(layer)
        path = self._resolve_managed_file(codex_layer, resource, relative_path)
        if path.exists():
            path.unlink()
        return {"workspaceId": workspace_id, "layer": codex_layer.value, "resource": resource, "path": str(path)}

    def _build_trust_state(self, user_config: dict[str, Any], user_config_path: Path) -> CodexOverviewTrustState:
        workspace_path = str(self._resolver.workspace_root)
        project_config = _as_table(_as_table(user_config.get("projects")).get(workspace_path))
        trust_level = project_config.get("trust_level")
        return CodexOverviewTrustState(
            workspacePath=workspace_path,
            trustLevel=trust_level if isinstance(trust_level, str) else None,
            trusted=trust_level == "trusted",
            sourcePath=str(user_config_path),
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
        if clean_path.is_absolute() or ".." in clean_path.parts or clean_path.suffix != ".rules":
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

    def _resolve_managed_file(self, layer: CodexLayer, resource: str, relative_path: str) -> Path:
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_FILE_PATH", "message": relative_path},
            )
        return self._file_resource_path(layer, resource) / clean_path

    def _resolve_subagent_file(self, layer: CodexLayer, relative_path: str) -> Path:
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts or clean_path.suffix.lower() != ".toml":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_SUBAGENT_PATH", "message": relative_path},
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

    def _subagent_item_from_file(self, layer: CodexLayer, path: Path) -> CodexSubagentItem:
        directory = self._resolver.resolve(layer, CodexResource.SUBAGENTS)
        relative_path = str(path.relative_to(directory))
        content = path.read_text(encoding="utf-8")
        data = self._parse_subagent_toml(content, path)
        definition = self._definition_from_subagent_data(data)
        return CodexSubagentItem(
            id=f"{layer.value}:{relative_path}",
            name=definition.name,
            source=layer.value,  # type: ignore[arg-type]
            editable=True,
            readOnly=False,
            layer=layer.value,
            path=str(path),
            relativePath=relative_path,
            sourcePath=str(path),
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
                definition=CodexSubagentDefinition(**definition),
                metadata={"format": "toml"},
            )
            for definition in BUILT_IN_SUBAGENTS
        ]

    def _plugin_subagent_items(self) -> list[CodexSubagentItem]:
        items: list[CodexSubagentItem] = []
        for manifest_path in self._plugin_manifest_paths():
            manifest = self._read_json_file(manifest_path)
            plugin_id = self._plugin_id_from_manifest(manifest, manifest_path)
            package_root = manifest_path.parent.parent
            agents_dir = package_root / "agents"
            if not agents_dir.is_dir():
                continue
            for path in sorted(agents_dir.glob("*.toml")):
                content = path.read_text(encoding="utf-8")
                data = self._parse_subagent_toml(content, path)
                definition = self._definition_from_subagent_data(data)
                items.append(
                    CodexSubagentItem(
                        id=f"plugin:{plugin_id}:{path.name}",
                        name=definition.name,
                        source="plugin",
                        editable=False,
                        readOnly=True,
                        path=str(path),
                        relativePath=path.name,
                        sourcePath=str(path),
                        content=content,
                        definition=definition,
                        pluginId=plugin_id,
                        pluginName=str(manifest.get("name") or manifest.get("id") or plugin_id),
                        marketplaceName=self._marketplace_from_plugin_id(plugin_id),
                        metadata={"format": "toml"},
                    ),
                )
        return items

    def _managed_subagent_items(self) -> list[CodexSubagentItem]:
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
                        id=f"managed:{layer.value}:{name}",
                        name=definition.name,
                        source="managed",
                        editable=False,
                        readOnly=True,
                        layer=layer.value,
                        sourcePath=str(path),
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
                max_threads=agents.get("max_threads") if isinstance(agents.get("max_threads"), int) else None,
                max_depth=agents.get("max_depth") if isinstance(agents.get("max_depth"), int) else None,
                job_max_runtime_seconds=agents.get("job_max_runtime_seconds")
                if isinstance(agents.get("job_max_runtime_seconds"), int)
                else None,
            )
            if settings.model_dump(exclude_none=True):
                sources.append(CodexSubagentRegistrySource(layer=layer.value, path=str(path), settings=settings))
        return sources

    @staticmethod
    def _subagent_source_order(item: CodexSubagentItem) -> int:
        return {"project": 0, "user": 1, "built_in": 2, "plugin": 3, "managed": 4}.get(item.source, 9)

    def _apply_subagent_precedence(self, items: list[CodexSubagentItem]) -> None:
        by_name: dict[str, list[CodexSubagentItem]] = {}
        for item in items:
            by_name.setdefault(item.name, []).append(item)
        for name_items in by_name.values():
            known = [item for item in name_items if item.source in {"project", "user", "built_in"}]
            effective = min(known, key=self._subagent_source_order) if known else None
            for item in name_items:
                item.effective = item is effective
                item.overridden = item in known and effective is not None and item is not effective

    def _parse_subagent_toml(self, content: str, path: Path | None = None) -> dict[str, Any]:
        try:
            parsed = parse_toml(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_TOML", "message": str(exc), "path": str(path) if path else None},
            ) from exc
        return parsed

    def _definition_from_subagent_data(self, data: dict[str, Any]) -> CodexSubagentDefinition:
        missing = [
            key
            for key in ("name", "description", "developer_instructions")
            if not isinstance(data.get(key), str) or not data.get(key, "").strip()
        ]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "MISSING_SUBAGENT_FIELD", "fields": missing},
            )
        definition_data = {key: data[key] for key in SUBAGENT_STRUCTURED_KEYS if key in data}
        return self._validated_subagent_definition(CodexSubagentDefinition(**definition_data))

    def _validated_subagent_definition(self, definition: CodexSubagentDefinition) -> CodexSubagentDefinition:
        missing = [
            key
            for key in ("name", "description", "developer_instructions")
            if not getattr(definition, key).strip()
        ]
        if missing:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "MISSING_SUBAGENT_FIELD", "fields": missing},
            )
        candidates = definition.nickname_candidates
        if candidates is not None:
            cleaned = [candidate.strip() for candidate in candidates if candidate.strip()]
            if not cleaned or len(cleaned) != len(candidates) or len(set(cleaned)) != len(cleaned):
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"error": "INVALID_NICKNAME_CANDIDATES"},
                )
            definition.nickname_candidates = cleaned
        return definition

    @staticmethod
    def _subagent_data_from_definition(definition: CodexSubagentDefinition) -> dict[str, Any]:
        return definition.model_dump(exclude_none=True)

    @staticmethod
    def _subagent_filename(name: str) -> str:
        stem = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
        if not stem:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_SUBAGENT_NAME", "message": name},
            )
        return f"{stem}.toml"

    def _configured_plugins(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for config in (self._user_config(), self._project_config()):
            merged.update(_as_table(config.get("plugins")))
        return merged

    def _discovered_plugins(self) -> dict[str, dict[str, Any]]:
        discovered: dict[str, dict[str, Any]] = {}
        self._collect_marketplace_plugins(discovered)
        for manifest_path in self._plugin_manifest_paths():
            manifest = self._read_json_file(manifest_path)
            plugin_id = self._plugin_id_from_manifest(manifest, manifest_path)
            current = discovered.setdefault(plugin_id, {})
            current.update(
                {
                    "name": manifest.get("name") or manifest.get("id") or plugin_id,
                    "marketplace": manifest.get("marketplace") or self._marketplace_from_plugin_id(plugin_id),
                    "installed": True,
                    "path": str(manifest_path.parent.parent),
                    "sourcePath": str(manifest_path),
                    "bundled": self._plugin_bundles(manifest, manifest_path.parent.parent),
                },
            )
        return discovered

    def _collect_marketplace_plugins(self, discovered: dict[str, dict[str, Any]]) -> None:
        marketplace_path = self._resolver.codex_home / ".tmp" / "plugins" / ".agents" / "plugins" / "marketplace.json"
        if not marketplace_path.is_file():
            return
        marketplace = self._read_json_file(marketplace_path)
        for entry in self._flatten_plugin_entries(marketplace):
            plugin_id = self._plugin_id_from_entry(entry)
            if not plugin_id:
                continue
            current = discovered.setdefault(plugin_id, {})
            current.update(
                {
                    "name": entry.get("name") or entry.get("id") or plugin_id,
                    "marketplace": entry.get("marketplace") or self._marketplace_from_plugin_id(plugin_id),
                    "listed": True,
                    "sourcePath": str(marketplace_path),
                    "bundled": self._plugin_bundles(entry, None),
                },
            )

    def _plugin_manifest_paths(self) -> list[Path]:
        roots = [
            self._resolver.codex_home / "plugins" / "cache",
            self._resolver.codex_home / ".tmp" / "plugins" / "plugins",
        ]
        paths: list[Path] = []
        for root in roots:
            if root.is_dir():
                paths.extend(sorted(root.glob("**/.codex-plugin/plugin.json")))
        return paths

    @staticmethod
    def _read_json_file(path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _flatten_plugin_entries(self, value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for entry in value for item in self._flatten_plugin_entries(entry)]
        if not isinstance(value, dict):
            return []
        if "id" in value or "name" in value:
            return [value]
        entries: list[dict[str, Any]] = []
        for item in value.values():
            entries.extend(self._flatten_plugin_entries(item))
        return entries

    @staticmethod
    def _plugin_id_from_entry(entry: dict[str, Any]) -> str | None:
        raw_id = entry.get("id") or entry.get("name")
        if not isinstance(raw_id, str) or not raw_id:
            return None
        marketplace = entry.get("marketplace")
        if "@" not in raw_id and isinstance(marketplace, str) and marketplace:
            return f"{raw_id}@{marketplace}"
        return raw_id

    def _plugin_id_from_manifest(self, manifest: dict[str, Any], manifest_path: Path) -> str:
        raw_id = manifest.get("id") or manifest.get("name") or manifest_path.parent.parent.name
        plugin_id = str(raw_id)
        marketplace = manifest.get("marketplace")
        if "@" not in plugin_id and isinstance(marketplace, str) and marketplace:
            return f"{plugin_id}@{marketplace}"
        if "@" not in plugin_id:
            inferred_marketplace = self._marketplace_from_cache_path(manifest_path)
            if inferred_marketplace:
                return f"{plugin_id}@{inferred_marketplace}"
        return plugin_id

    @staticmethod
    def _marketplace_from_plugin_id(plugin_id: str) -> str | None:
        return plugin_id.split("@", 1)[1] if "@" in plugin_id else None

    def _marketplace_from_cache_path(self, manifest_path: Path) -> str | None:
        try:
            relative = manifest_path.relative_to(self._resolver.codex_home / "plugins" / "cache")
        except ValueError:
            return None
        return relative.parts[0] if relative.parts else None

    @staticmethod
    def _plugin_bundles(manifest: dict[str, Any], package_root: Path | None) -> dict[str, Any]:
        skills = manifest.get("skills", [])
        mcp_servers = manifest.get("mcp_servers") or manifest.get("mcpServers") or {}
        apps = manifest.get("apps", {})
        hooks = manifest.get("hooks", {})
        if package_root is not None and not skills:
            skills_dir = package_root / "skills"
            if skills_dir.is_dir():
                skills = [path.name for path in sorted(skills_dir.iterdir()) if path.is_dir()]
        if package_root is not None and not hooks:
            hooks_file = package_root / "hooks" / "hooks.json"
            if hooks_file.is_file():
                try:
                    hooks = json.loads(hooks_file.read_text(encoding="utf-8"))
                except Exception:
                    hooks = {}
        return {
            "skills": skills,
            "mcpServers": mcp_servers,
            "apps": apps,
            "hooks": hooks,
        }

    def _plugin_skill_summaries(self) -> list[CodexFileSummary]:
        summaries: list[CodexFileSummary] = []
        for manifest_path in self._plugin_manifest_paths():
            package_root = manifest_path.parent.parent
            skills_dir = package_root / "skills"
            if not skills_dir.is_dir():
                continue
            plugin_id = self._plugin_id_from_manifest(self._read_json_file(manifest_path), manifest_path)
            for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
                summaries.append(
                    CodexFileSummary(
                        name=skill_md.parent.name,
                        path=str(skill_md.relative_to(skills_dir)),
                        sizeBytes=skill_md.stat().st_size,
                        source="plugin",
                        readOnly=True,
                        metadata={"pluginId": plugin_id, "sourcePath": str(skill_md)},
                    ),
                )
        return summaries

    def _resource_config(self, resource: str) -> dict[str, Any]:
        user_config = self._user_config()
        project_config = self._project_config()
        if resource == "skills":
            return {"skills": _as_table(user_config.get("skills")) | _as_table(project_config.get("skills"))}
        return {}

    @staticmethod
    def _file_metadata(resource: str, relative_path: Path, size_bytes: int) -> dict[str, Any]:
        suffix = relative_path.suffix.lower()
        if resource == "skills":
            return {"format": "markdown" if suffix == ".md" else "text", "sizeBytes": size_bytes}
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
                    detail={"error": "INVALID_FILE_EXTENSION", "message": relative_path},
                )
            if not content.strip():
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={"error": "EMPTY_CONTENT", "message": resource},
                )

    def _structured_hooks(self, layer: CodexLayer, content: str, path: Path) -> list[CodexHookEntry]:
        parsed = _parse_json_document(content)
        if not isinstance(parsed, dict):
            return []
        return self._hook_entries_from_event_map(
            parsed,
            source="hooks_json",
            read_only=False,
            layer=layer.value,
            source_path=str(path),
        )

    @staticmethod
    def _validate_hooks_document(content: str) -> None:
        parsed = _parse_json_document(content)
        if not isinstance(parsed, dict):
            _raise_invalid_hooks("INVALID_HOOKS_DOCUMENT", "hooks.json must contain an object")
        for event, event_hooks in parsed.items():
            if not isinstance(event, str) or not isinstance(event_hooks, list):
                _raise_invalid_hooks("INVALID_HOOK_EVENT", str(event))
            for hook_entry in event_hooks:
                if not isinstance(hook_entry, dict):
                    _raise_invalid_hooks("INVALID_HOOK_ENTRY", event)
                actions = hook_entry.get("hooks")
                if not isinstance(actions, list) or len(actions) == 0:
                    _raise_invalid_hooks("INVALID_HOOK_ACTIONS", event)
                for action in actions:
                    if not isinstance(action, dict):
                        _raise_invalid_hooks("INVALID_HOOK_ACTION", event)
                    hook_type = action.get("type", "command")
                    if hook_type is not None and not isinstance(hook_type, str):
                        _raise_invalid_hooks("INVALID_HOOK_TYPE", event)
                    command = action.get("command")
                    if hook_type == "command" and (not isinstance(command, str) or not command.strip()):
                        _raise_invalid_hooks("MISSING_HOOK_COMMAND", event)
                    status_message = action.get("statusMessage")
                    if status_message is not None and not isinstance(status_message, str):
                        _raise_invalid_hooks("INVALID_HOOK_STATUS_MESSAGE", event)
                    timeout = action.get("timeout")
                    if timeout is not None and not isinstance(timeout, int):
                        _raise_invalid_hooks("INVALID_HOOK_TIMEOUT", event)

    def _codex_hooks_enabled(self) -> bool:
        for config in (self._project_config(), self._user_config()):
            features = _as_table(config.get("features"))
            if features.get("codex_hooks") is True:
                return True
        return False

    def _inline_hooks(self) -> list[dict[str, Any]]:
        hooks: list[dict[str, Any]] = []
        for layer, config in (("project", self._project_config()), ("user", self._user_config())):
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
                        hooks.append({"layer": layer, "event": event, "hook": event_hooks})
        return hooks

    def _inline_hook_entries(self, inline_hooks: list[dict[str, Any]]) -> list[CodexHookEntry]:
        entries: list[CodexHookEntry] = []
        for index, hook in enumerate(inline_hooks):
            event = hook.get("event")
            config = hook.get("hook")
            layer = hook.get("layer") if hook.get("layer") in {"project", "user"} else None
            if not isinstance(event, str) or not isinstance(config, dict):
                continue
            entries.extend(
                self._hook_entries_from_event_map(
                    {event: [config]},
                    source="inline_config",
                    read_only=True,
                    layer=layer,
                    source_path=str(self._resolver.resolve(str(layer), CodexResource.CONFIG)) if layer else None,
                    id_prefix=f"inline:{layer or 'unknown'}:{index}",
                ),
            )
        return entries

    def _plugin_hook_entries(self) -> list[CodexHookEntry]:
        entries: list[CodexHookEntry] = []
        for plugin_id, plugin in sorted(self._discovered_plugins().items()):
            bundled = _as_table(plugin.get("bundled"))
            hook_map = self._normalize_hooks_root(bundled.get("hooks"))
            if not hook_map:
                continue
            entries.extend(
                self._hook_entries_from_event_map(
                    hook_map,
                    source="plugin",
                    read_only=True,
                    source_path=plugin.get("sourcePath") if isinstance(plugin.get("sourcePath"), str) else None,
                    plugin_id=plugin_id,
                    plugin_name=str(plugin.get("name") or plugin_id),
                    marketplace_name=plugin.get("marketplace") if isinstance(plugin.get("marketplace"), str) else None,
                    id_prefix=f"plugin:{plugin_id}",
                ),
            )
        return entries

    def _managed_hook_entries(self) -> list[CodexHookEntry]:
        entries: list[CodexHookEntry] = []
        for layer in (CodexLayer.PROJECT, CodexLayer.USER):
            path = self._resolver.resolve(layer, CodexResource.MANAGED_REQUIREMENTS)
            config = _read_toml(path)
            hook_map = self._normalize_hooks_root(config.get("hooks"))
            if not hook_map:
                continue
            entries.extend(
                self._hook_entries_from_event_map(
                    hook_map,
                    source="managed",
                    read_only=True,
                    layer=layer.value,
                    source_path=str(path),
                    id_prefix=f"managed:{layer.value}",
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
        id_prefix: str | None = None,
    ) -> list[CodexHookEntry]:
        hook_map = self._normalize_hooks_root(value)
        entries: list[CodexHookEntry] = []
        for event, event_hooks in hook_map.items():
            for index, hook_entry in enumerate(event_hooks):
                raw_actions = hook_entry.get("hooks") if "hooks" in hook_entry else [hook_entry]
                actions = self._hook_actions(raw_actions)
                first_action: CodexHookCommandAction | dict[str, Any] = actions[0] if actions else {}
                entry_id = ":".join(part for part in [id_prefix, str(layer) if not id_prefix else None, event, str(index)] if part)
                entries.append(
                    CodexHookEntry(
                        id=entry_id,
                        event=event,
                        index=index,
                        matcher=hook_entry.get("matcher") if isinstance(hook_entry.get("matcher"), str) else None,
                        actions=actions,
                        action=first_action,
                        source=source,  # type: ignore[arg-type]
                        layer=layer,  # type: ignore[arg-type]
                        readOnly=read_only,
                        sourcePath=source_path,
                        pluginId=plugin_id,
                        pluginName=plugin_name,
                        marketplaceName=marketplace_name,
                        raw=dict(hook_entry),
                    ),
                )
        return entries

    @staticmethod
    def _normalize_hooks_root(value: Any) -> dict[str, list[dict[str, Any]]]:
        root = _as_table(value)
        if "hooks" in root and isinstance(root.get("hooks"), dict):
            root = _as_table(root.get("hooks"))
        normalized: dict[str, list[dict[str, Any]]] = {}
        for event, event_hooks in root.items():
            if not isinstance(event, str):
                continue
            if isinstance(event_hooks, list):
                normalized[event] = [item for item in event_hooks if isinstance(item, dict)]
            elif isinstance(event_hooks, dict):
                normalized[event] = [event_hooks]
        return normalized

    @staticmethod
    def _hook_actions(value: Any) -> list[CodexHookCommandAction]:
        if not isinstance(value, list):
            return []
        actions: list[CodexHookCommandAction] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("type", "command") != "command":
                continue
            status_message = item.get("statusMessage")
            actions.append(
                CodexHookCommandAction(
                    type="command",
                    command=item.get("command") if isinstance(item.get("command"), str) else "",
                    timeout=item.get("timeout") if isinstance(item.get("timeout"), int) else None,
                    statusMessage=status_message if isinstance(status_message, str) else None,
                    raw=dict(item),
                ),
            )
        return actions

    def _project_config(self) -> dict[str, Any]:
        return _read_toml(self._resolver.resolve(CodexLayer.PROJECT, CodexResource.CONFIG))

    def _user_config(self) -> dict[str, Any]:
        return _read_toml(self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG))

    def _project_doc_max_bytes(self) -> int:
        for config in (self._project_config(), self._user_config()):
            value = config.get("project_doc_max_bytes")
            if isinstance(value, int) and value > 0:
                return value
        return DEFAULT_PROJECT_DOC_MAX_BYTES

    def _project_doc_fallback_filenames(self) -> list[str]:
        for config in (self._project_config(), self._user_config()):
            filenames = _as_string_list(config.get("project_doc_fallback_filenames"))
            if filenames:
                return filenames
        return []

    def _first_existing_fallback(self) -> Path | None:
        for filename in self._project_doc_fallback_filenames():
            path = self._resolver.workspace_root / filename
            if path.is_file():
                return path
        return None

    def _build_agents_md_caveats(
        self,
        layer: CodexLayer,
        path: Path,
        content: str,
        max_bytes: int,
    ) -> list[CodexAgentsMdCaveat]:
        caveats: list[CodexAgentsMdCaveat] = []
        if layer == CodexLayer.PROJECT:
            override_path = path.with_name("AGENTS.override.md")
            if override_path.is_file():
                caveats.append(
                    CodexAgentsMdCaveat(
                        type="override",
                        path=str(override_path),
                        messageKey="workspace.agentSettings.codex.agentsMd.caveats.override",
                    ),
                )
            if not path.is_file():
                fallback_path = self._first_existing_fallback()
                if fallback_path is not None:
                    caveats.append(
                        CodexAgentsMdCaveat(
                            type="fallback",
                            path=str(fallback_path),
                            messageKey="workspace.agentSettings.codex.agentsMd.caveats.fallback",
                        ),
                    )
        size_bytes = len(content.encode("utf-8"))
        if size_bytes >= int(max_bytes * 0.9):
            caveats.append(
                CodexAgentsMdCaveat(
                    type="size_limit",
                    path=str(path),
                    messageKey="workspace.agentSettings.codex.agentsMd.caveats.sizeLimit",
                    metadata={"sizeBytes": size_bytes, "maxBytes": max_bytes},
                ),
            )
        return caveats


def get_codex_settings_service() -> CodexSettingsService:
    """Return the Codex settings service dependency."""

    return CodexSettingsService()
