"""Canonical installed-root Codex plugin resource resolver."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from aileron_marketplace_core import (
    read_plugin_resource_owner,
    resolve_codex_plugin_resources,
)

from app.modules.cli_settings.cache import ProcessTTLCache
from app.modules.cli_settings.user_scope.paths import CodexPathResolver

CLI_TIMEOUT_SECONDS = 10
DEFAULT_PLUGIN_VERSION = "local"
PLUGIN_CACHE_RELATIVE_PATH = Path("plugins") / "cache"


_provider_cli_cache: ProcessTTLCache[
    tuple[str, str, tuple[str, ...], float],
    subprocess.CompletedProcess[str],
] = ProcessTTLCache()
_packages_cache: ProcessTTLCache[
    tuple[str, str],
    tuple["CodexPluginPackage", ...],
] = ProcessTTLCache()
_resources_cache: ProcessTTLCache[str, Any] = ProcessTTLCache()


@dataclass(frozen=True)
class CodexPluginPackage:
    """One package root reported by ``codex plugin list --json``."""

    plugin_id: str
    name: str
    marketplace_name: str
    package_root: Path
    manifest_path: Path
    manifest: dict[str, Any]
    enabled: bool = True


@dataclass(frozen=True)
class CodexPluginSkill:
    """Skill bundled in an installed Codex plugin."""

    plugin: CodexPluginPackage
    name: str
    relative_path: str
    path: Path
    relative_source_path: str | None = None


@dataclass(frozen=True)
class CodexPluginMcpServer:
    """MCP definition bundled in an installed Codex plugin."""

    plugin: CodexPluginPackage
    name: str
    config: dict[str, Any]
    relative_source_path: str = ""


@dataclass(frozen=True)
class CodexPluginHookDocument:
    """Hook document bundled in an installed Codex plugin."""

    plugin: CodexPluginPackage
    source_path: Path
    content: dict[str, Any]
    relative_source_path: str = ""


@dataclass(frozen=True)
class CodexPluginAppResource:
    """App or connector definition bundled in an installed Codex plugin."""

    plugin: CodexPluginPackage
    name: str
    config: dict[str, Any]
    relative_source_path: str


class CodexPluginResourceResolver:
    """Resolve Codex resources only from provider-reported installed roots."""

    def __init__(
        self,
        resolver: CodexPathResolver,
        inventory_loader: Callable[[], Iterable[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._resolver = resolver
        self._inventory_loader = inventory_loader
        self._packages_snapshot: tuple[CodexPluginPackage, ...] | None = None
        self._resources_by_root: dict[Path, Any] = {}

    def start_request_snapshot(self) -> None:
        """Start one fresh provider snapshot for the current Runtime request."""

        self._packages_snapshot = None
        self._resources_by_root.clear()

    def packages(
        self,
        enabled_plugin_ids: set[str] | None = None,
    ) -> list[CodexPluginPackage]:
        packages = list(self._request_packages())
        if enabled_plugin_ids is None:
            return packages
        return [
            package for package in packages if package.plugin_id in enabled_plugin_ids
        ]

    def clear_cache(self) -> None:
        """Clear the current request-scoped provider snapshot."""

        self._packages_snapshot = None
        self._resources_by_root.clear()

    def skills(
        self,
        enabled_plugin_ids: set[str] | None = None,
    ) -> list[CodexPluginSkill]:
        skills: list[CodexPluginSkill] = []
        for package in self.packages(enabled_plugin_ids):
            resources = self._resources(package)
            for resource in resources.file_resources:
                if resource.resource_type != "skill":
                    continue
                source = package.package_root / resource.source_locator
                root = package.package_root / resource.resource_root_locator
                skills.append(
                    CodexPluginSkill(
                        plugin=package,
                        name=root.name,
                        relative_path=self._skill_relative_path(
                            package,
                            resource.source_locator,
                        ),
                        path=source,
                        relative_source_path=resource.source_locator,
                    )
                )
        return sorted(
            skills,
            key=lambda item: (
                item.plugin.plugin_id,
                item.relative_source_path or item.relative_path,
            ),
        )

    def mcp_servers(
        self,
        enabled_plugin_ids: set[str] | None = None,
    ) -> list[CodexPluginMcpServer]:
        servers: list[CodexPluginMcpServer] = []
        for package in self.packages(enabled_plugin_ids):
            resources = self._resources(package)
            for name, owner in sorted(resources.mcp_servers.items()):
                value = read_plugin_resource_owner(package.package_root, owner)
                if not isinstance(value, dict):
                    raise ValueError("Installed Codex MCP definition is not an object")
                servers.append(
                    CodexPluginMcpServer(
                        plugin=package,
                        name=name,
                        config=dict(value),
                        relative_source_path=owner.file_path,
                    )
                )
        return servers

    def hook_documents(
        self,
        enabled_plugin_ids: set[str] | None = None,
    ) -> list[CodexPluginHookDocument]:
        documents: list[CodexPluginHookDocument] = []
        for package in self.packages(enabled_plugin_ids):
            resources = self._resources(package)
            for owner in resources.hook_sources:
                value = read_plugin_resource_owner(package.package_root, owner)
                if not isinstance(value, dict):
                    raise ValueError("Installed Codex hooks definition is not an object")
                documents.append(
                    CodexPluginHookDocument(
                        plugin=package,
                        source_path=package.package_root / owner.file_path,
                        content=dict(value),
                        relative_source_path=owner.file_path,
                    )
                )
        return documents

    def apps(
        self,
        enabled_plugin_ids: set[str] | None = None,
    ) -> list[CodexPluginAppResource]:
        apps: list[CodexPluginAppResource] = []
        for package in self.packages(enabled_plugin_ids):
            resources = self._resources(package)
            for resource in resources.file_resources:
                if resource.resource_type != "app":
                    continue
                source = package.package_root / resource.source_locator
                try:
                    value = json.loads(source.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        "Installed Codex app definition is invalid"
                    ) from exc
                if not isinstance(value, dict):
                    raise ValueError("Installed Codex app definition is not an object")
                apps.append(
                    CodexPluginAppResource(
                        plugin=package,
                        name=resource.resource_id,
                        config=dict(value),
                        relative_source_path=resource.source_locator,
                    )
                )
        return sorted(
            apps,
            key=lambda item: (
                item.plugin.plugin_id,
                item.relative_source_path,
                item.name,
            ),
        )

    def find_skill(
        self,
        plugin_id: str | None,
        relative_path: str,
        enabled_plugin_ids: set[str] | None = None,
    ) -> CodexPluginSkill | None:
        for skill in self.skills(enabled_plugin_ids):
            if plugin_id is not None and skill.plugin.plugin_id != plugin_id:
                continue
            if relative_path in {
                skill.relative_path,
                skill.relative_source_path,
            }:
                return skill
        return None

    def _request_packages(self) -> tuple[CodexPluginPackage, ...]:
        if self._packages_snapshot is None:
            inventory_loader = self._inventory_loader or self._plugin_rows
            key = (
                str(self._resolver.codex_home),
                str(self._resolver.workspace_root),
            )
            self._packages_snapshot = _packages_cache.get_or_load(
                key,
                lambda: self._packages_from_provider_rows(inventory_loader()),
            )
        return self._packages_snapshot

    def _packages_from_provider_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[CodexPluginPackage, ...]:
        packages: dict[str, CodexPluginPackage] = {}
        for row in rows:
            package = self._package_from_provider_row(row)
            existing = packages.get(package.plugin_id)
            if existing is not None:
                raise ValueError("Codex plugin inventory contains duplicate plugin IDs")
            packages[package.plugin_id] = package
        return tuple(packages[key] for key in sorted(packages))

    def _package_from_provider_row(
        self,
        row: Mapping[str, Any],
    ) -> CodexPluginPackage:
        plugin_id = self._required_string(row, "pluginId")
        name = self._required_string(row, "name")
        marketplace_name = self._required_string(row, "marketplaceName")
        version = self._required_string(row, "version")
        self._validate_plugin_segment(name, "plugin name")
        self._validate_plugin_segment(marketplace_name, "marketplace name")
        self._validate_plugin_version_segment(version)
        if plugin_id != f"{name}@{marketplace_name}":
            raise ValueError("Codex plugin inventory identity is inconsistent")
        if row.get("installed") is not True:
            raise ValueError("Codex installed plugin row must be installed")
        row_enabled = row.get("enabled")
        if not isinstance(row_enabled, bool):
            raise ValueError("Codex installed plugin enabled state must be boolean")
        if not isinstance(row.get("source"), Mapping):
            raise ValueError("Codex installed plugin source must be an object")

        package_root = self._installed_root(
            marketplace_name=marketplace_name,
            name=name,
            version=version,
        )
        try:
            manifest_path = (package_root / ".codex-plugin" / "plugin.json").resolve(
                strict=True
            )
            manifest_path.relative_to(package_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("Installed Codex plugin manifest path is invalid") from exc
        if not manifest_path.is_file():
            raise ValueError("Installed Codex plugin manifest is not a file")
        manifest = self._read_json_object(manifest_path)
        if manifest.get("name") != name:
            raise ValueError("Installed Codex plugin manifest identity does not match")
        manifest_version = manifest.get("version")
        if manifest_version is None:
            normalized_manifest_version = DEFAULT_PLUGIN_VERSION
        elif isinstance(manifest_version, str) and manifest_version.strip():
            normalized_manifest_version = manifest_version.strip()
        else:
            raise ValueError("Installed Codex plugin manifest version is invalid")
        if normalized_manifest_version != version:
            raise ValueError("Installed Codex plugin manifest version does not match")
        return CodexPluginPackage(
            plugin_id=plugin_id,
            name=name,
            marketplace_name=marketplace_name,
            package_root=package_root,
            manifest_path=manifest_path,
            manifest=manifest,
            enabled=row_enabled,
        )

    def _plugin_rows(self) -> list[dict[str, Any]]:
        try:
            completed = run_codex_plugin_cli(
                ["plugin", "list", "--json"],
                codex_home=self._resolver.codex_home,
                cwd=self._resolver.workspace_root,
                timeout=CLI_TIMEOUT_SECONDS,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Codex plugin inventory is unavailable") from exc
        if completed.returncode != 0:
            raise RuntimeError("Codex plugin inventory failed")
        try:
            payload = json.loads(completed.stdout or "null")
        except json.JSONDecodeError as exc:
            raise ValueError("Codex plugin inventory returned invalid JSON") from exc
        return self._provider_rows(payload)

    @staticmethod
    def _provider_rows(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise ValueError("Codex plugin inventory must be an object")
        rows = payload.get("installed")
        if not isinstance(rows, list) or any(
            not isinstance(item, dict) for item in rows
        ):
            raise ValueError(
                "Codex plugin inventory must contain an installed object list"
            )
        return list(rows)

    def _installed_root(
        self,
        *,
        marketplace_name: str,
        name: str,
        version: str,
    ) -> Path:
        cache_root_path = self._resolver.codex_home / PLUGIN_CACHE_RELATIVE_PATH
        candidate = cache_root_path / marketplace_name / name / version
        try:
            codex_home = self._resolver.codex_home.resolve(strict=True)
            cache_root = cache_root_path.resolve(strict=True)
            cache_root.relative_to(codex_home)
            root = candidate.resolve(strict=True)
            relative_root = root.relative_to(cache_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError("Installed Codex plugin cache root is invalid") from exc
        if relative_root != Path(marketplace_name) / name / version:
            raise ValueError("Installed Codex plugin cache root is inconsistent")
        if not root.is_dir():
            raise ValueError("Installed Codex plugin cache root is not a directory")
        return root

    @staticmethod
    def _read_json_object(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Installed Codex plugin manifest is invalid") from exc
        if not isinstance(value, dict):
            raise ValueError("Installed Codex plugin manifest is not an object")
        return value

    @staticmethod
    def _required_string(
        value: Mapping[str, Any],
        key: str,
    ) -> str:
        candidate = value.get(key)
        if not isinstance(candidate, str) or not candidate:
            raise ValueError(f"Codex installed plugin {key} must be a string")
        return candidate

    @staticmethod
    def _validate_plugin_segment(segment: str, kind: str) -> None:
        if not all(
            character.isascii() and (character.isalnum() or character in {"-", "_"})
            for character in segment
        ):
            raise ValueError(f"Invalid Codex {kind} segment")

    @staticmethod
    def _validate_plugin_version_segment(version: str) -> None:
        if version in {".", ".."} or not all(
            character.isascii()
            and (character.isalnum() or character in {"-", "_", ".", "+"})
            for character in version
        ):
            raise ValueError("Invalid Codex plugin version segment")

    @staticmethod
    def _skill_relative_path(
        package: CodexPluginPackage,
        source_locator: str,
    ) -> str:
        source = Path(source_locator)
        try:
            return source.relative_to("skills").as_posix()
        except ValueError:
            return source.name

    def _resources(self, package: CodexPluginPackage) -> Any:
        cached = self._resources_by_root.get(package.package_root)
        if cached is not None:
            return cached
        cache_key = str(package.package_root)

        def load_resources() -> Any:
            resources = resolve_codex_plugin_resources(package.package_root)
            if resources.diagnostics:
                detail = ",".join(
                    f"{item.code}:{item.source_locator}"
                    for item in resources.diagnostics
                )
                raise ValueError(f"Invalid installed Codex plugin resources: {detail}")
            return resources

        resources = _resources_cache.get_or_load(cache_key, load_resources)
        self._resources_by_root[package.package_root] = resources
        return resources


def run_codex_plugin_cli(
    args: Sequence[str],
    *,
    codex_home: Path,
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    """Cache one completed Codex plugin discovery result for five minutes."""

    key = (str(codex_home), str(cwd), tuple(args), timeout)
    return _provider_cli_cache.get_or_load(
        key,
        lambda: subprocess.run(
            ["codex", *args],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        ),
        cache_if=lambda completed: completed.returncode == 0,
    )


def clear_codex_plugin_inventory_cache(
    *,
    codex_home: Path | None = None,
    cwd: Path | None = None,
) -> None:
    """Clear completed provider, package, and resource discovery results."""

    if codex_home is None and cwd is None:
        _provider_cli_cache.clear()
        _packages_cache.clear()
        _resources_cache.clear()
        return
    home_identity = str(codex_home) if codex_home is not None else None
    cwd_identity = str(cwd) if cwd is not None else None
    _provider_cli_cache.clear(
        lambda key: (home_identity is None or key[0] == home_identity)
        and (cwd_identity is None or key[1] == cwd_identity)
    )
    _packages_cache.clear(
        lambda key: (home_identity is None or key[0] == home_identity)
        and (cwd_identity is None or key[1] == cwd_identity)
    )
    # Resource roots do not carry a stable reverse index, so provider refresh
    # clears this small bounded cache.
    _resources_cache.clear()
