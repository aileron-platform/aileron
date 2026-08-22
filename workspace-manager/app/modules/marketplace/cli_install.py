"""Coordinate one managed Marketplace plugin CLI installation."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.modules.marketplace.activity_repository import (
    MarketplaceActivityRepository,
)
from app.modules.marketplace.models import (
    MarketplaceActivityStatus,
    MarketplacePackageFormat,
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
    MarketplaceTargetClient,
)
from app.modules.marketplace.runtime_client import (
    MarketplaceRuntimeClient,
    MarketplaceRuntimeClientError,
)
from app.modules.workspace.access_repository import WorkspaceAccessRepository

_LOGGER = logging.getLogger(__name__)


class MarketplaceManagedPackage(Protocol):
    """Managed Registry fields consumed by the CLI installation workflow."""

    marketplace_id: str
    remote_url: str
    registry_ref: str


class MarketplaceInstallationPublisher(Protocol):
    """Narrow managed-package resolution seam required by CLI installation."""

    def resolve_managed_package_for_install(
        self,
        user_id: str,
        target_client: MarketplaceTargetClient,
        package_format: MarketplacePackageFormat,
        package_id: str,
        version: str,
    ) -> MarketplaceManagedPackage: ...

    def resolve_install_runtime(self, workspace_id: str) -> dict[str, str | None]: ...


class MarketplaceCliInstallError(RuntimeError):
    """Raised when Aileron cannot reach the target_client CLI installation stage."""

    def __init__(self, code: str, *, http_status: int = 400) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(code)


class _KeyedInstallMutex:
    """Serialize one workspace/target_client mutation without durable state."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._entries: dict[tuple[str, str, str], tuple[threading.Lock, int]] = {}

    @contextmanager
    def acquire(
        self,
        workspace_id: str,
        target_client: str,
        catalog_plugin_id: str,
    ) -> Iterator[None]:
        key = (workspace_id, target_client, catalog_plugin_id)
        with self._guard:
            lock, users = self._entries.get(key, (threading.Lock(), 0))
            self._entries[key] = (lock, users + 1)
        if not lock.acquire(blocking=False):
            with self._guard:
                current_lock, current_users = self._entries[key]
                if current_users == 1:
                    del self._entries[key]
                else:
                    self._entries[key] = (current_lock, current_users - 1)
            raise MarketplaceCliInstallError(
                "marketplace.install.operation-in-progress",
                http_status=409,
            )
        try:
            yield
        finally:
            lock.release()
            with self._guard:
                current_lock, current_users = self._entries[key]
                if current_users == 1:
                    del self._entries[key]
                else:
                    self._entries[key] = (current_lock, current_users - 1)


_INSTALL_MUTEX = _KeyedInstallMutex()


