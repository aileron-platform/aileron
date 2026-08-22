"""One-shot Marketplace user-copy preflight and apply orchestration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, cast

from aileron_marketplace_core import (
    PluginReleaseIdentity,
    SkippedUserCopyResourceContract,
    TargetClientName,
    PackageSourceError,
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyBlockingIssueContract,
    UserCopyConflictContract,
    UserCopyPlanResourceContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
    extract_user_copy_source_profile,
    package_tree_digest,
)

from app.config.settings import Settings, get_settings
from app.modules.cli_settings.cache_api import clear_agent_settings_cache
from app.modules.cli_settings.user_scope.codecs import fsync_directory
from app.modules.cli_settings.user_scope.materializer import (
    UserCopyMaterializationError,
    UserCopyMaterializationResult,
    UserCopyMaterializer,
)
from app.modules.cli_settings.user_scope.paths import (
    get_user_scope_path_resolver,
    target_client_state_root_id,
)
from app.modules.cli_settings.user_scope.planner import (
    UserCopyAction,
    UserCopyMaterializationPlan,
    UserCopyOverwriteApproval,
    UserCopyPlanner,
    UserCopyPlanStatus,
    validate_overwrite_approvals,
)
from app.modules.cli_settings.user_scope.adapter import UserCopyAdapterError
from .errors import MarketplaceOperationError
from .gate import MarketplaceTargetClientGate
from .inventory import FilesystemUserCopyInventoryReader
from .state import MarketplaceMutationStore, canonical_digest, write_json_atomic
from .user_copy_snapshot import UserCopySnapshotStager

_RECOVERY_VERSION = 1
_MAX_RECOVERY_BYTES = 256 * 1024
_RECOVERY_FILE = re.compile(r"^(?P<operation>[0-9a-f]{32})\.json$")
_RECOVERY_TEMP = re.compile(r"^\.[0-9a-f]{32}\.json\.[0-9a-f]{16}\.tmp$")


class MarketplaceUserCopyService:
    """Run one-shot copies without creating installation lifecycle state."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        mutation_store: MarketplaceMutationStore | None = None,
        snapshot_stager: UserCopySnapshotStager | None = None,
        inventory_reader: FilesystemUserCopyInventoryReader | None = None,
        gate: MarketplaceTargetClientGate | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        state_root = Path(self._settings.MARKETPLACE_OPERATION_JOURNAL_DIR)
        self._mutation_store = mutation_store or MarketplaceMutationStore(state_root)
        self._snapshot_stager = snapshot_stager or UserCopySnapshotStager(
            state_root / "user-copy-snapshots"
        )
        self._transaction_root = state_root / "user-copy-transactions"
        self._recovery_root = state_root / "user-copy-recovery"
        self._inventory_reader = (
            inventory_reader or FilesystemUserCopyInventoryReader(self._settings)
        )
        self._gate = gate or MarketplaceTargetClientGate(self._mutation_store)

    @property
    def max_archive_bytes(self) -> int:
        return self._snapshot_stager.limits.max_archive_bytes

    def preflight(
        self,
        request: UserCopyProjectionPreflightRequestContract,
    ) -> UserCopyProjectionPreflightResultContract:
        """Build a target-only plan from bounded Manager source proofs."""

        self._validate_runtime_identity(
            workspace_id=request.workspace_id,
            runtime_instance_id=request.runtime_instance_id,
        )
        try:
            profile = request.source_profile.to_profile()
        except (PackageSourceError, ValueError, TypeError, KeyError) as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.source_invalid",
                http_status=409,
            ) from exc
        if (
            profile.profile_version != request.expected_profile_version
            or profile.profile_digest != request.expected_profile_digest
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.source_invalid",
                http_status=409,
            )

        inventory = self._inventory_reader.inventory(
            request.target_client,
            profile=profile,
        )
        try:
            plan = UserCopyPlanner(
                package_id=_planner_package_id(request.catalog_plugin_id),
                release_revision=request.release_revision,
            ).plan_source_profile(
                profile,
                target_client=request.target_client,
                package_root=None,
                inventory=inventory,
            )
        except (UserCopyAdapterError, ValueError) as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=409,
            ) from exc
        root_id = self._user_copy_target_client_state_root_id(request.target_client)
        materialization_digest = contextual_materialization_digest(
            plan_digest=plan.materialization_digest,
            projection_digest=plan.projection_digest,
            package_format=request.package_format,
            target_client=request.target_client,
            catalog_plugin_id=request.catalog_plugin_id,
            release_revision=request.release_revision,
            workspace_id=request.workspace_id,
            runtime_instance_id=request.runtime_instance_id,
            target_client_state_root_id=root_id,
            source_digest=request.expected_source_digest,
            profile_version=profile.profile_version,
            profile_digest=profile.profile_digest,
        )

        return UserCopyProjectionPreflightResultContract(
            status=plan.status.value,
            packageFormat=request.package_format,
            targetClient=request.target_client,
            catalogPluginId=request.catalog_plugin_id,
            releaseRevision=request.release_revision,
            workspaceId=request.workspace_id,
            runtimeInstanceId=request.runtime_instance_id,
            targetClientStateRootId=root_id,
            sourceDigest=request.expected_source_digest,
            profileVersion=profile.profile_version,
            profileDigest=profile.profile_digest,
            projectionDigest=plan.projection_digest,
            materializationDigest=materialization_digest,
            resources=[
                UserCopyPlanResourceContract.model_validate(
                    {
                        "resourceType": resource.resource_type,
                        "resourceId": resource.resource_id,
                        "sourceLocator": resource.source_locator,
                        "targetLocator": resource.target_locator,
                        "targetIdentity": resource.target_identity,
                        "action": resource.action.value,
                        "incomingDigest": resource.content_digest,
                    }
                )
                for resource in plan.resources
                if resource.action is not UserCopyAction.OVERWRITE
            ],
            skippedResources=[
                SkippedUserCopyResourceContract.model_validate(
                    resource.canonical_dict()
                )
                for resource in plan.skipped_resources
            ],
            conflicts=[
                UserCopyConflictContract.model_validate(conflict.canonical_dict())
                for conflict in plan.conflicts
            ],
            blockingIssues=[
                UserCopyBlockingIssueContract.model_validate(issue.canonical_dict())
                for issue in plan.blocking_issues
            ],
        )

    def recover_incomplete_operations(self) -> None:
        """Recover every durable user-copy transaction before serving requests."""

        envelopes = self._scan_recovery_envelopes()
        snapshot_ids = set(self._snapshot_stager.recover_startup_state())
        transaction_ids = self._scan_transaction_ids()
        if not snapshot_ids.issubset(envelopes) or not transaction_ids.issubset(
            envelopes
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        for operation_id, metadata in sorted(envelopes.items()):
            self._recover_startup_operation(
                metadata,
                has_snapshot=operation_id in snapshot_ids,
                has_transaction=operation_id in transaction_ids,
            )

    def apply(
        self,
        metadata: UserCopyProjectionApplyMetadataContract,
        bundle: bytes,
    ) -> UserCopyProjectionApplyResultContract:
        """Stage, replan, apply, publish once, and remove transaction state."""

        self._validate_runtime_identity(
            workspace_id=metadata.workspace_id,
            runtime_instance_id=metadata.runtime_instance_id,
        )
        root_id = self._user_copy_target_client_state_root_id(metadata.target_client)
        if metadata.target_client_state_root_id != root_id:
            raise MarketplaceOperationError(
                "marketplace.user_copy.plan_stale",
                http_status=409,
            )
        recovery_envelope_persisted = False
        snapshot_staged = False
        retain_for_recovery = False
        materializer = UserCopyMaterializer(operation_state_root=self._transaction_root)
        try:
            self._persist_recovery_envelope(metadata)
            recovery_envelope_persisted = True
            snapshot = self._snapshot_stager.stage(
                operation_id=metadata.operation_id,
                archive=bundle,
                expected_archive_digest=metadata.expected_archive_digest,
                expected_package_tree_digest=(metadata.expected_package_tree_digest),
            )
            snapshot_staged = True
            profile = extract_user_copy_source_profile(
                metadata.package_format,
                snapshot.package_root,
                release=PluginReleaseIdentity(
                    catalog_plugin_id=metadata.catalog_plugin_id,
                    revision=metadata.release_revision,
                ),
            )
            source_digest = package_tree_digest(snapshot.package_root)
            if (
                source_digest != metadata.expected_source_digest
                or profile.profile_version != metadata.expected_profile_version
                or profile.profile_digest != metadata.expected_profile_digest
            ):
                raise MarketplaceOperationError(
                    "marketplace.user_copy.source_invalid",
                    http_status=409,
                )
            approvals = _approvals(metadata.overwrite_approvals)

            with self._mutation_store.target_client_lock(
                target_client=metadata.target_client,
            ):
                inventory = self._inventory_reader.inventory(
                    metadata.target_client,
                    profile=profile,
                )
                plan = UserCopyPlanner(
                    package_id=_planner_package_id(metadata.catalog_plugin_id),
                    release_revision=metadata.release_revision,
                ).plan_source_profile(
                    profile,
                    target_client=metadata.target_client,
                    package_root=snapshot.package_root,
                    inventory=inventory,
                )
                current_digest = contextual_materialization_digest(
                    plan_digest=plan.materialization_digest,
                    projection_digest=plan.projection_digest,
                    package_format=metadata.package_format,
                    target_client=metadata.target_client,
                    catalog_plugin_id=metadata.catalog_plugin_id,
                    release_revision=metadata.release_revision,
                    workspace_id=metadata.workspace_id,
                    runtime_instance_id=metadata.runtime_instance_id,
                    target_client_state_root_id=root_id,
                    source_digest=source_digest,
                    profile_version=profile.profile_version,
                    profile_digest=profile.profile_digest,
                )
                has_transaction = materializer.has_transaction(metadata.operation_id)
                if not has_transaction and (
                    plan.status is UserCopyPlanStatus.BLOCKED
                    or plan.projection_digest != metadata.expected_projection_digest
                    or len(plan.skipped_resources) != metadata.expected_skipped_count
                    or metadata.accept_partial_copy
                    != bool(plan.skipped_resources)
                    or current_digest != metadata.expected_materialization_digest
                ):
                    raise MarketplaceOperationError(
                        "marketplace.user_copy.plan_stale",
                        http_status=409,
                    )
                if not has_transaction:
                    try:
                        validate_overwrite_approvals(plan, approvals)
                    except UserCopyAdapterError as exc:
                        raise MarketplaceOperationError(
                            "marketplace.user_copy.plan_stale",
                            http_status=409,
                        ) from exc

                if has_transaction:
                    retain_for_recovery = True
                    result = self._recover_existing_transaction(
                        materializer=materializer,
                        metadata=metadata,
                        plan=plan,
                        approvals=approvals,
                        contextual_digest=(metadata.expected_materialization_digest),
                    )
                    self._snapshot_stager.remove(metadata.operation_id)
                    snapshot_staged = False
                    materializer.finalize(metadata.operation_id)
                    self._remove_recovery_envelope(metadata.operation_id)
                    recovery_envelope_persisted = False
                    retain_for_recovery = False
                    return _apply_result(metadata, result)

                retain_for_recovery = True
                try:
                    result = materializer.apply(
                        plan,
                        snapshot.package_root,
                        operation_id=metadata.operation_id,
                        workspace_id=metadata.workspace_id,
                        overwrite_approvals=approvals,
                        contextual_materialization_digest=current_digest,
                    )
                except Exception:
                    try:
                        self._cleanup_failed_transaction(
                            materializer=materializer,
                            metadata=metadata,
                        )
                    except Exception:
                        raise
                    snapshot_staged = False
                    recovery_envelope_persisted = False
                    retain_for_recovery = False
                    raise

                try:
                    self._clear_target_client_caches(metadata.target_client)
                    self._gate.advance_generation(metadata.target_client)
                    materializer.mark_published(metadata.operation_id)
                except Exception:
                    try:
                        recovery = materializer.recover(
                            plan,
                            operation_id=metadata.operation_id,
                            overwrite_approvals=approvals,
                            expected_contextual_materialization_digest=(current_digest),
                        )
                        if recovery.action != "rolled-back":
                            raise UserCopyMaterializationError(
                                "marketplace.user_copy.rollback_failed"
                            )
                        self._cleanup_failed_transaction(
                            materializer=materializer,
                            metadata=metadata,
                        )
                        snapshot_staged = False
                        recovery_envelope_persisted = False
                        retain_for_recovery = False
                    except Exception as rollback_exc:
                        retain_for_recovery = True
                        raise MarketplaceOperationError(
                            "marketplace.user_copy.rollback_failed",
                            http_status=500,
                        ) from rollback_exc
                    raise

                try:
                    self._snapshot_stager.remove(metadata.operation_id)
                    snapshot_staged = False
                    materializer.finalize(metadata.operation_id)
                    self._remove_recovery_envelope(metadata.operation_id)
                    recovery_envelope_persisted = False
                    retain_for_recovery = False
                except Exception:
                    retain_for_recovery = True
                    raise
                return _apply_result(metadata, result)
        except Exception as exc:
            if snapshot_staged and not retain_for_recovery:
                try:
                    self._snapshot_stager.remove(metadata.operation_id)
                except Exception as cleanup_exc:
                    raise MarketplaceOperationError(
                        "marketplace.user_copy.rollback_failed",
                        http_status=500,
                    ) from cleanup_exc
            if recovery_envelope_persisted and not retain_for_recovery:
                try:
                    self._remove_recovery_envelope(metadata.operation_id)
                except Exception as cleanup_exc:
                    raise MarketplaceOperationError(
                        "marketplace.user_copy.runtime_state_invalid",
                        http_status=500,
                    ) from cleanup_exc
            mapped = _user_copy_error(exc)
            if mapped is exc:
                raise
            raise mapped from exc

    def _recover_existing_transaction(
        self,
        *,
        materializer: UserCopyMaterializer,
        metadata: UserCopyProjectionApplyMetadataContract,
        plan: UserCopyMaterializationPlan,
        approvals: tuple[UserCopyOverwriteApproval, ...],
        contextual_digest: str,
    ) -> UserCopyMaterializationResult:
        recovery = materializer.recover(
            plan,
            operation_id=metadata.operation_id,
            overwrite_approvals=approvals,
            expected_contextual_materialization_digest=contextual_digest,
        )
        if recovery.action == "rolled-back":
            materializer.finalize(metadata.operation_id)
            self._snapshot_stager.remove(metadata.operation_id)
            self._remove_recovery_envelope(metadata.operation_id)
            raise MarketplaceOperationError(
                "marketplace.user_copy.apply_failed",
                http_status=500,
            )
        if recovery.result is None or not recovery.published:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        return recovery.result

    def _recover_startup_operation(
        self,
        metadata: UserCopyProjectionApplyMetadataContract,
        *,
        has_snapshot: bool,
        has_transaction: bool,
    ) -> None:
        self._validate_runtime_identity(
            workspace_id=metadata.workspace_id,
            runtime_instance_id=metadata.runtime_instance_id,
        )
        if metadata.target_client_state_root_id != self._user_copy_target_client_state_root_id(
            metadata.target_client
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        materializer = UserCopyMaterializer(operation_state_root=self._transaction_root)
        with self._mutation_store.target_client_lock(
            target_client=metadata.target_client,
        ):
            if not has_transaction:
                if has_snapshot:
                    self._snapshot_stager.remove(metadata.operation_id)
                self._remove_recovery_envelope(metadata.operation_id)
                return

            if materializer.transaction_published(
                metadata.operation_id,
                expected_contextual_materialization_digest=(
                    metadata.expected_materialization_digest
                ),
            ):
                if has_snapshot:
                    self._snapshot_stager.remove(metadata.operation_id)
                materializer.finalize(metadata.operation_id)
                self._remove_recovery_envelope(metadata.operation_id)
                return

            if not has_snapshot:
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            snapshot = self._snapshot_stager.load(
                metadata.operation_id,
                expected_archive_digest=metadata.expected_archive_digest,
                expected_package_tree_digest=(metadata.expected_package_tree_digest),
            )
            profile = extract_user_copy_source_profile(
                metadata.package_format,
                snapshot.package_root,
                release=PluginReleaseIdentity(
                    catalog_plugin_id=metadata.catalog_plugin_id,
                    revision=metadata.release_revision,
                ),
            )
            if (
                package_tree_digest(snapshot.package_root) != metadata.expected_source_digest
                or profile.profile_version != metadata.expected_profile_version
                or profile.profile_digest != metadata.expected_profile_digest
            ):
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            plan = UserCopyPlanner(
                package_id=_planner_package_id(metadata.catalog_plugin_id),
                release_revision=metadata.release_revision,
            ).plan_source_profile(
                profile,
                target_client=metadata.target_client,
                package_root=snapshot.package_root,
                inventory=self._inventory_reader.inventory(
                    metadata.target_client,
                    profile=profile,
                ),
            )
            try:
                self._recover_existing_transaction(
                    materializer=materializer,
                    metadata=metadata,
                    plan=plan,
                    approvals=_approvals(metadata.overwrite_approvals),
                    contextual_digest=(metadata.expected_materialization_digest),
                )
            except MarketplaceOperationError as exc:
                if exc.code != "marketplace.user_copy.apply_failed":
                    raise
                return
            self._snapshot_stager.remove(metadata.operation_id)
            materializer.finalize(metadata.operation_id)
            self._remove_recovery_envelope(metadata.operation_id)

    def _cleanup_failed_transaction(
        self,
        *,
        materializer: UserCopyMaterializer,
        metadata: UserCopyProjectionApplyMetadataContract,
    ) -> None:
        try:
            if materializer.has_transaction(metadata.operation_id):
                materializer.finalize(metadata.operation_id)
            self._snapshot_stager.remove(metadata.operation_id)
            self._remove_recovery_envelope(metadata.operation_id)
        except Exception as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.rollback_failed",
                http_status=500,
            ) from exc

    def _persist_recovery_envelope(
        self,
        metadata: UserCopyProjectionApplyMetadataContract,
    ) -> None:
        self._ensure_recovery_root()
        path = self._recovery_root / f"{metadata.operation_id}.json"
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        envelope = {
            "recoveryVersion": _RECOVERY_VERSION,
            "metadata": metadata.to_wire(),
        }
        encoded = json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(encoded) > _MAX_RECOVERY_BYTES:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=409,
            )
        if path.exists():
            existing = self._read_recovery_envelope(path)
            if existing != metadata:
                raise MarketplaceOperationError(
                    "marketplace.user_copy.operation_conflict",
                    http_status=409,
                )
            return
        write_json_atomic(path, envelope)

    def _read_recovery_envelope(
        self,
        path: Path,
    ) -> UserCopyProjectionApplyMetadataContract:
        match = _RECOVERY_FILE.fullmatch(path.name)
        if match is None or path.is_symlink() or not path.is_file():
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        try:
            if path.stat().st_size > _MAX_RECOVERY_BYTES:
                raise ValueError("recovery envelope too large")
            encoded = path.read_bytes()
            if len(encoded) > _MAX_RECOVERY_BYTES:
                raise ValueError("recovery envelope too large")
            value = json.loads(encoded)
            if (
                not isinstance(value, dict)
                or set(value) != {"recoveryVersion", "metadata"}
                or value["recoveryVersion"] != _RECOVERY_VERSION
                or not isinstance(value["metadata"], dict)
            ):
                raise ValueError("recovery envelope invalid")
            metadata = UserCopyProjectionApplyMetadataContract.from_wire(value["metadata"])
        except Exception as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            ) from exc
        if metadata.operation_id != match.group("operation"):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        return metadata

    def _scan_recovery_envelopes(
        self,
    ) -> dict[str, UserCopyProjectionApplyMetadataContract]:
        self._ensure_recovery_root()
        envelopes: dict[str, UserCopyProjectionApplyMetadataContract] = {}
        changed = False
        for path in sorted(self._recovery_root.iterdir(), key=lambda item: item.name):
            if path.is_symlink():
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            if _RECOVERY_TEMP.fullmatch(path.name):
                if not path.is_file():
                    raise MarketplaceOperationError(
                        "marketplace.user_copy.runtime_state_invalid",
                        http_status=500,
                    )
                path.unlink()
                changed = True
                continue
            match = _RECOVERY_FILE.fullmatch(path.name)
            if match is None or not path.is_file():
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            metadata = self._read_recovery_envelope(path)
            envelopes[match.group("operation")] = metadata
        if changed:
            fsync_directory(self._recovery_root)
        return envelopes

    def _scan_transaction_ids(self) -> set[str]:
        if self._transaction_root.is_symlink() or (
            self._transaction_root.exists() and not self._transaction_root.is_dir()
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        if not self._transaction_root.exists():
            return set()
        operation_ids: set[str] = set()
        for path in self._transaction_root.iterdir():
            if (
                path.is_symlink()
                or not path.is_dir()
                or _RECOVERY_FILE.fullmatch(f"{path.name}.json") is None
            ):
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            operation_ids.add(path.name)
        return operation_ids

    def _remove_recovery_envelope(self, operation_id: str) -> None:
        self._ensure_recovery_root()
        if _RECOVERY_FILE.fullmatch(f"{operation_id}.json") is None:
            raise MarketplaceOperationError(
                "marketplace.user_copy.operation_id_invalid",
                http_status=409,
            )
        path = self._recovery_root / f"{operation_id}.json"
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        if path.exists():
            path.unlink()
            fsync_directory(self._recovery_root)

    def _ensure_recovery_root(self) -> None:
        if self._recovery_root.is_symlink() or (
            self._recovery_root.exists() and not self._recovery_root.is_dir()
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        try:
            self._recovery_root.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o700,
            )
            os.chmod(self._recovery_root, 0o700)
        except OSError as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            ) from exc

    def _validate_runtime_identity(
        self,
        *,
        workspace_id: str,
        runtime_instance_id: str,
    ) -> None:
        if (
            workspace_id != self._settings.AILERON_WORKSPACE_ID
            or runtime_instance_id != self._settings.AILERON_RUNTIME_INSTANCE_ID
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=409,
            )

    def _clear_target_client_caches(self, target_client: str) -> None:
        clear_agent_settings_cache(
            provider=cast(TargetClientName, target_client),
            workspace_id=self._settings.AILERON_WORKSPACE_ID,
            scope="user",
        )

    def _user_copy_target_client_state_root_id(self, target_client: str) -> str:
        try:
            return target_client_state_root_id(
                target_client,
                paths=get_user_scope_path_resolver(),
            )
        except (ValueError, OSError) as exc:
            raise _user_copy_error(exc) from exc


