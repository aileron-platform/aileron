"""Marketplace package reads workflow module."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aileron_marketplace_core import PackageSourceError
from aileron_file_core import (
    ArchiveMemoryEntry,
    BuildArchiveRequest,
    FileCoreError,
    FileLocator,
)

from app.modules.marketplace.models import (
    MarketplacePackageDetail,
    MarketplacePackageListResult,
    MarketplacePackageSummary,
    MarketplaceProvider,
)
from app.modules.marketplace.resource_mutations import (
    canonical_entry_fingerprint,
    document_resource_root,
    get_json_entry,
    load_root_document_path,
    read_json_file,
    validate_package_relative_path,
)
from app.modules.marketplace.resource_resolvers import (
    hook_source_id,
    read_hook_source,
    resolve_mcp_owner,
    resolve_mcp_owners,
    resolve_hook_sources,
)

from .kernel import _MarketplaceRegistrySupport
from .registry_operations import (
    MarketplaceConflictError,
    MarketplacePathError,
    MarketplaceValidationError,
    _marketplace_path_exclusion,
)


class MarketplacePackageReadModel(_MarketplaceRegistrySupport):
    """Query packages and produce immutable package projections."""

    def list_packages(
        self,
        user_id: str,
        *,
        provider: MarketplaceProvider | None = None,
        q: str | None = None,
        category: str | None = None,
        features: list[str] | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> MarketplacePackageListResult:
        """Scan provider registry files and return package summaries."""
        root = self._get_registry_root(user_id)
        items, fingerprint = self._get_package_index(user_id, root)
        filtered = self._filter_packages(
            items,
            provider=provider,
            q=q,
            category=category,
            features=features or [],
        )
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        start = (page - 1) * page_size
        paged = filtered[start : start + page_size]
        total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
        return MarketplacePackageListResult(
            items=paged,
            total=len(filtered),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            categories=sorted({item.category for item in items if item.category}),
            source_types=sorted({item.source_type for item in items}),
            validation_severities=sorted({item.validation_severity for item in items}),
            registry_fingerprint=fingerprint,
        )

    def refresh_package_index(self, user_id: str) -> MarketplacePackageListResult:
        """Force a package index rescan and return the refreshed list."""
        self._invalidate_package_index(user_id)
        return self.list_packages(user_id)

    def refresh_package_overview(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> dict[str, bool]:
        """Clear one package overview so the next GET reads the filesystem."""
        if (
            self.get_package_detail(
                user_id,
                provider,
                package_id,
                use_cache=False,
            )
            is None
        ):
            raise FileNotFoundError("marketplace.package.not_found")
        self._invalidate_package_overview(user_id, provider, package_id)
        return {"refreshed": True}

    def get_package_operation_summary(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> MarketplacePackageSummary | None:
        """Build one package summary using operation-gating lifecycle rules."""

        candidate = self._get_package_candidate(user_id, provider, package_id)
        if candidate is None:
            return None
        return candidate.summary.model_copy(
            update={
                "lifecycle_status": candidate.operation_lifecycle_status,
            }
        )

    def get_package_detail(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        *,
        use_cache: bool = True,
    ) -> MarketplacePackageDetail | None:
        """Return a cached summary-first package overview."""
        cache_key = self.cache.package_overview_key(provider, package_id)
        if use_cache:
            cached = self.cache.get_json(cache_key)
            if cached is not None:
                try:
                    return MarketplacePackageDetail.model_validate(cached)
                except (TypeError, ValueError):
                    pass

        candidate = self._get_package_candidate(user_id, provider, package_id)
        if candidate is None:
            if not use_cache:
                self._invalidate_package_overview(user_id, provider, package_id)
            return None
        typed_catalog_entry = self._catalog_entry(
            self._get_registry_root(user_id),
            provider,
            package_id,
        )
        summary = self._with_family_metadata(
            self._get_registry_root(user_id),
            [candidate.summary],
            package_manifests={
                (provider, package_id): candidate.manifest,
            },
        )[0]
        catalog = {
            "name": summary.display_name,
            "description": summary.description,
            "version": summary.version,
            "category": (
                typed_catalog_entry.category
                if typed_catalog_entry is not None
                else None
            ),
            "tags": (
                typed_catalog_entry.tags if typed_catalog_entry is not None else []
            ),
        }
        detail = MarketplacePackageDetail(
            **summary.model_dump(by_alias=True),
            catalog_metadata=catalog,
            manifest_metadata=candidate.manifest,
            metadata_conflict=any(
                result.code == "marketplace.validation.metadata_conflict"
                for result in candidate.validation_results
            ),
            validation_results=candidate.validation_results,
        )
        self.cache.set_json(cache_key, detail.model_dump(by_alias=True, mode="json"))
        return detail

    def load_root_document(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        path = load_root_document_path(provider, package_path)
        return {
            "path": path.name,
            "content": path.read_text(encoding="utf-8") if path.exists() else "",
        }

    def list_documents(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        resource_type: str,
    ) -> list[dict[str, Any]]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        root = document_resource_root(provider, resource_type)
        directory = package_path / root
        if not directory.is_dir():
            return []
        documents: list[dict[str, Any]] = []
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative_path = path.relative_to(package_path).as_posix()
            documents.append(
                {
                    "id": relative_path,
                    "title": path.stem,
                    "path": relative_path,
                    "resourceType": resource_type,
                }
            )
        return documents

    def load_document(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        resource_type: str,
        path: str,
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        relative_path = validate_package_relative_path(path)
        root = document_resource_root(provider, resource_type)
        if not str(relative_path).startswith(f"{root}/"):
            raise MarketplacePathError("marketplace.package.path_escape")
        target = package_path / str(relative_path)
        if not target.is_file():
            raise FileNotFoundError("marketplace.resource.not_found")
        return {
            "id": str(relative_path),
            "title": target.stem,
            "path": str(relative_path),
            "resourceType": resource_type,
            "content": self._read_text_file(target),
        }

    def list_mcp_servers(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> list[dict[str, Any]]:
        detail = self.get_package_detail(user_id, provider, package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        package_path = self._resolve_package_path(user_id, provider, package_id)
        items: list[dict[str, Any]] = []
        for binding in resolve_mcp_owners(package_path, provider):
            name = binding.name
            owner = binding.owner
            current = get_json_entry(
                read_json_file(package_path / owner.file_path),
                owner.json_pointer,
            )
            if not isinstance(current, dict):
                continue
            items.append(
                {
                    "name": name,
                    "path": owner.file_path,
                    "baseEntryFingerprint": canonical_entry_fingerprint(current),
                    "ownerFilePath": owner.file_path,
                }
            )
        return items

    def get_mcp_server(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        name: str,
        owner_file_path: str,
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        owner = resolve_mcp_owner(
            package_path,
            provider,
            name,
            owner_file_path=owner_file_path,
        )
        if owner is None:
            raise FileNotFoundError("marketplace.resource.not_found")
        owner_path = package_path / owner.file_path
        data = read_json_file(owner_path)
        current = get_json_entry(data, owner.json_pointer)
        if current is None:
            raise FileNotFoundError("marketplace.resource.not_found")
        return {
            "name": name,
            "path": owner.file_path,
            "server": current,
            "baseEntryFingerprint": canonical_entry_fingerprint(current),
            "ownerFilePath": owner.file_path,
        }

    def get_basic_metadata(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> dict[str, Any]:
        detail = self.get_package_detail(user_id, provider, package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        return {
            "revision": detail.revision,
            "displayName": detail.display_name,
            "description": detail.description or "",
            "catalogMetadata": detail.catalog_metadata,
            "manifestMetadata": detail.manifest_metadata,
            "lifecycleStatus": detail.lifecycle_status,
            "validationResults": detail.validation_results,
        }

    def get_hooks(
        self, user_id: str, provider: MarketplaceProvider, package_id: str
    ) -> dict[str, Any]:
        detail = self.get_package_detail(user_id, provider, package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        package_path = self._resolve_package_path(user_id, provider, package_id)
        owners, diagnostics = resolve_hook_sources(package_path, provider)
        fatal_codes = {
            "source-reference-invalid",
            "source-missing",
            "source-not-allowed",
            "duplicate-resource-id",
        }
        fatal_diagnostics = [
            {
                "code": item["code"],
                "messageKey": f"marketplace.hooks.diagnostics.{item['code']}",
                "sourceLocator": item["sourceLocator"],
            }
            for item in diagnostics
            if item["code"] in fatal_codes
        ]
        if fatal_diagnostics:
            raise MarketplaceValidationError(fatal_diagnostics)

        sources: list[dict[str, Any]] = []
        for owner in owners:
            source_id = hook_source_id(owner)
            path = package_path / owner.file_path
            source_diagnostics = [
                {
                    "code": item["code"],
                    "messageKey": f"marketplace.hooks.diagnostics.{item['code']}",
                    "sourceLocator": item["sourceLocator"],
                }
                for item in diagnostics
                if (
                    item["sourceLocator"] == owner.file_path
                    or item["sourceLocator"].startswith(f"{owner.file_path}#")
                )
            ]
            try:
                raw_content, _, native_content = read_hook_source(
                    package_path, owner
                )
            except (OSError, UnicodeError, json.JSONDecodeError, PackageSourceError) as exc:
                raw_content = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
                native_content = None
                code = exc.code if isinstance(exc, PackageSourceError) else "source-document-invalid"
                source_diagnostics.append(
                    {
                        "code": code,
                        "messageKey": f"marketplace.hooks.diagnostics.{code}",
                        "sourceLocator": owner.file_path,
                    }
                )
            if any(
                item["code"] == "source-document-invalid"
                for item in source_diagnostics
            ):
                native_content = None
            sources.append(
                {
                    "sourceId": source_id,
                    "sourceType": "inline" if not owner.standalone_file else "file",
                    "path": owner.file_path,
                    "manifestPointer": owner.json_pointer,
                    "content": raw_content,
                    "nativeContent": native_content,
                    "writable": True,
                    "diagnostics": source_diagnostics,
                }
            )
        return {
            "revision": detail.revision,
            "sources": sources,
            "hookCapabilities": {
                "mode": "sources",
                "groups": [source["sourceId"] for source in sources],
            },
        }

    def get_readme(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> dict[str, Any]:
        """Load sanitized README content only when the UI opens it."""
        detail = self.get_package_detail(user_id, provider, package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        package_path = self._resolve_package_path(user_id, provider, package_id)
        readme_path = self._discover_readme_path(package_path)
        return {
            "revision": detail.revision,
            "path": (
                readme_path.relative_to(package_path).as_posix()
                if readme_path is not None
                else None
            ),
            "content": self._read_sanitized_readme_markdown(package_path),
        }

    def list_skill_files(
        self, user_id: str, provider: MarketplaceProvider, package_id: str
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        root = package_path / "skills"
        if not root.is_dir():
            return {"path": "skills", "scope": None, "nodes": [], "total": 0}
        nodes = [
            self._marketplace_file_node(package_path, path)
            for path in sorted(root.rglob("*"))
        ]
        return {"path": "skills", "scope": None, "nodes": nodes, "total": len(nodes)}

    def read_skill_file(
        self, user_id: str, provider: MarketplaceProvider, package_id: str, path: str
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        relative_path = self._validate_skill_relative_path(path)
        target = package_path / relative_path
        if not target.is_file():
            raise FileNotFoundError("marketplace.resource.not_found")
        return self._marketplace_file_content_response(relative_path, target)

    def list_package_files_tree(
        self, user_id: str, provider: MarketplaceProvider, package_id: str
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        nodes = [
            self._marketplace_file_node(package_path, path)
            for path in sorted(package_path.rglob("*"))
        ]
        return {"path": "", "scope": None, "nodes": nodes, "total": len(nodes)}

    def read_package_file(
        self, user_id: str, provider: MarketplaceProvider, package_id: str, path: str
    ) -> dict[str, Any]:
        package_path = self._resolve_package_path(user_id, provider, package_id)
        relative_path = self._validate_package_read_relative_path(path)
        target = package_path / relative_path
        if not target.is_file():
            raise FileNotFoundError("marketplace.resource.not_found")
        return self._marketplace_file_content_response(relative_path, target)

    def export_package(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        revision: str,
    ) -> bytes:
        """Export a package as a provider-native import-source zip archive."""
        detail = self.get_package_detail(user_id, provider, package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        if detail.revision != revision:
            raise MarketplaceConflictError("marketplace.package.revision_conflict")
        package_path = self._resolve_package_path(user_id, provider, package_id)
        if not package_path.exists():
            raise FileNotFoundError("marketplace.package.not_found")
        registry_root = self._get_registry_root(user_id)
        adapter = self._get_adapter(provider)
        self._raise_if_validation_blocks(
            adapter.validate_package(package_path), "export"
        )
        listing = adapter.export_listing_entry(registry_root, package_path, package_id)
        marketplace_manifest = getattr(adapter, "marketplace_manifest", None)
        extra_entries: list[ArchiveMemoryEntry] = []
        archive_root = ""
        if listing is not None and isinstance(marketplace_manifest, str):
            extra_entries.append(
                ArchiveMemoryEntry(
                    archive_path=marketplace_manifest,
                    content=(
                        json.dumps(
                            self._export_marketplace_manifest(
                                registry_root, adapter, listing
                            ),
                            indent=2,
                        )
                        + "\n"
                    ).encode("utf-8"),
                )
            )
            archive_root = (Path("plugins") / package_id).as_posix()
        path_exclusion = _marketplace_path_exclusion()
        selected_paths = sorted(
            child.name
            for child in package_path.iterdir()
            if not path_exclusion.is_excluded(Path(child.name))
        )
        try:
            result = self._file_engine_for_root(
                root=package_path,
                registry_root=registry_root,
            ).build_archive_bytes(
                BuildArchiveRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    paths=selected_paths,
                    archive_root=archive_root,
                    extra_entries=extra_entries,
                    reject_symlinks=True,
                )
            )
        except FileCoreError as exc:
            if exc.code == "SYMLINK_REJECTED":
                raise MarketplacePathError(
                    "marketplace.package.symlink_rejected"
                ) from exc
            raise
        return result.content
