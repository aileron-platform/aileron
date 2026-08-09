"""One-shot Marketplace user-copy preflight and apply orchestration."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, cast

from aileron_marketplace_core import (
    MarketplaceProviderName,
    PackageSourceError,
    UserCopyApplyMetadataContract,
    UserCopyApplyResultContract,
    UserCopyBlockingIssueContract,
    UserCopyConflictContract,
    UserCopyPlanResourceContract,
    UserCopyPreflightRequestContract,
    UserCopyPreflightResultContract,
    build_user_copy_profile_preview,
    resolve_user_copy_profile,
    user_copy_source_digest_from_preview,
)

from app.config.settings import Settings, get_settings
from app.modules.cli_settings.cache_api import clear_agent_settings_cache
from app.modules.cli_settings.user_scope.codecs import fsync_directory
from app.modules.cli_settings.user_scope.materializer import (
    UserCopyMaterializationError,
    UserCopyMaterializationResult,
    UserCopyMaterializer,
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
from .gate import MarketplaceProviderGate
from .inventory import FilesystemUserCopyInventoryProvider
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
        inventory_provider: FilesystemUserCopyInventoryProvider | None = None,
        gate: MarketplaceProviderGate | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        state_root = Path(self._settings.MARKETPLACE_OPERATION_JOURNAL_DIR)
        self._mutation_store = mutation_store or MarketplaceMutationStore(state_root)
        self._snapshot_stager = snapshot_stager or UserCopySnapshotStager(
            state_root / "user-copy-snapshots"
        )
        self._transaction_root = state_root / "user-copy-transactions"
        self._recovery_root = state_root / "user-copy-recovery"
        self._inventory_provider = (
            inventory_provider or FilesystemUserCopyInventoryProvider(self._settings)
        )
        self._gate = gate or MarketplaceProviderGate(self._mutation_store)

    @property
    def provider_state_root_id(self) -> str:
        return self._mutation_store.provider_state_root_id

    @property
    def max_archive_bytes(self) -> int:
        return self._snapshot_stager.limits.max_archive_bytes

    def preflight(
        self,
        request: UserCopyPreflightRequestContract,
    ) -> UserCopyPreflightResultContract:
        """Build a target-only plan from bounded Manager source proofs."""

        self._validate_runtime_identity(
            workspace_id=request.workspace_id,
            runtime_instance_id=request.runtime_instance_id,
        )
        preview = request.profile_preview.to_wire(exclude_unset=True)
        try:
            source_digest = request.profile_preview.source_digest
            profile = request.profile_preview.to_profile()
        except (PackageSourceError, ValueError, TypeError, KeyError) as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.source_invalid",
                http_status=409,
            ) from exc
        if (
            source_digest != request.expected_source_digest
            or profile.profile_version != request.expected_profile_version
            or profile.profile_digest != request.expected_profile_digest
        ):
            raise MarketplaceOperationError(
                "marketplace.user_copy.source_invalid",
                http_status=409,
            )

        inventory = self._inventory_provider.inventory(
            request.provider,
            profile=profile,
        )
        proof_by_id = {
            f"{item['resourceType']}:{item['resourceId']}": item
            for item in preview["resources"]
        }
        try:
            plan = UserCopyPlanner(package_id=request.package_id).plan_preview(
                profile,
                source_digests={
                    stable_id: item["sourceDigest"]
                    for stable_id, item in proof_by_id.items()
                },
                dependency_payload_required={
                    stable_id: item["dependencyPayloadRequired"]
                    for stable_id, item in proof_by_id.items()
                },
                dependency_payload_projectable={
                    stable_id: item["dependencyPayloadProjectable"]
                    for stable_id, item in proof_by_id.items()
                },
                dependency_payloads=preview["dependencyPayloads"],
                structured_value_types={
                    stable_id: item["structuredValueType"]
                    for stable_id, item in proof_by_id.items()
                    if item.get("structuredValueType") is not None
                },
                structured_value_templates={
                    stable_id: item["structuredValueTemplate"]
                    for stable_id, item in proof_by_id.items()
                    if "structuredValueTemplate" in item
                },
                inventory=inventory,
            )
        except UserCopyAdapterError as exc:
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=409,
            ) from exc
        provider_state_root_id = self._user_copy_provider_state_root_id()
        materialization_digest = contextual_materialization_digest(
            plan_digest=plan.materialization_digest,
            provider=request.provider,
            package_id=request.package_id,
            revision=request.revision,
            workspace_id=request.workspace_id,
            runtime_instance_id=request.runtime_instance_id,
            provider_state_root_id=provider_state_root_id,
            source_digest=source_digest,
            profile_version=profile.profile_version,
            profile_digest=profile.profile_digest,
        )

        return UserCopyPreflightResultContract(
            status=plan.status.value,
            provider=request.provider,
            packageId=request.package_id,
            revision=request.revision,
            workspaceId=request.workspace_id,
            runtimeInstanceId=request.runtime_instance_id,
            providerStateRootId=provider_state_root_id,
            sourceDigest=source_digest,
            profileVersion=profile.profile_version,
            profileDigest=profile.profile_digest,
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
        metadata: UserCopyApplyMetadataContract,
        bundle: bytes,
    ) -> UserCopyApplyResultContract:
        """Stage, replan, apply, publish once, and remove transaction state."""

        self._validate_runtime_identity(
            workspace_id=metadata.workspace_id,
            runtime_instance_id=metadata.runtime_instance_id,
        )
        provider_state_root_id = self._user_copy_provider_state_root_id()
        if metadata.provider_state_root_id != provider_state_root_id:
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
            profile = resolve_user_copy_profile(
                metadata.provider,
                snapshot.package_root,
            )
            preview = build_user_copy_profile_preview(
                snapshot.package_root,
                profile,
            )
            source_digest = user_copy_source_digest_from_preview(preview)
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

            with self._mutation_store.provider_lock(
                provider=metadata.provider,
            ):
                inventory = self._inventory_provider.inventory(
                    metadata.provider,
                    profile=profile,
                )
                plan = UserCopyPlanner(package_id=metadata.package_id).plan(
                    profile,
                    snapshot.package_root,
                    inventory=inventory,
                )
                current_digest = contextual_materialization_digest(
                    plan_digest=plan.materialization_digest,
                    provider=metadata.provider,
                    package_id=metadata.package_id,
                    revision=metadata.revision,
                    workspace_id=metadata.workspace_id,
                    runtime_instance_id=metadata.runtime_instance_id,
                    provider_state_root_id=provider_state_root_id,
                    source_digest=source_digest,
                    profile_version=profile.profile_version,
                    profile_digest=profile.profile_digest,
                )
                has_transaction = materializer.has_transaction(metadata.operation_id)
                if not has_transaction and (
                    plan.status is UserCopyPlanStatus.BLOCKED
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
                    self._clear_provider_caches(metadata.provider)
                    self._gate.advance_generation(metadata.provider)
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
        metadata: UserCopyApplyMetadataContract,
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
        metadata: UserCopyApplyMetadataContract,
        *,
        has_snapshot: bool,
        has_transaction: bool,
    ) -> None:
        self._validate_runtime_identity(
            workspace_id=metadata.workspace_id,
            runtime_instance_id=metadata.runtime_instance_id,
        )
        if metadata.provider_state_root_id != self._user_copy_provider_state_root_id():
            raise MarketplaceOperationError(
                "marketplace.user_copy.runtime_state_invalid",
                http_status=500,
            )
        materializer = UserCopyMaterializer(operation_state_root=self._transaction_root)
        with self._mutation_store.provider_lock(
            provider=metadata.provider,
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
            profile = resolve_user_copy_profile(
                metadata.provider,
                snapshot.package_root,
            )
            preview = build_user_copy_profile_preview(
                snapshot.package_root,
                profile,
            )
            if (
                user_copy_source_digest_from_preview(preview)
                != metadata.expected_source_digest
                or profile.profile_version != metadata.expected_profile_version
                or profile.profile_digest != metadata.expected_profile_digest
            ):
                raise MarketplaceOperationError(
                    "marketplace.user_copy.runtime_state_invalid",
                    http_status=500,
                )
            plan = UserCopyPlanner(package_id=metadata.package_id).plan(
                profile,
                snapshot.package_root,
                inventory=self._inventory_provider.inventory(
                    metadata.provider,
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
        metadata: UserCopyApplyMetadataContract,
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
        metadata: UserCopyApplyMetadataContract,
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
    ) -> UserCopyApplyMetadataContract:
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
            metadata = UserCopyApplyMetadataContract.from_wire(value["metadata"])
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
    ) -> dict[str, UserCopyApplyMetadataContract]:
        self._ensure_recovery_root()
        envelopes: dict[str, UserCopyApplyMetadataContract] = {}
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

    def _clear_provider_caches(self, provider: str) -> None:
        clear_agent_settings_cache(
            provider=cast(MarketplaceProviderName, provider),
            workspace_id=self._settings.AILERON_WORKSPACE_ID,
            scope="user",
        )

    def _user_copy_provider_state_root_id(self) -> str:
        try:
            return self.provider_state_root_id
        except MarketplaceOperationError as exc:
            raise _user_copy_error(exc) from exc


def _apply_result(
    metadata: UserCopyApplyMetadataContract,
    result: UserCopyMaterializationResult,
) -> UserCopyApplyResultContract:
    return UserCopyApplyResultContract(
        operationId=metadata.operation_id,
        provider=metadata.provider,
        packageId=metadata.package_id,
        revision=metadata.revision,
        workspaceId=metadata.workspace_id,
        createdCount=result.created_count,
        mergedCount=result.merged_count,
        unchangedCount=result.unchanged_count,
        overwrittenCount=result.overwritten_count,
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
    provider: str,
    package_id: str,
    revision: str,
    workspace_id: str,
    runtime_instance_id: str,
    provider_state_root_id: str,
    source_digest: str,
    profile_version: int,
    profile_digest: str,
) -> str:
    """Bind a target plan to one source, Runtime, workspace, and provider root."""

    return canonical_digest(
        {
            "digestVersion": "marketplace-user-copy-materialization-v1",
            "planDigest": plan_digest,
            "provider": provider,
            "packageId": package_id,
            "revision": revision,
            "workspaceId": workspace_id,
            "runtimeInstanceId": runtime_instance_id,
            "providerStateRootId": provider_state_root_id,
            "sourceDigest": source_digest,
            "profileVersion": profile_version,
            "profileDigest": profile_digest,
        }
    )


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
