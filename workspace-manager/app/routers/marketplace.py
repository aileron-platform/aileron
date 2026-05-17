"""Marketplace routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.openapi import build_responses
from app.db.database import get_db
from app.models import (
    MarketplaceActivityListResult,
    MarketplaceCliPreflightResult,
    MarketplaceImportCandidate,
    MarketplaceImportRequest,
    MarketplaceImportResult,
    MarketplaceImportSource,
    MarketplaceImportUploadResult,
    MarketplaceInstallRequest,
    MarketplaceInstallResult,
    MarketplaceGitCommitListResult,
    MarketplaceGitCommitFilesResult,
    MarketplaceGitCommitRequest,
    MarketplaceGitCommitResult,
    MarketplaceGitDiffResponse,
    MarketplaceGitPathRequest,
    MarketplaceGitStatus,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageDeleteResult,
    MarketplacePackageDetail,
    MarketplacePackageListResult,
    MarketplacePackageSaveRequest,
    MarketplacePackageSaveResult,
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
from app.modules.auth.auth_decorators import get_user_permissions, has_permission, load_role_mapping
from app.modules.auth import get_current_user_id
from app.services.marketplace_service import (
    MarketplaceConflictError,
    MarketplaceImportSourceError,
    MarketplacePathError,
    MarketplaceService,
    MarketplaceValidationError,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

MARKETPLACE_VIEW_PERMISSION = "marketplace:view"
MARKETPLACE_EDIT_PERMISSION = "marketplace:edit"
MARKETPLACE_DELETE_PERMISSION = "marketplace:delete"
MARKETPLACE_IMPORT_PERMISSION = "marketplace:import"
MARKETPLACE_INSTALL_PERMISSION = "marketplace:install"
MARKETPLACE_REGISTRY_MANAGE_PERMISSION = "marketplace:manage_registry"


def get_marketplace_service(db: Session = Depends(get_db)) -> MarketplaceService:
    """Get Marketplace service instance."""
    return MarketplaceService(db)


def get_marketplace_user_id(request: Request) -> str:
    """Resolve Marketplace user scope."""
    try:
        user_id = get_current_user_id(request)
        return user_id or "local-user"
    except HTTPException:
        if getattr(request.state, "auth_enabled", False):
            raise
    return "local-user"


def _validate_provider(provider: str, request: Request) -> None:
    if provider not in {"claude-code", "codex", "gemini"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=request.state.translate("marketplace.provider.invalid"),
        )


def _translate_error(request: Request, key: str) -> str:
    translate = getattr(request.state, "translate", None)
    return translate(key) if translate else key


def _raise_unsupported_git_operation(request: Request, key: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": key, "message": _translate_error(request, key)},
    )


def _extract_current_user_roles(current_user: object) -> list[str]:
    if not isinstance(current_user, dict):
        return []

    roles: list[str] = []
    direct_roles = current_user.get("roles") or []
    if isinstance(direct_roles, list):
        roles.extend(role for role in direct_roles if isinstance(role, str))

    realm_roles = (current_user.get("realm_access") or {}).get("roles", [])
    if isinstance(realm_roles, list):
        roles.extend(role for role in realm_roles if isinstance(role, str))

    resource_access = current_user.get("resource_access") or {}
    if isinstance(resource_access, dict):
        for access in resource_access.values():
            if isinstance(access, dict) and isinstance(access.get("roles"), list):
                roles.extend(role for role in access["roles"] if isinstance(role, str))

    groups = current_user.get("groups") or []
    if isinstance(groups, list):
        group_mappings = (load_role_mapping().get("group_mappings") or {})
        if isinstance(group_mappings, dict):
            for group in groups:
                if not isinstance(group, str):
                    continue
                mapped = group_mappings.get(group)
                if isinstance(mapped, dict) and isinstance(mapped.get("role"), str):
                    roles.append(mapped["role"])

    return list(dict.fromkeys(roles))


def _extract_current_user_permissions(current_user: object) -> list[str]:
    if not isinstance(current_user, dict):
        return []
    permissions: list[str] = []

    direct_permissions = current_user.get("permissions") or []
    if isinstance(direct_permissions, list):
        permissions.extend(permission for permission in direct_permissions if isinstance(permission, str))
        for permission in direct_permissions:
            if isinstance(permission, dict):
                permissions.extend(_extract_keycloak_authorization_permission(permission))

    authorization = current_user.get("authorization") or {}
    if isinstance(authorization, dict):
        authorization_permissions = authorization.get("permissions") or []
        if isinstance(authorization_permissions, list):
            for permission in authorization_permissions:
                if isinstance(permission, str):
                    permissions.append(permission)
                elif isinstance(permission, dict):
                    permissions.extend(_extract_keycloak_authorization_permission(permission))

    for claim in ("scope", "scp"):
        scope_value = current_user.get(claim)
        if isinstance(scope_value, str):
            permissions.extend(item for item in scope_value.split() if item)
        elif isinstance(scope_value, list):
            permissions.extend(item for item in scope_value if isinstance(item, str))

    return list(dict.fromkeys(permissions))


def _extract_keycloak_authorization_permission(permission: dict[str, object]) -> list[str]:
    resource = permission.get("rsname") or permission.get("resource") or permission.get("resource_name")
    scopes = permission.get("scopes") or permission.get("scope")
    if not isinstance(resource, str):
        return []
    if isinstance(scopes, str):
        scope_items = [scopes]
    elif isinstance(scopes, list):
        scope_items = [scope for scope in scopes if isinstance(scope, str)]
    else:
        scope_items = []
    return [
        f"{resource}:{scope}"
        for scope in scope_items
        if resource == "marketplace" and scope
    ]


def _marketplace_permission_aliases(permission: str) -> set[str]:
    aliases = {permission}
    if permission.startswith("marketplace:"):
        aliases.add(permission.replace("marketplace:", "marketplace.", 1))
    if permission.startswith("marketplace."):
        aliases.add(permission.replace("marketplace.", "marketplace:", 1))
    return aliases


def _require_marketplace_permission(request: Request, permission: str) -> None:
    if not getattr(request.state, "auth_enabled", False):
        return
    if getattr(request.state, "internal_authenticated", False):
        return
    current_user = getattr(request.state, "current_user", None) or {}
    permissions = [
        *get_user_permissions(_extract_current_user_roles(current_user)),
        *_extract_current_user_permissions(current_user),
    ]
    if any(has_permission(alias, permissions) for alias in _marketplace_permission_aliases(permission)):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=_translate_error(request, "marketplace.permission.denied"),
    )


def _validation_error_detail(request: Request, exc: MarketplaceValidationError) -> dict[str, object]:
    first = exc.results[0] if exc.results else {"code": str(exc)}
    code = str(first.get("messageKey") or first.get("code"))
    return {
        "code": first.get("code"),
        "message": _translate_error(request, code),
        "validationResults": exc.results,
    }


@router.get(
    "/packages",
    response_model=MarketplacePackageListResult,
    summary="List Marketplace packages",
    responses=build_responses(401, 500),
)
def list_marketplace_packages(
    request: Request,
    provider: str | None = Query(default=None),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    features: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, alias="pageSize", ge=1, le=100),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageListResult:
    """List current user's Marketplace packages."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    if provider:
        _validate_provider(provider, request)
    return service.list_packages(
        current_user_id,
        provider=provider,  # type: ignore[arg-type]
        q=q,
        category=category,
        features=[feature for feature in (features or "").split(",") if feature],
        page=page,
        page_size=page_size,
    )


