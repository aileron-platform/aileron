"""Managed Registry validation support mixin."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aileron_file_core import FileCoreError
from aileron_marketplace_core import (
    package_format_resource_name_contract,
    resolve_user_copy_profile,
)

from app.modules.marketplace.models import (
    MarketplacePackageFormat,
    MarketplaceTargetClient,
)
from app.modules.marketplace.target_clients import (
    create_package_format_adapters,
    package_format_from_storage_key,
)

from .registry_operations import (
    MarketplaceConflictError,
    MarketplacePathError,
    MarketplaceValidationAction,
    MarketplaceValidationError,
)


class _MarketplaceValidationSupport:
    """Provide validation support behavior to the composed registry kernel."""

    def _package_has_required_resources(
        self,
        package_format: MarketplacePackageFormat,
        package_path: Path,
    ) -> bool:
        """Check that at least one native target_client resource contains data."""
        if package_format == "agent-plugin/1.0.0":
            return (package_path / "plugin.json").is_file()
        profile = resolve_user_copy_profile(package_format, package_path)

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
        contract = package_format_resource_name_contract(package_format)
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
        target_client: MarketplaceTargetClient,
        package_id: str,
    ) -> dict[str, Any]:
        return {
            "severity": "error",
            "code": "marketplace.validation.catalog_metadata_missing",
            "messageKey": "marketplace.validation.catalog_metadata_missing",
            "filePath": self._catalog_path(root).relative_to(root).as_posix(),
            "details": {
                "target_client": target_client,
                "packageId": package_id,
            },
        }

    def _validate_registry_paths_after_mutation(
        self,
        registry_root: Path,
        paths: list[str],
    ) -> None:
        packages: set[tuple[MarketplaceTargetClient, MarketplacePackageFormat, str]] = (
            set()
        )
        for path in paths:
            parts = Path(path).parts
            if len(parts) < 4 or parts[1] != "plugins":
                continue
            target_client = parts[0]
            if target_client not in self.adapters:
                continue
            try:
                package_format = package_format_from_storage_key(parts[2])
            except ValueError:
                continue
            packages.add((target_client, package_format, parts[3]))  # type: ignore[arg-type]
        for target_client, package_format, package_id in sorted(packages):
            adapter = create_package_format_adapters()[package_format]
            package_path = adapter.package_path(registry_root, package_id)
            self._raise_if_validation_blocks(
                adapter.validate_package(package_path),
                "save",
            )

    def _validate_registry_file_after_restore(self, relative_path: str) -> None:
        parts = Path(relative_path).parts
        if len(parts) < 4 or parts[1] != "plugins":
            return
        target_client = parts[0]
        if target_client not in self.adapters:
            return
        try:
            package_format = package_format_from_storage_key(parts[2])
        except ValueError:
            return
        package_id = parts[3]
        adapter = create_package_format_adapters()[package_format]
        package_path = adapter.package_path(self.storage_root / "registry", package_id)
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
        if action not in {"create", "save", "export", "importSelectors", "importCopy"}:
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
        package_format: MarketplacePackageFormat,
        package_path: Path,
    ) -> bool:
        return self._package_has_required_resources(package_format, package_path)
