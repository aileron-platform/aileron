"""Composed private kernel for Marketplace workflow modules."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from aileron_file_core import (
    FileOperationEngine,
    FilePolicy,
    RootedFileAdapter,
    StaticRootResolver,
)
from sqlalchemy.orm import Session

from app.modules.marketplace.models import MarketplaceProvider
from app.modules.marketplace.providers import MarketplaceProviderAdapter

from .catalog_queries import _MarketplaceCatalogSupport
from .package_git import _MarketplaceGitSupport
from .import_application import _MarketplaceImportApplySupport
from .import_planning import _MarketplaceImportPlanningSupport
from .import_sources import _MarketplaceImportSourceSupport
from .resource_files import _MarketplaceResourceSupport
from .registry_operations import (
    MARKETPLACE_FILE_MAX_WRITE_BYTES,
    MarketplacePathError,
    _marketplace_path_exclusion,
    _MarketplaceMutationHooks,
    _MarketplaceRegistryContext,
    _resource_write_locks,
)
from .package_validation import _MarketplaceValidationSupport

__all__ = ["_MarketplaceRegistrySupport"]


class _MarketplaceRegistrySupport(
    _MarketplaceResourceSupport,
    _MarketplaceValidationSupport,
    _MarketplaceImportPlanningSupport,
    _MarketplaceImportApplySupport,
    _MarketplaceImportSourceSupport,
    _MarketplaceGitSupport,
    _MarketplaceCatalogSupport,
):
    """Private filesystem, cache, validation, and Git implementation kernel."""

    _registry_lock = threading.RLock()
    _package_id_pattern = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
    _git_scp_like_pattern = re.compile(
        r"^(?P<user>[A-Za-z0-9_.-]+)@(?P<host>[A-Za-z0-9_.-]+):(?P<path>.+)$"
    )
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
    _managed_package_roots = {
        "commands",
        "agents",
        "output-styles",
        "policies",
        "skills",
        ".codex-plugin",
        ".claude-plugin",
        ".mcp.json",
        "mcp.json",
        "hooks",
        "AGENTS.md",
        "CLAUDE.md",
    }

    _context_state_fields = frozenset(
        [
            "_generating_publish_manifests",
            "_stale_threshold",
            "adapters",
            "cache",
            "db",
            "local_history",
            "marketplace_runtime_client",
            "settings",
            "storage_root",
        ]
    )

    def __init__(
        self,
        db: Session | None = None,
        *,
        _context: _MarketplaceRegistryContext | None = None,
    ) -> None:
        object.__setattr__(
            self,
            "_context",
            _context or _MarketplaceRegistryContext.create(db),
        )

    def __getattr__(self, name: str) -> Any:
        if name in self._context_state_fields:
            return getattr(self._context, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name != "_context" and name in self._context_state_fields:
            setattr(self._context, name, value)
            return
        object.__setattr__(self, name, value)

    def _get_registry_root(self, user_id: str) -> Path:
        """Return the system-managed shared registry root."""
        return self.storage_root / "registry"

    def _file_engine_for_root(
        self,
        *,
        root: Path,
        registry_root: Path,
        invalidation_key: str = "registry",
        package_targets: set[tuple[MarketplaceProvider, str]] | None = None,
    ) -> FileOperationEngine:
        path_exclusion = _marketplace_path_exclusion()
        resolved_package_targets = set(package_targets or ())
        root_package_target = self._package_cache_target_for_path(root)
        if root_package_target is not None:
            resolved_package_targets.add(root_package_target)
        return FileOperationEngine(
            adapter=RootedFileAdapter(
                root_resolver=StaticRootResolver(root),
                path_exclusion=path_exclusion,
            ),
            policy=FilePolicy(
                max_read_bytes=1024 * 1024,
                max_write_bytes=MARKETPLACE_FILE_MAX_WRITE_BYTES,
                max_extract_entries=10000,
                max_extract_entry_bytes=MARKETPLACE_FILE_MAX_WRITE_BYTES,
                max_extract_total_bytes=MARKETPLACE_FILE_MAX_WRITE_BYTES,
                path_exclusion=path_exclusion,
            ),
            hooks=_MarketplaceMutationHooks(
                service=self,
                root=root,
                registry_root=registry_root,
                local_history=self.local_history,
                invalidation_key=invalidation_key,
                package_targets=resolved_package_targets,
            ),
            write_locks=_resource_write_locks,
        )

    def _package_cache_target_for_path(
        self,
        path: Path,
    ) -> tuple[MarketplaceProvider, str] | None:
        try:
            parts = (
                path.resolve()
                .relative_to((self.storage_root / "registry").resolve())
                .parts
            )
        except ValueError:
            return None
        if len(parts) < 3 or parts[0] not in self.adapters or parts[1] != "plugins":
            return None
        return parts[0], parts[2]  # type: ignore[return-value]

    def _marketplace_package_lock_key(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> tuple[str, MarketplaceProvider, str]:
        _ = user_id
        return ("marketplace", provider, package_id)

    @contextmanager
    def _package_source_lock(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> Iterator[None]:
        """Hold the package mutation lock while creating an immutable source view."""

        with _resource_write_locks.lock(
            self._marketplace_package_lock_key(user_id, provider, package_id)
        ):
            yield

    def _invalidate_package_index(self, user_id: str) -> None:
        """Invalidate every read model backed by the shared registry."""
        _ = user_id
        self.cache.delete(self.cache.registry_index_key())
        self.cache.delete_pattern(self.cache.package_overview_pattern())

    def _invalidate_package_overview(
        self,
        user_id: str,
        provider: MarketplaceProvider,
        package_id: str,
    ) -> None:
        """Invalidate one shared package overview and its registry index."""
        _ = user_id
        self.cache.delete(
            self.cache.registry_index_key(),
            self.cache.package_overview_key(provider, package_id),
        )

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _get_adapter(self, provider: MarketplaceProvider) -> MarketplaceProviderAdapter:
        return self.adapters[provider]

    def _assert_relative_to(self, path: Path, root: Path) -> None:
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError as exc:
            raise MarketplacePathError("marketplace.package.path_escape") from exc
