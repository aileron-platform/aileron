"""Shared Marketplace workflow contracts, context, and process-wide locks."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from aileron_file_core import (
    FileLocator,
    PathExclusionPolicy,
    ResourceWriteLockManager,
)
from aileron_git_core import (
    GitOperationInProgressError,
    OperationKind,
    OperationManager,
)
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.modules.marketplace.cache import MarketplaceCache
from app.modules.marketplace.models import (
    MarketplacePackageSummary,
    MarketplaceProvider,
    MarketplaceValidationResult,
)
from app.modules.marketplace.providers import (
    MarketplaceProviderAdapter,
    create_marketplace_adapters,
)
from app.modules.marketplace.runtime_client import MarketplaceRuntimeClient
from app.modules.version_control.local_history import ManagerLocalHistoryService

if TYPE_CHECKING:
    from .kernel import _MarketplaceRegistrySupport

MARKETPLACE_FILE_MAX_WRITE_BYTES = 1024 * 1024 * 1024
_LOGGER = logging.getLogger(__name__)


class MarketplacePathError(ValueError):
    """Raised when a Marketplace path would leave its provider root."""


class MarketplaceConflictError(ValueError):
    """Raised when a package revision does not match current registry content."""


class MarketplaceValidationError(ValueError):
    """Raised when provider-native package validation blocks a mutation."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self.results = results
        first_code = (
            results[0]["code"]
            if results
            else "marketplace.validation.invalid_manifest_shape"
        )
        super().__init__(first_code)


@dataclass(frozen=True)
class MarketplacePublishedPackageResolution:
    """Provider CLI source resolved from the canonical published registry."""

    marketplace_id: str
    remote_url: str
    publish_ref: str


@dataclass(frozen=True)
class _MarketplacePackageCandidate:
    """Single-package data shared by targeted and registry summary reads."""

    summary: MarketplacePackageSummary
    operation_lifecycle_status: str
    manifest: dict[str, Any]
    validation_results: list[MarketplaceValidationResult]


class _MarketplaceMutationHooks:
    def __init__(
        self,
        *,
        service: _MarketplaceRegistrySupport,
        root: Path,
        registry_root: Path,
        local_history: ManagerLocalHistoryService,
        invalidation_key: str,
        package_targets: set[tuple[MarketplaceProvider, str]] | None = None,
    ) -> None:
        self.service = service
        self.root = root
        self.registry_root = registry_root
        self.local_history = local_history
        self.invalidation_key = invalidation_key
        self._package_targets = set(package_targets or ())

    @contextmanager
    def write_barrier(self, locator: FileLocator, operation: str) -> Iterator[None]:
        _ = locator
        try:
            try:
                with MARKETPLACE_GIT_OPERATION_MANAGER.acquire_file_write_barrier(
                    "marketplace:registry",
                    operation_name=operation,
                ):
                    yield
            except GitOperationInProgressError as exc:
                raise MarketplaceConflictError(
                    MARKETPLACE_GIT_OPERATION_IN_PROGRESS
                ) from exc
        finally:
            keys = [self.service.cache.registry_index_key()]
            keys.extend(
                self.service.cache.package_overview_key(provider, package_id)
                for provider, package_id in sorted(self._package_targets)
            )
            self.service.cache.delete(*keys)

    def check_quota(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def snapshot_existing(
        self,
        locator: FileLocator,
        absolute_path: Path,
        relative_path: str,
        operation: str,
    ) -> None:
        _ = (locator, relative_path)
        package_target = self.service._package_cache_target_for_path(absolute_path)
        if package_target is not None:
            self._package_targets.add(package_target)
        if not absolute_path.exists() or not absolute_path.is_file():
            return
        try:
            registry_relative = (
                absolute_path.resolve()
                .relative_to(self.registry_root.resolve())
                .as_posix()
            )
        except ValueError:
            return
        if _is_generated_marketplace_registry_path(registry_relative):
            return
        self.local_history.snapshot_file(
            domain="marketplace",
            resource_id="registry",
            source_path=absolute_path,
            relative_path=registry_relative,
            operation=operation,
        )

    def after_size_change(self, locator: FileLocator, delta_bytes: int) -> None:
        _ = (locator, delta_bytes)

    def validate_after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: list[str],
    ) -> None:
        _ = (locator, operation)
        registry_paths: list[str] = []
        for path in paths:
            try:
                registry_paths.append(
                    (self.root / path)
                    .resolve()
                    .relative_to(self.registry_root.resolve())
                    .as_posix()
                )
            except ValueError:
                continue
        self.service._validate_registry_paths_after_mutation(
            self.registry_root, registry_paths
        )

    def after_mutation(
        self,
        locator: FileLocator,
        operation: str,
        paths: list[str],
    ) -> None:
        _ = (locator, operation, paths)
        self.service._regenerate_publish_manifests_after_mutation(
            self.registry_root,
            invalidation_key=self.invalidation_key,
        )


