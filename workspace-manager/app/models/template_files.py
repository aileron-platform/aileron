"""Template file management related data models"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============ Request models ============

class CreateFileRequest(BaseModel):
    """Create file or directory request"""
    path: str = Field(..., description="File or directory path")
    type: Literal["file", "directory"] = Field(..., description="Type")
    content: Optional[str] = Field(default="", description="File content (files only)")
    
    model_config = {"json_schema_extra": {
        "example": {
            "path": "src/main.py",
            "type": "file",
            "content": "print('Hello World')"
        }
    }}

class UpdateFileContentRequest(BaseModel):
    """Update file content request"""
    path: str = Field(..., description="File path")
    content: str = Field(..., description="New content")
    
    model_config = {"json_schema_extra": {
        "example": {
            "path": "src/main.py",
            "content": "print('Updated')"
        }
    }}

class RenameFileRequest(BaseModel):
    """Rename request"""
    old_path: str = Field(..., description="Original path")
    new_name: str = Field(..., description="New name")
    
    model_config = {"json_schema_extra": {
        "example": {
            "old_path": "src/old.py",
            "new_name": "new.py"
        }
    }}

class MoveFileRequest(BaseModel):
    """Move request"""
    source_path: str = Field(..., description="Source path")
    target_path: str = Field(..., description="Target path")
    overwrite: bool = Field(default=False, description="Whether to overwrite")
    
    model_config = {"json_schema_extra": {
        "example": {
            "source_path": "src/old.py",
            "target_path": "lib/new.py",
            "overwrite": False
        }
    }}

class CopyFileRequest(BaseModel):
    """Copy request"""
    source_path: str = Field(..., description="Source path")
    target_path: str = Field(..., description="Target path")
    overwrite: bool = Field(default=False, description="Whether to overwrite")
    
    model_config = {"json_schema_extra": {
        "example": {
            "source_path": "src/main.py",
            "target_path": "src/main_backup.py",
            "overwrite": False
        }
    }}

class BatchDeleteRequest(BaseModel):
    """Batch delete request"""
    paths: List[str] = Field(..., description="List of paths to delete")
    recursive: bool = Field(default=False, description="Whether to recursively delete directory")
    
    model_config = {"json_schema_extra": {
        "example": {
            "paths": ["src/temp.py", "lib/old/"],
            "recursive": True
        }
    }}

# FileSearchRequest moved to app.core.file_management.models

# ============ Response models =============

class FileNodeInfo(BaseModel):
    """File node information"""
    id: str = Field(description="Node ID")
    name: str = Field(description="Name")
    path: str = Field(description="Relative path")
    type: Literal["file", "directory"] = Field(description="Type")
    size: Optional[int] = Field(default=None, description="File size (bytes)")
    content: Optional[str] = Field(default=None, description="File content")
    extension: Optional[str] = Field(default=None, description="File extension")
    created_at: Optional[datetime] = Field(default=None, description="Creation time")
    modified_at: Optional[datetime] = Field(default=None, description="Modification time")
    children: Optional[List["FileNodeInfo"]] = Field(default=None, description="Child nodes")
    
    model_config = {"from_attributes": True}

class TemplateFilesResponse(BaseModel):
    """File tree response"""
    success: bool = Field(description="Whether successful")
    data: Optional[List[FileNodeInfo]] = Field(default=None, description="File tree")
    total_files: int = Field(default=0, description="Total file count")
    total_size: int = Field(default=0, description="Total size (bytes)")
    message: Optional[str] = Field(default=None, description="Message")
    error: Optional[str] = Field(default=None, description="Error message")

class FileContentResponse(BaseModel):
    """File content response"""
    success: bool = Field(description="Whether successful")
    data: Optional[FileNodeInfo] = Field(default=None, description="File information")
    message: Optional[str] = Field(default=None, description="Message")
    error: Optional[str] = Field(default=None, description="Error message")

class FileOperationResponse(BaseModel):
    """File operation response"""
    success: bool = Field(description="Whether successful")
    data: Optional[FileNodeInfo] = Field(default=None, description="File information after operation")
    message: Optional[str] = Field(default=None, description="Message")
    error: Optional[str] = Field(default=None, description="Error message")

class UploadedFileInfo(BaseModel):
    """Uploaded file information"""
    filename: str = Field(description="File name")
    path: str = Field(description="Save path")
    size: int = Field(description="File size")
    success: bool = Field(description="Whether successful")
    error: Optional[str] = Field(default=None, description="Error message")

class FileUploadResponse(BaseModel):
    """File upload response"""
    success: bool = Field(description="Overall success")
    uploaded: List[UploadedFileInfo] = Field(default_factory=list, description="Upload results")
    total: int = Field(description="Total file count")
    succeeded: int = Field(description="Success count")
    failed: int = Field(description="Failed count")
    message: Optional[str] = Field(default=None, description="Message")

class BatchOperationResult(BaseModel):
    """Batch operation result"""
    path: str = Field(description="Path")
    success: bool = Field(description="Whether successful")
    error: Optional[str] = Field(default=None, description="Error message")

class BatchOperationResponse(BaseModel):
    """Batch operation response"""
    success: bool = Field(description="Overall success")
    results: List[BatchOperationResult] = Field(default_factory=list, description="Operation results")
    total: int = Field(description="Total count")
    succeeded: int = Field(description="Success count")
    failed: int = Field(description="Failed count")
    message: Optional[str] = Field(default=None, description="Message")

# FileSearchResult, FileSearchResponse moved to app.core.file_management.models


__all__ = [
    "CreateFileRequest",
    "UpdateFileContentRequest",
    "RenameFileRequest",
    "MoveFileRequest",
    "CopyFileRequest",
    "BatchDeleteRequest",
    "FileNodeInfo",
    "TemplateFilesResponse",
    "FileContentResponse",
    "FileOperationResponse",
    "UploadedFileInfo",
    "FileUploadResponse",
    "BatchOperationResult",
    "BatchOperationResponse",
]