def _apply_result(
    metadata: UserCopyProjectionApplyMetadataContract,
    result: UserCopyMaterializationResult,
) -> UserCopyProjectionApplyResultContract:
    return UserCopyProjectionApplyResultContract(
        operationId=metadata.operation_id,
        packageFormat=metadata.package_format,
        targetClient=metadata.target_client,
        catalogPluginId=metadata.catalog_plugin_id,
        releaseRevision=metadata.release_revision,
        workspaceId=metadata.workspace_id,
        createdCount=result.created_count,
        mergedCount=result.merged_count,
        unchangedCount=result.unchanged_count,
        overwrittenCount=result.overwritten_count,
        skippedCount=metadata.expected_skipped_count,
    )


def _approvals(
    values: list[Any],
) -> tuple[UserCopyOverwriteApproval, ...]:
    return tuple(
        UserCopyOverwriteApproval(
            target_identity=item.target_identity,
            expected_revision=item.expected_revision,
        )
        for item in values
    )


def contextual_materialization_digest(
    *,
    plan_digest: str,
    projection_digest: str,
    package_format: str,
    target_client: str,
    catalog_plugin_id: str,
    release_revision: str,
    workspace_id: str,
    runtime_instance_id: str,
    target_client_state_root_id: str,
    source_digest: str,
    profile_version: int,
    profile_digest: str,
) -> str:
    """Bind a target plan to one source, Runtime, workspace, and target_client root."""

    return canonical_digest(
        {
            "digestVersion": "marketplace-user-copy-materialization-v2",
            "planDigest": plan_digest,
            "projectionDigest": projection_digest,
            "packageFormat": package_format,
            "targetClient": target_client,
            "catalogPluginId": catalog_plugin_id,
            "releaseRevision": release_revision,
            "workspaceId": workspace_id,
            "runtimeInstanceId": runtime_instance_id,
            "targetClientStateRootId": target_client_state_root_id,
            "sourceDigest": source_digest,
            "profileVersion": profile_version,
            "profileDigest": profile_digest,
        }
    )


