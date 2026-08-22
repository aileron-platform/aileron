"""Tests for the read-only OIDC profile snapshot service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.db.models import User as DBUser
from app.modules.identity.profile import UserProfileService
from app.modules.settings.models import UserProfile


@pytest.fixture
def db_session() -> MagicMock:
    return MagicMock(spec=Session)


@pytest.fixture
def service(db_session: MagicMock) -> UserProfileService:
    return UserProfileService(db_session)


def test_get_profile_returns_provider_owned_snapshot(
    service: UserProfileService, db_session: MagicMock
) -> None:
    user = DBUser(
        id="user-123",
        oidc_issuer="https://issuer.example",
        oidc_subject="subject-123",
        username="testuser",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
    )
    db_session.query.return_value.filter.return_value.first.return_value = user

    result = service.get_profile("user-123")

    assert isinstance(result, UserProfile)
    assert result.user_id == "user-123"
    assert result.username == "testuser"
    assert result.email == "test@example.com"
    assert result.avatar_url == "https://example.com/avatar.jpg"
    db_session.commit.assert_not_called()


def test_get_profile_accepts_special_use_provider_email_snapshot(
    service: UserProfileService, db_session: MagicMock
) -> None:
    user = DBUser(
        id="user-123",
        username="testuser",
        email="testuser@identity.invalid",
    )
    db_session.query.return_value.filter.return_value.first.return_value = user

    result = service.get_profile("user-123")

    assert isinstance(result, UserProfile)
    assert result.email == "testuser@identity.invalid"
    db_session.commit.assert_not_called()


def test_get_profile_returns_none_for_unknown_user(
    service: UserProfileService, db_session: MagicMock
) -> None:
    db_session.query.return_value.filter.return_value.first.return_value = None

    assert service.get_profile("missing") is None


def test_profile_service_has_no_external_profile_mutation_api() -> None:
    assert not hasattr(UserProfileService, "update_profile")
