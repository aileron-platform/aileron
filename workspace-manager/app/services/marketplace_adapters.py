"""Marketplace provider adapters."""

from __future__ import annotations

import json
import re
import tomllib
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

from app.models.marketplace import (
    MarketplaceCliPreflightResult,
    MarketplaceInstallCommandPlan,
    MarketplacePackageCreateRequest,
    MarketplacePackageSummary,
    MarketplaceProvider,
)


class MarketplaceProviderAdapter(Protocol):
    """Provider adapter contract for native Marketplace package operations."""

    provider: MarketplaceProvider

    def ensure_roots(self, registry_root: Path) -> None:
        """Ensure provider root directories exist."""

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        """Return package path under provider root."""

    def manifest_path(self, package_path: Path) -> Path:
        """Return package manifest path."""

    def scan_registry(self, registry_root: Path) -> list[MarketplacePackageSummary]:
        """Scan provider registry files."""

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        """Scan an external source for import candidates."""

    def create_package(self, package_path: Path, request: MarketplacePackageCreateRequest) -> None:
        """Create provider-native package scaffold."""

    def validate_package(self, package_path: Path, package_id: str | None = None) -> list[dict[str, Any]]:
        """Validate provider-native package files."""

    def validate_catalog_metadata(
        self,
        catalog_entry: dict[str, Any] | None,
        package_manifest: dict[str, Any],
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Validate catalog metadata against package manifest metadata."""

    def read_listing_entry(self, registry_root: Path, package_id: str) -> dict[str, Any] | None:
        """Read a single package listing projection from a root marketplace manifest."""

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        """Build a target listing entry for an imported package."""

    def upsert_listing_entry(self, registry_root: Path, package_id: str, entry: dict[str, Any]) -> None:
        """Upsert package listing entry when provider uses a root marketplace manifest."""

    def remove_listing_entry(self, registry_root: Path, package_id: str) -> None:
        """Remove package listing entry when provider uses a root marketplace manifest."""

    def is_remote_source_value(self, value: str) -> bool:
        """Return whether a source value points outside the scanned checkout."""

    def editor_tabs(self, package_path: Path) -> list[dict[str, Any]]:
        """Return provider-native editor tab descriptors."""

    def export_package(self, package_path: Path) -> bytes:
        """Export provider-native package archive."""

    def build_install_command(
        self,
        package_path: Path,
        workspace_id: str,
        preflight: MarketplaceCliPreflightResult,
    ) -> MarketplaceInstallCommandPlan:
        """Build provider-native install command plan."""

    def summarize_detail(self, package_path: Path) -> dict[str, Any]:
        """Summarize provider-native package detail metadata."""


class BaseMarketplaceProviderAdapter:
    """Shared provider adapter helpers."""

    provider: MarketplaceProvider
    package_type = "plugin"
    manifest_required_fields: tuple[str, ...] = ("name",)
    package_id_pattern = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")

    def read_json(self, path: Path) -> dict[str, Any]:
        data, _ = self.read_json_with_error(path)
        return data

    def read_json_with_error(self, path: Path) -> tuple[dict[str, Any], str | None]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            return {}, "missing"
        except json.JSONDecodeError:
            return {}, "invalid"
        if not isinstance(data, dict):
            return {}, "invalid"
        return data, None

    def atomic_write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def string_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

    def first_string(self, *values: Any) -> str | None:
        for value in values:
            string_value = self.string_or_none(value)
            if string_value:
                return string_value
        return None

    def first_string_list(self, *values: Any) -> list[str]:
        for value in values:
            items = self.string_list(value)
            if items:
                return items
        return []

    def source_type_from_metadata(self, *items: dict[str, Any]) -> str:
        for item in items:
            value = item.get("sourceType") or item.get("source_type")
            if value in {"created", "imported", "cloned"}:
                return str(value)
        for item in items:
            if isinstance(item.get("importSource"), dict) or isinstance(item.get("import_source"), dict):
                return "imported"
            if isinstance(item.get("clonedFrom"), dict) or isinstance(item.get("cloned_from"), dict):
                return "cloned"
        return "created"

    def highest_severity(self, results: list[dict[str, Any]]) -> str:
        order = {"none": 0, "info": 1, "warning": 2, "error": 3}
        highest = "none"
        for result in results:
            severity = str(result.get("severity") or "none")
            if order.get(severity, 0) > order[highest]:
                highest = severity
        return highest

    def is_remote_source_value(self, value: str) -> bool:
        normalized = value.strip().lower()
        if not normalized:
            return False
        remote_prefixes = ("http://", "https://", "ssh://", "git://")
        return (
            normalized.startswith(remote_prefixes)
            or normalized.startswith("git@")
            or normalized.startswith("github:")
            or normalized.startswith("github.com/")
            or normalized.endswith(".git")
        )

    def remote_source_metadata(
        self,
        *,
        source_type: str,
        url: str,
        path: str | None = None,
        ref: str | None = None,
        sha: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "kind": "git",
            "sourceType": source_type,
            "url": url,
        }
        if path:
            metadata["path"] = path
        if ref:
            metadata["ref"] = ref
        if sha:
            metadata["sha"] = sha
        return metadata

    def remote_source_path(self, url: str, path: str | None = None) -> str:
        return f"{url}:{path}" if path else url

    def github_repo_url(self, repo: str) -> str:
        value = repo.strip()
        if self.is_remote_source_value(value):
            return value
        return f"https://github.com/{value.removesuffix('.git')}.git"

    def revision_for_paths(self, paths: list[Path]) -> str:
        digest = sha256()
        for path in paths:
            if not path.exists():
                continue
            if path.is_file():
                stat = path.stat()
                digest.update(f"{path}:{stat.st_mtime_ns}:{stat.st_size}".encode())
                continue
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                stat = child.stat()
                digest.update(f"{child}:{stat.st_mtime_ns}:{stat.st_size}".encode())
        return digest.hexdigest()[:16]

    def updated_at_for_path(self, path: Path) -> str:
        latest = path.stat().st_mtime if path.exists() and path.is_file() else 0
        if path.exists() and path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    latest = max(latest, child.stat().st_mtime)
        return datetime.fromtimestamp(latest or 0, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def updated_at_for_paths(self, paths: list[Path]) -> str:
        latest = 0.0
        for path in paths:
            if not path.exists():
                continue
            if path.is_file():
                latest = max(latest, path.stat().st_mtime)
                continue
            for child in path.rglob("*"):
                if child.is_file():
                    latest = max(latest, child.stat().st_mtime)
        return datetime.fromtimestamp(latest or 0, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names: set[str] = set()
        for directory_name in ["skills", "commands", "agents", "hooks", "policies", "apps"]:
            directory_path = package_path / directory_name
            if directory_path.exists():
                names.add(directory_name)
                names.update(self.resource_names_from_directory(directory_path))
        if (package_path / ".mcp.json").exists():
            names.add("mcp")
            names.add(".mcp")
        mcp_root = package_path / "mcp"
        if mcp_root.exists():
            names.add("mcp")
            names.update(self.resource_names_from_directory(mcp_root))
        return sorted(names)

    def resource_names_from_directory(self, directory_path: Path) -> set[str]:
        names: set[str] = set()
        for path in sorted(item for item in directory_path.rglob("*") if item.is_file()):
            if path.name.startswith("."):
                continue
            names.add(path.stem)
            if path.suffix.lower() in {".md", ".mdx"}:
                names.update(self.markdown_resource_names(path))
            elif path.suffix.lower() == ".toml":
                names.update(self.toml_resource_names(path))
            elif path.suffix.lower() == ".json":
                names.update(self.json_resource_names(path))
        return {name for name in names if name}

    def markdown_resource_names(self, path: Path) -> set[str]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return set()
        names: set[str] = set()
        for line in lines[:20]:
            stripped = line.strip()
            if stripped.startswith("# "):
                names.add(stripped[2:].strip())
                break
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                if key.strip() in {"name", "title", "description"}:
                    names.add(value.strip().strip("\"'"))
        return names

    def json_resource_names(self, path: Path) -> set[str]:
        data = self.read_json(path)
        names: set[str] = set()
        for key in ["name", "title", "id", "command"]:
            value = data.get(key)
            if isinstance(value, str) and value:
                names.add(value)
        return names

    def toml_resource_names(self, path: Path) -> set[str]:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return set()
        names: set[str] = set()
        for key in ["id", "name", "title", "command"]:
            value = data.get(key)
            if isinstance(value, str) and value:
                names.add(value)
        return names

    def read_manifest(self, package_path: Path) -> dict[str, Any]:
        return self.read_json(self.manifest_path(package_path))

    def validation_result(
        self,
        *,
        code: str,
        severity: str = "error",
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "severity": severity,
            "code": code,
            "messageKey": code,
        }
        if file_path:
            result["filePath"] = file_path
        if details:
            result["details"] = details
        return result

    def validate_manifest_data(
        self,
        *,
        package_id: str,
        manifest: dict[str, Any],
        file_path: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        if not self.package_id_pattern.match(package_id):
            results.append(self.validation_result(
                code="marketplace.validation.invalid_package_id",
                file_path=file_path,
                details={"packageId": package_id},
            ))
        missing_fields = [
            field
            for field in self.manifest_required_fields
            if not isinstance(manifest.get(field), str) or not manifest.get(field).strip()
        ]
        if missing_fields:
            results.append(self.validation_result(
                code="marketplace.validation.invalid_manifest_shape",
                file_path=file_path,
                details={"missingFields": missing_fields},
            ))
        manifest_name = manifest.get("name")
        if isinstance(manifest_name, str) and manifest_name.strip() and manifest_name != package_id:
            results.append(self.validation_result(
                code="marketplace.validation.package_identity_mismatch",
                file_path=file_path,
                details={"packageId": package_id, "manifestName": manifest_name},
            ))
        return results

    def validate_package(self, package_path: Path, package_id: str | None = None) -> list[dict[str, Any]]:
        manifest_path = self.manifest_path(package_path)
        try:
            manifest_path.resolve().relative_to(package_path.resolve())
        except ValueError:
            return [self.validation_result(
                code="marketplace.validation.path_escape",
                file_path=str(manifest_path),
            )]
        if not manifest_path.exists():
            return [self.validation_result(
                code="marketplace.validation.required_manifest_missing",
                file_path=str(manifest_path.relative_to(package_path)),
            )]
        manifest, read_error = self.read_json_with_error(manifest_path)
        if read_error:
            return [self.validation_result(
                code="marketplace.validation.invalid_manifest_shape",
                file_path=str(manifest_path.relative_to(package_path)),
            )]
        return self.validate_manifest_data(
            package_id=package_id or package_path.name,
            manifest=manifest,
            file_path=str(manifest_path.relative_to(package_path)),
        )

    def validate_catalog_metadata(
        self,
        catalog_entry: dict[str, Any] | None,
        package_manifest: dict[str, Any],
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    def read_listing_entry(self, registry_root: Path, package_id: str) -> dict[str, Any] | None:
        return None

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        return None

    def upsert_listing_entry(self, registry_root: Path, package_id: str, entry: dict[str, Any]) -> None:
        return None

    def remove_listing_entry(self, registry_root: Path, package_id: str) -> None:
        return None

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        raise NotImplementedError("marketplace.import.not_implemented")

    def editor_tabs(self, package_path: Path) -> list[dict[str, Any]]:
        return []

    def export_package(self, package_path: Path) -> bytes:
        raise NotImplementedError("marketplace.export.not_implemented")

    def build_install_command(
        self,
        package_path: Path,
        workspace_id: str,
        preflight: MarketplaceCliPreflightResult,
    ) -> MarketplaceInstallCommandPlan:
        raise NotImplementedError("marketplace.install.not_implemented")

    def default_install_redact_patterns(self) -> list[str]:
        return [
            r"(?i)\b(api[_-]?key|token|secret|password)(\s*=\s*)\S+",
            r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
        ]

    def install_command_plan(
        self,
        *,
        provider: MarketplaceProvider,
        argv: list[str],
        cwd: Path,
        env: dict[str, str] | None = None,
    ) -> MarketplaceInstallCommandPlan:
        return MarketplaceInstallCommandPlan(
            provider=provider,
            argv=argv,
            cwd=str(cwd),
            env=env or {},
            timeout_ms=120_000,
            stdout_limit_bytes=65_536,
            stderr_limit_bytes=65_536,
            redact_patterns=self.default_install_redact_patterns(),
        )

    def summarize_detail(self, package_path: Path) -> dict[str, Any]:
        return self.read_manifest(package_path)


class MarketplaceManifestAdapter(BaseMarketplaceProviderAdapter):
    """Adapter for providers with root marketplace manifests."""

    marketplace_manifest: str
    plugin_root = "plugins"

    def marketplace_manifest_path(self, registry_root: Path) -> Path:
        return registry_root / self.provider / self.marketplace_manifest

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        return registry_root / self.provider / self.plugin_root / package_id

    def scan_registry(self, registry_root: Path) -> list[MarketplacePackageSummary]:
        manifest_path = self.marketplace_manifest_path(registry_root)
        data = self.read_json(manifest_path)
        entries = data.get("plugins") if isinstance(data.get("plugins"), list) else []
        packages: list[MarketplacePackageSummary] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            package_id = str(entry.get("name") or "").strip()
            if not package_id:
                continue
            if not self.package_id_pattern.match(package_id):
                validation = [self.validation_result(
                    code="marketplace.validation.invalid_package_id",
                    file_path=str(manifest_path.relative_to(registry_root)),
                    details={"packageId": package_id},
                )]
                packages.append(MarketplacePackageSummary(
                    provider=self.provider,
                    package_type="plugin",
                    package_id=package_id,
                    display_name=str(entry.get("displayName") or entry.get("display_name") or package_id),
                    version=self.string_or_none(entry.get("version")),
                    description=self.string_or_none(entry.get("description")),
                    category=self.string_or_none(entry.get("category")),
                    tags=self.string_list(entry.get("tags")) or self.string_list(entry.get("keywords")),
                    source_type="created",
                    indexed_resource_names=[],
                    validation_severity=self.highest_severity(validation),
                    registry_path=f"{self.provider}/{self.plugin_root}/{package_id}",
                    revision=self.revision_for_paths([manifest_path]),
                    updated_at=self.updated_at_for_path(manifest_path),
                ))
                continue
            package_path = self.package_path(registry_root, package_id)
            manifest = self.read_manifest(package_path)
            display_name = str(
                entry.get("displayName")
                or entry.get("display_name")
                or manifest.get("displayName")
                or manifest.get("display_name")
                or entry.get("name")
                or manifest.get("name")
                or package_id
            )
            description = self.first_string(entry.get("description"), manifest.get("description"))
            tags = self.first_string_list(
                entry.get("tags"),
                entry.get("keywords"),
                manifest.get("tags"),
                manifest.get("keywords"),
            )
            validation = [
                *self.validate_package(package_path),
                *self.validate_catalog_metadata(
                    entry,
                    manifest,
                    str(manifest_path.relative_to(registry_root)),
                ),
            ]
            packages.append(MarketplacePackageSummary(
                provider=self.provider,
                package_type="plugin",
                package_id=package_id,
                display_name=display_name,
                version=self.first_string(entry.get("version"), manifest.get("version")),
                description=description,
                category=self.first_string(entry.get("category"), manifest.get("category")),
                tags=tags,
                source_type=self.source_type_from_metadata(entry, manifest),
                indexed_resource_names=self.indexed_resource_names(package_path),
                validation_severity=self.highest_severity(validation),
                registry_path=str(package_path.relative_to(registry_root)),
                revision=self.revision_for_paths([manifest_path, package_path]),
                updated_at=self.updated_at_for_paths([manifest_path, package_path]),
            ))
        return packages

    def validate_catalog_metadata(
        self,
        catalog_entry: dict[str, Any] | None,
        package_manifest: dict[str, Any],
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        if not catalog_entry:
            return []
        conflicts: dict[str, dict[str, Any]] = {}
        scalar_pairs = {
            "description": ("description", "description"),
            "version": ("version", "version"),
            "displayName": ("displayName", "displayName"),
        }
        for field, (catalog_key, manifest_key) in scalar_pairs.items():
            catalog_value = catalog_entry.get(catalog_key)
            if field == "displayName" and catalog_value is None:
                catalog_value = catalog_entry.get("display_name")
            manifest_value = package_manifest.get(manifest_key)
            if (
                isinstance(catalog_value, str)
                and catalog_value.strip()
                and isinstance(manifest_value, str)
                and manifest_value.strip()
                and catalog_value != manifest_value
            ):
                conflicts[field] = {
                    "catalog": catalog_value,
                    "manifest": manifest_value,
                }
        catalog_tags = self.string_list(catalog_entry.get("tags")) or self.string_list(catalog_entry.get("keywords"))
        manifest_tags = self.string_list(package_manifest.get("tags")) or self.string_list(package_manifest.get("keywords"))
        if catalog_tags and manifest_tags and catalog_tags != manifest_tags:
            conflicts["tags"] = {
                "catalog": catalog_tags,
                "manifest": manifest_tags,
            }
        if not conflicts:
            return []
        return [self.validation_result(
            code="marketplace.validation.metadata_conflict",
            severity="warning",
            file_path=file_path,
            details={"fields": conflicts},
        )]

    def read_listing_entry(self, registry_root: Path, package_id: str) -> dict[str, Any] | None:
        manifest = self.read_json(self.marketplace_manifest_path(registry_root))
        plugins = manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        for entry in plugins:
            if isinstance(entry, dict) and entry.get("name") == package_id:
                return dict(entry)
        return None

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        manifest = self.read_json(source_root / self.marketplace_manifest)
        plugins = manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        for entry in plugins:
            if isinstance(entry, dict) and entry.get("name") == source_package_id:
                next_entry = dict(entry)
                next_entry["name"] = target_package_id
                if self.provider == "codex":
                    next_entry["source"] = {
                        "source": "local",
                        "path": f"./plugins/{target_package_id}",
                    }
                else:
                    next_entry["source"] = f"./plugins/{target_package_id}"
                return next_entry
        return None

    def upsert_listing_entry(self, registry_root: Path, package_id: str, entry: dict[str, Any]) -> None:
        manifest_path = self.marketplace_manifest_path(registry_root)
        manifest = self.read_json(manifest_path)
        plugins = manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        next_entry = {**entry, "name": package_id}
        updated = False
        next_plugins: list[Any] = []
        for current in plugins:
            if isinstance(current, dict) and current.get("name") == package_id:
                next_plugins.append(next_entry)
                updated = True
            else:
                next_plugins.append(current)
        if not updated:
            next_plugins.append(next_entry)
        manifest["plugins"] = next_plugins
        self.atomic_write_json(manifest_path, manifest)

    def remove_listing_entry(self, registry_root: Path, package_id: str) -> None:
        manifest_path = self.marketplace_manifest_path(registry_root)
        manifest = self.read_json(manifest_path)
        plugins = manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        manifest["plugins"] = [
            entry
            for entry in plugins
            if not (isinstance(entry, dict) and entry.get("name") == package_id)
        ]
        self.atomic_write_json(manifest_path, manifest)


class ClaudeCodeMarketplaceAdapter(MarketplaceManifestAdapter):
    """Claude Code Marketplace adapter."""

    provider: MarketplaceProvider = "claude-code"
    marketplace_manifest = ".claude-plugin/marketplace.json"
    local_marketplace_name = "local-marketplace"

    def ensure_roots(self, registry_root: Path) -> None:
        (registry_root / self.provider / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (registry_root / self.provider / "plugins").mkdir(parents=True, exist_ok=True)

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / ".claude-plugin" / "plugin.json"

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        manifest_path = source_root / self.marketplace_manifest
        data = self.read_json(manifest_path)
        entries = data.get("plugins") if isinstance(data.get("plugins"), list) else []
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            package_id = str(entry.get("name") or "").strip()
            if not package_id:
                continue
            package_path, source_path, source_results, source_metadata = self.resolve_external_package_source(
                source_root,
                entry,
                package_id,
            )
            manifest = self.read_manifest(package_path) if package_path is not None else {}
            validation_results = [
                *source_results,
                *([] if package_path is None else self.validate_package(package_path, package_id=package_id)),
                *self.validate_catalog_metadata(
                    entry,
                    manifest,
                    str(manifest_path.relative_to(source_root)),
                ),
            ]
            candidates.append({
                "id": f"{self.provider}:{package_id}",
                "provider": self.provider,
                "packageId": package_id,
                "displayName": str(
                    entry.get("displayName")
                    or entry.get("display_name")
                    or manifest.get("displayName")
                    or manifest.get("display_name")
                    or entry.get("name")
                    or manifest.get("name")
                    or package_id
                ),
                "sourcePath": source_path,
                "duplicate": False,
                "duplicateAction": "skip",
                "validationSeverity": self.highest_severity(validation_results),
                "validationResults": validation_results,
                "sourceMetadata": source_metadata,
            })
        return candidates

    def resolve_external_package_source(
        self,
        source_root: Path,
        entry: dict[str, Any],
        package_id: str,
    ) -> tuple[Path | None, str, list[dict[str, Any]], dict[str, Any]]:
        raw_source = entry.get("source")
        if isinstance(raw_source, str) and raw_source.strip():
            source_value = raw_source.strip()
        elif isinstance(raw_source, dict):
            source_type = str(raw_source.get("source") or "").strip()
            path_value = raw_source.get("path")
            url_value = raw_source.get("url")
            repo_value = raw_source.get("repo")
            if source_type == "local" and isinstance(path_value, str) and path_value.strip():
                source_value = path_value.strip()
            else:
                url = (
                    str(url_value).strip()
                    if isinstance(url_value, str) and url_value.strip()
                    else self.github_repo_url(str(repo_value).strip())
                    if isinstance(repo_value, str) and repo_value.strip()
                    else source_type
                    if source_type
                    else f"./plugins/{package_id}"
                )
                path = path_value.strip() if isinstance(path_value, str) and path_value.strip() else None
                ref = raw_source.get("ref")
                sha = raw_source.get("sha")
                return None, self.remote_source_path(url, path), [], self.remote_source_metadata(
                    source_type=source_type or "url",
                    url=url,
                    path=path,
                    ref=ref.strip() if isinstance(ref, str) and ref.strip() else None,
                    sha=sha.strip() if isinstance(sha, str) and sha.strip() else None,
                )
        else:
            source_value = f"./plugins/{package_id}"
        if self.is_remote_source_value(source_value):
            return None, source_value, [], self.remote_source_metadata(
                source_type="url",
                url=source_value,
            )
        source_path = Path(source_value)
        candidate = (source_root / source_path).resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            return None, source_value, [self.validation_result(
                code="marketplace.validation.path_escape",
                file_path=source_value,
                details={"packageId": package_id},
            )], {}
        try:
            relative_source = candidate.relative_to(source_root.resolve()).as_posix()
        except ValueError:
            relative_source = source_value
        return candidate, relative_source, [], {}

    def create_package(self, package_path: Path, request: MarketplacePackageCreateRequest) -> None:
        (package_path / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        self.atomic_write_json(package_path / ".claude-plugin" / "plugin.json", {"name": request.package_id})
        (package_path / "README.md").write_text(
            f"# {request.display_name}\n\n{request.description}\n",
            encoding="utf-8",
        )

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names = set(super().indexed_resource_names(package_path))
        if (package_path / "output-styles").exists():
            names.add("output-style")
        if (package_path / "AGENTS.md").exists():
            names.add("agentsMd")
        return sorted(names)

    def build_install_command(
        self,
        package_path: Path,
        workspace_id: str,
        preflight: MarketplaceCliPreflightResult,
    ) -> MarketplaceInstallCommandPlan:
        package_id = package_path.name
        provider_root = package_path.parents[1]
        executable = preflight.executable_path or "claude"
        argv = [
            executable,
            "plugin",
            "install",
            f"{package_id}@{self.local_marketplace_name}",
        ]
        if preflight.capabilities.supports_user_scope:
            argv.extend(["--scope", "user"])
        return self.install_command_plan(
            provider=self.provider,
            argv=argv,
            cwd=provider_root,
            env={
                "WORKSPACE_ID": workspace_id,
                "MARKETPLACE_NAME": self.local_marketplace_name,
            },
        )


class CodexMarketplaceAdapter(MarketplaceManifestAdapter):
    """Codex Marketplace adapter."""

    provider: MarketplaceProvider = "codex"
    marketplace_manifest = ".agents/plugins/marketplace.json"
    manifest_required_fields = ("name", "version", "description")

    def ensure_roots(self, registry_root: Path) -> None:
        (registry_root / self.provider / ".agents" / "plugins").mkdir(parents=True, exist_ok=True)
        (registry_root / self.provider / "plugins").mkdir(parents=True, exist_ok=True)

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / ".codex-plugin" / "plugin.json"

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        manifest_path = source_root / self.marketplace_manifest
        data = self.read_json(manifest_path)
        entries = data.get("plugins") if isinstance(data.get("plugins"), list) else []
        if not entries and self.manifest_path(source_root).exists():
            manifest = self.read_manifest(source_root)
            package_id = str(manifest.get("name") or source_root.name).strip()
            if not package_id:
                return []
            validation_results = self.validate_package(source_root, package_id=package_id)
            return [{
                "id": f"{self.provider}:{package_id}",
                "provider": self.provider,
                "packageId": package_id,
                "displayName": str(
                    manifest.get("displayName")
                    or manifest.get("display_name")
                    or manifest.get("name")
                    or package_id
                ),
                "sourcePath": ".",
                "duplicate": False,
                "duplicateAction": "skip",
                "validationSeverity": self.highest_severity(validation_results),
                "validationResults": validation_results,
                "sourceMetadata": {},
            }]
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            package_id = str(entry.get("name") or "").strip()
            if not package_id:
                continue
            package_path, source_path, source_results, source_metadata = self.resolve_external_package_source(
                source_root,
                entry,
                package_id,
            )
            manifest = self.read_manifest(package_path) if package_path is not None else {}
            validation_results = [
                *source_results,
                *([] if package_path is None else self.validate_package(package_path, package_id=package_id)),
                *self.validate_catalog_metadata(
                    entry,
                    manifest,
                    str(manifest_path.relative_to(source_root)),
                ),
            ]
            candidates.append({
                "id": f"{self.provider}:{package_id}",
                "provider": self.provider,
                "packageId": package_id,
                "displayName": str(
                    entry.get("displayName")
                    or entry.get("display_name")
                    or manifest.get("displayName")
                    or manifest.get("display_name")
                    or entry.get("name")
                    or manifest.get("name")
                    or package_id
                ),
                "sourcePath": source_path,
                "duplicate": False,
                "duplicateAction": "skip",
                "validationSeverity": self.highest_severity(validation_results),
                "validationResults": validation_results,
                "sourceMetadata": source_metadata,
            })
        return candidates

    def resolve_external_package_source(
        self,
        source_root: Path,
        entry: dict[str, Any],
        package_id: str,
    ) -> tuple[Path | None, str, list[dict[str, Any]], dict[str, Any]]:
        raw_source = entry.get("source")
        source_value = f"./plugins/{package_id}"
        if isinstance(raw_source, str) and raw_source.strip():
            source_value = raw_source.strip()
        elif isinstance(raw_source, dict):
            raw_source_type = raw_source.get("source")
            if isinstance(raw_source_type, str) and raw_source_type.strip() and raw_source_type.strip() != "local":
                source_type = raw_source_type.strip()
                raw_url = raw_source.get("url")
                raw_repo = raw_source.get("repo")
                url = (
                    raw_url.strip()
                    if isinstance(raw_url, str) and raw_url.strip()
                    else self.github_repo_url(raw_repo)
                    if isinstance(raw_repo, str) and raw_repo.strip()
                    else source_type
                )
                raw_path = raw_source.get("path")
                path = raw_path.strip() if isinstance(raw_path, str) and raw_path.strip() else None
                raw_ref = raw_source.get("ref")
                raw_sha = raw_source.get("sha")
                return None, self.remote_source_path(url, path), [], self.remote_source_metadata(
                    source_type=source_type,
                    url=url,
                    path=path,
                    ref=raw_ref.strip() if isinstance(raw_ref, str) and raw_ref.strip() else None,
                    sha=raw_sha.strip() if isinstance(raw_sha, str) and raw_sha.strip() else None,
                )
            raw_path = raw_source.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                source_value = raw_path.strip()
        if self.is_remote_source_value(source_value):
            return None, source_value, [], self.remote_source_metadata(
                source_type="url",
                url=source_value,
            )
        source_path = Path(source_value)
        candidate = (source_root / source_path).resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            return None, source_value, [self.validation_result(
                code="marketplace.validation.path_escape",
                file_path=source_value,
                details={"packageId": package_id},
            )], {}
        try:
            relative_source = candidate.relative_to(source_root.resolve()).as_posix()
        except ValueError:
            relative_source = source_value
        return candidate, relative_source, [], {}

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        listing = super().import_listing_entry(source_root, source_package_id, target_package_id)
        if listing is not None:
            return listing
        manifest_path = self.manifest_path(source_root)
        if not manifest_path.exists():
            return None
        manifest = self.read_json(manifest_path)
        return {
            "name": target_package_id,
            "description": self.string_or_none(manifest.get("description")),
            "version": self.string_or_none(manifest.get("version")),
            "source": {
                "source": "local",
                "path": f"./plugins/{target_package_id}",
            },
        }

    def create_package(self, package_path: Path, request: MarketplacePackageCreateRequest) -> None:
        (package_path / ".codex-plugin").mkdir(parents=True, exist_ok=True)
        self.atomic_write_json(
            package_path / ".codex-plugin" / "plugin.json",
            {
                "name": request.package_id,
                "version": "0.1.0",
                "description": request.description,
            },
        )
        (package_path / "README.md").write_text(
            f"# {request.display_name}\n\n{request.description}\n",
            encoding="utf-8",
        )

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names = set(super().indexed_resource_names(package_path))
        if (package_path / "hooks.json").exists() or (package_path / "hooks" / "hooks.json").exists():
            names.add("hooks")
        if (package_path / "AGENTS.md").exists():
            names.add("agentsMd")
        return sorted(names)

    def build_install_command(
        self,
        package_path: Path,
        workspace_id: str,
        preflight: MarketplaceCliPreflightResult,
    ) -> MarketplaceInstallCommandPlan:
        package_id = package_path.name
        provider_root = package_path.parents[1]
        executable = preflight.executable_path or "codex"
        argv = [
            executable,
            "plugin",
            "marketplace",
            "add",
            str(provider_root),
        ]
        if preflight.capabilities.supports_user_scope:
            argv.append("--user")
        return self.install_command_plan(
            provider=self.provider,
            argv=argv,
            cwd=provider_root,
            env={"WORKSPACE_ID": workspace_id},
        )


class GeminiExtensionAdapter(BaseMarketplaceProviderAdapter):
    """Gemini extension adapter."""

    provider: MarketplaceProvider = "gemini"
    package_type = "extension"
    manifest_required_fields = ("name", "version")

    def ensure_roots(self, registry_root: Path) -> None:
        (registry_root / self.provider / "extensions").mkdir(parents=True, exist_ok=True)

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        return registry_root / self.provider / "extensions" / package_id

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / "gemini-extension.json"

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        package_paths = self.external_extension_paths(source_root)
        candidates: list[dict[str, Any]] = []
        for package_path in package_paths:
            manifest = self.read_manifest(package_path)
            package_id = str(manifest.get("name") or package_path.name).strip()
            if not package_id:
                continue
            validation_results = self.validate_manifest_data(
                package_id=package_id,
                manifest=manifest,
                file_path="gemini-extension.json",
            )
            source_path = "."
            if package_path != source_root:
                source_path = package_path.relative_to(source_root).as_posix()
            candidates.append({
                "id": f"{self.provider}:{package_id}",
                "provider": self.provider,
                "packageId": package_id,
                "displayName": str(
                    manifest.get("displayName")
                    or manifest.get("display_name")
                    or manifest.get("name")
                    or package_id
                ),
                "sourcePath": source_path,
                "duplicate": False,
                "duplicateAction": "skip",
                "validationSeverity": self.highest_severity(validation_results),
                "validationResults": validation_results,
            })
        return candidates

    def external_extension_paths(self, source_root: Path) -> list[Path]:
        if self.manifest_path(source_root).exists():
            return [source_root]
        return sorted([
            child
            for child in source_root.iterdir()
            if child.is_dir() and self.manifest_path(child).exists()
        ])

    def create_package(self, package_path: Path, request: MarketplacePackageCreateRequest) -> None:
        self.atomic_write_json(
            package_path / "gemini-extension.json",
            {
                "name": request.package_id,
                "version": "0.1.0",
                "description": request.description,
            },
        )
        (package_path / "GEMINI.md").write_text(
            f"# {request.display_name}\n\n{request.description}\n",
            encoding="utf-8",
        )

    def scan_registry(self, registry_root: Path) -> list[MarketplacePackageSummary]:
        extensions_root = registry_root / self.provider / "extensions"
        if not extensions_root.exists():
            return []
        packages: list[MarketplacePackageSummary] = []
        for package_path in sorted(path for path in extensions_root.iterdir() if path.is_dir()):
            package_id = package_path.name
            manifest = self.read_manifest(package_path)
            validation = self.validate_package(package_path)
            packages.append(MarketplacePackageSummary(
                provider=self.provider,
                package_type="extension",
                package_id=package_id,
                display_name=str(
                    manifest.get("displayName")
                    or manifest.get("display_name")
                    or manifest.get("name")
                    or package_id
                ),
                version=self.string_or_none(manifest.get("version")),
                description=self.string_or_none(manifest.get("description")),
                category=self.string_or_none(manifest.get("category")),
                tags=self.first_string_list(manifest.get("tags"), manifest.get("keywords")),
                source_type=self.source_type_from_metadata(manifest),
                indexed_resource_names=self.indexed_resource_names(package_path),
                validation_severity=self.highest_severity(validation),
                registry_path=str(package_path.relative_to(registry_root)),
                revision=self.revision_for_paths([package_path]),
                updated_at=self.updated_at_for_paths([package_path]),
            ))
        return packages

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names = set(super().indexed_resource_names(package_path))
        if (package_path / "GEMINI.md").exists():
            names.add("agentsMd")
        gemini_commands = package_path / "commands"
        if gemini_commands.exists():
            names.update(self.resource_names_from_directory(gemini_commands))
        return sorted(names)

    def build_install_command(
        self,
        package_path: Path,
        workspace_id: str,
        preflight: MarketplaceCliPreflightResult,
    ) -> MarketplaceInstallCommandPlan:
        executable = preflight.executable_path or "gemini"
        argv = [
            executable,
            "extensions",
            "install",
            str(package_path),
            "--consent",
        ]
        if preflight.capabilities.supports_user_scope:
            argv.append("--user")
        return self.install_command_plan(
            provider=self.provider,
            argv=argv,
            cwd=package_path.parent,
            env={
                "WORKSPACE_ID": workspace_id,
                "GEMINI_CLI_TRUST_WORKSPACE": "true",
            },
        )


def create_marketplace_adapters() -> dict[MarketplaceProvider, MarketplaceProviderAdapter]:
    """Create Marketplace provider adapters."""
    return {
        "claude-code": ClaudeCodeMarketplaceAdapter(),
        "codex": CodexMarketplaceAdapter(),
        "gemini": GeminiExtensionAdapter(),
    }
