"""Knowledge base API."""

from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from git import GitCommandError

from app.core.file_management import FileContentResponse, FileManagementException, FileTreeResponse, FileUploadResponse
from app.core.openapi import build_responses
from app.models import (
    KnowledgeBaseAttachmentCreateRequest,
    KnowledgeBaseAttachmentListResponse,
    KnowledgeBaseAttachmentSummary,
    KnowledgeBaseAttachmentUpdateRequest,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseDetail,
    KnowledgeBaseErrorResponse,
    KnowledgeBaseFileMutationRequest,
    KnowledgeBaseFilePatchRequest,
    KnowledgeBaseGitEnableRequest,
    KnowledgeBaseGitLfsEnableRequest,
    KnowledgeBaseGitRevertRequest,
    KnowledgeBaseGitRollbackRequest,
    KnowledgeBaseGraphResponse,
    KnowledgeBaseIngestJobListResponse,
    KnowledgeBaseIngestJobRequest,
    KnowledgeBaseIngestJobResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseLintReportListResponse,
    KnowledgeBaseLintReportResponse,
    KnowledgeBaseQueryRequest,
    KnowledgeBaseQueryResponse,
    KnowledgeBaseQuerySaveRequest,
    KnowledgeBaseQuerySaveResponse,
    KnowledgeBaseSourceNormalizeRequest,
    KnowledgeBaseSourceNormalizeResponse,
    KnowledgeBaseSourceUploadResponse,
    KnowledgeBaseWebClipImportRequest,
    KnowledgeBaseWebClipImportResponse,
    KnowledgeBaseShareCreateRequest,
    KnowledgeBaseShareListResponse,
    KnowledgeBaseShareSummary,
    KnowledgeBaseShareUpdateRequest,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdateRequest,
    GitCommitRequest,
    GitOperationResponse,
    GitRemoteUrlRequest,
    GitRepositoryStatus,
    TemplateBlobResponse,
    TemplateChangesResponse,
    TemplateCheckoutRequest,
    TemplateCheckoutResponse,
    TemplateCommitFilesResponse,
    TemplateCommitListResponse,
    TemplateCommitResponse,
    TemplateDiffResponse,
    TemplateDiscardRequest,
    TemplateDiscardResponse,
    TemplateRemoteRequest,
    TemplateRemoteResponse,
    TemplateStageRequest,
    TemplateStageResponse,
    TemplateUnstageRequest,
    TemplateUnstageResponse,
    TemplateVersionControlBranchListResponse,
    TemplateVersionControlStatus,
)
from app.modules.auth import get_current_user_id
from app.services import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    get_knowledge_base_attachment_service,
    get_knowledge_base_file_service,
    get_knowledge_base_git_service,
    get_knowledge_base_graph_service,
    get_knowledge_base_ingest_service,
    get_knowledge_base_lint_service,
    get_knowledge_base_query_service,
    get_knowledge_base_service,
    get_knowledge_base_sharing_service,
    get_knowledge_base_source_service,
)
from app.services.knowledge_base_attachment_service import KnowledgeBaseAttachmentService
from app.services.knowledge_base_file_service import KnowledgeBaseFileService
from app.services.knowledge_base_service import (
    KB_IN_USE_MESSAGE,
    KB_NOT_FOUND_MESSAGE,
    KB_OWNER_NOT_FOUND_MESSAGE,
    KB_SHARE_CONFLICT_MESSAGE,
    KB_SHARE_INVALID_ROLE_MESSAGE,
    KB_SHARE_NOT_FOUND_MESSAGE,
    KB_SHARE_OWNER_FORBIDDEN_MESSAGE,
    KB_SLUG_REQUIRED_MESSAGE,
    KB_SLUG_CONFLICT_MESSAGE,
    KB_UNKNOWN_ROLE_MESSAGE,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
)
from app.services.knowledge_base_attachment_service import (
    KB_ALREADY_ATTACHED_MESSAGE,
    KB_ATTACHMENT_NOT_FOUND_MESSAGE,
    KB_MOUNT_ALIAS_CONFLICT_MESSAGE,
    WORKSPACE_NOT_FOUND_MESSAGE,
)
from app.services.knowledge_base_file_service import (
    KB_CONTENT_CONFLICT_MESSAGE,
    KB_INVALID_FILE_TYPE_MESSAGE,
    KB_NOT_A_FILE_REASON,
    KB_OWNER_QUOTA_EXCEEDED_MESSAGE,
    KB_PATH_TRAVERSAL_REASON,
    KB_QUOTA_EXCEEDED_MESSAGE,
)
from app.services.knowledge_base_git_service import KnowledgeBaseGitService
from app.services.knowledge_base_graph_service import KnowledgeBaseGraphService
from app.services.knowledge_base_ingest_service import KnowledgeBaseIngestService
from app.services.knowledge_base_lint_service import KnowledgeBaseLintService
from app.services.knowledge_base_query_service import KnowledgeBaseQueryService
from app.services.knowledge_base_source_service import KnowledgeBaseSourceService

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

