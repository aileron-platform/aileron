"""Knowledge base API."""

from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import Literal

from aileron_git_core import GitCommandError, VersionControlError
from fastapi import (
    APIRouter,
    BackgroundTasks,
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
from fastapi.responses import FileResponse
from pydantic import TypeAdapter
from sqlalchemy import func, select

from app.config.settings import get_settings
from app.core.api_error import ApiErrorResponse, authorization_error_detail
from app.core.file_management import (
    ConflictStrategy,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileContentResponse,
    FileExtractExecutionRequest,
    FileManagementException,
    FileTreeResponse,
)
from app.core.openapi import build_responses
from app.db import models as db_models
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.dependencies import get_authorization_actor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    OperationId,
    allowed_knowledge_base_operations,
)
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
)
from app.modules.identity.platform_role import PlatformRole, normalize_platform_role
from app.modules.knowledge_base.access import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
)
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.knowledge_base.archive import KnowledgeBaseArchiveService
from app.modules.knowledge_base.attachments import (
    AttachmentMutationProjection,
    KnowledgeBaseAttachmentService,
)
from app.modules.knowledge_base.dependencies import (
    get_knowledge_base_archive_service,
    get_knowledge_base_attachment_service,
    get_knowledge_base_file_service,
    get_knowledge_base_git_service,
    get_knowledge_base_query_service,
    get_knowledge_base_service,
    get_knowledge_base_sharing_service,
    get_knowledge_base_source_service,
)
from app.modules.knowledge_base.files import (
    KB_NOT_A_FILE_REASON,
    KB_PATH_TRAVERSAL_REASON,
    KnowledgeBaseFileService,
)
from app.modules.knowledge_base.git import KnowledgeBaseGitService
from app.modules.knowledge_base.models import (
    ArchiveDownloadAcceptedResponse,
    ArchiveDownloadRequest,
    ArchiveDownloadStatusResponse,
    KnowledgeBaseAttachmentListResponse,
    KnowledgeBaseAttachmentSummary,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDeleteRequest,
    KnowledgeBaseDetail,
    KnowledgeBaseFileMutationRequest,
    KnowledgeBaseFilePatchRequest,
    KnowledgeBaseFileSearchResponse,
    KnowledgeBaseGitCloneRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseLocalHistoryListResponse,
    KnowledgeBaseLocalHistoryRestoreRequest,
    KnowledgeBaseLocalHistoryRestoreResponse,
    KnowledgeBaseQueryRequest,
    KnowledgeBaseQueryResponse,
    KnowledgeBaseShareCandidateGroup,
    KnowledgeBaseShareCandidateGroupListResponse,
    KnowledgeBaseShareCreateRequest,
    KnowledgeBaseShareListResponse,
    KnowledgeBaseShareSummary,
    KnowledgeBaseShareUpdateRequest,
    KnowledgeBaseSourceUploadResponse,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdateRequest,
    KnowledgeBaseVisibilityUpdateRequest,
    KnowledgeBaseWebClipImportRequest,
    KnowledgeBaseWebClipImportResponse,
)
from app.modules.knowledge_base.query import KnowledgeBaseQueryService
from app.modules.knowledge_base.sources import KnowledgeBaseSourceService
from app.modules.version_control.application import version_control_error_envelope
from app.modules.version_control.models import (
    BlobResponse,
    BranchCreateRequest,
    BranchDeleteRequest,
    BranchMutationResponse,
    BranchPublishRequest,
    BranchRenameRequest,
    BranchSwitchRequest,
    CommitFilesResponse,
    CommitListResponse,
    CommitResponse,
    CommitRevertRequest,
    ConflictPathsRequest,
    DiffResponse,
    DiscardRequest,
    DiscardResponse,
    GitCommitRequest,
    GitRemoteUrlRequest,
    GitRepositoryStatus,
    LfsPatternsResponse,
    LfsPatternsUpdateRequest,
    LfsSnapshotConvertRequest,
    LfsSnapshotPreviewRequest,
    LfsSnapshotPreviewResponse,
    NumstatRequest,
    NumstatResponse,
    RemoteBranchesRequest,
    RemoteBranchesResponse,
    RemoteRequest,
    RemoteResponse,
    RemoteSettingsResponse,
    RepositoryInitializeRequest,
    StageRequest,
    StageResponse,
    UnstageRequest,
    UnstageResponse,
    VersionControlBranchListResponse,
    VersionControlChangesResponse,
    VersionControlOperationStatus,
    VersionControlStatus,
)

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

_FILE_CONFLICT_RESOLUTIONS = TypeAdapter(list[FileConflictResolution])

