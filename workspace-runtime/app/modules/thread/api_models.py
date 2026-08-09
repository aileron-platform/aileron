from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ThreadDraftCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    agentic_tool: str = Field(..., alias="agenticTool")
    model: str
    claude_mode: str | None = Field(None, alias="claudeMode")


class ThreadAttachmentKind(StrEnum):
    IMAGE = "image"
    PDF = "pdf"
    TEXT_FILE = "text-file"


class ThreadAttachmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attachment_id: str = Field(..., alias="attachmentId", min_length=1)


class ThreadAttachmentReference(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    attachment_id: str = Field(..., alias="attachmentId", min_length=1)
    kind: ThreadAttachmentKind
    name: str = Field(min_length=1)
    mime_type: str = Field(..., alias="mimeType", min_length=1)
    size: int = Field(ge=0)


class ThreadAttachmentUploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    attachment_id: str = Field(..., alias="attachmentId")
    kind: ThreadAttachmentKind
    name: str
    mime_type: str = Field(..., alias="mimeType")
    size: int


class ThreadAttachmentListResponse(BaseModel):
    items: list[ThreadAttachmentUploadResponse]
    total: int


class ThreadDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str
    attachments: list[ThreadAttachmentInput] = Field(default_factory=list)


class QuestionAnswerRequest(BaseModel):
    answers: dict[str, str | list[str]] = Field(default_factory=dict)
    text: str = Field(min_length=1)


class ThreadDraftPatchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    agentic_tool: str | None = Field(None, alias="agenticTool")
    model: str | None = None
    claude_mode: str | None = Field(None, alias="claudeMode")
    draft_message: ThreadDraftUpdateRequest | None = Field(None, alias="draftMessage")


class ThreadSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    user_id: str = Field(..., alias="userId")
    origin: str
    automation_job_id: str | None = Field(None, alias="automationJobId")
    automation_execution_id: str | None = Field(None, alias="automationExecutionId")
    title: str
    agentic_tool: str = Field(..., alias="agenticTool")
    model: str
    claude_mode: str | None = Field(None, alias="claudeMode")
    status: str
    version: int
    active_turn_id: str | None = Field(None, alias="activeTurnId")
    active_turn_execution_id: str | None = Field(None, alias="activeTurnExecutionId")
    git_context_id: str | None = Field(None, alias="gitContextId")
    context_tokens: int | None = Field(None, alias="contextTokens")
    context_window: int | None = Field(None, alias="contextWindow")
    archived: bool
    error_code: str | None = Field(None, alias="errorCode")
    error_info: dict[str, Any] | None = Field(None, alias="errorInfo")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class ThreadDetailResponse(ThreadSummaryResponse):
    queued_messages: list[dict[str, Any]] = Field(
        default_factory=list, alias="queuedMessages"
    )
    draft_message: dict[str, Any] | None = Field(None, alias="draftMessage")


class ThreadExecutionMetadataResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sequence: int
    agentic_tool: str = Field(..., alias="agenticTool")
    agent_resume_id: str | None = Field(None, alias="agentResumeId")
    version: int
    status: str
    error_code: str | None = Field(None, alias="errorCode")
    error_info: dict[str, Any] | None = Field(None, alias="errorInfo")
    created_at: datetime = Field(..., alias="createdAt")
    completed_at: datetime | None = Field(None, alias="completedAt")


class ThreadTurnMetadataResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sequence: int
    version: int
    status: str
    error_code: str | None = Field(None, alias="errorCode")
    error_info: dict[str, Any] | None = Field(None, alias="errorInfo")
    created_at: datetime = Field(..., alias="createdAt")
    completed_at: datetime | None = Field(None, alias="completedAt")


class TimelineToolCallResponse(BaseModel):
    name: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class TimelineToolResultResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(..., alias="messageId")
    is_error: bool = Field(..., alias="isError")
    preview: str
    byte_length: int = Field(..., alias="byteLength")
    line_count: int | None = Field(None, alias="lineCount")
    truncated: bool
    media_type: str = Field(..., alias="mediaType")


class TimelineInteractionAnswerResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str = Field(..., alias="messageId")
    answers: dict[str, str | list[str]] = Field(default_factory=dict)


class TimelineMessageItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    sequence: int
    item_version: int = Field(..., alias="itemVersion")
    turn_id: str = Field(..., alias="turnId")
    turn_execution_id: str = Field(..., alias="turnExecutionId")
    type: str
    parent_item_id: str | None = Field(None, alias="parentItemId")
    content: dict[str, Any] | None = None
    call: TimelineToolCallResponse | None = None
    provider_result: TimelineToolResultResponse | None = Field(
        None, alias="providerResult"
    )
    interaction_answer: TimelineInteractionAnswerResponse | None = Field(
        None, alias="interactionAnswer"
    )
    created_at: datetime = Field(..., alias="createdAt")


class TimelinePageInfoResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    oldest_sequence: int | None = Field(None, alias="oldestSequence")
    newest_sequence: int | None = Field(None, alias="newestSequence")
    next_before_sequence: int | None = Field(None, alias="nextBeforeSequence")
    has_more_before: bool = Field(..., alias="hasMoreBefore")


class TimelineItemsResponse(BaseModel):
    items: list[TimelineMessageItemResponse] = Field(default_factory=list)
    turns: list[ThreadTurnMetadataResponse] = Field(default_factory=list)
    executions: list[ThreadExecutionMetadataResponse] = Field(default_factory=list)


class ThreadTimelinePageResponse(TimelineItemsResponse):
    page_info: TimelinePageInfoResponse = Field(..., alias="pageInfo")


class TimelineBatchGetRequest(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=200)


class ThreadMutationResponse(ThreadDetailResponse):
    created_item_ids: list[str] = Field(default_factory=list, alias="createdItemIds")
    changed_item_ids: list[str] = Field(default_factory=list, alias="changedItemIds")
    turns: list[ThreadTurnMetadataResponse] = Field(default_factory=list)
    executions: list[ThreadExecutionMetadataResponse] = Field(default_factory=list)


class ThreadListResponse(BaseModel):
    items: list[ThreadSummaryResponse]
    total: int