def _is_generated_marketplace_registry_path(relative_path: str) -> bool:
    parts = Path(relative_path).parts
    return (
        relative_path
        in {
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
        }
        or ".git" in parts
        or ".marketplace" in parts
        or "__pycache__" in parts
    )


class MarketplaceImportSourceError(ValueError):
    """Raised when an import source fails safety validation."""

    def __init__(self, code: str, params: dict[str, Any] | None = None) -> None:
        self.code = code
        self.params = params or {}
        super().__init__(code)


MarketplaceValidationAction = Literal[
    "create", "save", "export", "install", "importCopy"
]

_resource_write_locks = ResourceWriteLockManager()
MARKETPLACE_GIT_OPERATION_IN_PROGRESS = "MARKETPLACE_GIT_OPERATION_IN_PROGRESS"
MARKETPLACE_GIT_OPERATION_MANAGER = OperationManager()
T = TypeVar("T")


def _registry_git_operation(
    kind: OperationKind,
    operation_name: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: run a registry method under the shared git-operation lock.

    Mirrors the KB ``_kb_git_operation`` decorator. The wrapped method runs as
    the ``callback`` of ``_run_registry_operation`` so non-READ ops gain stale
    on-disk lock recovery and conflict mapping to ``VersionControlError``.
    The first positional argument after ``self`` is treated as ``user_id``
    (the standard Marketplace registry-method signature).
    """

    def decorator(method: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(method)
        def wrapper(self: _MarketplaceRegistrySupport, *args: Any, **kwargs: Any) -> T:
            user_id = kwargs.get("user_id")
            if user_id is None and args:
                # Standard signature: (self, user_id, ...) -> args[0] is user_id.
                user_id = args[0]
            return self._run_registry_operation(
                user_id,
                kind=kind,
                operation_name=operation_name,
                callback=lambda: method(self, *args, **kwargs),
            )

        return wrapper

    return decorator


def _marketplace_path_exclusion() -> PathExclusionPolicy:
    return PathExclusionPolicy.defaults(extra_names={".marketplace"})


@dataclass
class _MarketplaceRegistryContext:
    """Mutable infrastructure shared by one Marketplace workflow graph."""

    settings: Any
    db: Session | None
    storage_root: Path
    local_history: ManagerLocalHistoryService
    adapters: dict[MarketplaceProvider, MarketplaceProviderAdapter]
    marketplace_runtime_client: MarketplaceRuntimeClient
    cache: MarketplaceCache
    _generating_publish_manifests: bool
    _stale_threshold: int

    @classmethod
    def create(cls, db: Session | None = None) -> _MarketplaceRegistryContext:
        settings = get_settings()
        return cls(
            settings=settings,
            db=db,
            storage_root=Path(settings.MARKETPLACE_STORAGE_PATH),
            local_history=ManagerLocalHistoryService(
                history_root=Path(settings.MANAGER_LOCAL_HISTORY_DIR)
            ),
            adapters=create_marketplace_adapters(),
            marketplace_runtime_client=MarketplaceRuntimeClient(),
            cache=MarketplaceCache(settings.REDIS_URL),
            _generating_publish_manifests=False,
            _stale_threshold=settings.GIT_STALE_LOCK_THRESHOLD_SECONDS,
        )
