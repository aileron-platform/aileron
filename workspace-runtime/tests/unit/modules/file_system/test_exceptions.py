from __future__ import annotations

from app.modules.file_system.exceptions import (
    ContentConflictException,
    DirectoryNotEmptyException,
    FileAlreadyExistsException,
    FileErrorCode,
    FileManagementException,
    FileNotFoundException,
    FileTooLargeException,
    InvalidPathException,
    InvalidScopeException,
    PermissionDeniedException,
    ReadonlyScopeException,
)


def test_file_management_exception_to_dict() -> None:
    exc = FileManagementException("ERR", "failed", {"path": "/tmp/a"}, 418)

    assert exc.status_code == 418
    assert exc.to_dict() == {
        "code": "ERR",
        "message": "failed",
        "details": {"path": "/tmp/a"},
    }


def test_file_not_found_exception_includes_scope() -> None:
    exc = FileNotFoundException("/tmp/missing.txt", scope="workspace")

    assert exc.code == FileErrorCode.FILE_NOT_FOUND
    assert exc.status_code == 404
    assert exc.details == {"path": "/tmp/missing.txt", "scope": "workspace"}


def test_other_file_exceptions_use_expected_codes_and_messages() -> None:
    cases = [
        (
            FileAlreadyExistsException("/tmp/existing.txt"),
            FileErrorCode.FILE_ALREADY_EXISTS,
            409,
        ),
        (ReadonlyScopeException("system"), FileErrorCode.READONLY_SCOPE, 403),
        (InvalidScopeException("unknown"), FileErrorCode.INVALID_SCOPE, 400),
        (
            InvalidPathException("../etc/passwd", "path traversal"),
            FileErrorCode.INVALID_PATH,
            400,
        ),
        (
            PermissionDeniedException("/tmp/file", "write"),
            FileErrorCode.PERMISSION_DENIED,
            403,
        ),
        (
            FileTooLargeException("/tmp/big.bin", 1024, 512),
            FileErrorCode.FILE_TOO_LARGE,
            413,
        ),
        (
            ContentConflictException("/tmp/conflict.txt", "v1", "v2"),
            FileErrorCode.CONTENT_CONFLICT,
            409,
        ),
        (
            DirectoryNotEmptyException("/tmp/dir"),
            FileErrorCode.DIRECTORY_NOT_EMPTY,
            400,
        ),
    ]

    for exc, code, status in cases:
        assert exc.code == code
        assert exc.status_code == status
        assert exc.to_dict()["message"] == exc.message
