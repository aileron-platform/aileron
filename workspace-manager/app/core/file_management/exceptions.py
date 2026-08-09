"""Unified file management exception definitions"""

from typing import Any, Dict, Optional


class FileErrorCode:
    """Unified error codes"""

    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ALREADY_EXISTS = "FILE_ALREADY_EXISTS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_PATH = "INVALID_PATH"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    DIRECTORY_NOT_EMPTY = "DIRECTORY_NOT_EMPTY"


class FileManagementException(Exception):
    """Base file management exception"""

    # Default HTTP status code
    status_code = 500

    def __init__(
        self,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class FileNotFoundException(FileManagementException):
    """File not found"""

    status_code = 404

    def __init__(self, path: str, scope: Optional[str] = None):
        details = {"path": path}
        if scope:
            details["scope"] = scope
        super().__init__(
            FileErrorCode.FILE_NOT_FOUND, f"File not found: {path}", details, 404
        )


class FileAlreadyExistsException(FileManagementException):
    """File already exists"""

    status_code = 409

    def __init__(self, path: str, scope: Optional[str] = None):
        details = {"path": path}
        if scope:
            details["scope"] = scope
        super().__init__(
            FileErrorCode.FILE_ALREADY_EXISTS,
            f"File already exists: {path}",
            details,
            409,
        )


class InvalidPathException(FileManagementException):
    """Invalid path"""

    status_code = 400

    def __init__(self, path: str, reason: str = ""):
        message = f"Invalid path: {path}"
        if reason:
            message += f" ({reason})"
        super().__init__(
            FileErrorCode.INVALID_PATH, message, {"path": path, "reason": reason}, 400
        )


class PermissionDeniedException(FileManagementException):
    """Permission denied"""

    status_code = 403

    def __init__(self, path: str, operation: str):
        super().__init__(
            FileErrorCode.PERMISSION_DENIED,
            f"Permission denied for {operation} on: {path}",
            {"path": path, "operation": operation},
            403,
        )


class FileTooLargeException(FileManagementException):
    """File too large"""

    status_code = 413

    def __init__(self, path: str, size: int, max_size: int):
        super().__init__(
            FileErrorCode.FILE_TOO_LARGE,
            f"File too large: {size} bytes (max: {max_size} bytes)",
            {"path": path, "size": size, "maxSize": max_size},
            413,
        )


class DirectoryNotEmptyException(FileManagementException):
    """Directory not empty"""

    status_code = 400

    def __init__(self, path: str):
        super().__init__(
            FileErrorCode.DIRECTORY_NOT_EMPTY,
            f"Directory not empty: {path}. Use recursive=true to delete.",
            {"path": path},
            400,
        )
