"""Codex plugin package resource discovery."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import threading

from app.modules.cli_settings.codex_paths import CodexPathResolver


@dataclass(frozen=True)
class CodexPluginPackage:
    """Installed Codex plugin package."""

    plugin_id: str
    name: str
    marketplace_name: str | None
    package_root: Path
    manifest_path: Path
    manifest: dict[str, Any]


@dataclass(frozen=True)
class CodexPluginSkill:
    """Skill file bundled in a Codex plugin."""

    plugin: CodexPluginPackage
    name: str
    relative_path: str
    path: Path


@dataclass(frozen=True)
class CodexPluginMcpServer:
    """MCP server bundled in a Codex plugin."""

    plugin: CodexPluginPackage
    name: str
    config: dict[str, Any]


@dataclass(frozen=True)
class CodexPluginHookDocument:
    """Hook document bundled in a Codex plugin."""

    plugin: CodexPluginPackage
    source_path: Path
    content: dict[str, Any]


@dataclass(frozen=True)
class _PluginPackageCacheEntry:
    key: tuple[Any, ...]
    packages: tuple[CodexPluginPackage, ...]


_package_cache: dict[tuple[str, str], _PluginPackageCacheEntry] = {}
_package_cache_lock = threading.Lock()


class CodexPluginResourceResolver:
    """Resolve official Codex plugin resources relative to package roots."""

    def __init__(self, resolver: CodexPathResolver) -> None:
        self._resolver = resolver

    def packages(self, enabled_plugin_ids: set[str] | None = None) -> list[CodexPluginPackage]:
        packages = list(self._cached_packages())
        if enabled_plugin_ids is None:
            return packages
        return [package for package in packages if package.plugin_id in enabled_plugin_ids]

    def clear_cache(self) -> None:
        """Clear cached package discovery for this resolver root."""

        with _package_cache_lock:
            _package_cache.pop(self._cache_namespace(), None)

    def skills(self, enabled_plugin_ids: set[str] | None = None) -> list[CodexPluginSkill]:
        skills: list[CodexPluginSkill] = []
        for package in self.packages(enabled_plugin_ids):
            for skill_md in self._skill_files(package):
                skills.append(
                    CodexPluginSkill(
                        plugin=package,
                        name=skill_md.parent.name,
                        relative_path=str(skill_md.relative_to(self._skill_base_dir(package, skill_md))),
                        path=skill_md,
                    ),
                )
        return sorted(skills, key=lambda item: (item.plugin.plugin_id, item.relative_path))

    def mcp_servers(self, enabled_plugin_ids: set[str] | None = None) -> list[CodexPluginMcpServer]:
        servers: list[CodexPluginMcpServer] = []
        for package in self.packages(enabled_plugin_ids):
            for name, config in sorted(self._mcp_server_map(package).items()):
                if isinstance(name, str) and isinstance(config, dict):
                    servers.append(CodexPluginMcpServer(plugin=package, name=name, config=dict(config)))
        return servers

    def hook_documents(self, enabled_plugin_ids: set[str] | None = None) -> list[CodexPluginHookDocument]:
        documents: list[CodexPluginHookDocument] = []
        for package in self.packages(enabled_plugin_ids):
            source_path, content = self._hook_document(package)
            if source_path is not None and content:
                documents.append(CodexPluginHookDocument(plugin=package, source_path=source_path, content=content))
        return documents

    def bundled_summary(self, package: CodexPluginPackage) -> dict[str, Any]:
        return {
            "skills": self._skill_summary(package),
            "mcpServers": self._mcp_server_map(package),
            "apps": package.manifest.get("apps") if isinstance(package.manifest.get("apps"), dict) else {},
            "hooks": self._hook_document(package)[1],
        }

    def find_skill(
        self,
        plugin_id: str | None,
        relative_path: str,
        enabled_plugin_ids: set[str] | None = None,
    ) -> CodexPluginSkill | None:
        for skill in self.skills(enabled_plugin_ids):
            if plugin_id is not None and skill.plugin.plugin_id != plugin_id:
                continue
            if skill.relative_path == relative_path:
                return skill
        return None

    def _manifest_paths(self) -> list[Path]:
        roots = [
            self._resolver.codex_home / "plugins" / "cache",
            self._resolver.codex_home / ".tmp" / "plugins" / "plugins",
            *sorted((self._resolver.codex_home / ".tmp").glob("plugins-clone-*/plugins")),
        ]
        paths: list[Path] = []
        for root in roots:
            if root.is_dir():
                paths.extend(sorted(root.glob("**/.codex-plugin/plugin.json")))
        return paths

    def _cached_packages(self) -> tuple[CodexPluginPackage, ...]:
        namespace = self._cache_namespace()
        key = self._cache_key()
        with _package_cache_lock:
            entry = _package_cache.get(namespace)
            if entry is not None and entry.key == key:
                return entry.packages

        packages: list[CodexPluginPackage] = []
        for manifest_path in self._manifest_paths():
            manifest = self._read_json_file(manifest_path)
            if not manifest:
                continue
            packages.append(self._package_from_manifest(manifest_path, manifest))

        cached = _PluginPackageCacheEntry(key=key, packages=tuple(packages))
        with _package_cache_lock:
            _package_cache[namespace] = cached
        return cached.packages

    def _cache_namespace(self) -> tuple[str, str]:
        return (str(self._resolver.codex_home), str(self._resolver.workspace_root))

    def _cache_key(self) -> tuple[Any, ...]:
        roots = [
            self._resolver.codex_home / "plugins" / "cache",
            self._resolver.codex_home / ".tmp" / "plugins" / "plugins",
            self._resolver.codex_home / ".tmp",
        ]
        return tuple((str(root), self._path_mtime_ns(root)) for root in roots)

    @staticmethod
    def _path_mtime_ns(path: Path) -> int | None:
        try:
            return path.stat().st_mtime_ns
        except OSError:
            return None

    def _package_from_manifest(self, manifest_path: Path, manifest: dict[str, Any]) -> CodexPluginPackage:
        package_root = manifest_path.parent.parent
        raw_id = manifest.get("id") or manifest.get("name") or package_root.name
        plugin_id = str(raw_id)
        marketplace_name = manifest.get("marketplace") if isinstance(manifest.get("marketplace"), str) else None
        if "@" not in plugin_id and marketplace_name:
            plugin_id = f"{plugin_id}@{marketplace_name}"
        if "@" not in plugin_id:
            inferred_marketplace = self._marketplace_from_cache_path(manifest_path)
            if not inferred_marketplace:
                inferred_marketplace = self._marketplace_from_tmp_clone_path(manifest_path)
            if inferred_marketplace:
                marketplace_name = inferred_marketplace
                plugin_id = f"{plugin_id}@{inferred_marketplace}"
        if marketplace_name is None and "@" in plugin_id:
            marketplace_name = plugin_id.split("@", 1)[1]
        return CodexPluginPackage(
            plugin_id=plugin_id,
            name=str(manifest.get("name") or manifest.get("id") or plugin_id.split("@", 1)[0]),
            marketplace_name=marketplace_name,
            package_root=package_root,
            manifest_path=manifest_path,
            manifest=manifest,
        )

    def _marketplace_from_cache_path(self, manifest_path: Path) -> str | None:
        try:
            relative = manifest_path.relative_to(self._resolver.codex_home / "plugins" / "cache")
        except ValueError:
            return None
        return relative.parts[0] if relative.parts else None

    def _marketplace_from_tmp_clone_path(self, manifest_path: Path) -> str | None:
        for parent in manifest_path.parents:
            if not parent.name.startswith("plugins-clone-"):
                continue
            marketplace_path = parent / ".agents" / "plugins" / "marketplace.json"
            marketplace = self._read_json_file(marketplace_path)
            name = marketplace.get("name")
            return name if isinstance(name, str) and name else None
        return None

    def _skills_for_package(self, package: CodexPluginPackage) -> list[CodexPluginSkill]:
        return [
            skill
            for skill in self.skills()
            if skill.plugin.manifest_path == package.manifest_path
        ]

    def _skill_summary(self, package: CodexPluginPackage) -> list[str]:
        skills = [skill.name for skill in self._skills_for_package(package)]
        if skills:
            return skills
        value = package.manifest.get("skills")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        if isinstance(value, str):
            return [value]
        return []

    def _skill_files(self, package: CodexPluginPackage) -> list[Path]:
        value = package.manifest.get("skills")
        if isinstance(value, str):
            directory = self._resolve_relative(package.package_root, value)
            return self._skill_files_from_dir(directory)
        if isinstance(value, list):
            files: list[Path] = []
            for item in value:
                if not isinstance(item, str):
                    continue
                resolved = self._resolve_relative(package.package_root, item)
                if resolved is None:
                    resolved = self._resolve_relative(package.package_root, f"skills/{item}")
                if resolved is None:
                    continue
                if resolved.is_file() and resolved.name == "SKILL.md":
                    files.append(resolved)
                elif resolved.is_dir():
                    skill_md = resolved / "SKILL.md"
                    if skill_md.is_file():
                        files.append(skill_md)
            return sorted(set(files))
        return self._skill_files_from_dir(package.package_root / "skills")

    @staticmethod
    def _skill_base_dir(package: CodexPluginPackage, skill_md: Path) -> Path:
        skills_dir = package.package_root / "skills"
        try:
            skill_md.relative_to(skills_dir)
        except ValueError:
            return skill_md.parent
        return skills_dir

    @staticmethod
    def _skill_files_from_dir(directory: Path | None) -> list[Path]:
        if directory is None or not directory.is_dir():
            return []
        return sorted(path for path in directory.glob("*/SKILL.md") if path.is_file())

    def _mcp_server_map(self, package: CodexPluginPackage) -> dict[str, Any]:
        value = package.manifest.get("mcpServers")
        if value is None:
            value = package.manifest.get("mcp_servers")
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            return self._mcp_server_map_from_file(self._resolve_relative(package.package_root, value))
        default_file = package.package_root / ".mcp.json"
        return self._mcp_server_map_from_file(default_file)

    def _mcp_server_map_from_file(self, path: Path | None) -> dict[str, Any]:
        if path is None or not path.is_file():
            return {}
        data = self._read_json_file(path)
        servers = data.get("mcpServers")
        return dict(servers) if isinstance(servers, dict) else {}

    def _hook_document(self, package: CodexPluginPackage) -> tuple[Path | None, dict[str, Any]]:
        value = package.manifest.get("hooks")
        if isinstance(value, dict):
            return package.manifest_path, dict(value)
        if isinstance(value, str):
            path = self._resolve_relative(package.package_root, value)
            return path, self._read_json_file(path) if path is not None else {}
        default_file = package.package_root / "hooks" / "hooks.json"
        if default_file.is_file():
            return default_file, self._read_json_file(default_file)
        return None, {}

    @staticmethod
    def _resolve_relative(root: Path, value: str) -> Path | None:
        clean_path = Path(value)
        if clean_path.is_absolute() or ".." in clean_path.parts:
            return None
        return root / clean_path

    @staticmethod
    def _read_json_file(path: Path | None) -> dict[str, Any]:
        if path is None or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
