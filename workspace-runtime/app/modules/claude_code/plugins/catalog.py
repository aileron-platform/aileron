"""Claude Code plugin workflow service."""

from __future__ import annotations

import json
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from aileron_marketplace_core import (
    ClaudePluginResources,
    read_plugin_resource_owner,
    resolve_claude_plugin_resources,
)
from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.claude_code.documents import (
    DocumentScope,
    resolve_scope_root,
    workspace_root,
)
from app.modules.claude_code.settings.configuration import SettingsService
from app.modules.cli_settings.user_scope.codecs import JsonDocumentCodec
from app.modules.cli_settings.user_scope.paths import (
    logical_runtime_locator,
    runtime_user_home,
)
from app.modules.marketplace_operations.gate import get_marketplace_provider_gate
from app.modules.marketplace_operations.plugin_resources import (
    sanitize_plugin_definition,
)

from .models import (
    ClaudePluginDependency,
    ClaudePluginDetail,
    ClaudePluginDetailResponse,
    ClaudePluginInstallation,
    ClaudePluginMarketplaceSummary,
    ClaudePluginResourceCounts,
    ClaudePluginScope,
    ClaudePluginsResponse,
    ClaudePluginSummary,
    ClaudePluginToggleResponse,
)
from .provider_inventory import (
    ClaudeProviderInventorySnapshot,
    build_claude_provider_inventory_snapshot,
    read_claude_installed_manifest,
    run_claude_plugin_cli,
)

CLI_TIMEOUT_SECONDS = 10

_settings_locks: dict[str, threading.Lock] = {}
_settings_locks_guard = threading.Lock()
_json_codec = JsonDocumentCodec()
_provider_read_executor = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="claude-provider-read",
)


