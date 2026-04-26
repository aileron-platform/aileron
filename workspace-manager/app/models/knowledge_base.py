"""Knowledge base related Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.utils.pydantic import CamelModel

KnowledgeBaseRole = str
KnowledgeBaseAttachmentMode = str


class KnowledgeBaseErrorDetail(CamelModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class KnowledgeBaseErrorResponse(CamelModel):
    detail: KnowledgeBaseErrorDetail


class KnowledgeBaseSummary(CamelModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    owner_id: str = Field(..., alias="ownerId")
    current_size_bytes: int = Field(..., alias="currentSizeBytes")
    quota_bytes: Optional[int] = Field(None, alias="quotaBytes")
    access_role: str = Field(..., alias="accessRole")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class KnowledgeBaseListResponse(CamelModel):
    items: list[KnowledgeBaseSummary]


class KnowledgeBaseShareSummary(CamelModel):
    id: str
    kb_id: str = Field(..., alias="kbId")
    user_id: str = Field(..., alias="userId")
    role: str
    granted_by_id: str = Field(..., alias="grantedById")
    created_at: datetime = Field(..., alias="createdAt")


class KnowledgeBaseAttachmentSummary(CamelModel):
    id: str
    workspace_id: str = Field(..., alias="workspaceId")
    kb_id: str = Field(..., alias="kbId")
    mount_alias: str = Field(..., alias="mountAlias")
    mode: str
    attached_by_id: str = Field(..., alias="attachedById")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")


class KnowledgeBaseDetail(KnowledgeBaseSummary):
    pass


class KnowledgeBaseCreateRequest(CamelModel):
    name: str
    slug: str
    description: Optional[str] = None
    quota_bytes: Optional[int] = Field(None, alias="quotaBytes")


class KnowledgeBaseUpdateRequest(CamelModel):
    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseShareCreateRequest(CamelModel):
    user_id: str = Field(..., alias="userId")
    role: str


class KnowledgeBaseShareUpdateRequest(CamelModel):
    role: str


class KnowledgeBaseShareListResponse(CamelModel):
    items: list[KnowledgeBaseShareSummary]


class KnowledgeBaseAttachmentCreateRequest(CamelModel):
    workspace_id: str = Field(..., alias="workspaceId")
    mount_alias: Optional[str] = Field(None, alias="mountAlias")
    mode: str = "rw"


class KnowledgeBaseAttachmentUpdateRequest(CamelModel):
    mount_alias: Optional[str] = Field(None, alias="mountAlias")
    mode: Optional[str] = None


class KnowledgeBaseAttachmentListResponse(CamelModel):
    items: list[KnowledgeBaseAttachmentSummary]


class KnowledgeBaseFileMutationRequest(CamelModel):
    path: str
    type: str
    content: Optional[str] = ""


class KnowledgeBaseFilePatchRequest(CamelModel):
    source_path: str = Field(..., alias="sourcePath")
    destination_path: str = Field(..., alias="destinationPath")
    overwrite: bool = False
