"""Auth request-state helper tests."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.modules.auth.auth_decorators import get_current_user_id


def test_get_current_user_id_reads_request_state(request_factory):
    request = request_factory("/api/test")
    request.state.user_id = "user-123"

    assert get_current_user_id(request) == "user-123"


def test_get_current_user_id_requires_state_user_id(request_factory):
    request = request_factory("/api/test")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "auth.unauthenticated"


@pytest.mark.parametrize("invalid_identity", ["", 123])
def test_get_current_user_id_rejects_invalid_local_identity(
    request_factory,
    invalid_identity,
):
    request = request_factory("/api/v1/workspaces")
    request.state.user_id = invalid_identity
    request.state.translate = lambda key: f"translated:{key}"

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(request)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "translated:auth.unauthenticated"
