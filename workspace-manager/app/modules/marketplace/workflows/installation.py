"""Marketplace installation workflow module."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from aileron_file_core import FileOperationEngine
from aileron_git_core import git_allow_failure

from app.db import models as db_models
from app.modules.marketplace.models import (
    MarketplacePackageSummary,
    MarketplaceProvider,
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyApplyResult,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
)
from app.modules.marketplace.user_copy import MarketplaceUserCopyService
from .kernel import _MarketplaceRegistrySupport
from .package_reads import MarketplacePackageReadModel
from .settings_activity import MarketplaceSettingsActivityWorkflow
from .registry_operations import (
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplacePublishedPackageResolution,
    _MarketplaceRegistryContext,
)


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

    def package_source_lock(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> AbstractContextManager[None]:
        return self.installation._package_source_lock(
            user_id,
            provider,
            package_id,
        )

    def get_package_operation_summary(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> MarketplacePackageSummary | None:
        return self.package_reads.get_package_operation_summary(
            user_id,
            provider,
            package_id,
        )

    def resolve_package_path(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> Path:
        return self.installation._resolve_package_path(
            user_id,
            provider,
            package_id,
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
    """Resolve published sources and coordinate plugin or user-copy delivery."""

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

    def resolve_published_package_for_install(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
        revision: str,
    ) -> MarketplacePublishedPackageResolution:
        """Resolve an exact Ready package from the canonical remote-tracking ref."""

        with self._registry_lock:
            root = self._get_registry_root(user_id)
            self._require_registry_git_repo(root)
            summary = self._package_reads.get_package_operation_summary(
                user_id,
                provider,
                package_id,
            )
            if summary is None:
                raise FileNotFoundError("marketplace.package.not_found")
            if summary.revision != revision:
                raise MarketplaceConflictError("marketplace.package.revision_conflict")
            if summary.lifecycle_status != "ready":
                raise MarketplaceImportSourceError(
                    "marketplace.install.package_not_ready"
                )

            catalog = self._read_catalog(root)
            publish_ref = catalog.publish_branch
            remote_url = self._git_output(
                root,
                ["remote", "get-url", "origin"],
            )
            if not remote_url:
                raise MarketplaceImportSourceError("marketplace.git.remote_required")
            self._validate_registry_remote(remote_url)

            tracking_ref = f"refs/remotes/origin/{publish_ref}"
            catalog_path = self._catalog_path(root).relative_to(root).as_posix()
            package_path = self._resolve_registry_git_path(
                root,
                summary.registry_path,
            )
            if not self._published_paths_match_remote_tracking(
                root,
                tracking_ref=tracking_ref,
                catalog_path=catalog_path,
                package_path=package_path,
            ):
                raise MarketplaceImportSourceError(
                    "marketplace.install.package_not_published"
                )

            manifest_path = (
                (
                    self._claude_manifest_path(root)
                    if provider == "claude-code"
                    else self._codex_manifest_path(root)
                )
                .relative_to(root)
                .as_posix()
            )
            provider_manifest = self._read_published_manifest(
                root,
                tracking_ref=tracking_ref,
                manifest_path=manifest_path,
            )
            published_packages = provider_manifest.get("plugins")
            if (
                provider_manifest.get("name") != catalog.marketplace_id
                or not isinstance(published_packages, list)
                or not any(
                    isinstance(entry, dict) and entry.get("name") == package_id
                    for entry in published_packages
                )
            ):
                raise MarketplaceImportSourceError(
                    "marketplace.install.package_not_published"
                )

            return MarketplacePublishedPackageResolution(
                marketplace_id=catalog.marketplace_id,
                remote_url=remote_url,
                publish_ref=publish_ref,
            )

    @staticmethod
    def _published_paths_match_remote_tracking(
        root: Path,
        *,
        tracking_ref: str,
        catalog_path: str,
        package_path: str,
    ) -> bool:
        ref_result = git_allow_failure(
            root,
            "rev-parse",
            "--verify",
            "--quiet",
            f"{tracking_ref}^{{commit}}",
        )
        if ref_result.returncode != 0:
            return False

        package_result = git_allow_failure(
            root,
            "cat-file",
            "-e",
            f"{tracking_ref}:{package_path}",
        )
        if package_result.returncode != 0:
            return False

        paths = [catalog_path, package_path]
        diff_result = git_allow_failure(
            root,
            "diff",
            "--quiet",
            tracking_ref,
            "--",
            *paths,
        )
        if diff_result.returncode != 0:
            return False

        untracked_result = git_allow_failure(
            root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "--",
            *paths,
        )
        if untracked_result.returncode != 0 or untracked_result.stdout.strip():
            return False

        ignored_result = git_allow_failure(
            root,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--",
            *paths,
        )
        return ignored_result.returncode == 0 and not ignored_result.stdout.strip()

    @staticmethod
    def _read_published_manifest(
        root: Path,
        *,
        tracking_ref: str,
        manifest_path: str,
    ) -> dict[str, Any]:
        result = git_allow_failure(
            root,
            "show",
            f"{tracking_ref}:{manifest_path}",
        )
        if result.returncode != 0:
            raise MarketplaceImportSourceError(
                "marketplace.install.package_not_published"
            )
        try:
            manifest = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise MarketplaceImportSourceError(
                "marketplace.install.package_not_published"
            ) from exc
        if not isinstance(manifest, dict):
            raise MarketplaceImportSourceError(
                "marketplace.install.package_not_published"
            )
        return manifest

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
