"""One-shot Marketplace package merge into Runtime user scope."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from aileron_file_core import (
    BuildArchiveRequest,
    FileCoreError,
    FileLocator,
    FileOperationEngine,
)
from aileron_marketplace_core import (
    PackageSourceError,
    PluginReleaseIdentity,
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyOverwriteApprovalContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
    UserCopySourceProfile,
    UserCopySourceProfilePreviewContract,
    decode_json_pointer,
    extract_user_copy_source_profile,
    package_tree_digest,
    validate_source_locator,
)
from app.modules.marketplace.target_clients import create_package_format_adapters
from sqlalchemy.orm import Session

from app.modules.marketplace.models import (
    MarketplacePackageSummary,
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyApplyResult,
    MarketplaceUserCopyBlockingIssue,
    MarketplaceUserCopyConflict,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
    MarketplaceUserCopyResource,
    MarketplaceSkippedUserCopyResource,
)
from app.modules.marketplace.runtime_client import (
    MarketplaceRuntimeClient,
    MarketplaceRuntimeClientError,
)
from app.modules.workspace.access_repository import WorkspaceAccessRepository

_MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)


class MarketplaceUserCopyError(RuntimeError):
    """Typed public failure for one-shot user-copy operations."""

    def __init__(self, code: str, *, http_status: int = 409) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(code)


@dataclass(frozen=True)
class _RuntimeDescriptor:
    runtime_url: str
    runtime_instance_id: str


@dataclass(frozen=True)
class _SparseSource:
    root: Path
    profile: UserCopySourceProfile
    preview: UserCopySourceProfilePreviewContract
    source_digest: str
    package_tree_digest: str


class MarketplaceUserCopyRegistryPort(Protocol):
    """Narrow registry seam required by the user-copy workflow."""

    def open_user_copy_source(
        self,
        user_id: str,
        catalog_plugin_id: str,
        package_format: str,
        target_client: str,
    ) -> AbstractContextManager[tuple[MarketplacePackageSummary, Path]]: ...

    def file_engine_for_root(
        self,
        *,
        root: Path,
        registry_root: Path,
        invalidation_key: str,
    ) -> FileOperationEngine: ...

    def resolve_install_runtime(
        self,
        workspace_id: str,
    ) -> dict[str, str | None]: ...

    def record_activity(self, user_id: str, **kwargs: Any) -> Any: ...


class MarketplaceUserCopyService:
    """Preflight and apply user-copy without creating managed installation state."""

    def __init__(
        self,
        db: Session,
        registry: MarketplaceUserCopyRegistryPort,
        *,
        runtime_client: MarketplaceRuntimeClient | None = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.workspace_access = WorkspaceAccessRepository(db)
        self.runtime_client = runtime_client or MarketplaceRuntimeClient()

    def preflight(
        self,
        user_id: str,
        request: MarketplaceUserCopyRequest,
    ) -> MarketplaceUserCopyPreflightResult:
        """Return a fresh Runtime plan for the canonical sparse package."""

        self._require_workspace_mutator(
            workspace_id=request.workspace_id,
            user_id=user_id,
        )
        with self._sparse_source(user_id, request) as source:
            runtime = self._require_runtime_descriptor(request.workspace_id)
            contract = self._preflight_contract(
                request=request,
                runtime=runtime,
                source=source,
            )
            try:
                result = self.runtime_client.preflight_user_copy(
                    runtime_url=runtime.runtime_url,
                    workspace_id=request.workspace_id,
                    runtime_instance_id=runtime.runtime_instance_id,
                    request=contract,
                )
                self._verify_preflight(
                    result,
                    request=request,
                    runtime_instance_id=runtime.runtime_instance_id,
                    source=source,
                )
            except MarketplaceRuntimeClientError as exc:
                raise self._runtime_error(exc) from exc
            return self._typed_public_preflight_result(
                result,
                request=request,
                source=source,
            )

    def apply(
        self,
        user_id: str,
        request: MarketplaceUserCopyApplyRequest,
    ) -> MarketplaceUserCopyApplyResult:
        """Apply a preflighted plan and persist only an append-only audit event."""

        self._require_workspace_mutator(
            workspace_id=request.workspace_id,
            user_id=user_id,
        )
        operation_id = uuid4().hex
        try:
            with self._sparse_source(user_id, request) as source:
                if source.source_digest != request.expected_source_digest:
                    raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
                runtime = self._require_runtime_descriptor(request.workspace_id)
                preflight_contract = self._preflight_contract(
                    request=request,
                    runtime=runtime,
                    source=source,
                )
                wire_preflight = self.runtime_client.preflight_user_copy(
                    runtime_url=runtime.runtime_url,
                    workspace_id=request.workspace_id,
                    runtime_instance_id=runtime.runtime_instance_id,
                    request=preflight_contract,
                )
                self._verify_preflight(
                    wire_preflight,
                    request=request,
                    runtime_instance_id=runtime.runtime_instance_id,
                    source=source,
                )
                preflight = self._typed_public_preflight_result(
                    wire_preflight,
                    request=request,
                    source=source,
                )
                if (
                    preflight.profile_digest != request.expected_profile_digest
                    or preflight.projection_digest != request.expected_projection_digest
                    or preflight.materialization_digest
                    != request.expected_materialization_digest
                ):
                    raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
                self._validate_confirmations(request, preflight)
                if preflight.status == "blocked":
                    raise MarketplaceUserCopyError(
                        preflight.blocking_issues[0].error_code
                        if preflight.blocking_issues
                        else "marketplace.user_copy.apply_failed"
                    )
                archive = self._build_archive(source.root)
                archive_digest = sha256(archive).hexdigest()
                metadata = UserCopyProjectionApplyMetadataContract(
                    operationId=operation_id,
                    packageFormat=request.package_format,
                    targetClient=request.target_client,
                    catalogPluginId=request.catalog_plugin_id,
                    releaseRevision=request.release_revision,
                    workspaceId=request.workspace_id,
                    runtimeInstanceId=runtime.runtime_instance_id,
                    targetClientStateRootId=wire_preflight.target_client_state_root_id,
                    expectedSourceDigest=source.source_digest,
                    expectedArchiveDigest=archive_digest,
                    expectedPackageTreeDigest=source.package_tree_digest,
                    expectedProfileVersion=source.profile.profile_version,
                    expectedProfileDigest=source.profile.profile_digest,
                    expectedProjectionDigest=preflight.projection_digest,
                    expectedMaterializationDigest=preflight.materialization_digest,
                    acceptPartialCopy=request.accept_partial_copy,
                    expectedSkippedCount=len(preflight.skipped_resources),
                    overwriteApprovals=[
                        UserCopyOverwriteApprovalContract.model_validate(
                            approval.model_dump(by_alias=True)
                        )
                        for approval in request.overwrite_approvals
                    ],
                )
                wire_result = self.runtime_client.apply_user_copy(
                    runtime_url=runtime.runtime_url,
                    workspace_id=request.workspace_id,
                    runtime_instance_id=runtime.runtime_instance_id,
                    metadata=metadata,
                    bundle=archive,
                )
                metadata.verify_result(
                    wire_result,
                    expected_counts=wire_preflight.expected_result_counts,
                )
                result = self._typed_apply_result(
                    wire_result,
                    request=request,
                    operation_id=operation_id,
                )
        except MarketplaceRuntimeClientError as exc:
            error = self._runtime_error(exc)
            self._record_activity(
                user_id=user_id,
                request=request,
                operation_id=operation_id,
                status="failed",
                error_code=error.code,
            )
            raise error from exc
        except MarketplaceUserCopyError as exc:
            self._record_activity(
                user_id=user_id,
                request=request,
                operation_id=operation_id,
                status="failed",
                error_code=exc.code,
            )
            raise

        self._record_activity(
            user_id=user_id,
            request=request,
            operation_id=operation_id,
            status="succeeded",
            error_code=None,
            preflight=preflight,
            result=result,
        )
        return result

    @contextmanager
    def _sparse_source(
        self,
        user_id: str,
        request: MarketplaceUserCopyRequest,
    ) -> Iterator[_SparseSource]:
        with tempfile.TemporaryDirectory(prefix="marketplace-user-copy-") as tmp:
            sparse_root = Path(tmp) / "package"
            sparse_root.mkdir()
            try:
                with self.registry.open_user_copy_source(
                    user_id,
                    request.catalog_plugin_id,
                    request.package_format,
                    request.target_client,
                ) as source:
                    summary, package_root = source
                    if (
                        summary.catalog_plugin_id != request.catalog_plugin_id
                        or summary.package_format != request.package_format
                        or summary.user_copy_target_client != request.target_client
                    ):
                        raise MarketplaceUserCopyError(
                            "marketplace.user_copy.package_identity_mismatch"
                        )
                    if summary.revision != request.release_revision:
                        raise MarketplaceUserCopyError(
                            "marketplace.user_copy.revision_conflict"
                        )
                    try:
                        release = PluginReleaseIdentity(
                            catalog_plugin_id=request.catalog_plugin_id,
                            revision=request.release_revision,
                        )
                        full_profile = extract_user_copy_source_profile(
                            request.package_format,
                            package_root,
                            release=release,
                        )
                        self._materialize_sparse_root(
                            package_root=package_root,
                            sparse_root=sparse_root,
                            package_format=request.package_format,
                            profile=full_profile,
                            dependency_locators=tuple(
                                reference.source_locator
                                for resource in full_profile.resources
                                for reference in resource.dependency_references
                            ),
                        )
                        profile = extract_user_copy_source_profile(
                            request.package_format,
                            sparse_root,
                            release=release,
                        )
                        preview_payload = profile.canonical_dict()
                        preview_payload["profileDigest"] = profile.profile_digest
                        preview = UserCopySourceProfilePreviewContract.from_wire(
                            preview_payload
                        )
                        source_digest = package_tree_digest(sparse_root)
                    except (OSError, PackageSourceError, ValueError) as exc:
                        raise MarketplaceUserCopyError(
                            "marketplace.user_copy.source_invalid"
                        ) from exc
            except FileNotFoundError as exc:
                raise MarketplaceUserCopyError(
                    "marketplace.user_copy.package_not_found",
                    http_status=404,
                ) from exc
            except MarketplaceUserCopyError:
                raise
            except (OSError, PackageSourceError, ValueError) as exc:
                raise MarketplaceUserCopyError(
                    "marketplace.user_copy.source_invalid"
                ) from exc
            yield _SparseSource(
                root=sparse_root,
                profile=profile,
                preview=preview,
                source_digest=source_digest,
                package_tree_digest=source_digest,
            )

    def _materialize_sparse_root(
        self,
        *,
        package_root: Path,
        sparse_root: Path,
        package_format: str,
        profile: UserCopySourceProfile,
        dependency_locators: tuple[str, ...],
    ) -> None:
        """Copy canonical profile sources and their exact dependency closure."""

        resolved_package_root = package_root.resolve(strict=True)
        if package_root.is_symlink() or not resolved_package_root.is_dir():
            raise ValueError("Invalid package root")
        locators = {
            _manifest_locator(package_format),
            *(resource.source_locator for resource in profile.resources),
            *dependency_locators,
            *self._diagnostic_source_locators(package_root, profile),
        }
        copied: set[str] = set()
        for raw_locator in sorted(locators):
            locator = raw_locator.split("#", 1)[0].replace("\\", "/")
            parts = Path(locator).parts
            if (
                not locator
                or Path(locator).is_absolute()
                or any(part in {"", ".", ".."} for part in parts)
            ):
                continue
            source = package_root.joinpath(*parts)
            if not source.exists():
                continue
            resolved_source = source.resolve(strict=True)
            try:
                resolved_source.relative_to(resolved_package_root)
            except ValueError as exc:
                raise ValueError("Sparse source escapes package root") from exc
            self._reject_symlinks(package_root, source)
            relative = source.relative_to(package_root).as_posix()
            if any(
                relative == existing or relative.startswith(f"{existing}/")
                for existing in copied
            ):
                continue
            target = sparse_root.joinpath(*Path(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            elif source.is_file():
                shutil.copy2(source, target)
            else:
                raise ValueError("Unsupported sparse source entry")
            copied.add(relative)

    @staticmethod
    def _diagnostic_source_locators(
        package_root: Path,
        profile: UserCopySourceProfile,
    ) -> set[str]:
        """Return bounded source files required to reproduce diagnostics."""

        locators: set[str] = set()
        for diagnostic in profile.diagnostics:
            source_locator, separator, pointer = diagnostic.source_locator.partition(
                "#"
            )
            try:
                canonical = validate_source_locator(source_locator)
            except PackageSourceError:
                continue
            locators.add(canonical)
            if not separator:
                continue
            try:
                document = json.loads(
                    package_root.joinpath(*Path(canonical).parts).read_text(
                        encoding="utf-8"
                    )
                )
                value: Any = document
                for token in decode_json_pointer(pointer):
                    if isinstance(value, dict):
                        value = value[token]
                    elif isinstance(value, list):
                        value = value[int(token)]
                    else:
                        raise KeyError(token)
            except (
                IndexError,
                KeyError,
                OSError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue
            references = (
                [value]
                if isinstance(value, str)
                else value
                if isinstance(value, list)
                else []
            )
            for reference in references:
                if not isinstance(reference, str):
                    continue
                try:
                    locators.add(validate_source_locator(reference.removeprefix("./")))
                except PackageSourceError:
                    continue
        return locators

    @staticmethod
    def _reject_symlinks(package_root: Path, source: Path) -> None:
        current = source
        while current != package_root:
            if current.is_symlink():
                raise ValueError("Symlink is not allowed")
            current = current.parent
        if source.is_dir() and any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("Symlink is not allowed")

    def _build_archive(self, sparse_root: Path) -> bytes:
        try:
            result = self.registry.file_engine_for_root(
                root=sparse_root,
                registry_root=sparse_root,
                invalidation_key="marketplace-user-copy",
            ).build_archive_bytes(
                BuildArchiveRequest(
                    locator=FileLocator(
                        domain="marketplace",
                        resource_id="user-copy",
                    ),
                    paths=sorted(child.name for child in sparse_root.iterdir()),
                    archive_root="",
                    reject_symlinks=True,
                )
            )
        except FileCoreError as exc:
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.source_invalid"
            ) from exc
        if len(result.content) > _MAX_ARCHIVE_BYTES:
            raise MarketplaceUserCopyError("marketplace.user_copy.source_invalid")
        return result.content

    def _require_runtime_descriptor(self, workspace_id: str) -> _RuntimeDescriptor:
        raw = self.registry.resolve_install_runtime(workspace_id)
        runtime_url = raw.get("runtimeUrl")
        runtime_instance_id = raw.get("runtimeInstanceId")
        if (
            raw.get("errorCode")
            or not isinstance(runtime_url, str)
            or not runtime_url
            or not isinstance(runtime_instance_id, str)
            or not runtime_instance_id
        ):
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_unavailable",
                http_status=503,
            )
        try:
            descriptor = self.runtime_client.descriptor(
                runtime_url=runtime_url,
                workspace_id=workspace_id,
                runtime_instance_id=runtime_instance_id,
            )
        except MarketplaceRuntimeClientError as exc:
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_unavailable",
                http_status=503,
            ) from exc
        details = descriptor.get("details")
        if not isinstance(details, dict):
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=503,
            )
        descriptor_runtime_id = details.get("runtimeInstanceId")
        if descriptor_runtime_id != runtime_instance_id:
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=503,
            )
        return _RuntimeDescriptor(
            runtime_url=runtime_url,
            runtime_instance_id=runtime_instance_id,
        )

    @staticmethod
    def _preflight_contract(
        *,
        request: MarketplaceUserCopyRequest,
        runtime: _RuntimeDescriptor,
        source: _SparseSource,
    ) -> UserCopyProjectionPreflightRequestContract:
        return UserCopyProjectionPreflightRequestContract(
            packageFormat=request.package_format,
            targetClient=request.target_client,
            catalogPluginId=request.catalog_plugin_id,
            releaseRevision=request.release_revision,
            workspaceId=request.workspace_id,
            runtimeInstanceId=runtime.runtime_instance_id,
            expectedSourceDigest=source.source_digest,
            expectedProfileVersion=source.profile.profile_version,
            expectedProfileDigest=source.profile.profile_digest,
            sourceProfile=source.preview,
        )

    @staticmethod
    def _typed_public_preflight_result(
        result: UserCopyProjectionPreflightResultContract,
        *,
        request: MarketplaceUserCopyRequest,
        source: _SparseSource,
    ) -> MarketplaceUserCopyPreflightResult:
        return MarketplaceUserCopyPreflightResult(
            status=result.status,
            packageFormat=request.package_format,
            targetClient=request.target_client,
            catalogPluginId=request.catalog_plugin_id,
            releaseRevision=request.release_revision,
            workspaceId=request.workspace_id,
            sourceDigest=source.source_digest,
            profileDigest=source.profile.profile_digest,
            projectionDigest=result.projection_digest,
            materializationDigest=result.materialization_digest,
            resources=[
                MarketplaceUserCopyResource(
                    resourceType=resource.resource_type,
                    resourceId=resource.resource_id,
                    sourceLocator=resource.source_locator,
                    targetLocator=resource.target_locator,
                    operation=resource.action,
                )
                for resource in result.resources
            ],
            skippedResources=[
                MarketplaceSkippedUserCopyResource(
                    code=item.code,
                    resourceType=item.resource_type,
                    resourceId=item.resource_id,
                    sourceLocator=item.source_locator,
                )
                for item in result.skipped_resources
            ],
            conflicts=[
                MarketplaceUserCopyConflict(
                    resourceType=conflict.resource_type,
                    resourceId=conflict.resource_id,
                    sourceLocator=conflict.source_locator,
                    targetLocator=conflict.target_locator,
                    targetIdentity=conflict.target_identity,
                    baselineRevision=conflict.baseline_revision,
                    incomingDigest=conflict.incoming_digest,
                    overwritable=conflict.overwritable,
                )
                for conflict in result.conflicts
            ],
            blockingIssues=[
                MarketplaceUserCopyBlockingIssue(
                    resourceType=issue.resource_type,
                    resourceId=issue.resource_id,
                    sourceLocator=issue.source_locator,
                    targetLocator=issue.target_locator,
                    errorCode=issue.code,
                )
                for issue in result.blocking_issues
            ],
        )

    @staticmethod
    def _typed_apply_result(
        result: UserCopyProjectionApplyResultContract,
        *,
        request: MarketplaceUserCopyApplyRequest,
        operation_id: str,
    ) -> MarketplaceUserCopyApplyResult:
        return MarketplaceUserCopyApplyResult(
            status="completed",
            operationId=operation_id,
            packageFormat=request.package_format,
            targetClient=request.target_client,
            catalogPluginId=request.catalog_plugin_id,
            releaseRevision=request.release_revision,
            workspaceId=request.workspace_id,
            createdCount=result.created_count,
            mergedCount=result.merged_count,
            unchangedCount=result.unchanged_count,
            overwrittenCount=result.overwritten_count,
            skippedCount=result.skipped_count,
        )

    @staticmethod
    def _verify_preflight(
        result: UserCopyProjectionPreflightResultContract,
        *,
        request: MarketplaceUserCopyRequest,
        runtime_instance_id: str,
        source: _SparseSource,
    ) -> None:
        if (
            result.package_format != request.package_format
            or result.target_client != request.target_client
            or result.catalog_plugin_id != request.catalog_plugin_id
            or result.release_revision != request.release_revision
            or result.workspace_id != request.workspace_id
            or result.runtime_instance_id != runtime_instance_id
            or result.source_digest != source.source_digest
            or result.profile_version != source.profile.profile_version
            or result.profile_digest != source.profile.profile_digest
        ):
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=503,
            )

    @classmethod
    def _validate_confirmations(
        cls,
        request: MarketplaceUserCopyApplyRequest,
        preflight: MarketplaceUserCopyPreflightResult,
    ) -> None:
        if preflight.status == "confirmation-required":
            cls._validate_overwrite_approvals(request, preflight)
        elif request.overwrite_approvals:
            raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
        if bool(preflight.skipped_resources) != request.accept_partial_copy:
            raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")

    def _validate_overwrite_approvals(
        request: MarketplaceUserCopyApplyRequest,
        preflight: MarketplaceUserCopyPreflightResult,
    ) -> None:
        supplied = [
            (approval.target_identity, approval.expected_revision)
            for approval in request.overwrite_approvals
        ]
        supplied_identities = [identity for identity, _ in supplied]
        if len(supplied) != len(set(supplied)) or len(supplied_identities) != len(
            set(supplied_identities)
        ):
            raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
        expected = {
            (conflict.target_identity, conflict.baseline_revision)
            for conflict in preflight.conflicts
        }
        supplied_set = set(supplied)
        if supplied_set.difference(expected):
            raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
        if expected.difference(supplied_set):
            raise MarketplaceUserCopyError("marketplace.user_copy.plan_stale")

    def _require_workspace_mutator(
        self,
        *,
        workspace_id: str,
        user_id: str,
    ) -> None:
        if not self.workspace_access.actor_can_mutate(
            workspace_id=workspace_id,
            user_id=user_id,
        ):
            raise MarketplaceUserCopyError(
                "marketplace.user_copy.workspace_access_denied",
                http_status=403,
            )

    @staticmethod
    def _runtime_error(
        error: MarketplaceRuntimeClientError,
    ) -> MarketplaceUserCopyError:
        if error.code == "marketplace.user_copy.rollback_failed":
            return MarketplaceUserCopyError(error.code, http_status=500)
        if error.code in {
            "marketplace.user_copy.materialization_mismatch",
            "marketplace.user_copy.overwrite_approval_invalid",
            "marketplace.user_copy.operation_conflict",
        }:
            return MarketplaceUserCopyError("marketplace.user_copy.plan_stale")
        if error.code.startswith("marketplace.user_copy.archive_"):
            return MarketplaceUserCopyError("marketplace.user_copy.source_invalid")
        if error.code in {
            "marketplace.user_copy.runtime_delegation_unavailable",
        }:
            return MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_unavailable",
                http_status=503,
            )
        if error.code in {
            "marketplace.user_copy.runtime_contract_invalid",
            "marketplace.user_copy.runtime_state_invalid",
        }:
            return MarketplaceUserCopyError(
                "marketplace.user_copy.runtime_contract_invalid",
                http_status=503,
            )
        return MarketplaceUserCopyError("marketplace.user_copy.apply_failed")

    def _record_activity(
        self,
        *,
        user_id: str,
        request: MarketplaceUserCopyApplyRequest,
        operation_id: str,
        status: str,
        error_code: str | None,
        preflight: MarketplaceUserCopyPreflightResult | None = None,
        result: MarketplaceUserCopyApplyResult | None = None,
    ) -> None:
        try:
            self.registry.record_activity(
                user_id,
                action="copy",
                status=status,
                package_format=request.package_format,
                target_client=request.target_client,
                package_id=request.catalog_plugin_id,
                operation_id=operation_id,
                workspace_id=request.workspace_id,
                error_code=error_code,
                catalog_plugin_id=request.catalog_plugin_id,
                release_revision=request.release_revision,
                profile_digest=(preflight.profile_digest if preflight else None),
                projection_digest=(preflight.projection_digest if preflight else None),
                projected_count=(len(preflight.resources) if preflight else None),
                skipped_count=(
                    result.skipped_count
                    if result
                    else (len(preflight.skipped_resources) if preflight else None)
                ),
                conflict_count=(len(preflight.conflicts) if preflight else None),
                created_count=(result.created_count if result else None),
                merged_count=(result.merged_count if result else None),
                unchanged_count=(result.unchanged_count if result else None),
                overwritten_count=(result.overwritten_count if result else None),
                target_locators=(
                    tuple(
                        dict.fromkeys(
                            [
                                *(item.target_locator for item in preflight.resources),
                                *(item.target_locator for item in preflight.conflicts),
                            ]
                        )
                    )
                    if preflight
                    else ()
                ),
                diagnostic_codes=(
                    tuple(
                        dict.fromkeys(
                            [
                                *(item.code for item in preflight.skipped_resources),
                                *(
                                    item.error_code
                                    for item in preflight.blocking_issues
                                ),
                            ]
                        )
                    )
                    if preflight
                    else ()
                ),
            )
        except Exception:
            _LOGGER.exception("Failed to append one-shot Marketplace copy activity")


def _manifest_locator(package_format: str) -> str:
    return str(create_package_format_adapters()[package_format].manifest_path(Path()))
