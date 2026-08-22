"""Marketplace settings activity workflow module."""

from __future__ import annotations

from datetime import datetime, timezone

from aileron_git_core import OperationKind

from app.modules.marketplace.models import (
    MarketplaceActivityAction,
    MarketplaceActivityDetail,
    MarketplaceActivityListResult,
    MarketplaceActivityRecord,
    MarketplaceActivityStatus,
    MarketplacePackageFormat,
    MarketplaceTargetClient,
    MarketplacePluginCliCommand,
    MarketplaceRegistryCatalog,
    MarketplaceRegistryInitResult,
    MarketplaceRegistryRootMetadataSavePayload,
    MarketplaceRegistrySettings,
    MarketplaceSettingsSaveResult,
)
from app.modules.marketplace.activity_repository import (
    MarketplaceActivityRepository,
)

from .kernel import _MarketplaceRegistrySupport
from .registry_operations import (
    _LOGGER,
    MarketplaceImportSourceError,
    _registry_git_operation,
)


class MarketplaceSettingsActivityWorkflow(_MarketplaceRegistrySupport):
    """Manage registry settings, credentials, bootstrap, and activity history."""

    @_registry_git_operation(OperationKind.WRITE, "initialize_registry")
    def initialize_registry(
        self,
        user_id: str,
        metadata: MarketplaceRegistryRootMetadataSavePayload | None = None,
    ) -> MarketplaceRegistryInitResult:
        """Bootstrap the canonical catalog and derived publish manifests."""
        with self._registry_lock:
            root = self._get_registry_root(user_id)
            created = not root.exists()
            self._ensure_target_client_roots(root)
            self._ensure_registry_gitignore(root, invalidation_key=user_id)
            metadata = metadata or self._default_metadata()
            catalog_path = self._catalog_path(root)
            if not catalog_path.exists():
                self._persist_catalog_and_publish_manifests(
                    root,
                    MarketplaceRegistryCatalog(
                        schema_version=1,
                        marketplace_id=self._initial_marketplace_id(metadata.name),
                        display_name=metadata.name,
                        owner=metadata.owner,
                        description=metadata.description,
                        publish_branch="main",
                        packages=[],
                    ),
                    invalidation_key=user_id,
                )
            else:
                self._generate_publish_manifests(
                    root,
                    self._read_catalog(root),
                    invalidation_key=user_id,
                )
            self._invalidate_package_index(user_id)
            return MarketplaceRegistryInitResult(
                root_path=str(root),
                created=created,
                claude_manifest_path=str(
                    self._claude_manifest_path(root).relative_to(root)
                ),
                codex_manifest_path=str(
                    self._codex_manifest_path(root).relative_to(root)
                ),
            )

    def get_settings(self, user_id: str) -> MarketplaceRegistrySettings:
        """Read editable metadata and immutable identity from the catalog."""
        root = self._get_registry_root(user_id)
        if not self._catalog_path(root).exists():
            return MarketplaceRegistrySettings(
                display_name="",
                marketplace_id=None,
                publish_branch=None,
                root_path=str(root),
                status="uninitialized",
                description="",
                maintainer_name="",
                maintainer_email="",
            )

        catalog = self._read_catalog(root)
        return MarketplaceRegistrySettings(
            display_name=catalog.display_name,
            marketplace_id=catalog.marketplace_id,
            publish_branch=catalog.publish_branch,
            root_path=str(root),
            status="ready",
            description=catalog.description,
            maintainer_name=catalog.owner.name,
            maintainer_email=catalog.owner.email,
        )

    def list_activity(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
        workspace_id: str | None = None,
        package_format: MarketplacePackageFormat | None = None,
        target_client: MarketplaceTargetClient | None = None,
        package_id: str | None = None,
        action: MarketplaceActivityAction | None = None,
        status: MarketplaceActivityStatus | None = None,
    ) -> MarketplaceActivityListResult:
        """Return authorized workspace audit and actor-owned registry activity."""

        if self.db is None:
            raise RuntimeError("Marketplace activity persistence is unavailable")
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        repository = MarketplaceActivityRepository(self.db)
        rows, total = repository.list(
            user_id=user_id,
            page=page,
            page_size=page_size,
            workspace_id=workspace_id,
            package_format=package_format,
            target_client=target_client,
            package_id=package_id,
            action=action,
            status=status,
        )
        return MarketplaceActivityListResult(
            items=[
                MarketplaceActivityRecord(
                    id=row.id,
                    action=row.action,
                    package_format=row.package_format,
                    target_client=row.target_client,
                    package_id=row.package_id,
                    operation_id=row.operation_id,
                    workspace_id=row.workspace_id,
                    marketplace_id=row.marketplace_id,
                    status=row.status,
                    error_code=row.error_code,
                    created_at=row.created_at.isoformat().replace("+00:00", "Z"),
                )
                for row in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size,
        )

    def record_activity(
        self,
        user_id: str,
        *,
        action: MarketplaceActivityAction,
        status: MarketplaceActivityStatus,
        package_format: MarketplacePackageFormat | None = None,
        target_client: MarketplaceTargetClient | None = None,
        package_id: str | None = None,
        operation_id: str | None = None,
        workspace_id: str | None = None,
        marketplace_id: str | None = None,
        error_code: str | None = None,
        catalog_plugin_id: str | None = None,
        release_revision: str | None = None,
        profile_digest: str | None = None,
        projection_digest: str | None = None,
        materialization_digest: str | None = None,
        projected_count: int | None = None,
        skipped_count: int | None = None,
        conflict_count: int | None = None,
        created_count: int | None = None,
        merged_count: int | None = None,
        unchanged_count: int | None = None,
        overwritten_count: int | None = None,
        target_locators: tuple[str, ...] = (),
        diagnostic_codes: tuple[str, ...] = (),
    ) -> MarketplaceActivityRecord | None:
        """Append an audit event without reversing an already completed operation."""

        if self.db is None:
            _LOGGER.error(
                "Marketplace activity append skipped because persistence is unavailable"
            )
            return None
        try:
            row = MarketplaceActivityRepository(self.db).append(
                actor_user_id=user_id,
                action=action,
                status=status,
                package_format=package_format,
                target_client=target_client,
                package_id=package_id,
                operation_id=operation_id,
                workspace_id=workspace_id,
                marketplace_id=marketplace_id,
                error_code=error_code,
                catalog_plugin_id=catalog_plugin_id,
                release_revision=release_revision,
                profile_digest=profile_digest,
                projection_digest=projection_digest,
                materialization_digest=materialization_digest,
                projected_count=projected_count,
                skipped_count=skipped_count,
                conflict_count=conflict_count,
                created_count=created_count,
                merged_count=merged_count,
                unchanged_count=unchanged_count,
                overwritten_count=overwritten_count,
                target_locators=target_locators,
                diagnostic_codes=diagnostic_codes,
                now=datetime.now(timezone.utc),
            )
            self.db.commit()
            return MarketplaceActivityRecord(
                id=row.id,
                action=row.action,
                package_format=row.package_format,
                target_client=row.target_client,
                package_id=row.package_id,
                operation_id=row.operation_id,
                workspace_id=row.workspace_id,
                marketplace_id=row.marketplace_id,
                status=row.status,
                error_code=row.error_code,
                created_at=row.created_at.isoformat().replace("+00:00", "Z"),
            )
        except Exception:
            self.db.rollback()
            _LOGGER.exception("Failed to append Marketplace activity")
            return None

    def get_activity_detail(
        self,
        user_id: str,
        activity_id: str,
    ) -> MarketplaceActivityDetail | None:
        """Return authorized proof and raw command detail for one activity."""

        if self.db is None:
            raise RuntimeError("Marketplace activity persistence is unavailable")
        resolved = MarketplaceActivityRepository(self.db).get_detail(
            user_id=user_id,
            activity_id=activity_id,
        )
        if resolved is None:
            return None
        row, commands = resolved
        return MarketplaceActivityDetail(
            id=row.id,
            action=row.action,
            packageFormat=row.package_format,
            targetClient=row.target_client,
            packageId=row.package_id,
            operationId=row.operation_id,
            workspaceId=row.workspace_id,
            marketplaceId=row.marketplace_id,
            status=row.status,
            errorCode=row.error_code,
            createdAt=row.created_at.isoformat().replace("+00:00", "Z"),
            workspaceIdSnapshot=row.workspace_id_snapshot,
            catalogPluginId=row.catalog_plugin_id,
            releaseRevision=row.release_revision,
            profileDigest=row.profile_digest,
            projectionDigest=row.projection_digest,
            materializationDigest=row.materialization_digest,
            projectedCount=row.projected_count,
            skippedCount=row.skipped_count,
            conflictCount=row.conflict_count,
            createdCount=row.created_count,
            mergedCount=row.merged_count,
            unchangedCount=row.unchanged_count,
            overwrittenCount=row.overwritten_count,
            targetLocators=row.target_locators,
            diagnosticCodes=row.diagnostic_codes,
            commands=[
                MarketplacePluginCliCommand(
                    sequence=command.sequence,
                    stage=command.stage,
                    argvDisplay=command.argv_display,
                    exitCode=command.exit_code,
                    startedAt=command.started_at,
                    endedAt=command.ended_at,
                    stdout=command.stdout,
                    stderr=command.stderr,
                    stdoutOriginalByteCount=command.stdout_original_byte_count,
                    stderrOriginalByteCount=command.stderr_original_byte_count,
                    truncated=command.truncated,
                )
                for command in commands
            ],
        )

    @_registry_git_operation(OperationKind.WRITE, "save_settings")
    def save_settings(
        self,
        user_id: str,
        metadata: MarketplaceRegistryRootMetadataSavePayload,
    ) -> MarketplaceSettingsSaveResult:
        """Save editable catalog metadata without changing immutable identity."""
        with self._registry_lock:
            root = self._get_registry_root(user_id)
            if not self._catalog_path(root).exists():
                raise MarketplaceImportSourceError(
                    "marketplace.registry.not_initialized"
                )
            catalog = self._read_catalog(root)

            claude_written = False
            codex_written = False
            partial_target_client: MarketplaceTargetClient | None = None
            error_code: str | None = None

            try:
                next_catalog = catalog.model_copy(
                    update={
                        "display_name": metadata.name,
                        "owner": metadata.owner,
                        "description": metadata.description,
                    }
                )
                self._persist_catalog_and_publish_manifests(
                    root,
                    next_catalog,
                    invalidation_key=user_id,
                )
                claude_written = True
                codex_written = True
                self._invalidate_package_index(user_id)
            except Exception:
                if claude_written and not codex_written:
                    partial_target_client = "claude-code"
                elif codex_written and not claude_written:
                    partial_target_client = "codex"
                if claude_written or codex_written:
                    self._invalidate_package_index(user_id)
                error_code = "marketplace.settings.partial_write"

            return MarketplaceSettingsSaveResult(
                settings=self.get_settings(user_id),
                claude_written=claude_written,
                codex_written=codex_written,
                partial_success_target_client=partial_target_client,
                error_code=error_code,
            )
