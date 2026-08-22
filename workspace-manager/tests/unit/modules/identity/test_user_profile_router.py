"""Unit tests for the user profile route contract."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.modules.auth.auth_decorators import get_current_user_id
from app.modules.identity.profile import (
    UserProfileService,
    get_user_profile_service,
)
from app.modules.identity.router import get_user_profile, router
from app.modules.settings.models import UserProfile


def _request() -> MagicMock:
    request = MagicMock(spec=Request)
    request.state = SimpleNamespace(translate=lambda key: key)
    return request


def test_get_user_profile_returns_special_use_email_over_http() -> None:
    service = MagicMock(spec=UserProfileService)
    service.get_profile.return_value = UserProfile(
        userId="user-123",
        username="testuser",
        email="testuser@identity.invalid",
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user_id] = lambda: "viewer-123"
    app.dependency_overrides[get_user_profile_service] = lambda: service

    with TestClient(app) as client:
        response = client.get("/users/user-123/profile")

    assert response.status_code == 200
    assert response.json()["data"]["userId"] == "user-123"
    assert response.json()["data"]["email"] == "testuser@identity.invalid"


@pytest.mark.asyncio
async def test_get_user_profile_preserves_unknown_user_404() -> None:
    service = MagicMock(spec=UserProfileService)
    service.get_profile.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_user_profile(
            user_id="missing",
            request=_request(),
            _current_user_id="viewer-123",
            service=service,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "user.not_found"
