"""User Profile API 整合Testing"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as db_models


@pytest.mark.integration
def test_get_user_profile_returns_profile(
    internal_client, create_user
) -> None:
    """Testing獲Getting用Household個PersonFile"""
    client, _ = internal_client
    user = create_user(
        id="user-123",
        username="developer",
        first_name="On發",
        last_name="者",
        display_name="On發者",
        email="developer@example.com",
        avatar_url="https://cdn.example.com/avatar.png",
    )

    response = client.get(f"/api/v1/users/{user.id}/profile")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["userId"] == "user-123"
    assert data["username"] == "developer"
    assert data["firstName"] == "On發"
    assert data["lastName"] == "者"
    assert data["email"] == "developer@example.com"
    assert data["avatarUrl"] == "https://cdn.example.com/avatar.png"


@pytest.mark.integration
def test_update_user_profile_updates_fields(internal_client, create_user) -> None:
    """TestingMoreNew用Household個PersonFile"""
    client, session_factory = internal_client
    user = create_user(
        id="user-234",
        first_name="原始",
        last_name="Name",
        display_name="原始Name",
        email="old@example.com",
    )

    payload = {
        "firstName": "New",
        "lastName": "Name",
        "avatarUrl": "https://cdn.example.com/new-avatar.png",
    }

    response = client.put(f"/api/v1/users/{user.id}/profile", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["firstName"] == "New"
    assert data["lastName"] == "Name"

    # VerifyingData庫中的DataIndeed已MoreNew
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "New"
        assert refreshed.last_name == "Name"
        assert refreshed.display_name == "New Name"
        assert refreshed.avatar_url == "https://cdn.example.com/new-avatar.png"


@pytest.mark.integration
def test_get_user_profile_not_found(internal_client) -> None:
    """Testing獲Getting不存At用Household的個PersonFile時返Back 404"""
    client, _ = internal_client

    response = client.get("/api/v1/users/non-existent-user/profile")

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_not_found(internal_client) -> None:
    """TestingMoreNew不存At用Household的個PersonFile時返Back 404"""
    client, _ = internal_client

    payload = {"firstName": "NewName"}
    response = client.put("/api/v1/users/non-existent-user/profile", json=payload)

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_partial_update(internal_client, create_user) -> None:
    """TestingPartMoreNew用Household個PersonFile"""
    client, session_factory = internal_client
    user = create_user(
        id="user-345",
        first_name="原始",
        last_name="Name",
        display_name="原始Name",
        email="original@example.com",
    )

    # 只MoreNew firstName
    payload = {"firstName": "New"}
    response = client.put(f"/api/v1/users/{user.id}/profile", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["firstName"] == "New"
    assert data["lastName"] == "Name"  # Keeping原Value
    assert data["email"] == "original@example.com"  # Keeping原Value

    # VerifyingData庫中Only指定欄位被MoreNew
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "New"
        assert refreshed.last_name == "Name"
        assert refreshed.display_name == "New Name"
        assert refreshed.email == "original@example.com"
