"""Unified file management module - Workspace Manager

This module provides file management interface consistent with Workspace Runtime
"""

# Copied unified models and exceptions from workspace-runtime
# To maintain consistency, we redefine the same structure here

from .models import (
    FileNode,
    FileTreeRequest,
    FileContentRequest,
    FileWriteRequest,
    FileCreateRequest,
    FileDeleteRequest,
    FileCopyRequest,
    FileMoveRequest,
    BatchDeleteRequest,
    FileTreeResponse,
    FileContentResponse,
    FileOperationResponse,
    BatchOperationResponse,
    FileError,
    FileSearchRequest,
    FileSearchResult,
    FileSearchResponse,
    FileUploadResult,
    FileUploadResponse,
)

from .exceptions import (
    FileErrorCode,
    FileManagementException,
    FileNotFoundException,
    FileAlreadyExistsException,
    InvalidScopeException,
    InvalidPathException,
    PermissionDeniedException,
    FileTooLargeException,
    DirectoryNotEmptyException,
    KnowledgeBasePathNotWritableError,
    KnowledgeBaseRawRootCannotBeDeletedError,
)

__all__ = [
    # Models
    "FileNode",
    "FileTreeRequest",
    "FileContentRequest",
    "FileWriteRequest",
    "FileCreateRequest",
    "FileDeleteRequest",
    "FileCopyRequest",
    "FileMoveRequest",
    "BatchDeleteRequest",
    "FileTreeResponse",
    "FileContentResponse",
    "FileOperationResponse",
    "BatchOperationResponse",
    "FileError",
    "FileSearchRequest",
    "FileSearchResult",
    "FileSearchResponse",
    "FileUploadResult",
    "FileUploadResponse",
    # Exceptions
    "FileErrorCode",
    "FileManagementException",
    "FileNotFoundException",
    "FileAlreadyExistsException",
    "InvalidScopeException",
    "InvalidPathException",
    "PermissionDeniedException",
    "FileTooLargeException",
    "DirectoryNotEmptyException",
    "KnowledgeBasePathNotWritableError",
    "KnowledgeBaseRawRootCannotBeDeletedError",
]
