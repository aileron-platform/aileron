"""Marketplace registry service."""

from __future__ import annotations

import json
import difflib
import mimetypes
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterator, Literal
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.models.marketplace import (
    MarketplaceActivityAction,
    MarketplaceActivityListResult,
    MarketplaceActivityRecord,
    MarketplaceActivityStatus,
    MarketplaceCliCapabilities,
    MarketplaceCliPreflightResult,
    MarketplaceFeatureContent,
    MarketplaceFeatureContentItem,
    MarketplaceImportBranchesResult,
    MarketplaceImportCandidate,
    MarketplaceImportFailedCandidate,
    MarketplaceImportRequest,
    MarketplaceImportResult,
    MarketplaceImportSource,
    MarketplaceImportUploadResult,
    MarketplaceInstallCommandPlan,
    MarketplaceInstallRequest,
    MarketplaceInstallResult,
    MarketplaceGitCommitListResult,
    MarketplaceGitCommitFilesResult,
    MarketplaceGitCommitRequest,
    MarketplaceGitCommitResult,
    MarketplaceGitCommitSummary,
    MarketplaceGitDiffResponse,
    MarketplaceGitFileChange,
    MarketplaceGitPathRequest,
    MarketplaceGitStatus,
    MarketplaceProvider,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageDeleteResult,
    MarketplacePackageDetail,
    MarketplacePackageFile,
    MarketplacePackageListResult,
    MarketplacePackageSaveRequest,
    MarketplacePackageSaveResult,
    MarketplacePackageSummary,
    MarketplaceRegistryInitResult,
    MarketplaceRegistryCloneRequest,
    MarketplaceRegistryGitOperationResult,
    MarketplaceRegistryRemoteRequest,
    MarketplaceRegistryRepositoryStatus,
    MarketplaceRegistryRootMetadataSavePayload,
    MarketplaceRegistrySshKeyResponse,
    MarketplaceRegistrySettings,
    MarketplaceSettingsSaveResult,
)
from app.services.marketplace_adapters import (
    MarketplaceProviderAdapter,
    create_marketplace_adapters,
)


class MarketplacePathError(ValueError):
    """Raised when a Marketplace path would leave its provider root."""


class MarketplaceConflictError(ValueError):
    """Raised when a package revision does not match current registry content."""


