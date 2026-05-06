"""Claude Code plugin workflow service."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
from typing import Any

from fastapi import HTTPException, status

from app.modules.claude_code.common import DocumentScope, resolve_scope_root, workspace_root
from app.modules.claude_code.settings.service import SettingsService

from .loader import get_plugin_loader
from .models import (
    ClaudePluginDependency,
    ClaudePluginDetail,
    ClaudePluginDetailResponse,
    ClaudePluginInstallation,
    ClaudePluginMarketplaceSummary,
    ClaudePluginResourceCounts,
    ClaudePluginsResponse,
    ClaudePluginSummary,
    ClaudePluginToggleResponse,
    ClaudePluginScope,
)

CLI_TIMEOUT_SECONDS = 10

_settings_locks: dict[str, threading.Lock] = {}
_settings_locks_guard = threading.Lock()
_list_cache: dict[str, tuple[tuple[Any, ...], ClaudePluginsResponse]] = {}
_list_cache_guard = threading.Lock()


class ClaudePluginsService:
    """Read and toggle Claude Code plugins."""

    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self._settings_service = settings_service or SettingsService()

    def list_plugins(self, workspace_id: str) -> ClaudePluginsResponse:
        signature = self._list_signature(workspace_id)
        with _list_cache_guard:
            cached = _list_cache.get(workspace_id)
            if cached is not None and cached[0] == signature:
                return cached[1]

        rows = self._plugin_rows(workspace_id)
        marketplace_rows = self._marketplace_rows(workspace_id)
        summaries = [
            self._summary_from_group(workspace_id, plugin_id, group)
            for plugin_id, group in sorted(self._group_rows(rows).items())
        ]
        marketplace_counts: dict[str, int] = {}
        for summary in summaries:
            if summary.marketplace:
                marketplace_counts[summary.marketplace] = marketplace_counts.get(summary.marketplace, 0) + 1
        marketplaces = [
            self._marketplace_summary(row, marketplace_counts)
            for row in marketplace_rows
        ]
        known_marketplaces = {item.name for item in marketplaces}
        for name, count in sorted(marketplace_counts.items()):
            if name not in known_marketplaces:
                marketplaces.append(ClaudePluginMarketplaceSummary(name=name, pluginCount=count))
        response = ClaudePluginsResponse(workspaceId=workspace_id, plugins=summaries, marketplaces=marketplaces)
        with _list_cache_guard:
            _list_cache[workspace_id] = (signature, response)
        return response

    def get_plugin_detail(self, workspace_id: str, plugin_id: str) -> ClaudePluginDetailResponse:
        rows = self._plugin_rows(workspace_id)
        group = self._group_rows(rows).get(plugin_id)
        if not group:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id})
        summary = self._summary_from_group(workspace_id, plugin_id, group)
        selected = self._selected_installation_row(group)
        install_path = Path(str(selected.get("installPath") or ""))
        marketplace_entry = self._marketplace_plugin_entry(workspace_id, plugin_id)
        metadata = self._registry_metadata(marketplace_entry, plugin_id)
        resource_root = self._resource_root(workspace_id, plugin_id, marketplace_entry, install_path)
        detail = ClaudePluginDetail(
            **summary.model_dump(),
            repository=metadata.get("repository"),
            license=metadata.get("license"),
            readme=self._read_text(resource_root / "README.md") or self._read_text(install_path / "README.md"),
            dependencies=self._dependencies(marketplace_entry, summary.marketplace),
            resources=self._resource_lists(resource_root, include_metadata=True),
            manifest=marketplace_entry,
        )
        return ClaudePluginDetailResponse(workspaceId=workspace_id, plugin=detail)

    def set_plugin_enabled(
        self,
        workspace_id: str,
        plugin_id: str,
        scope: ClaudePluginScope,
        enabled: bool,
    ) -> ClaudePluginToggleResponse:
        rows = self._plugin_rows(workspace_id)
        if plugin_id not in self._group_rows(rows):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"error": "PLUGIN_NOT_FOUND", "message": plugin_id})
        settings_path = self._settings_file(workspace_id, scope)
        lock = self._settings_lock(settings_path)
        with lock:
            state = self._read_settings_strict(settings_path)
            plugins = state.get("enabledPlugins")
            if not isinstance(plugins, dict):
                plugins = {}
            plugins[plugin_id] = enabled
            state["enabledPlugins"] = plugins
            self._atomic_write_json(settings_path, state)
        get_plugin_loader(self._settings_service).clear_cache(workspace_id)
        self._clear_list_cache(workspace_id)
        return ClaudePluginToggleResponse(workspaceId=workspace_id, pluginId=plugin_id, scope=scope, enabled=enabled)

    def _plugin_rows(self, workspace_id: str) -> list[dict[str, Any]]:
        output = self._run_claude_json(workspace_id, ["plugin", "list", "--json"])
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            rows = output.get("plugins") or output.get("items") or output.get("data")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"})

    def _marketplace_rows(self, workspace_id: str) -> list[dict[str, Any]]:
        output = self._run_claude_json(workspace_id, ["plugin", "marketplace", "list", "--json"])
        if isinstance(output, list):
            return [item for item in output if isinstance(item, dict)]
        if isinstance(output, dict):
            rows = output.get("marketplaces") or output.get("items") or output.get("data")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"})

    def _run_claude_json(self, workspace_id: str, args: list[str]) -> Any:
        try:
            completed = subprocess.run(
                ["claude", *args],
                cwd=str(workspace_root()),
                text=True,
                capture_output=True,
                timeout=CLI_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail={"error": "CLAUDE_PLUGIN_CLI_UNAVAILABLE"}) from exc
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, detail={"error": "CLAUDE_PLUGIN_CLI_TIMEOUT"}) from exc

        if completed.returncode != 0:
            combined = f"{completed.stdout}\n{completed.stderr}".lower()
            error = "CLAUDE_PLUGIN_CLI_UNSUPPORTED" if "unknown" in combined or "unsupported" in combined else "CLAUDE_PLUGIN_CLI_FAILED"
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"error": error, "message": completed.stderr.strip() or completed.stdout.strip()})
        try:
            return json.loads(completed.stdout or "null")
        except json.JSONDecodeError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail={"error": "CLAUDE_PLUGIN_CLI_INVALID_JSON"}) from exc

    @staticmethod
    def _group_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            plugin_id = row.get("id") or row.get("pluginId") or row.get("name")
            if isinstance(plugin_id, str) and plugin_id:
                groups.setdefault(plugin_id, []).append(row)
        return groups

    def _summary_from_group(self, workspace_id: str, plugin_id: str, rows: list[dict[str, Any]]) -> ClaudePluginSummary:
        selected = self._selected_installation_row(rows)
        install_path = Path(str(selected.get("installPath") or ""))
        marketplace_entry = self._marketplace_plugin_entry(workspace_id, plugin_id)
        resource_root = self._resource_root(workspace_id, plugin_id, marketplace_entry, install_path)
        metadata = self._registry_metadata(marketplace_entry, plugin_id)
        errors: list[str] = []
        for row in rows:
            raw_errors = row.get("errors")
            if isinstance(raw_errors, list):
                errors.extend(item for item in raw_errors if isinstance(item, str))
        installations = [self._installation(row) for row in rows]
        return ClaudePluginSummary(
            id=plugin_id,
            name=metadata["name"],
            marketplace=self._marketplace_from_id(plugin_id),
            version=metadata.get("version") or self._optional_str(selected.get("version")),
            description=metadata.get("description"),
            author=metadata.get("author"),
            category=metadata.get("category"),
            homepage=metadata.get("homepage"),
            enabled=self._effective_enabled(installations),
            installations=sorted(installations, key=lambda item: self._scope_rank(item.scope)),
            errors=errors,
            resourceCounts=self._resource_counts(resource_root),
        )

    def _selected_installation_row(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return sorted(rows, key=lambda row: self._scope_rank(str(row.get("scope") or "user")), reverse=True)[0]

    @staticmethod
    def _installation(row: dict[str, Any]) -> ClaudePluginInstallation:
        scope = str(row.get("scope") or "user")
        if scope not in {"user", "project", "local"}:
            scope = "user"
        return ClaudePluginInstallation(
            scope=scope,  # type: ignore[arg-type]
            enabled=bool(row.get("enabled")),
            installPath=str(row.get("installPath") or row.get("path") or ""),
            projectPath=row.get("projectPath") if isinstance(row.get("projectPath"), str) else None,
            version=row.get("version") if isinstance(row.get("version"), str) else None,
            installedAt=row.get("installedAt") if isinstance(row.get("installedAt"), str) else None,
            lastUpdated=row.get("lastUpdated") if isinstance(row.get("lastUpdated"), str) else None,
        )

    @classmethod
    def _effective_enabled(cls, installations: list[ClaudePluginInstallation]) -> bool:
        value = False
        for installation in sorted(installations, key=lambda item: cls._scope_rank(item.scope)):
            value = installation.enabled
        return value

    @staticmethod
    def _scope_rank(scope: str) -> int:
        return {"user": 0, "project": 1, "local": 2}.get(scope, 0)

    @staticmethod
    def _marketplace_from_id(plugin_id: str) -> str | None:
        return plugin_id.split("@", 1)[1] if "@" in plugin_id else None

    def _registry_metadata(self, registry_entry: dict[str, Any], plugin_id: str) -> dict[str, str | None]:
        author = registry_entry.get("author")
        if isinstance(author, dict):
            author_name = self._optional_str(author.get("name"))
        else:
            author_name = self._optional_str(author)
        source = registry_entry.get("source")
        repository = None
        if isinstance(source, dict):
            repository = self._optional_str(source.get("repo")) or self._optional_str(source.get("url"))
        return {
            "name": self._optional_str(registry_entry.get("name")) or plugin_id.split("@", 1)[0],
            "version": self._optional_str(registry_entry.get("version")),
            "description": self._optional_str(registry_entry.get("description")),
            "author": author_name,
            "category": self._optional_str(registry_entry.get("category")),
            "homepage": self._optional_str(registry_entry.get("homepage")),
            "repository": self._optional_str(registry_entry.get("repository")) or repository,
            "license": self._optional_str(registry_entry.get("license")),
        }

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def _resource_counts(self, install_path: Path) -> ClaudePluginResourceCounts:
        resources = self._resource_lists(install_path, include_metadata=False)
        return ClaudePluginResourceCounts(
            commands=len(resources["commands"]),
            agents=len(resources["agents"]),
            hooks=len(resources["hooks"]),
            mcpServers=len(resources["mcpServers"]),
            skills=len(resources["skills"]),
            lspServers=len(resources["lspServers"]),
        )

    def _resource_lists(self, install_path: Path, *, include_metadata: bool) -> dict[str, list[dict[str, Any]]]:
        return {
            "commands": self._markdown_resources(install_path / "commands", include_metadata=include_metadata),
            "agents": self._markdown_resources(install_path / "agents", include_metadata=include_metadata),
            "hooks": self._hooks_resources(install_path / "hooks" / "hooks.json"),
            "mcpServers": self._mcp_resources(install_path / ".mcp.json"),
            "skills": self._skill_resources(install_path / "skills", include_metadata=include_metadata),
            "lspServers": [],
        }

    def _markdown_resources(self, directory: Path, *, include_metadata: bool) -> list[dict[str, Any]]:
        if not directory.is_dir():
            return []
        return [
            self._markdown_resource(path, directory, include_metadata=include_metadata)
            for path in sorted(directory.rglob("*.md"))
            if path.is_file()
        ]

    def _skill_resources(self, directory: Path, *, include_metadata: bool) -> list[dict[str, Any]]:
        if not directory.is_dir():
            return []
        skill_files = sorted(path for path in directory.glob("*/SKILL.md") if path.is_file())
        if not skill_files:
            skill_files = sorted(path for path in directory.rglob("SKILL.md") if path.is_file())
        return [
            self._markdown_resource(path, directory, include_metadata=include_metadata)
            for path in skill_files
        ]

    def _markdown_resource(self, path: Path, root: Path, *, include_metadata: bool) -> dict[str, Any]:
        resource: dict[str, Any] = {
            "name": path.parent.name if path.name == "SKILL.md" else path.stem,
            "path": str(path.relative_to(root.parent if path.name == "SKILL.md" else root)),
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

    def _hooks_resources(self, path: Path) -> list[dict[str, Any]]:
        data = self._read_json(path)
        hooks = data.get("hooks") if isinstance(data, dict) else None
        if isinstance(hooks, dict):
            return [
                {"name": str(name), "config": config if isinstance(config, dict) else {"value": config}}
                for name, config in hooks.items()
            ]
        if isinstance(hooks, list):
            return [item if isinstance(item, dict) else {"name": str(item)} for item in hooks]
        return []

    def _mcp_resources(self, path: Path) -> list[dict[str, Any]]:
        data = self._read_json(path)
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            return [
                {"name": str(name), "config": config if isinstance(config, dict) else {"value": config}}
                for name, config in servers.items()
            ]
        return []

    def _dependencies(self, registry_entry: dict[str, Any], own_marketplace: str | None) -> list[ClaudePluginDependency]:
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
                        marketplace=self._optional_str(item.get("marketplace")) or own_marketplace,
                    ),
                )
        return result

    @staticmethod
    def _marketplace_summary(row: dict[str, Any], counts: dict[str, int]) -> ClaudePluginMarketplaceSummary:
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
            return source
        if isinstance(source, dict):
            return (
                ClaudePluginsService._optional_str(source.get("source"))
                or ClaudePluginsService._optional_str(source.get("repo"))
                or ClaudePluginsService._optional_str(source.get("url"))
            )
        return None

    def _marketplace_plugin_entry(self, workspace_id: str, plugin_id: str) -> dict[str, Any]:
        plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)
        marketplace_path = self._marketplace_registry_path(workspace_id, marketplace_name)
        data = self._read_json(marketplace_path)
        plugins = data.get("plugins") if isinstance(data, dict) else None
        if isinstance(plugins, list):
            for item in plugins:
                if isinstance(item, dict) and item.get("name") == plugin_name:
                    return item
        return {"name": plugin_name}

    def _resource_root(
        self,
        workspace_id: str,
        plugin_id: str,
        registry_entry: dict[str, Any],
        install_path: Path,
    ) -> Path:
        _plugin_name, marketplace_name = self._parse_plugin_id(plugin_id)
        if not marketplace_name:
            return install_path
        source = registry_entry.get("source")
        if not isinstance(source, str) or not source:
            return install_path
        marketplace_root = self._marketplace_root(workspace_id, marketplace_name)
        try:
            root = marketplace_root.resolve(strict=False)
            candidate = (marketplace_root / source).resolve(strict=False)
            candidate.relative_to(root)
        except (OSError, ValueError):
            return install_path
        return candidate if candidate.is_dir() else install_path

    def _marketplace_root(self, workspace_id: str, marketplace_name: str) -> Path:
        return resolve_scope_root(workspace_id, DocumentScope.USER) / "plugins" / "marketplaces" / marketplace_name

    def _marketplace_registry_path(self, workspace_id: str, marketplace_name: str) -> Path:
        return self._marketplace_root(workspace_id, marketplace_name) / ".claude-plugin" / "marketplace.json"

    @staticmethod
    def _parse_plugin_id(plugin_id: str) -> tuple[str, str]:
        if "@" not in plugin_id:
            return plugin_id, ""
        plugin_name, marketplace_name = plugin_id.split("@", 1)
        return plugin_name, marketplace_name

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

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
            trimmed_value = value.strip().strip('"\'')
            if trimmed_key:
                result[trimmed_key] = trimmed_value
        return result

    def _list_signature(self, workspace_id: str) -> tuple[Any, ...]:
        user_root = resolve_scope_root(workspace_id, DocumentScope.USER)
        paths = [
            user_root / "plugins" / "installed_plugins.json",
            user_root / "plugins" / "known_marketplaces.json",
            self._settings_file(workspace_id, "user"),
            self._settings_file(workspace_id, "project"),
            self._settings_file(workspace_id, "local"),
        ]
        marketplace_root = user_root / "plugins" / "marketplaces"
        paths.extend(sorted(marketplace_root.glob("*/.claude-plugin/marketplace.json")) if marketplace_root.exists() else [])
        resource_roots = sorted(
            {self._resource_signature_path(path) for path in self._installed_resource_roots(workspace_id)},
            key=str,
        )
        return (
            tuple(self._file_signature(path) for path in paths),
            tuple(self._tree_signature(path) for path in resource_roots),
        )

    def _installed_resource_roots(self, workspace_id: str) -> list[Path]:
        user_root = resolve_scope_root(workspace_id, DocumentScope.USER)
        data = self._read_json(user_root / "plugins" / "installed_plugins.json")
        plugins = data.get("plugins") if isinstance(data, dict) else None
        if not isinstance(plugins, dict):
            return []
        roots: list[Path] = []
        for plugin_id, raw_installations in plugins.items():
            if not isinstance(plugin_id, str):
                continue
            rows = raw_installations if isinstance(raw_installations, list) else []
            rows = [row for row in rows if isinstance(row, dict)]
            if not rows:
                continue
            selected = self._selected_installation_row(rows)
            install_path = Path(str(selected.get("installPath") or selected.get("path") or ""))
            marketplace_entry = self._marketplace_plugin_entry(workspace_id, plugin_id)
            roots.append(self._resource_root(workspace_id, plugin_id, marketplace_entry, install_path))
        return roots

    @staticmethod
    def _resource_signature_path(path: Path) -> Path:
        try:
            return path.resolve(strict=False)
        except OSError:
            return path

    @staticmethod
    def _file_signature(path: Path) -> tuple[str, int | None, int | None]:
        try:
            stat = path.stat()
            return (str(path), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return (str(path), None, None)

    def _tree_signature(self, path: Path) -> tuple[Any, ...]:
        if not path.exists():
            return (str(path), None)
        return (
            str(path),
            tuple(
                self._file_signature(child)
                for child in sorted(path.rglob("*"))
                if child.is_file() and self._is_resource_signature_file(path, child)
            ),
        )

    @staticmethod
    def _is_resource_signature_file(root: Path, path: Path) -> bool:
        try:
            relative = path.relative_to(root)
        except ValueError:
            return False
        parts = relative.parts
        if parts == ("README.md",) or parts == (".mcp.json",):
            return True
        if parts == ("hooks", "hooks.json"):
            return True
        if len(parts) >= 2 and parts[0] in {"commands", "agents"} and path.suffix == ".md":
            return True
        return len(parts) >= 3 and parts[0] == "skills" and path.name == "SKILL.md"

    @staticmethod
    def _clear_list_cache(workspace_id: str | None = None) -> None:
        with _list_cache_guard:
            if workspace_id is None:
                _list_cache.clear()
            else:
                _list_cache.pop(workspace_id, None)

    @staticmethod
    def _settings_file(workspace_id: str, scope: ClaudePluginScope) -> Path:
        if scope == "user":
            return resolve_scope_root(workspace_id, DocumentScope.USER) / "settings.json"
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
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_SETTINGS_JSON", "message": str(path)}) from exc
        if not isinstance(data, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail={"error": "INVALID_SETTINGS_JSON", "message": str(path)})
        return data

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)


def get_claude_plugins_service() -> ClaudePluginsService:
    """Return Claude plugin service dependency."""

    return ClaudePluginsService()