_KB_ERROR_EXAMPLES = {
    400: {
        "invalidFileType": {
            "summary": "Whitelisted file extension restriction",
            "value": {
                "detail": {
                    "code": "INVALID_FILE_TYPE",
                    "message": "Unsupported file extension: .exe",
                    "details": {
                        "path": "/malware.exe",
                        "extension": ".exe",
                        "allowedExtensions": [".md", ".txt"],
                    },
                }
            },
        }
    },
    404: {
        "tombstonedKnowledgeBase": {
            "summary": "Tombstoned KB cannot be accessed",
            "value": {
                "detail": {
                    "code": "KB_NOT_FOUND",
                    "message": "Knowledge base not found",
                    "details": {"resource": "knowledge_base"},
                }
            },
        }
    },
    409: {
        "quotaExceeded": {
            "summary": "KB quota exceeded",
            "value": {
                "detail": {
                    "code": "KB_QUOTA_EXCEEDED",
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
                    "code": "KB_ALREADY_ATTACHED",
                    "message": "Knowledge base is already attached to this workspace",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "aliasConflict": {
            "summary": "Mount alias conflict",
            "value": {
                "detail": {
                    "code": "KB_MOUNT_ALIAS_CONFLICT",
                    "message": "Knowledge base mount alias already exists",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "knowledgeBaseInUse": {
            "summary": "KB still mounted by workspace",
            "value": {
                "detail": {
                    "code": "KB_IN_USE",
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
                    "code": "FILE_TOO_LARGE",
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
    400: "Knowledge base request is invalid, such as whitelisted file extension restriction or path format error. `detail.message` will be localized according to request language.",
    403: "Current user does not have operation permission on knowledge base or workspace. `detail.message` will be localized according to request language.",
    404: "Specified knowledge base, share, or attachment does not exist, or KB is tombstoned. `detail.message` will be localized according to request language.",
    409: "Knowledge base status conflict, such as quota exceeded, duplicate attachment, alias conflict, or KB still mounted. `detail.message` will be localized according to request language.",
    413: "Single uploaded or written file exceeds `KB_SINGLE_FILE_SIZE_LIMIT`. `detail.message` will be localized according to request language.",
}


def _build_kb_responses(*status_codes: int) -> dict[int, dict]:
    return build_responses(
        *status_codes,
        model=KnowledgeBaseErrorResponse,
        descriptions=_KB_ERROR_DESCRIPTIONS,
        examples={status_code: _KB_ERROR_EXAMPLES[status_code] for status_code in status_codes if status_code in _KB_ERROR_EXAMPLES},
    )


def _to_summary(kb, access_role: str) -> KnowledgeBaseSummary:
    return KnowledgeBaseSummary(
        id=kb.id,
        slug=kb.slug,
        name=kb.name,
        description=kb.description,
        owner_id=kb.owner_id,
        current_size_bytes=kb.current_size_bytes,
        quota_bytes=kb.quota_bytes,
        version_control_enabled=getattr(kb, "version_control_enabled", False),
        git_lfs_enabled=getattr(kb, "git_lfs_enabled", False),
        git_default_branch=getattr(kb, "git_default_branch", "main"),
        git_last_commit_sha=getattr(kb, "git_last_commit_sha", None),
        wiki_initialized_at=getattr(kb, "wiki_initialized_at", None),
        last_indexed_at=getattr(kb, "last_indexed_at", None),
        last_index_status=getattr(kb, "last_index_status", None),
        last_index_error=getattr(kb, "last_index_error", None),
        access_role=access_role,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


def _to_share_summary(share) -> KnowledgeBaseShareSummary:
    return KnowledgeBaseShareSummary(
        id=share.id,
        kb_id=share.kb_id,
        user_id=share.user_id,
        role=share.role,
        granted_by_id=share.granted_by_id,
        created_at=share.created_at,
    )


def _to_attachment_summary(attachment) -> KnowledgeBaseAttachmentSummary:
    return KnowledgeBaseAttachmentSummary(
        id=attachment.id,
        workspace_id=attachment.workspace_id,
        kb_id=attachment.kb_id,
        mount_alias=attachment.mount_alias,
        mode=attachment.mode,
        attached_by_id=attachment.attached_by_id,
        created_at=attachment.created_at,
        updated_at=attachment.updated_at,
    )


def _translate_kb_message(translate, *, code: str, fallback_message: str, details: dict) -> str:
    if code == "KB_NOT_FOUND":
        return translate("knowledge_base.not_found")
    if code == "KB_ATTACHMENT_NOT_FOUND":
        return translate("knowledge_base.attachment_not_found")
    if code == "KB_SHARE_NOT_FOUND":
        return translate("knowledge_base.share.not_found")
    if code == "KB_INGEST_JOB_NOT_FOUND":
        return translate("knowledge_base.ingest.job_not_found")
    if code == "KB_ACCESS_DENIED":
        return translate("knowledge_base.access_denied")
    if code == "KB_PERMISSION_DENIED":
        return translate("knowledge_base.permission_denied")
    if code == "KB_ALREADY_ATTACHED":
        return translate("knowledge_base.already_attached")
    if code == "KB_MOUNT_ALIAS_CONFLICT":
        return translate("knowledge_base.alias_conflict")
    if code == "KB_IN_USE":
        return translate("knowledge_base.in_use")
    if code == "KB_SLUG_CONFLICT":
        return translate("knowledge_base.slug_conflict")
    if code == "KB_SHARE_CONFLICT":
        return translate("knowledge_base.share.conflict")
    if code == "KB_INVALID_SHARE_TARGET":
        return translate("knowledge_base.share.owner_forbidden")
    if code == "KB_INVALID_SHARE_ROLE":
        return translate("knowledge_base.invalid.share_role")
    if code == "KB_INVALID_SLUG":
        return translate("knowledge_base.invalid.slug")
    if code == "KB_OWNER_NOT_FOUND":
        return translate("knowledge_base.invalid.owner")
    if code == "KB_INVALID_ROLE":
        return translate("knowledge_base.invalid.role")
    if code == "KB_CONFLICT":
        return translate("knowledge_base.conflict")
    if code == "KB_INVALID_REQUEST":
        return translate("knowledge_base.invalid.request")
    if code == "FILE_NOT_FOUND":
        return translate("knowledge_base.file.not_found", path=details.get("path", ""))
    if code == "FILE_ALREADY_EXISTS":
        return translate("knowledge_base.file.exists", path=details.get("path", ""))
    if code == "INVALID_PATH":
        return translate("knowledge_base.file.invalid_path")
    if code == "FILE_TOO_LARGE":
        return translate("knowledge_base.file.too_large")
    if code == "CONTENT_CONFLICT":
        return translate("knowledge_base.file.content_conflict")
    if code == "DIRECTORY_NOT_EMPTY":
        return translate("knowledge_base.file.directory_not_empty")
    if code == "INVALID_FILE_TYPE":
        return translate("knowledge_base.file.invalid_type", extension=details.get("extension", ""))
    if code == "KB_QUOTA_EXCEEDED":
        return translate("knowledge_base.file.kb_quota_exceeded")
    if code == "USER_KB_QUOTA_EXCEEDED":
        return translate("knowledge_base.file.owner_quota_exceeded")
    if code == "KB_VERSION_CONTROL_DISABLED":
        return translate("knowledge_base.git.version_control_disabled")
    if code == "GIT_REPO_NOT_FOUND":
        return translate("knowledge_base.git.repo_not_found")
    if code == "GIT_NO_CHANGES":
        return translate("knowledge_base.git.no_changes_to_commit")
    if code == "GIT_PATH_OUTSIDE_REPOSITORY":
        return translate("knowledge_base.git.path_outside_repository")
    if code == "GIT_REPOSITORY_ALREADY_INITIALIZED":
        return translate("knowledge_base.git.repository_already_initialized")
    if code == "KB_GIT_ROLLBACK_CONFIRMATION_REQUIRED":
        return translate("knowledge_base.git.rollback_confirmation_required")
    if code == "KB_GIT_OPERATION_FAILED":
        return translate("knowledge_base.git.operation_failed")
    return translate("knowledge_base.unexpected_error")


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
    if isinstance(exc, KnowledgeBaseNotFoundError):
        code = getattr(exc, "code", "KB_NOT_FOUND")
        details = _not_found_details(code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details=details),
                details=details,
            ),
        ) from exc
    if isinstance(exc, LookupError):
        code = "KB_INGEST_JOB_NOT_FOUND"
        details = _not_found_details(code)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details=details),
                details=details,
            ),
        ) from exc
    if isinstance(exc, KnowledgeBaseAccessDeniedError):
        code = getattr(exc, "code", "KB_ACCESS_DENIED")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details={}),
            ),
        ) from exc
    if isinstance(exc, KnowledgeBaseConflictError):
        code = getattr(exc, "code", "KB_CONFLICT")
        details = _conflict_details(code)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details=details),
                details=details,
            ),
        ) from exc
    if isinstance(exc, FileManagementException):
        localized = _localize_file_management_error(exc)
        localized["message"] = _translate_kb_message(
            translate,
            code=localized["code"],
            fallback_message=localized["message"],
            details=localized["details"],
        )
        localized["details"] = _translate_kb_details(
            translate,
            code=localized["code"],
            details=localized["details"],
        )
        raise HTTPException(status_code=exc.status_code, detail=_build_error_detail(**localized)) from exc
    if isinstance(exc, ValueError):
        message = str(exc)
        known_codes = {
            "KB_VERSION_CONTROL_DISABLED",
            "GIT_REPO_NOT_FOUND",
            "GIT_NO_CHANGES",
            "GIT_PATH_OUTSIDE_REPOSITORY",
            "GIT_REPOSITORY_ALREADY_INITIALIZED",
            "KB_GIT_ROLLBACK_CONFIRMATION_REQUIRED",
        }
        code = message if message in known_codes else getattr(exc, "code", "KB_INVALID_REQUEST")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details={}),
                details=getattr(exc, "params", {}),
            ),
        ) from exc
    if isinstance(exc, GitCommandError):
        code = "KB_GIT_OPERATION_FAILED"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details={}),
                details={},
            ),
        ) from exc
    raise exc