class MarketplaceValidationError(ValueError):
    """Raised when provider-native package validation blocks a mutation."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        first_code = results[0]["code"] if results else "marketplace.validation.invalid_manifest_shape"
        super().__init__(first_code)


class MarketplaceImportSourceError(ValueError):
    """Raised when an import source fails safety validation."""

    def __init__(self, code: str, params: dict[str, Any] | None = None) -> None:
        self.code = code
        self.params = params or {}
        super().__init__(code)


MarketplaceValidationAction = Literal["save", "export", "install", "importCopy"]


class MarketplaceService:
    """Manage provider-native Marketplace registry files."""

    _registry_lock = threading.RLock()
    _index_lock = threading.RLock()
    _package_index: dict[str, tuple[str, list[MarketplacePackageSummary]]] = {}
    _package_id_pattern = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
    _git_scp_like_pattern = re.compile(r"^(?P<user>[A-Za-z0-9_.-]+)@(?P<host>[A-Za-z0-9_.-]+):(?P<path>.+)$")
    _git_ref_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/@+-]*$")
    _version_pattern = re.compile(r"(?P<version>\d+(?:\.\d+){0,3})")
    _raw_private_key_pattern = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
    _unsafe_readme_block_pattern = re.compile(
        r"<\s*(script|style|iframe|object|embed|form)\b[^>]*>.*?<\s*/\s*\1\s*>",
        re.IGNORECASE | re.DOTALL,
    )
    _unsafe_readme_single_tag_pattern = re.compile(
        r"<\s*/?\s*(script|style|iframe|object|embed|form)\b[^>]*>",
        re.IGNORECASE,
    )
    _readme_event_attr_pattern = re.compile(
        r"\s+on[a-zA-Z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
        re.IGNORECASE,
    )
    _readme_javascript_link_pattern = re.compile(
        r"(\[[^\]]+\]\()\s*javascript:[^)]+(\))",
        re.IGNORECASE,
    )

    def __init__(self, db: Session | None = None) -> None:
        settings = get_settings()
        self.db = db
        self.storage_root = Path(settings.MARKETPLACE_STORAGE_PATH)
        self.adapters = create_marketplace_adapters()

    def get_registry_root(self, user_id: str) -> Path:
        """Return the system-managed shared registry root."""
        return self.storage_root / "registry"

    def initialize_registry(
        self,
        user_id: str,
        metadata: MarketplaceRegistryRootMetadataSavePayload | None = None,
    ) -> MarketplaceRegistryInitResult:
        """Bootstrap provider roots and required provider marketplace manifests."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            created = not root.exists()
            self._ensure_provider_roots(root)
            metadata = metadata or self._default_metadata()
            self._write_manifest_if_missing(
                self._claude_manifest_path(root),
                self._build_claude_manifest(metadata),
            )
            self._write_manifest_if_missing(
                self._codex_manifest_path(root),
                self._build_codex_manifest(metadata),
            )
            self.invalidate_package_index(user_id)
            return MarketplaceRegistryInitResult(
                root_path=str(root),
                created=created,
                claude_manifest_path=str(self._claude_manifest_path(root).relative_to(root)),
                codex_manifest_path=str(self._codex_manifest_path(root).relative_to(root)),
                gemini_root_path=str((root / "gemini").relative_to(root)),
            )

    def get_settings(self, user_id: str) -> MarketplaceRegistrySettings:
        """Read Marketplace registry settings from provider manifests."""
        root = self.get_registry_root(user_id)
        if not self._claude_manifest_path(root).exists() or not self._codex_manifest_path(root).exists():
            return MarketplaceRegistrySettings(
                display_name="",
                root_path=str(root),
                status="uninitialized",
                description="",
                maintainer_name="",
                maintainer_email="",
            )

        metadata = self._read_metadata(root)
        return MarketplaceRegistrySettings(
            display_name=metadata.name,
            root_path=str(root),
            status="ready",
            description=metadata.description,
            maintainer_name=metadata.owner.name,
            maintainer_email=metadata.owner.email,
        )

    def list_packages(
        self,
        user_id: str,
        *,
        provider: MarketplaceProvider | None = None,
        q: str | None = None,
        category: str | None = None,
        features: list[str] | None = None,
        page: int = 1,
        page_size: int = 12,
    ) -> MarketplacePackageListResult:
        """Scan provider registry files and return package summaries."""
        root = self.get_registry_root(user_id)
        items, fingerprint = self._get_package_index(root)
        filtered = self._filter_packages(
            items,
            provider=provider,
            q=q,
            category=category,
            features=features or [],
        )
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        start = (page - 1) * page_size
        paged = filtered[start:start + page_size]
        total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
        return MarketplacePackageListResult(
            items=paged,
            total=len(filtered),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            categories=sorted({item.category for item in items if item.category}),
            source_types=sorted({item.source_type for item in items}),
            validation_severities=sorted({item.validation_severity for item in items}),
            registry_fingerprint=fingerprint,
        )

    def refresh_package_index(self, user_id: str) -> MarketplacePackageListResult:
        """Force a package index rescan and return the refreshed list."""
        self.invalidate_package_index(user_id)
        return self.list_packages(user_id)

    def invalidate_package_index(self, user_id: str) -> None:
        """Invalidate the current user's package index."""
        root_key = str(self.get_registry_root(user_id))
        with self._index_lock:
            self._package_index.pop(root_key, None)

    def get_package_detail(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> MarketplacePackageDetail | None:
        """Return provider-native package detail."""
        for item in self._get_package_index(self.get_registry_root(user_id))[0]:
            if item.provider == provider and item.package_id == package_id:
                package_path = self.resolve_package_path(user_id, provider, package_id)
                adapter = self._get_adapter(provider)
                manifest = adapter.read_manifest(package_path)  # type: ignore[attr-defined]
                catalog_entry = adapter.read_listing_entry(self.get_registry_root(user_id), package_id)
                catalog = {
                    "name": item.display_name,
                    "description": item.description,
                    "version": item.version,
                    "category": item.category,
                    "tags": item.tags,
                }
                validation_results = [
                    *adapter.validate_package(package_path),
                    *adapter.validate_catalog_metadata(catalog_entry, manifest),  # type: ignore[attr-defined]
                ]
                return MarketplacePackageDetail(
                    **item.model_dump(by_alias=True),
                    catalog_metadata=catalog,
                    manifest_metadata=manifest,
                    metadata_conflict=any(
                        result.get("code") == "marketplace.validation.metadata_conflict"
                        for result in validation_results
                    ),
                    readme_markdown=self._read_sanitized_readme_markdown(package_path),
                    feature_content=self._build_feature_content(provider, package_path),
                    package_files=self._build_package_files(package_path),
                    validation_results=validation_results,
                    activity=[],
                )
        return None

    def _build_feature_content(
        self,
        provider: MarketplaceProvider,
        package_path: Path,
    ) -> MarketplaceFeatureContent:
        agents_md = self._read_first_existing_text(package_path, self._agents_md_candidates(provider))
        return MarketplaceFeatureContent(
            agents_md=agents_md,
            hooks=self._feature_items_from_directory(package_path, self._provider_directory(provider, "hooks")),
            mcp_servers=self._mcp_feature_items(package_path),
            agents=self._feature_items_from_directory(package_path, self._provider_directory(provider, "agents")),
            commands=self._feature_items_from_directory(package_path, self._provider_directory(provider, "commands")),
            output_styles=self._feature_items_from_directory(package_path, "output-styles"),
            skills=self._feature_items_from_directory(package_path, self._provider_directory(provider, "skills")),
        )

    def _agents_md_candidates(self, provider: MarketplaceProvider) -> tuple[str, ...]:
        if provider == "claude-code":
            return ("AGENTS.md", "CLAUDE.md")
        if provider == "gemini":
            return ("GEMINI.md", "AGENTS.md")
        return ("AGENTS.md",)

    def _provider_directory(self, provider: MarketplaceProvider, feature: str) -> str:
        return feature

    def _read_first_existing_text(self, package_path: Path, relative_paths: tuple[str, ...]) -> str | None:
        for relative_path in relative_paths:
            path = package_path / relative_path
            if path.is_file():
                return self._read_text_file(path)
        return None

    def _feature_items_from_directory(self, package_path: Path, relative_directory: str) -> list[MarketplaceFeatureContentItem]:
        directory = package_path / relative_directory
        if not directory.is_dir():
            return []
        items: list[MarketplaceFeatureContentItem] = []
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            relative_path = path.relative_to(package_path).as_posix()
            content = self._read_text_file(path)
            items.append(MarketplaceFeatureContentItem(
                id=relative_path,
                name=path.stem,
                path=relative_path,
                content=content,
                description=self._feature_description_from_content(content),
                data=self._feature_data_from_file(path),
            ))
        return items

    def _mcp_feature_items(self, package_path: Path) -> list[MarketplaceFeatureContentItem]:
        items: list[MarketplaceFeatureContentItem] = []
        for relative_path in (".mcp.json", "mcp.json"):
            path = package_path / relative_path
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            servers = data.get("mcpServers") if isinstance(data, dict) else None
            if not isinstance(servers, dict):
                continue
            for server_id, config in sorted(servers.items()):
                if not isinstance(config, dict):
                    continue
                items.append(MarketplaceFeatureContentItem(
                    id=f"{relative_path}:{server_id}",
                    name=str(server_id),
                    path=relative_path,
                    description=self._string_or_none(config.get("description")),
                    data=config,
                ))
        items.extend(self._feature_items_from_directory(package_path, "mcp"))
        return items

    def _feature_description_from_content(self, content: str | None) -> str | None:
        if not content:
            return None
        for line in content.splitlines()[:20]:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                if key.strip().lower() == "description":
                    return value.strip().strip("\"'")
        return None

    def _feature_data_from_file(self, path: Path) -> dict[str, Any] | None:
        suffix = path.suffix.lower()
        if suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            return data if isinstance(data, dict) else None
        return None

    def _read_text_file(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _string_or_none(self, value: Any) -> str | None:
        return value if isinstance(value, str) and value.strip() else None

    def _build_package_files(self, package_path: Path) -> list[MarketplacePackageFile]:
        files: list[MarketplacePackageFile] = []
        if not package_path.is_dir():
            return files

        for path in sorted(item for item in package_path.rglob("*") if item.is_file()):
            try:
                self._assert_relative_to(path, package_path)
            except MarketplacePathError:
                continue
            relative_path = path.relative_to(package_path).as_posix()
            if any(part == ".git" for part in path.relative_to(package_path).parts):
                continue

            try:
                raw = path.read_bytes()
            except OSError:
                continue

            try:
                content = raw.decode("utf-8")
                binary = False
            except UnicodeDecodeError:
                content = ""
                binary = True

            files.append(MarketplacePackageFile(
                path=relative_path,
                content=content,
                binary=binary,
                mime_type=mimetypes.guess_type(path.name)[0],
                size=len(raw),
            ))
        return files

    def _sync_package_files(self, package_path: Path, package_files: list[MarketplacePackageFile]) -> None:
        package_path.mkdir(parents=True, exist_ok=True)
        requested_paths: set[Path] = set()

        for package_file in package_files:
            relative_path = self._normalize_package_file_path(package_file.path)
            target_path = package_path / relative_path
            self._assert_relative_to(target_path, package_path)
            requested_paths.add(target_path.resolve())

            if package_file.binary:
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(package_file.content, encoding="utf-8")

        for path in sorted((item for item in package_path.rglob("*") if item.is_file()), reverse=True):
            relative_parts = path.relative_to(package_path).parts
            if any(part == ".git" for part in relative_parts):
                continue
            if path.resolve() not in requested_paths:
                path.unlink()

        for path in sorted((item for item in package_path.rglob("*") if item.is_dir()), reverse=True):
            relative_parts = path.relative_to(package_path).parts
            if any(part == ".git" for part in relative_parts):
                continue
            try:
                path.rmdir()
            except OSError:
                continue

    def _normalize_package_file_path(self, path: str) -> str:
        cleaned = path.strip().replace("\\", "/")
        parts = Path(cleaned).parts
        if (
            not cleaned
            or cleaned.startswith("/")
            or "\x00" in cleaned
            or any(part in {"", ".", ".."} for part in parts)
            or any(part == ".git" for part in parts)
        ):
            raise MarketplacePathError("marketplace.package.path_escape")
        return Path(cleaned).as_posix()

    def list_activity(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 50,
    ) -> MarketplaceActivityListResult:
        """Return current user's registry-scoped Marketplace activity records."""
        records = self._read_activity_records(user_id)
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        start = (page - 1) * page_size
        total_pages = max(1, (len(records) + page_size - 1) // page_size)
        return MarketplaceActivityListResult(
            items=records[start:start + page_size],
            total=len(records),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def record_activity(
        self,
        user_id: str,
        *,
        action: MarketplaceActivityAction,
        status: MarketplaceActivityStatus,
        provider: MarketplaceProvider | None = None,
        package_id: str | None = None,
        error_code: str | None = None,
    ) -> MarketplaceActivityRecord:
        """Append a current-user Marketplace activity record."""
        record = MarketplaceActivityRecord(
            id=str(uuid4()),
            action=action,
            provider=provider,
            package_id=package_id,
            status=status,
            error_code=error_code,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        path = self._activity_log_path(self.get_registry_root(user_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(by_alias=True), separators=(",", ":")) + "\n")
        return record

    def scan_import_source(
        self,
        user_id: str,
        source: MarketplaceImportSource,
    ) -> list[MarketplaceImportCandidate]:
        """Validate an external import source before provider-native scanning."""
        metadata = self.validate_import_source(user_id, source)
        adapter = self._get_adapter(source.provider)
        with self._prepared_import_source_root(source, metadata) as source_root:
            try:
                candidates = adapter.scan_external_source(source_root)
            except NotImplementedError:
                return []
        return [
            self._with_duplicate_import_state(user_id, MarketplaceImportCandidate.model_validate(candidate))
            for candidate in candidates
        ]

    def list_import_branches(
        self,
        user_id: str,
        source: MarketplaceImportSource,
    ) -> MarketplaceImportBranchesResult:
        """Return remote branches for a Git import source."""
        if source.source_kind != "git":
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_source_kind")
        metadata = self.validate_import_source(user_id, source)
        command = ["git", "ls-remote", "--heads", source.source]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=self._git_ssh_env(metadata.get("sshKeyPath")),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError("marketplace.import.validation.branch_list_failed") from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.import.validation.branch_list_failed")
        branches = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) != 2 or not parts[1].startswith("refs/heads/"):
                continue
            branch = parts[1].removeprefix("refs/heads/")
            if branch:
                branches.append(branch)
        return MarketplaceImportBranchesResult(branches=sorted(set(branches)))

    def _with_duplicate_import_state(
        self,
        user_id: str,
        candidate: MarketplaceImportCandidate,
    ) -> MarketplaceImportCandidate:
        try:
            package_path = self.resolve_package_path(user_id, candidate.provider, candidate.package_id)
        except MarketplacePathError:
            return candidate
        if not package_path.exists():
            return candidate
        detail = self.get_package_detail(user_id, candidate.provider, candidate.package_id)
        return candidate.model_copy(update={
            "duplicate": True,
            "duplicate_action": "skip",
            "local_revision": detail.revision if detail else None,
        })

    def import_candidates(
        self,
        user_id: str,
        request: MarketplaceImportRequest,
    ) -> MarketplaceImportResult:
        """Copy selected import candidates into the local Marketplace registry."""
        self.initialize_registry(user_id)
        imported: list[MarketplacePackageSummary] = []
        skipped: list[MarketplaceImportCandidate] = []
        failed: list[MarketplaceImportFailedCandidate] = []
        warnings: list[dict[str, Any]] = []
        metadata = self.validate_import_source(user_id, request.source)
        with self._registry_lock:
            with self._prepared_import_source_root(request.source, metadata) as source_root:
                adapter = self._get_adapter(request.source.provider)
                scanned = [
                    self._with_duplicate_import_state(
                        user_id,
                        MarketplaceImportCandidate.model_validate(candidate),
                    )
                    for candidate in adapter.scan_external_source(source_root)
                ]
                scanned_by_key = {
                    self._import_candidate_key(candidate): candidate
                    for candidate in scanned
                }
                for requested in request.candidates:
                    server_candidate = scanned_by_key.get(self._import_candidate_key(requested))
                    candidate = self._merge_import_candidate_action(server_candidate, requested)
                    try:
                        if server_candidate is None:
                            raise MarketplaceImportSourceError("marketplace.import.validation.candidate_not_found")
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
                        warnings.extend([
                            result.model_dump(by_alias=True)
                            for result in candidate.validation_results
                            if result.severity in {"warning", "info"}
                        ])
                        imported.append(self._import_one_candidate(user_id, source_root, request.source, candidate))
                    except (
                        MarketplaceImportSourceError,
                        MarketplacePathError,
                        MarketplaceConflictError,
                        MarketplaceValidationError,
                    ) as exc:
                        failed.append(self._failed_import_candidate(candidate, str(exc)))
                    except Exception as exc:
                        failed.append(self._failed_import_candidate(
                            candidate,
                            "marketplace.import.validation.copy_failed",
                        ))
        if imported:
            self.invalidate_package_index(user_id)
        if imported and not failed:
            self.record_activity(user_id, action="import", status="success")
        elif failed:
            self.record_activity(
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

    def _import_candidate_key(self, candidate: MarketplaceImportCandidate) -> tuple[str, str, str]:
        return (candidate.provider, candidate.package_id, candidate.source_path)

    def _merge_import_candidate_action(
        self,
        scanned: MarketplaceImportCandidate | None,
        requested: MarketplaceImportCandidate,
    ) -> MarketplaceImportCandidate:
        if scanned is None:
            return requested
        return scanned.model_copy(update={
            "duplicate_action": requested.duplicate_action,
            "new_package_id": requested.new_package_id,
            "local_revision": requested.local_revision or scanned.local_revision,
        })

    def _failed_import_candidate(
        self,
        candidate: MarketplaceImportCandidate,
        error_code: str,
    ) -> MarketplaceImportFailedCandidate:
        return MarketplaceImportFailedCandidate.model_validate({
            **candidate.model_dump(by_alias=True),
            "errorCode": error_code,
        })

    def _import_one_candidate(
        self,
        user_id: str,
        source_root: Path,
        source: MarketplaceImportSource,
        candidate: MarketplaceImportCandidate,
    ) -> MarketplacePackageSummary:
        target_package_id = self._target_import_package_id(candidate)
        adapter = self._get_adapter(candidate.provider)
        registry_root = self.get_registry_root(user_id)
        source_package_path = self._resolve_import_candidate_source(source_root, candidate)
        target_package_path = self.resolve_package_path(user_id, candidate.provider, target_package_id)
        target_parent = target_package_path.parent
        target_parent.mkdir(parents=True, exist_ok=True)
        target_exists = target_package_path.exists()
        if candidate.duplicate_action == "overwrite":
            self._validate_import_overwrite_revision(user_id, candidate)
        elif target_exists:
            raise MarketplaceImportSourceError("marketplace.package.already_exists")
        self._reject_import_symlinks(source_package_path)

        staging_root = target_parent / f".import-{uuid4().hex}"
        staging_path = staging_root / target_package_id
        backup_path = target_parent / f".backup-{uuid4().hex}"
        manifest_backup = self._provider_manifest_backup(registry_root, adapter)
        promoted = False
        backup_created = False
        try:
            staging_root.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_package_path, staging_path, symlinks=False)
            self._rewrite_imported_manifest_name(adapter, staging_path, target_package_id)
            self._write_import_source_metadata(adapter, staging_path, source, candidate, target_package_id)
            self._raise_if_validation_blocks(adapter.validate_package(staging_path), "importCopy")
            if target_exists:
                target_package_path.rename(backup_path)
                backup_created = True
            staging_path.rename(target_package_path)
            promoted = True
            listing = adapter.import_listing_entry(
                source_root,
                candidate.package_id,
                target_package_id,
            )
            if listing is not None:
                adapter.upsert_listing_entry(registry_root, target_package_id, listing)
            if backup_created:
                shutil.rmtree(backup_path)
            if staging_root.exists():
                shutil.rmtree(staging_root)
        except MarketplaceValidationError:
            self._rollback_import_candidate(
                target_package_path,
                staging_path,
                backup_path,
                manifest_backup,
                promoted,
                backup_created,
            )
            raise
        except Exception as exc:
            self._rollback_import_candidate(
                target_package_path,
                staging_path,
                backup_path,
                manifest_backup,
                promoted,
                backup_created,
            )
            raise MarketplaceImportSourceError("marketplace.import.validation.copy_failed") from exc

        detail = self.get_package_detail(user_id, candidate.provider, target_package_id)
        if detail is None:
            raise MarketplaceImportSourceError("marketplace.package.not_found")
        return MarketplacePackageSummary.model_validate(detail.model_dump(by_alias=True))

    def _target_import_package_id(self, candidate: MarketplaceImportCandidate) -> str:
        if candidate.duplicate_action != "import-as-new":
            return candidate.package_id
        target_package_id = (candidate.new_package_id or "").strip()
        if not self._package_id_pattern.match(target_package_id):
            raise MarketplaceImportSourceError("marketplace.package.invalid_id")
        return target_package_id

    def _validate_import_overwrite_revision(
        self,
        user_id: str,
        candidate: MarketplaceImportCandidate,
    ) -> None:
        detail = self.get_package_detail(user_id, candidate.provider, candidate.package_id)
        if detail is None:
            raise MarketplaceImportSourceError("marketplace.package.not_found")
        if candidate.local_revision != detail.revision:
            raise MarketplaceConflictError("marketplace.package.revision_conflict")

    def _resolve_import_candidate_source(
        self,
        source_root: Path,
        candidate: MarketplaceImportCandidate,
    ) -> Path:
        if self._get_adapter(candidate.provider).is_remote_source_value(candidate.source_path):
            raise MarketplaceImportSourceError("marketplace.import.validation.nested_remote_source_unsupported")
        if candidate.source_path == ".":
            package_path = source_root.resolve()
        else:
            package_path = (source_root / candidate.source_path).resolve()
        try:
            package_path.relative_to(source_root.resolve())
        except ValueError as exc:
            raise MarketplacePathError("marketplace.validation.path_escape") from exc
        if not package_path.exists() or not package_path.is_dir():
            raise MarketplaceImportSourceError("marketplace.import.validation.source_path_not_found")
        return package_path

    def _reject_import_symlinks(self, package_path: Path) -> None:
        for path in package_path.rglob("*"):
            if path.is_symlink():
                raise MarketplaceImportSourceError("marketplace.package.symlink_rejected")

    def _rewrite_imported_manifest_name(
        self,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        package_id: str,
    ) -> None:
        manifest_path = adapter.manifest_path(package_path)
        manifest = self._read_json(manifest_path)
        manifest["name"] = package_id
        self._atomic_write_json(manifest_path, manifest)

    def _write_import_source_metadata(
        self,
        adapter: MarketplaceProviderAdapter,
        package_path: Path,
        source: MarketplaceImportSource,
        candidate: MarketplaceImportCandidate,
        target_package_id: str,
    ) -> None:
        manifest_path = adapter.manifest_path(package_path)
        manifest = self._read_json(manifest_path)
        manifest["sourceType"] = "imported"
        manifest["importSource"] = {
            "provider": source.provider,
            "sourceKind": source.source_kind,
            "source": source.source,
            "ref": source.ref,
            "packageId": candidate.package_id,
            "targetPackageId": target_package_id,
            "sourcePath": candidate.source_path,
            "importedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._atomic_write_json(manifest_path, manifest)

    def _provider_manifest_backup(
        self,
        registry_root: Path,
        adapter: MarketplaceProviderAdapter,
    ) -> tuple[Path, dict[str, Any]] | None:
        try:
            manifest_path = adapter.marketplace_manifest_path(registry_root)  # type: ignore[attr-defined]
        except AttributeError:
            return None
        return (manifest_path, self._read_json(manifest_path))

    def _rollback_import_candidate(
        self,
        target_path: Path,
        staging_path: Path,
        backup_path: Path,
        manifest_backup: tuple[Path, dict[str, Any]] | None,
        promoted: bool,
        backup_created: bool,
    ) -> None:
        if staging_path.exists():
            shutil.rmtree(staging_path)
        staging_root = staging_path.parent
        if staging_root.name.startswith(".import-") and staging_root.exists():
            shutil.rmtree(staging_root)
        if promoted and target_path.exists():
            shutil.rmtree(target_path)
        if backup_created and backup_path.exists():
            backup_path.rename(target_path)
        if manifest_backup is not None:
            self._atomic_write_json(manifest_backup[0], manifest_backup[1])

    def validate_import_source(self, user_id: str, source: MarketplaceImportSource) -> dict[str, Any]:
        """Validate import source safety boundaries and return resolved source metadata."""
        self._reject_raw_secret_material(source)
        if source.ref:
            self._validate_import_ref(source.ref)
        if source.source_kind == "local":
            return {
                "sourceKind": "local",
                "sourceRoot": self._resolve_allowed_import_local_path(user_id, source.source),
            }
        if source.source_kind == "git":
            parsed = self._parse_git_import_source(source.source)
            if parsed["scheme"] == "https":
                self._reject_https_token_source(source.source)
            ssh_key_path = None
            if parsed["scheme"] == "ssh":
                ssh_key_path = str(self._validate_registry_ssh_key_for_import(user_id)["privateKeyPath"])
            return {
                "sourceKind": "git",
                "host": parsed["host"],
                "scheme": parsed["scheme"],
                "workRoot": self._import_work_root(user_id),
                "sshKeyPath": ssh_key_path,
            }
        raise MarketplaceImportSourceError("marketplace.import.validation.invalid_source_kind")

    def save_uploaded_import_source(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        file_name: str,
        content: bytes,
    ) -> MarketplaceImportUploadResult:
        """Persist and extract an uploaded local import archive."""
        if not file_name or not file_name.lower().endswith(".zip"):
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_upload_archive")
        if not content:
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_upload_archive")
        upload_root = self._allowed_import_local_roots(user_id)[0] / f"upload-{uuid4().hex}"
        upload_root.mkdir(parents=True, exist_ok=False)
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                self._extract_import_archive(archive, upload_root)
        except MarketplaceImportSourceError:
            shutil.rmtree(upload_root, ignore_errors=True)
            raise
        except (zipfile.BadZipFile, OSError) as exc:
            shutil.rmtree(upload_root, ignore_errors=True)
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_upload_archive") from exc
        return MarketplaceImportUploadResult(
            source=MarketplaceImportSource(
                provider=provider,
                source_kind="local",
                source=str(upload_root),
            ),
            file_name=file_name,
        )

    def _extract_import_archive(self, archive: zipfile.ZipFile, target_root: Path) -> None:
        """Extract an import archive without allowing paths to escape the target root."""
        target_resolved = target_root.resolve()
        for member in archive.infolist():
            member_path = target_resolved / member.filename
            try:
                member_path.resolve().relative_to(target_resolved)
            except ValueError as exc:
                raise MarketplaceImportSourceError("marketplace.validation.path_escape") from exc
            if member.is_dir():
                member_path.mkdir(parents=True, exist_ok=True)
                continue
            member_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source_file, member_path.open("wb") as target_file:
                shutil.copyfileobj(source_file, target_file)

    def save_registry_ssh_key(self, user_id: str, key_record: dict[str, Any]) -> None:
        """Persist the current user's registry Git SSH key material."""
        path = self._registry_ssh_key_path(self.get_registry_root(user_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(path, key_record)

    def get_registry_ssh_key(self, user_id: str) -> dict[str, Any] | None:
        """Return the current user's registry Git SSH key material."""
        path = self._registry_ssh_key_path(self.get_registry_root(user_id))
        return self._read_json(path) if path.exists() else None

    def get_registry_ssh_key_metadata(self, user_id: str) -> MarketplaceRegistrySshKeyResponse:
        """Return current user's registry Git SSH public key metadata."""
        record = self.get_registry_ssh_key(user_id)
        if not record:
            return MarketplaceRegistrySshKeyResponse(exists=False)
        return MarketplaceRegistrySshKeyResponse(
            exists=True,
            public_key=str(record.get("publicKey") or ""),
            fingerprint=str(record.get("fingerprint") or ""),
            algorithm=str(record.get("algorithm") or ""),
            created_at=str(record.get("createdAt") or ""),
        )

    def generate_registry_ssh_key(self, user_id: str) -> MarketplaceRegistrySshKeyResponse:
        """Generate and persist a registry Git SSH key pair for the current user."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            root.mkdir(parents=True, exist_ok=True)
            key_dir = root / ".marketplace" / "ssh"
            key_dir.mkdir(parents=True, exist_ok=True)
            private_key_path = key_dir / "id_ed25519"
            if private_key_path.exists():
                private_key_path.unlink()
            public_key_path = Path(f"{private_key_path}.pub")
            if public_key_path.exists():
                public_key_path.unlink()
            self._run_process(
                [
                    "ssh-keygen",
                    "-q",
                    "-t",
                    "ed25519",
                    "-N",
                    "",
                    "-C",
                    f"marketplace-{user_id}",
                    "-f",
                    str(private_key_path),
                ],
                cwd=root,
            )
            public_key = public_key_path.read_text(encoding="utf-8").strip()
            fingerprint_output = self._process_output(["ssh-keygen", "-lf", str(public_key_path)], cwd=root)
            fingerprint_parts = fingerprint_output.split()
            record = {
                "algorithm": "ed25519",
                "publicKey": public_key,
                "fingerprint": fingerprint_parts[1] if len(fingerprint_parts) > 1 else "",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "privateKeyPath": str(private_key_path),
                "publicKeyPath": str(public_key_path),
            }
            self.save_registry_ssh_key(user_id, record)
            return self.get_registry_ssh_key_metadata(user_id)

    def save_git_identity(self, user_id: str, identity: dict[str, str]) -> None:
        """Persist the current user's Marketplace registry Git identity."""
        path = self._git_identity_path(self.get_registry_root(user_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write_json(path, {
            "name": identity.get("name", ""),
            "email": identity.get("email", ""),
        })

    def get_git_identity(self, user_id: str) -> dict[str, str] | None:
        """Return the current user's Marketplace registry Git identity."""
        path = self._git_identity_path(self.get_registry_root(user_id))
        if not path.exists():
            return None
        data = self._read_json(path)
        return {
            "name": str(data.get("name") or ""),
            "email": str(data.get("email") or ""),
        }

    def create_package(
        self,
        user_id: str,
        request: MarketplacePackageCreateRequest,
    ) -> MarketplacePackageDetail:
        """Create a provider-native package scaffold."""
        with self._registry_lock:
            self.initialize_registry(user_id)
            package_path = self.resolve_package_path(user_id, request.provider, request.package_id)
            if package_path.exists():
                raise FileExistsError("marketplace.package.already_exists")
            package_path.mkdir(parents=True)
            adapter = self._get_adapter(request.provider)
            adapter.create_package(package_path, request)
            if request.provider == "claude-code":
                adapter.upsert_listing_entry(
                    self.get_registry_root(user_id),
                    request.package_id,
                    {
                        "name": request.package_id,
                        "source": f"./plugins/{request.package_id}",
                        "description": request.description,
                    },
                )
            elif request.provider == "codex":
                adapter.upsert_listing_entry(
                    self.get_registry_root(user_id),
                    request.package_id,
                    {
                        "name": request.package_id,
                        "source": {"source": "local", "path": f"./plugins/{request.package_id}"},
                        "description": request.description,
                        "category": "uncategorized",
                    },
                )
            self.invalidate_package_index(user_id)
            detail = self.get_package_detail(user_id, request.provider, request.package_id)
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            return detail

    def save_package(
        self,
        user_id: str,
        request: MarketplacePackageSaveRequest,
    ) -> MarketplacePackageSaveResult:
        """Save package projection and manifest with optimistic revision checks."""
        with self._registry_lock:
            detail = self.get_package_detail(user_id, request.provider, request.package_id)
            if detail is None:
                raise FileNotFoundError("marketplace.package.not_found")
            if detail.revision != request.revision:
                raise MarketplaceConflictError("marketplace.package.revision_conflict")

            package_path = self.resolve_package_path(user_id, request.provider, request.package_id)
            validation_results: list[dict[str, Any]] = []
            adapter = self._get_adapter(request.provider)
            if request.manifest is None:
                self._raise_if_validation_blocks(
                    adapter.validate_package(package_path),
                    "save",
                )

            if request.provider in {"claude-code", "codex"} and request.listing is not None:
                listing, stripped = self._strip_root_metadata(request.listing)
                listing_validation = self._validate_listing_entry(request.package_id, listing)
                if listing_validation:
                    raise MarketplaceValidationError(listing_validation)
                if stripped:
                    validation_results.append({
                        "severity": "info",
                        "code": "marketplace.validation.root_metadata_stripped",
                        "messageKey": "marketplace.validation.root_metadata_stripped",
                    })
                adapter.upsert_listing_entry(self.get_registry_root(user_id), request.package_id, listing)

            if request.manifest is not None:
                manifest_validation = adapter.validate_manifest_data(  # type: ignore[attr-defined]
                    package_id=request.package_id,
                    manifest=request.manifest,
                    file_path=str(adapter.manifest_path(package_path).relative_to(package_path)),
                )
                self._raise_if_validation_blocks(manifest_validation, "save")
                manifest_path = adapter.manifest_path(package_path)
                self._atomic_write_json(manifest_path, request.manifest)

            if request.readme_markdown is not None:
                (package_path / "README.md").write_text(request.readme_markdown, encoding="utf-8")

            if request.package_files is not None:
                self._sync_package_files(package_path, request.package_files)

            self.invalidate_package_index(user_id)
            updated = self.get_package_detail(user_id, request.provider, request.package_id)
            if updated is None:
                raise FileNotFoundError("marketplace.package.not_found")
            return MarketplacePackageSaveResult(
                package=updated,
                revision=updated.revision,
                validation_results=validation_results,
            )

    def delete_package(
        self,
        user_id: str,
        request: MarketplacePackageDeleteRequest,
    ) -> MarketplacePackageDeleteResult:
        """Hard delete a package after revision verification."""
        with self._registry_lock:
            detail = self.get_package_detail(user_id, request.provider, request.package_id)
            if detail is None:
                self.record_activity(
                    user_id,
                    action="delete",
                    status="failed",
                    provider=request.provider,
                    package_id=request.package_id,
                    error_code="marketplace.package.not_found",
                )
                return MarketplacePackageDeleteResult(
                    deleted=False,
                    error_code="marketplace.package.not_found",
                )
            if detail.revision != request.revision:
                self.record_activity(
                    user_id,
                    action="delete",
                    status="failed",
                    provider=request.provider,
                    package_id=request.package_id,
                    error_code="marketplace.package.revision_conflict",
                )
                return MarketplacePackageDeleteResult(
                    deleted=False,
                    error_code="marketplace.package.revision_conflict",
                )
            package_path = self.resolve_package_path(user_id, request.provider, request.package_id)
            if package_path.exists():
                shutil.rmtree(package_path)
            if request.provider in {"claude-code", "codex"}:
                adapter = self._get_adapter(request.provider)
                adapter.remove_listing_entry(self.get_registry_root(user_id), request.package_id)
            self.invalidate_package_index(user_id)
            self.record_activity(
                user_id,
                action="delete",
                status="success",
                provider=request.provider,
                package_id=request.package_id,
            )
            return MarketplacePackageDeleteResult(
                deleted=True,
                revision=f"deleted-{detail.revision}",
            )

    def export_package(self, user_id: str, provider: MarketplaceProvider, package_id: str) -> bytes:
        """Export a package directory as a provider-native zip archive."""
        package_path = self.resolve_package_path(user_id, provider, package_id)
        if not package_path.exists():
            raise FileNotFoundError("marketplace.package.not_found")
        adapter = self._get_adapter(provider)
        self._raise_if_validation_blocks(adapter.validate_package(package_path), "export")
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(item for item in package_path.rglob("*") if item.is_file()):
                if path.is_symlink():
                    raise MarketplacePathError("marketplace.package.symlink_rejected")
                self._assert_relative_to(path, package_path)
                rel_path = path.relative_to(package_path)
                if ".git" in rel_path.parts or "__pycache__" in rel_path.parts:
                    continue
                archive.write(path, rel_path.as_posix())
        return buffer.getvalue()

    def install_package(
        self,
        user_id: str,
        request: MarketplaceInstallRequest,
    ) -> MarketplaceInstallResult:
        """Validate and coordinate a provider-native CLI install into a workspace runtime."""
        detail = self.get_package_detail(user_id, request.provider, request.package_id)
        if detail is None:
            raise FileNotFoundError("marketplace.package.not_found")
        if detail.revision != request.revision:
            raise MarketplaceConflictError("marketplace.package.revision_conflict")

        package_path = self.resolve_package_path(user_id, request.provider, request.package_id)
        adapter = self._get_adapter(request.provider)
        validation_results = adapter.validate_package(package_path)
        try:
            self._raise_if_validation_blocks(validation_results, "install")
        except MarketplaceValidationError:
            result = self._install_result(
                request,
                "validation",
                "marketplace.install.validation_failed",
            )
            self._record_install_completion(user_id, result)
            return result

        runtime = self._resolve_install_runtime(request.workspace_id)
        if runtime["errorCode"]:
            result = self._install_result(
                request,
                "runtimeUnavailable",
                str(runtime["errorCode"]),
            )
            self._record_install_completion(user_id, result)
            return result

        self._record_install_intent(
            user_id,
            request,
            package_revision=detail.revision,
            runtime_url=str(runtime["runtimeUrl"]),
        )
        preflight = self.detect_cli(request.provider)
        if preflight.error_code == "marketplace.install.cli_unavailable":
            preflight = self._detect_cli_on_runtime(request.provider, str(runtime["runtimeUrl"]))
        if preflight.error_code == "marketplace.install.cli_unavailable":
            result = self._install_result(
                request,
                "cliUnavailable",
                preflight.error_code,
            )
            self._record_install_completion(user_id, result)
            return result
        if preflight.error_code == "marketplace.install.cli_version_unsupported":
            result = self._install_result(
                request,
                "cliVersionUnsupported",
                preflight.error_code,
            )
            self._record_install_completion(user_id, result)
            return result
        if preflight.error_code == "marketplace.install.cli_capability_missing":
            result = self._install_result(
                request,
                "cliCapabilityMissing",
                preflight.error_code,
            )
            self._record_install_completion(user_id, result)
            return result

        try:
            runtime_package_path = self._stage_install_provider_root(
                request.workspace_id,
                request.provider,
                package_path,
            )
            command_plan = adapter.build_install_command(runtime_package_path, request.workspace_id, preflight)
            self._validate_install_command_plan(command_plan)
        except NotImplementedError:
            result = self._install_result(
                request,
                "cliCapabilityMissing",
                "marketplace.install.cli_capability_missing",
            )
            self._record_install_completion(user_id, result)
            return result
        except OSError:
            result = self._install_result(
                request,
                "cliUnavailable",
                "marketplace.install.cli_unavailable",
            )
            self._record_install_completion(user_id, result)
            return result

        result = self._execute_install_command_on_runtime(
            request,
            command_plan,
            runtime_url=str(runtime["runtimeUrl"]),
        )
        self._record_install_completion(user_id, result)
        return result

    def detect_cli(self, provider: MarketplaceProvider) -> MarketplaceCliPreflightResult:
        """Detect provider CLI availability, version, and install capabilities."""
        config = self._cli_preflight_config(provider)
        executable_path = self._find_cli_executable(config["executables"])
        if executable_path is None:
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=False,
                error_code="marketplace.install.cli_unavailable",
            )

        version_text = self._run_cli_probe([executable_path, *config["versionArgs"]])
        if version_text is None:
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=False,
                executable_path=executable_path,
                error_code="marketplace.install.cli_unavailable",
            )
        version = self._extract_cli_version(version_text)
        if self._is_cli_version_unsupported(version, config["minimumVersion"]):
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=True,
                executable_path=executable_path,
                version=version,
                error_code="marketplace.install.cli_version_unsupported",
            )

        help_text = self._run_cli_probe([executable_path, *config["helpArgs"]]) or ""
        capabilities = self._detect_cli_capabilities(provider, help_text)
        if self._missing_required_cli_capability(provider, capabilities):
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=True,
                executable_path=executable_path,
                version=version,
                capabilities=capabilities,
                error_code="marketplace.install.cli_capability_missing",
            )
        return MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path=executable_path,
            version=version,
            capabilities=capabilities,
        )

    def detect_cli_for_workspace(
        self,
        provider: MarketplaceProvider,
        workspace_id: str,
    ) -> MarketplaceCliPreflightResult:
        runtime = self._resolve_install_runtime(workspace_id)
        if runtime["errorCode"]:
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=False,
                error_code=str(runtime["errorCode"]),
            )
        return self._detect_cli_on_runtime(provider, str(runtime["runtimeUrl"]))

    def save_settings(
        self,
        user_id: str,
        metadata: MarketplaceRegistryRootMetadataSavePayload,
    ) -> MarketplaceSettingsSaveResult:
        """Save root metadata to Claude and Codex manifests under the registry lock."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            self._ensure_provider_roots(root)
            claude_path = self._claude_manifest_path(root)
            codex_path = self._codex_manifest_path(root)

            claude_written = False
            codex_written = False
            partial_provider: MarketplaceProvider | None = None
            error_code: str | None = None

            try:
                claude_manifest = self._merge_root_manifest(
                    claude_path,
                    self._build_claude_manifest(metadata),
                )
                self._atomic_write_json(claude_path, claude_manifest)
                claude_written = True
                codex_manifest = self._merge_root_manifest(
                    codex_path,
                    self._build_codex_manifest(metadata),
                )
                self._atomic_write_json(codex_path, codex_manifest)
                codex_written = True
                self.invalidate_package_index(user_id)
            except Exception:
                if claude_written and not codex_written:
                    partial_provider = "claude-code"
                elif codex_written and not claude_written:
                    partial_provider = "codex"
                if claude_written or codex_written:
                    self.invalidate_package_index(user_id)
                error_code = "marketplace.settings.partial_write"

            return MarketplaceSettingsSaveResult(
                settings=self.get_settings(user_id),
                claude_written=claude_written,
                codex_written=codex_written,
                partial_success_provider=partial_provider,
                error_code=error_code,
            )

    def get_registry_repository_status(self, user_id: str) -> MarketplaceRegistryRepositoryStatus:
        """Return current user's Marketplace registry Git repository status."""
        root = self.get_registry_root(user_id)
        is_git_repo = (root / ".git").exists()
        has_local_content = root.exists() and any(root.iterdir())
        if not is_git_repo:
            return MarketplaceRegistryRepositoryStatus(
                is_git_repo=False,
                has_local_content=has_local_content,
                can_clone_safely=not has_local_content,
                can_init_safely=True,
                clone_blocked_reason="marketplace.git.clone_target_not_empty" if has_local_content else None,
            )
        current_branch = self._git_output(root, ["rev-parse", "--abbrev-ref", "HEAD"]) or None
        remote_url = self._git_output(root, ["remote", "get-url", "origin"]) or None
        return MarketplaceRegistryRepositoryStatus(
            is_git_repo=True,
            current_branch=current_branch,
            remote_url=remote_url,
            has_origin=bool(remote_url),
            has_local_content=has_local_content,
            can_clone_safely=False,
            can_init_safely=False,
            clone_blocked_reason="marketplace.git.repository_already_initialized",
        )

    def initialize_git_repository(
        self,
        user_id: str,
        payload: MarketplaceRegistryRemoteRequest | None = None,
    ) -> MarketplaceRegistryGitOperationResult:
        """Initialize the current user's Marketplace registry as a Git repository."""
        with self._registry_lock:
            self.initialize_registry(user_id)
            root = self.get_registry_root(user_id)
            try:
                self._run_git(root, ["init"])
                if payload and payload.remote_url.strip():
                    self._set_git_origin(root, payload.remote_url.strip())
                return MarketplaceRegistryGitOperationResult(
                    success=True,
                    message_key="marketplace.git.init_success",
                    repository=self.get_registry_repository_status(user_id),
                )
            except MarketplaceImportSourceError as exc:
                return MarketplaceRegistryGitOperationResult(
                    success=False,
                    message_key=exc.code,
                    error_code=exc.code,
                    repository=self.get_registry_repository_status(user_id),
                )

    def clone_registry(
        self,
        user_id: str,
        payload: MarketplaceRegistryCloneRequest,
    ) -> MarketplaceRegistryGitOperationResult:
        """Clone a Marketplace registry into the current user's managed registry root."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            if root.exists() and any(root.iterdir()):
                return MarketplaceRegistryGitOperationResult(
                    success=False,
                    message_key="marketplace.git.clone_target_not_empty",
                    error_code="marketplace.git.clone_target_not_empty",
                    repository=self.get_registry_repository_status(user_id),
                )
            root.parent.mkdir(parents=True, exist_ok=True)
            if root.exists():
                shutil.rmtree(root)
            command = ["git", "clone"]
            if payload.branch:
                command.extend(["--branch", payload.branch])
            command.extend([payload.remote_url, str(root)])
            try:
                self._run_process(command, cwd=root.parent)
                self._ensure_provider_roots(root)
                metadata = self._read_metadata(root) if (
                    self._claude_manifest_path(root).exists() or self._codex_manifest_path(root).exists()
                ) else self._default_metadata()
                self._write_manifest_if_missing(
                    self._claude_manifest_path(root),
                    self._build_claude_manifest(metadata),
                )
                self._write_manifest_if_missing(
                    self._codex_manifest_path(root),
                    self._build_codex_manifest(metadata),
                )
                self.invalidate_package_index(user_id)
                return MarketplaceRegistryGitOperationResult(
                    success=True,
                    message_key="marketplace.git.clone_success",
                    repository=self.get_registry_repository_status(user_id),
                )
            except MarketplaceImportSourceError as exc:
                if root.exists() and not (root / ".git").exists():
                    shutil.rmtree(root, ignore_errors=True)
                return MarketplaceRegistryGitOperationResult(
                    success=False,
                    message_key=exc.code,
                    error_code=exc.code,
                    repository=self.get_registry_repository_status(user_id),
                )

    def set_registry_remote(
        self,
        user_id: str,
        payload: MarketplaceRegistryRemoteRequest,
    ) -> MarketplaceRegistryGitOperationResult:
        """Set current user's Marketplace registry origin remote."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            if not (root / ".git").exists():
                return MarketplaceRegistryGitOperationResult(
                    success=False,
                    message_key="marketplace.git.repository_not_initialized",
                    error_code="marketplace.git.repository_not_initialized",
                    repository=self.get_registry_repository_status(user_id),
                )
            try:
                self._set_git_origin(root, payload.remote_url.strip())
                return MarketplaceRegistryGitOperationResult(
                    success=True,
                    message_key="marketplace.git.remote_update_success",
                    repository=self.get_registry_repository_status(user_id),
                )
            except MarketplaceImportSourceError as exc:
                return MarketplaceRegistryGitOperationResult(
                    success=False,
                    message_key=exc.code,
                    error_code=exc.code,
                    repository=self.get_registry_repository_status(user_id),
                )

    def get_registry_git_status(self, user_id: str) -> MarketplaceGitStatus:
        """Return file-level Git status for the current user's Marketplace registry."""
        root = self.get_registry_root(user_id)
        if not (root / ".git").exists():
            return MarketplaceGitStatus(
                branch="",
                is_git_repo=False,
                staged_count=0,
                unstaged_count=0,
                untracked_count=0,
            )
        branch = self._git_output(root, ["rev-parse", "--abbrev-ref", "HEAD"]) or "HEAD"
        output = self._git_output(root, ["status", "--porcelain=v1", "--untracked-files=all"])
        staged: list[MarketplaceGitFileChange] = []
        unstaged: list[MarketplaceGitFileChange] = []
        untracked: list[MarketplaceGitFileChange] = []
        for line in output.splitlines():
            if not line:
                continue
            index_status = line[0]
            worktree_status = line[1]
            path_text = line[3:]
            old_path: str | None = None
            if " -> " in path_text:
                old_path, path_text = path_text.split(" -> ", 1)
            if index_status == "?" and worktree_status == "?":
                untracked.append(self._git_file_change(path_text, "??", old_path=old_path))
                continue
            if index_status != " ":
                staged.append(self._git_file_change(path_text, index_status, old_path=old_path))
            if worktree_status != " ":
                unstaged.append(self._git_file_change(path_text, worktree_status, old_path=old_path))
        return MarketplaceGitStatus(
            branch=branch,
            is_git_repo=True,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            staged_count=len(staged),
            unstaged_count=len(unstaged),
            untracked_count=len(untracked),
        )

    def get_registry_file_diff(
        self,
        user_id: str,
        path: str,
        *,
        head: Literal["WORKTREE", "INDEX"] = "WORKTREE",
    ) -> MarketplaceGitDiffResponse:
        """Return a selected registry file diff from the worktree or index."""
        root = self.get_registry_root(user_id)
        safe_path = self._resolve_registry_git_path(root, path)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError("marketplace.git.repository_not_initialized")
        status = self.get_registry_git_status(user_id)
        if head != "INDEX" and safe_path in {item.path for item in status.untracked}:
            patch = self._untracked_registry_file_diff(root, safe_path)
            return MarketplaceGitDiffResponse(path=safe_path, patch=patch, diff=patch, binary="Binary files" in patch, head=head)
        args = ["diff"]
        if head == "INDEX":
            args.append("--cached")
        args.extend(["--", safe_path])
        patch = self._git_output(root, args)
        return MarketplaceGitDiffResponse(path=safe_path, patch=patch, diff=patch, binary="Binary files" in patch, head=head)

    def get_registry_commit_file_diff(
        self,
        user_id: str,
        commit_id: str,
        path: str,
    ) -> MarketplaceGitDiffResponse:
        """Return a selected registry file diff for a commit."""
        root = self.get_registry_root(user_id)
        safe_path = self._resolve_registry_git_path(root, path)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError("marketplace.git.repository_not_initialized")
        parent = f"{commit_id}^"
        if not self._git_output(root, ["rev-parse", "--verify", f"{commit_id}^{{commit}}"]):
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")
        if not self._git_output(root, ["rev-parse", "--verify", f"{parent}^{{commit}}"]):
            parent = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        patch = self._git_output(root, ["diff", parent, commit_id, "--", safe_path])
        return MarketplaceGitDiffResponse(
            path=safe_path,
            patch=patch,
            diff=patch,
            binary="Binary files" in patch,
            commit_id=commit_id,
        )

    def get_registry_commit_files(self, user_id: str, commit_id: str) -> MarketplaceGitCommitFilesResult:
        """Return provider-prefixed file changes for a selected commit."""
        root = self.get_registry_root(user_id)
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError("marketplace.git.repository_not_initialized")
        if not self._git_output(root, ["rev-parse", "--verify", f"{commit_id}^{{commit}}"]):
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")
        parent = f"{commit_id}^"
        if not self._git_output(root, ["rev-parse", "--verify", f"{parent}^{{commit}}"]):
            parent = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        output = self._git_output(root, ["diff", "--name-status", parent, commit_id])
        files: list[MarketplaceGitFileChange] = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status_code = parts[0]
            if status_code.startswith(("R", "C")) and len(parts) >= 3:
                files.append(self._git_file_change(parts[2], status_code[:1], old_path=parts[1]))
            else:
                files.append(self._git_file_change(parts[1], status_code[:1]))
        return MarketplaceGitCommitFilesResult(commit_id=commit_id, files=files)

    def stage_registry_paths(self, user_id: str, payload: MarketplaceGitPathRequest) -> MarketplaceGitStatus:
        """Stage selected Marketplace registry paths."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            self._require_registry_git_repo(root)
            paths = [self._resolve_registry_git_path(root, path) for path in payload.paths]
            if paths:
                self._run_git(root, ["add", "--", *paths])
            return self.get_registry_git_status(user_id)

    def unstage_registry_paths(self, user_id: str, payload: MarketplaceGitPathRequest) -> MarketplaceGitStatus:
        """Unstage selected Marketplace registry paths."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            self._require_registry_git_repo(root)
            paths = [self._resolve_registry_git_path(root, path) for path in payload.paths]
            if paths:
                if self._git_output(root, ["rev-parse", "--verify", "HEAD"]):
                    self._run_git(root, ["restore", "--staged", "--", *paths])
                else:
                    self._run_git(root, ["rm", "--cached", "--ignore-unmatch", "--", *paths])
            return self.get_registry_git_status(user_id)

    def commit_registry_changes(
        self,
        user_id: str,
        payload: MarketplaceGitCommitRequest,
    ) -> MarketplaceGitCommitResult:
        """Commit selected or already staged Marketplace registry changes."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            self._require_registry_git_repo(root)
            message = payload.message.strip()
            if not message:
                raise MarketplaceImportSourceError("marketplace.git.commit_message_required")
            if payload.paths:
                paths = [self._resolve_registry_git_path(root, path) for path in payload.paths]
                self._run_git(root, ["add", "--", *paths])
            status_before = self.get_registry_git_status(user_id)
            if status_before.staged_count == 0:
                return MarketplaceGitCommitResult(
                    success=False,
                    message_key="marketplace.git.no_changes_to_commit",
                    error_code="marketplace.git.no_changes_to_commit",
                    status=status_before,
                )
            self._run_process(["git", *self._git_identity_args(user_id), "commit", "-m", message], cwd=root)
            commit_id = self._git_output(root, ["rev-parse", "HEAD"])
            return MarketplaceGitCommitResult(
                success=True,
                message_key="marketplace.git.commit_success",
                commit=self._registry_commit_summary(root, commit_id),
                status=self.get_registry_git_status(user_id),
            )

    def list_registry_commits(
        self,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> MarketplaceGitCommitListResult:
        """List Marketplace registry commit history."""
        root = self.get_registry_root(user_id)
        self._require_registry_git_repo(root)
        safe_page = max(page, 1)
        safe_page_size = min(max(page_size, 1), 100)
        total_text = self._git_output(root, ["rev-list", "--count", "HEAD"])
        total = int(total_text) if total_text.isdigit() else 0
        if total == 0:
            return MarketplaceGitCommitListResult(page=safe_page, page_size=safe_page_size, total=0, items=[])
        skip = (safe_page - 1) * safe_page_size
        commit_ids = self._git_output(root, ["log", f"--skip={skip}", f"--max-count={safe_page_size}", "--format=%H"])
        return MarketplaceGitCommitListResult(
            page=safe_page,
            page_size=safe_page_size,
            total=total,
            items=[
                self._registry_commit_summary(root, commit_id)
                for commit_id in commit_ids.splitlines()
                if commit_id
            ],
        )

    def fetch_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Fetch current user's Marketplace registry remote."""
        with self._registry_lock:
            return self._run_registry_remote_operation(user_id, ["fetch", "origin"], "marketplace.git.fetch_success")

    def pull_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Pull current user's Marketplace registry remote branch."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            branch = self._current_registry_branch(root)
            return self._run_registry_remote_operation(
                user_id,
                ["pull", "--ff-only", "origin", branch],
                "marketplace.git.pull_success",
            )

    def push_registry(self, user_id: str) -> MarketplaceRegistryGitOperationResult:
        """Push current user's Marketplace registry branch to origin."""
        with self._registry_lock:
            root = self.get_registry_root(user_id)
            branch = self._current_registry_branch(root)
            return self._run_registry_remote_operation(
                user_id,
                ["push", "origin", branch],
                "marketplace.git.push_success",
            )

    def resolve_package_path(self, user_id: str, provider: MarketplaceProvider, package_id: str) -> Path:
        """Resolve a package path and ensure it stays inside the selected provider root."""
        if not self._package_id_pattern.match(package_id):
            raise MarketplacePathError("marketplace.package.invalid_id")

        root = self.get_registry_root(user_id)
        adapter = self._get_adapter(provider)
        provider_root = self.get_provider_root(user_id, provider)
        candidate = adapter.package_path(root, package_id)

        self._assert_relative_to(candidate, root)
        self._assert_relative_to(candidate, provider_root)
        return candidate

    def _get_package_index(self, root: Path) -> tuple[list[MarketplacePackageSummary], str]:
        fingerprint = self._registry_fingerprint(root)
        root_key = str(root)
        with self._index_lock:
            cached = self._package_index.get(root_key)
            if cached and cached[0] == fingerprint:
                return cached[1], fingerprint
            items = self._scan_registry(root)
            self._package_index[root_key] = (fingerprint, items)
            return items, fingerprint

    def _registry_fingerprint(self, root: Path) -> str:
        digest = sha256()
        if not root.exists():
            return digest.hexdigest()[:16]
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if ".git" in path.relative_to(root).parts:
                continue
            stat = path.stat()
            digest.update(f"{path.relative_to(root)}:{stat.st_mtime_ns}:{stat.st_size}".encode())
        return digest.hexdigest()[:16]

    def _scan_registry(self, root: Path) -> list[MarketplacePackageSummary]:
        if not root.exists():
            return []
        packages: list[MarketplacePackageSummary] = []
        for adapter in self.adapters.values():
            packages.extend(adapter.scan_registry(root))
        return sorted(packages, key=lambda item: (item.provider, item.package_id))

    def _activity_log_path(self, root: Path) -> Path:
        return root / ".marketplace" / "activity.jsonl"

    def _install_intents_path(self, root: Path) -> Path:
        return root / ".marketplace" / "install-intents.jsonl"

    def _registry_ssh_key_path(self, root: Path) -> Path:
        return root / ".marketplace" / "registry-ssh-key.json"

    def _git_identity_path(self, root: Path) -> Path:
        return root / ".marketplace" / "git-identity.json"

    def _install_result(
        self,
        request: MarketplaceInstallRequest,
        install_status: str,
        error_code: str | None = None,
        *,
        stdout: str | None = None,
        stderr: str | None = None,
        truncated: bool = False,
        stdout_limit_bytes: int = 65_536,
        stderr_limit_bytes: int = 65_536,
        redact_patterns: list[str] | None = None,
    ) -> MarketplaceInstallResult:
        sanitized_stdout, sanitized_stderr, output_truncated = self._sanitize_install_output(
            stdout=stdout,
            stderr=stderr,
            stdout_limit_bytes=stdout_limit_bytes,
            stderr_limit_bytes=stderr_limit_bytes,
            redact_patterns=redact_patterns or self._default_install_redact_patterns(),
        )
        return MarketplaceInstallResult(
            status=install_status,  # type: ignore[arg-type]
            provider=request.provider,
            package_id=request.package_id,
            workspace_id=request.workspace_id,
            error_code=error_code,
            stdout=sanitized_stdout,
            stderr=sanitized_stderr,
            truncated=truncated or output_truncated,
        )

    def _sanitize_install_output(
        self,
        *,
        stdout: str | None,
        stderr: str | None,
        stdout_limit_bytes: int,
        stderr_limit_bytes: int,
        redact_patterns: list[str],
    ) -> tuple[str | None, str | None, bool]:
        sanitized_stdout = self._redact_install_output(stdout, redact_patterns)
        sanitized_stderr = self._redact_install_output(stderr, redact_patterns)
        limited_stdout, stdout_truncated = self._limit_install_output(
            sanitized_stdout,
            stdout_limit_bytes,
        )
        limited_stderr, stderr_truncated = self._limit_install_output(
            sanitized_stderr,
            stderr_limit_bytes,
        )
        return limited_stdout, limited_stderr, stdout_truncated or stderr_truncated

    def _redact_install_output(self, output: str | None, patterns: list[str]) -> str | None:
        if output is None:
            return None
        redacted = output
        for pattern in patterns:
            redacted = re.sub(pattern, self._redact_match, redacted)
        return redacted

    def _redact_match(self, match: re.Match[str]) -> str:
        if match.groups():
            return "".join(group or "" for group in match.groups()) + "[REDACTED]"
        return "[REDACTED]"

    def _limit_install_output(self, output: str | None, limit_bytes: int) -> tuple[str | None, bool]:
        if output is None:
            return None, False
        encoded = output.encode("utf-8")
        if len(encoded) <= limit_bytes:
            return output, False
        return encoded[:limit_bytes].decode("utf-8", errors="ignore"), True

    def _default_install_redact_patterns(self) -> list[str]:
        return [
            r"(?i)\b(api[_-]?key|token|secret|password)(\s*=\s*)\S+",
            r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+",
        ]

    def _cli_preflight_config(self, provider: MarketplaceProvider) -> dict[str, Any]:
        configs: dict[MarketplaceProvider, dict[str, Any]] = {
            "claude-code": {
                "executables": ["claude"],
                "versionArgs": ["--version"],
                "helpArgs": ["plugin", "--help"],
                "minimumVersion": None,
            },
            "codex": {
                "executables": ["codex"],
                "versionArgs": ["--version"],
                "helpArgs": ["plugin", "marketplace", "--help"],
                "minimumVersion": None,
            },
            "gemini": {
                "executables": ["gemini"],
                "versionArgs": ["--version"],
                "helpArgs": ["extensions", "--help"],
                "minimumVersion": None,
            },
        }
        return configs[provider]

    def _find_cli_executable(self, names: list[str]) -> str | None:
        for name in names:
            resolved = shutil.which(name)
            if resolved:
                return resolved
        return None

    def _run_cli_probe(self, argv: list[str]) -> str | None:
        try:
            result = subprocess.run(
                argv,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 and not (result.stdout or result.stderr):
            return None
        return "\n".join(part for part in [result.stdout, result.stderr] if part)

    def _git_output(self, root: Path, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.rstrip("\n") if result.returncode == 0 else ""

    def _run_git(self, root: Path, args: list[str]) -> None:
        self._run_process(["git", *args], cwd=root)

    def _run_process(self, command: list[str], *, cwd: Path) -> None:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed") from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")

    def _process_output(self, command: list[str], *, cwd: Path) -> str:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed") from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.git.operation_failed")
        return result.stdout.strip()

    def _set_git_origin(self, root: Path, remote_url: str) -> None:
        if not remote_url:
            raise MarketplaceImportSourceError("marketplace.git.remote_required")
        if self._git_output(root, ["remote", "get-url", "origin"]):
            self._run_git(root, ["remote", "set-url", "origin", remote_url])
        else:
            self._run_git(root, ["remote", "add", "origin", remote_url])

    def _git_file_change(
        self,
        path: str,
        status_code: str,
        *,
        old_path: str | None = None,
    ) -> MarketplaceGitFileChange:
        change_type_by_status = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
            "R": "renamed",
            "C": "copied",
            "T": "typechange",
            "U": "unmerged",
            "?": "untracked",
        }
        return MarketplaceGitFileChange(
            path=path,
            status=status_code,
            type=change_type_by_status.get(status_code[:1], "modified"),  # type: ignore[arg-type]
            old_path=old_path,
        )

    def _extract_cli_version(self, output: str) -> str | None:
        match = self._version_pattern.search(output)
        return match.group("version") if match else None

    def _is_cli_version_unsupported(
        self,
        version: str | None,
        minimum_version: str | None,
    ) -> bool:
        if minimum_version is None:
            return False
        if version is None:
            return True
        return self._parse_version_tuple(version) < self._parse_version_tuple(minimum_version)

    def _parse_version_tuple(self, version: str) -> tuple[int, ...]:
        return tuple(int(part) for part in version.split("."))

    def _detect_cli_capabilities(
        self,
        provider: MarketplaceProvider,
        help_text: str,
    ) -> MarketplaceCliCapabilities:
        normalized = help_text.lower()
        supports_provider_install = (
            ("plugin" in normalized and "install" in normalized and "marketplace" in normalized)
            if provider == "claude-code"
            else ("marketplace" in normalized and "add" in normalized)
        )
        return MarketplaceCliCapabilities(
            supports_user_scope=("--user" in normalized or " user" in normalized),
            supports_marketplace_add=supports_provider_install,
            supports_extension_install=(
                provider == "gemini"
                and "extensions" in normalized
                and "install" in normalized
            ),
        )

    def _missing_required_cli_capability(
        self,
        provider: MarketplaceProvider,
        capabilities: MarketplaceCliCapabilities,
    ) -> bool:
        if provider in {"claude-code", "codex"}:
            return not capabilities.supports_marketplace_add
        if provider == "gemini":
            return not capabilities.supports_extension_install
        return True

    def _detect_cli_on_runtime(
        self,
        provider: MarketplaceProvider,
        runtime_url: str,
    ) -> MarketplaceCliPreflightResult:
        config = self._cli_preflight_config(provider)
        executable_name = str(config["executables"][0])
        executable_path = self._run_runtime_probe(
            runtime_url,
            provider,
            ["sh", "-lc", f"command -v {shlex.quote(executable_name)}"],
        )
        if not executable_path:
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=False,
                error_code="marketplace.install.cli_unavailable",
            )

        executable = executable_path.strip().splitlines()[0]
        version_text = self._run_runtime_probe(runtime_url, provider, [executable, *config["versionArgs"]])
        if version_text is None:
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=False,
                executable_path=executable,
                error_code="marketplace.install.cli_unavailable",
            )
        version = self._extract_cli_version(version_text)
        if self._is_cli_version_unsupported(version, config["minimumVersion"]):
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=True,
                executable_path=executable,
                version=version,
                error_code="marketplace.install.cli_version_unsupported",
            )

        help_text = self._run_runtime_probe(runtime_url, provider, [executable, *config["helpArgs"]]) or ""
        capabilities = self._detect_cli_capabilities(provider, help_text)
        if self._missing_required_cli_capability(provider, capabilities):
            return MarketplaceCliPreflightResult(
                provider=provider,
                available=True,
                executable_path=executable,
                version=version,
                capabilities=capabilities,
                error_code="marketplace.install.cli_capability_missing",
            )
        return MarketplaceCliPreflightResult(
            provider=provider,
            available=True,
            executable_path=executable,
            version=version,
            capabilities=capabilities,
        )

    def _run_runtime_probe(
        self,
        runtime_url: str,
        provider: MarketplaceProvider,
        argv: list[str],
    ) -> str | None:
        payload = MarketplaceInstallCommandPlan(
            provider=provider,
            argv=argv,
            cwd="/workspace",
            timeout_ms=5_000,
            stdout_limit_bytes=16_384,
            stderr_limit_bytes=16_384,
        ).model_dump(by_alias=True)
        headers = {"Authorization": f"Bearer {get_settings().INTERNAL_API_TOKEN}"}
        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(
                    f"{runtime_url.rstrip('/')}/api/v1/internal/marketplace/install/execute",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None
        if data.get("status") != "success":
            return None
        return "\n".join(
            part
            for part in [data.get("stdout"), data.get("stderr")]
            if isinstance(part, str) and part.strip()
        )

    def _validate_install_command_plan(self, plan: MarketplaceInstallCommandPlan) -> None:
        if not plan.argv or any(not isinstance(arg, str) or not arg for arg in plan.argv):
            raise MarketplaceValidationError([{
                "severity": "error",
                "code": "marketplace.install.command_plan_invalid",
                "messageKey": "marketplace.install.command_plan_invalid",
            }])
        if any(any(token in arg for token in ["&&", "||", ";", "`"]) for arg in plan.argv):
            raise MarketplaceValidationError([{
                "severity": "error",
                "code": "marketplace.install.command_plan_invalid",
                "messageKey": "marketplace.install.command_plan_invalid",
            }])
        if not plan.cwd:
            raise MarketplaceValidationError([{
                "severity": "error",
                "code": "marketplace.install.command_plan_invalid",
                "messageKey": "marketplace.install.command_plan_invalid",
            }])
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in plan.env.items()):
            raise MarketplaceValidationError([{
                "severity": "error",
                "code": "marketplace.install.command_plan_invalid",
                "messageKey": "marketplace.install.command_plan_invalid",
            }])

    def _resolve_install_runtime(self, workspace_id: str) -> dict[str, str | None]:
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
        runtime_url = workspace.runtime_internal_url or workspace.runtime_external_url
        if not runtime_url:
            return {
                "runtimeUrl": None,
                "errorCode": "marketplace.install.runtime_url_missing",
            }
        return {
            "runtimeUrl": runtime_url.rstrip("/"),
            "errorCode": None,
        }

    def _stage_install_provider_root(
        self,
        workspace_id: str,
        provider: MarketplaceProvider,
        package_path: Path,
    ) -> Path:
        provider_root = package_path.parents[1]
        manager_workspace = self._manager_workspace_path(workspace_id)
        runtime_workspace = Path("/workspace")
        stage_relative = Path(".marketplace-install") / provider
        manager_stage_root = manager_workspace / stage_relative
        runtime_stage_root = runtime_workspace / stage_relative

        if manager_stage_root.exists():
            shutil.rmtree(manager_stage_root)
        manager_stage_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(provider_root, manager_stage_root)
        if provider == "claude-code":
            self._normalize_staged_claude_marketplace_manifest(manager_stage_root)

        relative_package_path = package_path.relative_to(provider_root)
        return runtime_stage_root / relative_package_path

    def _normalize_staged_claude_marketplace_manifest(self, staged_provider_root: Path) -> None:
        manifest_path = staged_provider_root / ".claude-plugin" / "marketplace.json"
        manifest = self._read_json(manifest_path)
        if not manifest:
            return
        manifest["name"] = "local-marketplace"
        self._atomic_write_json(manifest_path, manifest)

    def _manager_workspace_path(self, workspace_id: str) -> Path:
        base = Path(get_settings().MANAGER_WORKSPACES_DIR)
        candidates = [
            base / workspace_id,
            base / workspace_id.replace("-", "_"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        candidates[0].mkdir(parents=True, exist_ok=True)
        return candidates[0]

    def _execute_install_command_on_runtime(
        self,
        request: MarketplaceInstallRequest,
        command_plan: MarketplaceInstallCommandPlan,
        *,
        runtime_url: str,
    ) -> MarketplaceInstallResult:
        if request.provider == "claude-code":
            marketplace_add_plan = MarketplaceInstallCommandPlan(
                provider=command_plan.provider,
                argv=[
                    command_plan.argv[0],
                    "plugin",
                    "marketplace",
                    "add",
                    command_plan.cwd,
                ],
                cwd=command_plan.cwd,
                env=command_plan.env,
                timeout_ms=command_plan.timeout_ms,
                stdout_limit_bytes=command_plan.stdout_limit_bytes,
                stderr_limit_bytes=command_plan.stderr_limit_bytes,
                redact_patterns=command_plan.redact_patterns,
            )
            marketplace_add_data = self._execute_runtime_command_plan(marketplace_add_plan, runtime_url)
            if marketplace_add_data is None:
                return self._install_result(
                    request,
                    "runtimeUnavailable",
                    "marketplace.install.runtime_delegation_unavailable",
                )
            if marketplace_add_data.get("status") != "success":
                return self._install_result(
                    request,
                    "failed",
                    str(marketplace_add_data.get("errorCode") or "marketplace.install.command_failed"),
                    stdout=marketplace_add_data.get("stdout"),
                    stderr=marketplace_add_data.get("stderr"),
                    truncated=bool(marketplace_add_data.get("truncated")),
                    stdout_limit_bytes=command_plan.stdout_limit_bytes,
                    stderr_limit_bytes=command_plan.stderr_limit_bytes,
                    redact_patterns=command_plan.redact_patterns,
                )

        data = self._execute_runtime_command_plan(command_plan, runtime_url)
        if data is None:
            return self._install_result(
                request,
                "runtimeUnavailable",
                "marketplace.install.runtime_delegation_unavailable",
            )

        runtime_status = data.get("status")
        if runtime_status == "success":
            status: str = "success"
            error_code = None
        elif runtime_status == "timeout":
            status = "timeout"
            error_code = str(data.get("errorCode") or "marketplace.install.timeout")
        else:
            status = "failed"
            error_code = str(data.get("errorCode") or "marketplace.install.command_failed")

        return self._install_result(
            request,
            status,
            error_code,
            stdout=data.get("stdout"),
            stderr=data.get("stderr"),
            truncated=bool(data.get("truncated")),
            stdout_limit_bytes=command_plan.stdout_limit_bytes,
            stderr_limit_bytes=command_plan.stderr_limit_bytes,
            redact_patterns=command_plan.redact_patterns,
        )

    def _execute_runtime_command_plan(
        self,
        command_plan: MarketplaceInstallCommandPlan,
        runtime_url: str,
    ) -> dict[str, Any] | None:
        payload = command_plan.model_dump(by_alias=True)
        headers = {"Authorization": f"Bearer {get_settings().INTERNAL_API_TOKEN}"}
        try:
            with httpx.Client(timeout=(command_plan.timeout_ms / 1000) + 10) as client:
                response = client.post(
                    f"{runtime_url.rstrip('/')}/api/v1/internal/marketplace/install/execute",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None
        return data if isinstance(data, dict) else None

    def _record_install_intent(
        self,
        user_id: str,
        request: MarketplaceInstallRequest,
        *,
        package_revision: str,
        runtime_url: str,
    ) -> None:
        record = {
            "id": str(uuid4()),
            "provider": request.provider,
            "packageId": request.package_id,
            "workspaceId": request.workspace_id,
            "revision": package_revision,
            "runtimeUrl": runtime_url,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        path = self._install_intents_path(self.get_registry_root(user_id))
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    def _record_install_completion(
        self,
        user_id: str,
        result: MarketplaceInstallResult,
    ) -> None:
        self.record_activity(
            user_id,
            action="install",
            status="success" if result.status == "success" else "failed",
            provider=result.provider,
            package_id=result.package_id,
            error_code=result.error_code,
        )

    def _import_work_root(self, user_id: str) -> Path:
        path = self.get_registry_root(user_id).parent / "import-worktrees"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @contextmanager
    def _prepared_import_source_root(
        self,
        source: MarketplaceImportSource,
        metadata: dict[str, Any],
    ) -> Iterator[Path]:
        if metadata["sourceKind"] == "local":
            yield metadata["sourceRoot"]
            return

        work_root = metadata["workRoot"]
        checkout_parent = Path(tempfile.mkdtemp(prefix="scan-", dir=work_root))
        checkout_root = checkout_parent / "checkout"
        try:
            self._clone_import_source(source, checkout_root, metadata.get("sshKeyPath"))
            yield checkout_root
        finally:
            shutil.rmtree(checkout_parent, ignore_errors=True)

    def _clone_import_source(
        self,
        source: MarketplaceImportSource,
        checkout_root: Path,
        ssh_key_path: str | None = None,
    ) -> None:
        command = ["git", "clone", "--depth", "1"]
        if source.ref:
            command.extend(["--branch", source.ref])
        command.extend([source.source, str(checkout_root)])
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env=self._git_ssh_env(ssh_key_path),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise MarketplaceImportSourceError("marketplace.import.validation.clone_failed") from exc
        if result.returncode != 0:
            raise MarketplaceImportSourceError("marketplace.import.validation.clone_failed")
        if not checkout_root.exists() or not checkout_root.is_dir():
            raise MarketplaceImportSourceError("marketplace.import.validation.clone_failed")

    def _git_ssh_env(self, ssh_key_path: str | None) -> dict[str, str] | None:
        if not ssh_key_path:
            return None
        return {
            **os.environ,
            "GIT_SSH_COMMAND": (
                f"ssh -i {shlex.quote(ssh_key_path)} "
                "-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
            ),
        }

    def _allowed_import_local_roots(self, user_id: str) -> list[Path]:
        user_root = self.get_registry_root(user_id).parent
        return [
            (user_root / "import-sources").resolve(),
            (self.storage_root / "import-sources").resolve(),
        ]

    def _resolve_allowed_import_local_path(self, user_id: str, source: str) -> Path:
        if not source.strip():
            raise MarketplaceImportSourceError("marketplace.import.validation.source_required")
        path = Path(source).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except OSError as exc:
            raise MarketplaceImportSourceError("marketplace.import.validation.local_path_not_found") from exc
        if not resolved.is_dir():
            raise MarketplaceImportSourceError("marketplace.import.validation.local_path_not_found")
        for root in self._allowed_import_local_roots(user_id):
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue
        raise MarketplaceImportSourceError("marketplace.import.validation.local_path_not_allowed")

    def _reject_raw_secret_material(self, source: MarketplaceImportSource) -> None:
        values = [source.source]
        if any(self._raw_private_key_pattern.search(value) for value in values):
            raise MarketplaceImportSourceError("marketplace.import.validation.raw_private_key_unsupported")

    def _validate_import_ref(self, ref: str) -> None:
        if (
            not self._git_ref_pattern.match(ref)
            or ".." in ref
            or ref.endswith(".")
            or ref.endswith("/")
            or ref.startswith("-")
        ):
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_ref")

    def _parse_git_import_source(self, source: str) -> dict[str, str]:
        if not source.strip():
            raise MarketplaceImportSourceError("marketplace.import.validation.source_required")
        scp_like = self._git_scp_like_pattern.match(source)
        if scp_like:
            return {
                "scheme": "ssh",
                "host": scp_like.group("host").lower(),
            }
        parsed = urlparse(source)
        scheme = parsed.scheme.lower()
        if scheme not in {"https", "ssh"} or not parsed.netloc:
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_repository_url")
        if parsed.username or parsed.password:
            if scheme == "https":
                raise MarketplaceImportSourceError("marketplace.import.validation.https_token_unsupported")
            raise MarketplaceImportSourceError("marketplace.import.validation.invalid_repository_url")
        return {
            "scheme": scheme,
            "host": (parsed.hostname or "").lower(),
        }

    def _reject_https_token_source(self, source: str) -> None:
        parsed = urlparse(source)
        query = parse_qs(parsed.query)
        token_keys = {"token", "access_token", "auth", "password"}
        if token_keys.intersection(query):
            raise MarketplaceImportSourceError("marketplace.import.validation.https_token_unsupported")

    def _validate_registry_ssh_key_for_import(self, user_id: str) -> dict[str, Any]:
        record = self.get_registry_ssh_key(user_id)
        private_key_path = Path(str(record.get("privateKeyPath") or "")) if record else None
        if not private_key_path or not private_key_path.exists():
            raise MarketplaceImportSourceError("marketplace.import.validation.ssh_key_required")
        return record

    def _read_activity_records(self, user_id: str) -> list[MarketplaceActivityRecord]:
        path = self._activity_log_path(self.get_registry_root(user_id))
        if not path.exists():
            return []
        records: list[MarketplaceActivityRecord] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(MarketplaceActivityRecord.model_validate_json(line))
            except ValueError:
                continue
        return sorted(records, key=lambda record: record.created_at, reverse=True)

    def _filter_packages(
        self,
        items: list[MarketplacePackageSummary],
        *,
        provider: MarketplaceProvider | None,
        q: str | None,
        category: str | None,
        features: list[str],
    ) -> list[MarketplacePackageSummary]:
        normalized_q = (q or "").strip().lower()
        normalized_features = {feature for feature in features if feature}
        result: list[MarketplacePackageSummary] = []
        for item in items:
            if provider and item.provider != provider:
                continue
            if category and category != "all" and item.category != category:
                continue
            indexed_terms = set(item.tags) | set(item.indexed_resource_names)
            if normalized_features and not normalized_features.issubset(indexed_terms):
                continue
            if normalized_q:
                haystack = " ".join([
                    item.provider,
                    item.package_id,
                    item.display_name,
                    item.description or "",
                    item.category or "",
                    *item.tags,
                    *item.indexed_resource_names,
                ]).lower()
                if normalized_q not in haystack:
                    continue
            result.append(item)
        return result

    def _strip_root_metadata(self, listing: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        root_keys = {"owner", "description", "plugins"}
        stripped = any(key in listing for key in root_keys)
        return {key: value for key, value in listing.items() if key not in root_keys}, stripped

    def _discover_readme_path(self, package_path: Path) -> Path | None:
        candidates = [
            "README.md",
            "README.MD",
            "Readme.md",
            "readme.md",
            "README.mdx",
            "README.MDX",
            "readme.mdx",
        ]
        for name in candidates:
            path = package_path / name
            if path.exists() and path.is_file():
                self._assert_relative_to(path, package_path)
                return path
        return None

    def _read_sanitized_readme_markdown(self, package_path: Path) -> str:
        readme_path = self._discover_readme_path(package_path)
        if readme_path is None:
            return ""
        return self._sanitize_readme_markdown(readme_path.read_text(encoding="utf-8"))

    def _sanitize_readme_markdown(self, markdown: str) -> str:
        cleaned = self._unsafe_readme_block_pattern.sub("", markdown)
        cleaned = self._unsafe_readme_single_tag_pattern.sub("", cleaned)
        cleaned = self._readme_event_attr_pattern.sub("", cleaned)
        cleaned = self._readme_javascript_link_pattern.sub(r"\1#\2", cleaned)
        return cleaned

    def _validate_listing_entry(self, package_id: str, listing: dict[str, Any]) -> list[dict[str, Any]]:
        listing_name = listing.get("name")
        if isinstance(listing_name, str) and listing_name and listing_name != package_id:
            return [{
                "severity": "error",
                "code": "marketplace.validation.package_identity_mismatch",
                "messageKey": "marketplace.validation.package_identity_mismatch",
                "details": {
                    "packageId": package_id,
                    "listingName": listing_name,
                },
            }]
        return []

    def validation_blocks_action(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> bool:
        """Return whether validation results block the requested action."""
        return bool(self.blocking_validation_results(validation_results, action))

    def blocking_validation_results(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> list[dict[str, Any]]:
        """Return validation results that block the requested action."""
        if action not in {"save", "export", "install", "importCopy"}:
            return []
        return [
            result
            for result in validation_results
            if result.get("severity") == "error"
        ]

    def _raise_if_validation_blocks(
        self,
        validation_results: list[dict[str, Any]],
        action: MarketplaceValidationAction,
    ) -> None:
        blocking_results = self.blocking_validation_results(validation_results, action)
        if blocking_results:
            raise MarketplaceValidationError(blocking_results)

    def get_provider_root(self, user_id: str, provider: MarketplaceProvider) -> Path:
        """Return a provider root path under the user's registry."""
        root = self.get_registry_root(user_id)
        return root / provider

    def _ensure_provider_roots(self, root: Path) -> None:
        for adapter in self.adapters.values():
            adapter.ensure_roots(root)

    def _read_metadata(self, root: Path) -> MarketplaceRegistryRootMetadataSavePayload:
        data = self._read_json(self._claude_manifest_path(root))
        owner = data.get("owner") if isinstance(data.get("owner"), dict) else {}
        return MarketplaceRegistryRootMetadataSavePayload(
            name=str(data.get("name") or ""),
            owner={
                "name": str(owner.get("name") or ""),
                "email": str(owner.get("email") or ""),
            },
            description=str(data.get("description") or ""),
        )

    def _default_metadata(self) -> MarketplaceRegistryRootMetadataSavePayload:
        return MarketplaceRegistryRootMetadataSavePayload(
            name="Local Marketplace Registry",
            owner={
                "name": "Marketplace Maintainer",
                "email": "marketplace@example.local",
            },
            description="Provider-separated Marketplace package registry.",
        )

    def _build_claude_manifest(self, metadata: MarketplaceRegistryRootMetadataSavePayload) -> dict[str, Any]:
        return {
            "name": metadata.name,
            "owner": {
                "name": metadata.owner.name,
                "email": metadata.owner.email,
            },
            "description": metadata.description,
            "plugins": [],
        }

    def _build_codex_manifest(self, metadata: MarketplaceRegistryRootMetadataSavePayload) -> dict[str, Any]:
        return {
            "name": metadata.name,
            "description": metadata.description,
            "plugins": [],
        }

    def _merge_root_manifest(self, path: Path, metadata_manifest: dict[str, Any]) -> dict[str, Any]:
        current = self._read_json(path) if path.exists() else {}
        plugins = current.get("plugins") if isinstance(current.get("plugins"), list) else []
        return {
            **metadata_manifest,
            "plugins": plugins,
        }

    def _write_manifest_if_missing(self, path: Path, manifest: dict[str, Any]) -> None:
        if path.exists():
            return
        self._atomic_write_json(path, manifest)

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _atomic_write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def _claude_manifest_path(self, root: Path) -> Path:
        adapter = self._get_adapter("claude-code")
        return adapter.marketplace_manifest_path(root)  # type: ignore[attr-defined]

    def _codex_manifest_path(self, root: Path) -> Path:
        adapter = self._get_adapter("codex")
        return adapter.marketplace_manifest_path(root)  # type: ignore[attr-defined]

    def _get_adapter(self, provider: MarketplaceProvider) -> MarketplaceProviderAdapter:
        return self.adapters[provider]

    def _assert_relative_to(self, path: Path, root: Path) -> None:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise MarketplacePathError("marketplace.package.path_escape") from exc

    def _resolve_registry_git_path(self, root: Path, path: str) -> str:
        cleaned = path.strip().replace("\\", "/")
        if not cleaned or cleaned.startswith("/") or "\x00" in cleaned:
            raise MarketplacePathError("marketplace.package.path_escape")
        candidate = root / cleaned
        self._assert_relative_to(candidate, root)
        return str(Path(cleaned))

    def _require_registry_git_repo(self, root: Path) -> None:
        if not (root / ".git").exists():
            raise MarketplaceImportSourceError("marketplace.git.repository_not_initialized")

    def _git_identity_args(self, user_id: str) -> list[str]:
        identity = self.get_git_identity(user_id) or {}
        name = identity.get("name") or "Marketplace"
        email = identity.get("email") or "marketplace@example.local"
        return ["-c", f"user.name={name}", "-c", f"user.email={email}"]

    def _current_registry_branch(self, root: Path) -> str:
        branch = self._git_output(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        return branch if branch and branch != "HEAD" else "main"

    def _run_registry_remote_operation(
        self,
        user_id: str,
        args: list[str],
        message_key: str,
    ) -> MarketplaceRegistryGitOperationResult:
        root = self.get_registry_root(user_id)
        self._require_registry_git_repo(root)
        if not self._git_output(root, ["remote", "get-url", "origin"]):
            return MarketplaceRegistryGitOperationResult(
                success=False,
                message_key="marketplace.git.remote_required",
                error_code="marketplace.git.remote_required",
                repository=self.get_registry_repository_status(user_id),
            )
        try:
            self._run_git(root, args)
            self.invalidate_package_index(user_id)
            return MarketplaceRegistryGitOperationResult(
                success=True,
                message_key=message_key,
                repository=self.get_registry_repository_status(user_id),
            )
        except MarketplaceImportSourceError as exc:
            return MarketplaceRegistryGitOperationResult(
                success=False,
                message_key=exc.code,
                error_code=exc.code,
                repository=self.get_registry_repository_status(user_id),
            )

    def _registry_commit_summary(self, root: Path, commit_id: str) -> MarketplaceGitCommitSummary:
        metadata = self._git_output(root, ["show", "-s", "--format=%H%x1f%an%x1f%ae%x1f%cI%x1f%s", commit_id])
        parts = metadata.split("\x1f")
        numstat = self._git_output(root, ["show", "--numstat", "--format=", commit_id])
        additions = 0
        deletions = 0
        files_changed = 0
        for line in numstat.splitlines():
            columns = line.split("\t")
            if len(columns) < 3:
                continue
            files_changed += 1
            if columns[0].isdigit():
                additions += int(columns[0])
            if columns[1].isdigit():
                deletions += int(columns[1])
        return MarketplaceGitCommitSummary(
            id=parts[0] if parts else commit_id,
            author=parts[1] if len(parts) > 1 else "",
            email=parts[2] if len(parts) > 2 else "",
            timestamp=parts[3] if len(parts) > 3 else "",
            message=parts[4] if len(parts) > 4 else "",
            additions=additions,
            deletions=deletions,
            files_changed=files_changed,
        )

    def _untracked_registry_file_diff(self, root: Path, path: str) -> str:
        file_path = root / path
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Binary files /dev/null and b/{path} differ\n"
        return "".join(
            difflib.unified_diff(
                [],
                content.splitlines(keepends=True),
                fromfile="/dev/null",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
