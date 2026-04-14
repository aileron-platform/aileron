"""統一的檔案管理模組 - Workspace Manager

此模組提供與 Workspace Runtime 一致的檔案管理介面
"""

# 從 workspace-runtime 複製的統一模型和異常
# 為了保持一致性，我們在這裡重新定義相同的結構

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
]