@router.post(
    "/packages/refresh",
    response_model=MarketplacePackageListResult,
    summary="Refresh Marketplace package index",
    responses=build_responses(401, 500),
)
def refresh_marketplace_packages(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageListResult:
    """Force current user's Marketplace package index to rescan registry files."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.refresh_package_index(current_user_id)


@router.post(
    "/packages",
    response_model=MarketplacePackageDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create Marketplace package",
    responses=build_responses(400, 401, 409, 500),
)
def create_marketplace_package(
    payload: MarketplacePackageCreateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageDetail:
    """Create a provider-native Marketplace package scaffold."""
    _require_marketplace_permission(request, MARKETPLACE_EDIT_PERMISSION)
    try:
        return service.create_package(current_user_id, payload)
    except MarketplacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except FileExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_error_detail(request, exc),
        ) from exc


@router.get(
    "/packages/{provider}/{package_id}",
    response_model=MarketplacePackageDetail,
    summary="Get Marketplace package detail",
    responses=build_responses(400, 401, 404, 500),
)
def get_marketplace_package_detail(
    provider: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageDetail:
    """Get a provider-native Marketplace package detail."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    _validate_provider(provider, request)
    detail = service.get_package_detail(current_user_id, provider, package_id)  # type: ignore[arg-type]
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("marketplace.package.not_found"),
        )
    return detail


