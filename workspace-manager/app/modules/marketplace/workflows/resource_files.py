"""Private Marketplace resource support mixin."""

from __future__ import annotations

import base64
import binascii
import json
import tempfile
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from aileron_file_core import (
    FileCoreError,
    FileLocator,
    ListFilesRequest,
    ReadTextRequest,
    RootedFileAdapter,
    StaticRootResolver,
    SyncTreeItem,
    SyncTreeRequest,
    WriteBytesRequest,
    WriteTextRequest,
)

from app.modules.marketplace.models import (
    MarketplaceCatalogPackage,
    MarketplaceFeatureContentItem,
    MarketplacePackageCreateRequest,
    MarketplacePackageDetail,
    MarketplacePackageFile,
    MarketplacePackageMutationResult,
    MarketplaceProvider,
)
from app.modules.marketplace.providers import MarketplaceProviderAdapter
from app.modules.marketplace.resource_mutations import (
    validate_package_relative_path,
)

from .registry_operations import (
    MarketplaceConflictError,
    MarketplacePathError,
    _is_generated_marketplace_registry_path,
    _marketplace_path_exclusion,
)


class _MarketplaceResourceSupport:
    """Provide resource support behavior to the composed private kernel."""

    def _mutation_result_for_package(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        *,
        path: str,
        owner_file_path: str | None = None,
        base_entry_fingerprint: str | None = None,
    ) -> MarketplacePackageMutationResult:
        """Return the canonical resource identity and fresh package revision."""
        self._invalidate_package_overview(user_id, provider, package_id)
        summary = self._package_reads.get_package_operation_summary(
            user_id,
            provider,
            package_id,
        )
        if summary is None:
            raise FileNotFoundError("marketplace.package.not_found")
        return MarketplacePackageMutationResult(
            success=True,
            path=path,
            revision=summary.revision,
            owner_file_path=owner_file_path,
            base_entry_fingerprint=base_entry_fingerprint,
        )

    def _get_package_detail_for_mutation(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> MarketplacePackageDetail | None:
        """Read the current filesystem revision without trusting Redis."""
        return self._package_reads.get_package_detail(
            user_id,
            provider,
            package_id,
            use_cache=False,
        )

    def _feature_items_from_directory(
        self, package_path: Path, relative_directory: str
    ) -> list[MarketplaceFeatureContentItem]:
        directory = package_path / relative_directory
        if not directory.is_dir():
            return []
        engine = self._file_engine_for_root(
            root=package_path,
            registry_root=self.storage_root / "registry",
        )
        listed = engine.list_files(
            ListFilesRequest(
                locator=FileLocator(domain="marketplace", resource_id="registry"),
                path=relative_directory,
                include_content=True,
            )
        )
        return [
            MarketplaceFeatureContentItem(
                id=item.path,
                name=Path(item.path).stem,
                path=item.path,
                content=item.content if not item.binary else "",
                description=self._feature_description_from_content(
                    item.content if not item.binary else None
                ),
                data=self._feature_data_from_content(item.name, item.content),
            )
            for item in listed.items
        ]

    def _feature_description_from_content(self, content: str | None) -> str | None:
        if not content:
            return None
        for line in content.splitlines()[:20]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                if key.strip().lower() == "description":
                    return value.strip().strip("\"'")
        return None

    def _feature_data_from_content(
        self,
        name: str,
        content: str | None,
    ) -> dict[str, Any] | None:
        suffix = Path(name).suffix.lower()
        if content is None:
            return None
        if suffix == ".json":
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                return None
            return data if isinstance(data, dict) else None
        return None

    def _read_text_file(self, path: Path) -> str:
        root = self._core_write_root_for_path(path)
        try:
            result = self._file_engine_for_root(
                root=root,
                registry_root=self.storage_root / "registry",
            ).read_text(
                ReadTextRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=path.resolve().relative_to(root.resolve()).as_posix(),
                )
            )
        except (FileCoreError, ValueError):
            return ""
        return result.content

    def _string_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    def _sync_package_files(
        self,
        package_path: Path,
        package_files: list[MarketplacePackageFile],
        *,
        invalidation_key: str = "registry",
    ) -> None:
        package_path.mkdir(parents=True, exist_ok=True)
        registry_root = self.storage_root / "registry"
        engine = self._file_engine_for_root(
            root=package_path,
            registry_root=registry_root,
            invalidation_key=invalidation_key,
        )
        locator = FileLocator(domain="marketplace", resource_id="registry")
        sync_items: list[SyncTreeItem] = []

        for package_file in package_files:
            relative_path = self._resolve_package_file_path_with_core(package_file.path)
            try:
                content = (
                    base64.b64decode(package_file.content, validate=True)
                    if package_file.binary
                    else package_file.content.encode("utf-8")
                )
            except (ValueError, binascii.Error) as exc:
                raise MarketplacePathError(
                    "marketplace.package.invalid_binary_content"
                ) from exc
            sync_items.append(SyncTreeItem(path=relative_path, content=content))

        result = engine.sync_tree(
            SyncTreeRequest(
                locator=locator,
                files=sync_items,
            )
        )
        failed = next(
            (item for item in result.results if item.status == "failed"), None
        )
        if failed is not None:
            raise MarketplacePathError("marketplace.package.path_escape")

    def _is_generated_registry_path(self, relative_path: str) -> bool:
        return _is_generated_marketplace_registry_path(relative_path)

    def _normalize_registry_file_path_with_core(self, path: str) -> str:
        try:
            safe_path = RootedFileAdapter(
                root_resolver=StaticRootResolver(self.storage_root / "registry"),
                path_exclusion=_marketplace_path_exclusion(),
            ).resolve_path(
                FileLocator(domain="marketplace", resource_id="registry"),
                path,
            )
        except FileCoreError as exc:
            raise MarketplacePathError("marketplace.package.path_escape") from exc
        if safe_path.relative_path == ".":
            raise MarketplacePathError("marketplace.package.path_escape")
        return safe_path.relative_path

    def _core_write_root_for_path(self, path: Path) -> Path:
        registry_root = (self.storage_root / "registry").resolve()
        resolved = path.resolve()
        try:
            registry_relative = resolved.relative_to(registry_root).as_posix()
        except ValueError:
            return path.parent
        if self._is_generated_registry_path(registry_relative):
            return path.parent
        return registry_root

    def _write_text_with_core(
        self,
        path: Path,
        content: str,
        *,
        operation: str = "write",
        invalidation_key: str = "registry",
    ) -> None:
        root = self._core_write_root_for_path(path)
        relative_path = path.resolve().relative_to(root.resolve()).as_posix()
        try:
            self._file_engine_for_root(
                root=root,
                registry_root=self.storage_root / "registry",
                invalidation_key=invalidation_key,
                package_targets={
                    target
                    for target in [self._package_cache_target_for_path(path)]
                    if target is not None
                },
            ).write_text(
                WriteTextRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=relative_path,
                    content=content,
                )
            )
        except FileCoreError as exc:
            raise MarketplacePathError("marketplace.package.path_escape") from exc

    def _write_bytes_with_core(
        self,
        path: Path,
        content: bytes,
        *,
        operation: str = "restore",
        invalidation_key: str = "registry",
        revision: str | None = None,
    ) -> None:
        root = self._core_write_root_for_path(path)
        try:
            self._file_engine_for_root(
                root=root,
                registry_root=self.storage_root / "registry",
                invalidation_key=invalidation_key,
                package_targets={
                    target
                    for target in [self._package_cache_target_for_path(path)]
                    if target is not None
                },
            ).write_bytes(
                WriteBytesRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=path.resolve().relative_to(root.resolve()).as_posix(),
                    content=content,
                    operation=operation,
                    expected_version_id=revision,
                )
            )
        except FileCoreError as exc:
            if exc.code == "CONTENT_CONFLICT":
                raise MarketplaceConflictError(
                    "marketplace.registry.history.content_conflict"
                ) from exc
            raise MarketplacePathError("marketplace.package.path_escape") from exc

    def _write_json_with_core(
        self,
        path: Path,
        data: dict[str, Any],
        *,
        invalidation_key: str = "registry",
    ) -> None:
        self._write_text_with_core(
            path,
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            invalidation_key=invalidation_key,
        )

    @staticmethod
    def _json_file_matches_document(
        path: Path,
        data: dict[str, Any],
    ) -> bool:
        expected = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode(
            "utf-8"
        )
        try:
            return path.read_bytes() == expected
        except OSError:
            return False

    def _upsert_listing_entry_with_core(
        self,
        adapter: MarketplaceProviderAdapter,
        registry_root: Path,
        package_id: str,
        entry: dict[str, Any],
        invalidation_key: str = "registry",
    ) -> None:
        catalog = self._read_catalog(registry_root)
        provider = adapter.provider
        existing = next(
            (
                item
                for item in catalog.packages
                if item.provider == provider and item.package_id == package_id
            ),
            None,
        )
        raw_policy = entry.get("policy")
        policy = (
            raw_policy
            if isinstance(raw_policy, dict)
            else (
                existing.policy.model_dump()
                if existing is not None and existing.policy is not None
                else None
            )
        )
        next_entry = MarketplaceCatalogPackage(
            provider=provider,
            package_id=package_id,
            category=(
                str(entry["category"])
                if isinstance(entry.get("category"), str)
                else existing.category if existing is not None else None
            ),
            tags=(
                [value for value in entry.get("tags", []) if isinstance(value, str)]
                if isinstance(entry.get("tags"), list)
                else existing.tags if existing is not None else []
            ),
            policy=policy,
        )
        packages = [
            item
            for item in catalog.packages
            if not (item.provider == provider and item.package_id == package_id)
        ]
        packages.append(next_entry)
        next_catalog = catalog.model_copy(update={"packages": packages})
        self._persist_catalog_and_publish_manifests(
            registry_root,
            next_catalog,
            invalidation_key=invalidation_key,
        )

    def _remove_listing_entry_with_core(
        self,
        adapter: MarketplaceProviderAdapter,
        registry_root: Path,
        package_id: str,
        invalidation_key: str = "registry",
    ) -> None:
        catalog = self._read_catalog(registry_root)
        next_catalog = catalog.model_copy(
            update={
                "packages": [
                    entry
                    for entry in catalog.packages
                    if not (
                        entry.provider == adapter.provider
                        and entry.package_id == package_id
                    )
                ]
            }
        )
        self._persist_catalog_and_publish_manifests(
            registry_root,
            next_catalog,
            invalidation_key=invalidation_key,
        )

    def _create_package_scaffold_with_core(
        self,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        request: MarketplacePackageCreateRequest,
        invalidation_key: str,
    ) -> None:
        manifest_path = adapter.manifest_path(package_path)
        if request.provider == "codex":
            manifest = {
                "name": request.package_id,
                "version": "0.1.0",
                "description": request.description,
            }
        else:
            manifest = {"name": request.package_id}
        self._write_json_with_core(
            manifest_path,
            manifest,
            invalidation_key=invalidation_key,
        )
        self._write_text_with_core(
            package_path / "README.md",
            f"# {request.display_name}\n\n{request.description}\n",
            invalidation_key=invalidation_key,
        )

    def _resolve_package_file_path_with_core(self, path: str) -> str:
        try:
            safe_path = RootedFileAdapter(
                root_resolver=StaticRootResolver(Path(tempfile.gettempdir())),
                path_exclusion=_marketplace_path_exclusion(),
            ).resolve_path(
                FileLocator(domain="marketplace", resource_id="package"),
                path,
            )
        except FileCoreError as exc:
            raise MarketplacePathError("marketplace.package.path_escape") from exc
        if safe_path.relative_path == ".":
            raise MarketplacePathError("marketplace.package.path_escape")
        return safe_path.relative_path

    def _marketplace_file_node(self, package_path: Path, path: Path) -> dict[str, Any]:
        relative_path = path.relative_to(package_path).as_posix()
        node = {
            "id": relative_path,
            "name": path.name,
            "path": relative_path,
            "type": "directory" if path.is_dir() else "file",
            "hasChildren": path.is_dir() and any(path.iterdir()),
            "children": [],
        }
        if path.is_file():
            node["size"] = path.stat().st_size
        return node

    def _marketplace_file_content_response(
        self, relative_path: str, target: Path
    ) -> dict[str, Any]:
        content = self._read_text_file(target)
        return {
            "path": relative_path,
            "scope": None,
            "content": content,
            "size": len(content.encode("utf-8")),
            "updatedAt": datetime.fromtimestamp(
                target.stat().st_mtime, tz=timezone.utc
            ).isoformat(),
            "revision": sha256(content.encode("utf-8")).hexdigest(),
        }

    def _validate_skill_relative_path(self, path: str) -> str:
        try:
            relative_path = str(validate_package_relative_path(path))
        except ValueError as exc:
            raise MarketplacePathError(str(exc)) from exc
        if relative_path == "skills" or relative_path.startswith("skills/"):
            return relative_path
        raise MarketplacePathError("marketplace.package.path_escape")

    def _validate_package_read_relative_path(self, path: str) -> str:
        return str(validate_package_relative_path(path))

    def _validate_package_file_relative_path(self, path: str) -> str:
        relative_path = str(validate_package_relative_path(path))
        if relative_path == ".":
            raise MarketplacePathError("marketplace.package.path_escape")
        first_part = Path(relative_path).parts[0] if Path(relative_path).parts else ""
        if (
            first_part in self._managed_package_roots
            or relative_path in self._managed_package_roots
        ):
            raise MarketplacePathError("marketplace.package.path_escape")
        return relative_path

    def _export_marketplace_manifest(
        self,
        registry_root: Path,
        adapter: MarketplaceProviderAdapter,
        listing: dict[str, Any],
    ) -> dict[str, Any]:
        manifest: dict[str, Any] = {}
        try:
            manifest_path = adapter.marketplace_manifest_path(registry_root)  # type: ignore[attr-defined]
        except AttributeError:
            manifest_path = None
        if manifest_path is not None and manifest_path.exists():
            manifest = self._read_json(manifest_path)
        manifest["plugins"] = [listing]
        return manifest

    def _resolve_package_path(
        self, user_id: str, provider: MarketplaceProvider, package_id: str
    ) -> Path:
        """Resolve a package path and ensure it stays inside the selected provider root."""
        if not self._package_id_pattern.match(package_id):
            raise MarketplacePathError("marketplace.package.invalid_id")

        root = self._get_registry_root(user_id)
        adapter = self._get_adapter(provider)
        provider_root = self._get_provider_root(user_id, provider)
        candidate = adapter.package_path(root, package_id)

        self._assert_relative_to(candidate, root)
        self._assert_relative_to(candidate, provider_root)
        return candidate