class ClaudePluginsService:
    """Read and toggle Claude Code plugins."""

    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self._settings_service = settings_service or SettingsService()

    def list_plugins(self, workspace_id: str) -> ClaudePluginsResponse:
        snapshot_future = _provider_read_executor.submit(
            self.read_provider_inventory,
            workspace_id,
        )
        marketplace_future = _provider_read_executor.submit(
            self._marketplace_rows,
            workspace_id,
        )
        snapshot = snapshot_future.result()
        marketplace_rows = marketplace_future.result()
        summaries: list[ClaudePluginSummary] = []
        for plugin_id, group in sorted(self._group_rows(list(snapshot.rows)).items()):
            projection = snapshot.resource_projection(plugin_id)
            if projection is None:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY,
                    detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"},
                )
            summaries.append(
                self._summary_from_group(
                    plugin_id,
                    group,
                    install_path=projection.install_root,
                    installed_manifest=projection.manifest,
                    resolved_resources=projection.resources,
                )
            )
        marketplace_counts: dict[str, int] = {}
        for summary in summaries:
            if summary.marketplace:
                marketplace_counts[summary.marketplace] = (
                    marketplace_counts.get(summary.marketplace, 0) + 1
                )
        marketplaces = [
            self._marketplace_summary(row, marketplace_counts)
            for row in marketplace_rows
        ]
        known_marketplaces = {item.name for item in marketplaces}
        for name, count in sorted(marketplace_counts.items()):
            if name not in known_marketplaces:
                marketplaces.append(
                    ClaudePluginMarketplaceSummary(name=name, pluginCount=count)
                )
        response = ClaudePluginsResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=self._provider_generation(),
            plugins=summaries,
            marketplaces=marketplaces,
        )
        return response

    def get_plugin_detail(
        self, workspace_id: str, plugin_id: str
    ) -> ClaudePluginDetailResponse:
        rows = self._plugin_rows(workspace_id)
        group = self._group_rows(rows).get(plugin_id)
        if not group:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id},
            )
        selected = self._selected_installation_row(group)
        raw_install_path = selected.get("installPath")
        if not isinstance(raw_install_path, str) or not raw_install_path.strip():
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"},
            )
        install_path = Path(raw_install_path)
        installed_manifest = self._installed_manifest(install_path)
        resolved_resources = self._resolved_resources(install_path)
        summary = self._summary_from_group(
            plugin_id,
            group,
            install_path=install_path,
            installed_manifest=installed_manifest,
            resolved_resources=resolved_resources,
        )
        metadata = self._manifest_metadata(installed_manifest, plugin_id)
        detail = ClaudePluginDetail(
            **summary.model_dump(),
            repository=metadata.get("repository"),
            license=metadata.get("license"),
            readme=self._read_text(install_path / "README.md"),
            dependencies=self._dependencies(installed_manifest, summary.marketplace),
            resources=self._resource_lists(
                install_path,
                include_metadata=True,
                resolved_resources=resolved_resources,
            ),
            manifest=self._public_manifest(installed_manifest, install_path),
        )
        return ClaudePluginDetailResponse(
            workspaceId=workspace_id,
            providerResourceGeneration=self._provider_generation(),
            plugin=detail,
        )

    def read_provider_inventory(
        self,
        workspace_id: str,
    ) -> ClaudeProviderInventorySnapshot:
        """Read provider rows with internal roots retained outside public models."""

        return build_claude_provider_inventory_snapshot(self._plugin_rows(workspace_id))

    def set_plugin_enabled(
        self,
        workspace_id: str,
        plugin_id: str,
        scope: ClaudePluginScope,
        enabled: bool,
        revision: str | None = None,
    ) -> ClaudePluginToggleResponse:
        gate = get_marketplace_provider_gate()
        rows = self._plugin_rows(workspace_id)
        if plugin_id not in self._group_rows(rows):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id},
            )
        settings_path = self._settings_file(workspace_id, scope)
        lock = self._settings_lock(settings_path)
        with lock:
            current_content = (
                settings_path.read_bytes() if settings_path.is_file() else b""
            )
            assert_revision(compute_revision(current_content), revision)
            state = self._read_settings_strict(settings_path)
            plugins = state.get("enabledPlugins")
            if not isinstance(plugins, dict):
                plugins = {}
            plugins[plugin_id] = enabled
            state["enabledPlugins"] = plugins
            _json_codec.write(settings_path, state)
            next_content = (
                settings_path.read_bytes() if settings_path.is_file() else b""
            )
        generation = gate.advance_generation("claude-code")
        from app.modules.cli_settings.cache_api import clear_agent_settings_cache

        clear_agent_settings_cache(
            provider="claude-code",
            workspace_id=workspace_id,
        )
        return ClaudePluginToggleResponse(
            workspaceId=workspace_id,
            pluginId=plugin_id,
            scope=scope,
            enabled=enabled,
            revision=compute_revision(next_content),
            providerResourceGeneration=generation,
        )

    def _plugin_rows(self, workspace_id: str) -> list[dict[str, Any]]:
        output = self._run_claude_json(workspace_id, ["plugin", "list", "--json"])
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            rows = output.get("plugins") or output.get("items") or output.get("data")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"},
        )

    def _marketplace_rows(self, workspace_id: str) -> list[dict[str, Any]]:
        output = self._run_claude_json(
            workspace_id, ["plugin", "marketplace", "list", "--json"]
        )
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            rows = (
                output.get("marketplaces") or output.get("items") or output.get("data")
            )
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"},
        )

    def _run_claude_json(self, workspace_id: str, args: list[str]) -> Any:
        try:
            completed = run_claude_plugin_cli(
                args,
                cwd=workspace_root(),
                timeout=CLI_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"},
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"error": "CLAUDE_PLUGIN_CLI_TIMEOUT"},
            ) from exc

        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}".lower()
            error = (
                "CLAUDE_PLUGIN_CLI_UNSUPPORTED"
                if "unknown" in combined or "unsupported" in combined
                else "CLAUDE_PLUGIN_CLI_FAILED"
            )
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={"error": error},
            )
        try:
            return json.loads(completed.stdout or "null")
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"},
            ) from exc

    @staticmethod
    def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            plugin_id = row.get("id") or row.get("pluginId") or row.get("name")
            if isinstance(plugin_id, str) and plugin_id:
                groups.setdefault(plugin_id, []).append(row)
        return groups

    def _summary_from_group(
        self,
        plugin_id: str,
        rows: list[dict[str, Any]],
        *,
        install_path: Path,
        installed_manifest: dict[str, Any],
        resolved_resources: ClaudePluginResources,
    ) -> ClaudePluginSummary:
        selected = self._selected_installation_row(rows)
        metadata = self._manifest_metadata(installed_manifest, plugin_id)
        errors: list[str] = []
        for row in rows:
            raw_errors = row.get("errors")
            if isinstance(raw_errors, list) and raw_errors:
                errors.append("marketplace.settings.plugin_provider_error")
        installations = [self._installation(row) for row in rows]
        return ClaudePluginSummary(
            id=plugin_id,
            name=metadata["name"] or plugin_id.split("@", 1)[0],
            marketplace=self._marketplace_from_id(plugin_id),
            version=metadata.get("version")
            or self._optional_str(selected.get("version")),
            description=metadata.get("description"),
            author=metadata.get("author"),
            category=metadata.get("category"),
            homepage=metadata.get("homepage"),
            enabled=self._effective_enabled(installations),
            installations=sorted(
                installations, key=lambda item: self._scope_rank(item.scope)
            ),
            errors=errors,
            resourceCounts=self._resource_counts(
                install_path,
                resolved_resources=resolved_resources,
            ),
        )

    def _selected_installation_row(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(
            rows,
            key=lambda row: self._scope_rank(str(row.get("scope") or "user")),
            reverse=True,
        )[0]

    @staticmethod
    def _installation(row: dict[str, Any]) -> ClaudePluginInstallation:
        scope = str(row.get("scope") or "user")
        if scope not in {"user", "project", "local"}:
            scope = "user"
        return ClaudePluginInstallation(
            scope=scope,  # type: ignore[arg-type]
            enabled=bool(row.get("enabled")),
            version=row.get("version") if isinstance(row.get("version"), str) else None,
            installedAt=(
                row.get("installedAt")
                if isinstance(row.get("installedAt"), str)
                else None
            ),
            lastUpdated=(
                row.get("lastUpdated")
                if isinstance(row.get("lastUpdated"), str)
                else None
            ),
        )

    @classmethod
    def _effective_enabled(cls, installations: list[ClaudePluginInstallation]) -> bool:
        value = False
        for installation in sorted(
            installations, key=lambda item: cls._scope_rank(item.scope)
        ):
            value = installation.enabled
        return value

    @staticmethod
    def _scope_rank(scope: str) -> int:
        return {"user": 0, "project": 1, "local": 2}.get(scope, 0)

    @staticmethod
    def _marketplace_from_id(plugin_id: str) -> str | None:
        return plugin_id.split("@", 1)[1] if "@" in plugin_id else None

    def _manifest_metadata(
        self, installed_manifest: dict[str, Any], plugin_id: str
    ) -> dict[str, str | None]:
        author = installed_manifest.get("author")
        if isinstance(author, dict):
            author_name = self._optional_str(author.get("name"))
        else:
            author_name = self._optional_str(author)
        source = installed_manifest.get("source")
        repository = None
        if isinstance(source, dict):
            repository = self._optional_str(source.get("repo")) or self._optional_str(
                source.get("url")
            )
        return {
            "name": self._optional_str(installed_manifest.get("name"))
            or plugin_id.split("@", 1)[0],
            "version": self._optional_str(installed_manifest.get("version")),
            "description": self._optional_str(installed_manifest.get("description")),
            "author": author_name,
            "category": self._optional_str(installed_manifest.get("category")),
            "homepage": self._optional_str(installed_manifest.get("homepage")),
            "repository": self._optional_str(installed_manifest.get("repository"))
            or repository,
            "license": self._optional_str(installed_manifest.get("license")),
        }

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _resource_counts(
        self,
        install_path: Path,
        *,
        resolved_resources: ClaudePluginResources | None = None,
    ) -> ClaudePluginResourceCounts:
        resources = self._resource_lists(
            install_path,
            include_metadata=False,
            resolved_resources=resolved_resources,
        )
        return ClaudePluginResourceCounts(
            commands=len(resources["commands"]),
            agents=len(resources["agents"]),
            hooks=len(resources["hooks"]),
            mcpServers=len(resources["mcpServers"]),
            skills=len(resources["skills"]),
            outputStyles=len(resources["outputStyles"]),
        )

    def _resource_lists(
        self,
        install_path: Path,
        *,
        include_metadata: bool,
        resolved_resources: ClaudePluginResources | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        resolved = (
            self._validate_resolved_resources(resolved_resources)
            if resolved_resources is not None
            else self._resolved_resources(install_path)
        )
        return self._resource_lists_from_resolved(
            install_path,
            resolved,
            include_metadata=include_metadata,
        )

    @staticmethod
    def _resolved_resources(install_path: Path) -> ClaudePluginResources:
        return ClaudePluginsService._validate_resolved_resources(
            resolve_claude_plugin_resources(install_path)
        )

    @staticmethod
    def _validate_resolved_resources(
        resolved: ClaudePluginResources,
    ) -> ClaudePluginResources:
        if resolved.diagnostics:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={
                    "errorCode": ("marketplace.settings.plugin_resource_parse_failed"),
                    "diagnostics": [
                        {
                            "code": item.code,
                            "sourceLocator": item.source_locator,
                        }
                        for item in resolved.diagnostics
                    ],
                },
            )
        return resolved

    def _resource_lists_from_resolved(
        self,
        install_path: Path,
        resolved: ClaudePluginResources,
        *,
        include_metadata: bool,
    ) -> dict[str, list[dict[str, Any]]]:
        file_resources: dict[str, list[dict[str, Any]]] = {
            "command": [],
            "agent": [],
            "skill": [],
            "output-style": [],
        }
        for resource in resolved.file_resources:
            file_resources[resource.resource_type].append(
                self._file_resource(
                    install_path,
                    resource.source_locator,
                    resource.resource_root_locator,
                    resource.resource_type == "skill",
                    include_metadata=include_metadata,
                )
            )
        return {
            "commands": file_resources["command"],
            "agents": file_resources["agent"],
            "hooks": self._hook_resources(install_path, resolved.hook_sources),
            "mcpServers": self._owned_config_resources(
                install_path,
                resolved.mcp_servers,
            ),
            "skills": file_resources["skill"],
            "outputStyles": file_resources["output-style"],
        }

    def _file_resource(
        self,
        install_path: Path,
        source_locator: str,
        resource_root_locator: str,
        is_skill: bool,
        *,
        include_metadata: bool,
    ) -> dict[str, Any]:
        path = install_path / source_locator
        resource: dict[str, Any] = {
            "name": (Path(resource_root_locator).name if is_skill else path.stem),
            "path": source_locator,
        }
        if include_metadata:
            metadata = self._markdown_frontmatter(path)
            description = metadata.get("description")
            if isinstance(description, str):
                resource["description"] = description
            name = metadata.get("name")
            if isinstance(name, str):
                resource["name"] = name
        return resource

    @staticmethod
    def _owned_config_resources(
        install_path: Path,
        owners: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            {
                "name": name,
                "config": sanitize_plugin_definition(
                    read_plugin_resource_owner(install_path, owner),
                    installed_root=install_path,
                ),
            }
            for name, owner in sorted(owners.items())
        ]

    @staticmethod
    def _hook_resources(install_path: Path, owners: Any) -> list[dict[str, Any]]:
        hooks: dict[str, list[Any]] = {}
        for owner in owners or ():
            value = sanitize_plugin_definition(
                read_plugin_resource_owner(install_path, owner),
                installed_root=install_path,
            )
            if not isinstance(value, dict):
                continue
            for name, config in value.items():
                hooks.setdefault(str(name), []).append(config)
        return [
            {
                "name": name,
                "config": config,
            }
            for name, config in sorted(hooks.items())
        ]

    def _dependencies(
        self, registry_entry: dict[str, Any], own_marketplace: str | None
    ) -> list[ClaudePluginDependency]:
        dependencies = registry_entry.get("dependencies")
        if not isinstance(dependencies, list):
            return []
        result: list[ClaudePluginDependency] = []
        for item in dependencies:
            if isinstance(item, str):
                result.append(ClaudePluginDependency(name=item))
            elif isinstance(item, dict) and isinstance(item.get("name"), str):
                result.append(
                    ClaudePluginDependency(
                        name=item["name"],
                        version=self._optional_str(item.get("version")),
                        marketplace=self._optional_str(item.get("marketplace"))
                        or own_marketplace,
                    ),
                )
        return result

    @staticmethod
    def _marketplace_summary(
        row: dict[str, Any], counts: dict[str, int]
    ) -> ClaudePluginMarketplaceSummary:
        name = str(row.get("name") or row.get("id") or row.get("marketplace") or "")
        owner = row.get("owner")
        owner_name = owner.get("name") if isinstance(owner, dict) else owner
        plugins = row.get("plugins")
        count = counts.get(name)
        if count is None and isinstance(plugins, list):
            count = len(plugins)
        return ClaudePluginMarketplaceSummary(
            name=name,
            owner=owner_name if isinstance(owner_name, str) else None,
            pluginCount=count or 0,
            source=ClaudePluginsService._marketplace_source_label(row.get("source")),
        )

    @staticmethod
    def _marketplace_source_label(source: Any) -> str | None:
        if isinstance(source, str):
            return ClaudePluginsService._logical_marketplace_source(source)
        if isinstance(source, dict):
            value = (
                ClaudePluginsService._optional_str(source.get("repo"))
                or ClaudePluginsService._optional_str(source.get("url"))
                or ClaudePluginsService._optional_str(source.get("path"))
                or ClaudePluginsService._optional_str(source.get("source"))
            )
            return ClaudePluginsService._logical_marketplace_source(value)
        return None

    @staticmethod
    def _logical_marketplace_source(value: str | None) -> str | None:
        sanitized = sanitize_plugin_definition(value)
        if not isinstance(sanitized, str) or not sanitized:
            return None
        try:
            parsed = urlsplit(sanitized)
        except ValueError:
            return "local"
        if parsed.scheme:
            if parsed.scheme.casefold() != "file":
                return sanitized if parsed.netloc else "local"
            if parsed.netloc not in {"", "localhost"}:
                return "local"
            candidate = Path(unquote(parsed.path))
            if not candidate.is_absolute():
                return "local"
            return (
                logical_runtime_locator(
                    candidate,
                    user_home=runtime_user_home(),
                    workspace_root=workspace_root(),
                )
                or "local"
            )
        candidate = Path(sanitized)
        if not candidate.is_absolute():
            return sanitized
        return (
            logical_runtime_locator(
                candidate,
                user_home=runtime_user_home(),
                workspace_root=workspace_root(),
            )
            or "local"
        )

    @staticmethod
    def _installed_manifest(install_path: Path) -> dict[str, Any]:
        return read_claude_installed_manifest(install_path)

    @staticmethod
    def _read_text(path: Path) -> str | None:
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None

    @classmethod
    def _markdown_frontmatter(cls, path: Path) -> dict[str, Any]:
        content = cls._read_text(path)
        if not content or not content.startswith("---"):
            return {}
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}
        result: dict[str, Any] = {}
        for line in parts[1].splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            trimmed_key = key.strip()
            trimmed_value = value.strip().strip("\"'")
            if trimmed_key:
                result[trimmed_key] = trimmed_value
        return result

    @staticmethod
    def _public_manifest(
        manifest: dict[str, Any],
        install_path: Path,
    ) -> dict[str, Any]:
        public_fields = {
            "name",
            "version",
            "description",
            "author",
            "category",
            "homepage",
            "repository",
            "license",
            "source",
            "keywords",
            "capabilities",
        }
        sanitized = sanitize_plugin_definition(
            {key: value for key, value in manifest.items() if key in public_fields},
            installed_root=install_path,
        )
        return sanitized if isinstance(sanitized, dict) else {}

    @staticmethod
    def _provider_generation() -> int:
        return get_marketplace_provider_gate().generation("claude-code")

    @staticmethod
    def _settings_file(workspace_id: str, scope: ClaudePluginScope) -> Path:
        if scope == "user":
            return (
                resolve_scope_root(workspace_id, DocumentScope.USER) / "settings.json"
            )
        root = resolve_scope_root(workspace_id, DocumentScope.PROJECT)
        return root / ("settings.local.json" if scope == "local" else "settings.json")

    @staticmethod
    def _settings_lock(path: Path) -> threading.Lock:
        key = str(path)
        with _settings_locks_guard:
            lock = _settings_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                _settings_locks[key] = lock
            return lock

    @staticmethod
    def _read_settings_strict(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_SETTINGS_JSON", "message": str(path)},
            ) from exc
        if not isinstance(data, dict):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_SETTINGS_JSON", "message": str(path)},
            )
        return data


def get_claude_plugins_service() -> ClaudePluginsService:
    """Return Claude plugin service dependency."""

    return ClaudePluginsService()
