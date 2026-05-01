"""Unified file management data models"""

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field


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
    writable: bool = Field(default=True, description="Whether write operations are allowed for this node")

    # Optional extended columns
    extension: Optional[str] = Field(default=None, description="File extension")
    fileType: Optional[str] = Field(default=None, description="File type")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


# ============ Request models =============

class FileTreeRequest(BaseModel):
    """File tree request"""
    path: str = Field(default="/", description="Target path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    includeHidden: bool = Field(default=False, description="Include hidden files")
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


class FileDeleteRequest(BaseModel):
    """Delete request"""
    path: str = Field(description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    recursive: bool = Field(default=False, description="Recursively delete directory")


class FileCopyRequest(BaseModel):
    """Copy request"""
    sourcePath: str = Field(description="Source path")
    destPath: str = Field(description="Destination path")
    sourceScope: Optional[str] = Field(default=None, description="Source scope")
    destScope: Optional[str] = Field(default=None, description="Destination scope")
    overwrite: bool = Field(default=False, description="Overwrite existing")


class FileMoveRequest(BaseModel):
    """Move request"""
    sourcePath: str = Field(description="Source path")
    destPath: str = Field(description="Destination path")
    sourceScope: Optional[str] = Field(default=None, description="Source scope")
    destScope: Optional[str] = Field(default=None, description="Destination scope")
    overwrite: bool = Field(default=False, description="Overwrite existing")


class BatchDeleteRequest(BaseModel):
    """Batch delete request"""
    paths: List[str] = Field(description="Path list")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    recursive: bool = Field(default=False, description="Recursively delete directory")


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


class FileContentResponse(BaseModel):
    """File content response"""
    path: str = Field(description="File path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    content: str = Field(description="File content")
    size: int = Field(description="File size")
    updatedAt: str = Field(description="Last modification time")
    versionId: Optional[str] = Field(default=None, description="Version ID")
    contentHash: Optional[str] = Field(default=None, description="Content hash")


class FileOperationResponse(BaseModel):
    """File operation response"""
    success: bool = Field(description="Success status")
    path: Optional[str] = Field(default=None, description="Path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    message: Optional[str] = Field(default=None, description="Message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional data")


class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    total: int = Field(description="Total count")
    succeeded: int = Field(description="Success count")
    failed: int = Field(description="Failed count")
    results: List[Dict[str, Any]] = Field(description="Detailed results")


class FileError(BaseModel):
    """File error"""
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")


class FileSearchRequest(BaseModel):
    """File search request"""
    query: str = Field(description="Search keyword")
    path: str = Field(default="/", description="Search path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    fileTypes: Optional[List[str]] = Field(default=None, description="File type filter")
    searchContent: bool = Field(default=False, description="Search file content")
    caseSensitive: bool = Field(default=False, description="Case sensitive")
    maxResults: int = Field(default=100, ge=1, le=1000, description="Maximum results")


class FileSearchResult(BaseModel):
    """File search result item"""
    path: str = Field(description="File path")
    name: str = Field(description="File name")
    type: Literal["file", "directory"] = Field(description="Type")
    size: int = Field(description="File size")
    updatedAt: str = Field(description="Last modification time")
    matches: Optional[List[str]] = Field(default=None, description="Matched content fragments")


class FileSearchResponse(BaseModel):
    """File search response"""
    query: str = Field(description="Search keyword")
    path: str = Field(description="Search path")
    scope: Optional[str] = Field(default=None, description="Scope identifier")
    results: List[FileSearchResult] = Field(description="Search results")
    total: int = Field(description="Total result count")


class FileUploadResult(BaseModel):
    """File upload result item"""
    filename: str = Field(description="File name")
    path: str = Field(description="Save path")
    size: int = Field(description="File size")
    success: bool = Field(description="Success status")
    message: Optional[str] = Field(default=None, description="Message")


class FileUploadResponse(BaseModel):
    """File upload response"""
    total: int = Field(description="Total file count")
    succeeded: int = Field(description="Success count")
    failed: int = Field(description="Failed count")
    results: List[FileUploadResult] = Field(description="Upload results")