_KB_ERROR_EXAMPLES = {
    409: {
        "quotaExceeded": {
            "summary": "KB quota exceeded",
            "value": {
                "detail": {
                    "errorCode": "KB_QUOTA_EXCEEDED",
                    "message": "Knowledge base quota exceeded",
                    "details": {
                        "kbId": "kb-123",
                        "currentSizeBytes": 4,
                        "deltaBytes": 5,
                        "quotaBytes": 4,
                    },
                }
            },
        },
        "duplicateAttachment": {
            "summary": "Duplicate attachment of the same KB",
            "value": {
                "detail": {
                    "errorCode": "KB_ALREADY_ATTACHED",
                    "message": "Knowledge base is already attached to this workspace",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "aliasConflict": {
            "summary": "Mount alias conflict",
            "value": {
                "detail": {
                    "errorCode": "KB_MOUNT_ALIAS_CONFLICT",
                    "message": "Knowledge base mount alias already exists",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "knowledgeBaseInUse": {
            "summary": "KB still mounted by workspace",
            "value": {
                "detail": {
                    "errorCode": "KB_DELETE_ATTACHMENT_CONFLICT",
                    "message": "Knowledge base is still attached to one or more workspaces",
                    "details": {"resource": "knowledge_base"},
                }
            },
        },
    },
    413: {
        "fileTooLarge": {
            "summary": "Single file size limit exceeded",
            "value": {
                "detail": {
                    "errorCode": "FILE_TOO_LARGE",
                    "message": "File size exceeds the configured limit",
                    "details": {
                        "path": "/too-large.md",
                        "size": 8,
                        "maxSize": 4,
                    },
                }
            },
        }
    },
}

_KB_ERROR_DESCRIPTIONS = {
    400: "Knowledge base request is invalid, such as path format error. `detail.message` will be localized according to request language.",
    403: "Current user does not have operation permission on knowledge base or workspace. `detail.message` will be localized according to request language.",
    404: "Specified knowledge base, share, or attachment does not exist. `detail.message` will be localized according to request language.",
    409: "Knowledge base status conflict, such as quota exceeded, duplicate attachment, alias conflict, or KB still mounted. `detail.message` will be localized according to request language.",
    413: "Single read file exceeds `KB_SINGLE_FILE_SIZE_LIMIT`. `detail.message` will be localized according to request language.",
    422: "Knowledge base file path is syntactically invalid. `detail.message` will be localized according to request language.",
}


def _build_kb_responses(*status_codes: int) -> dict[int, dict]:
    return build_responses(
        *status_codes,
        model=ApiErrorResponse,
        descriptions=_KB_ERROR_DESCRIPTIONS,
        examples={
            status_code: _KB_ERROR_EXAMPLES[status_code]
            for status_code in status_codes
            if status_code in _KB_ERROR_EXAMPLES
        },
    )


def _to_summary(
    kb,
    access_role: ResourceAccessRole | str,
    *,
    current_user_id: str,
    service: KnowledgeBaseService,
) -> KnowledgeBaseSummary:
    settings = get_settings()
    effective_quota = (
        kb.quota_bytes
        if kb.quota_bytes is not None
        else settings.DEFAULT_KB_QUOTA_BYTES
    )
    owner_quota_used = (
        service.db.scalar(
            select(
                func.coalesce(func.sum(db_models.KnowledgeBase.current_size_bytes), 0)
            ).where(db_models.KnowledgeBase.owner_id == kb.owner_id)
        )
        or 0
    )
    canonical_role = ResourceAccessRole(access_role)
    user = service.db.get(db_models.User, current_user_id)
    effective_access = KnowledgeBaseAccessResolver(service.db).resolve(
        knowledge_base_id=kb.id,
        user_id=current_user_id,
    )
    sources = list(effective_access.access_sources if effective_access else ())
    if (
        normalize_platform_role(user.platform_role if user is not None else None)
        is PlatformRole.ADMIN
        and ResourceAccessSource.PLATFORM_ADMIN not in sources
    ):
        sources.append(ResourceAccessSource.PLATFORM_ADMIN)
    if not sources:
        sources.append(ResourceAccessSource.DIRECT_SHARE)
    primary_source = (
        ResourceAccessSource.OWNED
        if canonical_role is ResourceAccessRole.OWNER
        else (
            ResourceAccessSource.PLATFORM_ADMIN
            if ResourceAccessSource.PLATFORM_ADMIN in sources
            and (
                effective_access is None
                or effective_access.access_role is not canonical_role
            )
            else sources[0]
        )
    )
    return KnowledgeBaseSummary(
        id=kb.id,
        slug=kb.slug,
        name=kb.name,
        description=kb.description,
        owner_id=kb.owner_id,
        current_size_bytes=kb.current_size_bytes,
        quota_bytes=kb.quota_bytes,
        effective_quota_bytes=effective_quota,
        quota_source=("custom" if kb.quota_bytes is not None else "platform_default"),
        utilization_percent=(
            ((kb.current_size_bytes or 0) / effective_quota) * 100
            if effective_quota > 0
            else 0
        ),
        owner_quota_used_bytes=owner_quota_used,
        owner_effective_quota_bytes=settings.DEFAULT_USER_KB_QUOTA_BYTES,
        version_control_enabled=getattr(kb, "version_control_enabled", False),
        last_indexed_at=getattr(kb, "last_indexed_at", None),
        last_index_status=getattr(kb, "last_index_status", None),
        last_index_error=getattr(kb, "last_index_error", None),
        access_role=canonical_role,
        access_source=primary_source,
        access_sources=sources,
        visibility=kb.visibility,
        allowed_operations=list(allowed_knowledge_base_operations(canonical_role)),
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


def _to_share_summary(share, target_label: str) -> KnowledgeBaseShareSummary:
    return KnowledgeBaseShareSummary(
        id=share.id,
        kb_id=share.kb_id,
        target_type=share.target_type,
        target_id=share.target_id,
        target_label=target_label,
        role=share.role,
        granted_by_id=share.granted_by_id,
        created_at=share.created_at,
    )


def _to_attachment_summary(attachment) -> KnowledgeBaseAttachmentSummary:
    if isinstance(attachment, AttachmentMutationProjection):
        workspace_id = attachment.workspace_id
        workspace_name = attachment.workspace_name
        attachment_status = attachment.status
    else:
        workspace_id = attachment.workspace_id
        workspace_name = attachment.workspace.name
        attachment_status = "active"
    if workspace_id is None or workspace_name is None:
        raise ValueError("Workspace attachment projection is incomplete")
    return KnowledgeBaseAttachmentSummary(
        attachment_id=attachment.id,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        mount_alias=attachment.mount_alias,
        attachment_status=attachment_status,
    )


_KB_MESSAGE_KEYS = {
    "KB_NOT_FOUND": "knowledge_base.not_found",
    "KB_ATTACHMENT_NOT_FOUND": "knowledge_base.attachment_not_found",
    "KB_ACCESS_DENIED": "knowledge_base.access_denied",
    "KB_PERMISSION_DENIED": "knowledge_base.permission_denied",
    "KB_ALREADY_ATTACHED": "knowledge_base.already_attached",
    "KB_MOUNT_ALIAS_CONFLICT": "knowledge_base.alias_conflict",
    "KB_DELETE_ATTACHMENT_CONFLICT": "knowledge_base.in_use",
    "KB_DELETE_STORAGE_CLEANUP_FAILED": "knowledge_base.delete_storage_cleanup_failed",
    "RESOURCE_DELETE_CONFIRMATION_MISMATCH": "knowledge_base.delete_confirmation_mismatch",
    "KB_SLUG_CONFLICT": "knowledge_base.slug_conflict",
    "KB_SHARE_DUPLICATE_TARGET": "knowledge_base.share.duplicate_target",
    "KB_SHARE_INVALID_TARGET_TYPE": "knowledge_base.share.invalid_target_type",
    "KB_SHARE_TARGET_NOT_FOUND": "knowledge_base.share.target_not_found",
    "KB_SHARE_OWNER_TARGET_FORBIDDEN": "knowledge_base.share.owner_forbidden",
    "KB_SHARE_FORBIDDEN": "knowledge_base.permission_denied",
    "KB_SHARE_INVALID_ROLE": "knowledge_base.invalid.share_role",
    "KB_INVALID_SLUG": "knowledge_base.invalid.slug",
    "KB_OWNER_NOT_FOUND": "knowledge_base.invalid.owner",
    "KB_INVALID_ROLE": "knowledge_base.invalid.role",
    "KB_INVALID_QUOTA": "knowledge_base.invalid.quota",
    "KB_QUOTA_BELOW_USAGE": "knowledge_base.invalid.quota_below_usage",
    "KB_CONFLICT": "knowledge_base.conflict",
    "KB_INVALID_REQUEST": "knowledge_base.invalid.request",
    "FILE_NOT_FOUND": "knowledge_base.file.not_found",
    "FILE_ALREADY_EXISTS": "knowledge_base.file.exists",
    "INVALID_PATH": "knowledge_base.file.invalid_path",
    "FILE_TOO_LARGE": "knowledge_base.file.too_large",
    "CONTENT_CONFLICT": "knowledge_base.file.content_conflict",
    "DIRECTORY_NOT_EMPTY": "knowledge_base.file.directory_not_empty",
    "INVALID_FILE_TYPE": "knowledge_base.file.invalid_type",
    "KB_QUOTA_EXCEEDED": "knowledge_base.file.kb_quota_exceeded",
    "USER_KB_QUOTA_EXCEEDED": "knowledge_base.file.owner_quota_exceeded",
    "PATH_NOT_WRITABLE": "knowledge_base.file.path_not_writable",
    "RAW_ROOT_CANNOT_BE_DELETED": "knowledge_base.file.raw_root_cannot_be_deleted",
    "LOCAL_HISTORY_ENTRY_NOT_FOUND": "knowledge_base.file.history_entry_not_found",
    "KB_VERSION_CONTROL_DISABLED": "knowledge_base.git.version_control_disabled",
    "GIT_REPO_NOT_FOUND": "knowledge_base.git.repo_not_found",
    "GIT_NO_CHANGES": "knowledge_base.git.no_changes_to_commit",
    "GIT_PATH_OUTSIDE_REPOSITORY": "knowledge_base.git.path_outside_repository",
    "GIT_REPOSITORY_ALREADY_INITIALIZED": (
        "knowledge_base.git.repository_already_initialized"
    ),
    "VC_REPOSITORY_ALREADY_INITIALIZED": (
        "knowledge_base.git.repository_already_initialized"
    ),
    "VC_CLONE_TARGET_NOT_EMPTY": "knowledge_base.git.clone_target_not_empty",
    "VC_REMOTE_URL_INVALID": "knowledge_base.git.remote_url_invalid",
    "VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED": (
        "knowledge_base.git.remote_url_credentials_not_allowed"
    ),
    "VC_SSH_KEY_REQUIRED": "knowledge_base.git.ssh_key_required",
    "KB_GIT_OPERATION_IN_PROGRESS": "knowledge_base.git.operation_in_progress",
    "KB_GIT_OPERATION_FAILED": "knowledge_base.git.operation_failed",
}

_KB_MESSAGE_DETAIL_FIELDS = {
    "FILE_NOT_FOUND": "path",
    "FILE_ALREADY_EXISTS": "path",
    "INVALID_FILE_TYPE": "extension",
}


def _translate_kb_message(translate, *, code: str, details: dict) -> str:
    message_key = _KB_MESSAGE_KEYS.get(code)
    if message_key is None:
        return translate("knowledge_base.unexpected_error")

    detail_field = _KB_MESSAGE_DETAIL_FIELDS.get(code)
    if detail_field is None:
        return translate(message_key)
    return translate(message_key, **{detail_field: details.get(detail_field, "")})


def _translate_kb_details(translate, *, code: str, details: dict) -> dict:
    localized = dict(details)
    if code == "INVALID_PATH" and "reason" in localized:
        if localized["reason"] == KB_PATH_TRAVERSAL_REASON:
            localized["reason"] = translate("knowledge_base.file.path_traversal")
        elif localized["reason"] == KB_NOT_A_FILE_REASON:
            localized["reason"] = translate("knowledge_base.file.not_a_file")
    return localized


def _raise_kb_error(request: Request, exc: Exception) -> None:
    translate = request.state.translate
    if isinstance(exc, AuthorizationOperationError):
        message_key = (
            "auth.unauthenticated"
            if exc.http_status == status.HTTP_401_UNAUTHORIZED
            else (
                "knowledge_base.not_found"
                if exc.http_status == status.HTTP_404_NOT_FOUND
                else "knowledge_base.access_denied"
            )
        )
        raise HTTPException(
            status_code=exc.http_status,
            detail=authorization_error_detail(
                exc.error_code,
                translate(message_key),
            ),
        ) from exc
    if isinstance(exc, KnowledgeBaseNotFoundError):
        code = getattr(exc, "code", "KB_NOT_FOUND")
        details = _not_found_details(code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, details=details),
                details=details,
            ),
        ) from exc
    if isinstance(exc, KnowledgeBaseAccessDeniedError):
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, details={}),
            ),
        ) from exc
    if isinstance(exc, KnowledgeBaseConflictError):
        code = getattr(exc, "code", "KB_CONFLICT")
        details = getattr(exc, "params", {}) or _conflict_details(code)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, details=details),
                details=details,
            ),
        ) from exc
    if isinstance(exc, FileManagementException):
        localized = _localize_file_management_error(exc)
        localized["message"] = _translate_kb_message(
            translate,
            code=localized["code"],
            details=localized["details"],
        )
        localized["details"] = _translate_kb_details(
            translate,
            code=localized["code"],
            details=localized["details"],
        )
        raise HTTPException(
            status_code=exc.status_code, detail=_build_error_detail(**localized)
        ) from exc
    if isinstance(exc, VersionControlError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=version_control_error_envelope(exc),
        ) from exc
    if isinstance(exc, ValueError):
        message = str(exc)
        known_codes = {
            "KB_VERSION_CONTROL_DISABLED",
            "GIT_REPO_NOT_FOUND",
            "GIT_NO_CHANGES",
            "GIT_PATH_OUTSIDE_REPOSITORY",
            "GIT_REPOSITORY_ALREADY_INITIALIZED",
            "VC_REPOSITORY_ALREADY_INITIALIZED",
            "VC_CLONE_TARGET_NOT_EMPTY",
            "VC_REMOTE_URL_INVALID",
            "VC_REMOTE_URL_CREDENTIALS_NOT_ALLOWED",
            "VC_SSH_KEY_REQUIRED",
            "KB_GIT_OPERATION_IN_PROGRESS",
        }
        code = (
            message
            if message in known_codes
            else getattr(exc, "code", "KB_INVALID_REQUEST")
        )
        status_code = (
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if code == "RESOURCE_DELETE_CONFIRMATION_MISMATCH"
            else (
                status.HTTP_409_CONFLICT
                if code
                in {
                    "KB_GIT_OPERATION_IN_PROGRESS",
                    "VC_REPOSITORY_ALREADY_INITIALIZED",
                    "VC_CLONE_TARGET_NOT_EMPTY",
                }
                else status.HTTP_400_BAD_REQUEST
            )
        )
        raise HTTPException(
            status_code=status_code,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, details={}),
                details=getattr(exc, "params", {}),
            ),
        ) from exc
    if isinstance(exc, GitCommandError):
        code = "KB_GIT_OPERATION_FAILED"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, details={}),
                details={},
            ),
        ) from exc
    raise exc