@router.put(
    "/packages/{provider}/{package_id}",
    response_model=MarketplacePackageSaveResult,
    summary="Save Marketplace package",
    responses=build_responses(400, 401, 404, 409, 500),
)
def save_marketplace_package(
    provider: str,
    package_id: str,
    payload: MarketplacePackageSaveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageSaveResult:
    """Save a provider-native Marketplace package."""
    _require_marketplace_permission(request, MARKETPLACE_EDIT_PERMISSION)
    _validate_provider(provider, request)
    if payload.provider != provider or payload.package_id != package_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, "marketplace.package.identity_mismatch"),
        )
    try:
        return service.save_package(current_user_id, payload)
    except MarketplacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_error_detail(request, exc),
        ) from exc


@router.delete(
    "/packages/{provider}/{package_id}",
    response_model=MarketplacePackageDeleteResult,
    summary="Delete Marketplace package",
    responses=build_responses(400, 401, 404, 409, 500),
)
def delete_marketplace_package(
    provider: str,
    package_id: str,
    request: Request,
    revision: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplacePackageDeleteResult:
    """Hard delete a Marketplace package."""
    _require_marketplace_permission(request, MARKETPLACE_DELETE_PERMISSION)
    _validate_provider(provider, request)
    result = service.delete_package(
        current_user_id,
        MarketplacePackageDeleteRequest(
            provider=provider,  # type: ignore[arg-type]
            package_id=package_id,
            revision=revision,
        ),
    )
    if not result.deleted and result.error_code == "marketplace.package.revision_conflict":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_error(request, result.error_code),
        )
    if not result.deleted and result.error_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, result.error_code),
        )
    return result


