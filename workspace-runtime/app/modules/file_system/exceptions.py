"""統一的檔案管理異常定義"""

from typing import Optional, Dict, Any


class FileErrorCode:
    """統一的錯誤代碼"""
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ALREADY_EXISTS = "FILE_ALREADY_EXISTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_PATH = "INVALID_PATH"
    INVALID_SCOPE = "INVALID_SCOPE"
    READONLY_SCOPE = "READONLY_SCOPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    CONTENT_CONFLICT = "CONTENT_CONFLICT"
    DIRECTORY_NOT_EMPTY = "DIRECTORY_NOT_EMPTY"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"


class FileManagementException(Exception):
    """檔案管理基礎異常"""

    # 預設 HTTP 狀態碼
    status_code = 500

    def __init__(
        self,
        code: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        # backward compatibility:
        # FileManagementException("Not found", status_code=404)
        # => code="FILE_ERROR", message="Not found"
        if message is None:
            self.code = "FILE_ERROR"
            self.message = code
        else:
            self.code = code
            self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details
        }


class FileNotFoundException(FileManagementException):
    """檔案不存在"""

    status_code = 404

    def __init__(self, path: str, scope: Optional[str] = None):
        details = {"path": path}
        if scope:
            details["scope"] = scope
        super().__init__(
            FileErrorCode.FILE_NOT_FOUND,
            f"File not found: {path}",
            details,
            404
        )


class FileAlreadyExistsException(FileManagementException):
    """檔案已存在"""

    status_code = 409

    def __init__(self, path: str, scope: Optional[str] = None):
        details = {"path": path}
        if scope:
            details["scope"] = scope
        super().__init__(
            FileErrorCode.FILE_ALREADY_EXISTS,
            f"File already exists: {path}",
            details,
            409
        )


class ReadonlyScopeException(FileManagementException):
    """唯讀範圍"""

    status_code = 403

    def __init__(self, scope: str):
        super().__init__(
            FileErrorCode.READONLY_SCOPE,
            f"Scope '{scope}' is read-only",
            {"scope": scope},
            403
        )


class InvalidScopeException(FileManagementException):
    """無效範圍"""

    status_code = 400

    def __init__(self, scope: str):
        super().__init__(
            FileErrorCode.INVALID_SCOPE,
            f"Invalid scope: {scope}",
            {"scope": scope},
            400
        )


class InvalidPathException(FileManagementException):
    """無效路徑"""

    status_code = 400

    def __init__(self, path: str, reason: str = ""):
        message = f"Invalid path: {path}"
        if reason:
            message += f" ({reason})"
        super().__init__(
            FileErrorCode.INVALID_PATH,
            message,
            {"path": path, "reason": reason},
            400
        )


class PermissionDeniedException(FileManagementException):
    """權限不足"""

    status_code = 403

    def __init__(self, path: str, operation: str):
        super().__init__(
            FileErrorCode.PERMISSION_DENIED,
            f"Permission denied for {operation} on: {path}",
            {"path": path, "operation": operation},
            403
        )


class FileTooLargeException(FileManagementException):
    """檔案過大"""

    status_code = 413

    def __init__(self, path: str, size: int, max_size: int):
        super().__init__(
            FileErrorCode.FILE_TOO_LARGE,
            f"File too large: {size} bytes (max: {max_size} bytes)",
            {"path": path, "size": size, "maxSize": max_size},
            413
        )


class ContentConflictException(FileManagementException):
    """內容衝突"""

    status_code = 409

    def __init__(self, path: str, expected_version: str, actual_version: str):
        super().__init__(
            FileErrorCode.CONTENT_CONFLICT,
            f"Content conflict: expected version {expected_version}, got {actual_version}",
            {
                "path": path,
                "expectedVersion": expected_version,
                "actualVersion": actual_version
            },
            409
        )


class DirectoryNotEmptyException(FileManagementException):
    """目錄不為空"""

    status_code = 400

    def __init__(self, path: str):
        super().__init__(
            FileErrorCode.DIRECTORY_NOT_EMPTY,
            f"Directory not empty: {path}. Use recursive=true to delete.",
            {"path": path},
            400
        )


class InvalidFileTypeException(FileManagementException):
    """無效的檔案類型"""

    status_code = 400

    def __init__(self, path: str, file_type: str):
        super().__init__(
            FileErrorCode.INVALID_FILE_TYPE,
            f"Invalid file type '{file_type}' for: {path}",
            {"path": path, "fileType": file_type},
            400
        )
