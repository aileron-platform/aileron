"""Knowledge base related Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import Field
from pydantic.config import ConfigDict

from app.core.pydantic import CamelModel
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
)

KnowledgeBaseRole = ResourceAccessRole


class KnowledgeBaseSummary(CamelModel):
    id: str
    slug: str
    name: str
    description: Optional[str] = None
    owner_id: str = Field(..., alias="ownerId")
    current_size_bytes: int = Field(..., alias="currentSizeBytes")
    quota_bytes: Optional[int] = Field(None, alias="quotaBytes")
    effective_quota_bytes: int = Field(..., alias="effectiveQuotaBytes")
    quota_source: Literal["custom", "platform_default"] = Field(
        ..., alias="quotaSource"
    )
    utilization_percent: float = Field(..., alias="utilizationPercent")
    owner_quota_used_bytes: int = Field(..., alias="ownerQuotaUsedBytes")
    owner_effective_quota_bytes: int = Field(..., alias="ownerEffectiveQuotaBytes")
    version_control_enabled: bool = Field(False, alias="versionControlEnabled")
    last_indexed_at: Optional[datetime] = Field(None, alias="lastIndexedAt")
    last_index_status: Optional[str] = Field(None, alias="lastIndexStatus")
    last_index_error: Optional[str] = Field(None, alias="lastIndexError")
    access_role: ResourceAccessRole = Field(..., alias="accessRole")
    access_source: ResourceAccessSource = Field(..., alias="accessSource")
    access_sources: list[ResourceAccessSource] = Field(..., alias="accessSources")
    visibility: Literal["private", "public"]
    allowed_operations: list[str] = Field(..., alias="allowedOperations")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class KnowledgeBaseListResponse(CamelModel):
    items: list[KnowledgeBaseSummary]


class KnowledgeBaseShareSummary(CamelModel):
    id: str
    kb_id: str = Field(..., alias="kbId")
    target_type: Literal["user", "user_group"] = Field(..., alias="targetType")
    target_id: str = Field(..., alias="targetId")
    target_label: str = Field(..., alias="targetLabel")
    role: str
    granted_by_id: str = Field(..., alias="grantedById")
    created_at: datetime = Field(..., alias="createdAt")


class KnowledgeBaseAttachmentSummary(CamelModel):
    attachment_id: str = Field(..., alias="attachmentId")
    workspace_id: str = Field(..., alias="workspaceId")
    workspace_name: str = Field(..., alias="workspaceName")
    mount_alias: str = Field(..., alias="mountAlias")
    attachment_status: Literal["active", "pending", "pending_removal"] = Field(
        ...,
        alias="attachmentStatus",
    )


class KnowledgeBaseDetail(KnowledgeBaseSummary):
    pass


class KnowledgeBaseCreateRequest(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    slug: str
    description: Optional[str] = None


class KnowledgeBaseUpdateRequest(CamelModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: Optional[str] = None
    description: Optional[str] = None


class KnowledgeBaseDeleteRequest(CamelModel):
    confirmation_name: str = Field(..., alias="confirmationName")


class KnowledgeBaseVisibilityUpdateRequest(CamelModel):
    visibility: Literal["private", "public"]


class KnowledgeBaseShareCreateRequest(CamelModel):
    target_type: str = Field(..., alias="targetType")
    target_id: str = Field(..., alias="targetId")
    role: str


class KnowledgeBaseShareUpdateRequest(CamelModel):
    role: str


class KnowledgeBaseShareListResponse(CamelModel):
    items: list[KnowledgeBaseShareSummary]


class KnowledgeBaseShareCandidateGroup(CamelModel):
    id: str
    name: str


class KnowledgeBaseShareCandidateGroupListResponse(CamelModel):
    items: list[KnowledgeBaseShareCandidateGroup]


class KnowledgeBaseAttachmentListResponse(CamelModel):
    visible_items: list[KnowledgeBaseAttachmentSummary] = Field(
        default_factory=list,
        alias="visibleItems",
    )
    hidden_workspace_count: int = Field(0, alias="hiddenWorkspaceCount")
    attachment_count: int = Field(0, alias="attachmentCount")


class KnowledgeBaseFileMutationRequest(CamelModel):
    path: str
    type: str
    content: Optional[str] = ""
    revision: str

    model_config = ConfigDict(
        alias_generator=CamelModel.model_config["alias_generator"],
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class KnowledgeBaseFileSearchResult(CamelModel):
    path: str
    name: str
    type: Literal["file", "directory"]
    size: int
    updated_at: str = Field(..., alias="updatedAt")
    matches: Optional[list[str]] = None


class KnowledgeBaseFileSearchResponse(CamelModel):
    query: str
    path: str
    scope: Optional[str] = None
    results: list[KnowledgeBaseFileSearchResult]
    total: int


class KnowledgeBaseFilePatchRequest(CamelModel):
    source_path: str = Field(..., alias="sourcePath")
    destination_path: str = Field(..., alias="destinationPath")


class KnowledgeBaseLocalHistoryEntry(CamelModel):
    id: str
    domain: str
    resource_id: str = Field(..., alias="resourceId")
    path: str
    operation: str
    timestamp: str
    revision_before: Optional[str] = Field(None, alias="revisionBefore")
    revision_after: Optional[str] = Field(None, alias="revisionAfter")
    snapshot_path: Optional[str] = Field(None, alias="snapshotPath")
    size: int


class KnowledgeBaseLocalHistoryListResponse(CamelModel):
    items: list[KnowledgeBaseLocalHistoryEntry]


class KnowledgeBaseLocalHistoryRestoreRequest(CamelModel):
    revision: Optional[str] = None


class KnowledgeBaseLocalHistoryRestoreResponse(CamelModel):
    path: str
    restored_from: str = Field(..., alias="restoredFrom")
    revision: str


class KnowledgeBaseSourceImportResponse(CamelModel):
    path: str
    size: int
    source_hash: str = Field(..., alias="sourceHash")


class KnowledgeBaseWebClipImportRequest(CamelModel):
    title: str
    markdown: str
    assets: Optional[dict[str, str]] = None
    clip_slug: Optional[str] = Field(None, alias="clipSlug")
    overwrite: bool = False


class KnowledgeBaseWebClipImportResponse(CamelModel):
    path: str
    asset_paths: list[str] = Field(default_factory=list, alias="assetPaths")
    size: int
    source_hash: str = Field(..., alias="sourceHash")


class KnowledgeBaseSourceUploadResponse(CamelModel):
    source: KnowledgeBaseSourceImportResponse


class ArchiveDownloadRequest(CamelModel):
    paths: list[str] = Field(min_length=1)
    archive_name: Optional[str] = Field(None, alias="archiveName")
    archive_format: Literal["zip"] = Field("zip", alias="archiveFormat")


class ArchiveDownloadAcceptedResponse(CamelModel):
    operation_id: str = Field(..., alias="operationId")
    status: Literal["pending", "running"]
    message: str
    started_at: datetime = Field(..., alias="startedAt")


class ArchiveDownloadResult(CamelModel):
    archive_name: str = Field(..., alias="archiveName")
    size: int
    download_url: str = Field(..., alias="downloadUrl")
    expires_at: datetime = Field(..., alias="expiresAt")


class ArchiveDownloadStatusResponse(CamelModel):
    operation_id: str = Field(..., alias="operationId")
    status: Literal["pending", "running", "completed", "failed", "expired"]
    progress: float = Field(0.0, ge=0.0, le=1.0)
    message: str
    started_at: datetime = Field(..., alias="startedAt")
    completed_at: Optional[datetime] = Field(None, alias="completedAt")
    error: Optional[str] = None
    result: Optional[ArchiveDownloadResult] = None


class KnowledgeBaseGitCloneRequest(CamelModel):
    remote_url: str = Field(..., min_length=1, alias="remoteUrl")
    branch: Optional[str] = None


class KnowledgeBaseQueryCitation(CamelModel):
    path: str
    title: str
    type: str
    score: float = 0
    snippet: Optional[str] = None


class KnowledgeBaseQueryContextItem(CamelModel):
    path: str
    title: str
    type: str
    score: float = 0
    content: str
    citation_index: int = Field(..., alias="citationIndex")
    reasons: list[str] = Field(default_factory=list)


class KnowledgeBaseQueryResponse(CamelModel):
    kb_id: str = Field(..., alias="kbId")
    query: str
    status: Literal["context_ready", "no_context"]
    answer: str
    citations: list[KnowledgeBaseQueryCitation] = Field(default_factory=list)
    context: list[KnowledgeBaseQueryContextItem] = Field(default_factory=list)


class KnowledgeBaseQueryRequest(CamelModel):
    query: str
    limit: int = Field(8, ge=1, le=20)
