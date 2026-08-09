"""Private Marketplace import apply support mixin."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.modules.marketplace.models import (
    MarketplaceImportCandidate,
    MarketplaceImportSource,
    MarketplacePackageFamily,
    MarketplacePackageFamilySource,
    MarketplacePackageSummary,
    MarketplaceProviderVariant,
)
from app.modules.marketplace.providers import MarketplaceProviderAdapter

from .registry_operations import (
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplaceValidationError,
    _resource_write_locks,
)


class _MarketplaceImportApplySupport:
    """Provide import apply support behavior to the composed private kernel."""

    def _import_one_candidate(
        self,
        user_id: str,
        source_root: Path,
        source: MarketplaceImportSource,
        candidate: MarketplaceImportCandidate,
        import_metadata: dict[str, Any],
    ) -> MarketplacePackageSummary:
        target_package_id = self._target_import_package_id(candidate)
        adapter = self._get_adapter(candidate.provider)
        source_package_path, cleanup_path = self._resolve_import_candidate_source(
            user_id,
            source_root,
            candidate,
            import_metadata,
        )
        lock_key = self._marketplace_package_lock_key(
            user_id, candidate.provider, target_package_id
        )
        try:
            with _resource_write_locks.lock(lock_key):
                with self._registry_lock:
                    registry_root = self._get_registry_root(user_id)
                    target_package_path = self._resolve_package_path(
                        user_id, candidate.provider, target_package_id
                    )
                    target_parent = target_package_path.parent
                    target_parent.mkdir(parents=True, exist_ok=True)
                    target_exists = target_package_path.exists()
                    if candidate.duplicate_action == "overwrite":
                        self._validate_import_overwrite_revision(user_id, candidate)
                    elif target_exists:
                        raise MarketplaceImportSourceError(
                            "marketplace.package.already_exists"
                        )
                    component_selectors, selector_results = (
                        adapter.import_component_selectors(
                            source_root,
                            source_package_path,
                            candidate.package_id,
                        )
                    )
                    self._raise_if_validation_blocks(
                        selector_results,
                        "importSelectors",
                    )
                    if component_selectors:
                        for selectors in component_selectors.values():
                            for selector in selectors:
                                self._reject_import_symlinks(
                                    source_package_path / selector
                                )
                    else:
                        self._reject_import_symlinks(source_package_path)

                    staging_root = target_parent / f".import-{uuid4().hex}"
                    staging_path = staging_root / target_package_id
                    backup_path = target_parent / f".backup-{uuid4().hex}"
                    manifest_backup = self._provider_manifest_backup(
                        registry_root, adapter
                    )
                    family_backup = self._package_families_backup(registry_root)
                    promoted = False
                    backup_created = False
                    try:
                        staging_root.mkdir(parents=True, exist_ok=True)
                        self._copy_import_candidate_source(
                            source_package_path=source_package_path,
                            staging_path=staging_path,
                            component_selectors=component_selectors,
                        )
                        self._seed_manifest_from_listing(
                            adapter,
                            source_root,
                            source_package_path,
                            staging_path,
                            candidate,
                            target_package_id,
                            component_selectors=component_selectors,
                        )
                        self._rewrite_imported_manifest_name(
                            adapter, staging_path, target_package_id
                        )
                        self._write_import_source_metadata(
                            adapter, staging_path, source, candidate, target_package_id
                        )
                        if component_selectors:
                            self._raise_if_validation_blocks(
                                adapter.validate_component_projection(staging_path),
                                "importSelectors",
                            )
                        self._raise_if_validation_blocks(
                            adapter.validate_package(staging_path), "importCopy"
                        )
                        if target_exists:
                            target_package_path.rename(backup_path)
                            backup_created = True
                        staging_path.rename(target_package_path)
                        promoted = True
                        listing = adapter.import_listing_entry(
                            source_root,
                            candidate.package_id,
                            target_package_id,
                        )
                        if listing is None:
                            listing = adapter.export_listing_entry(
                                registry_root,
                                target_package_path,
                                target_package_id,
                            )
                        if listing is None:
                            raise MarketplaceImportSourceError(
                                "marketplace.import.validation.copy_failed"
                            )
                        for field_name, selectors in component_selectors.items():
                            listing[field_name] = [
                                f"./{selector}" for selector in selectors
                            ]
                        self._upsert_listing_entry_with_core(
                            adapter,
                            registry_root,
                            target_package_id,
                            listing,
                            invalidation_key=user_id,
                        )
                        self._upsert_import_family_variant(
                            registry_root,
                            source,
                            candidate,
                            target_package_id,
                            str(target_package_path.relative_to(registry_root)),
                        )
                        if backup_created:
                            shutil.rmtree(backup_path)
                        if staging_root.exists():
                            shutil.rmtree(staging_root)
                    except MarketplaceValidationError:
                        self._rollback_import_candidate(
                            target_package_path,
                            staging_path,
                            backup_path,
                            manifest_backup,
                            family_backup,
                            promoted,
                            backup_created,
                        )
                        raise
                    except Exception as exc:
                        self._rollback_import_candidate(
                            target_package_path,
                            staging_path,
                            backup_path,
                            manifest_backup,
                            family_backup,
                            promoted,
                            backup_created,
                        )
                        raise MarketplaceImportSourceError(
                            "marketplace.import.validation.copy_failed"
                        ) from exc

                    detail = self._package_reads.get_package_detail(
                        user_id, candidate.provider, target_package_id
                    )
                    if detail is None:
                        raise MarketplaceImportSourceError(
                            "marketplace.package.not_found"
                        )
                    return MarketplacePackageSummary.model_validate(
                        detail.model_dump(by_alias=True)
                    )
        finally:
            if cleanup_path is not None:
                shutil.rmtree(cleanup_path, ignore_errors=True)

    def _copy_import_candidate_source(
        self,
        *,
        source_package_path: Path,
        staging_path: Path,
        component_selectors: dict[str, list[str]],
    ) -> None:
        """Copy either a complete package or its explicit component projection."""

        if not component_selectors:
            shutil.copytree(
                source_package_path,
                staging_path,
                symlinks=False,
                ignore=shutil.ignore_patterns(".git"),
            )
            return

        staging_path.mkdir(parents=True, exist_ok=False)
        copied: set[str] = set()
        for selectors in component_selectors.values():
            for selector in selectors:
                normalized = Path(selector).as_posix()
                if normalized in copied:
                    continue
                copied.add(normalized)
                source = source_package_path / normalized
                target = staging_path / normalized
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(
                        source,
                        target,
                        symlinks=False,
                        ignore=shutil.ignore_patterns(".git"),
                    )
                else:
                    shutil.copy2(source, target)

    def _upsert_import_family_variant(
        self,
        registry_root: Path,
        source: MarketplaceImportSource,
        candidate: MarketplaceImportCandidate,
        target_package_id: str,
        registry_path: str,
    ) -> None:
        source_identity = candidate.source_identity or self._source_identity_for_import(
            source, {}
        )
        document = self._read_package_families(registry_root)
        family = next(
            (item for item in document.families if item.family_id == source_identity),
            None,
        )
        if family is None:
            family = MarketplacePackageFamily(
                familyId=source_identity,
                displayName=candidate.family_display_name or candidate.display_name,
                source=MarketplacePackageFamilySource(
                    kind=source.source_kind,
                    source=source.source.strip(),
                    normalizedUrl=source_identity,
                ),
                variants=[],
            )
            document.families.append(family)
        next_variants = [
            variant
            for variant in family.variants
            if not (
                variant.provider == candidate.provider
                and variant.package_id == target_package_id
            )
        ]
        next_variants.append(
            MarketplaceProviderVariant(
                provider=candidate.provider,
                packageId=target_package_id,
                registryPath=registry_path,
                displayName=candidate.display_name,
            )
        )
        family.variants = sorted(
            next_variants, key=lambda item: (item.provider, item.package_id)
        )
        self._write_package_families(registry_root, document)

    def _target_import_package_id(self, candidate: MarketplaceImportCandidate) -> str:
        if candidate.duplicate_action != "import-as-new":
            return candidate.package_id
        target_package_id = (candidate.new_package_id or "").strip()
        if not self._package_id_pattern.match(target_package_id):
            raise MarketplaceImportSourceError("marketplace.package.invalid_id")
        return target_package_id

    def _validate_import_overwrite_revision(
        self,
        user_id: str,
        candidate: MarketplaceImportCandidate,
    ) -> None:
        detail = self._package_reads.get_package_detail(
            user_id, candidate.provider, candidate.package_id
        )
        if detail is None:
            raise MarketplaceImportSourceError("marketplace.package.not_found")
        if candidate.local_revision != detail.revision:
            raise MarketplaceConflictError("marketplace.package.revision_conflict")

    def _reject_import_symlinks(self, package_path: Path) -> None:
        package_root = package_path.resolve()
        for path in package_path.rglob("*"):
            if path.is_symlink():
                try:
                    path.resolve(strict=True).relative_to(package_root)
                except (OSError, ValueError) as exc:
                    raise MarketplaceImportSourceError(
                        "marketplace.package.symlink_rejected"
                    ) from exc

    def _rewrite_imported_manifest_name(
        self,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        package_id: str,
    ) -> None:
        manifest_path = adapter.manifest_path(package_path)
        manifest = self._read_json(manifest_path)
        manifest["name"] = package_id
        self._write_json_with_core(manifest_path, manifest)

    def _seed_manifest_from_listing(
        self,
        adapter: MarketplaceProviderAdapter,
        source_root: Path,
        source_package_path: Path,
        package_path: Path,
        candidate: MarketplaceImportCandidate,
        target_package_id: str,
        *,
        component_selectors: dict[str, list[str]],
    ) -> None:
        """Materialize package metadata and authoritative listing selectors."""

        manifest_path = adapter.manifest_path(package_path)
        source_manifest_path = adapter.manifest_path(source_package_path)
        seeded = (
            self._read_json(manifest_path)
            if manifest_path.is_file()
            else (
                self._read_json(source_manifest_path)
                if source_manifest_path.is_file()
                else {}
            )
        )
        listing = (
            adapter.import_listing_entry(
                source_root, candidate.package_id, target_package_id
            )
            or {}
        )
        seeded["name"] = target_package_id
        for key in (
            "displayName",
            "description",
            "version",
            "author",
            "category",
            "tags",
            "keywords",
            "homepage",
            "repository",
            "license",
            "lspServers",
            "strict",
        ):
            value = listing.get(key)
            if value is not None and key not in seeded:
                seeded[key] = value
        if component_selectors:
            for field_name in ("skills", "commands", "agents", "outputStyles"):
                seeded.pop(field_name, None)
            for field_name, selectors in component_selectors.items():
                seeded[field_name] = [f"./{selector}" for selector in selectors]
        self._write_json_with_core(manifest_path, seeded)

    def _write_import_source_metadata(
        self,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        source: MarketplaceImportSource,
        candidate: MarketplaceImportCandidate,
        target_package_id: str,
    ) -> None:
        manifest_path = adapter.manifest_path(package_path)
        manifest = self._read_json(manifest_path)
        manifest["sourceType"] = "imported"
        manifest["importSource"] = {
            "provider": candidate.provider,
            "scanProvider": source.provider,
            "sourceKind": source.source_kind,
            "source": source.source,
            "packageId": candidate.package_id,
            "targetPackageId": target_package_id,
            "sourcePath": candidate.source_path,
            "sourceMetadata": candidate.source_metadata,
            "sourceIdentity": candidate.source_identity
            or self._source_identity_for_import(source, {}),
            "importedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._write_json_with_core(manifest_path, manifest)

    def _provider_manifest_backup(
        self,
        registry_root: Path,
        adapter: MarketplaceProviderAdapter,
    ) -> tuple[Path, dict[str, Any]] | None:
        try:
            manifest_path = adapter.marketplace_manifest_path(registry_root)  # type: ignore[attr-defined]
        except AttributeError:
            return None
        return (manifest_path, self._read_json(manifest_path))

    def _package_families_backup(
        self, registry_root: Path
    ) -> tuple[Path, dict[str, Any] | None]:
        path = self._package_families_path(registry_root)
        if not path.exists():
            return (path, None)
        return (path, self._read_json(path))

    def _rollback_import_candidate(
        self,
        target_path: Path,
        staging_path: Path,
        backup_path: Path,
        manifest_backup: tuple[Path, dict[str, Any]] | None,
        family_backup: tuple[Path, dict[str, Any] | None] | None,
        promoted: bool,
        backup_created: bool,
    ) -> None:
        if staging_path.exists():
            shutil.rmtree(staging_path)
        staging_root = staging_path.parent
        if staging_root.name.startswith(".import-") and staging_root.exists():
            shutil.rmtree(staging_root)
        if promoted and target_path.exists():
            shutil.rmtree(target_path)
        if backup_created and backup_path.exists():
            backup_path.rename(target_path)
        if manifest_backup is not None:
            self._write_json_with_core(manifest_backup[0], manifest_backup[1])
        if family_backup is not None:
            path, data = family_backup
            if data is None:
                path.unlink(missing_ok=True)
            else:
                self._write_json_with_core(path, data)
