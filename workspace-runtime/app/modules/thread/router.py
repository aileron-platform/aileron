from __future__ import annotations

import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.database.session import get_async_db, get_async_session_local
from app.middleware.auth import get_current_user_id
from app.modules.thread.api_models import (
    QuestionAnswerRequest,
    ThreadAttachmentListResponse,
    ThreadAttachmentKind,
    ThreadAttachmentUploadResponse,
    ThreadDetailResponse,
    ThreadDraftCreateRequest,
    ThreadDraftPatchRequest,
    ThreadDraftUpdateRequest,
    ThreadListResponse,
    ThreadMutationResponse,
    ThreadTimelinePageResponse,
    TimelineBatchGetRequest,
    TimelineItemsResponse,
)
from app.modules.thread.attachments import (
    ThreadAttachmentError,
    ThreadAttachmentService,
    ThreadStoredAttachment,
)
from app.modules.thread.lifecycle import ThreadApiError, ThreadService

logger = logging.getLogger(__name__)


def _error_response(exc: ThreadApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "error_info": exc.error_info},
    )


def get_thread_service(db: AsyncSession = Depends(get_async_db)) -> ThreadService:
    return ThreadService(
        db,
        workspace_id=get_settings().AILERON_WORKSPACE_ID,
        attachment_service=get_thread_attachment_service(),
        event_session_factory=get_async_session_local(),
    )


def get_thread_attachment_service() -> ThreadAttachmentService:
    return ThreadAttachmentService(
        storage_root=Path(get_settings().AILERON_WORKSPACE_PATH)
        / ".aileron"
        / "thread-attachments",
    )


def _to_attachment_response(
    attachment: ThreadStoredAttachment,
) -> ThreadAttachmentUploadResponse:
    return ThreadAttachmentUploadResponse(
        attachmentId=attachment.attachment_id,
        kind=ThreadAttachmentKind(attachment.kind),
        name=attachment.name,
        mimeType=attachment.mime_type,
        size=attachment.size,
    )


router = APIRouter(prefix="/threads", tags=["threads"])


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    request: Request,
    archived: bool = False,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadListResponse:
    user_id = get_current_user_id(request)
    items = await service.list_threads(user_id=user_id, archived=archived)
    return ThreadListResponse(items=items, total=len(items))


