"""Unified file management data models"""

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

    @model_validator(mode="after")
    def validate_operation_sources(self):
        if self.operation in {"upload", "paste"} and not self.sources:
            raise ValueError("sources are required for upload and paste preflight")
        if self.operation == "extract" and not self.archivePath:
            raise ValueError("archivePath is required for extract preflight")
        return self


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

# ============ File tree nodes ============


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
    hasChildren: bool = Field(default=False, description="Has child nodes")
    writable: bool = Field(
        default=True, description="Whether write operations are allowed for this node"
    )

    # Optional extended columns
    extension: Optional[str] = Field(default=None, description="File extension")
    fileType: Optional[str] = Field(default=None, description="File type")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


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
    revision: Optional[str] = Field(default=None, description="Content revision")
    readable: bool = Field(description="Whether the content can be displayed as text")
    unreadableReason: Optional[Literal["binary"]] = Field(
        default=None,
        description="Stable reason code when content is not text-readable",
    )
