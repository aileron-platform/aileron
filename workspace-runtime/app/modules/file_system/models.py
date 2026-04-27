"""Unified file management data models"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


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
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")
    skillName: Optional[str] = Field(default=None, description="Skill name (only for SKILL.md nodes, parsed from front matter)")
    skillDescription: Optional[str] = Field(default=None, description="Skill description (only for SKILL.md nodes, parsed from front matter)")


# ============ Request Models ============

class FileTreeRequest(BaseModel):
    """File tree request"""
    path: str = Field(default="/", description="Target path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    includeHidden: bool = Field(default=False, description="Whether to include hidden files")
    maxDepth: int = Field(default=1, ge=1, le=3, description="Maximum depth")


class FileContentRequest(BaseModel):
    """Read file request"""
    path: str = Field(description="File path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")


class FileWriteRequest(BaseModel):
    """Write file request"""
    path: str = Field(description="File path")
    content: str = Field(description="File content")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    expectedVersionId: Optional[str] = Field(default=None, description="Expected version ID (conflict detection)")


class FileCreateRequest(BaseModel):
    """Create file or directory request"""
    path: str = Field(description="Path")
    type: Literal["file", "directory"] = Field(description="Type")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    content: Optional[str] = Field(default="", description="File content (files only)")
    encoding: Optional[Literal["utf-8", "base64"]] = Field(default="utf-8", description="Content encoding method")


class FileDeleteRequest(BaseModel):
    """Delete request"""
    path: str = Field(description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    recursive: bool = Field(default=False, description="Whether to recursively delete directory")


class FileCopyRequest(BaseModel):
    """Copy request"""
    sourcePath: str = Field(description="Source path")
    destPath: str = Field(description="Destination path")
    sourceScope: Optional[str] = Field(default=None, description="Source scope")
    destScope: Optional[str] = Field(default=None, description="Destination scope")
    overwrite: bool = Field(default=False, description="Whether to overwrite")


class FileMoveRequest(BaseModel):
    """Move request"""
    sourcePath: str = Field(description="Source path")
    destPath: str = Field(description="Destination path")
    sourceScope: Optional[str] = Field(default=None, description="Source scope")
    destScope: Optional[str] = Field(default=None, description="Destination scope")
    overwrite: bool = Field(default=False, description="Whether to overwrite")


class BatchDeleteRequest(BaseModel):
    """Batch delete request"""
    paths: List[str] = Field(description="Path list")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    recursive: bool = Field(default=False, description="Whether to recursively delete directory")


class BatchWriteRequest(BaseModel):
    """Batch write request"""
    files: List[Dict[str, str]] = Field(description="File list [{'path': '...', 'content': '...'}, ...]")
    scope: Optional[str] = Field(default=None, description="Scope identifier")


# ============ Response Models ============

class FileTreeResponse(BaseModel):
    """File tree response"""
    path: str = Field(description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    nodes: List[FileNode] = Field(description="Node list")
    total: int = Field(description="Total node count")

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "nodes" not in value:
            data = value.get("data") or {}
            return {
                "path": data.get("path", "/"),
                "scope": data.get("scope"),
                "nodes": data.get("children", []),
                "total": data.get("total", len(data.get("children", []))),
            }
        return value


class FileContentResponse(BaseModel):
    """File content response"""
    path: str = Field(description="File path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    content: str = Field(description="File content")
    size: int = Field(description="File size")
    updatedAt: str = Field(description="Last modification time")
    versionId: Optional[str] = Field(default=None, description="Version ID")
    contentHash: Optional[str] = Field(default=None, description="Content hash")

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "content" not in value:
            data = value.get("data") or {}
            return {
                "path": data.get("path", ""),
                "scope": data.get("scope"),
                "content": data.get("content", ""),
                "size": data.get("size", len(data.get("content", ""))),
                "updatedAt": data.get("updatedAt", ""),
                "versionId": data.get("versionId"),
                "contentHash": data.get("contentHash"),
            }
        return value


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

    @model_validator(mode="before")
    @classmethod
    def _compat_old_shape(cls, value):
        if isinstance(value, dict) and "data" in value and "results" not in value:
            data = value.get("data") or {}
            results = data.get("results", [])
            succeeded = sum(1 for item in results if item.get("success"))
            failed = len(results) - succeeded
            return {
                "total": len(results),
                "succeeded": succeeded,
                "failed": failed,
                "results": results,
            }
        return value


class FileError(BaseModel):
    """File error"""
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")

class UploadResult(BaseModel):
    """Single file upload result"""
    path: str = Field(description="File storage path")
    size: int = Field(description="File size")
    lastModified: str = Field(description="Last modification time")
    type: Literal["file", "directory"] = Field(default="file", description="Result type")


class UploadResponse(BaseModel):
    """Upload file response"""
    uploaded: List[UploadResult] = Field(description="Successfully uploaded list")
    extracted: List[UploadResult] = Field(default_factory=list, description="Successfully extracted list")
    skipped: List[str] = Field(default_factory=list, description="Skipped files")


class ExtractArchiveRequest(BaseModel):
    """Extract archive request"""
    archivePath: str = Field(description="Existing ZIP file path")
    targetPath: Optional[str] = Field(default=None, description="Extraction target directory, defaults to ZIP's directory")
    conflictStrategy: Literal["rename", "overwrite", "reject"] = Field(
        default="rename",
        description="Conflict handling strategy",
    )


class ExtractArchiveAcceptedResponse(BaseModel):
    """Accept background extraction request response"""
    operationId: str = Field(description="Background extraction operation ID")
    status: Literal["pending", "running"] = Field(description="Current status")
    message: str = Field(description="Status message")
    startedAt: datetime = Field(description="Creation time")


class ExtractArchiveResult(BaseModel):
    """Background extraction result"""
    extracted: List[UploadResult] = Field(default_factory=list, description="Successfully extracted items")
    extractedPaths: List[str] = Field(default_factory=list, description="Successfully extracted paths")


class ExtractArchiveStatusResponse(BaseModel):
    """Background extraction status response"""
    operationId: str = Field(description="Background extraction operation ID")
    status: Literal["pending", "running", "completed", "failed"] = Field(description="Current status")
    progress: float = Field(default=0.0, description="Progress 0.0-1.0", ge=0.0, le=1.0)
    message: str = Field(description="Status message")
    startedAt: datetime = Field(description="Creation time")
    completedAt: Optional[datetime] = Field(default=None, description="Completion time")
    error: Optional[str] = Field(default=None, description="Failure message")
    result: Optional[ExtractArchiveResult] = Field(default=None, description="Success result")
