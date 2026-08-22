"""Managed Registry importing planning support mixin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.modules.marketplace.target_clients import create_package_format_adapters
from app.modules.marketplace.models import (
    MarketplacePackageFamiliesDocument,
    MarketplacePackageFamily,
    MarketplacePackageFamilySource,
    MarketplacePackageFormat,
    MarketplacePackageSummary,
    MarketplaceTargetClient,
    MarketplacePackageVariant,
    MarketplaceImportCandidate,
    MarketplaceImportFailedCandidate,
    MarketplaceImportSource,
)

from .registry_operations import (
    MarketplacePathError,
)


class _MarketplaceImportPlanningSupport:
    """Provide importing planning behavior to the composed registry kernel."""

    def _scan_import_candidates(
        self,
        source: MarketplaceImportSource,
        source_root: Path,
    ) -> list[dict[str, Any]]:
        target_clients = (
            list(self.adapters)
            if source.target_client == "all"
            else [source.target_client]
        )
        candidates: list[dict[str, Any]] = []
        for target_client in target_clients:
            adapter = self._get_adapter(target_client)
            try:
                candidates.extend(adapter.scan_external_source(source_root))
            except NotImplementedError:
                continue
        return candidates

    def _with_duplicate_import_state(
        self,
        user_id: str,
        candidate: MarketplaceImportCandidate,
        source: MarketplaceImportSource | None = None,
        import_metadata: dict[str, Any] | None = None,
    ) -> MarketplaceImportCandidate:
        root = self._get_registry_root(user_id)
        source_identity = candidate.source_identity
        family: MarketplacePackageFamily | None = None
        if source is not None:
            source_identity = self._source_identity_for_import(
                source, import_metadata or {}
            )
            family = self._find_family_by_source_identity(root, source_identity)
        if family is None and source_identity:
            family = self._find_family_by_source_identity(root, source_identity)

        summaries, _ = self._get_package_index(user_id, root)
        existing = next(
            (item for item in summaries if item.package_id == candidate.package_id),
            None,
        )
        existing_same_variant = existing is not None
        unrelated_duplicate = False
        if existing_same_variant and family is not None:
            unrelated_duplicate = not any(
                variant.target_client == candidate.target_client
                and variant.package_format == candidate.package_format
                and variant.package_id == candidate.package_id
                for variant in family.variants
            )
        variant_status = self._candidate_variant_status(
            candidate,
            family,
            existing_same_variant=existing_same_variant,
            unrelated_duplicate=unrelated_duplicate,
        )
        family_updates: dict[str, Any] = {
            "source_identity": source_identity,
            "variant_status": variant_status,
        }
        if family is not None:
            family_updates.update(
                {
                    "family_id": family.family_id,
                    "family_display_name": family.display_name,
                    "variants": family.variants,
                }
            )
        if not existing_same_variant:
            return candidate.model_copy(update=family_updates)
        return candidate.model_copy(
            update={
                **family_updates,
                "duplicate": True,
                "local_revision": existing.revision if existing else None,
            }
        )

    def _with_batch_variant_metadata(
        self,
        source: MarketplaceImportSource,
        import_metadata: dict[str, Any],
        candidates: list[MarketplaceImportCandidate],
    ) -> list[MarketplaceImportCandidate]:
        source_identity = self._source_identity_for_import(source, import_metadata)
        if not source_identity:
            return candidates

        # Group peers by package_id: distinct target-client/package-format builds
        # are variants, while unrelated package IDs from one source stay separate.
        peers_by_package_id: dict[str, list[MarketplacePackageVariant]] = {}
        for candidate in candidates:
            bucket = peers_by_package_id.setdefault(candidate.package_id, [])
            if any(
                item.target_client == candidate.target_client
                and item.package_format == candidate.package_format
                for item in bucket
            ):
                continue
            bucket.append(
                MarketplacePackageVariant(
                    target_client=candidate.target_client,
                    package_format=candidate.package_format,
                    package_id=candidate.package_id,
                    display_name=candidate.display_name,
                )
            )

        merged: list[MarketplaceImportCandidate] = []
        for candidate in candidates:
            peer_variants = peers_by_package_id.get(candidate.package_id, [])
            variants = self._merge_variants(candidate.variants, peer_variants)
            merged.append(
                candidate.model_copy(
                    update={
                        "family_id": candidate.family_id or source_identity,
                        "family_display_name": candidate.family_display_name
                        or candidate.display_name,
                        "source_identity": candidate.source_identity or source_identity,
                        "variants": variants,
                    }
                )
            )
        return merged

    def _merge_variants(
        self,
        existing: list[MarketplacePackageVariant],
        incoming: list[MarketplacePackageVariant],
    ) -> list[MarketplacePackageVariant]:
        merged: list[MarketplacePackageVariant] = []
        seen: set[tuple[str, str]] = set()
        for variant in [*existing, *incoming]:
            key = (variant.target_client, variant.package_format)
            if key in seen:
                continue
            seen.add(key)
            merged.append(variant)
        return merged

    def _candidate_variant_status(
        self,
        candidate: MarketplaceImportCandidate,
        family: MarketplacePackageFamily | None,
        *,
        existing_same_variant: bool,
        unrelated_duplicate: bool,
    ) -> str:
        if candidate.validation_severity == "error":
            return "invalid"
        if unrelated_duplicate:
            return "unrelated-duplicate"
        if existing_same_variant:
            return "duplicate-variant"
        if family is not None:
            return "add-variant"
        return "new-family"

    def _import_candidate_key(
        self, candidate: MarketplaceImportCandidate
    ) -> tuple[str, str, str]:
        return (candidate.target_client, candidate.package_id, candidate.source_path)

    def _merge_import_candidate_action(
        self,
        scanned: MarketplaceImportCandidate | None,
        requested: MarketplaceImportCandidate,
    ) -> MarketplaceImportCandidate:
        if scanned is None:
            return requested
        return scanned.model_copy(
            update={
                "import_options": requested.import_options,
                "local_revision": requested.local_revision or scanned.local_revision,
            }
        )

    def _failed_import_candidate(
        self,
        candidate: MarketplaceImportCandidate,
        error_code: str,
        *,
        stage: str,
        source: str | None,
        destination: str | None,
        category: str,
    ) -> MarketplaceImportFailedCandidate:
        return MarketplaceImportFailedCandidate.model_validate(
            {
                **candidate.model_dump(by_alias=True),
                "errorCode": error_code,
                "stage": stage,
                "source": source,
                "destination": destination,
                "category": category,
            }
        )

    def _infer_imported_families(
        self,
        root: Path,
        packages: list[MarketplacePackageSummary],
        existing: MarketplacePackageFamiliesDocument,
        *,
        package_manifests: dict[
            tuple[MarketplaceTargetClient, MarketplacePackageFormat, str],
            dict[str, Any],
        ] = None,
    ) -> list[MarketplacePackageFamily]:
        existing_ids = {family.family_id for family in existing.families}
        grouped: dict[str, MarketplacePackageFamily] = {}
        for item in packages:
            adapter = create_package_format_adapters()[item.package_format]
            manifest = (
                package_manifests.get(
                    (item.target_client, item.package_format, item.package_id)
                )
                if package_manifests is not None
                else None
            )
            package_path = adapter.package_path(root, item.package_id)
            if manifest is None:
                manifest = adapter.read_manifest(package_path)  # type: ignore[attr-defined]
            import_source = manifest.get("importSource")
            if (
                not isinstance(import_source, dict)
                and item.package_format == "agent-plugin/1.0.0"
            ):
                import_source = self._read_json(
                    package_path / ".aileron" / "import.json"
                )
            if not isinstance(import_source, dict):
                continue
            source_kind = str(import_source.get("sourceKind") or "git")
            source_value = str(import_source.get("source") or "").strip()
            if source_kind not in {"git", "local"} or not source_value:
                continue
            source = MarketplaceImportSource(
                target_client=item.target_client,
                sourceKind=source_kind,
                source=source_value,
            )
            stored_identity = import_source.get("sourceIdentity")
            source_identity = (
                stored_identity.strip()
                if isinstance(stored_identity, str) and stored_identity.strip()
                else self._source_identity_for_import(source, {})
            )
            if not source_identity or source_identity in existing_ids:
                continue
            family = grouped.get(source_identity)
            if family is None:
                family = MarketplacePackageFamily(
                    familyId=source_identity,
                    displayName=item.display_name,
                    source=MarketplacePackageFamilySource(
                        kind=source.source_kind,
                        source=source.source,
                        normalizedUrl=source_identity,
                    ),
                    variants=[],
                )
                grouped[source_identity] = family
            family.variants.append(self._variant_for_summary(item))
        return list(grouped.values())

    def _variant_for_summary(
        self, item: MarketplacePackageSummary
    ) -> MarketplacePackageVariant:
        return MarketplacePackageVariant(
            target_client=item.target_client,
            package_format=item.package_format,
            packageId=item.package_id,
            registryPath=item.registry_path,
            displayName=item.display_name,
        )

    def _package_families_path(self, root: Path) -> Path:
        return root / ".marketplace" / "package-families.json"

    def _read_package_families(self, root: Path) -> MarketplacePackageFamiliesDocument:
        path = self._package_families_path(root)
        if not path.exists():
            return MarketplacePackageFamiliesDocument()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return MarketplacePackageFamiliesDocument()
        try:
            document = MarketplacePackageFamiliesDocument.model_validate(data)
        except ValueError:
            return MarketplacePackageFamiliesDocument()
        return self._validated_package_families(root, document)

    def _write_package_families(
        self, root: Path, document: MarketplacePackageFamiliesDocument
    ) -> None:
        document = self._validated_package_families(root, document)
        path = self._package_families_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_json_with_core(path, document.model_dump(by_alias=True))

    def _validated_package_families(
        self,
        root: Path,
        document: MarketplacePackageFamiliesDocument,
    ) -> MarketplacePackageFamiliesDocument:
        families: list[MarketplacePackageFamily] = []
        seen_family_ids: set[str] = set()
        for family in document.families:
            if not family.family_id or family.family_id in seen_family_ids:
                continue
            seen_family_ids.add(family.family_id)
            variants: list[MarketplacePackageVariant] = []
            seen_variants: set[tuple[str, str]] = set()
            for variant in family.variants:
                key = (variant.target_client, variant.package_format)
                if key in seen_variants:
                    continue
                seen_variants.add(key)
                try:
                    package_path = create_package_format_adapters()[
                        variant.package_format
                    ].package_path(root, variant.package_id)
                    self._assert_relative_to(package_path, root)
                except (MarketplacePathError, ValueError):
                    continue
                registry_path = variant.registry_path or str(
                    package_path.relative_to(root)
                )
                variants.append(
                    variant.model_copy(update={"registry_path": registry_path})
                )
            families.append(family.model_copy(update={"variants": variants}))
        return MarketplacePackageFamiliesDocument(families=families)

    def _find_family_by_source_identity(
        self, root: Path, source_identity: str | None
    ) -> MarketplacePackageFamily | None:
        if not source_identity:
            return None
        for family in self._read_package_families(root).families:
            if (
                family.family_id == source_identity
                or family.source.normalized_url == source_identity
            ):
                return family
        return None

    def _source_identity_for_import(
        self,
        source: MarketplaceImportSource,
        import_metadata: dict[str, Any] | None = None,
    ) -> str:
        if source.source_kind == "git":
            return self._normalize_git_source_identity(source.source)
        root = import_metadata.get("sourceRoot") if import_metadata else None
        return f"local:{root or source.source.strip()}"

    def _normalize_git_source_identity(self, source: str) -> str:
        value = source.strip()
        scp_like = self._git_scp_like_pattern.match(value)
        if scp_like:
            host = scp_like.group("host").lower()
            repo_path = scp_like.group("path")
        else:
            parsed = urlparse(value)
            host = (parsed.hostname or parsed.netloc).lower()
            repo_path = parsed.path
        repo_path = repo_path.strip().lstrip("/")
        if repo_path.endswith(".git"):
            repo_path = repo_path[:-4]
        repo_path = repo_path.rstrip("/")
        return f"{host}/{repo_path}" if host and repo_path else value
