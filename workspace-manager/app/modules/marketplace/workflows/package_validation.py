"""Private Marketplace validation support mixin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aileron_file_core import FileCoreError
from aileron_marketplace_core import (
    provider_resource_name_contract,
    resolve_user_copy_profile,
)

from app.modules.marketplace.models import (
    MarketplaceProvider,
    MarketplaceValidationResult,
)

from .registry_operations import (
    MarketplaceConflictError,
    MarketplacePathError,
    MarketplaceValidationAction,
    MarketplaceValidationError,
)


class _MarketplaceValidationSupport:
    """Provide validation support behavior to the composed private kernel."""

    def _package_lifecycle_status_from_summary(
        self,
        manifest_metadata: dict[str, Any],
        has_required_resources: bool,
        validation_results: list[MarketplaceValidationResult] | list[dict[str, Any]],
    ) -> str:
        has_error = any(
            (
                result.severity
                if isinstance(result, MarketplaceValidationResult)
                else result.get("severity")
            )
            == "error"
            for result in validation_results
        )
        manifest_name = manifest_metadata.get("name")
        if not isinstance(manifest_name, str) or not manifest_name.strip():
            return "draft"

        return "draft" if has_error or not has_required_resources else "ready"

    def _package_has_required_resources(
        self,
        provider: MarketplaceProvider,
        package_path: Path,
    ) -> bool:
        """Check that at least one native provider resource contains data."""
        profile = resolve_user_copy_profile(provider, package_path)

        def has_content(path: Path) -> bool:
            try:
                return path.is_file() and bool(path.read_bytes().strip())
            except OSError:
                return False

        for resource in profile.resources:
            source = package_path / resource.source_locator
            if has_content(source):
                return True
            if source.is_dir() and has_content(source / "SKILL.md"):
                return True
        contract = provider_resource_name_contract(provider)
        if has_content(package_path / contract.root_document_name):
            return True
        resource_directories = {
            directory.source_name for directory in contract.indexed_directories
        }
        resource_directories.update(
            {
                "agents",
                "apps",
                "commands",
                "hooks",
                "mcp",
                "output-styles",
                "policies",
                "prompts",
                "rules",
                "skills",
            }
        )
        for directory_name in resource_directories:
            resource_root = package_path / directory_name
            if resource_root.is_dir() and any(
                has_content(path) for path in resource_root.rglob("*")
            ):
                return True
        return False

    def _catalog_metadata_missing_validation(
        self,
        root: Path,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> dict[str, Any]:
        return {
            "severity": "error",
            "code": "marketplace.validation.catalog_metadata_missing",
            "messageKey": "marketplace.validation.catalog_metadata_missing",
            "filePath": self._catalog_path(root).relative_to(root).as_posix(),
            "details": {
                "provider": provider,
                "packageId": package_id,
            },
        }

    def _validate_registry_paths_after_mutation(
        self,
        registry_root: Path,
        paths: list[str],
    ) -> None:
        packages: set[tuple[MarketplaceProvider, str]] = set()
        for path in paths:
            parts = Path(path).parts
            if len(parts) < 3 or parts[1] != "plugins":
                continue
            provider = parts[0]
            if provider not in self.adapters:
                continue
            packages.add((provider, parts[2]))  # type: ignore[arg-type]
        for provider, package_id in sorted(packages):
            package_path = registry_root / provider / "plugins" / package_id
            adapter = self._get_adapter(provider)
            self._raise_if_validation_blocks(
                adapter.validate_package(package_path),
                "save",
            )

    def _validate_registry_file_after_restore(self, relative_path: str) -> None:
        parts = Path(relative_path).parts
        if len(parts) < 3 or parts[1] != "plugins":
            return
        provider = parts[0]
        if provider not in self.adapters:
            return
        package_id = parts[2]
        package_path = (
            self.storage_root / "registry" / provider / "plugins" / package_id
        )
        adapter = self._get_adapter(provider)  # type: ignore[arg-type]
        self._raise_if_validation_blocks(adapter.validate_package(package_path), "save")

    @staticmethod
    def _raise_skill_archive_error(exc: FileCoreError) -> None:
        if exc.code == "FILE_ALREADY_EXISTS":
            raise MarketplaceConflictError(
                "marketplace.resource.entry_conflict"
            ) from exc
        if exc.code == "FILE_TOO_LARGE":
            raise MarketplacePathError("marketplace.resource.file_too_large") from exc
        if exc.code in {
            "INVALID_ARCHIVE",
            "INVALID_ARCHIVE_ENTRY",
            "ARCHIVE_LIMIT_EXCEEDED",
        }:
            raise MarketplacePathError("marketplace.resource.archive_invalid") from exc
        raise MarketplacePathError("marketplace.resource.upload_failed") from exc

    def _validate_listing_entry(
        self, package_id: str, listing: dict[str, Any]
    ) -> list[dict[str, Any]]:
        listing_name = listing.get("name")
        if (
            isinstance(listing_name, str)
            and listing_name
            and listing_name != package_id
        ):
            return [
                {
                    "severity": "error",
                    "code": "marketplace.validation.package_identity_mismatch",
                    "messageKey": "marketplace.validation.package_identity_mismatch",
                    "details": {
                        "packageId": package_id,
                        "listingName": listing_name,
                    },
                }
            ]
        return []

    def _validation_blocks_action(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> bool:
        """Return whether validation results block the requested action."""
        return bool(self._blocking_validation_results(validation_results, action))

    def _blocking_validation_results(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> list[dict[str, Any]]:
        """Return validation results that block the requested action."""
        if action not in {"create", "save", "export", "install", "importCopy"}:
            return []
        return [
            result for result in validation_results if result.get("severity") == "error"
        ]

    def _raise_if_validation_blocks(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> None:
        blocking_results = self._blocking_validation_results(validation_results, action)
        if blocking_results:
            raise MarketplaceValidationError(blocking_results)

    def _package_path_has_ready_resource(
        self,
        provider: MarketplaceProvider,
        package_path: Path,
    ) -> bool:
        return self._package_has_required_resources(provider, package_path)