@router.get(
    "/packages/{provider}/{package_id}/export",
    summary="Export Marketplace package",
    responses=build_responses(400, 401, 404, 500),
)
def export_marketplace_package(
    provider: str,
    package_id: str,
    request: Request,
    revision: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> Response:
    """Export a provider-native Marketplace package zip."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    _validate_provider(provider, request)
    try:
        archive = service.export_package(current_user_id, provider, package_id, revision)  # type: ignore[arg-type]
    except MarketplacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_error_detail(request, exc),
        ) from exc
    filename = f"{provider}-{package_id}.zip"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/activity",
    response_model=MarketplaceActivityListResult,
    summary="List Marketplace activity records",
    responses=build_responses(401, 500),
)
def list_marketplace_activity(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=100),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceActivityListResult:
    """List current user's registry-scoped Marketplace activity records."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    return service.list_activity(current_user_id, page=page, page_size=page_size)


@router.post(
    "/import/scan",
    response_model=list[MarketplaceImportCandidate],
    summary="Scan Marketplace import source",
    responses=build_responses(400, 401, 403, 500),
)
def scan_marketplace_import_source(
    payload: MarketplaceImportSource,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> list[MarketplaceImportCandidate]:
    """Validate and scan an external Marketplace import source."""
    _require_marketplace_permission(request, MARKETPLACE_IMPORT_PERMISSION)
    try:
        return service.scan_import_source(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        translate = getattr(request.state, "translate", None)
        message = translate(exc.code, **exc.params) if translate else exc.code
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": message},
        ) from exc


@router.post(
    "/import/upload",
    response_model=MarketplaceImportUploadResult,
    summary="Upload local Marketplace import source",
    responses=build_responses(400, 401, 403, 500),
)
async def upload_marketplace_import_source(
    request: Request,
    provider: str = Form(...),
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceImportUploadResult:
    """Upload a local Marketplace import archive into the managed import source root."""
    _require_marketplace_permission(request, MARKETPLACE_IMPORT_PERMISSION)
    _validate_provider(provider, request)
    try:
        content = await file.read()
        return service.save_uploaded_import_source(
            current_user_id,
            provider,  # type: ignore[arg-type]
            file.filename or "",
            content,
        )
    except MarketplaceImportSourceError as exc:
        translate = getattr(request.state, "translate", None)
        message = translate(exc.code, **exc.params) if translate else exc.code
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": message},
        ) from exc


@router.post(
    "/import",
    response_model=MarketplaceImportResult,
    summary="Import Marketplace candidates",
    responses=build_responses(400, 401, 403, 500),
)
def import_marketplace_candidates(
    payload: MarketplaceImportRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceImportResult:
    """Import selected Marketplace candidates into the local registry."""
    _require_marketplace_permission(request, MARKETPLACE_IMPORT_PERMISSION)
    try:
        return service.import_candidates(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        translate = getattr(request.state, "translate", None)
        message = translate(exc.code, **exc.params) if translate else exc.code
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": message},
        ) from exc


@router.post(
    "/install",
    response_model=MarketplaceInstallResult,
    summary="Install Marketplace package into workspace runtime",
    responses=build_responses(400, 401, 403, 404, 409, 500),
)
def install_marketplace_package(
    payload: MarketplaceInstallRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceInstallResult:
    """Install a provider-native Marketplace package through the workspace runtime."""
    _require_marketplace_permission(request, MARKETPLACE_INSTALL_PERMISSION)
    try:
        return service.install_package(current_user_id, payload)
    except MarketplacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except MarketplaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.get(
    "/install/preflight",
    response_model=MarketplaceCliPreflightResult,
    summary="Detect provider CLI install readiness",
    responses=build_responses(400, 401, 403, 500),
)
def detect_marketplace_install_cli(
    provider: str,
    request: Request,
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceCliPreflightResult:
    """Detect provider CLI availability, version, and install capabilities."""
    _require_marketplace_permission(request, MARKETPLACE_INSTALL_PERMISSION)
    _validate_provider(provider, request)
    if workspace_id:
        return service.detect_cli_for_workspace(provider, workspace_id)  # type: ignore[arg-type]
    return service.detect_cli(provider)  # type: ignore[arg-type]


@router.post(
    "/registry/init",
    response_model=MarketplaceRegistryInitResult,
    status_code=status.HTTP_201_CREATED,
    summary="Initialize Marketplace registry",
    responses=build_responses(401, 500),
)
def initialize_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryInitResult:
    """Initialize the shared Marketplace registry."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.initialize_registry(current_user_id)


@router.get(
    "/registry/repository",
    response_model=MarketplaceRegistryRepositoryStatus,
    summary="Get Marketplace registry Git repository status",
    responses=build_responses(401, 500),
)
def get_marketplace_registry_repository(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryRepositoryStatus:
    """Get shared Marketplace registry Git repository metadata."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.get_registry_repository_status(current_user_id)


@router.post(
    "/registry/git/init",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Initialize Marketplace registry Git repository",
    responses=build_responses(401, 500),
)
def initialize_marketplace_registry_git(
    request: Request,
    payload: MarketplaceRegistryRemoteRequest | None = None,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Initialize current user's Marketplace registry Git repository."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    return service.initialize_git_repository(current_user_id, payload)


@router.post(
    "/registry/clone",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Clone Marketplace registry",
    responses=build_responses(400, 401, 500),
)
def clone_marketplace_registry(
    payload: MarketplaceRegistryCloneRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Clone a Marketplace registry into the current user's managed registry root."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    return service.clone_registry(current_user_id, payload)


@router.put(
    "/registry/remote",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Set Marketplace registry origin remote",
    responses=build_responses(400, 401, 500),
)
def set_marketplace_registry_remote(
    payload: MarketplaceRegistryRemoteRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Set current user's Marketplace registry origin remote."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    return service.set_registry_remote(current_user_id, payload)


@router.get(
    "/registry/status",
    response_model=MarketplaceGitStatus,
    summary="Get Marketplace registry Git file status",
    responses=build_responses(401, 500),
)
def get_marketplace_registry_git_status(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitStatus:
    """Get current user's Marketplace registry file-level Git status."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.get_registry_git_status(current_user_id)


@router.get(
    "/registry/diff",
    response_model=MarketplaceGitDiffResponse,
    summary="Get Marketplace registry file diff",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_file_diff(
    request: Request,
    path: str = Query(..., min_length=1),
    head: Literal["WORKTREE", "INDEX"] = Query("WORKTREE"),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitDiffResponse:
    """Get selected current user's Marketplace registry file diff."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    try:
        return service.get_registry_file_diff(current_user_id, path, head=head)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.get(
    "/registry/commits/{commit_id}/files",
    response_model=MarketplaceGitCommitFilesResult,
    summary="Get Marketplace registry commit files",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_commit_files(
    commit_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitCommitFilesResult:
    """Get selected current user's Marketplace registry commit file list."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    try:
        return service.get_registry_commit_files(current_user_id, commit_id)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.get(
    "/registry/commits/{commit_id}/diff",
    response_model=MarketplaceGitDiffResponse,
    summary="Get Marketplace registry commit file diff",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_commit_file_diff(
    commit_id: str,
    request: Request,
    path: str = Query(..., min_length=1),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitDiffResponse:
    """Get selected current user's Marketplace registry commit file diff."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    try:
        return service.get_registry_commit_file_diff(current_user_id, commit_id, path)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/stage",
    response_model=MarketplaceGitStatus,
    summary="Stage Marketplace registry files",
    responses=build_responses(400, 401, 500),
)
def stage_marketplace_registry_paths(
    payload: MarketplaceGitPathRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitStatus:
    """Stage selected current user's Marketplace registry files."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.stage_registry_paths(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/unstage",
    response_model=MarketplaceGitStatus,
    summary="Unstage Marketplace registry files",
    responses=build_responses(400, 401, 500),
)
def unstage_marketplace_registry_paths(
    payload: MarketplaceGitPathRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitStatus:
    """Unstage selected current user's Marketplace registry files."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.unstage_registry_paths(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/commit",
    response_model=MarketplaceGitCommitResult,
    summary="Commit Marketplace registry changes",
    responses=build_responses(400, 401, 500),
)
def commit_marketplace_registry_changes(
    payload: MarketplaceGitCommitRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitCommitResult:
    """Commit current user's Marketplace registry changes."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.commit_registry_changes(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.get(
    "/registry/commits",
    response_model=MarketplaceGitCommitListResult,
    summary="List Marketplace registry commits",
    responses=build_responses(400, 401, 500),
)
def list_marketplace_registry_commits(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceGitCommitListResult:
    """List current user's Marketplace registry commit history."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    try:
        return service.list_registry_commits(current_user_id, page=page, page_size=page_size)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/fetch",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Fetch Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def fetch_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Fetch current user's Marketplace registry remote."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.fetch_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/pull",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Pull Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def pull_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Pull current user's Marketplace registry remote branch."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.pull_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/push",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Push Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def push_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistryGitOperationResult:
    """Push current user's Marketplace registry branch."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.push_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.get(
    "/registry/ssh-key",
    response_model=MarketplaceRegistrySshKeyResponse,
    summary="Get Marketplace registry SSH public key",
    responses=build_responses(401, 500),
)
def get_marketplace_registry_ssh_key(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistrySshKeyResponse:
    """Get shared Marketplace registry SSH public key metadata."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.get_registry_ssh_key_metadata(current_user_id)


@router.post(
    "/registry/ssh-key",
    response_model=MarketplaceRegistrySshKeyResponse,
    summary="Generate Marketplace registry SSH key",
    responses=build_responses(400, 401, 500),
)
def generate_marketplace_registry_ssh_key(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistrySshKeyResponse:
    """Generate current user's Marketplace registry SSH key pair."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    try:
        return service.generate_registry_ssh_key(current_user_id)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.post(
    "/registry/branches",
    summary="Create Marketplace registry branch",
    responses=build_responses(400, 401, 500),
)
def create_marketplace_registry_branch(request: Request) -> None:
    """Return localized unsupported error for first-version branch creation."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.branch_create_unsupported")


@router.post(
    "/registry/checkout",
    summary="Switch Marketplace registry branch",
    responses=build_responses(400, 401, 500),
)
def checkout_marketplace_registry_branch(request: Request) -> None:
    """Return localized unsupported error for first-version branch switching."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.branch_switch_unsupported")


@router.post(
    "/registry/merge",
    summary="Merge Marketplace registry branch",
    responses=build_responses(400, 401, 500),
)
def merge_marketplace_registry_branch(request: Request) -> None:
    """Return localized unsupported error for first-version merge."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.merge_unsupported")


@router.post(
    "/registry/rebase",
    summary="Rebase Marketplace registry branch",
    responses=build_responses(400, 401, 500),
)
def rebase_marketplace_registry_branch(request: Request) -> None:
    """Return localized unsupported error for first-version rebase."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.rebase_unsupported")


@router.post(
    "/registry/cherry-pick",
    summary="Cherry-pick Marketplace registry commit",
    responses=build_responses(400, 401, 500),
)
def cherry_pick_marketplace_registry_commit(request: Request) -> None:
    """Return localized unsupported error for first-version cherry-pick."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.cherry_pick_unsupported")


@router.post(
    "/registry/stash",
    summary="Stash Marketplace registry changes",
    responses=build_responses(400, 401, 500),
)
def stash_marketplace_registry_changes(request: Request) -> None:
    """Return localized unsupported error for first-version stash."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.stash_unsupported")


@router.post(
    "/registry/conflicts/resolve",
    summary="Resolve Marketplace registry conflicts",
    responses=build_responses(400, 401, 500),
)
def resolve_marketplace_registry_conflicts(request: Request) -> None:
    """Return localized unsupported error for first-version conflict resolution."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    _raise_unsupported_git_operation(request, "marketplace.git.conflict_resolution_unsupported")


@router.get(
    "/settings",
    response_model=MarketplaceRegistrySettings,
    summary="Get Marketplace registry settings",
    responses=build_responses(401, 500),
)
def get_marketplace_settings(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceRegistrySettings:
    """Get current user's Marketplace registry settings."""
    _require_marketplace_permission(request, MARKETPLACE_VIEW_PERMISSION)
    return service.get_settings(current_user_id)


@router.put(
    "/settings",
    response_model=MarketplaceSettingsSaveResult,
    summary="Save Marketplace registry settings",
    responses=build_responses(400, 401, 409, 500),
)
def save_marketplace_settings(
    payload: MarketplaceRegistryRootMetadataSavePayload,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceService = Depends(get_marketplace_service),
) -> MarketplaceSettingsSaveResult:
    """Save current user's Marketplace registry root metadata."""
    _require_marketplace_permission(request, MARKETPLACE_REGISTRY_MANAGE_PERMISSION)
    result = service.save_settings(current_user_id, payload)
    if result.error_code:
        translate = getattr(request.state, "translate", None)
        detail = (
            translate(result.error_code, provider=result.partial_success_provider or "none")
            if translate
            else result.error_code
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)
    return result
