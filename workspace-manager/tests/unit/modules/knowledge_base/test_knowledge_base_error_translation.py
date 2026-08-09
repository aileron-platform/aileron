"""Knowledge base error translation tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.modules.knowledge_base.router import _translate_kb_message


@pytest.mark.unit
@pytest.mark.parametrize(
    ("code", "message_key"),
    [
        ("KB_NOT_FOUND", "knowledge_base.not_found"),
        ("KB_ATTACHMENT_NOT_FOUND", "knowledge_base.attachment_not_found"),
        ("KB_ACCESS_DENIED", "knowledge_base.access_denied"),
        ("KB_PERMISSION_DENIED", "knowledge_base.permission_denied"),
        ("KB_ALREADY_ATTACHED", "knowledge_base.already_attached"),
        ("KB_MOUNT_ALIAS_CONFLICT", "knowledge_base.alias_conflict"),
        ("KB_DELETE_ATTACHMENT_CONFLICT", "knowledge_base.in_use"),
        ("KB_SLUG_CONFLICT", "knowledge_base.slug_conflict"),
        ("KB_SHARE_DUPLICATE_TARGET", "knowledge_base.share.duplicate_target"),
        ("KB_SHARE_INVALID_TARGET_TYPE", "knowledge_base.share.invalid_target_type"),
        ("KB_SHARE_TARGET_NOT_FOUND", "knowledge_base.share.target_not_found"),
        ("KB_SHARE_OWNER_TARGET_FORBIDDEN", "knowledge_base.share.owner_forbidden"),
        ("KB_SHARE_FORBIDDEN", "knowledge_base.permission_denied"),
        ("KB_SHARE_INVALID_ROLE", "knowledge_base.invalid.share_role"),
        ("KB_INVALID_SLUG", "knowledge_base.invalid.slug"),
        ("KB_OWNER_NOT_FOUND", "knowledge_base.invalid.owner"),
        ("KB_INVALID_ROLE", "knowledge_base.invalid.role"),
        ("KB_INVALID_QUOTA", "knowledge_base.invalid.quota"),
        ("KB_QUOTA_BELOW_USAGE", "knowledge_base.invalid.quota_below_usage"),
        ("KB_CONFLICT", "knowledge_base.conflict"),
        ("KB_INVALID_REQUEST", "knowledge_base.invalid.request"),
        ("INVALID_PATH", "knowledge_base.file.invalid_path"),
        ("FILE_TOO_LARGE", "knowledge_base.file.too_large"),
        ("CONTENT_CONFLICT", "knowledge_base.file.content_conflict"),
        ("DIRECTORY_NOT_EMPTY", "knowledge_base.file.directory_not_empty"),
        ("KB_QUOTA_EXCEEDED", "knowledge_base.file.kb_quota_exceeded"),
        ("USER_KB_QUOTA_EXCEEDED", "knowledge_base.file.owner_quota_exceeded"),
        ("PATH_NOT_WRITABLE", "knowledge_base.file.path_not_writable"),
        (
            "RAW_ROOT_CANNOT_BE_DELETED",
            "knowledge_base.file.raw_root_cannot_be_deleted",
        ),
        (
            "LOCAL_HISTORY_ENTRY_NOT_FOUND",
            "knowledge_base.file.history_entry_not_found",
        ),
        (
            "KB_VERSION_CONTROL_DISABLED",
            "knowledge_base.git.version_control_disabled",
        ),
        ("GIT_REPO_NOT_FOUND", "knowledge_base.git.repo_not_found"),
        ("GIT_NO_CHANGES", "knowledge_base.git.no_changes_to_commit"),
        (
            "GIT_PATH_OUTSIDE_REPOSITORY",
            "knowledge_base.git.path_outside_repository",
        ),
        (
            "GIT_REPOSITORY_ALREADY_INITIALIZED",
            "knowledge_base.git.repository_already_initialized",
        ),
        (
            "KB_GIT_OPERATION_IN_PROGRESS",
            "knowledge_base.git.operation_in_progress",
        ),
        ("KB_GIT_OPERATION_FAILED", "knowledge_base.git.operation_failed"),
    ],
)
def test_translate_kb_message_maps_error_code_to_i18n_key(
    code: str,
    message_key: str,
) -> None:
    translate = Mock(return_value="localized")

    result = _translate_kb_message(translate, code=code, details={})

    assert result == "localized"
    translate.assert_called_once_with(message_key)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("code", "details", "message_key", "expected_parameters"),
    [
        (
            "FILE_NOT_FOUND",
            {"path": "/raw/missing.md"},
            "knowledge_base.file.not_found",
            {"path": "/raw/missing.md"},
        ),
        (
            "FILE_ALREADY_EXISTS",
            {"path": "/raw/existing.md"},
            "knowledge_base.file.exists",
            {"path": "/raw/existing.md"},
        ),
        (
            "INVALID_FILE_TYPE",
            {"extension": ".exe"},
            "knowledge_base.file.invalid_type",
            {"extension": ".exe"},
        ),
        (
            "FILE_NOT_FOUND",
            {},
            "knowledge_base.file.not_found",
            {"path": ""},
        ),
        (
            "FILE_ALREADY_EXISTS",
            {},
            "knowledge_base.file.exists",
            {"path": ""},
        ),
        (
            "INVALID_FILE_TYPE",
            {},
            "knowledge_base.file.invalid_type",
            {"extension": ""},
        ),
    ],
)
def test_translate_kb_message_forwards_expected_detail(
    code: str,
    details: dict,
    message_key: str,
    expected_parameters: dict,
) -> None:
    translate = Mock(return_value="localized")

    result = _translate_kb_message(translate, code=code, details=details)

    assert result == "localized"
    translate.assert_called_once_with(message_key, **expected_parameters)


@pytest.mark.unit
def test_translate_kb_message_uses_unexpected_error_for_unknown_code() -> None:
    translate = Mock(return_value="localized")

    result = _translate_kb_message(
        translate,
        code="UNKNOWN_KB_ERROR",
        details={"path": "/ignored"},
    )

    assert result == "localized"
    translate.assert_called_once_with("knowledge_base.unexpected_error")