@router.post(
    "/draft",
    response_model=ThreadDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_draft(
    payload: ThreadDraftCreateRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.create_draft(
            user_id=get_current_user_id(request),
            agentic_tool=payload.agentic_tool,
            model=payload.model,
            claude_mode=payload.claude_mode,
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.get(
    "/by-automation-execution/{execution_id}",
    response_model=ThreadDetailResponse,
)
async def get_thread_by_automation_execution(
    execution_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.get_by_automation_execution(
            automation_execution_id=execution_id,
            user_id=get_current_user_id(request),
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.get("/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.get_thread(thread_id, user_id=get_current_user_id(request))
    except ThreadApiError as exc:
        return _error_response(exc)


@router.get("/{thread_id}/timeline", response_model=ThreadTimelinePageResponse)
async def get_thread_timeline(
    thread_id: str,
    request: Request,
    before_sequence: int | None = Query(None, alias="beforeSequence", ge=1),
    limit: int = Query(100, ge=1, le=200),
    service: ThreadService = Depends(get_thread_service),
) -> ThreadTimelinePageResponse | JSONResponse:
    try:
        return await service.list_timeline(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            before_sequence=before_sequence,
            limit=limit,
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post(
    "/{thread_id}/timeline/items/batch-get",
    response_model=TimelineItemsResponse,
)
async def get_thread_timeline_items(
    thread_id: str,
    payload: TimelineBatchGetRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> TimelineItemsResponse | JSONResponse:
    try:
        return await service.get_timeline_items(
            thread_id=thread_id,
            item_ids=payload.ids,
            user_id=get_current_user_id(request),
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.get("/{thread_id}/messages/{message_id}/tool-result", response_model=None)
async def get_tool_result_content(
    thread_id: str,
    message_id: int,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> Response | JSONResponse:
    try:
        media_type, payload = await service.get_tool_result_content(
            thread_id=thread_id,
            message_id=message_id,
            user_id=get_current_user_id(request),
        )
        return Response(
            content=payload,
            media_type=media_type,
            headers={"Content-Length": str(len(payload))},
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.get(
    "/{thread_id}/attachments",
    response_model=ThreadAttachmentListResponse,
)
async def list_thread_attachments(
    thread_id: str,
    request: Request,
    thread_service: ThreadService = Depends(get_thread_service),
    attachment_service: ThreadAttachmentService = Depends(
        get_thread_attachment_service
    ),
) -> ThreadAttachmentListResponse | JSONResponse:
    try:
        await thread_service.get_thread(thread_id, user_id=get_current_user_id(request))
        attachments = attachment_service.list_attachments(thread_id)
    except ThreadApiError as exc:
        return _error_response(exc)
    return ThreadAttachmentListResponse(
        items=[_to_attachment_response(attachment) for attachment in attachments],
        total=len(attachments),
    )


@router.post(
    "/{thread_id}/attachments",
    response_model=ThreadAttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_thread_attachment(
    thread_id: str,
    request: Request,
    file: UploadFile = File(...),
    thread_service: ThreadService = Depends(get_thread_service),
    attachment_service: ThreadAttachmentService = Depends(
        get_thread_attachment_service
    ),
) -> ThreadAttachmentUploadResponse | JSONResponse:
    user_id = get_current_user_id(request)
    logger.info(
        "Thread attachment upload request received",
        extra={
            "thread_id": thread_id,
            "user_id": user_id,
            "file_name": file.filename,
            "content_type": file.content_type,
        },
    )
    try:
        await thread_service.get_thread(thread_id, user_id=user_id)
        logger.info(
            "Thread attachment upload thread verified",
            extra={"thread_id": thread_id, "user_id": user_id},
        )
        attachment = await attachment_service.save_upload(
            thread_id=thread_id,
            upload=file,
        )
    except ThreadApiError as exc:
        logger.warning(
            "Thread attachment upload rejected by thread service",
            extra={
                "thread_id": thread_id,
                "user_id": user_id,
                "status_code": exc.status_code,
                "error_code": exc.error_code,
                "error_info": exc.error_info,
            },
        )
        return _error_response(exc)
    except ThreadAttachmentError as exc:
        status_code = 404 if exc.code == "attachment-not-found" else 400
        logger.warning(
            "Thread attachment upload rejected by attachment service",
            extra={
                "thread_id": thread_id,
                "user_id": user_id,
                "status_code": status_code,
                "error_code": exc.code,
                "file_name": file.filename,
                "content_type": file.content_type,
            },
        )
        return _error_response(ThreadApiError(status_code, exc.code, {}))
    logger.info(
        "Thread attachment upload succeeded",
        extra={
            "thread_id": thread_id,
            "user_id": user_id,
            "attachment_id": attachment.attachment_id,
            "kind": attachment.kind,
            "file_name": attachment.name,
            "mime_type": attachment.mime_type,
            "size": attachment.size,
        },
    )
    return _to_attachment_response(attachment)


@router.delete(
    "/{thread_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_thread_attachment(
    thread_id: str,
    attachment_id: str,
    request: Request,
    thread_service: ThreadService = Depends(get_thread_service),
    attachment_service: ThreadAttachmentService = Depends(
        get_thread_attachment_service
    ),
) -> Response:
    try:
        await thread_service.get_thread(thread_id, user_id=get_current_user_id(request))
        attachment_service.delete_attachment(thread_id, attachment_id)
    except ThreadApiError as exc:
        return _error_response(exc)
    except ThreadAttachmentError as exc:
        status_code = 404 if exc.code == "attachment-not-found" else 400
        return _error_response(ThreadApiError(status_code, exc.code, {}))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{thread_id}/draft", response_model=ThreadDetailResponse)
async def update_draft(
    thread_id: str,
    payload: ThreadDraftPatchRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        patch = payload.model_dump(exclude_unset=True)
        if payload.draft_message is not None:
            patch["draft_message"] = payload.draft_message.model_dump(
                by_alias=True,
                exclude_none=True,
            )
        return await service.update_draft(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            patch=patch,
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post("/{thread_id}/archive", response_model=ThreadDetailResponse)
async def archive_thread(
    thread_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.archive_thread(
            thread_id, user_id=get_current_user_id(request)
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.delete(
    "/{thread_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_thread(
    thread_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> Response | JSONResponse:
    try:
        await service.delete_thread(thread_id, user_id=get_current_user_id(request))
    except ThreadApiError as exc:
        return _error_response(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{thread_id}/submit", response_model=ThreadMutationResponse)
async def submit_thread(
    thread_id: str,
    payload: ThreadDraftUpdateRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadMutationResponse | JSONResponse:
    try:
        return await service.submit_thread(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            message=payload.model_dump(by_alias=True, exclude_none=True),
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post("/{thread_id}/messages", response_model=ThreadMutationResponse)
async def post_message(
    thread_id: str,
    payload: ThreadDraftUpdateRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadMutationResponse | JSONResponse:
    try:
        return await service.post_message(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            message=payload.model_dump(by_alias=True, exclude_none=True),
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.delete(
    "/{thread_id}/queued-messages/{queued_message_id}",
    response_model=ThreadDetailResponse,
)
async def delete_queued_message(
    thread_id: str,
    queued_message_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.remove_queued_message(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            queued_message_id=queued_message_id,
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post(
    "/{thread_id}/questions/{message_id}/answer",
    response_model=ThreadMutationResponse,
)
async def answer_question(
    thread_id: str,
    message_id: int,
    payload: QuestionAnswerRequest,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadMutationResponse | JSONResponse:
    try:
        return await service.answer_question(
            thread_id=thread_id,
            user_id=get_current_user_id(request),
            message_id=message_id,
            answers=payload.answers,
            text=payload.text,
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post("/{thread_id}/cancel", response_model=ThreadDetailResponse)
async def cancel_thread(
    thread_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.cancel_thread(
            thread_id=thread_id, user_id=get_current_user_id(request)
        )
    except ThreadApiError as exc:
        return _error_response(exc)


@router.post("/{thread_id}/retry", response_model=ThreadDetailResponse)
async def retry_thread(
    thread_id: str,
    request: Request,
    service: ThreadService = Depends(get_thread_service),
) -> ThreadDetailResponse | JSONResponse:
    try:
        return await service.retry_thread(
            thread_id=thread_id, user_id=get_current_user_id(request)
        )
    except ThreadApiError as exc:
        return _error_response(exc)


__all__ = ["router"]
