"""Marketplace routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.file_management import (
    ConflictStrategy,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileExtractExecutionRequest,
)
from app.core.openapi import build_responses
from app.db.database import get_db
from app.modules.auth.auth_decorators import get_current_user_id
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.marketplace.cli_install import (
    MarketplaceCliInstallError,
    MarketplaceCliInstallService,
)
from app.modules.marketplace.models import (
    MarketplaceActivityAction,
    MarketplaceActivityDetail,
    MarketplaceActivityListResult,
    MarketplaceActivityStatus,
    MarketplaceBasicUpdateRequest,
    MarketplaceDocumentMutationRequest,
    MarketplaceDocumentRemoveRequest,
    MarketplaceDocumentRenameRequest,
    MarketplaceGitCommitFilesResult,
    MarketplaceGitCommitRequest,
    MarketplaceGitCommitResult,
    MarketplaceGitDiffResponse,
    MarketplaceGitPathRequest,
    MarketplaceGitStageResult,
    MarketplaceGitUnstageResult,
    MarketplaceLocalHistoryListResponse,
    MarketplaceLocalHistoryRestoreRequest,
    MarketplaceLocalHistoryRestoreResponse,
    MarketplaceMcpServerCreateRequest,
    MarketplaceMcpServerDeleteRequest,
    MarketplaceMcpServerMutationRequest,
    MarketplacePackageCreateRequest,
    MarketplacePackageDeleteRequest,
    MarketplacePackageDeleteResult,
    MarketplacePackageDetail,
    MarketplacePackageListResult,
    MarketplacePackageFormat,
    MarketplacePackageFormatOption,
    MarketplacePackageMutationResult,
    MarketplacePackageSaveRequest,
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
    MarketplaceRegistryCloneRequest,
    MarketplaceRegistryGitOperationResult,
    MarketplaceRegistryRepositoryStatus,
    MarketplaceRegistryRootMetadataSavePayload,
    MarketplaceRegistrySettings,
    MarketplaceSettingsSaveResult,
    MarketplaceTargetClient,
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyApplyResult,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
    MarketplaceImportCandidate,
    MarketplaceImportRequest,
    MarketplaceImportResult,
    MarketplaceImportSource,
    MarketplaceImportUploadResult,
)
from app.modules.marketplace.request import MarketplaceRequest
from app.modules.marketplace.runtime_client import MarketplaceRuntimeClientError
from app.modules.marketplace.user_copy import MarketplaceUserCopyError
from app.modules.marketplace.target_clients import package_format_storage_key
from app.modules.marketplace.workflows.registry_operations import (
    MARKETPLACE_FILE_MAX_WRITE_BYTES,
    MARKETPLACE_GIT_OPERATION_IN_PROGRESS,
    MarketplaceConflictError,
    MarketplacePathError,
    MarketplaceValidationError,
    MarketplaceImportSourceError,
)
from app.modules.version_control.models import (
    BlobResponse,
    BranchCreateRequest,
    BranchDeleteRequest,
    BranchMutationResponse,
    BranchPublishRequest,
    BranchRenameRequest,
    BranchSwitchRequest,
    CommitListResponse,
    CommitRevertRequest,
    ConflictPathsRequest,
    DiscardRequest,
    DiscardResponse,
    GitRemoteUrlRequest,
    LfsPatternsResponse,
    LfsPatternsUpdateRequest,
    LfsSnapshotConvertRequest,
    LfsSnapshotPreviewRequest,
    LfsSnapshotPreviewResponse,
    NumstatRequest,
    NumstatResponse,
    RemoteBranchesRequest,
    RemoteBranchesResponse,
    RemoteSettingsResponse,
    RepositoryInitializeRequest,
    VersionControlBranchListResponse,
    VersionControlChangesResponse,
    VersionControlOperationStatus,
    VersionControlStatus,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])

_FILE_CONFLICT_RESOLUTIONS = TypeAdapter(list[FileConflictResolution])
DocumentResourceType = Literal["commands", "subagents", "output-styles", "policies"]


def get_marketplace_request(
    request: Request,
    db: Session = Depends(get_db),
    actor: AuthorizationActor = Depends(get_authorization_actor),
) -> MarketplaceRequest:
    """Build the request-scoped Marketplace interface."""

    return MarketplaceRequest.create(db, request=request, actor=actor)


def get_marketplace_cli_install_service(
    db: Session = Depends(get_db),
    marketplace: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceCliInstallService:
    """Get the one-shot Marketplace CLI install service."""

    return MarketplaceCliInstallService(db, marketplace)


def get_marketplace_user_id(request: Request) -> str:
    """Resolve Marketplace user scope."""
    try:
        user_id = get_current_user_id(request)
        return user_id or "local-user"
    except HTTPException:
        if getattr(request.state, "auth_enabled", False):
            raise
    return "local-user"


def _validate_target_client(target_client: str, request: Request) -> None:
    if target_client not in {"claude-code", "codex"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=request.state.translate("marketplace.target_client.invalid"),
        )
    if "/marketplace/packages/" not in request.url.path:
        return
    package_format = request.query_params.get("packageFormat")
    compatible_formats = {
        "codex": {"codex-native", "agent-plugin/1.0.0"},
        "claude-code": {"claude-native"},
    }
    if package_format not in compatible_formats[target_client]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=request.state.translate("marketplace.package.format_invalid"),
        )


def _translate_error(request: Request, key: str) -> str:
    translate = getattr(request.state, "translate", None)
    return translate(key) if translate else key


def _marketplace_import_error_status(code: str) -> int:
    if code == MARKETPLACE_GIT_OPERATION_IN_PROGRESS:
        return status.HTTP_409_CONFLICT
    return status.HTTP_400_BAD_REQUEST


def _marketplace_import_error_detail(
    request: Request, exc: MarketplaceImportSourceError
) -> dict[str, str | None]:
    translate = getattr(request.state, "translate", None)
    message = translate(exc.code, **exc.params) if translate else exc.code
    return {
        "errorCode": exc.code,
        "message": message,
        "stage": exc.stage,
        "source": exc.source,
        "destination": exc.destination,
        "category": exc.category,
    }


def _raise_marketplace_path_or_import_error(
    request: Request,
    exc: MarketplacePathError | MarketplaceImportSourceError,
) -> None:
    if isinstance(exc, MarketplaceImportSourceError):
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=_translate_error(request, str(exc)),
    ) from exc


def _raise_marketplace_mutation_error(
    request: Request,
    exc: (
        MarketplacePathError
        | MarketplaceConflictError
        | MarketplaceValidationError
        | FileNotFoundError
    ),
) -> None:
    if isinstance(exc, MarketplaceConflictError):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, FileNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    else:
        status_code = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, MarketplaceValidationError):
        detail = _validation_error_detail(request, exc)
    else:
        detail = _translate_error(request, str(exc))
    raise HTTPException(status_code=status_code, detail=detail) from exc


async def _read_upload_within_limit(request: Request, file: UploadFile) -> bytes:
    content_length = request.headers.get("content-length")
    parsed_content_length = (
        int(content_length) if content_length and content_length.isdigit() else None
    )
    if (
        parsed_content_length
        and parsed_content_length > MARKETPLACE_FILE_MAX_WRITE_BYTES
    ):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=_translate_error(request, "marketplace.resource.file_too_large"),
        )

    content = bytearray()
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MARKETPLACE_FILE_MAX_WRITE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=_translate_error(request, "marketplace.resource.file_too_large"),
            )
    return bytes(content)


class MarketplaceRootDocumentSaveRequest(BaseModel):
    revision: str
    content: str


class MarketplaceHooksSaveRequest(BaseModel):
    revision: str
    sourceId: str | None = None
    content: str


class MarketplaceFileContentSaveRequest(BaseModel):
    revision: str
    content: str


class MarketplaceFileEntryCreateRequest(BaseModel):
    revision: str
    path: str
    type: Literal["file", "directory"] = "file"
    content: str = ""


class MarketplaceFileEntryMoveRequest(BaseModel):
    revision: str
    previousPath: str
    nextPath: str


class MarketplaceSkillConflictPreflightRequest(FileConflictPreflightRequest):
    revision: str


class MarketplaceSkillArchiveExtractRequest(FileExtractExecutionRequest):
    revision: str


def _upload_size(file: UploadFile) -> int:
    if file.size is not None:
        return file.size
    current_position = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current_position)
    return size


def _validation_error_detail(
    request: Request, exc: MarketplaceValidationError
) -> dict[str, object]:
    first = exc.results[0] if exc.results else {"code": str(exc)}
    code = str(first.get("messageKey") or first.get("code"))
    return {
        "errorCode": first.get("code"),
        "message": _translate_error(request, code),
        "validationResults": exc.results,
    }


def _marketplace_install_error_detail(
    request: Request,
    payload: MarketplacePluginInstallRequest,
    code: str,
    *,
    stage: str,
    category: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    source = payload.source_id or (
        f"plugins/{payload.target_client}/"
        f"{package_format_storage_key(payload.package_format)}/"
        f"{payload.package_id}/v{payload.version}"
        if payload.version
        else None
    )
    return {
        "errorCode": code,
        "message": _translate_error(request, code),
        "stage": stage,
        "source": source,
        "destination": payload.workspace_id,
        "category": category,
        **(extra or {}),
    }


@router.get(
    "/packages",
    response_model=MarketplacePackageListResult,
    summary="List Marketplace packages",
    responses=build_responses(401, 500),
)
def list_marketplace_packages(
    request: Request,
    target_client: str | None = Query(default=None),
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    features: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, alias="pageSize", ge=1, le=100),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageListResult:
    """List current user's Marketplace packages."""
    if target_client:
        _validate_target_client(target_client, request)
    return service.list_packages(
        current_user_id,
        target_client=target_client,  # type: ignore[arg-type]
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
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageListResult:
    """Force current user's Marketplace package index to rescan registry files."""
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
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageDetail:
    """Create a target_client-native Marketplace package scaffold."""
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
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.get(
    "/packages/{target_client}/{package_id}",
    response_model=MarketplacePackageDetail,
    summary="Get Marketplace package detail",
    responses=build_responses(400, 401, 404, 500),
)
def get_marketplace_package_detail(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageDetail:
    """Get a target_client-native Marketplace package detail."""
    _validate_target_client(target_client, request)
    detail = service.get_package_detail(current_user_id, target_client, package_id)  # type: ignore[arg-type]
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=request.state.translate("marketplace.package.not_found"),
        )
    return detail


@router.post(
    "/packages/{target_client}/{package_id}/refresh",
    summary="Refresh one Marketplace package overview",
    responses=build_responses(400, 401, 404, 500),
)
def refresh_marketplace_package(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, bool]:
    """Clear one cached package overview and the user's registry index."""
    _validate_target_client(target_client, request)
    try:
        return service.refresh_package_overview(
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
        )
    except FileNotFoundError as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.put(
    "/packages/{target_client}/{package_id}",
    response_model=MarketplacePackageMutationResult,
    summary="Save Marketplace package",
    responses=build_responses(400, 401, 404, 409, 500),
)
def save_marketplace_package(
    target_client: str,
    package_id: str,
    payload: MarketplacePackageSaveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    """Save a target_client-native Marketplace package snapshot."""
    _validate_target_client(target_client, request)
    try:
        return service.save_package(
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
            payload,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get("/packages/{target_client}/{package_id}/root-document")
def get_marketplace_root_document(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    try:
        return service.load_root_document(
            current_user_id,
            target_client,
            package_id,  # type: ignore[arg-type]
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, str(exc)),
        ) from exc


@router.put("/packages/{target_client}/{package_id}/root-document")
def save_marketplace_root_document(
    target_client: str,
    package_id: str,
    payload: MarketplaceRootDocumentSaveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.save_root_document(
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
            payload.revision,
            payload.content,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get("/packages/{target_client}/{package_id}/mcp-servers")
def list_marketplace_mcp_servers(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> list[dict[str, Any]]:
    _validate_target_client(target_client, request)
    return service.list_mcp_servers(
        current_user_id,
        target_client,
        package_id,  # type: ignore[arg-type]
    )


@router.get("/packages/{target_client}/{package_id}/mcp-servers/{name}")
def get_marketplace_mcp_server(
    target_client: str,
    package_id: str,
    name: str,
    request: Request,
    owner_file_path: str = Query(..., alias="ownerFilePath"),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    try:
        return service.get_mcp_server(
            current_user_id,
            target_client,
            package_id,
            name,  # type: ignore[arg-type]
            owner_file_path,
        )
    except FileNotFoundError as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/mcp-servers")
def create_marketplace_mcp_server(
    target_client: str,
    package_id: str,
    payload: MarketplaceMcpServerCreateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.create_mcp_server(
            current_user_id,
            target_client,
            package_id,
            payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.put("/packages/{target_client}/{package_id}/mcp-servers/{name}")
def put_marketplace_mcp_server(
    target_client: str,
    package_id: str,
    name: str,
    payload: MarketplaceMcpServerMutationRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.save_mcp_server(
            current_user_id,
            target_client,
            package_id,
            name,
            payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.delete("/packages/{target_client}/{package_id}/mcp-servers/{name}")
def delete_marketplace_mcp_server(
    target_client: str,
    package_id: str,
    name: str,
    payload: MarketplaceMcpServerDeleteRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.delete_mcp_server(
            current_user_id,
            target_client,
            package_id,
            name,
            payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.delete(
    "/packages/{target_client}/{package_id}",
    response_model=MarketplacePackageDeleteResult,
    summary="Delete Marketplace package",
    responses=build_responses(400, 401, 404, 409, 500),
)
def delete_marketplace_package(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageDeleteResult:
    """Hard delete a Marketplace package."""
    _validate_target_client(target_client, request)
    try:
        result = service.delete_package(
            current_user_id,
            MarketplacePackageDeleteRequest(
                target_client=target_client,  # type: ignore[arg-type]
                package_id=package_id,
            ),
        )
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc
    if not result.deleted and result.error_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_translate_error(request, result.error_code),
        )
    return result


@router.get(
    "/packages/{target_client}/{package_id}/export",
    summary="Export Marketplace package",
    responses=build_responses(400, 401, 404, 500),
)
def export_marketplace_package(
    target_client: str,
    package_id: str,
    request: Request,
    revision: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> Response:
    """Export a target_client-native Marketplace package zip."""
    _validate_target_client(target_client, request)
    try:
        archive = service.export_package(
            current_user_id, target_client, package_id, revision
        )  # type: ignore[arg-type]
    except MarketplacePathError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_error(request, str(exc)),
        ) from exc
    except FileNotFoundError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "errorCode": code,
                "message": _translate_error(request, code),
            },
        ) from exc
    except MarketplaceConflictError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "errorCode": code,
                "message": _translate_error(request, code),
            },
        ) from exc
    except MarketplaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_validation_error_detail(request, exc),
        ) from exc
    filename = f"{target_client}-{package_id}.zip"
    return Response(
        content=archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/packages/{target_client}/{package_id}/basic")
def get_marketplace_basic(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    return service.get_basic_metadata(current_user_id, target_client, package_id)  # type: ignore[arg-type]


@router.get("/packages/{target_client}/{package_id}/readme")
def get_marketplace_readme(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    """Load README content separately from the package overview."""
    _validate_target_client(target_client, request)
    return service.get_readme(current_user_id, target_client, package_id)  # type: ignore[arg-type]


@router.put("/packages/{target_client}/{package_id}/basic")
def update_marketplace_basic(
    target_client: str,
    package_id: str,
    payload: MarketplaceBasicUpdateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    return service.update_basic_metadata(current_user_id, target_client, package_id, payload)  # type: ignore[arg-type]


@router.get("/packages/{target_client}/{package_id}/hooks")
def get_marketplace_hooks(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    return service.get_hooks(current_user_id, target_client, package_id)  # type: ignore[arg-type]


@router.put("/packages/{target_client}/{package_id}/hooks")
def update_marketplace_hooks(
    target_client: str,
    package_id: str,
    payload: MarketplaceHooksSaveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.update_hooks(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload.sourceId,
            payload.content,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get("/packages/{target_client}/{package_id}/skills/tree")
def get_marketplace_skills_tree(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    return service.list_skill_files(current_user_id, target_client, package_id)  # type: ignore[arg-type]


@router.get("/packages/{target_client}/{package_id}/skills/content")
def get_marketplace_skill_content(
    target_client: str,
    package_id: str,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    try:
        return service.read_skill_file(current_user_id, target_client, package_id, path)  # type: ignore[arg-type]
    except (MarketplacePathError, FileNotFoundError) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.put("/packages/{target_client}/{package_id}/skills/content")
def put_marketplace_skill_content(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileContentSaveRequest,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.write_skill_file(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            path,
            payload.content,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/skills/conflicts/preflight",
    response_model=FileConflictPreflightResponse,
)
def preflight_marketplace_skill_conflicts(
    target_client: str,
    package_id: str,
    payload: MarketplaceSkillConflictPreflightRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictPreflightResponse:
    _validate_target_client(target_client, request)
    try:
        return service.preflight_skill_file_conflicts(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/skills/upload",
    response_model=FileConflictBatchResult,
)
async def upload_marketplace_skill_file(
    target_client: str,
    package_id: str,
    request: Request,
    revision: str = Form(...),
    targetPath: str = Form(...),
    defaultStrategy: ConflictStrategy = Form(...),
    resolutions: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictBatchResult:
    _validate_target_client(target_client, request)
    try:
        stream_files: list[tuple[str, Any, int]] = []
        for file in files:
            filename = Path(file.filename or "").name
            if not filename:
                raise MarketplacePathError("marketplace.resource.upload_failed")
            stream_files.append((filename, file.file, _upload_size(file)))
        return await run_in_threadpool(
            service.upload_skill_streams,
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
            revision,
            targetPath,
            stream_files,
            defaultStrategy,
            _FILE_CONFLICT_RESOLUTIONS.validate_json(resolutions),
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/skills/extract",
    response_model=FileConflictBatchResult,
)
async def extract_marketplace_skill_archive(
    target_client: str,
    package_id: str,
    payload: MarketplaceSkillArchiveExtractRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictBatchResult:
    _validate_target_client(target_client, request)
    try:
        return await run_in_threadpool(
            service.extract_skill_archive,
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
            payload.revision,
            payload.archivePath,
            payload.targetPath,
            payload.defaultStrategy,
            payload.resolutions,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/skills")
def post_marketplace_skill_entry(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileEntryCreateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.create_skill_entry(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload.path,
            payload.type,
            payload.content,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.delete("/packages/{target_client}/{package_id}/skills")
def delete_marketplace_skill_entry(
    target_client: str,
    package_id: str,
    request: Request,
    revision: str = Query(...),
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.delete_skill_entry(
            current_user_id,
            target_client,
            package_id,
            revision,
            path,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/skills/move")
def post_marketplace_skill_move(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileEntryMoveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.move_skill_entry(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload.previousPath,
            payload.nextPath,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get("/packages/{target_client}/{package_id}/files/tree")
def get_marketplace_files_tree(
    target_client: str,
    package_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    return service.list_package_files_tree(current_user_id, target_client, package_id)  # type: ignore[arg-type]


@router.get("/packages/{target_client}/{package_id}/files/content")
def get_marketplace_file_content(
    target_client: str,
    package_id: str,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    try:
        return service.read_package_file(current_user_id, target_client, package_id, path)  # type: ignore[arg-type]
    except (MarketplacePathError, FileNotFoundError) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.put("/packages/{target_client}/{package_id}/files/content")
def put_marketplace_file_content(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileContentSaveRequest,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.write_package_file(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            path,
            payload.content,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/files/conflicts/preflight",
    response_model=FileConflictPreflightResponse,
)
def preflight_marketplace_file_conflicts(
    target_client: str,
    package_id: str,
    payload: FileConflictPreflightRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictPreflightResponse:
    _validate_target_client(target_client, request)
    try:
        return service.preflight_package_file_conflicts(
            current_user_id,
            target_client,
            package_id,
            payload,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/files/upload",
    response_model=FileConflictBatchResult,
)
async def upload_marketplace_file_entries(
    target_client: str,
    package_id: str,
    request: Request,
    target_path: str = Form(..., alias="targetPath"),
    default_strategy: ConflictStrategy = Form(..., alias="defaultStrategy"),
    resolutions: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictBatchResult:
    _validate_target_client(target_client, request)
    try:
        streams = []
        for file in files:
            filename = Path(file.filename or "").name
            if not filename:
                raise MarketplacePathError("marketplace.resource.upload_failed")
            streams.append((filename, file.file, _upload_size(file)))
        parsed_resolutions = _FILE_CONFLICT_RESOLUTIONS.validate_json(resolutions)
        return await run_in_threadpool(
            service.upload_package_files,
            current_user_id,
            target_client,  # type: ignore[arg-type]
            package_id,
            target_path,
            streams,
            default_strategy,
            parsed_resolutions,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/files/paste",
    response_model=FileConflictBatchResult,
)
def paste_marketplace_file_entries(
    target_client: str,
    package_id: str,
    payload: FileConflictExecutionRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictBatchResult:
    _validate_target_client(target_client, request)
    try:
        return service.paste_package_files(
            current_user_id,
            target_client,
            package_id,
            payload,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post(
    "/packages/{target_client}/{package_id}/files/extract",
    response_model=FileConflictBatchResult,
)
def extract_marketplace_file_archive(
    target_client: str,
    package_id: str,
    payload: FileExtractExecutionRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> FileConflictBatchResult:
    _validate_target_client(target_client, request)
    try:
        return service.extract_package_archive(
            current_user_id,
            target_client,
            package_id,
            payload,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/files")
def post_marketplace_file_entry(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileEntryCreateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.create_package_file_entry(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload.path,
            payload.type,
            payload.content,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.delete("/packages/{target_client}/{package_id}/files")
def delete_marketplace_file_entry(
    target_client: str,
    package_id: str,
    request: Request,
    revision: str = Query(...),
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.delete_package_file_entry(
            current_user_id,
            target_client,
            package_id,
            revision,
            path,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/files/move")
def post_marketplace_file_move(
    target_client: str,
    package_id: str,
    payload: MarketplaceFileEntryMoveRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.move_package_file_entry(
            current_user_id,
            target_client,
            package_id,
            payload.revision,
            payload.previousPath,
            payload.nextPath,
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get("/packages/{target_client}/{package_id}/{resource_type}")
def list_marketplace_documents(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> list[dict[str, Any]]:
    _validate_target_client(target_client, request)
    return service.list_documents(
        current_user_id,
        target_client,
        package_id,
        resource_type,  # type: ignore[arg-type]
    )


@router.get("/packages/{target_client}/{package_id}/{resource_type}/content")
def load_marketplace_document(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> dict[str, Any]:
    _validate_target_client(target_client, request)
    return service.load_document(
        current_user_id,
        target_client,
        package_id,
        resource_type,
        path,  # type: ignore[arg-type]
    )


@router.post("/packages/{target_client}/{package_id}/{resource_type}")
def create_marketplace_document(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    payload: MarketplaceDocumentMutationRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.create_document(
            current_user_id,
            target_client,
            package_id,
            resource_type,
            payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.put("/packages/{target_client}/{package_id}/{resource_type}/content")
def update_marketplace_document(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    payload: MarketplaceDocumentMutationRequest,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    request_payload = payload.model_copy(update={"path": path})
    try:
        return service.update_document(
            current_user_id,
            target_client,
            package_id,
            resource_type,
            request_payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.post("/packages/{target_client}/{package_id}/{resource_type}/move")
def move_marketplace_document(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    payload: MarketplaceDocumentRenameRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    try:
        return service.move_document(
            current_user_id,
            target_client,
            package_id,
            resource_type,
            payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.delete("/packages/{target_client}/{package_id}/{resource_type}/content")
def delete_marketplace_document(
    target_client: str,
    package_id: str,
    resource_type: DocumentResourceType,
    request: Request,
    payload: MarketplaceDocumentRemoveRequest,
    path: str = Query(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplacePackageMutationResult:
    _validate_target_client(target_client, request)
    request_payload = payload.model_copy(update={"path": path})
    try:
        return service.remove_document(
            current_user_id,
            target_client,
            package_id,
            resource_type,
            request_payload,  # type: ignore[arg-type]
        )
    except (
        MarketplacePathError,
        MarketplaceConflictError,
        MarketplaceValidationError,
        FileNotFoundError,
    ) as exc:
        _raise_marketplace_mutation_error(request, exc)


@router.get(
    "/activities",
    response_model=MarketplaceActivityListResult,
    summary="List Marketplace activity records",
    responses=build_responses(401, 403, 500),
)
def list_marketplace_activity(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=100),
    workspace_id: str | None = Query(default=None, alias="workspaceId"),
    package_format: MarketplacePackageFormat | None = Query(
        default=None, alias="packageFormat"
    ),
    target_client: MarketplaceTargetClient | None = Query(
        default=None, alias="targetClient"
    ),
    package_id: str | None = Query(default=None, alias="packageId"),
    action: MarketplaceActivityAction | None = Query(default=None),
    activity_status: MarketplaceActivityStatus | None = Query(
        default=None,
        alias="status",
    ),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceActivityListResult:
    """List authorized workspace audit and actor-owned registry activity."""
    return service.list_activity(
        current_user_id,
        page=page,
        page_size=page_size,
        workspace_id=workspace_id,
        package_format=package_format,
        target_client=target_client,
        package_id=package_id,
        action=action,
        status=activity_status,
    )


@router.get(
    "/activities/{activity_id}",
    response_model=MarketplaceActivityDetail,
    summary="Get Marketplace activity detail",
    responses=build_responses(401, 403, 404, 500),
)
def get_marketplace_activity_detail(
    activity_id: str,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceActivityDetail:
    """Return raw CLI output only to the actor or Workspace managers."""

    detail = service.get_activity_detail(current_user_id, activity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="marketplace.activity.not_found")
    return detail


@router.post(
    "/imports/scan",
    response_model=list[MarketplaceImportCandidate],
    summary="Scan Plugin import source",
    responses=build_responses(400, 401, 403, 500),
)
def scan_marketplace_import_source(
    payload: MarketplaceImportSource,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> list[MarketplaceImportCandidate]:
    """Validate and scan an external Plugin import source."""
    try:
        return service.scan_import_source(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.post(
    "/imports/upload",
    response_model=MarketplaceImportUploadResult,
    summary="Upload local Plugin import source",
    responses=build_responses(400, 401, 403, 500),
)
async def upload_marketplace_import_source(
    request: Request,
    target_client: str = Form(..., alias="targetClient"),
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceImportUploadResult:
    """Upload a local archive into the managed import source root."""
    _validate_target_client(target_client, request)
    try:
        content = await file.read()
        return service.save_uploaded_import_source(
            current_user_id,
            target_client,  # type: ignore[arg-type]
            file.filename or "",
            content,
        )
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.post(
    "/imports",
    response_model=MarketplaceImportResult,
    summary="Import Plugin candidates",
    responses=build_responses(400, 401, 403, 500),
)
def import_marketplace_candidates(
    payload: MarketplaceImportRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceImportResult:
    """Import selected Plugin candidates into the managed registry."""
    try:
        return service.import_candidates(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.post(
    "/plugins/install",
    response_model=MarketplacePluginCommandResult,
    summary="Install a managed Plugin with the Target Client CLI",
    responses=build_responses(400, 401, 403, 404, 409, 500, 502, 503),
)
def install_marketplace_plugin(
    payload: MarketplacePluginInstallRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceCliInstallService = Depends(
        get_marketplace_cli_install_service
    ),
) -> MarketplacePluginCommandResult:
    """Publish one package and return the target_client CLI terminal result."""
    try:
        return service.install(current_user_id, payload)
    except MarketplaceCliInstallError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail=_marketplace_install_error_detail(
                request,
                payload,
                exc.code,
                stage="authorize" if exc.http_status == 403 else "install",
                category="authorization" if exc.http_status == 403 else "target_client",
            ),
        ) from exc
    except MarketplaceRuntimeClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_marketplace_install_error_detail(
                request,
                payload,
                exc.code,
                stage="install",
                category="runtime",
            ),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_marketplace_install_error_detail(
                request,
                payload,
                str(exc),
                stage="resolve",
                category="not_found",
            ),
        ) from exc
    except MarketplaceConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_marketplace_install_error_detail(
                request,
                payload,
                str(exc),
                stage="resolve",
                category="conflict",
            ),
        ) from exc
    except MarketplaceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_marketplace_install_error_detail(
                request,
                payload,
                str(exc),
                stage="validate",
                category="validation",
                extra={"validationResults": exc.results},
            ),
        ) from exc
    except MarketplaceImportSourceError as exc:
        detail = _marketplace_install_error_detail(
            request,
            payload,
            exc.code,
            stage=exc.stage,
            category=exc.category,
        )
        if exc.source is not None:
            detail["source"] = exc.source
        if exc.destination is not None:
            detail["destination"] = exc.destination
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=detail,
        ) from exc


@router.post(
    "/user-copies/preflight",
    response_model=MarketplaceUserCopyPreflightResult,
    summary="Preflight a one-shot Marketplace user copy",
    responses=build_responses(400, 401, 403, 404, 409, 500, 503),
)
def preflight_marketplace_user_copy(
    payload: MarketplaceUserCopyRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceUserCopyPreflightResult:
    """Plan a one-shot merge into Runtime user scope without creating state."""
    try:
        return service.preflight_user_copy(current_user_id, payload)
    except MarketplaceUserCopyError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={
                "errorCode": exc.code,
                "message": _translate_error(request, exc.code),
            },
        ) from exc


@router.post(
    "/user-copies",
    response_model=MarketplaceUserCopyApplyResult,
    summary="Apply a one-shot Marketplace user copy",
    responses=build_responses(400, 401, 403, 404, 409, 500, 503),
)
def create_marketplace_user_copy(
    payload: MarketplaceUserCopyApplyRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceUserCopyApplyResult:
    """Apply a preflighted user-scope merge without managed ownership."""
    try:
        return service.apply_user_copy(current_user_id, payload)
    except MarketplaceUserCopyError as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={
                "errorCode": exc.code,
                "message": _translate_error(request, exc.code),
            },
        ) from exc


@router.get(
    "/version-control/repository",
    response_model=MarketplaceRegistryRepositoryStatus,
    summary="Get Marketplace registry Git repository status",
    responses=build_responses(401, 500),
)
def get_marketplace_registry_repository(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceRegistryRepositoryStatus:
    """Get shared Marketplace registry Git repository metadata."""
    return service.get_registry_repository_status(current_user_id)


@router.post(
    "/version-control/remote-branches",
    response_model=RemoteBranchesResponse,
    summary="List remote Marketplace registry branches",
    responses=build_responses(400, 401, 500),
)
def list_marketplace_registry_remote_branches(
    payload: RemoteBranchesRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> RemoteBranchesResponse:
    """List branches available from a Marketplace registry remote."""
    return service.remote_branches(current_user_id, payload.remote_url)


@router.get(
    "/version-control/branches",
    response_model=VersionControlBranchListResponse,
    responses=build_responses(401, 500),
)
def list_marketplace_version_control_branches(
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlBranchListResponse:
    return service.list_branches(current_user_id)


@router.post(
    "/version-control/branches/create",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def create_marketplace_version_control_branch(
    payload: BranchCreateRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.create_branch_and_switch(
        current_user_id,
        name=payload.name,
        start_point=payload.start_point,
        upstream=payload.upstream,
    )


@router.post(
    "/version-control/branches/switch",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def switch_marketplace_version_control_branch(
    payload: BranchSwitchRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.switch_branch(current_user_id, name=payload.name)


@router.post(
    "/version-control/branches/rename",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def rename_marketplace_version_control_branch(
    payload: BranchRenameRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.rename_branch(
        current_user_id,
        old_name=payload.old_name,
        new_name=payload.new_name,
    )


@router.post(
    "/version-control/branches/delete",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def delete_marketplace_version_control_branch(
    payload: BranchDeleteRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.delete_branch(current_user_id, name=payload.name)


@router.post(
    "/version-control/branches/publish",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def publish_marketplace_version_control_branch(
    payload: BranchPublishRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    try:
        return service.publish_branch(
            current_user_id,
            remote=payload.remote,
            remote_name=payload.remote_name,
        )
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/conflicts/mark-resolved",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def mark_marketplace_version_control_conflicts_resolved(
    payload: ConflictPathsRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.mark_conflicts_resolved(current_user_id, paths=payload.paths)


@router.post(
    "/version-control/conflicts/abort",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def abort_marketplace_version_control_conflict(
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.abort_conflict(current_user_id)


@router.post(
    "/version-control/commits/revert",
    response_model=BranchMutationResponse,
    responses=build_responses(400, 401, 409, 500),
)
def revert_marketplace_version_control_commit(
    payload: CommitRevertRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.revert_commit(current_user_id, sha=payload.sha)


@router.post(
    "/version-control/init",
    response_model=VersionControlStatus,
    summary="Initialize Marketplace registry Git repository",
    responses=build_responses(401, 500),
)
def initialize_marketplace_registry_git(
    request: Request,
    payload: RepositoryInitializeRequest | None = None,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlStatus:
    """Initialize current user's Marketplace registry Git repository."""
    try:
        return service.initialize_git_repository(
            current_user_id,
            default_branch=(payload or RepositoryInitializeRequest()).default_branch,
        )
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.post(
    "/version-control/clone",
    response_model=VersionControlStatus,
    summary="Clone Marketplace registry",
    responses=build_responses(400, 401, 500),
)
def clone_marketplace_registry(
    payload: MarketplaceRegistryCloneRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlStatus:
    """Clone a Marketplace registry into the current user's managed registry root."""
    try:
        return service.clone_registry(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.get(
    "/version-control/lfs",
    response_model=LfsPatternsResponse,
    summary="Get Marketplace registry Git LFS patterns",
    responses=build_responses(400, 401, 409, 500),
)
def get_marketplace_registry_lfs_patterns(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> LfsPatternsResponse:
    return service.get_lfs_patterns(current_user_id)


@router.post(
    "/version-control/lfs",
    response_model=BranchMutationResponse,
    summary="Update Marketplace registry Git LFS patterns",
    responses=build_responses(400, 401, 409, 500),
)
def update_marketplace_registry_lfs_patterns(
    payload: LfsPatternsUpdateRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.update_lfs_patterns(current_user_id, patterns=payload.patterns)


@router.post(
    "/version-control/lfs/preview",
    response_model=LfsSnapshotPreviewResponse,
    summary="Preview Marketplace registry Git LFS snapshot conversion",
    responses=build_responses(400, 401, 409, 500),
)
def preview_marketplace_registry_lfs_snapshot(
    payload: LfsSnapshotPreviewRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> LfsSnapshotPreviewResponse:
    return service.preview_lfs_snapshot(
        current_user_id,
        patterns=payload.patterns,
    )


@router.post(
    "/version-control/lfs/convert",
    response_model=BranchMutationResponse,
    summary="Convert Marketplace registry files to Git LFS pointers",
    responses=build_responses(400, 401, 409, 500),
)
def convert_marketplace_registry_lfs_snapshot(
    payload: LfsSnapshotConvertRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.convert_lfs_snapshot(current_user_id, paths=payload.paths)


@router.get(
    "/version-control/remote",
    response_model=RemoteSettingsResponse,
    summary="Get Marketplace registry origin settings",
    responses=build_responses(400, 401, 409, 500),
)
def get_marketplace_registry_remote_settings(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> RemoteSettingsResponse:
    return service.get_remote_settings(current_user_id)


@router.put(
    "/version-control/remote",
    response_model=BranchMutationResponse,
    summary="Set Marketplace registry origin remote",
    responses=build_responses(400, 401, 500),
)
def set_marketplace_registry_remote(
    payload: GitRemoteUrlRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    """Set current user's Marketplace registry origin remote."""
    try:
        return service.set_registry_remote(current_user_id, payload.url)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc


@router.get(
    "/version-control/changes",
    response_model=VersionControlChangesResponse,
    summary="Get Marketplace registry version-control changes",
    responses=build_responses(401, 500),
)
def get_marketplace_version_control_changes(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    group: Literal["all", "staged", "unstaged", "untracked", "conflicts"] = Query(
        "all"
    ),
    include_stats: bool = Query(
        True,
        alias="includeStats",
        description="When false, additions/deletions are null (deferred to /changes/numstat)",
    ),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlChangesResponse:
    """Get current user's Marketplace registry version-control changes."""
    try:
        return service.get_registry_changes(
            current_user_id,
            cursor=cursor,
            limit=limit,
            group=group,
            include_stats=include_stats,
        )
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/changes/numstat",
    response_model=NumstatResponse,
    summary="Get deferred numstat for visible Marketplace registry paths",
    responses=build_responses(401, 500),
)
def get_marketplace_version_control_changes_numstat(
    request: Request,
    payload: NumstatRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> NumstatResponse:
    """Get deferred numstat for the visible Marketplace registry paths."""
    try:
        return service.get_registry_changes_numstat(
            current_user_id,
            staged_paths=payload.stagedPaths,
            unstaged_paths=payload.unstagedPaths,
        )
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/status",
    response_model=VersionControlStatus,
    summary="Get Marketplace registry version-control status",
    responses=build_responses(401, 500),
)
def get_marketplace_version_control_status(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlStatus:
    """Get current user's Marketplace registry version-control status."""
    try:
        return service.get_registry_status(current_user_id)
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/operation-status",
    response_model=VersionControlOperationStatus,
    summary="Get Marketplace registry Git operation status",
    responses=build_responses(401, 500),
)
def get_marketplace_version_control_operation_status(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> VersionControlOperationStatus:
    """Get current user's Marketplace registry in-progress Git operation."""
    return service.get_registry_operation_status(current_user_id)


@router.post(
    "/version-control/operation/cancel",
    response_model=BranchMutationResponse,
    summary="Cancel active Marketplace registry Git operation",
    responses=build_responses(400, 401, 409, 500),
)
def cancel_marketplace_version_control_operation(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    return service.cancel_operation(current_user_id)


@router.get(
    "/version-control/files/history",
    response_model=MarketplaceLocalHistoryListResponse,
    summary="List Marketplace registry local history entries",
    responses=build_responses(400, 401, 500),
)
def list_marketplace_registry_file_history(
    request: Request,
    path: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceLocalHistoryListResponse:
    """List Marketplace registry local history entries."""
    try:
        return MarketplaceLocalHistoryListResponse(
            **service.list_registry_file_history(path=path, limit=limit)
        )
    except MarketplacePathError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/files/history/{entry_id}/restore",
    response_model=MarketplaceLocalHistoryRestoreResponse,
    summary="Restore Marketplace registry local history entry",
    responses=build_responses(400, 401, 404, 409, 500),
)
def restore_marketplace_registry_file_history(
    entry_id: str,
    payload: MarketplaceLocalHistoryRestoreRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceLocalHistoryRestoreResponse:
    """Restore a Marketplace registry file from local history."""
    try:
        return MarketplaceLocalHistoryRestoreResponse(
            **service.restore_registry_file_history(
                current_user_id,
                entry_id=entry_id,
                revision=payload.revision,
            )
        )
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
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/diff",
    response_model=MarketplaceGitDiffResponse,
    summary="Get Marketplace registry file diff",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_file_diff(
    request: Request,
    path: str = Query(..., min_length=1),
    head: Literal["WORKTREE", "INDEX"] = Query("WORKTREE"),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitDiffResponse:
    """Get selected current user's Marketplace registry file diff."""
    try:
        return service.get_registry_file_diff(current_user_id, path, head=head)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/blob",
    response_model=BlobResponse,
    summary="Get Marketplace registry file content",
    responses=build_responses(400, 401, 409, 500),
)
def get_marketplace_registry_blob(
    path: str = Query(..., min_length=1),
    revision: str | None = Query(default=None),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BlobResponse:
    return service.get_registry_blob(
        current_user_id,
        path=path,
        revision=revision,
    )


@router.get(
    "/version-control/commits/{commit_id}/files",
    response_model=MarketplaceGitCommitFilesResult,
    summary="Get Marketplace registry commit files",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_commit_files(
    commit_id: str,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitCommitFilesResult:
    """Get selected current user's Marketplace registry commit file list."""
    try:
        return service.get_registry_commit_files(current_user_id, commit_id)
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/commits/{commit_id}/diff",
    response_model=MarketplaceGitDiffResponse,
    summary="Get Marketplace registry commit file diff",
    responses=build_responses(400, 401, 500),
)
def get_marketplace_registry_commit_file_diff(
    commit_id: str,
    request: Request,
    path: str = Query(..., min_length=1),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitDiffResponse:
    """Get selected current user's Marketplace registry commit file diff."""
    try:
        return service.get_registry_commit_file_diff(current_user_id, commit_id, path)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/stage",
    response_model=MarketplaceGitStageResult,
    summary="Stage Marketplace registry files",
    responses=build_responses(400, 401, 500),
)
def stage_marketplace_registry_paths(
    payload: MarketplaceGitPathRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitStageResult:
    """Stage selected current user's Marketplace registry files."""
    try:
        return service.stage_registry_paths(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/unstage",
    response_model=MarketplaceGitUnstageResult,
    summary="Unstage Marketplace registry files",
    responses=build_responses(400, 401, 500),
)
def unstage_marketplace_registry_paths(
    payload: MarketplaceGitPathRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitUnstageResult:
    """Unstage selected current user's Marketplace registry files."""
    try:
        return service.unstage_registry_paths(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/discard",
    response_model=DiscardResponse,
    summary="Discard Marketplace registry changes",
    responses=build_responses(400, 401, 409, 500),
)
def discard_marketplace_registry_paths(
    payload: DiscardRequest,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> DiscardResponse:
    return service.discard_registry_paths(current_user_id, payload)


@router.post(
    "/version-control/commit",
    response_model=MarketplaceGitCommitResult,
    summary="Commit Marketplace registry changes",
    responses=build_responses(400, 401, 500),
)
def commit_marketplace_registry_changes(
    payload: MarketplaceGitCommitRequest,
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceGitCommitResult:
    """Commit current user's Marketplace registry changes."""
    try:
        return service.commit_registry_changes(current_user_id, payload)
    except (MarketplacePathError, MarketplaceImportSourceError) as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.get(
    "/version-control/commits",
    response_model=CommitListResponse,
    summary="List Marketplace registry commits",
    responses=build_responses(400, 401, 500),
)
def list_marketplace_registry_commits(
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    query_scope: Literal["current", "all", "local", "remote"] = Query(
        "current", alias="queryScope"
    ),
    branch: str | None = Query(None),
    search: str | None = Query(None),
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> CommitListResponse:
    """List current user's Marketplace registry commit history."""
    try:
        return service.list_registry_commits(
            current_user_id,
            cursor=cursor,
            limit=limit,
            query_scope=query_scope,
            branch=branch,
            search=search,
        )
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/fetch",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Fetch Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def fetch_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceRegistryGitOperationResult:
    """Fetch current user's Marketplace registry remote."""
    try:
        return service.fetch_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/pull",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Pull Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def pull_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceRegistryGitOperationResult:
    """Pull current user's Marketplace registry remote branch."""
    try:
        return service.pull_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/push",
    response_model=MarketplaceRegistryGitOperationResult,
    summary="Push Marketplace registry remote",
    responses=build_responses(400, 401, 500),
)
def push_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceRegistryGitOperationResult:
    """Push current user's Marketplace registry branch."""
    try:
        return service.push_registry(current_user_id)
    except MarketplaceImportSourceError as exc:
        _raise_marketplace_path_or_import_error(request, exc)


@router.post(
    "/version-control/force-unlock",
    response_model=BranchMutationResponse,
    summary="Force-clear stale Marketplace registry Git locks",
    responses=build_responses(401, 409, 500),
)
def force_unlock_marketplace_registry(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> BranchMutationResponse:
    """Manually clear stale on-disk Git locks for the shared Marketplace registry.

    Returns the shared mutation result without exposing repository filesystem paths.
    """
    return service.force_unlock(current_user_id)


@router.get(
    "/settings",
    response_model=MarketplaceRegistrySettings,
    summary="Get Marketplace registry settings",
    responses=build_responses(401, 500),
)
def get_marketplace_settings(
    request: Request,
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceRegistrySettings:
    """Get current user's Marketplace registry settings."""
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
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> MarketplaceSettingsSaveResult:
    """Save current user's Marketplace registry root metadata."""
    try:
        result = service.save_settings(current_user_id, payload)
    except MarketplaceImportSourceError as exc:
        raise HTTPException(
            status_code=_marketplace_import_error_status(exc.code),
            detail=_marketplace_import_error_detail(request, exc),
        ) from exc
    if result.error_code:
        translate = getattr(request.state, "translate", None)
        detail = (
            translate(
                result.error_code,
                target_client=result.partial_success_target_client or "none",
            )
            if translate
            else result.error_code
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail
        )
    return result
@router.get(
    "/package-formats",
    response_model=list[MarketplacePackageFormatOption],
    summary="List creatable Plugin package formats",
)
def list_marketplace_package_formats(
    current_user_id: str = Depends(get_marketplace_user_id),
    service: MarketplaceRequest = Depends(get_marketplace_request),
) -> list[MarketplacePackageFormatOption]:
    """Return Manager-owned format, client, and authoring capabilities."""

    del current_user_id
    return service.list_package_format_options()
