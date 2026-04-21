"""Knowledge base API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status

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
    KnowledgeBaseListResponse,
    KnowledgeBaseShareCreateRequest,
    KnowledgeBaseShareListResponse,
    KnowledgeBaseShareSummary,
    KnowledgeBaseShareUpdateRequest,
    KnowledgeBaseSummary,
    KnowledgeBaseUpdateRequest,
)
from app.modules.auth import get_current_user_id
from app.services import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    get_knowledge_base_attachment_service,
    get_knowledge_base_file_service,
    get_knowledge_base_service,
    get_knowledge_base_sharing_service,
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

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

_KB_ERROR_EXAMPLES = {
    400: {
        "invalidFileType": {
            "summary": "白名單副檔名限制",
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
            "summary": "已 tombstone 的 KB 不可再讀取",
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
            "summary": "KB 配額超限",
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
            "summary": "重複 attach 同一個 KB",
            "value": {
                "detail": {
                    "code": "KB_ALREADY_ATTACHED",
                    "message": "Knowledge base is already attached to this workspace",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "aliasConflict": {
            "summary": "mount alias 衝突",
            "value": {
                "detail": {
                    "code": "KB_MOUNT_ALIAS_CONFLICT",
                    "message": "Knowledge base mount alias already exists",
                    "details": {"resource": "knowledge_base_attachment"},
                }
            },
        },
        "knowledgeBaseInUse": {
            "summary": "KB 仍被 workspace 掛載",
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
            "summary": "單檔超過大小限制",
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
    400: "Knowledge base 請求不合法，例如白名單副檔名限制或路徑格式錯誤。`detail.message` 會依請求語系本地化。",
    403: "目前使用者沒有對 knowledge base 或 workspace 的操作權限。`detail.message` 會依請求語系本地化。",
    404: "指定 knowledge base、share 或 attachment 不存在，或 KB 已 tombstone。`detail.message` 會依請求語系本地化。",
    409: "Knowledge base 狀態衝突，例如配額超限、重複 attach、alias 衝突或 KB 仍被掛載。`detail.message` 會依請求語系本地化。",
    413: "上傳或寫入的單一檔案超過 `KB_SINGLE_FILE_SIZE_LIMIT`。`detail.message` 會依請求語系本地化。",
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
        code = getattr(exc, "code", "KB_INVALID_REQUEST")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail(
                code=code,
                message=_translate_kb_message(translate, code=code, fallback_message="", details={}),
                details=getattr(exc, "params", {}),
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
    summary="列出目前使用者可見的 knowledge bases",
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
    summary="建立 knowledge base",
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
    summary="取得 knowledge base 詳情",
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
    summary="更新 knowledge base",
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
    summary="刪除 knowledge base",
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
    summary="取得 knowledge base 檔案樹",
    responses=_build_kb_responses(401, 403, 404, 500),
)
def get_knowledge_base_file_tree(
    kb_id: str,
    request: Request,
    path: str = Query("/", description="相對路徑"),
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
    summary="讀取 knowledge base 檔案內容",
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
    summary="寫入 knowledge base 檔案內容",
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
    summary="建立資料夾或上傳檔案到 knowledge base",
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
    summary="移動或重新命名 knowledge base 檔案",
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


@router.delete(
    "/{kb_id}/files",
    summary="刪除 knowledge base 檔案或資料夾",
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


@router.get(
    "/{kb_id}/shares",
    response_model=KnowledgeBaseShareListResponse,
    summary="列出 knowledge base shares",
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
    summary="建立 knowledge base share",
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
    summary="更新 knowledge base share",
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
    summary="刪除 knowledge base share",
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
    summary="列出 knowledge base attachments",
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
    summary="建立 knowledge base attachment",
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
    summary="更新 knowledge base attachment",
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
    summary="刪除 knowledge base attachment",
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
