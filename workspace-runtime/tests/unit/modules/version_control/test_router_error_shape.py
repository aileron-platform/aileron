"""Tests for the shared version-control error envelope."""

from app.modules.version_control.router import _handle_error
from app.modules.version_control.repository import VersionControlError


def test_handle_error_emits_exact_shared_envelope():
    exc = VersionControlError(
        "blocked",
        status_code=409,
        error_code="operation_locked",
        blocking_scope="common_repository",
        stale=True,
        can_force_unlock=True,
    )
    http_exc = _handle_error(exc)
    assert http_exc.status_code == 409
    assert http_exc.detail == {
        "errorCode": "operation_locked",
        "messageKey": "operation_locked",
        "blockingScope": "common_repository",
        "operationStatus": None,
        "stale": True,
        "canForceUnlock": True,
    }


def test_handle_error_keeps_all_envelope_fields_when_values_are_empty():
    exc = VersionControlError("boom", status_code=500, error_code="VC_STATUS_FAILED")
    http_exc = _handle_error(exc)
    assert set(http_exc.detail) == {
        "errorCode",
        "messageKey",
        "blockingScope",
        "operationStatus",
        "stale",
        "canForceUnlock",
    }
    assert "lockState" not in http_exc.detail
