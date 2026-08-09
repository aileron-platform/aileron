"""Private Marketplace catalog support mixin."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.modules.marketplace.models import (
    MarketplaceCatalogPackage,
    MarketplacePackageFamily,
    MarketplacePackageSummary,
    MarketplaceProvider,
    MarketplaceRegistryCatalog,
    MarketplaceRegistryRootMetadataSavePayload,
    MarketplaceValidationResult,
)
from app.modules.marketplace.providers import MarketplaceProviderAdapter

from .registry_operations import (
    MarketplaceImportSourceError,
    _MarketplacePackageCandidate,
)


class _MarketplaceCatalogSupport:
    """Provide catalog support behavior to the composed private kernel."""

    def _get_package_candidate(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> _MarketplacePackageCandidate | None:
        root = self._get_registry_root(user_id)
        if not self._catalog_path(root).is_file() or not self._package_id_pattern.match(
            package_id
        ):
            return None
        package_path = self._resolve_package_path(user_id, provider, package_id)
        if not package_path.is_dir():
            return None
        catalog = self._read_catalog(root)
        catalog_entry = next(
            (
                entry
                for entry in catalog.packages
                if entry.provider == provider and entry.package_id == package_id
            ),
            None,
        )
        candidate = self._build_package_candidate(
            root,
            self._get_adapter(provider),
            package_path,
            catalog_entry,
        )
        return candidate

    def _get_package_index(
        self,
        user_id: str,
        root: Path,
    ) -> tuple[list[MarketplacePackageSummary], str]:
        cache_key = self.cache.registry_index_key()
        cached = self.cache.get_json(cache_key)
        if isinstance(cached, dict):
            try:
                items = [
                    MarketplacePackageSummary.model_validate(item)
                    for item in cached["items"]
                ]
                fingerprint = str(cached["fingerprint"])
                return items, fingerprint
            except (KeyError, TypeError, ValueError):
                pass

        items = self._scan_registry(root)
        serialized_items = [
            item.model_dump(by_alias=True, mode="json") for item in items
        ]
        fingerprint = sha256(
            json.dumps(
                serialized_items,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:16]
        self.cache.set_json(
            cache_key,
            {"items": serialized_items, "fingerprint": fingerprint},
        )
        return items, fingerprint

    def _build_package_candidate(
        self,
        root: Path,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        catalog_entry: MarketplaceCatalogPackage | None,
    ) -> _MarketplacePackageCandidate:
        """Build one summary and its lifecycle inputs with one provider read."""

        package_id = package_path.name
        manifest = adapter.read_manifest(package_path)  # type: ignore[attr-defined]
        package_validation = [
            *adapter.validate_package(package_path),
            *adapter.validate_component_projection(package_path),
        ]
        summary_validation = list(package_validation)
        if catalog_entry is None:
            summary_validation.append(
                self._catalog_metadata_missing_validation(
                    root,
                    adapter.provider,
                    package_id,
                )
            )

        summary = MarketplacePackageSummary(
            provider=adapter.provider,
            package_type="plugin",
            package_id=package_id,
            display_name=str(
                manifest.get("displayName")
                or manifest.get("display_name")
                or manifest.get("name")
                or package_id
            ),
            version=(
                str(manifest["version"])
                if isinstance(manifest.get("version"), str)
                else None
            ),
            description=(
                str(manifest["description"])
                if isinstance(manifest.get("description"), str)
                else None
            ),
            category=catalog_entry.category if catalog_entry is not None else None,
            tags=catalog_entry.tags if catalog_entry is not None else [],
            source_type=adapter.source_type_from_metadata(manifest),  # type: ignore[attr-defined]
            indexed_resource_names=adapter.indexed_resource_names(package_path),  # type: ignore[attr-defined]
            validation_severity=adapter.highest_severity(summary_validation),  # type: ignore[attr-defined]
            registry_path=package_path.relative_to(root).as_posix(),
            revision=adapter.revision_for_paths(  # type: ignore[attr-defined]
                [self._catalog_path(root), package_path]
            ),
            updated_at=adapter.updated_at_for_paths(  # type: ignore[attr-defined]
                [self._catalog_path(root), package_path]
            ),
        )
        catalog_payload = (
            catalog_entry.model_dump(by_alias=True)
            if catalog_entry is not None
            else None
        )
        catalog_validation = list(
            adapter.validate_catalog_metadata(catalog_payload, manifest)  # type: ignore[attr-defined]
        )
        has_required_resources = self._package_has_required_resources(
            adapter.provider,
            package_path,
        )
        lifecycle_status = self._package_lifecycle_status_from_summary(
            manifest,
            has_required_resources,
            [*summary_validation, *catalog_validation],
        )
        operation_lifecycle_status = self._package_lifecycle_status_from_summary(
            manifest,
            has_required_resources,
            [*package_validation, *catalog_validation],
        )
        summary = summary.model_copy(update={"lifecycle_status": lifecycle_status})
        return _MarketplacePackageCandidate(
            summary=summary,
            operation_lifecycle_status=operation_lifecycle_status,
            manifest=manifest,
            validation_results=[
                MarketplaceValidationResult.model_validate(result)
                for result in [*summary_validation, *catalog_validation]
            ],
        )

    def _scan_registry(self, root: Path) -> list[MarketplacePackageSummary]:
        if not root.exists() or not self._catalog_path(root).exists():
            return []
        catalog = self._read_catalog(root)
        catalog_entries = {
            (entry.provider, entry.package_id): entry for entry in catalog.packages
        }
        candidates: list[_MarketplacePackageCandidate] = []
        for adapter in self.adapters.values():
            plugins_root = root / adapter.provider / "plugins"
            if not plugins_root.is_dir():
                continue
            for package_path in sorted(
                path for path in plugins_root.iterdir() if path.is_dir()
            ):
                candidates.append(
                    self._build_package_candidate(
                        root,
                        adapter,
                        package_path,
                        catalog_entries.get((adapter.provider, package_path.name)),
                    )
                )
        packages = self._with_family_metadata(
            root,
            [candidate.summary for candidate in candidates],
            package_manifests={
                (candidate.summary.provider, candidate.summary.package_id): (
                    candidate.manifest
                )
                for candidate in candidates
            },
        )
        return sorted(packages, key=lambda item: (item.provider, item.package_id))

    def _with_family_metadata(
        self,
        root: Path,
        packages: list[MarketplacePackageSummary],
        *,
        package_manifests: (
            dict[tuple[MarketplaceProvider, str], dict[str, Any]] | None
        ) = None,
    ) -> list[MarketplacePackageSummary]:
        document = self._read_package_families(root)
        inferred = self._infer_imported_families(
            root,
            packages,
            document,
            package_manifests=package_manifests,
        )
        families = {
            family.family_id: family for family in [*document.families, *inferred]
        }
        by_variant: dict[tuple[str, str], MarketplacePackageFamily] = {}
        for family in families.values():
            for variant in family.variants:
                by_variant[(variant.provider, variant.package_id)] = family
        enriched: list[MarketplacePackageSummary] = []
        for item in packages:
            family = by_variant.get((item.provider, item.package_id))
            if family is None:
                enriched.append(item)
                continue
            # Only cross-provider builds of the same package are real variants.
            # Other packages persisted under the same source-scoped family are
            # unrelated peers and must be excluded from this summary's variants.
            same_package_variants = [
                variant
                for variant in family.variants
                if variant.package_id == item.package_id
            ]
            enriched.append(
                item.model_copy(
                    update={
                        "family_id": family.family_id,
                        "family_display_name": family.display_name,
                        "source_identity": family.source.normalized_url
                        or family.source.source,
                        "variants": same_package_variants,
                    }
                )
            )
        return enriched

    def _filter_packages(
        self,
        items: list[MarketplacePackageSummary],
        *,
        provider: MarketplaceProvider | None,
        q: str | None,
        category: str | None,
        features: list[str],
    ) -> list[MarketplacePackageSummary]:
        normalized_q = (q or "").strip().lower()
        normalized_features = {feature for feature in features if feature}
        result: list[MarketplacePackageSummary] = []
        for item in items:
            if provider and item.provider != provider:
                continue
            if category and category != "all" and item.category != category:
                continue
            indexed_terms = set(item.tags) | set(item.indexed_resource_names)
            if normalized_features and not normalized_features.issubset(indexed_terms):
                continue
            if normalized_q:
                haystack = " ".join(
                    [
                        item.provider,
                        item.package_id,
                        item.display_name,
                        item.description or "",
                        item.category or "",
                        *item.tags,
                        *item.indexed_resource_names,
                    ]
                ).lower()
                if normalized_q not in haystack:
                    continue
            result.append(item)
        return result

    def _strip_root_metadata(
        self, listing: dict[str, Any]
    ) -> tuple[dict[str, Any], bool]:
        root_keys = {"owner", "plugins"}
        stripped = any(key in listing for key in root_keys)
        return {
            key: value for key, value in listing.items() if key not in root_keys
        }, stripped

    def _discover_readme_path(self, package_path: Path) -> Path | None:
        candidates = [
            "README.md",
            "README.MD",
            "Readme.md",
            "readme.md",
            "README.mdx",
            "README.MDX",
            "readme.mdx",
        ]
        for name in candidates:
            path = package_path / name
            if path.exists() and path.is_file():
                self._assert_relative_to(path, package_path)
                return path
        return None

    def _read_sanitized_readme_markdown(self, package_path: Path) -> str:
        readme_path = self._discover_readme_path(package_path)
        if readme_path is None:
            return ""
        return self._sanitize_readme_markdown(readme_path.read_text(encoding="utf-8"))

    def _sanitize_readme_markdown(self, markdown: str) -> str:
        cleaned = self._unsafe_readme_block_pattern.sub("", markdown)
        cleaned = self._unsafe_readme_single_tag_pattern.sub("", cleaned)
        cleaned = self._readme_event_attr_pattern.sub("", cleaned)
        cleaned = self._readme_javascript_link_pattern.sub(r"\1#\2", cleaned)
        return cleaned

    def _get_provider_root(self, user_id: str, provider: MarketplaceProvider) -> Path:
        """Return a provider root path under the user's registry."""
        root = self._get_registry_root(user_id)
        return root / provider

    def _ensure_provider_roots(self, root: Path) -> None:
        for adapter in self.adapters.values():
            adapter.ensure_roots(root)

    def _catalog_path(self, root: Path) -> Path:
        return root / "marketplace" / "catalog.json"

    def _read_catalog(self, root: Path) -> MarketplaceRegistryCatalog:
        path = self._catalog_path(root)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return MarketplaceRegistryCatalog.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.registry.catalog_invalid"
            ) from exc

    def _initial_marketplace_id(self, display_name: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", display_name.strip().lower())
        normalized = normalized.strip("-")[:64].rstrip("-")
        candidate = normalized or "marketplace"
        MarketplaceRegistryCatalog(
            schema_version=1,
            marketplace_id=candidate,
            display_name=display_name,
            owner={
                "name": "Marketplace Maintainer",
                "email": "marketplace@example.local",
            },
            description="",
            publish_branch="main",
            packages=[],
        )
        return candidate

    def _catalog_entry(
        self,
        root: Path,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> MarketplaceCatalogPackage | None:
        catalog = self._read_catalog(root)
        return next(
            (
                entry
                for entry in catalog.packages
                if entry.provider == provider and entry.package_id == package_id
            ),
            None,
        )

    def _persist_catalog_and_publish_manifests(
        self,
        root: Path,
        catalog: MarketplaceRegistryCatalog,
        *,
        invalidation_key: str,
    ) -> None:
        """Persist the catalog and both derived manifests as one file transaction."""

        catalog_path = self._catalog_path(root)
        previous_catalog = catalog_path.read_bytes() if catalog_path.is_file() else None
        try:
            self._generating_publish_manifests = True
            self._write_json_with_core(
                catalog_path,
                catalog.model_dump(by_alias=True),
                invalidation_key=invalidation_key,
            )
            self._generating_publish_manifests = False
            self._generate_publish_manifests(
                root,
                catalog,
                invalidation_key=invalidation_key,
            )
        except Exception:
            self._generating_publish_manifests = True
            try:
                if previous_catalog is None:
                    catalog_path.unlink(missing_ok=True)
                else:
                    self._write_bytes_with_core(
                        catalog_path,
                        previous_catalog,
                        operation="restore",
                        invalidation_key=invalidation_key,
                    )
            finally:
                self._generating_publish_manifests = False
            raise
        finally:
            self._generating_publish_manifests = False

    def _generate_publish_manifests(
        self,
        root: Path,
        catalog: MarketplaceRegistryCatalog,
        *,
        invalidation_key: str,
    ) -> None:
        """Generate both provider manifests from one canonical catalog snapshot."""

        if self._generating_publish_manifests:
            return
        self._write_publish_manifests(
            root,
            self._build_publish_manifests(root, catalog),
            invalidation_key=invalidation_key,
        )

    def _build_publish_manifests(
        self,
        root: Path,
        catalog: MarketplaceRegistryCatalog,
    ) -> dict[MarketplaceProvider, dict[str, Any]]:
        """Build both complete provider manifests without mutating the registry."""

        manifests: dict[MarketplaceProvider, dict[str, Any]] = {
            "claude-code": {
                "name": catalog.marketplace_id,
                "owner": catalog.owner.model_dump(),
                "description": catalog.description,
                "plugins": [],
            },
            "codex": {
                "name": catalog.marketplace_id,
                "interface": {"displayName": catalog.display_name},
                "description": catalog.description,
                "plugins": [],
            },
        }
        entries = sorted(
            catalog.packages,
            key=lambda item: (item.provider, item.package_id),
        )
        for entry in entries:
            adapter = self._get_adapter(entry.provider)
            package_path = adapter.package_path(root, entry.package_id)  # type: ignore[attr-defined]
            if not package_path.is_dir():
                continue
            manifest = adapter.read_manifest(package_path)  # type: ignore[attr-defined]
            validation = adapter.validate_package(package_path)
            if any(item.get("severity") == "error" for item in validation):
                continue
            if not self._package_path_has_ready_resource(entry.provider, package_path):
                continue
            publish_entry: dict[str, Any] = {
                "name": entry.package_id,
                "description": manifest.get("description"),
            }
            for key in ("displayName", "version"):
                if manifest.get(key) is not None:
                    publish_entry[key] = manifest[key]
            if entry.category is not None:
                publish_entry["category"] = entry.category
            if entry.tags:
                publish_entry["tags"] = entry.tags
            if entry.provider == "claude-code":
                publish_entry["source"] = f"./claude-code/plugins/{entry.package_id}"
            else:
                publish_entry["source"] = {
                    "source": "local",
                    "path": f"./codex/plugins/{entry.package_id}",
                }
                publish_entry["category"] = entry.category or "uncategorized"
                publish_entry["policy"] = (
                    entry.policy.model_dump()
                    if entry.policy is not None
                    else {
                        "installation": "AVAILABLE",
                        "authentication": "ON_INSTALL",
                    }
                )
            manifests[entry.provider]["plugins"].append(publish_entry)

        return manifests

    def _write_publish_manifests(
        self,
        root: Path,
        manifests: dict[MarketplaceProvider, dict[str, Any]],
        *,
        invalidation_key: str,
    ) -> None:
        """Write both provider manifests as one rollback-safe transaction."""

        manifest_paths = (
            self._claude_manifest_path(root),
            self._codex_manifest_path(root),
        )
        previous = {
            path: path.read_bytes() if path.is_file() else None
            for path in manifest_paths
        }
        self._generating_publish_manifests = True
        try:
            self._write_json_with_core(
                manifest_paths[0],
                manifests["claude-code"],
                invalidation_key=invalidation_key,
            )
            self._write_json_with_core(
                manifest_paths[1],
                manifests["codex"],
                invalidation_key=invalidation_key,
            )
        except Exception:
            for path, content in previous.items():
                try:
                    if content is None:
                        path.unlink(missing_ok=True)
                    else:
                        self._write_bytes_with_core(
                            path,
                            content,
                            operation="restore",
                            invalidation_key=invalidation_key,
                        )
                except Exception:
                    continue
            raise
        finally:
            self._generating_publish_manifests = False

    def _regenerate_publish_manifests_after_mutation(
        self,
        root: Path,
        *,
        invalidation_key: str,
    ) -> None:
        if self._generating_publish_manifests or not self._catalog_path(root).is_file():
            return
        self._generate_publish_manifests(
            root,
            self._read_catalog(root),
            invalidation_key=invalidation_key,
        )

    def _default_metadata(self) -> MarketplaceRegistryRootMetadataSavePayload:
        return MarketplaceRegistryRootMetadataSavePayload(
            name="Local Marketplace Registry",
            owner={
                "name": "Marketplace Maintainer",
                "email": "marketplace@example.local",
            },
            description="Provider-separated Marketplace package registry.",
        )

    def _claude_manifest_path(self, root: Path) -> Path:
        adapter = self._get_adapter("claude-code")
        return adapter.marketplace_manifest_path(root)  # type: ignore[attr-defined]

    def _codex_manifest_path(self, root: Path) -> Path:
        adapter = self._get_adapter("codex")
        return adapter.marketplace_manifest_path(root)  # type: ignore[attr-defined]
