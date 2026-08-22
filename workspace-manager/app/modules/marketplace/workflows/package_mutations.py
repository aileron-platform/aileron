"""Marketplace package mutations workflow module."""

from __future__ import annotations

from collections.abc import Sequence
from io import BytesIO
import json
from typing import BinaryIO

from aileron_marketplace_core import (
    PackageSourceError,
    hook_map,
    validate_inline_hooks,
)
from aileron_file_core import (
    CopyEntriesRequest,
    CreateEntryRequest,
    DeleteEntryRequest,
    ExtractArchiveRequest,
    ExtractArchiveStreamRequest,
    FileCoreError,
    FileLocator,
    MoveEntryRequest,
    UploadStreamItem,
    to_file_conflict_preflight,
    to_upload_batch_result,
)
from aileron_file_core import (
    FileConflictResolution as CoreFileConflictResolution,
)
from aileron_git_core import OperationKind

from app.core.file_management import (
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileExtractExecutionRequest,
)
from app.modules.marketplace.models import (
    MarketplaceBasicUpdateRequest,
    MarketplaceDocumentMutationRequest,
    MarketplaceDocumentRemoveRequest,
    MarketplaceDocumentRenameRequest,
    MarketplaceMcpServerCreateRequest,
    MarketplaceMcpServerDeleteRequest,
    MarketplaceMcpServerMutationRequest,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageDeleteResult,
    MarketplacePackageDetail,
    MarketplacePackageMutationResult,
    MarketplacePackageSaveRequest,
    MarketplaceTargetClient,
)
from app.modules.marketplace.resource_mutations import (
    canonical_entry_fingerprint,
    default_mcp_owner,
    document_resource_root,
    get_json_entry,
    load_root_document_path,
    patch_json_entry,
    read_json_file,
    remove_json_entry,
    validate_package_relative_path,
)
from app.modules.marketplace.resource_resolvers import (
    hook_source_id,
    read_hook_source,
    resolve_mcp_owner,
    resolve_mcp_owners,
    resolve_hook_sources,
)
from app.modules.marketplace.target_clients import create_package_format_adapters

from .kernel import _MarketplaceRegistrySupport
from .package_reads import MarketplacePackageReadModel
from .registry_operations import (
    MarketplaceConflictError,
    MarketplacePathError,
    MarketplaceValidationError,
    _MarketplaceRegistryContext,
    _registry_git_operation,
    _resource_write_locks,
)
from .settings_activity import MarketplaceSettingsActivityWorkflow


