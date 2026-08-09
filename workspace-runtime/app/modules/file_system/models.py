"""Unified file management data models"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ConflictStrategy = Literal["keep-both", "replace", "skip", "cancel"]
FileEntryType = Literal["file", "directory"]
FileConflictOperation = Literal["upload", "paste", "extract"]
FileConflictResultStatus = Literal[
    "created",
    "kept-both",
    "replaced",
    "merged",
    "skipped",
    "cancelled",
    "failed",
]


# ============ File Tree Nodes ============


class FileNode(BaseModel):
    """Unified file tree node"""

    id: str = Field(description="Unique node identifier (usually path)")
    name: str = Field(description="Node name")
    path: str = Field(description="Relative path (without scope prefix)")
    type: Literal["file", "directory"] = Field(description="Node type")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    size: int = Field(default=0, description="File size (bytes)")
    updatedAt: str = Field(description="Last modification time (ISO8601)")
    depth: int = Field(default=0, description="Level in tree")
    children: List["FileNode"] = Field(default_factory=list, description="Child nodes")
    hasChildren: bool = Field(default=False, description="Whether has child nodes")

    # Optional extension fields
    extension: Optional[str] = Field(default=None, description="File extension")
    fileType: Optional[str] = Field(default=None, description="File type")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )
    skillName: Optional[str] = Field(
        default=None,
        description="Skill name (only for SKILL.md nodes, parsed from front matter)",
    )
    skillDescription: Optional[str] = Field(
        default=None,
        description="Skill description (only for SKILL.md nodes, parsed from front matter)",
    )

    @model_validator(mode="before")
    @classmethod
    def _compat_tree_node_without_id(cls, value: Any) -> Any:
        if isinstance(value, dict) and not value.get("id") and value.get("path"):
            return {**value, "id": value["path"]}
        return value


# ============ Request Models ============


class FileTreeRequest(BaseModel):
    """File tree request"""

    path: str = Field(default="/", description="Target path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    includeHidden: bool = Field(
        default=False, description="Whether to include hidden files"
    )
    maxDepth: int = Field(default=1, ge=1, le=3, description="Maximum depth")


class FileWriteRequest(BaseModel):
    """Write file request"""

    path: str = Field(description="File path")
    content: str = Field(description="File content")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    revision: Optional[str] = Field(
        default=None, description="Expected revision (conflict detection)"
    )


class FileCreateRequest(BaseModel):
    """Create file or directory request"""

    path: str = Field(description="Path")
    type: Literal["file", "directory"] = Field(description="Type")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    content: Optional[str] = Field(default="", description="File content (files only)")
    encoding: Optional[Literal["utf-8", "base64"]] = Field(
        default="utf-8", description="Content encoding method"
    )


class FileMoveRequest(BaseModel):
    """Move request"""

    sourcePath: str = Field(description="Source path")
    destPath: str = Field(description="Destination path")
    sourceScope: Optional[str] = Field(default=None, description="Source scope")
    destScope: Optional[str] = Field(default=None, description="Destination scope")
    model_config = ConfigDict(extra="forbid")


class BatchDeleteRequest(BaseModel):
    """Batch delete request"""

    paths: List[str] = Field(description="Path list")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    recursive: bool = Field(
        default=False, description="Whether to recursively delete directory"
    )


class BatchWriteRequest(BaseModel):
    """Batch write request"""

    files: List[Dict[str, str]] = Field(
        description="File list [{'path': '...', 'content': '...'}, ...]"
    )
    scope: Optional[str] = Field(default=None, description="Scope identifier")


class FileSearchResult(BaseModel):
    """Single file search match"""

    path: str = Field(description="Matched path")
    name: str = Field(description="File name")
    type: Literal["file", "directory"] = Field(description="Entry type")
    size: int = Field(description="File size")
    updatedAt: str = Field(description="Last modification time")
    matches: Optional[List[str]] = Field(default=None, description="Content previews")


class FileSearchResponse(BaseModel):
    """File search response"""

    query: str = Field(description="Search query")
    path: str = Field(description="Search root path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    results: List[FileSearchResult] = Field(description="Search results")
    total: int = Field(description="Total result count")


# ============ Response Models ============


class FileTreeResponse(BaseModel):
    """File tree response"""

    path: str = Field(description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    nodes: List[FileNode] = Field(description="Node list")
    total: int = Field(description="Total node count")


class FileContentResponse(BaseModel):
    """File content response"""

    path: str = Field(description="File path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    content: str = Field(description="File content")
    size: int = Field(description="File size")
    updatedAt: str = Field(description="Last modification time")
    revision: Optional[str] = Field(default=None, description="Revision")


class FileOperationResponse(BaseModel):
    """File operation response"""

    success: bool = Field(description="Success")
    path: Optional[str] = Field(default=None, description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    message: Optional[str] = Field(default=None, description="Message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class BatchOperationResponse(BaseModel):
    """Batch operation response"""

    total: int = Field(description="Total")
    succeeded: int = Field(description="Succeeded count")
    failed: int = Field(description="Failed count")
    results: List[Dict[str, Any]] = Field(description="Detailed results")


class LocalHistoryEntryResponse(BaseModel):
    """Local history entry response"""

    id: str = Field(description="History entry ID")
    domain: str = Field(description="History domain")
    resourceId: str = Field(description="Resource ID")
    path: str = Field(description="File path")
    operation: str = Field(description="Operation that created the snapshot")
    timestamp: str = Field(description="Snapshot creation time")
    revisionBefore: Optional[str] = Field(
        default=None,
        description="Revision before operation",
    )
    revisionAfter: Optional[str] = Field(
        default=None,
        description="Revision after operation",
    )
    snapshotPath: Optional[str] = Field(default=None, description="Snapshot file path")
    size: int = Field(description="Snapshot size in bytes")


class LocalHistoryListResponse(BaseModel):
    """Local history list response"""

    items: List[LocalHistoryEntryResponse] = Field(description="History entries")


class LocalHistoryRestoreRequest(BaseModel):
    """Restore local history request"""

    revision: Optional[str] = Field(
        default=None,
        description="Expected current revision",
    )


class LocalHistoryRestoreResponse(BaseModel):
    """Restore local history response"""

    path: str = Field(description="Restored file path")
    restoredFrom: str = Field(description="History entry ID")
    revision: str = Field(description="Revision after restore")


class FileConflictSource(BaseModel):
    sourcePath: str = Field(min_length=1)
    entryType: FileEntryType

    model_config = ConfigDict(extra="forbid")


class FileConflictResolution(BaseModel):
    sourcePath: str = Field(min_length=1)
    strategy: ConflictStrategy

    model_config = ConfigDict(extra="forbid")


class FileConflictPreflightRequest(BaseModel):
    operation: FileConflictOperation
    targetPath: str
    sources: Optional[List[FileConflictSource]] = None
    archivePath: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class FileConflictItem(BaseModel):
    sourcePath: str
    targetPath: str
    sourceType: FileEntryType
    targetType: FileEntryType
    canReplace: bool

    model_config = ConfigDict(extra="forbid")


class FileConflictPreflightResponse(BaseModel):
    conflicts: List[FileConflictItem] = Field(default_factory=list)
    total: int

    model_config = ConfigDict(extra="forbid")


class FileConflictExecutionRequest(BaseModel):
    targetPath: str
    sources: List[FileConflictSource] = Field(min_length=1)
    defaultStrategy: ConflictStrategy
    resolutions: List[FileConflictResolution]

    model_config = ConfigDict(extra="forbid")


class FileExtractExecutionRequest(BaseModel):
    archivePath: str = Field(min_length=1)
    targetPath: str
    defaultStrategy: ConflictStrategy
    resolutions: List[FileConflictResolution]

    model_config = ConfigDict(extra="forbid")


class FileConflictResultItem(BaseModel):
    sourcePath: str
    finalPath: Optional[str]
    status: FileConflictResultStatus
    size: int
    type: FileEntryType
    error: Optional[str]

    model_config = ConfigDict(extra="forbid")


class FileConflictBatchResult(BaseModel):
    items: List[FileConflictResultItem]
    total: int
    succeeded: int
    skipped: int
    failed: int

    model_config = ConfigDict(extra="forbid")


class ArchiveDownloadRequest(BaseModel):
    """Archive download request"""

    paths: List[str] = Field(
        min_length=1, description="File or directory paths to package"
    )
    archiveName: Optional[str] = Field(
        default=None, description="Preferred archive file name"
    )
    archiveFormat: Literal["zip"] = Field(default="zip", description="Archive format")


class ArchiveDownloadAcceptedResponse(BaseModel):
    """Accept background archive download request response"""

    operationId: str = Field(description="Background archive operation ID")
    status: Literal["pending", "running"] = Field(description="Current status")
    message: str = Field(description="Status message")
    startedAt: datetime = Field(description="Creation time")


class ArchiveDownloadResult(BaseModel):
    """Background archive download result"""

    archiveName: str = Field(description="Archive file name")
    size: int = Field(description="Archive file size in bytes")
    downloadUrl: str = Field(description="Archive download URL")
    expiresAt: datetime = Field(description="Archive expiration time")


class ArchiveDownloadStatusResponse(BaseModel):
    """Background archive download status response"""

    operationId: str = Field(description="Background archive operation ID")
    status: Literal["pending", "running", "completed", "failed", "expired"] = Field(
        description="Current status"
    )
    progress: float = Field(default=0.0, description="Progress 0.0-1.0", ge=0.0, le=1.0)
    message: str = Field(description="Status message")
    startedAt: datetime = Field(description="Creation time")
    completedAt: Optional[datetime] = Field(default=None, description="Completion time")
    error: Optional[str] = Field(default=None, description="Failure message")
    result: Optional[ArchiveDownloadResult] = Field(
        default=None, description="Success result"
    )