def _build_error_detail(*, code: str, message: str, details: dict | None = None) -> dict:
    return {
        "code": code,
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
        "KB_SHARE_NOT_FOUND": "knowledge_base_share",
        "KB_INGEST_JOB_NOT_FOUND": "knowledge_base_ingest_job",
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseListResponse:
    rows = service.list_accessible(user_id=current_user_id)
    return KnowledgeBaseListResponse(items=[_to_summary(kb, access_role) for kb, access_role in rows])


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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb = service.create_kb(
            owner_id=current_user_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            quota_bytes=payload.quota_bytes,
        )
        return KnowledgeBaseDetail(**_to_summary(kb, "owner").model_dump())
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb(user_id=current_user_id, kb_id=kb_id, minimum_role="viewer")
        return KnowledgeBaseDetail(**_to_summary(kb, access.access_role).model_dump())
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb(user_id=current_user_id, kb_id=kb_id, minimum_role="manager")
        if payload.name is not None:
            kb = service.rename_kb(user_id=current_user_id, kb_id=kb_id, name=payload.name)
        if payload.description is not None:
            kb = service.update_description(user_id=current_user_id, kb_id=kb_id, description=payload.description)
        return KnowledgeBaseDetail(**_to_summary(kb, access.access_role).model_dump())
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}",
    response_model=KnowledgeBaseDetail,
    summary="Delete knowledge base",
    responses=_build_kb_responses(401, 403, 404, 409, 500),
)
def delete_knowledge_base(
    kb_id: str,
    request: Request,
    force: bool = Query(False),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseService = Depends(get_knowledge_base_service),
) -> KnowledgeBaseDetail:
    try:
        kb, access = service.get_kb(user_id=current_user_id, kb_id=kb_id, minimum_role="manager")
        deleted = service.delete_kb(user_id=current_user_id, kb_id=kb_id, force=force)
        return KnowledgeBaseDetail(**_to_summary(deleted, access.access_role).model_dump())
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileTreeResponse:
    try:
        return service.get_tree(
            user_id=current_user_id,
            kb_id=kb_id,
            path=path,
            include_hidden=include_hidden,
            max_depth=max_depth,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/files/content",
    response_model=FileContentResponse,
    summary="Read knowledge base FileContent",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_file_content(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> FileContentResponse:
    try:
        return service.read_file(user_id=current_user_id, kb_id=kb_id, path=path)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.put(
    "/{kb_id}/files/content",
    summary="Write knowledge base FileContent",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def put_knowledge_base_file_content(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseFileMutationRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.write_file(
            user_id=current_user_id,
            kb_id=kb_id,
            path=payload.path,
            content=payload.content or "",
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files",
    response_model=FileUploadResponse | dict,
    summary="Create folder or upload files to knowledge base",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
async def post_knowledge_base_files(
    kb_id: str,
    request: Request,
    path: str = Form("/"),
    type: str = Form("directory"),
    content: str = Form(""),
    overwrite: bool = Form(False),
    files: list[UploadFile] | None = File(default=None),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
):
    try:
        if files:
            return await service.upload_files(
                user_id=current_user_id,
                kb_id=kb_id,
                target_path=path,
                files=files,
                overwrite=overwrite,
            )
        return service.create_entry(
            user_id=current_user_id,
            kb_id=kb_id,
            path=path,
            entry_type=type,
            content=content,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.patch(
    "/{kb_id}/files",
    summary="Move or rename knowledge base file",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def patch_knowledge_base_files(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseFilePatchRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.move_entry(
            user_id=current_user_id,
            kb_id=kb_id,
            source_path=payload.source_path,
            dest_path=payload.destination_path,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/files/copy",
    summary="Copy knowledge base file or folder",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def copy_knowledge_base_files(
    kb_id: str,
    request: Request,
    source_path: str = Query(...),
    dest_path: str = Query(...),
    overwrite: bool = Query(False),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.copy_entry(
            user_id=current_user_id,
            kb_id=kb_id,
            source_path=source_path,
            dest_path=dest_path,
            overwrite=overwrite,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}/files",
    summary="Delete knowledge base file or folder",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def delete_knowledge_base_files(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    recursive: bool = Query(False),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseFileService = Depends(get_knowledge_base_file_service),
) -> dict:
    try:
        return service.delete_entry(
            user_id=current_user_id,
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
    target_subdir: str = Form("uploads", alias="targetSubdir"),
    target_name: str | None = Form(None, alias="targetName"),
    overwrite: bool = Form(False),
    normalize: bool = Form(True),
    current_user_id: str = Depends(get_current_user_id),
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
            user_id=current_user_id,
            kb_id=kb_id,
            source_file=temp_path,
            target_subdir=target_subdir,
            target_name=target_name or file.filename,
            overwrite=overwrite,
        )
        normalization = None
        if normalize and Path(source.path).suffix.lower() != ".pdf":
            normalization = service.normalize_source(
                user_id=current_user_id,
                kb_id=kb_id,
                source_path=source.path,
                force=overwrite,
            )
        return KnowledgeBaseSourceUploadResponse(source=source, normalization=normalization)
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSourceService = Depends(get_knowledge_base_source_service),
) -> KnowledgeBaseWebClipImportResponse:
    try:
        assets = {name: content.encode("utf-8") for name, content in (payload.assets or {}).items()}
        return service.import_web_clip(
            user_id=current_user_id,
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
    "/{kb_id}/sources/normalize",
    response_model=KnowledgeBaseSourceNormalizeResponse,
    summary="Normalize a knowledge base source file",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def normalize_knowledge_base_source(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseSourceNormalizeRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSourceService = Depends(get_knowledge_base_source_service),
) -> KnowledgeBaseSourceNormalizeResponse:
    try:
        return service.normalize_source(
            user_id=current_user_id,
            kb_id=kb_id,
            source_path=payload.source_path,
            force=payload.force,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/ingest",
    response_model=KnowledgeBaseIngestJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a knowledge base ingest job",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def create_knowledge_base_ingest_job(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseIngestJobRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseIngestService = Depends(get_knowledge_base_ingest_service),
) -> KnowledgeBaseIngestJobResponse:
    try:
        return service.create_job(
            user_id=current_user_id,
            kb_id=kb_id,
            source_paths=payload.source_paths,
            force=payload.force,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/jobs",
    response_model=KnowledgeBaseIngestJobListResponse,
    summary="List knowledge base ingest jobs",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def list_knowledge_base_ingest_jobs(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseIngestService = Depends(get_knowledge_base_ingest_service),
) -> KnowledgeBaseIngestJobListResponse:
    try:
        return KnowledgeBaseIngestJobListResponse(items=service.list_jobs(user_id=current_user_id, kb_id=kb_id))
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/jobs/{job_id}",
    response_model=KnowledgeBaseIngestJobResponse,
    summary="Get knowledge base ingest job",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_ingest_job(
    kb_id: str,
    job_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseIngestService = Depends(get_knowledge_base_ingest_service),
) -> KnowledgeBaseIngestJobResponse:
    try:
        return service.get_job(user_id=current_user_id, kb_id=kb_id, job_id=job_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/jobs/{job_id}/retry",
    response_model=KnowledgeBaseIngestJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Retry a knowledge base ingest job",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 413, 500),
)
def retry_knowledge_base_ingest_job(
    kb_id: str,
    job_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseIngestService = Depends(get_knowledge_base_ingest_service),
) -> KnowledgeBaseIngestJobResponse:
    try:
        return service.retry_job(user_id=current_user_id, kb_id=kb_id, job_id=job_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/jobs/{job_id}/cancel",
    response_model=KnowledgeBaseIngestJobResponse,
    summary="Cancel a knowledge base ingest job",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def cancel_knowledge_base_ingest_job(
    kb_id: str,
    job_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseIngestService = Depends(get_knowledge_base_ingest_service),
) -> KnowledgeBaseIngestJobResponse:
    try:
        return service.cancel_job(user_id=current_user_id, kb_id=kb_id, job_id=job_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/query",
    response_model=KnowledgeBaseQueryResponse,
    summary="Query knowledge base wiki context",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def query_knowledge_base(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseQueryRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseQueryService = Depends(get_knowledge_base_query_service),
) -> KnowledgeBaseQueryResponse:
    try:
        return service.query(
            user_id=current_user_id,
            kb_id=kb_id,
            query=payload.query,
            limit=payload.limit,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/query/save",
    response_model=KnowledgeBaseQuerySaveResponse,
    summary="Save a knowledge base query answer to wiki",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def save_knowledge_base_query_answer(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseQuerySaveRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseQueryService = Depends(get_knowledge_base_query_service),
) -> KnowledgeBaseQuerySaveResponse:
    try:
        return service.save_answer_to_wiki(
            user_id=current_user_id,
            kb_id=kb_id,
            query=payload.query,
            answer=payload.answer,
            citations=payload.citations,
            title=payload.title,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/lint",
    response_model=KnowledgeBaseLintReportResponse,
    summary="Run knowledge base structural lint",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def run_knowledge_base_lint(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseLintService = Depends(get_knowledge_base_lint_service),
) -> KnowledgeBaseLintReportResponse:
    try:
        return service.run_structural_lint(user_id=current_user_id, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/lint/reports",
    response_model=KnowledgeBaseLintReportListResponse,
    summary="List knowledge base lint reports",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def list_knowledge_base_lint_reports(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseLintService = Depends(get_knowledge_base_lint_service),
) -> KnowledgeBaseLintReportListResponse:
    try:
        return KnowledgeBaseLintReportListResponse(items=service.list_reports(user_id=current_user_id, kb_id=kb_id))
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/lint/reports/content",
    response_model=KnowledgeBaseLintReportResponse,
    summary="Read knowledge base lint report",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_lint_report(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseLintService = Depends(get_knowledge_base_lint_service),
) -> KnowledgeBaseLintReportResponse:
    try:
        return service.get_report(user_id=current_user_id, kb_id=kb_id, report_path=path)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/graph",
    response_model=KnowledgeBaseGraphResponse,
    summary="Get knowledge base wiki graph",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_graph(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGraphService = Depends(get_knowledge_base_graph_service),
) -> KnowledgeBaseGraphResponse:
    try:
        return service.build_graph(user_id=current_user_id, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/repository/status",
    response_model=GitRepositoryStatus,
    summary="Get knowledge base Git repository status",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_git_repository_status(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitRepositoryStatus:
    try:
        return service.repository_status(user_id=current_user_id, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/repository/enable",
    response_model=GitRepositoryStatus,
    summary="Enable knowledge base Git version control",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def enable_knowledge_base_git_repository(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseGitEnableRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitRepositoryStatus:
    try:
        return service.enable(
            user_id=current_user_id,
            kb_id=kb_id,
            default_branch=payload.default_branch,
            initial_message=payload.initial_message,
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/lfs/enable",
    response_model=GitOperationResponse,
    summary="Enable knowledge base Git LFS tracking",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def enable_knowledge_base_git_lfs(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseGitLfsEnableRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitOperationResponse:
    try:
        service.enable_lfs(user_id=current_user_id, kb_id=kb_id, patterns=payload.patterns)
        return GitOperationResponse(success=True, message=request.state.translate("knowledge_base.git.lfs_enabled"))
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/remote-url",
    response_model=GitOperationResponse,
    summary="Set knowledge base Git origin URL",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def set_knowledge_base_git_remote_url(
    kb_id: str,
    request: Request,
    payload: GitRemoteUrlRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitOperationResponse:
    try:
        service.set_remote_url(user_id=current_user_id, kb_id=kb_id, url=payload.url)
        return GitOperationResponse(success=True, message=request.state.translate("knowledge_base.git.remote_url_set"))
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/status",
    response_model=TemplateVersionControlStatus,
    summary="Get knowledge base Git file status",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_status(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateVersionControlStatus:
    try:
        return service.get_version_control_status(user_id=current_user_id, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/changes",
    response_model=TemplateChangesResponse,
    summary="Get knowledge base Git file changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize"),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateChangesResponse:
    try:
        return service.get_file_changes(user_id=current_user_id, kb_id=kb_id, page=page, page_size=page_size)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/stage",
    response_model=TemplateStageResponse,
    summary="Stage knowledge base Git files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def stage_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: TemplateStageRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateStageResponse:
    try:
        return service.stage(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/unstage",
    response_model=TemplateUnstageResponse,
    summary="Unstage knowledge base Git files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def unstage_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: TemplateUnstageRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateUnstageResponse:
    try:
        return service.unstage(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/discard",
    response_model=TemplateDiscardResponse,
    summary="Discard knowledge base Git file changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def discard_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: TemplateDiscardRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateDiscardResponse:
    try:
        return service.discard(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/commit",
    response_model=TemplateCommitResponse,
    summary="Commit knowledge base Git changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def commit_knowledge_base_version_control_changes(
    kb_id: str,
    request: Request,
    payload: GitCommitRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateCommitResponse:
    try:
        return service.commit(user_id=current_user_id, kb_id=kb_id, message=payload.message, paths=payload.paths)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/commits",
    response_model=TemplateCommitListResponse,
    summary="List knowledge base Git commits",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def list_knowledge_base_version_control_commits(
    kb_id: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateCommitListResponse:
    try:
        return service.list_commits(user_id=current_user_id, kb_id=kb_id, page=page, page_size=page_size)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/commits/{commit_id}/files",
    response_model=TemplateCommitFilesResponse,
    summary="Get knowledge base Git commit files",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_commit_files(
    kb_id: str,
    commit_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateCommitFilesResponse:
    try:
        return service.get_commit_files(user_id=current_user_id, kb_id=kb_id, commit_id=commit_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/diff",
    response_model=TemplateDiffResponse,
    summary="Get knowledge base Git file diff",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_diff(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    head: str = Query("WORKTREE"),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateDiffResponse:
    try:
        return service.diff(user_id=current_user_id, kb_id=kb_id, path=path, head=head)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/blob",
    response_model=TemplateBlobResponse,
    summary="Read knowledge base Git file blob",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def get_knowledge_base_version_control_blob(
    kb_id: str,
    request: Request,
    path: str = Query(...),
    revision: str | None = Query(None),
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateBlobResponse:
    try:
        return service.blob(user_id=current_user_id, kb_id=kb_id, path=path, revision=revision)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.get(
    "/{kb_id}/git/version-control/branches",
    response_model=TemplateVersionControlBranchListResponse,
    summary="List knowledge base Git branches",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def list_knowledge_base_version_control_branches(
    kb_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateVersionControlBranchListResponse:
    try:
        return service.list_branches(user_id=current_user_id, kb_id=kb_id)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/branches/{branch_name:path}/checkout",
    response_model=TemplateCheckoutResponse,
    summary="Switch to or create a knowledge base Git branch",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def checkout_knowledge_base_version_control_branch(
    kb_id: str,
    branch_name: str,
    request: Request,
    payload: TemplateCheckoutRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateCheckoutResponse:
    try:
        return service.checkout_branch(user_id=current_user_id, kb_id=kb_id, branch_name=branch_name, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/fetch",
    response_model=TemplateRemoteResponse,
    summary="Fetch knowledge base Git remote references",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def fetch_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateRemoteResponse:
    try:
        return service.fetch(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/pull",
    response_model=TemplateRemoteResponse,
    summary="Pull knowledge base Git remote changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def pull_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateRemoteResponse:
    try:
        return service.pull(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/push",
    response_model=TemplateRemoteResponse,
    summary="Push knowledge base Git changes",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def push_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: TemplateRemoteRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> TemplateRemoteResponse:
    try:
        return service.push(user_id=current_user_id, kb_id=kb_id, payload=payload)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/revert",
    response_model=GitOperationResponse,
    summary="Revert a knowledge base Git commit",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def revert_knowledge_base_version_control_commit(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseGitRevertRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitOperationResponse:
    try:
        service.revert_commit(user_id=current_user_id, kb_id=kb_id, commit_id=payload.commit_id)
        return GitOperationResponse(success=True, message=request.state.translate("knowledge_base.git.revert_success"))
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/git/version-control/rollback",
    response_model=GitOperationResponse,
    summary="Reset knowledge base Git repository to a revision",
    responses=_build_kb_responses(400, 401, 403, 404, 500),
)
def rollback_knowledge_base_version_control(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseGitRollbackRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseGitService = Depends(get_knowledge_base_git_service),
) -> GitOperationResponse:
    try:
        service.rollback(user_id=current_user_id, kb_id=kb_id, revision=payload.revision, confirm=payload.confirm)
        return GitOperationResponse(success=True, message=request.state.translate("knowledge_base.git.rollback_success"))
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareListResponse:
    try:
        shares = service.list_shares(user_id=current_user_id, kb_id=kb_id)
        return KnowledgeBaseShareListResponse(items=[_to_share_summary(share) for share in shares])
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareSummary:
    try:
        share = service.grant_share(
            user_id=current_user_id,
            kb_id=kb_id,
            target_user_id=payload.user_id,
            role=payload.role,
        )
        return _to_share_summary(share)
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> KnowledgeBaseShareSummary:
    try:
        share = service.update_share_role(user_id=current_user_id, share_id=share_id, role=payload.role)
        return _to_share_summary(share)
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseSharingService = Depends(get_knowledge_base_sharing_service),
) -> None:
    try:
        service.revoke_share(user_id=current_user_id, share_id=share_id)
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
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> KnowledgeBaseAttachmentListResponse:
    try:
        attachments = service.list_attachments_for_kb(user_id=current_user_id, kb_id=kb_id)
        return KnowledgeBaseAttachmentListResponse(
            items=[_to_attachment_summary(attachment) for attachment in attachments]
        )
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.post(
    "/{kb_id}/attachments",
    response_model=KnowledgeBaseAttachmentSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Create knowledge base attachment",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def create_knowledge_base_attachment(
    kb_id: str,
    request: Request,
    payload: KnowledgeBaseAttachmentCreateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> KnowledgeBaseAttachmentSummary:
    try:
        attachment = service.attach(
            user_id=current_user_id,
            workspace_id=payload.workspace_id,
            kb_id=kb_id,
            mount_alias=payload.mount_alias,
            mode=payload.mode,
        )
        return _to_attachment_summary(attachment)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.patch(
    "/{kb_id}/attachments/{attachment_id}",
    response_model=KnowledgeBaseAttachmentSummary,
    summary="Update knowledge base attachment",
    responses=_build_kb_responses(400, 401, 403, 404, 409, 500),
)
def update_knowledge_base_attachment(
    kb_id: str,
    attachment_id: str,
    request: Request,
    payload: KnowledgeBaseAttachmentUpdateRequest,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> KnowledgeBaseAttachmentSummary:
    try:
        attachment = service.update_attachment(
            user_id=current_user_id,
            attachment_id=attachment_id,
            mount_alias=payload.mount_alias,
            mode=payload.mode,
        )
        return _to_attachment_summary(attachment)
    except Exception as exc:
        _raise_kb_error(request, exc)


@router.delete(
    "/{kb_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete knowledge base attachment",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def delete_knowledge_base_attachment(
    kb_id: str,
    attachment_id: str,
    request: Request,
    current_user_id: str = Depends(get_current_user_id),
    service: KnowledgeBaseAttachmentService = Depends(get_knowledge_base_attachment_service),
) -> None:
    try:
        service.detach(user_id=current_user_id, attachment_id=attachment_id)
    except Exception as exc:
        _raise_kb_error(request, exc)