def _build_error_detail(
    *, code: str, message: str, details: dict | None = None
) -> dict:
    # NOTE: the JSON envelope key is `errorCode` (consistent with workspace-runtime
    # and marketplace). `code` here is only the internal parameter/variable name.
    return {
        "errorCode": code,
        "message": message,
        "details": details or {},
    }


def _conflict_details(code: str) -> dict:
    if code in {
        "KB_ALREADY_ATTACHED",
        "KB_MOUNT_ALIAS_CONFLICT",
    }:
        return {"resource": "knowledge_base_attachment"}
    return {"resource": "knowledge_base"}


def _not_found_details(code: str) -> dict:
    resource_mapping = {
        "KB_NOT_FOUND": "knowledge_base",
        "KB_ATTACHMENT_NOT_FOUND": "knowledge_base_attachment",
        "KB_SHARE_TARGET_NOT_FOUND": "knowledge_base_share_target",
        "WORKSPACE_NOT_FOUND": "workspace",
    }
    return {"resource": resource_mapping.get(code, "knowledge_base")}


def _localize_file_management_error(exc: FileManagementException) -> dict:
    details = dict(exc.details)
    code = exc.code

    if code == "INVALID_PATH":
        reason = details.get("reason")
        if reason == KB_PATH_TRAVERSAL_REASON:
            details["reason"] = KB_PATH_TRAVERSAL_REASON
        elif reason == KB_NOT_A_FILE_REASON:
            details["reason"] = KB_NOT_A_FILE_REASON

    return {
        "code": code,
        "message": exc.message,
        "details": details,
    }


