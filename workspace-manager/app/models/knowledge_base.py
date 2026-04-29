"""Knowledge base related Pydantic models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

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
    version_control_enabled: bool = Field(False, alias="versionControlEnabled")
    git_lfs_enabled: bool = Field(False, alias="gitLfsEnabled")
    git_default_branch: str = Field("main", alias="gitDefaultBranch")
    git_last_commit_sha: Optional[str] = Field(None, alias="gitLastCommitSha")
    wiki_initialized_at: Optional[datetime] = Field(None, alias="wikiInitializedAt")
    last_indexed_at: Optional[datetime] = Field(None, alias="lastIndexedAt")
    last_index_status: Optional[str] = Field(None, alias="lastIndexStatus")
    last_index_error: Optional[str] = Field(None, alias="lastIndexError")
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


class KnowledgeBaseSourceNormalizeRequest(CamelModel):
    source_path: str = Field(..., alias="sourcePath")
    force: bool = False


class KnowledgeBaseSourceNormalizeResponse(CamelModel):
    source_path: str = Field(..., alias="sourcePath")
    normalized_text_path: str = Field(..., alias="normalizedTextPath")
    metadata_path: str = Field(..., alias="metadataPath")
    source_hash: str = Field(..., alias="sourceHash")
    normalized_hash: str = Field(..., alias="normalizedHash")
    skipped: bool
    extractor: str


class KnowledgeBaseSourceUploadResponse(CamelModel):
    source: KnowledgeBaseSourceImportResponse
    normalization: Optional[KnowledgeBaseSourceNormalizeResponse] = None


class KnowledgeBaseIngestJobRequest(CamelModel):
    source_paths: Optional[list[str]] = Field(None, alias="sourcePaths")
    force: bool = False


class KnowledgeBaseIngestJobResponse(CamelModel):
    id: str
    kb_id: str = Field(..., alias="kbId")
    status: Literal["queued", "running", "skipped", "success", "failed", "canceled"]
    source_paths: list[str] = Field(default_factory=list, alias="sourcePaths")
    skipped_sources: list[str] = Field(default_factory=list, alias="skippedSources")
    changed_files: list[str] = Field(default_factory=list, alias="changedFiles")
    version_control_enabled: bool = Field(False, alias="versionControlEnabled")
    commit_id: Optional[str] = Field(None, alias="commitId")
    error: Optional[str] = None
    created_at: str = Field("", alias="createdAt")
    updated_at: str = Field("", alias="updatedAt")


class KnowledgeBaseIngestJobListResponse(CamelModel):
    items: list[KnowledgeBaseIngestJobResponse]


class KnowledgeBaseGitEnableRequest(CamelModel):
    default_branch: str = Field("main", alias="defaultBranch")
    initial_message: str = Field("Initialize knowledge base", alias="initialMessage")


class KnowledgeBaseGitLfsEnableRequest(CamelModel):
    patterns: Optional[list[str]] = None


class KnowledgeBaseGitRevertRequest(CamelModel):
    commit_id: str = Field(..., alias="commitId")


class KnowledgeBaseGitRollbackRequest(CamelModel):
    revision: str
    confirm: str


class KnowledgeBaseGraphNode(CamelModel):
    id: str
    label: str
    type: str
    path: str
    sources: list[str] = Field(default_factory=list)
    outbound_count: int = Field(0, alias="outboundCount")
    inbound_count: int = Field(0, alias="inboundCount")
    degree: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseGraphEdgeReason(CamelModel):
    type: str
    weight: float
    details: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseGraphEdge(CamelModel):
    id: str
    source: str
    target: str
    weight: float
    reasons: list[KnowledgeBaseGraphEdgeReason] = Field(default_factory=list)


class KnowledgeBaseGraphResponse(CamelModel):
    kb_id: str = Field(..., alias="kbId")
    generated_at: datetime = Field(..., alias="generatedAt")
    nodes: list[KnowledgeBaseGraphNode] = Field(default_factory=list)
    edges: list[KnowledgeBaseGraphEdge] = Field(default_factory=list)
    report_path: Optional[str] = Field(None, alias="reportPath")


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


class KnowledgeBaseQuerySaveRequest(CamelModel):
    query: str
    answer: str
    citations: list[KnowledgeBaseQueryCitation] = Field(default_factory=list)
    title: Optional[str] = None


class KnowledgeBaseQuerySaveResponse(CamelModel):
    path: str
    commit_id: Optional[str] = Field(None, alias="commitId")


class KnowledgeBaseLintIssue(CamelModel):
    issue_type: str = Field(..., alias="issueType")
    severity: Literal["info", "warning", "error"] = "warning"
    path: str
    details: dict[str, Any] = Field(default_factory=dict)


class KnowledgeBaseLintReportResponse(CamelModel):
    kb_id: str = Field(..., alias="kbId")
    generated_at: datetime = Field(..., alias="generatedAt")
    report_path: str = Field(..., alias="reportPath")
    issue_counts: dict[str, int] = Field(default_factory=dict, alias="issueCounts")
    issues: list[KnowledgeBaseLintIssue] = Field(default_factory=list)
    commit_id: Optional[str] = Field(None, alias="commitId")


class KnowledgeBaseLintReportListResponse(CamelModel):
    items: list[KnowledgeBaseLintReportResponse]