def _planner_package_id(catalog_plugin_id: str) -> str:
    return f"catalog-{canonical_digest({'catalogPluginId': catalog_plugin_id})[:32]}"


def _user_copy_error(exc: Exception) -> MarketplaceOperationError:
    if isinstance(exc, MarketplaceOperationError):
        if exc.code.startswith("marketplace.user_copy."):
            return exc
        if exc.code in {
            "marketplace.install.lock_timeout",
            "marketplace.install.operation_conflict",
        }:
            return MarketplaceOperationError(
                "marketplace.user_copy.operation_conflict",
                http_status=exc.http_status,
            )
        return MarketplaceOperationError(
            "marketplace.user_copy.runtime_state_invalid",
            http_status=exc.http_status,
        )
    if isinstance(exc, UserCopyMaterializationError):
        return MarketplaceOperationError(
            exc.code,
            http_status=(
                500
                if exc.code
                in {
                    "marketplace.user_copy.apply_failed",
                    "marketplace.user_copy.rollback_failed",
                    "marketplace.user_copy.runtime_state_invalid",
                }
                else 409
            ),
        )
    if isinstance(exc, (PackageSourceError, UserCopyAdapterError)):
        return MarketplaceOperationError(
            "marketplace.user_copy.source_invalid",
            http_status=409,
        )
    return MarketplaceOperationError(
        "marketplace.user_copy.apply_failed",
        http_status=500,
    )
