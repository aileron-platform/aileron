"""Marketplace target-client adapters."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import tomllib
from aileron_marketplace_core import (
    PackageSourceError,
    PluginPackageFormat,
    PluginReleaseIdentity,
    extract_user_copy_source_profile,
    resolve_claude_plugin_resources,
    resolve_codex_plugin_resources,
    revision_for_package_paths,
)
from aileron_marketplace_core.package_format_resources import (
    package_format_resource_name_contract,
)

from app.modules.marketplace.models import (
    MarketplacePackageFormat,
    MarketplaceTargetClient,
)

_AUTHORING_FEATURES = (
    "basic",
    "agentsMd",
    "hooks",
    "mcp",
    "agents",
    "commands",
    "outputStyle",
    "skills",
    "files",
)

_PACKAGE_FORMAT_WRITABLE_FEATURES: dict[str, frozenset[str]] = {
    "claude-native": frozenset(_AUTHORING_FEATURES),
    "codex-native": frozenset(
        feature for feature in _AUTHORING_FEATURES if feature != "outputStyle"
    ),
    "agent-plugin/1.0.0": frozenset({"basic", "mcp", "skills", "files"}),
}


def package_format_authoring_capabilities(package_format: str) -> dict[str, str]:
    """Return the single package-format authoring capability contract."""

    writable = _PACKAGE_FORMAT_WRITABLE_FEATURES[package_format]
    return {
        feature: "read-write" if feature in writable else "unsupported"
        for feature in _AUTHORING_FEATURES
    }

_PACKAGE_FORMAT_STORAGE_KEYS: dict[MarketplacePackageFormat, str] = {
    "codex-native": "codex-native",
    "claude-native": "claude-native",
    "agent-plugin/1.0.0": "agent-plugin-1.0.0",
}


def package_format_storage_key(package_format: MarketplacePackageFormat) -> str:
    """Return the stable path/tag segment for one package grammar."""

    return _PACKAGE_FORMAT_STORAGE_KEYS[package_format]


def package_format_from_storage_key(value: str) -> MarketplacePackageFormat:
    """Resolve one canonical package grammar from its stable path segment."""

    for package_format, storage_key in _PACKAGE_FORMAT_STORAGE_KEYS.items():
        if storage_key == value:
            return package_format
    raise ValueError("marketplace.package.format_invalid")


class MarketplaceTargetClientAdapter(Protocol):
    """TargetClient adapter contract for native Marketplace package operations."""

    target_client: MarketplaceTargetClient
    package_format: MarketplacePackageFormat
    user_copy_target_client: MarketplaceTargetClient
    marketplace_manifest: str

    def ensure_roots(self, registry_root: Path) -> None:
        """Ensure target_client root directories exist."""

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        """Return package path under target_client root."""

    def manifest_path(self, package_path: Path) -> Path:
        """Return package manifest path."""

    def read_manifest(self, package_path: Path) -> dict[str, Any]:
        """Read one target_client-native Plugin manifest."""

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        """Scan an external source for import candidates."""

    def validate_package(
        self, package_path: Path, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Validate target_client-native package files."""

    def validate_catalog_metadata(
        self,
        catalog_entry: dict[str, Any] | None,
        package_manifest: dict[str, Any],
        file_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Validate catalog metadata against package manifest metadata."""

    def read_listing_entry(
        self, registry_root: Path, package_id: str
    ) -> dict[str, Any] | None:
        """Read a single package listing projection from a root marketplace manifest."""

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        """Build a target listing entry for an imported package."""

    def import_component_selectors(
        self,
        source_root: Path,
        source_package_root: Path,
        source_package_id: str,
    ) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
        """Return validated server-side component selectors for one import."""

    def validate_component_projection(
        self,
        package_path: Path,
    ) -> list[dict[str, Any]]:
        """Validate that an explicit component projection is self-contained."""

    def export_listing_entry(
        self,
        registry_root: Path,
        package_path: Path,
        package_id: str,
    ) -> dict[str, Any] | None:
        """Build a listing entry for an exported package archive."""

    def is_remote_source_value(self, value: str) -> bool:
        """Return whether a source value points outside the scanned checkout."""


class BaseMarketplaceTargetClientAdapter:
    """Shared target_client adapter helpers."""

    target_client: MarketplaceTargetClient
    package_format: MarketplacePackageFormat
    user_copy_target_client: MarketplaceTargetClient
    package_type = "plugin"
    manifest_required_fields: tuple[str, ...] = ("name",)
    package_id_pattern = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        return (
            registry_root
            / self.target_client
            / "plugins"
            / package_format_storage_key(self.package_format)
            / package_id
        )

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

    def string_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    def string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str) and item]

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
        return revision_for_package_paths(paths)

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
        return (
            datetime.fromtimestamp(latest or 0, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names: set[str] = set()
        contract = package_format_resource_name_contract(self.package_format)
        for directory in contract.indexed_directories:
            directory_path = package_path / directory.source_name
            if directory_path.exists():
                names.add(directory.index_name)
                names.update(self.resource_names_from_directory(directory_path))
        if (package_path / contract.root_document_name).is_file():
            names.add(contract.root_document_index_name)
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
        for path in sorted(
            item for item in directory_path.rglob("*") if item.is_file()
        ):
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
            results.append(
                self.validation_result(
                    code="marketplace.validation.invalid_package_id",
                    file_path=file_path,
                    details={"packageId": package_id},
                )
            )
        missing_fields = [
            field
            for field in self.manifest_required_fields
            if not isinstance(manifest.get(field), str)
            or not manifest.get(field).strip()
        ]
        if missing_fields:
            results.append(
                self.validation_result(
                    code="marketplace.validation.invalid_manifest_shape",
                    file_path=file_path,
                    details={"missingFields": missing_fields},
                )
            )
        manifest_name = manifest.get("name")
        if (
            isinstance(manifest_name, str)
            and manifest_name.strip()
            and manifest_name != package_id
        ):
            results.append(
                self.validation_result(
                    code="marketplace.validation.package_identity_mismatch",
                    file_path=file_path,
                    details={"packageId": package_id, "manifestName": manifest_name},
                )
            )
        return results

    def validate_package(
        self, package_path: Path, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        manifest_path = self.manifest_path(package_path)
        try:
            manifest_path.resolve().relative_to(package_path.resolve())
        except ValueError:
            return [
                self.validation_result(
                    code="marketplace.validation.path_escape",
                    file_path=str(manifest_path),
                )
            ]
        if not manifest_path.exists():
            # Per-package plugin manifest is optional: marketplace listing
            # entries are allowed to declare full plugin metadata. Validation
            # only applies when a manifest file is present; the import flow
            # synthesizes one from the listing entry when missing.
            return []
        manifest, read_error = self.read_json_with_error(manifest_path)
        if read_error:
            return [
                self.validation_result(
                    code="marketplace.validation.invalid_manifest_shape",
                    file_path=str(manifest_path.relative_to(package_path)),
                )
            ]
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

    def read_listing_entry(
        self, registry_root: Path, package_id: str
    ) -> dict[str, Any] | None:
        return None

    def import_listing_entry(
        self,
        source_root: Path,
        source_package_id: str,
        target_package_id: str,
    ) -> dict[str, Any] | None:
        return None

    def import_component_selectors(
        self,
        source_root: Path,
        source_package_root: Path,
        source_package_id: str,
    ) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
        _ = (source_root, source_package_root, source_package_id)
        return {}, []

    def export_listing_entry(
        self,
        registry_root: Path,
        package_path: Path,
        package_id: str,
    ) -> dict[str, Any] | None:
        return None

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        raise NotImplementedError("marketplace.import.not_implemented")


class MarketplaceManifestAdapter(BaseMarketplaceTargetClientAdapter):
    """Adapter for target_clients with root marketplace manifests."""

    marketplace_manifest: str
    plugin_root = "plugins"
    component_selector_fields: tuple[str, ...] = (
        "skills",
        "commands",
        "agents",
        "outputStyles",
    )

    def marketplace_manifest_path(self, registry_root: Path) -> Path:
        return registry_root / self.marketplace_manifest

    def package_path(self, registry_root: Path, package_id: str) -> Path:
        return super().package_path(registry_root, package_id)

    def direct_root_plugin_candidate(
        self,
        source_root: Path,
    ) -> dict[str, Any] | None:
        """Return one native plugin candidate when no Marketplace index exists."""

        if not self.manifest_path(source_root).is_file():
            return None
        manifest = self.read_manifest(source_root)
        package_id = str(manifest.get("name") or source_root.name).strip()
        if not package_id:
            return None
        validation_results = self.validate_package(
            source_root,
            package_id=package_id,
        )
        return {
            "id": f"{self.target_client}:{package_id}",
            "target_client": self.target_client,
            "packageFormat": self.package_format,
            "packageId": package_id,
            "version": str(manifest.get("version") or "1.0.0"),
            "displayName": str(
                manifest.get("displayName")
                or manifest.get("display_name")
                or manifest.get("name")
                or package_id
            ),
            "sourcePath": ".",
            "duplicate": False,
            "validationSeverity": self.highest_severity(validation_results),
            "validationResults": validation_results,
            "sourceMetadata": {},
        }

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
        catalog_tags = self.string_list(catalog_entry.get("tags")) or self.string_list(
            catalog_entry.get("keywords")
        )
        manifest_tags = self.string_list(
            package_manifest.get("tags")
        ) or self.string_list(package_manifest.get("keywords"))
        if catalog_tags and manifest_tags and catalog_tags != manifest_tags:
            conflicts["tags"] = {
                "catalog": catalog_tags,
                "manifest": manifest_tags,
            }
        if not conflicts:
            return []
        return [
            self.validation_result(
                code="marketplace.validation.metadata_conflict",
                severity="warning",
                file_path=file_path,
                details={"fields": conflicts},
            )
        ]

    def read_listing_entry(
        self, registry_root: Path, package_id: str
    ) -> dict[str, Any] | None:
        manifest = self.read_json(self.marketplace_manifest_path(registry_root))
        plugins = (
            manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        )
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
        plugins = (
            manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        )
        for entry in plugins:
            if isinstance(entry, dict) and entry.get("name") == source_package_id:
                next_entry = dict(entry)
                next_entry["name"] = target_package_id
                if self.target_client == "codex":
                    next_entry["source"] = {
                        "source": "local",
                        "path": f"./plugins/{target_package_id}",
                    }
                else:
                    next_entry["source"] = f"./plugins/{target_package_id}"
                return next_entry
        return None

    def import_component_selectors(
        self,
        source_root: Path,
        source_package_root: Path,
        source_package_id: str,
    ) -> tuple[dict[str, list[str]], list[dict[str, Any]]]:
        """Validate explicit component paths from the authoritative listing."""

        manifest_path = source_root / self.marketplace_manifest
        manifest = self.read_json(manifest_path)
        plugins = (
            manifest.get("plugins") if isinstance(manifest.get("plugins"), list) else []
        )
        listing = next(
            (
                entry
                for entry in plugins
                if isinstance(entry, dict) and entry.get("name") == source_package_id
            ),
            None,
        )
        if listing is None:
            return {}, []

        selectors: dict[str, list[str]] = {}
        results: list[dict[str, Any]] = []
        package_root = source_package_root.resolve()
        file_path = str(manifest_path.relative_to(source_root))
        target_identities: set[tuple[str, str]] = set()
        for field_name in self.component_selector_fields:
            if field_name not in listing:
                continue
            raw_value = listing.get(field_name)
            values = [raw_value] if isinstance(raw_value, str) else raw_value
            if not isinstance(values, list) or any(
                not isinstance(item, str) or not item.strip() for item in values
            ):
                results.append(
                    self.validation_result(
                        code="marketplace.validation.invalid_component_selector",
                        file_path=file_path,
                        details={
                            "packageId": source_package_id,
                            "field": field_name,
                        },
                    )
                )
                continue

            normalized_values: list[str] = []
            for raw_selector in values:
                selector = str(raw_selector).strip().replace("\\", "/")
                while selector.startswith("./"):
                    selector = selector[2:]
                selector_path = Path(selector)
                if (
                    not selector
                    or selector_path.is_absolute()
                    or any(part in {"", ".", ".."} for part in selector_path.parts)
                ):
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.path_escape",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "field": field_name,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue

                candidate = package_root / selector_path
                try:
                    candidate.resolve().relative_to(package_root)
                except ValueError:
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.path_escape",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "field": field_name,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue
                if not candidate.exists():
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.component_selector_not_found",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "field": field_name,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue
                if self._path_tree_contains_symlink(package_root, candidate):
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.component_selector_symlink",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "field": field_name,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue
                if field_name == "skills" and (
                    not candidate.is_dir() or not (candidate / "SKILL.md").is_file()
                ):
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.invalid_skill_selector",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue

                normalized = selector_path.as_posix()
                logical_identities = self._component_selector_target_identities(
                    field_name,
                    candidate,
                )
                if any(
                    identity in target_identities for identity in logical_identities
                ):
                    results.append(
                        self.validation_result(
                            code="marketplace.validation.component_selector_conflict",
                            file_path=file_path,
                            details={
                                "packageId": source_package_id,
                                "field": field_name,
                                "selector": raw_selector,
                            },
                        )
                    )
                    continue
                target_identities.update(logical_identities)
                normalized_values.append(normalized)
            selectors[field_name] = normalized_values
        return selectors, results

    def _component_selector_target_identities(
        self,
        field_name: str,
        candidate: Path,
    ) -> set[tuple[str, str]]:
        """Return target_client logical target identities, independent of source paths."""

        source_directory_by_field = {
            "skills": "skills",
            "commands": "commands",
            "agents": "agents",
            "outputStyles": "output-styles",
        }
        source_directory = source_directory_by_field[field_name]
        contract = package_format_resource_name_contract(self.package_format)
        index_name = next(
            (
                directory.index_name
                for directory in contract.indexed_directories
                if directory.source_name == source_directory
            ),
            field_name,
        )
        if field_name == "skills":
            names = {candidate.name}
        elif candidate.is_dir():
            names = self.resource_names_from_directory(candidate)
        else:
            names = {candidate.stem}
        return {(index_name.casefold(), name.casefold()) for name in names if name}

    def validate_component_projection(
        self,
        package_path: Path,
    ) -> list[dict[str, Any]]:
        """Reject an explicit projection with unresolved package dependencies."""

        resolved = (
            resolve_claude_plugin_resources(package_path)
            if self.target_client == "claude-code"
            else resolve_codex_plugin_resources(package_path)
        )
        return [
            self.validation_result(
                code=(
                    "marketplace.validation."
                    "component_selector_dependency_unprojectable"
                ),
                file_path=diagnostic.source_locator,
                details={"diagnosticCode": diagnostic.code},
            )
            for diagnostic in resolved.diagnostics
        ]

    @staticmethod
    def _path_tree_contains_symlink(package_root: Path, candidate: Path) -> bool:
        current = candidate
        while current != package_root:
            if current.is_symlink():
                return True
            current = current.parent
        return candidate.is_symlink() or (
            candidate.is_dir()
            and any(child.is_symlink() for child in candidate.rglob("*"))
        )

    def export_listing_entry(
        self,
        registry_root: Path,
        package_path: Path,
        package_id: str,
    ) -> dict[str, Any] | None:
        entry = self.read_listing_entry(registry_root, package_id)
        if entry is not None:
            next_entry = dict(entry)
            next_entry["name"] = package_id
            return next_entry

        manifest = self.read_manifest(package_path)
        next_entry: dict[str, Any] = {
            "name": package_id,
        }
        for key in (
            "displayName",
            "description",
            "version",
            "category",
            "tags",
            "keywords",
        ):
            value = manifest.get(key)
            if value is not None:
                next_entry[key] = value
        if self.target_client == "codex":
            next_entry["source"] = {
                "source": "local",
                "path": f"./plugins/{package_id}",
            }
        else:
            next_entry["source"] = f"./plugins/{package_id}"
        return next_entry


class ClaudeCodeMarketplaceAdapter(MarketplaceManifestAdapter):
    """Claude Code Marketplace adapter."""

    target_client: MarketplaceTargetClient = "claude-code"
    package_format: MarketplacePackageFormat = "claude-native"
    user_copy_target_client: MarketplaceTargetClient = "claude-code"
    marketplace_manifest = ".claude-plugin/marketplace.json"

    def ensure_roots(self, registry_root: Path) -> None:
        (registry_root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (registry_root / self.target_client / "plugins").mkdir(
            parents=True, exist_ok=True
        )

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / ".claude-plugin" / "plugin.json"

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        manifest_path = source_root / self.marketplace_manifest
        data = self.read_json(manifest_path)
        entries = data.get("plugins") if isinstance(data.get("plugins"), list) else []
        if not entries:
            direct_candidate = self.direct_root_plugin_candidate(source_root)
            return [direct_candidate] if direct_candidate is not None else []
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            package_id = str(entry.get("name") or "").strip()
            if not package_id:
                continue
            package_path, source_path, source_results, source_metadata = (
                self.resolve_external_package_source(
                    source_root,
                    entry,
                    package_id,
                )
            )
            manifest = (
                self.read_manifest(package_path) if package_path is not None else {}
            )
            component_selectors: dict[str, list[str]] = {}
            selector_results: list[dict[str, Any]] = []
            if package_path is not None:
                component_selectors, selector_results = self.import_component_selectors(
                    source_root,
                    package_path,
                    package_id,
                )
                if component_selectors:
                    source_metadata = {
                        **source_metadata,
                        "componentSelectors": component_selectors,
                    }
            validation_results = [
                *source_results,
                *selector_results,
                *(
                    []
                    if package_path is None
                    else self.validate_package(package_path, package_id=package_id)
                ),
                *self.validate_catalog_metadata(
                    entry,
                    manifest,
                    str(manifest_path.relative_to(source_root)),
                ),
            ]
            candidates.append(
                {
                    "id": f"{self.target_client}:{package_id}",
                    "target_client": self.target_client,
                    "packageFormat": self.package_format,
                    "packageId": package_id,
                    "version": str(
                        entry.get("version") or manifest.get("version") or "1.0.0"
                    ),
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
                    "validationSeverity": self.highest_severity(validation_results),
                    "validationResults": validation_results,
                    "sourceMetadata": source_metadata,
                }
            )
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
            if (
                source_type == "local"
                and isinstance(path_value, str)
                and path_value.strip()
            ):
                source_value = path_value.strip()
            else:
                url = (
                    str(url_value).strip()
                    if isinstance(url_value, str) and url_value.strip()
                    else (
                        self.github_repo_url(str(repo_value).strip())
                        if isinstance(repo_value, str) and repo_value.strip()
                        else source_type if source_type else f"./plugins/{package_id}"
                    )
                )
                path = (
                    path_value.strip()
                    if isinstance(path_value, str) and path_value.strip()
                    else None
                )
                ref = raw_source.get("ref")
                sha = raw_source.get("sha")
                return (
                    None,
                    self.remote_source_path(url, path),
                    [],
                    self.remote_source_metadata(
                        source_type=source_type or "url",
                        url=url,
                        path=path,
                        ref=(
                            ref.strip()
                            if isinstance(ref, str) and ref.strip()
                            else None
                        ),
                        sha=(
                            sha.strip()
                            if isinstance(sha, str) and sha.strip()
                            else None
                        ),
                    ),
                )
        else:
            source_value = f"./plugins/{package_id}"
        if self.is_remote_source_value(source_value):
            return (
                None,
                source_value,
                [],
                self.remote_source_metadata(
                    source_type="url",
                    url=source_value,
                ),
            )
        source_path = Path(source_value)
        candidate = (source_root / source_path).resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            return (
                None,
                source_value,
                [
                    self.validation_result(
                        code="marketplace.validation.path_escape",
                        file_path=source_value,
                        details={"packageId": package_id},
                    )
                ],
                {},
            )
        try:
            relative_source = candidate.relative_to(source_root.resolve()).as_posix()
        except ValueError:
            relative_source = source_value
        return candidate, relative_source, [], {}


class CodexMarketplaceAdapter(MarketplaceManifestAdapter):
    """Codex Marketplace adapter."""

    target_client: MarketplaceTargetClient = "codex"
    package_format: MarketplacePackageFormat = "codex-native"
    user_copy_target_client: MarketplaceTargetClient = "codex"
    marketplace_manifest = ".agents/plugins/marketplace.json"
    manifest_required_fields = ("name", "version", "description")

    def ensure_roots(self, registry_root: Path) -> None:
        (registry_root / ".agents" / "plugins").mkdir(parents=True, exist_ok=True)
        (registry_root / self.target_client / "plugins").mkdir(
            parents=True, exist_ok=True
        )

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / ".codex-plugin" / "plugin.json"

    def scan_external_source(self, source_root: Path) -> list[dict[str, Any]]:
        manifest_path = source_root / self.marketplace_manifest
        data = self.read_json(manifest_path)
        entries = data.get("plugins") if isinstance(data.get("plugins"), list) else []
        if not entries:
            direct_candidate = self.direct_root_plugin_candidate(source_root)
            if direct_candidate is not None:
                return [direct_candidate]
            portable_candidate = (
                AgentPluginMarketplaceAdapter().direct_root_plugin_candidate(
                    source_root
                )
            )
            return [portable_candidate] if portable_candidate is not None else []
        candidates: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            package_id = str(entry.get("name") or "").strip()
            if not package_id:
                continue
            package_path, source_path, source_results, source_metadata = (
                self.resolve_external_package_source(
                    source_root,
                    entry,
                    package_id,
                )
            )
            artifact_adapter: MarketplaceTargetClientAdapter = self
            if package_path is not None and (package_path / "plugin.json").is_file():
                artifact_adapter = AgentPluginMarketplaceAdapter()
            manifest = (
                artifact_adapter.read_manifest(package_path)
                if package_path is not None
                else {}
            )
            validation_results = [
                *source_results,
                *(
                    []
                    if package_path is None
                    else artifact_adapter.validate_package(
                        package_path,
                        package_id=package_id,
                    )
                ),
                *artifact_adapter.validate_catalog_metadata(
                    entry,
                    manifest,
                    str(manifest_path.relative_to(source_root)),
                ),
            ]
            candidates.append(
                {
                    "id": f"{self.target_client}:{package_id}",
                    "target_client": self.target_client,
                    "packageFormat": artifact_adapter.package_format,
                    "packageId": package_id,
                    "version": str(
                        entry.get("version") or manifest.get("version") or "1.0.0"
                    ),
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
                    "validationSeverity": self.highest_severity(validation_results),
                    "validationResults": validation_results,
                    "sourceMetadata": source_metadata,
                }
            )
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
            if (
                isinstance(raw_source_type, str)
                and raw_source_type.strip()
                and raw_source_type.strip() != "local"
            ):
                source_type = raw_source_type.strip()
                raw_url = raw_source.get("url")
                raw_repo = raw_source.get("repo")
                url = (
                    raw_url.strip()
                    if isinstance(raw_url, str) and raw_url.strip()
                    else (
                        self.github_repo_url(raw_repo)
                        if isinstance(raw_repo, str) and raw_repo.strip()
                        else source_type
                    )
                )
                raw_path = raw_source.get("path")
                path = (
                    raw_path.strip()
                    if isinstance(raw_path, str) and raw_path.strip()
                    else None
                )
                raw_ref = raw_source.get("ref")
                raw_sha = raw_source.get("sha")
                return (
                    None,
                    self.remote_source_path(url, path),
                    [],
                    self.remote_source_metadata(
                        source_type=source_type,
                        url=url,
                        path=path,
                        ref=(
                            raw_ref.strip()
                            if isinstance(raw_ref, str) and raw_ref.strip()
                            else None
                        ),
                        sha=(
                            raw_sha.strip()
                            if isinstance(raw_sha, str) and raw_sha.strip()
                            else None
                        ),
                    ),
                )
            raw_path = raw_source.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                source_value = raw_path.strip()
        if self.is_remote_source_value(source_value):
            return (
                None,
                source_value,
                [],
                self.remote_source_metadata(
                    source_type="url",
                    url=source_value,
                ),
            )
        source_path = Path(source_value)
        candidate = (source_root / source_path).resolve()
        try:
            candidate.relative_to(source_root.resolve())
        except ValueError:
            return (
                None,
                source_value,
                [
                    self.validation_result(
                        code="marketplace.validation.path_escape",
                        file_path=source_value,
                        details={"packageId": package_id},
                    )
                ],
                {},
            )
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
        listing = super().import_listing_entry(
            source_root, source_package_id, target_package_id
        )
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

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        names = set(super().indexed_resource_names(package_path))
        if (package_path / "hooks.json").exists() or (
            package_path / "hooks" / "hooks.json"
        ).exists():
            names.add("hooks")
        return sorted(names)


class AgentPluginMarketplaceAdapter(BaseMarketplaceTargetClientAdapter):
    """Portable Agent Plugins 1.0.0 artifact grammar adapter."""

    target_client: MarketplaceTargetClient = "codex"
    package_format: MarketplacePackageFormat = "agent-plugin/1.0.0"
    user_copy_target_client: MarketplaceTargetClient = "codex"
    manifest_required_fields = ("$schema", "name")

    def validate_component_projection(
        self,
        package_path: Path,
    ) -> list[dict[str, Any]]:
        """Portable extraction validates its complete dependency closure."""

        return []

    def manifest_path(self, package_path: Path) -> Path:
        return package_path / "plugin.json"

    def direct_root_plugin_candidate(
        self,
        source_root: Path,
    ) -> dict[str, Any] | None:
        """Return one portable root plugin candidate."""

        if not self.manifest_path(source_root).is_file():
            return None
        manifest = self.read_manifest(source_root)
        package_id = str(manifest.get("name") or source_root.name).strip()
        if not package_id:
            return None
        validation_results = self.validate_package(
            source_root,
            package_id=package_id,
        )
        return {
            "id": f"{self.target_client}:{package_id}",
            "target_client": self.target_client,
            "packageFormat": self.package_format,
            "packageId": package_id,
            "version": str(manifest.get("version") or "1.0.0"),
            "displayName": str(manifest.get("name") or package_id),
            "sourcePath": ".",
            "duplicate": False,
            "validationSeverity": self.highest_severity(validation_results),
            "validationResults": validation_results,
            "sourceMetadata": {},
        }

    def validate_package(
        self,
        package_path: Path,
        package_id: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            profile = extract_user_copy_source_profile(
                PluginPackageFormat.AGENT_PLUGIN_V1,
                package_path,
                release=PluginReleaseIdentity(
                    catalog_plugin_id=f"validation/{package_id or package_path.name}",
                    revision="0" * 64,
                ),
            )
        except (OSError, PackageSourceError, ValueError):
            return [
                self.validation_result(
                    code="marketplace.validation.invalid_manifest_shape",
                    file_path="plugin.json",
                )
            ]
        manifest = self.read_manifest(package_path)
        results: list[dict[str, Any]] = []
        if package_id is not None and manifest.get("name") != package_id:
            results.append(
                self.validation_result(
                    code="marketplace.validation.package_identity_mismatch",
                    file_path="plugin.json",
                    details={
                        "expected": package_id,
                        "actual": manifest.get("name"),
                    },
                )
            )
        for diagnostic in profile.diagnostics:
            results.append(
                self.validation_result(
                    code=f"marketplace.validation.{diagnostic.code.replace('-', '_')}",
                    severity="warning",
                    file_path=diagnostic.source_locator,
                    details={
                        key: value
                        for key, value in {
                            "resourceType": diagnostic.resource_type,
                            "resourceId": diagnostic.resource_id,
                        }.items()
                        if value is not None
                    },
                )
            )
        return results

    def indexed_resource_names(self, package_path: Path) -> list[str]:
        try:
            profile = extract_user_copy_source_profile(
                PluginPackageFormat.AGENT_PLUGIN_V1,
                package_path,
                release=PluginReleaseIdentity(
                    catalog_plugin_id=f"index/{package_path.name}",
                    revision="0" * 64,
                ),
            )
        except (OSError, PackageSourceError, ValueError):
            return []
        names = {resource.resource_type.value for resource in profile.resources}
        if "skill" in names:
            names.add("skills")
        return sorted(names)


def create_package_format_adapters() -> (
    dict[MarketplacePackageFormat, MarketplaceTargetClientAdapter]
):
    """Create artifact grammar adapters keyed by canonical package format."""

    return {
        "claude-native": ClaudeCodeMarketplaceAdapter(),
        "codex-native": CodexMarketplaceAdapter(),
        "agent-plugin/1.0.0": AgentPluginMarketplaceAdapter(),
    }


def create_marketplace_adapters() -> (
    dict[MarketplaceTargetClient, MarketplaceTargetClientAdapter]
):
    """Create Marketplace target_client adapters."""
    return {
        "claude-code": ClaudeCodeMarketplaceAdapter(),
        "codex": CodexMarketplaceAdapter(),
    }