@router.get(
    "",
    response_model=KnowledgeBaseListResponse,
    summary="List knowledge bases visible to current user",
    responses=_build_kb_responses(401, 500),
)
def list_knowledge_bases(
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseListResponse:
    rows = service.list_accessible(actor=actor)
    return KnowledgeBaseListResponse(
        items=[
            _to_summary(
                kb,
                access_role,
                current_user_id=actor.user_id,
                service=service,
            )
            for kb, access_role in rows
        ]
    )


@router.post(
    "",
    response_model=KnowledgeBaseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create knowledge base",
    responses=_build_kb_responses(400, 401, 409, 500),
)
def create_knowledge_base(
    request: Request,
    payload: KnowledgeBaseCreateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb = service.create_kb(
            actor=actor,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        return KnowledgeBaseDetail(
            **_to_summary(
                kb,
                ResourceAccessRole.OWNER,
                current_user_id=actor.user_id,
                service=service,
            ).model_dump()
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}",
    response_model=KnowledgeBaseDetail,
    summary="Get knowledge base details",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        return KnowledgeBaseDetail(
            **_to_summary(
                kb,
                access.access_role,
                current_user_id=actor.user_id,
                service=service,
            ).model_dump()
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.patch(
    "/{kb_id}",
    response_model=KnowledgeBaseDetail,
    summary="Update knowledge base",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_knowledge_base(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseUpdateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        if payload.name is not None:
            kb = service.rename_kb(actor=actor, kb_id=kb_id, name=payload.name)
        if payload.description is not None:
            kb = service.update_description(
                actor=actor, kb_id=kb_id, description=payload.description
            )
        return KnowledgeBaseDetail(
            **_to_summary(
                kb,
                access.access_role,
                current_user_id=actor.user_id,
                service=service,
            ).model_dump()
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.patch(
    "/{kb_id}/visibility",
    response_model=KnowledgeBaseDetail,
    summary="Update knowledge base visibility",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_knowledge_base_visibility(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseVisibilityUpdateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        knowledge_base = service.update_visibility(
            actor=actor,
            kb_id=kb_id,
            visibility=payload.visibility,
            correlation_id=request.state.correlation_id,
        )
        access = service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )[1]
        return KnowledgeBaseDetail(
            **_to_summary(
                knowledge_base,
                access.access_role,
                current_user_id=actor.user_id,
                service=service,
            ).model_dump()
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}",
    response_model=KnowledgeBaseDetail,
    summary="Delete knowledge base",
    responses=_build_kb_responses(401, 403, 404, 409, 422, 500),
)
def delete_knowledge_base(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseDeleteRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_DELETE,
        )
        deleted = service.delete_kb(
            actor=actor,
            kb_id=kb_id,
            confirmation_name=payload.confirmation_name,
            correlation_id=request.state.correlation_id,
            root_correlation_id=getattr(
                request.state,
                "root_correlation_id",
                request.state.correlation_id,
            ),
        )
        return KnowledgeBaseDetail(
            **_to_summary(
                deleted,
                access.access_role,
                current_user_id=actor.user_id,
                service=service,
            ).model_dump()
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/tree",
    response_model=FileTreeResponse,
    summary="Get knowledge base file tree",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_file_tree(
    kb_id: str,
    request: Request,
    path: str = Query("/", description="Relative path"),
    include_hidden: bool = Query(False, alias="includeHidden"),
    max_depth: int = Query(1, alias="maxDepth", ge=1, le=5),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileTreeResponse:
    try:
        return service.get_tree(
            actor=actor,
            kb_id=kb_id,
            path=path,
            include_hidden=include_hidden,
            max_depth=max_depth,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/search",
    response_model=KnowledgeBaseFileSearchResponse,
    summary="Search knowledge base files",
    responses=_build_kb_responses(400, 401, 403, 404, 422, 500),
)
def search_knowledge_base_files(
    kb_id: str,
    request: Request,
    query: str = Query(..., min_length=1),
    path: str = Query("/"),
    include_content: bool = Query(True, alias="includeContent"),
    case_sensitive: bool = Query(False, alias="caseSensitive"),
    max_results: int | None = Query(None, alias="maxResults", ge=1),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> KnowledgeBaseFileSearchResponse:
    try:
        return KnowledgeBaseFileSearchResponse(
            **service.search_entries(
                actor=actor,
                kb_id=kb_id,
                query=query,
                path=path,
                include_content=include_content,
                case_sensitive=case_sensitive,
                max_results=max_results,
            )
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/content",
    response_model=None,
    summary="Read knowledge base FileContent",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_file_content(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    raw: bool = Query(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileContentResponse | Response:
    try:
        if raw:
            content, _ = service.read_file_bytes(actor=actor, kb_id=kb_id, path=path)
            media_type = mimetypes.guess_type(path)[0] or "application/octet-stream"
            return Response(content=content, media_type=media_type)
        return service.read_file(actor=actor, kb_id=kb_id, path=path)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/download",
    response_model=None,
    summary="Download a single knowledge base file",
    responses=_build_kb_responses(400, 401, 403, 404, 422, 500),
)
def download_knowledge_base_file(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileResponse:
    try:
        fs_path = service.resolve_download_path(actor=actor, kb_id=kb_id, path=path)
        return FileResponse(
            path=fs_path, filename=fs_path.name, media_type="application/octet-stream"
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/archive",
    response_model=ArchiveDownloadAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a background knowledge base archive download",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 422, 500),
)
def create_knowledge_base_archive_download(
    kb_id: str,
    payload: ArchiveDownloadRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseArchiveService = Depends(get_knowledge_base_archive_service),
) -> ArchiveDownloadAcceptedResponse:
    try:
        operation, archive_name = service.create_archive_operation(
            actor=actor,
            kb_id=kb_id,
            paths=payload.paths,
            archive_name=payload.archive_name,
        )
        background_tasks.add_task(
            service.run_archive_operation,
            kb_id=kb_id,
            operation_id=operation.operation_id,
            paths=payload.paths,
            archive_name=archive_name,
        )
        return ArchiveDownloadAcceptedResponse(
            operationId=operation.operation_id,
            status=operation.status,
            message=operation.message,
            startedAt=operation.started_at,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/archive/{operation_id}",
    response_model=ArchiveDownloadStatusResponse,
    summary="Get knowledge base archive download status",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_archive_download_status(
    kb_id: str,
    operation_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseArchiveService = Depends(get_knowledge_base_archive_service),
) -> ArchiveDownloadStatusResponse:
    try:
        return service.get_archive_status(
            actor=actor, kb_id=kb_id, operation_id=operation_id
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/archive/{operation_id}/download",
    response_model=None,
    summary="Download a completed knowledge base archive",
    responses=_build_kb_responses(401, 403, 404, 409, 500),
)
def download_knowledge_base_archive(
    kb_id: str,
    operation_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseArchiveService = Depends(get_knowledge_base_archive_service),
) -> FileResponse:
    try:
        archive_path, archive_name = service.resolve_archive_download(
            actor=actor,
            kb_id=kb_id,
            operation_id=operation_id,
        )
        return FileResponse(
            path=archive_path, filename=archive_name, media_type="application/zip"
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/extract",
    response_model=FileConflictBatchResult,
    summary="Extract a knowledge base ZIP archive",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 422, 500),
)
def extract_knowledge_base_archive(
    kb_id: str,
    payload: FileExtractExecutionRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileConflictBatchResult:
    try:
        return service.extract_archive(
            actor=actor,
            kb_id=kb_id,
            payload=payload,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.put(
    "/{kb_id}/files/content",
    summary="Write knowledge base FileContent",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 422, 500),
)
def put_knowledge_base_file_content(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseFileMutationRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.write_file(
            actor=actor,
            kb_id=kb_id,
            path=payload.path,
            content=payload.content or "",
            revision=payload.revision,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/history",
    response_model=KnowledgeBaseLocalHistoryListResponse,
    summary="List knowledge base local history entries",
    responses=_build_kb_responses(401, 403, 404, 422, 500),
)
def list_knowledge_base_file_history(
    kb_id: str,
    request: Request,
    path: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> KnowledgeBaseLocalHistoryListResponse:
    try:
        return KnowledgeBaseLocalHistoryListResponse(
            **service.list_history(
                actor=actor,
                kb_id=kb_id,
                path=path,
                limit=limit,
            )
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/history/{entry_id}/restore",
    response_model=KnowledgeBaseLocalHistoryRestoreResponse,
    summary="Restore knowledge base local history entry",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 422, 500),
)
def restore_knowledge_base_file_history(
    kb_id: str,
    entry_id: str,
    request: Request,
    payload: KnowledgeBaseLocalHistoryRestoreRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> KnowledgeBaseLocalHistoryRestoreResponse:
    try:
        return KnowledgeBaseLocalHistoryRestoreResponse(
            **service.restore_history(
                actor=actor,
                kb_id=kb_id,
                entry_id=entry_id,
                revision=payload.revision,
            )
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files",
    response_model=dict,
    summary="Create a knowledge base file or directory",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 422, 500),
)
async def post_knowledge_base_files(
    kb_id: str,
    request: Request,
    path: str = Form("/"),
    type: str = Form("directory"),
    content: str = Form(""),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
):
    try:
        return service.create_entry(
            actor=actor,
            kb_id=kb_id,
            path=path,
            entry_type=type,
            content=content,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/conflicts/preflight",
    response_model=FileConflictPreflightResponse,
    summary="Preflight knowledge base file conflicts",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 422, 500),
)
def preflight_knowledge_base_file_conflicts(
    kb_id: str,
    payload: FileConflictPreflightRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileConflictPreflightResponse:
    try:
        return service.preflight_conflicts(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/upload",
    response_model=FileConflictBatchResult,
    summary="Upload knowledge base files",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 422, 500),
)
async def upload_knowledge_base_files(
    kb_id: str,
    request: Request,
    target_path: str = Form(..., alias="targetPath"),
    default_strategy: ConflictStrategy = Form(..., alias="defaultStrategy"),
    resolutions: str = Form(...),
    files: list[UploadFile] = File(...),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileConflictBatchResult:
    try:
        parsed_resolutions = _FILE_CONFLICT_RESOLUTIONS.validate_json(resolutions)
        return await service.upload_files(
            actor=actor,
            kb_id=kb_id,
            target_path=target_path,
            files=files,
            default_strategy=default_strategy,
            resolutions=parsed_resolutions,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/paste",
    response_model=FileConflictBatchResult,
    summary="Paste knowledge base files",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 422, 500),
)
def paste_knowledge_base_files(
    kb_id: str,
    payload: FileConflictExecutionRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileConflictBatchResult:
    try:
        return service.paste_entries(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/move",
    summary="Move or rename knowledge base file",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 422, 500),
)
def move_knowledge_base_files(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseFilePatchRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.move_entry(
            actor=actor,
            kb_id=kb_id,
            source_path=payload.source_path,
            dest_path=payload.destination_path,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}/files",
    summary="Delete knowledge base file or folder",
    responses=_build_kb_responses(400, 401, 403, 404, 422, 500),
)
def delete_knowledge_base_files(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    recursive: bool = Query(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.delete_entry(
            actor=actor,
            kb_id=kb_id,
            path=path,
            recursive=recursive,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/sources",
    response_model=KnowledgeBaseSourceUploadResponse,
    summary="Upload a knowledge base source file",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
async def upload_knowledge_base_source(
    kb_id: str,
    request: Request,
    file: UploadFile = File(...),
    target_name: str | None = Form(None, alias="targetName"),
    overwrite: bool = Form(False),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSourceService = Depends(get_knowledge_base_source_service),
) -> KnowledgeBaseSourceUploadResponse:
    temp_path: Path | None = None
    try:
        if not file.filename:
            raise ValueError("KB_INVALID_REQUEST")
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            while chunk := await file.read(1024 * 1024):
                temp_file.write(chunk)

        source = service.import_file(
            actor=actor,
            kb_id=kb_id,
            source_file=temp_path,
            target_name=target_name or file.filename,
            overwrite=overwrite,
        )
        return KnowledgeBaseSourceUploadResponse(source=source)
    except Exception as exc:
        _raise_kb_error(request, exc)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


@router.post(
    "/{kb_id}/sources/web-clip",
    response_model=KnowledgeBaseWebClipImportResponse,
    summary="Import a knowledge base web clip source",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def import_knowledge_base_web_clip(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseWebClipImportRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSourceService = Depends(get_knowledge_base_source_service),
) -> KnowledgeBaseWebClipImportResponse:
    try:
        assets = {
            name: content.encode("utf-8")
            for name, content in (payload.assets or {}).items()
        }
        return service.import_web_clip(
            actor=actor,
            kb_id=kb_id,
            title=payload.title,
            markdown=payload.markdown,
            assets=assets,
            clip_slug=payload.clip_slug,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/query",
    response_model=KnowledgeBaseQueryResponse,
    summary="Query knowledge base context",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def query_knowledge_base(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseQueryRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseQueryService = Depends(get_knowledge_base_query_service),
) -> KnowledgeBaseQueryResponse:
    try:
        return service.query(
            actor=actor,
            kb_id=kb_id,
            query=payload.query,
            limit=payload.limit,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/repository",
    response_model=GitRepositoryStatus,
    summary="Get knowledge base Git repository status",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_git_repository_status(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitRepositoryStatus:
    try:
        return service.repository_status(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/init",
    response_model=VersionControlStatus,
    summary="Initialize knowledge base Git version control",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def enable_knowledge_base_git_repository(
    kb_id: str,
    request: Request,
    payload: RepositoryInitializeRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlStatus:
    try:
        return service.enable(
            actor=actor,
            kb_id=kb_id,
            default_branch=payload.default_branch,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/clone",
    response_model=VersionControlStatus,
    summary="Clone a repository into the knowledge base root",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def clone_knowledge_base_git_repository(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseGitCloneRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlStatus:
    try:
        return service.clone(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/remote-branches",
    response_model=RemoteBranchesResponse,
    summary="List remote knowledge base repository branches",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def list_knowledge_base_remote_branches(
    kb_id: str,
    request: Request,
    payload: RemoteBranchesRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> RemoteBranchesResponse:
    try:
        return service.remote_branches(
            actor=actor,
            kb_id=kb_id,
            remote_url=payload.remote_url,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/lfs",
    response_model=LfsPatternsResponse,
    summary="Get knowledge base Git LFS patterns",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_git_lfs_patterns(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> LfsPatternsResponse:
    try:
        return service.get_lfs_patterns(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/lfs",
    response_model=BranchMutationResponse,
    summary="Update knowledge base Git LFS patterns",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def update_knowledge_base_git_lfs_patterns(
    kb_id: str,
    request: Request,
    payload: LfsPatternsUpdateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.update_lfs_patterns(
            actor=actor,
            kb_id=kb_id,
            patterns=payload.patterns,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/lfs/preview",
    response_model=LfsSnapshotPreviewResponse,
    summary="Preview knowledge base Git LFS snapshot conversion",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def preview_knowledge_base_git_lfs_snapshot(
    kb_id: str,
    request: Request,
    payload: LfsSnapshotPreviewRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> LfsSnapshotPreviewResponse:
    try:
        return service.preview_lfs_snapshot(
            actor=actor,
            kb_id=kb_id,
            patterns=payload.patterns,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/lfs/convert",
    response_model=BranchMutationResponse,
    summary="Convert knowledge base files to Git LFS pointers",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def convert_knowledge_base_git_lfs_snapshot(
    kb_id: str,
    request: Request,
    payload: LfsSnapshotConvertRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.convert_lfs_snapshot(
            actor=actor,
            kb_id=kb_id,
            paths=payload.paths,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/remote",
    response_model=RemoteSettingsResponse,
    summary="Get knowledge base Git origin settings",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_git_remote_settings(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> RemoteSettingsResponse:
    try:
        return service.get_remote_settings(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.put(
    "/{kb_id}/version-control/remote",
    response_model=BranchMutationResponse,
    summary="Set knowledge base Git origin URL",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def set_knowledge_base_git_remote_url(
    kb_id: str,
    request: Request,
    payload: GitRemoteUrlRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.set_remote_url(actor=actor, kb_id=kb_id, url=payload.url)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/status",
    response_model=VersionControlStatus,
    summary="Get knowledge base Git file status",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_status(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlStatus:
    try:
        return service.get_version_control_status(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/operation-status",
    response_model=VersionControlOperationStatus,
    summary="Get knowledge base Git operation status",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_operation_status(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlOperationStatus:
    try:
        return service.get_operation_status(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/operation/cancel",
    response_model=BranchMutationResponse,
    summary="Cancel active knowledge base Git operation",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def cancel_knowledge_base_version_control_operation(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.cancel_operation(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/changes",
    response_model=VersionControlChangesResponse,
    summary="Get knowledge base Git file changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    group: Literal["all", "staged", "unstaged", "untracked", "conflicts"] = Query("all"),
    include_stats: bool = Query(
        True,
        alias="includeStats",
        description="When false, additions/deletions are null (deferred to /changes/numstat)",
    ),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlChangesResponse:
    try:
        return service.get_file_changes(
            actor=actor,
            kb_id=kb_id,
            cursor=cursor,
            limit=limit,
            group=group,
            include_stats=include_stats,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/changes/numstat",
    response_model=NumstatResponse,
    summary="Get deferred numstat for visible knowledge base paths",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_changes_numstat(
    kb_id: str,
    request: Request,
    payload: NumstatRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> NumstatResponse:
    try:
        return service.get_file_changes_numstat(
            actor=actor,
            kb_id=kb_id,
            staged_paths=payload.stagedPaths,
            unstaged_paths=payload.unstagedPaths,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/stage",
    response_model=StageResponse,
    summary="Stage knowledge base Git files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def stage_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: StageRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> StageResponse:
    try:
        return service.stage(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/unstage",
    response_model=UnstageResponse,
    summary="Unstage knowledge base Git files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def unstage_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: UnstageRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> UnstageResponse:
    try:
        return service.unstage(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/discard",
    response_model=DiscardResponse,
    summary="Discard knowledge base Git file changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def discard_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: DiscardRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> DiscardResponse:
    try:
        return service.discard(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/commit",
    response_model=CommitResponse,
    summary="Commit knowledge base Git changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def commit_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: GitCommitRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> CommitResponse:
    try:
        return service.commit(
            actor=actor,
            kb_id=kb_id,
            message=payload.message,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/commits",
    response_model=CommitListResponse,
    summary="List knowledge base Git commits",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def list_knowledge_base_version_control_commits(
    kb_id: str,
    request: Request,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    query_scope: Literal["current", "all", "local", "remote"] = Query(
        "current", alias="queryScope"
    ),
    branch: str | None = Query(None),
    search: str | None = Query(None),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> CommitListResponse:
    try:
        return service.list_commits(
            actor=actor,
            kb_id=kb_id,
            cursor=cursor,
            limit=limit,
            query_scope=query_scope,
            branch=branch,
            search=search,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/commits/{commit_id}/files",
    response_model=CommitFilesResponse,
    summary="Get knowledge base Git commit files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_commit_files(
    kb_id: str,
    commit_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> CommitFilesResponse:
    try:
        return service.get_commit_files(actor=actor, kb_id=kb_id, commit_id=commit_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/diff",
    response_model=DiffResponse,
    summary="Get knowledge base Git file diff",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_diff(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    head: str = Query("WORKTREE"),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> DiffResponse:
    try:
        return service.diff(actor=actor, kb_id=kb_id, path=path, head=head)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/blob",
    response_model=BlobResponse,
    summary="Read knowledge base Git file blob",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_blob(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    revision: str | None = Query(None),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BlobResponse:
    try:
        return service.blob(actor=actor, kb_id=kb_id, path=path, revision=revision)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/version-control/branches",
    response_model=VersionControlBranchListResponse,
    summary="List knowledge base Git branches",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def list_knowledge_base_version_control_branches(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> VersionControlBranchListResponse:
    try:
        return service.list_branches(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/branches/create",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def create_knowledge_base_version_control_branch(
    kb_id: str,
    payload: BranchCreateRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.create_branch_and_switch(
            actor=actor,
            kb_id=kb_id,
            name=payload.name,
            start_point=payload.start_point,
            upstream=payload.upstream,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/branches/switch",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def switch_knowledge_base_version_control_branch(
    kb_id: str,
    payload: BranchSwitchRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.switch_branch(actor=actor, kb_id=kb_id, name=payload.name)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/branches/rename",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def rename_knowledge_base_version_control_branch(
    kb_id: str,
    payload: BranchRenameRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.rename_branch(
            actor=actor,
            kb_id=kb_id,
            old_name=payload.old_name,
            new_name=payload.new_name,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/branches/delete",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def delete_knowledge_base_version_control_branch(
    kb_id: str,
    payload: BranchDeleteRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.delete_branch(actor=actor, kb_id=kb_id, name=payload.name)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/branches/publish",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def publish_knowledge_base_version_control_branch(
    kb_id: str,
    payload: BranchPublishRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.publish_branch(
            actor=actor,
            kb_id=kb_id,
            remote=payload.remote,
            remote_name=payload.remote_name,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/fetch",
    response_model=RemoteResponse,
    summary="Fetch knowledge base Git remote references",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def fetch_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: RemoteRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> RemoteResponse:
    try:
        return service.fetch(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/pull",
    response_model=RemoteResponse,
    summary="Pull knowledge base Git remote changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def pull_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: RemoteRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> RemoteResponse:
    try:
        return service.pull(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/push",
    response_model=RemoteResponse,
    summary="Push knowledge base Git changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def push_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: RemoteRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> RemoteResponse:
    try:
        return service.push(actor=actor, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/commits/revert",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def revert_knowledge_base_version_control_commit(
    kb_id: str,
    payload: CommitRevertRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.revert_commit(actor=actor, kb_id=kb_id, commit_id=payload.sha)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/conflicts/mark-resolved",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def mark_knowledge_base_version_control_conflicts_resolved(
    kb_id: str,
    payload: ConflictPathsRequest,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.mark_conflicts_resolved(
            actor=actor,
            kb_id=kb_id,
            paths=payload.paths,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/conflicts/abort",
    response_model=BranchMutationResponse,
    responses=_build_kb_responses(400, 401, 403, 404, 409),
)
def abort_knowledge_base_version_control_conflict(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    try:
        return service.abort_conflict(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/version-control/force-unlock",
    response_model=BranchMutationResponse,
    summary="Force-clear stale knowledge base Git locks",
    responses=_build_kb_responses(401, 403, 404, 409, 500),
)
def force_unlock_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> BranchMutationResponse:
    """Manually clear stale on-disk Git locks for a knowledge base.

    Returns the shared mutation result without exposing repository filesystem paths.
    """
    try:
        return service.force_unlock(actor=actor, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/share-candidate-groups",
    response_model=KnowledgeBaseShareCandidateGroupListResponse,
    summary="Search shareable user groups",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def list_share_candidate_groups(
    kb_id: str,
    request: Request,
    query: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=50),
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareCandidateGroupListResponse:
    try:
        groups = service.list_share_candidate_groups(
            actor=actor,
            kb_id=kb_id,
            query=query,
            limit=limit,
        )
        return KnowledgeBaseShareCandidateGroupListResponse(
            items=[
                KnowledgeBaseShareCandidateGroup(id=group.id, name=group.name)
                for group in groups
            ]
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/shares",
    response_model=KnowledgeBaseShareListResponse,
    summary="List knowledge base shares",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def list_knowledge_base_shares(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareListResponse:
    try:
        shares = service.list_shares(actor=actor, kb_id=kb_id)
        labels = service.resolve_share_target_labels(shares)
        return KnowledgeBaseShareListResponse(
            items=[_to_share_summary(share, labels[share.id]) for share in shares]
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/shares",
    response_model=KnowledgeBaseShareSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create knowledge base share",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def create_knowledge_base_share(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseShareCreateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareSummary:
    try:
        share = service.grant_share(
            actor=actor,
            kb_id=kb_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            role=payload.role,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
        labels = service.resolve_share_target_labels([share])
        return _to_share_summary(share, labels[share.id])
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.patch(
    "/{kb_id}/shares/{share_id}",
    response_model=KnowledgeBaseShareSummary,
    summary="Update knowledge base share",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_knowledge_base_share(
    kb_id: str,
    share_id: str,
    request: Request,
    payload: KnowledgeBaseShareUpdateRequest,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareSummary:
    try:
        share = service.update_share_role(
            actor=actor,
            kb_id=kb_id,
            share_id=share_id,
            role=payload.role,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
        labels = service.resolve_share_target_labels([share])
        return _to_share_summary(share, labels[share.id])
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge base share",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def delete_knowledge_base_share(
    kb_id: str,
    share_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> None:
    try:
        service.revoke_share(
            actor=actor,
            kb_id=kb_id,
            share_id=share_id,
            correlation_id=request.state.correlation_id,
            root_correlation_id=request.state.correlation_id,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/attachments",
    response_model=KnowledgeBaseAttachmentListResponse,
    summary="List knowledge base attachments",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def list_knowledge_base_attachments(
    kb_id: str,
    request: Request,
    actor: AuthorizationActor = Depends(get_authorization_actor),
    service: KnowledgeBaseAttachmentService = Depends(
        get_knowledge_base_attachment_service
    ),
) -> KnowledgeBaseAttachmentListResponse:
    try:
        usage = service.list_attachments_for_kb(actor=actor, kb_id=kb_id)
        return KnowledgeBaseAttachmentListResponse(
            visible_items=[
                _to_attachment_summary(attachment)
                for attachment in usage.visible_attachments
            ],
            hidden_workspace_count=usage.hidden_workspace_count,
            attachment_count=usage.attachment_count,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)
