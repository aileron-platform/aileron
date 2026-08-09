"""Marketplace imports workflow module."""

from __future__ import annotations

import shutil
from typing import Any
from uuid import uuid4

from aileron_file_core import ExtractArchiveRequest, FileCoreError, FileLocator
from aileron_git_core import OperationKind

from app.modules.marketplace.models import (
    MarketplaceImportCandidate,
    MarketplaceImportFailedCandidate,
    MarketplaceImportRequest,
    MarketplaceImportResult,
    MarketplaceImportSource,
    MarketplaceImportUploadResult,
    MarketplacePackageSummary,
    MarketplaceProvider,
)
from app.modules.version_control.remote import require_user_ssh_private_key

from .kernel import _MarketplaceRegistrySupport
from .package_reads import MarketplacePackageReadModel
from .registry_operations import (
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplacePathError,
    MarketplaceValidationError,
    _MarketplaceRegistryContext,
    _registry_git_operation,
)
from .settings_activity import MarketplaceSettingsActivityWorkflow


class MarketplaceImportWorkflow(_MarketplaceRegistrySupport):
    """Validate, stage, merge, and roll back Marketplace imports."""

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

    def scan_import_source(
        self,
        user_id: str,
        source: MarketplaceImportSource,
    ) -> list[MarketplaceImportCandidate]:
        """Validate an external import source before provider-native scanning."""
        metadata = self.validate_import_source(user_id, source)
        with self._prepared_import_source_root(source, metadata) as source_root:
            candidates = self._scan_import_candidates(source, source_root)
        enriched = [
            self._with_duplicate_import_state(
                user_id,
                MarketplaceImportCandidate.model_validate(candidate),
                source,
                metadata,
            )
            for candidate in candidates
        ]
        return self._with_batch_variant_metadata(source, metadata, enriched)

    @_registry_git_operation(OperationKind.WRITE, "import_candidates")
    def import_candidates(
        self,
        user_id: str,
        request: MarketplaceImportRequest,
    ) -> MarketplaceImportResult:
        """Copy selected import candidates into the local Marketplace registry."""
        self._settings_activity.initialize_registry(user_id)
        imported: list[MarketplacePackageSummary] = []
        skipped: list[MarketplaceImportCandidate] = []
        failed: list[MarketplaceImportFailedCandidate] = []
        warnings: list[dict[str, Any]] = []
        metadata = self.validate_import_source(user_id, request.source)
        with self._prepared_import_source_root(request.source, metadata) as source_root:
            with self._registry_lock:
                scanned = [
                    self._with_duplicate_import_state(
                        user_id,
                        MarketplaceImportCandidate.model_validate(candidate),
                        request.source,
                        metadata,
                    )
                    for candidate in self._scan_import_candidates(
                        request.source, source_root
                    )
                ]
                scanned = self._with_batch_variant_metadata(
                    request.source, metadata, scanned
                )
                scanned_by_key = {
                    self._import_candidate_key(candidate): candidate
                    for candidate in scanned
                }
            for requested in request.candidates:
                server_candidate = scanned_by_key.get(
                    self._import_candidate_key(requested)
                )
                candidate = self._merge_import_candidate_action(
                    server_candidate, requested
                )
                try:
                    if server_candidate is None:
                        raise MarketplaceImportSourceError(
                            "marketplace.import.validation.candidate_not_found"
                        )
                    if candidate.duplicate and candidate.duplicate_action == "skip":
                        skipped.append(candidate)
                        continue
                    blocking = [
                        result
                        for result in candidate.validation_results
                        if result.severity == "error"
                    ]
                    if blocking:
                        raise MarketplaceImportSourceError(blocking[0].code)
                    warnings.extend(
                        [
                            result.model_dump(by_alias=True)
                            for result in candidate.validation_results
                            if result.severity in {"warning", "info"}
                        ]
                    )
                    imported.append(
                        self._import_one_candidate(
                            user_id,
                            source_root,
                            request.source,
                            candidate,
                            metadata,
                        )
                    )
                except (
                    MarketplaceImportSourceError,
                    MarketplacePathError,
                    MarketplaceConflictError,
                    MarketplaceValidationError,
                ) as exc:
                    failed.append(self._failed_import_candidate(candidate, str(exc)))
                except Exception:
                    failed.append(
                        self._failed_import_candidate(
                            candidate,
                            "marketplace.import.validation.copy_failed",
                        )
                    )
        if imported:
            self._invalidate_package_index(user_id)
            imported = self._with_family_metadata(
                self._get_registry_root(user_id), imported
            )
        if imported and not failed:
            self._settings_activity.record_activity(
                user_id, action="import", status="succeeded"
            )
        elif failed:
            self._settings_activity.record_activity(
                user_id,
                action="import",
                status="failed",
                error_code=failed[0].error_code,
            )
        return MarketplaceImportResult(
            imported=imported,
            skipped=skipped,
            failed=failed,
            warnings=warnings,
        )

    def validate_import_source(
        self, user_id: str, source: MarketplaceImportSource
    ) -> dict[str, Any]:
        """Validate import source safety boundaries and return resolved source metadata."""
        self._reject_raw_secret_material(source)
        if source.source_kind == "local":
            return {
                "sourceKind": "local",
                "sourceRoot": self._resolve_allowed_import_local_path(
                    user_id, source.source
                ),
            }
        if source.source_kind == "git":
            parsed = self._parse_git_import_source(source.source)
            if parsed["scheme"] == "https":
                self._reject_https_token_source(source.source)
            if parsed["scheme"] == "ssh":
                require_user_ssh_private_key(self.db, user_id=user_id)
            return {
                "sourceKind": "git",
                "host": parsed["host"],
                "scheme": parsed["scheme"],
                "cloneUrl": parsed.get("cloneUrl", source.source.strip()),
                "ref": parsed.get("ref"),
                "sourceSubpath": parsed.get("sourceSubpath"),
                "workRoot": self._import_work_root(user_id),
                "userId": user_id,
            }
        raise MarketplaceImportSourceError(
            "marketplace.import.validation.invalid_source_kind"
        )

    def save_uploaded_import_source(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        file_name: str,
        content: bytes,
    ) -> MarketplaceImportUploadResult:
        """Persist and extract an uploaded local import archive."""
        if not file_name or not file_name.lower().endswith(".zip"):
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_upload_archive"
            )
        if not content:
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_upload_archive"
            )
        upload_root = (
            self._allowed_import_local_roots(user_id)[0] / f"upload-{uuid4().hex}"
        )
        upload_root.mkdir(parents=True, exist_ok=False)
        try:
            self._file_engine_for_root(
                root=upload_root,
                registry_root=self._get_registry_root(user_id),
            ).extract_archive(
                ExtractArchiveRequest(
                    locator=FileLocator(domain="marketplace", resource_id="import"),
                    target_path="/",
                    archive_name=file_name,
                    archive_bytes=content,
                    default_strategy="replace",
                    resolutions=(),
                )
            )
        except MarketplaceImportSourceError:
            shutil.rmtree(upload_root, ignore_errors=True)
            raise
        except FileCoreError as exc:
            shutil.rmtree(upload_root, ignore_errors=True)
            if exc.code == "INVALID_ARCHIVE_ENTRY":
                raise MarketplaceImportSourceError(
                    "marketplace.validation.path_escape"
                ) from exc
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_upload_archive"
            ) from exc
        except OSError as exc:
            shutil.rmtree(upload_root, ignore_errors=True)
            raise MarketplaceImportSourceError(
                "marketplace.import.validation.invalid_upload_archive"
            ) from exc
        return MarketplaceImportUploadResult(
            source=MarketplaceImportSource(
                provider=provider,
                source_kind="local",
                source=str(upload_root),
            ),
            file_name=file_name,
        )
