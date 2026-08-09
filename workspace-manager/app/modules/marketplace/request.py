"""Marketplace request interface owning authorization and workflow dispatch."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import Any

from aileron_file_core import FileCoreError
from aileron_git_core import VersionControlError
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.api_error import authorization_error_detail
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.marketplace.user_copy import MarketplaceUserCopyError
from app.modules.marketplace.workflows.imports import MarketplaceImportWorkflow
from app.modules.marketplace.workflows.installation import (
    MarketplaceInstallationWorkflow,
)
from app.modules.marketplace.workflows.package_mutations import (
    MarketplacePackageMutationWorkflow,
)
from app.modules.marketplace.workflows.package_reads import MarketplacePackageReadModel
from app.modules.marketplace.workflows.registry_git import (
    MarketplaceRegistryGitWorkflow,
)
from app.modules.marketplace.workflows.registry_operations import (
    MARKETPLACE_GIT_OPERATION_IN_PROGRESS,
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplacePathError,
    MarketplaceValidationError,
    _MarketplaceRegistryContext,
)
from app.modules.marketplace.workflows.settings_activity import (
    MarketplaceSettingsActivityWorkflow,
)
from app.modules.version_control.application import version_control_error_envelope
from app.modules.version_control.remote import VersionControlRemoteError

MARKETPLACE_OPERATION_IDS = MappingProxyType(
    {
        "list_packages": OperationId.MARKETPLACE_CATALOG_READ,
        "refresh_package_index": OperationId.MARKETPLACE_CATALOG_READ,
        "refresh_package_overview": OperationId.MARKETPLACE_CATALOG_READ,
        "get_package_operation_summary": OperationId.MARKETPLACE_CATALOG_READ,
        "get_package_detail": OperationId.MARKETPLACE_CATALOG_READ,
        "load_root_document": OperationId.MARKETPLACE_CATALOG_READ,
        "list_documents": OperationId.MARKETPLACE_CATALOG_READ,
        "load_document": OperationId.MARKETPLACE_CATALOG_READ,
        "list_mcp_servers": OperationId.MARKETPLACE_CATALOG_READ,
        "get_mcp_server": OperationId.MARKETPLACE_CATALOG_READ,
        "get_basic_metadata": OperationId.MARKETPLACE_CATALOG_READ,
        "get_hooks": OperationId.MARKETPLACE_CATALOG_READ,
        "get_readme": OperationId.MARKETPLACE_CATALOG_READ,
        "list_skill_files": OperationId.MARKETPLACE_CATALOG_READ,
        "read_skill_file": OperationId.MARKETPLACE_CATALOG_READ,
        "list_package_files_tree": OperationId.MARKETPLACE_CATALOG_READ,
        "read_package_file": OperationId.MARKETPLACE_CATALOG_READ,
        "export_package": OperationId.MARKETPLACE_CATALOG_READ,
        "get_settings": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "list_activity": OperationId.MARKETPLACE_CATALOG_READ,
        "list_registry_file_history": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_repository_status": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "remote_branches": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "list_branches": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_changes": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_changes_numstat": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_status": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_file_diff": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_commit_file_diff": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_commit_files": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "list_registry_commits": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_operation_status": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_lfs_patterns": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_remote_settings": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "create_package": OperationId.MARKETPLACE_CONTENT_PUBLISH,
        "save_root_document": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "create_document": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "update_document": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "move_document": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "remove_document": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "create_mcp_server": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "update_basic_metadata": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "save_package": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "update_hooks": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "write_skill_file": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "preflight_skill_file_conflicts": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "upload_skill_streams": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "extract_skill_archive": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "create_skill_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "delete_skill_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "move_skill_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "write_package_file": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "preflight_package_file_conflicts": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "upload_package_files": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "paste_package_files": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "extract_package_archive": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "create_package_file_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "delete_package_file_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "move_package_file_entry": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "save_mcp_server": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "delete_mcp_server": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "scan_import_source": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "import_candidates": OperationId.MARKETPLACE_CONTENT_PUBLISH,
        "validate_import_source": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "save_uploaded_import_source": OperationId.MARKETPLACE_CONTENT_PUBLISH,
        "record_activity": OperationId.MARKETPLACE_CONTENT_MANAGE,
        "delete_package": OperationId.MARKETPLACE_DELETE_EXECUTE,
        "discard_draft_package": OperationId.MARKETPLACE_DELETE_EXECUTE,
        "preflight_user_copy": OperationId.MARKETPLACE_USER_COPY_MANAGE,
        "apply_user_copy": OperationId.MARKETPLACE_USER_COPY_MANAGE,
        "resolve_published_package_for_install": OperationId.MARKETPLACE_INSTALL_EXECUTE,
        "resolve_install_runtime": OperationId.MARKETPLACE_INSTALL_EXECUTE,
        "initialize_registry": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "save_settings": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "restore_registry_file_history": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "initialize_git_repository": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "clone_registry": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "set_registry_remote": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "create_branch_and_switch": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "switch_branch": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "rename_branch": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "delete_branch": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "publish_branch": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "mark_conflicts_resolved": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "abort_conflict": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "revert_commit": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "update_lfs_patterns": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "preview_lfs_snapshot": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "convert_lfs_snapshot": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "cancel_operation": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "stage_registry_paths": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "unstage_registry_paths": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "discard_registry_paths": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "get_registry_blob": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "commit_registry_changes": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "fetch_registry": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "pull_registry": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "push_registry": OperationId.MARKETPLACE_REGISTRY_MANAGE,
        "force_unlock": OperationId.MARKETPLACE_REGISTRY_MANAGE,
    }
)


class MarketplaceRequest:
    """Small request seam over the internal Marketplace workflow graph."""

    def __init__(
        self,
        db: Session | None,
        *,
        request: Request | None = None,
        actor: AuthorizationActor | None = None,
    ) -> None:
        context = _MarketplaceRegistryContext.create(db)
        package_reads = MarketplacePackageReadModel(_context=context)
        settings_activity = MarketplaceSettingsActivityWorkflow(_context=context)
        self._db = db
        self._request = request
        self._actor = actor
        self._owners = (
            package_reads,
            MarketplacePackageMutationWorkflow(
                context=context,
                package_reads=package_reads,
                settings_activity=settings_activity,
            ),
            MarketplaceImportWorkflow(
                context=context,
                package_reads=package_reads,
                settings_activity=settings_activity,
            ),
            settings_activity,
            MarketplaceRegistryGitWorkflow(
                context=context,
                settings_activity=settings_activity,
            ),
            MarketplaceInstallationWorkflow(
                context=context,
                package_reads=package_reads,
                settings_activity=settings_activity,
            ),
        )
        self._operations = self._index_operations()

    @classmethod
    def create(
        cls,
        db: Session | None = None,
        *,
        request: Request | None = None,
        actor: AuthorizationActor | None = None,
    ) -> MarketplaceRequest:
        return cls(db, request=request, actor=actor)

    def execute(self, operation: str, /, *args: Any, **kwargs: Any) -> Any:
        """Authorize, dispatch, and translate one Marketplace operation."""

        target = self._operations.get(operation)
        if target is None:
            raise AttributeError(f"Marketplace operation is not available: {operation}")
        self._require_operation(operation)
        try:
            return target(*args, **kwargs)
        except HTTPException:
            raise
        except MarketplaceUserCopyError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail=self._error_detail(exc.code),
            ) from exc
        except MarketplaceImportSourceError as exc:
            status_code = (
                status.HTTP_409_CONFLICT
                if exc.code == MARKETPLACE_GIT_OPERATION_IN_PROGRESS
                else status.HTTP_400_BAD_REQUEST
            )
            raise HTTPException(
                status_code=status_code,
                detail={
                    "errorCode": exc.code,
                    "message": self._translate(exc.code, **exc.params),
                },
            ) from exc
        except VersionControlRemoteError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": exc.code,
                    "message": self._translate(exc.code),
                },
            ) from exc
        except VersionControlError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=version_control_error_envelope(exc),
            ) from exc
        except FileCoreError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail={
                    "errorCode": exc.code,
                    "message": self._translate(exc.code),
                },
            ) from exc
        except MarketplaceValidationError as exc:
            first = exc.results[0] if exc.results else {"code": str(exc)}
            code = str(first.get("messageKey") or first.get("code"))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "errorCode": first.get("code"),
                    "message": self._translate(code),
                    "validationResults": exc.results,
                },
            ) from exc
        except MarketplaceConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=self._error_detail(str(exc)),
            ) from exc
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=self._error_detail(str(exc)),
            ) from exc
        except (MarketplacePathError, FileExistsError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=self._error_detail(str(exc)),
            ) from exc

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        """Route existing endpoint calls through the single request interface."""

        if operation.startswith("_") or operation not in self._operations:
            raise AttributeError(operation)

        def dispatch(*args: Any, **kwargs: Any) -> Any:
            return self.execute(operation, *args, **kwargs)

        return dispatch

    def _index_operations(self) -> dict[str, Callable[..., Any]]:
        operations: dict[str, Callable[..., Any]] = {}
        for owner in self._owners:
            for name in dir(owner):
                if name.startswith("_"):
                    continue
                candidate = getattr(owner, name)
                if not callable(candidate):
                    continue
                if name in operations:
                    raise RuntimeError(
                        f"Marketplace operation has multiple owners: {name}"
                    )
                operations[name] = candidate
        return operations

    def _require_operation(self, operation: str) -> None:
        request = self._request
        if request is None or not getattr(request.state, "auth_enabled", False):
            return
        if self._db is None:
            raise RuntimeError("Marketplace authorization requires a database session")
        operation_id = MARKETPLACE_OPERATION_IDS.get(operation)
        if operation_id is None:
            raise RuntimeError(
                f"Marketplace operation has no authorization mapping: {operation}"
            )
        if self._actor is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=authorization_error_detail(
                    "PLATFORM_AUTHORIZATION_DENIED",
                    self._translate("auth.unauthenticated"),
                ),
            )
        try:
            AuthorizationOperationPolicy(self._db).require_platform_operation(
                self._actor,
                operation_id,
            )
        except AuthorizationOperationError as exc:
            raise HTTPException(
                status_code=exc.http_status,
                detail=authorization_error_detail(
                    exc.error_code,
                    self._translate("marketplace.permission.denied"),
                ),
            ) from exc

    def _error_detail(self, key: str) -> str:
        return self._translate(key)

    def _translate(self, key: str, **params: Any) -> str:
        request = self._request
        translate = getattr(request.state, "translate", None) if request else None
        return translate(key, **params) if translate else key
