"""Canvas module data models"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

CanvasType = Literal["html", "nextjs", "default"]
CanvasManifestStatus = Literal["missing", "valid", "invalid"]
CanvasReviewTargetType = Literal["element", "multi-element", "area"]
CanvasReviewStatus = Literal["open", "seen", "applied", "dismissed"]
CanvasReviewReplyRole = Literal["user", "agent"]
CanvasReviewSelectorKind = Literal["data-canvas-id", "id", "css", "xpath"]
CanvasCoordinateSpace = Literal["viewport", "document"]

MAX_REVIEW_ELEMENTS = 20
MAX_PREVIEW_LENGTH = 2000
MAX_INSTRUCTION_LENGTH = 12000
MAX_REPLY_LENGTH = 12000


class CanvasRoute(BaseModel):
    """Canvas route information"""

    path: str = Field(..., description="Route path")
    file: str | None = Field(default=None, description="Corresponding file for HTML renderer")

    model_config = {"populate_by_name": True}


class CanvasDetectResponse(BaseModel):
    """Canvas detection result"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType
    manifest_status: CanvasManifestStatus = Field(..., alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    error: str | None = None
    detected_at: datetime = Field(..., alias="detectedAt")

    model_config = {"populate_by_name": True}


class CanvasRoutesResponse(BaseModel):
    """Canvas route list response"""

    workspace_id: str = Field(..., alias="workspaceId")
    type: CanvasType = "default"
    manifest_status: CanvasManifestStatus = Field("missing", alias="manifestStatus")
    default_path: str = Field("/", alias="defaultPath")
    routes: list[CanvasRoute] = Field(default_factory=list)
    total: int = Field(..., description="Total route count")
    scanned_at: datetime = Field(..., alias="scannedAt", description="Scan time")

    model_config = {"populate_by_name": True}


class CanvasHealthResponse(BaseModel):
    """Canvas health status"""

    workspace_id: str = Field(..., alias="workspaceId")
    status: str
    type: CanvasType | None = None
    manifest_status: CanvasManifestStatus | None = Field(default=None, alias="manifestStatus")
    renderer_running: bool = Field(False, alias="rendererRunning")
    port_available: bool = Field(False, alias="portAvailable")
    message: str = ""
    source: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CanvasActionResponse(BaseModel):
    """Canvas action response"""

    workspace_id: str = Field(..., alias="workspaceId")
    status: str
    type: CanvasType | None = None
    manifest_status: CanvasManifestStatus | None = Field(default=None, alias="manifestStatus")
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CanvasLogsResponse(BaseModel):
    """Canvas log response"""

    workspace_id: str = Field(..., alias="workspaceId")
    logs: list[str] = Field(default_factory=list)
    renderer_logs: list[str] = Field(default_factory=list, alias="rendererLogs")
    total: int = 0

    model_config = {"populate_by_name": True}


class CanvasReviewRect(BaseModel):
    """Canvas review geometry."""

    x: float
    y: float
    width: float = Field(..., ge=0)
    height: float = Field(..., ge=0)
    coordinate_space: CanvasCoordinateSpace = Field(..., alias="coordinateSpace")

    model_config = {"populate_by_name": True}


class CanvasReviewElementTarget(BaseModel):
    """Single selected element target."""

    type: Literal["element"] = "element"
    selector: str = Field(..., min_length=1, max_length=2000)
    selector_kind: CanvasReviewSelectorKind = Field(..., alias="selectorKind")
    tag_name: str = Field(..., min_length=1, max_length=80, alias="tagName")
    text_preview: str = Field("", max_length=MAX_PREVIEW_LENGTH, alias="textPreview")
    html_preview: str = Field("", max_length=MAX_PREVIEW_LENGTH, alias="htmlPreview")
    parent_html_preview: str = Field("", max_length=MAX_PREVIEW_LENGTH, alias="parentHtmlPreview")
    rect: CanvasReviewRect
    document_rect: CanvasReviewRect | None = Field(default=None, alias="documentRect")

    model_config = {"populate_by_name": True}

    @field_validator("tag_name")
    @classmethod
    def normalize_tag_name(cls, value: str) -> str:
        return value.lower()


class CanvasReviewMultiElementTarget(BaseModel):
    """Multiple selected element target."""

    type: Literal["multi-element"] = "multi-element"
    elements: list[CanvasReviewElementTarget] = Field(
        ..., min_length=1, max_length=MAX_REVIEW_ELEMENTS
    )
    rect: CanvasReviewRect
    document_rect: CanvasReviewRect | None = Field(default=None, alias="documentRect")

    model_config = {"populate_by_name": True}


class CanvasReviewAreaTarget(BaseModel):
    """Rectangular area target."""

    type: Literal["area"] = "area"
    rect: CanvasReviewRect
    document_rect: CanvasReviewRect | None = Field(default=None, alias="documentRect")

    model_config = {"populate_by_name": True}


CanvasReviewTarget = (
    CanvasReviewElementTarget | CanvasReviewMultiElementTarget | CanvasReviewAreaTarget
)


class CanvasReviewReply(BaseModel):
    """Reply attached to a review note."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    role: CanvasReviewReplyRole
    content: str = Field(..., min_length=1, max_length=MAX_REPLY_LENGTH)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")

    model_config = {"populate_by_name": True}


class CanvasReviewNoteBase(BaseModel):
    """Base payload for Canvas review notes."""

    session_id: str | None = Field(default=None, max_length=200, alias="sessionId")
    route_path: str = Field(..., min_length=1, max_length=2048, alias="routePath")
    canvas_url: str = Field(..., min_length=1, max_length=4096, alias="canvasUrl")
    target: CanvasReviewTarget = Field(..., discriminator="type")
    instruction: str = Field(..., min_length=1, max_length=MAX_INSTRUCTION_LENGTH)

    model_config = {"populate_by_name": True}

    @field_validator("route_path")
    @classmethod
    def validate_route_path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("CANVAS_REVIEW_ROUTE_PATH_INVALID")
        return value


class CanvasReviewNoteCreate(CanvasReviewNoteBase):
    """Create Canvas review note request."""

    status: CanvasReviewStatus = "open"


class CanvasReviewNote(CanvasReviewNoteBase):
    """Persisted Canvas review note."""

    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    status: CanvasReviewStatus = "open"
    replies: list[CanvasReviewReply] = Field(default_factory=list)
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")

    model_config = {"populate_by_name": True}


class CanvasReviewNotesResponse(BaseModel):
    """List Canvas review notes response."""

    workspace_id: str = Field(..., alias="workspaceId")
    notes: list[CanvasReviewNote] = Field(default_factory=list)
    total: int

    model_config = {"populate_by_name": True}


class CanvasReviewStatusUpdate(BaseModel):
    """Update Canvas review note status request."""

    status: CanvasReviewStatus


class CanvasReviewReplyCreate(BaseModel):
    """Create Canvas review note reply request."""

    role: CanvasReviewReplyRole
    content: str = Field(..., min_length=1, max_length=MAX_REPLY_LENGTH)


class CanvasReviewNoteRecord(CanvasReviewNoteBase):
    """Internal persisted record."""

    id: str = Field(default_factory=lambda: uuid4().hex)
    workspace_id: str = Field(..., alias="workspaceId")
    status: CanvasReviewStatus = "open"
    replies: list[CanvasReviewReply] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="updatedAt")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def update_resolved_at(self) -> "CanvasReviewNoteRecord":
        if self.status in {"applied", "dismissed"} and self.resolved_at is None:
            self.resolved_at = self.updated_at
        if self.status in {"open", "seen"}:
            self.resolved_at = None
        return self

    def to_response(self) -> CanvasReviewNote:
        return CanvasReviewNote.model_validate(self.model_dump(by_alias=True))
