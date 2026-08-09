"""Unified file management module - Workspace Manager

This module provides file management interface consistent with Workspace Runtime
"""

# Copied unified models and exceptions from workspace-runtime
# To maintain consistency, we redefine the same structure here

from .exceptions import (
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileErrorCode,
    FileManagementException,
    FileNotFoundException,
    FileTooLargeException,
    InvalidPathException,
    PermissionDeniedException,
)
from .models import (
    ConflictStrategy,
    FileConflictBatchResult,
    FileConflictExecutionRequest,
    FileConflictItem,
    FileConflictPreflightRequest,
    FileConflictPreflightResponse,
    FileConflictResolution,
    FileConflictResultItem,
    FileConflictSource,
    FileContentResponse,
    FileExtractExecutionRequest,
    FileNode,
    FileTreeResponse,
)

__all__ = [
    # Models
    "FileNode",
    "FileTreeResponse",
    "FileContentResponse",
    "ConflictStrategy",
    "FileConflictBatchResult",
    "FileConflictExecutionRequest",
    "FileConflictItem",
    "FileConflictPreflightRequest",
    "FileConflictPreflightResponse",
    "FileConflictResolution",
    "FileConflictResultItem",
    "FileConflictSource",
    "FileExtractExecutionRequest",
    # Exceptions
    "FileErrorCode",
    "FileManagementException",
    "FileNotFoundException",
    "FileAlreadyExistsException",
    "InvalidPathException",
    "PermissionDeniedException",
    "FileTooLargeException",
    "DirectoryNotEmptyException",
]