class MarketplaceCliInstallService:
    """Resolve a managed package and return one target_client CLI terminal result."""

    def __init__(
        self,
        db: Session,
        publisher: MarketplaceInstallationPublisher,
        *,
        runtime_client: MarketplaceRuntimeClient | None = None,
        activity_repository: MarketplaceActivityRepository | None = None,
        workspace_access: WorkspaceAccessRepository | None = None,
        operation_id_factory: Callable[[], str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.db = db
        self.publisher = publisher
        self.runtime_client = runtime_client or MarketplaceRuntimeClient()
        self.activity_repository = activity_repository or MarketplaceActivityRepository(
            db
        )
        self.workspace_access = workspace_access or WorkspaceAccessRepository(db)
        self.operation_id_factory = operation_id_factory or (lambda: uuid4().hex)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def install(
        self,
        user_id: str,
        request: MarketplacePluginInstallRequest,
    ) -> MarketplacePluginCommandResult:
        """Resolve and install once without mutating the canonical registry."""

        operation_id = self.operation_id_factory()
        marketplace_id: str | None = None
        try:
            self._require_workspace_mutator(
                workspace_id=request.workspace_id,
                user_id=user_id,
            )
            managed_package = self.publisher.resolve_managed_package_for_install(
                user_id,
                request.target_client,
                request.package_format,
                request.package_id,
                request.version,
            )
            marketplace_id = managed_package.marketplace_id
            remote_url = managed_package.remote_url
            registry_ref = managed_package.registry_ref
            catalog_plugin_id = f"{marketplace_id}/{request.package_id}"
            with _INSTALL_MUTEX.acquire(
                request.workspace_id,
                request.target_client,
                catalog_plugin_id,
            ):
                runtime_url, runtime_instance_id = self._resolve_runtime(
                    request.workspace_id
                )
                payload = {
                    "operationId": operation_id,
                    "targetClient": request.target_client,
                    "packageId": request.package_id,
                    "marketplaceId": marketplace_id,
                    "remoteUrl": remote_url,
                    "registryRef": registry_ref,
                    "workspaceId": request.workspace_id,
                    "runtimeInstanceId": runtime_instance_id,
                }
                raw_result = self.runtime_client.install_plugin(
                    runtime_url=runtime_url,
                    workspace_id=request.workspace_id,
                    runtime_instance_id=runtime_instance_id,
                    payload=payload,
                )
                result = self._validate_runtime_result(raw_result, payload)
        except Exception as exc:
            self._append_activity(
                actor_user_id=user_id,
                request=request,
                operation_id=operation_id,
                marketplace_id=marketplace_id,
                status="failed",
                error_code=self._error_code(exc),
            )
            raise

        self._append_activity(
            actor_user_id=user_id,
            request=request,
            operation_id=operation_id,
            marketplace_id=marketplace_id,
            status="succeeded" if result.status == "installed" else "failed",
            error_code=(
                None
                if result.status == "installed"
                else "marketplace.install.cli_failed"
            ),
            result=result,
        )
        if result.status == "installed" and not self._last_activity_persisted:
            result = result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        "marketplace.install.audit-persistence-failed",
                    ]
                }
            )
        return result

    def _resolve_runtime(self, workspace_id: str) -> tuple[str, str]:
        raw = self.publisher.resolve_install_runtime(workspace_id)
        error_code = raw.get("errorCode")
        runtime_url = raw.get("runtimeUrl")
        runtime_instance_id = raw.get("runtimeInstanceId")
        if isinstance(error_code, str) and error_code:
            http_status = 404 if error_code.endswith("workspace_not_found") else 503
            raise MarketplaceCliInstallError(error_code, http_status=http_status)
        if (
            not isinstance(runtime_url, str)
            or not runtime_url
            or not isinstance(runtime_instance_id, str)
            or not runtime_instance_id
        ):
            raise MarketplaceCliInstallError(
                "marketplace.install.runtime_unavailable",
                http_status=503,
            )
        return runtime_url.rstrip("/"), runtime_instance_id

    @staticmethod
    def _validate_runtime_result(
        raw_result: dict[str, Any],
        expected: dict[str, str],
    ) -> MarketplacePluginCommandResult:
        try:
            result = MarketplacePluginCommandResult.model_validate(raw_result)
        except ValidationError as exc:
            raise MarketplaceRuntimeClientError(
                "marketplace.install.runtime_contract_invalid"
            ) from exc
        identity_fields = (
            ("operationId", result.operation_id),
            ("targetClient", result.target_client),
            ("packageId", result.package_id),
            ("marketplaceId", result.marketplace_id),
            ("workspaceId", result.workspace_id),
        )
        if any(expected[key] != value for key, value in identity_fields):
            raise MarketplaceRuntimeClientError(
                "marketplace.install.runtime_contract_invalid"
            )
        return result

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
            raise MarketplaceCliInstallError(
                "marketplace.workspace.access_denied",
                http_status=403,
            )

    def _append_activity(
        self,
        *,
        actor_user_id: str,
        request: MarketplacePluginInstallRequest,
        operation_id: str,
        marketplace_id: str | None,
        status: MarketplaceActivityStatus,
        error_code: str | None,
        result: MarketplacePluginCommandResult | None = None,
    ) -> None:
        self._last_activity_persisted = False
        for attempt in range(3):
            try:
                self.activity_repository.append(
                    actor_user_id=actor_user_id,
                    action="install",
                    status=status,
                    package_format=request.package_format,
                    target_client=request.target_client,
                    package_id=request.package_id,
                    operation_id=operation_id,
                    workspace_id=request.workspace_id,
                    marketplace_id=marketplace_id,
                    error_code=error_code,
                    commands=() if result is None else result.commands,
                    now=self.now(),
                )
                self.db.commit()
                self._last_activity_persisted = True
                return
            except Exception:
                self.db.rollback()
                _LOGGER.exception(
                    "Failed to append Marketplace CLI install activity (attempt %s)",
                    attempt + 1,
                )

    @staticmethod
    def _error_code(exc: Exception) -> str:
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code:
            return code
        message = str(exc)
        if message.startswith("marketplace."):
            return message
        return "marketplace.install.failed"