class MarketplacePackageMutationWorkflow(_MarketplaceRegistrySupport):
    """Apply package and resource mutations as revision-fenced workflows."""

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

    @staticmethod
    def _core_conflict_resolutions(
        resolutions: Sequence[FileConflictResolution],
    ) -> tuple[CoreFileConflictResolution, ...]:
        return tuple(
            CoreFileConflictResolution(
                source_path=resolution.sourcePath,
                strategy=resolution.strategy,
            )
            for resolution in resolutions
        )

    @staticmethod
    def _file_preflight_response(result) -> FileConflictPreflightResponse:
        return FileConflictPreflightResponse.model_validate(
            to_file_conflict_preflight(result)
        )

    @staticmethod
    def _file_batch_response(result) -> FileConflictBatchResult:
        return FileConflictBatchResult.model_validate(to_upload_batch_result(result))

    def _package_file_engine(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
    ):
        detail = self._get_package_detail_for_mutation(
            user_id, target_client, package_id
        )
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        package_path = self._resolve_package_path(user_id, target_client, package_id)
        return (
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ),
            package_path,
        )

    @_registry_git_operation(OperationKind.WRITE, "create_package")
    def create_package(
        self,
        user_id: str,
        request: MarketplacePackageCreateRequest,
    ) -> MarketplacePackageDetail:
        """Create a format-first Managed Plugin scaffold."""
        with self._registry_lock:
            self._settings_activity.initialize_registry(user_id)
            adapter = create_package_format_adapters()[request.package_format]
            if set(request.target_clients) != {adapter.target_client}:
                raise MarketplacePathError("marketplace.package.variant_invalid")
            root = self._get_registry_root(user_id)
            if any(
                entry.package_id == request.package_id
                for entry in self._read_catalog(root).packages
            ):
                raise FileExistsError("marketplace.package.already_exists")
            package_path = self._resolve_package_path(
                user_id,
                adapter.target_client,
                request.package_id,
                request.package_format,
            )
            if package_path.exists():
                raise FileExistsError("marketplace.package.already_exists")
            # Validate the prospective manifest against target_client requirements before
            # touching disk so callers cannot create packages in an invalid state.
            prospective_manifest = {
                "name": request.package_id,
                "version": request.version,
                "description": request.description,
            }
            relative_manifest_path = str(
                adapter.manifest_path(package_path).relative_to(package_path),
            )
            self._raise_if_validation_blocks(
                adapter.validate_manifest_data(
                    package_id=request.package_id,
                    manifest=prospective_manifest,
                    file_path=relative_manifest_path,
                ),
                "create",
            )
            self._create_package_scaffold_with_core(
                adapter,
                package_path,
                request,
                invalidation_key=user_id,
            )
            if adapter.target_client == "claude-code":
                self._upsert_listing_entry_with_core(
                    adapter,
                    self._get_registry_root(user_id),
                    request.package_id,
                    {
                        "name": request.package_id,
                        "source": f"./plugins/{request.package_id}",
                        "description": request.description,
                    },
                    invalidation_key=user_id,
                )
            elif adapter.target_client == "codex":
                self._upsert_listing_entry_with_core(
                    adapter,
                    self._get_registry_root(user_id),
                    request.package_id,
                    {
                        "name": request.package_id,
                        "source": {
                            "source": "local",
                            "path": f"./plugins/{request.package_id}",
                        },
                        "description": request.description,
                        "category": "uncategorized",
                    },
                    invalidation_key=user_id,
                )
            detail = self._package_reads.get_package_detail(
                user_id,
                adapter.target_client,
                request.package_id,
                request.package_format,
                use_cache=False,
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            return detail

    @_registry_git_operation(OperationKind.WRITE, "delete_package")
    def delete_package(
        self,
        user_id: str,
        request: MarketplacePackageDeleteRequest,
    ) -> MarketplacePackageDeleteResult:
        """Hard delete the current Managed Plugin working tree."""
        with self._registry_lock:
            detail = self._get_package_detail_for_mutation(
                user_id, request.target_client, request.package_id
            )
            if detail is None:
                self._settings_activity.record_activity(
                    user_id,
                    action="delete",
                    status="failed",
                    target_client=request.target_client,
                    package_id=request.package_id,
                    error_code="marketplace.package.not_found",
                )
                return MarketplacePackageDeleteResult(
                    deleted=False,
                    error_code="marketplace.package.not_found",
                )
            try:
                package_path = self._resolve_package_path(
                    user_id, request.target_client, request.package_id
                )
                if package_path.exists():
                    registry_root = self._get_registry_root(user_id)
                    plugins_root = package_path.parent
                    try:
                        self._file_engine_for_root(
                            root=plugins_root,
                            registry_root=registry_root,
                            invalidation_key=user_id,
                        ).delete_entry(
                            DeleteEntryRequest(
                                locator=FileLocator(
                                    domain="marketplace",
                                    resource_id="registry",
                                ),
                                path=package_path.name,
                                recursive=True,
                            )
                        )
                    except FileCoreError as exc:
                        raise MarketplacePathError(
                            "marketplace.package.path_escape"
                        ) from exc
                if request.target_client in {"claude-code", "codex"}:
                    adapter = self._get_adapter(request.target_client)
                    self._remove_listing_entry_with_core(
                        adapter,
                        self._get_registry_root(user_id),
                        request.package_id,
                        invalidation_key=user_id,
                    )
                self._settings_activity.record_activity(
                    user_id,
                    action="delete",
                    status="succeeded",
                    package_format=detail.package_format,
                    target_client=request.target_client,
                    package_id=request.package_id,
                )
                return MarketplacePackageDeleteResult(
                    deleted=True,
                    revision=f"deleted-{detail.revision}",
                )
            finally:
                self._invalidate_package_overview(
                    user_id,
                    request.target_client,
                    request.package_id,
                )

    def save_root_document(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        content: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            path = load_root_document_path(target_client, package_path)
            self._write_text_with_core(path, content, invalidation_key=user_id)
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=path.relative_to(package_path).as_posix(),
            )

    def create_document(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        resource_type: str,
        request: MarketplaceDocumentMutationRequest,
    ) -> MarketplacePackageMutationResult:
        package_path = self._resolve_package_path(user_id, target_client, package_id)
        relative_path = validate_package_relative_path(request.path)
        root = document_resource_root(target_client, resource_type)
        if not str(relative_path).startswith(f"{root}/"):
            raise MarketplacePathError("marketplace.package.path_escape")
        if (package_path / str(relative_path)).exists():
            raise MarketplaceConflictError("marketplace.resource.entry_conflict")
        return self.update_document(
            user_id, target_client, package_id, resource_type, request
        )

    def update_document(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        resource_type: str,
        request: MarketplaceDocumentMutationRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            relative_path = validate_package_relative_path(request.path)
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            root = document_resource_root(target_client, resource_type)
            if not str(relative_path).startswith(f"{root}/"):
                raise MarketplacePathError("marketplace.package.path_escape")
            target = package_path / str(relative_path)
            self._write_text_with_core(
                target, request.content, invalidation_key=user_id
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path.as_posix(),
            )

    def move_document(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        resource_type: str,
        request: MarketplaceDocumentRenameRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            root = document_resource_root(target_client, resource_type)
            previous_path = validate_package_relative_path(request.previous_path)
            next_path = validate_package_relative_path(request.next_path)
            if not str(previous_path).startswith(f"{root}/") or not str(
                next_path
            ).startswith(f"{root}/"):
                raise MarketplacePathError("marketplace.package.path_escape")
            source = package_path / str(previous_path)
            target = package_path / str(next_path)
            if not source.is_file():
                raise FileNotFoundError("marketplace.resource.not_found")
            content = self._read_text_file(source)
            self._write_text_with_core(target, content, invalidation_key=user_id)
            try:
                self._file_engine_for_root(
                    root=package_path,
                    registry_root=self._get_registry_root(user_id),
                    invalidation_key=user_id,
                ).delete_entry(
                    DeleteEntryRequest(
                        locator=FileLocator(
                            domain="marketplace", resource_id="registry"
                        ),
                        path=str(previous_path),
                    )
                )
            except FileCoreError as exc:
                raise MarketplacePathError("marketplace.package.path_escape") from exc
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=next_path.as_posix(),
            )

    def remove_document(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        resource_type: str,
        request: MarketplaceDocumentRemoveRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            root = document_resource_root(target_client, resource_type)
            relative_path = validate_package_relative_path(request.path)
            if not str(relative_path).startswith(f"{root}/"):
                raise MarketplacePathError("marketplace.package.path_escape")
            target = package_path / str(relative_path)
            if not target.is_file():
                raise FileNotFoundError("marketplace.resource.not_found")
            try:
                self._file_engine_for_root(
                    root=package_path,
                    registry_root=self._get_registry_root(user_id),
                    invalidation_key=user_id,
                ).delete_entry(
                    DeleteEntryRequest(
                        locator=FileLocator(
                            domain="marketplace", resource_id="registry"
                        ),
                        path=str(relative_path),
                    )
                )
            except FileCoreError as exc:
                raise MarketplacePathError("marketplace.package.path_escape") from exc
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path.as_posix(),
            )

    def create_mcp_server(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        request: MarketplaceMcpServerCreateRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            if any(
                binding.name == request.name
                for binding in resolve_mcp_owners(package_path, target_client)
            ):
                raise MarketplaceConflictError("marketplace.resource.entry_conflict")
            try:
                owner = default_mcp_owner(package_path, request.name, target_client)
            except ValueError as exc:
                raise MarketplacePathError(str(exc)) from exc
            owner_path = package_path / owner.file_path
            data = read_json_file(owner_path)
            pointer = owner.json_pointer
            if pointer is None:
                raise MarketplacePathError("marketplace.resource.invalid_json_root")
            if get_json_entry(data, pointer) is not None:
                raise MarketplaceConflictError("marketplace.resource.entry_conflict")
            patched = patch_json_entry(data, pointer, request.server)
            self._write_json_with_core(owner_path, patched, invalidation_key=user_id)
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=owner.file_path,
                owner_file_path=owner.file_path,
                base_entry_fingerprint=canonical_entry_fingerprint(request.server),
            )

    def update_basic_metadata(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        payload: MarketplaceBasicUpdateRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            adapter = self._get_adapter(target_client)
            try:
                manifest = adapter.read_manifest(package_path)  # type: ignore[attr-defined]
                if payload.display_name is not None:
                    manifest["displayName"] = payload.display_name
                if payload.description is not None:
                    manifest["description"] = payload.description
                manifest.update(payload.manifest_metadata)
                self._write_json_with_core(
                    adapter.manifest_path(package_path),
                    manifest,
                    invalidation_key=user_id,
                )
                listing = (
                    adapter.read_listing_entry(
                        self._get_registry_root(user_id), package_id
                    )
                    or {}
                )
                if payload.display_name is not None:
                    listing["displayName"] = payload.display_name
                if payload.description is not None:
                    listing["description"] = payload.description
                listing.update(payload.catalog_metadata)
                self._upsert_listing_entry_with_core(
                    adapter,
                    self._get_registry_root(user_id),
                    package_id,
                    listing,
                    invalidation_key=user_id,
                )
                return self._mutation_result_for_package(
                    user_id,
                    target_client,
                    package_id,
                    path=adapter.manifest_path(package_path)
                    .relative_to(package_path)
                    .as_posix(),
                )
            finally:
                self._invalidate_package_overview(user_id, target_client, package_id)

    def save_package(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        payload: MarketplacePackageSaveRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            if (
                payload.target_client != target_client
                or payload.package_id != package_id
            ):
                raise MarketplacePathError("marketplace.package.path_escape")
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            adapter = self._get_adapter(target_client)
            manifest_path = adapter.manifest_path(package_path)
            relative_manifest_path = str(manifest_path.relative_to(package_path))
            listing, _ = self._strip_root_metadata(payload.listing)
            validation_results = [
                *adapter.validate_manifest_data(
                    package_id=package_id,
                    manifest=payload.manifest,
                    file_path=relative_manifest_path,
                ),
                *self._validate_listing_entry(package_id, listing),
            ]
            self._raise_if_validation_blocks(validation_results, "save")

            try:
                self._sync_package_files(
                    package_path,
                    payload.package_files,
                    invalidation_key=user_id,
                )
                self._write_json_with_core(
                    manifest_path,
                    payload.manifest,
                    invalidation_key=user_id,
                )
                if payload.readme_markdown is not None:
                    self._write_text_with_core(
                        package_path / "README.md",
                        payload.readme_markdown,
                        invalidation_key=user_id,
                    )
                self._upsert_listing_entry_with_core(
                    adapter,
                    self._get_registry_root(user_id),
                    package_id,
                    listing,
                    invalidation_key=user_id,
                )
                return self._mutation_result_for_package(
                    user_id,
                    target_client,
                    package_id,
                    path=relative_manifest_path,
                )
            finally:
                self._invalidate_package_overview(user_id, target_client, package_id)

    def update_hooks(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        source_id: str | None,
        content: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            try:
                submitted = json.loads(content)
            except (TypeError, json.JSONDecodeError) as exc:
                raise MarketplaceValidationError(
                    [
                        {
                            "code": "marketplace.hooks.invalid_json",
                            "messageKey": "marketplace.hooks.diagnostics.source-document-invalid",
                            "sourceLocator": source_id or "hooks",
                        }
                    ]
                ) from exc
            if not isinstance(submitted, dict):
                raise MarketplaceValidationError(
                    [
                        {
                            "code": "marketplace.hooks.invalid_json",
                            "messageKey": "marketplace.hooks.diagnostics.source-document-invalid",
                            "sourceLocator": source_id or "hooks",
                        }
                    ]
                )

            owners, diagnostics = resolve_hook_sources(package_path, target_client)
            fatal_codes = {
                "source-reference-invalid",
                "source-missing",
                "source-not-allowed",
                "duplicate-resource-id",
            }
            fatal_diagnostics = [
                {
                    "code": item["code"],
                    "messageKey": f"marketplace.hooks.diagnostics.{item['code']}",
                    "sourceLocator": item["sourceLocator"],
                }
                for item in diagnostics
                if item["code"] in fatal_codes
            ]
            if fatal_diagnostics:
                raise MarketplaceValidationError(fatal_diagnostics)

            owner = (
                next(
                    (item for item in owners if hook_source_id(item) == source_id),
                    None,
                )
                if source_id
                else None
            )
            if source_id and owner is None:
                raise MarketplaceValidationError(
                    [
                        {
                            "code": "marketplace.hooks.source_not_found",
                            "messageKey": "marketplace.hooks.diagnostics.source-not-found",
                            "sourceLocator": source_id,
                        }
                    ]
                )

            if owner is not None:
                source_path = package_path / owner.file_path
                try:
                    _, current_document, _ = read_hook_source(package_path, owner)
                except (
                    OSError,
                    UnicodeError,
                    json.JSONDecodeError,
                    PackageSourceError,
                ) as exc:
                    code = (
                        exc.code
                        if isinstance(exc, PackageSourceError)
                        else "source-document-invalid"
                    )
                    raise MarketplaceValidationError(
                        [
                            {
                                "code": f"marketplace.hooks.{code}",
                                "messageKey": f"marketplace.hooks.diagnostics.{code}",
                                "sourceLocator": owner.file_path,
                            }
                        ]
                    ) from exc
                submitted_native = get_json_entry(submitted, owner.json_pointer)
                if not isinstance(submitted_native, dict):
                    raise MarketplaceValidationError(
                        [
                            {
                                "code": "marketplace.hooks.invalid_json",
                                "messageKey": "marketplace.hooks.diagnostics.source-document-invalid",
                                "sourceLocator": owner.file_path,
                            }
                        ]
                    )
                try:
                    validate_inline_hooks(
                        submitted_native,
                        source_locator=owner.file_path,
                    )
                except PackageSourceError as exc:
                    raise MarketplaceValidationError(
                        [
                            {
                                "code": f"marketplace.hooks.{exc.code}",
                                "messageKey": f"marketplace.hooks.diagnostics.{exc.code}",
                                "sourceLocator": exc.source_locator,
                            }
                        ]
                    ) from exc
                updated_document = patch_json_entry(
                    current_document,
                    owner.json_pointer,
                    submitted_native,
                )
                self._write_json_with_core(
                    source_path,
                    updated_document,
                    invalidation_key=user_id,
                )
                canonical_path = source_path
            else:
                manifest_path = self._get_adapter(target_client).manifest_path(
                    package_path
                )
                manifest = read_json_file(manifest_path)
                if "hooks" in manifest:
                    raise MarketplaceValidationError(
                        [
                            {
                                "code": "marketplace.hooks.source_not_found",
                                "messageKey": "marketplace.hooks.diagnostics.source-not-found",
                                "sourceLocator": "hooks",
                            }
                        ]
                    )
                try:
                    _, hooks = hook_map(submitted, source_locator="hooks")
                    validate_inline_hooks(hooks, source_locator="hooks")
                except PackageSourceError as exc:
                    raise MarketplaceValidationError(
                        [
                            {
                                "code": f"marketplace.hooks.{exc.code}",
                                "messageKey": f"marketplace.hooks.diagnostics.{exc.code}",
                                "sourceLocator": exc.source_locator,
                            }
                        ]
                    ) from exc
                target_path = package_path / "hooks" / "hooks.json"
                self._write_json_with_core(
                    target_path, submitted, invalidation_key=user_id
                )
                canonical_path = target_path
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=canonical_path.relative_to(package_path).as_posix(),
            )

    def write_skill_file(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
        content: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_skill_relative_path(path)
            self._write_text_with_core(
                package_path / relative_path, content, invalidation_key=user_id
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def upload_skill_streams(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        target_path: str,
        files: Sequence[tuple[str, BinaryIO, int]],
        default_strategy: str,
        resolutions: Sequence[FileConflictResolution],
    ) -> FileConflictBatchResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, _ = self._skill_file_engine_for_revision(
                user_id, target_client, package_id, revision
            )
            relative_target = self._validate_skill_relative_path(target_path)
            locator = FileLocator(domain="marketplace", resource_id="registry")
            try:
                upload_items = []
                for filename, stream, size in files:
                    stream.seek(0)
                    upload_items.append(
                        UploadStreamItem(
                            filename=filename,
                            stream=stream,
                            size=size,
                        )
                    )
                result = engine.upload_streams(
                    locator=locator,
                    target_path=relative_target,
                    files=upload_items,
                    default_strategy=default_strategy,
                    resolutions=self._core_conflict_resolutions(resolutions),
                )
            except FileCoreError as exc:
                self._raise_skill_archive_error(exc)
            return self._file_batch_response(result)

    def preflight_skill_file_conflicts(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        payload: FileConflictPreflightRequest,
    ) -> FileConflictPreflightResponse:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            if payload.operation == "paste":
                raise MarketplacePathError("marketplace.resource.invalid_operation")
            engine, package_path = self._skill_file_engine_for_revision(
                user_id, target_client, package_id, revision
            )
            relative_target = self._validate_skill_relative_path(payload.targetPath)
            locator = FileLocator(domain="marketplace", resource_id="registry")
            try:
                if payload.operation == "upload":
                    result = engine.preflight_upload_streams(
                        locator=locator,
                        target_path=relative_target,
                        files=[
                            UploadStreamItem(
                                filename=source.sourcePath,
                                stream=BytesIO(),
                                size=0,
                            )
                            for source in payload.sources or []
                        ],
                    )
                else:
                    if not payload.archivePath:
                        raise MarketplacePathError("marketplace.resource.invalid_path")
                    relative_archive = self._validate_skill_relative_path(
                        payload.archivePath
                    )
                    archive_file = package_path / relative_archive
                    if not archive_file.is_file():
                        raise FileNotFoundError("marketplace.resource.not_found")
                    result = engine.preflight_extract_archive(
                        ExtractArchiveRequest(
                            locator=locator,
                            target_path=relative_target,
                            archive_name=archive_file.name,
                            archive_bytes=archive_file.read_bytes(),
                        )
                    )
            except FileCoreError as exc:
                self._raise_skill_archive_error(exc)
            return self._file_preflight_response(result)

    def extract_skill_archive(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        archive_path: str,
        target_path: str,
        default_strategy: str,
        resolutions: Sequence[FileConflictResolution],
    ) -> FileConflictBatchResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, package_path = self._skill_file_engine_for_revision(
                user_id, target_client, package_id, revision
            )
            relative_archive = self._validate_skill_relative_path(archive_path)
            relative_target = self._validate_skill_relative_path(target_path)
            archive_file = package_path / relative_archive
            if not archive_file.is_file():
                raise FileNotFoundError("marketplace.resource.not_found")
            try:
                with archive_file.open("rb") as archive_stream:
                    result = engine.extract_archive_stream(
                        ExtractArchiveStreamRequest(
                            locator=FileLocator(
                                domain="marketplace",
                                resource_id="registry",
                            ),
                            target_path=relative_target,
                            archive_name=archive_file.name,
                            archive_stream=archive_stream,
                            archive_size=archive_file.stat().st_size,
                            default_strategy=default_strategy,
                            resolutions=self._core_conflict_resolutions(resolutions),
                        )
                    )
            except FileCoreError as exc:
                self._raise_skill_archive_error(exc)
            return self._file_batch_response(result)

    def _skill_file_engine_for_revision(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
    ):
        detail = self._get_package_detail_for_mutation(
            user_id, target_client, package_id
        )
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        package_path = self._resolve_package_path(user_id, target_client, package_id)
        return (
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ),
            package_path,
        )

    def create_skill_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
        entry_type: str,
        content: str = "",
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_skill_relative_path(path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).create_entry(
                CreateEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=relative_path,
                    entry_type=entry_type,
                    content=content,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def delete_skill_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_skill_relative_path(path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).delete_entry(
                DeleteEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=relative_path,
                    recursive=True,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def move_skill_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        previous_path: str,
        next_path: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            source_path = self._validate_skill_relative_path(previous_path)
            dest_path = self._validate_skill_relative_path(next_path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).move_entry(
                MoveEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    source_path=source_path,
                    dest_path=dest_path,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=dest_path,
            )

    def write_package_file(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
        content: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_package_file_relative_path(path)
            self._write_text_with_core(
                package_path / relative_path, content, invalidation_key=user_id
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def preflight_package_file_conflicts(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        payload: FileConflictPreflightRequest,
    ) -> FileConflictPreflightResponse:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, _ = self._package_file_engine(user_id, target_client, package_id)
            locator = FileLocator(domain="marketplace", resource_id="registry")
            sources = payload.sources or []
            if payload.operation == "upload":
                result = engine.preflight_upload_streams(
                    locator=locator,
                    target_path=payload.targetPath,
                    files=[
                        UploadStreamItem(
                            filename=source.sourcePath,
                            stream=BytesIO(),
                            size=0,
                        )
                        for source in sources
                    ],
                )
            elif payload.operation == "paste":
                result = engine.preflight_copy_entries(
                    CopyEntriesRequest(
                        locator=locator,
                        source_paths=[source.sourcePath for source in sources],
                        target_path=payload.targetPath,
                    )
                )
            else:
                if not payload.archivePath:
                    raise MarketplacePathError("marketplace.resource.invalid_path")
                archive_path = self._validate_package_file_relative_path(
                    payload.archivePath
                )
                _, package_path = self._package_file_engine(
                    user_id, target_client, package_id
                )
                archive_file = package_path / archive_path
                if not archive_file.is_file():
                    raise FileNotFoundError("marketplace.resource.not_found")
                result = engine.preflight_extract_archive(
                    ExtractArchiveRequest(
                        locator=locator,
                        target_path=payload.targetPath,
                        archive_name=archive_file.name,
                        archive_bytes=archive_file.read_bytes(),
                    )
                )
            return self._file_preflight_response(result)

    def upload_package_files(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        target_path: str,
        files: Sequence[tuple[str, BinaryIO, int]],
        default_strategy: str,
        resolutions: Sequence[FileConflictResolution],
    ) -> FileConflictBatchResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, _ = self._package_file_engine(user_id, target_client, package_id)
            relative_target = self._validate_package_file_relative_path(target_path)
            result = engine.upload_streams(
                locator=FileLocator(domain="marketplace", resource_id="registry"),
                target_path=relative_target,
                files=[
                    UploadStreamItem(filename=name, stream=stream, size=size)
                    for name, stream, size in files
                ],
                default_strategy=default_strategy,
                resolutions=self._core_conflict_resolutions(resolutions),
            )
            return self._file_batch_response(result)

    def paste_package_files(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        payload: FileConflictExecutionRequest,
    ) -> FileConflictBatchResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, _ = self._package_file_engine(user_id, target_client, package_id)
            result = engine.copy_entries(
                CopyEntriesRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    source_paths=[source.sourcePath for source in payload.sources],
                    target_path=payload.targetPath,
                    default_strategy=payload.defaultStrategy,
                    resolutions=self._core_conflict_resolutions(payload.resolutions),
                )
            )
            return self._file_batch_response(result)

    def extract_package_archive(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        payload: FileExtractExecutionRequest,
    ) -> FileConflictBatchResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            engine, package_path = self._package_file_engine(
                user_id, target_client, package_id
            )
            archive_path = self._validate_package_file_relative_path(
                payload.archivePath
            )
            archive_file = package_path / archive_path
            if not archive_file.is_file():
                raise FileNotFoundError("marketplace.resource.not_found")
            with archive_file.open("rb") as archive_stream:
                extracted = engine.extract_archive_stream(
                    ExtractArchiveStreamRequest(
                        locator=FileLocator(
                            domain="marketplace", resource_id="registry"
                        ),
                        target_path=payload.targetPath,
                        archive_name=archive_file.name,
                        archive_stream=archive_stream,
                        archive_size=archive_file.stat().st_size,
                        default_strategy=payload.defaultStrategy,
                        resolutions=self._core_conflict_resolutions(
                            payload.resolutions
                        ),
                    )
                )
            return self._file_batch_response(extracted)

    def create_package_file_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
        entry_type: str,
        content: str = "",
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_package_file_relative_path(path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).create_entry(
                CreateEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=relative_path,
                    entry_type=entry_type,
                    content=content,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def delete_package_file_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        path: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            relative_path = self._validate_package_file_relative_path(path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).delete_entry(
                DeleteEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    path=relative_path,
                    recursive=True,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=relative_path,
            )

    def move_package_file_entry(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        revision: str,
        previous_path: str,
        next_path: str,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            source_path = self._validate_package_file_relative_path(previous_path)
            dest_path = self._validate_package_file_relative_path(next_path)
            self._file_engine_for_root(
                root=package_path,
                registry_root=self._get_registry_root(user_id),
                invalidation_key=user_id,
            ).move_entry(
                MoveEntryRequest(
                    locator=FileLocator(domain="marketplace", resource_id="registry"),
                    source_path=source_path,
                    dest_path=dest_path,
                )
            )
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=dest_path,
            )

    def save_mcp_server(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        name: str,
        request: MarketplaceMcpServerMutationRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            owner = resolve_mcp_owner(
                package_path,
                target_client,
                name,
                owner_file_path=request.owner_file_path,
            )
            if owner is None:
                raise MarketplaceConflictError("marketplace.resource.entry_conflict")
            owner_path = package_path / owner.file_path
            data = read_json_file(owner_path)
            current = get_json_entry(data, owner.json_pointer)
            if current is None:
                raise FileNotFoundError("marketplace.resource.not_found")
            pointer = owner.json_pointer
            if pointer is None:
                raise MarketplacePathError("marketplace.resource.invalid_json_root")
            patched = patch_json_entry(data, pointer, request.server)
            self._write_json_with_core(owner_path, patched, invalidation_key=user_id)
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=owner.file_path,
                owner_file_path=owner.file_path,
                base_entry_fingerprint=canonical_entry_fingerprint(request.server),
            )

    def delete_mcp_server(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_id: str,
        name: str,
        request: MarketplaceMcpServerDeleteRequest,
    ) -> MarketplacePackageMutationResult:
        lock_key = self._marketplace_package_lock_key(
            user_id, target_client, package_id
        )
        with _resource_write_locks.lock(lock_key):
            detail = self._get_package_detail_for_mutation(
                user_id, target_client, package_id
            )
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            package_path = self._resolve_package_path(
                user_id, target_client, package_id
            )
            owner = resolve_mcp_owner(
                package_path,
                target_client,
                name,
                owner_file_path=request.owner_file_path,
            )
            if owner is None:
                raise MarketplaceConflictError("marketplace.resource.entry_conflict")
            owner_path = package_path / owner.file_path
            data = read_json_file(owner_path)
            pointer = owner.json_pointer
            if pointer is None:
                raise MarketplacePathError("marketplace.resource.invalid_json_root")
            current = get_json_entry(data, pointer)
            if current is None:
                raise FileNotFoundError("marketplace.resource.not_found")
            try:
                patched = remove_json_entry(data, pointer)
            except ValueError as exc:
                raise MarketplacePathError(str(exc)) from exc
            self._write_json_with_core(owner_path, patched, invalidation_key=user_id)
            return self._mutation_result_for_package(
                user_id,
                target_client,
                package_id,
                path=owner.file_path,
                owner_file_path=owner.file_path,
                base_entry_fingerprint=None,
            )
