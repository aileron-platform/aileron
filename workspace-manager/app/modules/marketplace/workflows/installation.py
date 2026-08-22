"""Marketplace installation workflow module."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from aileron_file_core import FileOperationEngine
from app.db import models as db_models
from app.modules.marketplace.models import (
    MarketplacePackageFormat,
    MarketplacePackageSummary,
    MarketplaceTargetClient,
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyApplyResult,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
)
from app.modules.marketplace.user_copy import MarketplaceUserCopyService

from .kernel import _MarketplaceRegistrySupport
from .package_reads import MarketplacePackageReadModel
from .registry_operations import (
    MarketplaceManagedPackageResolution,
    MarketplaceImportSourceError,
    _MarketplaceRegistryContext,
)
from .settings_activity import MarketplaceSettingsActivityWorkflow


class _MarketplaceUserCopyRegistryAdapter:
    """Adapt internal Marketplace modules to the user-copy registry port."""

    def __init__(
        self,
        installation: MarketplaceInstallationWorkflow,
        package_reads: MarketplacePackageReadModel,
        settings_activity: MarketplaceSettingsActivityWorkflow,
    ) -> None:
        self.installation = installation
        self.package_reads = package_reads
        self.settings_activity = settings_activity

    def _resolve_user_copy_catalog_entry(
        self,
        user_id: str,
        catalog_plugin_id: str,
        package_format: MarketplacePackageFormat,
        target_client: MarketplaceTargetClient,
    ) -> MarketplacePackageSummary | None:
        root = self.package_reads._get_registry_root(user_id)
        items, _ = self.package_reads._get_package_index(user_id, root)
        matches = [
            item
            for item in items
            if item.catalog_plugin_id == catalog_plugin_id
            and item.package_format == package_format
            and item.target_client == target_client
        ]
        if len(matches) > 1:
            raise RuntimeError("Duplicate catalog plugin identity")
        if not matches:
            return None
        item = matches[0]
        return self.package_reads.get_package_operation_summary(
            user_id,
            item.target_client,
            item.package_id,
            item.package_format,
        )

    @contextmanager
    def open_user_copy_source(
        self,
        user_id: str,
        catalog_plugin_id: str,
        package_format: MarketplacePackageFormat,
        target_client: MarketplaceTargetClient,
    ) -> Iterator[tuple[MarketplacePackageSummary, Path]]:
        summary = self._resolve_user_copy_catalog_entry(
            user_id, catalog_plugin_id, package_format, target_client
        )
        if summary is None:
            raise FileNotFoundError("marketplace.user_copy.package_not_found")
        with self.installation._package_source_lock(
            user_id,
            summary.target_client,
            summary.package_id,
        ):
            current = self._resolve_user_copy_catalog_entry(
                user_id, catalog_plugin_id, package_format, target_client
            )
            if current is None:
                raise FileNotFoundError("marketplace.user_copy.package_not_found")
            yield current, self.installation._resolve_package_path(
                user_id,
                current.target_client,
                current.package_id,
                current.package_format,
            )

    def file_engine_for_root(
        self,
        *,
        root: Path,
        registry_root: Path,
        invalidation_key: str,
    ) -> FileOperationEngine:
        return self.installation._file_engine_for_root(
            root=root,
            registry_root=registry_root,
            invalidation_key=invalidation_key,
        )

    def resolve_install_runtime(self, workspace_id: str) -> dict[str, str | None]:
        return self.installation.resolve_install_runtime(workspace_id)

    def record_activity(self, user_id: str, **kwargs: Any) -> Any:
        return self.settings_activity.record_activity(user_id, **kwargs)


class MarketplaceInstallationWorkflow(_MarketplaceRegistrySupport):
    """Resolve managed sources and coordinate plugin or user-copy delivery."""

    def __init__(
        self,
        *,
        context: _MarketplaceRegistryContext,
        package_reads: MarketplacePackageReadModel,
        settings_activity: MarketplaceSettingsActivityWorkflow,
    ) -> None:
        super().__init__(_context=context)
        self._package_reads = package_reads
        self._settings_activity = settings_activity

    def preflight_user_copy(
        self,
        user_id: str,
        request: MarketplaceUserCopyRequest,
    ) -> MarketplaceUserCopyPreflightResult:
        return self._user_copy_service().preflight(user_id, request)

    def apply_user_copy(
        self,
        user_id: str,
        request: MarketplaceUserCopyApplyRequest,
    ) -> MarketplaceUserCopyApplyResult:
        return self._user_copy_service().apply(user_id, request)

    def _user_copy_service(self) -> MarketplaceUserCopyService:
        if self.db is None:
            raise RuntimeError("Marketplace user-copy persistence is unavailable")
        return MarketplaceUserCopyService(
            self.db,
            _MarketplaceUserCopyRegistryAdapter(
                self,
                self._package_reads,
                self._settings_activity,
            ),
            runtime_client=self.marketplace_runtime_client,
        )

    def resolve_managed_package_for_install(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_format: MarketplacePackageFormat,
        package_id: str,
        version: str,
    ) -> MarketplaceManagedPackageResolution:
        """Resolve the configured registry Git source and let the CLI install it."""

        with self._registry_lock:
            root = self._get_registry_root(user_id)
            self._require_registry_git_repo(root)
            summary = self._package_reads.get_package_operation_summary(
                user_id,
                target_client,
                package_id,
                package_format,
            )
            if summary is None:
                raise FileNotFoundError("marketplace.package.not_found")
            catalog = self._read_catalog(root)
            remote_url = self._git_output(
                root,
                ["remote", "get-url", "origin"],
            )
            if not remote_url:
                raise MarketplaceImportSourceError("marketplace.git.remote_required")
            self._validate_registry_remote(remote_url)
            registry_ref = self._git_output(
                root,
                ["branch", "--show-current"],
            ) or "HEAD"

            return MarketplaceManagedPackageResolution(
                marketplace_id=catalog.marketplace_id,
                remote_url=remote_url,
                registry_ref=registry_ref,
            )

    def resolve_install_runtime(self, workspace_id: str) -> dict[str, str | None]:
        if self.db is None:
            return {
                "runtimeUrl": None,
                "errorCode": "marketplace.install.runtime_unavailable",
            }
        workspace = (
            self.db.query(db_models.Workspace)
            .filter(db_models.Workspace.id == workspace_id)
            .first()
        )
        if workspace is None:
            return {
                "runtimeUrl": None,
                "errorCode": "marketplace.install.workspace_not_found",
            }
        if workspace.runtime_status != "running":
            return {
                "runtimeUrl": None,
                "errorCode": "marketplace.install.workspace_not_running",
            }
        if not workspace.runtime_instance_id:
            return {
                "runtimeUrl": None,
                "runtimeInstanceId": None,
                "errorCode": "marketplace.install.runtime_unavailable",
            }
        runtime_url = workspace.runtime_internal_url
        if not runtime_url:
            return {
                "runtimeUrl": None,
                "errorCode": "marketplace.install.runtime_url_missing",
            }
        return {
            "runtimeUrl": runtime_url.rstrip("/"),
            "runtimeInstanceId": workspace.runtime_instance_id,
            "errorCode": None,
        }
