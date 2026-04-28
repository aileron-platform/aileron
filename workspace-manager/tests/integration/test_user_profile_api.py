"""User Profile API Integration Testing"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as db_models


@pytest.mark.integration
def test_get_user_profile_returns_profile(
    internal_client, create_user
) -> None:
    """Test getting user profile"""
    client, _ = internal_client
    user = create_user(
        id="user-123",
        username="developer",
        first_name="John",
        last_name="Doe",
        display_name="John Doe",
        email="developer@example.com",
        avatar_url="https://cdn.example.com/avatar.png",
    )

    response = client.get(f"/api/v1/users/{user.id}/profile")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["userId"] == "user-123"
    assert data["username"] == "developer"
    assert data["firstName"] == "John"
    assert data["lastName"] == "Doe"
    assert data["email"] == "developer@example.com"
    assert data["avatarUrl"] == "https://cdn.example.com/avatar.png"


@pytest.mark.integration
def test_update_user_profile_updates_fields(internal_client, create_user) -> None:
    """Test updating user profile"""
    client, session_factory = internal_client
    user = create_user(
        id="user-234",
        first_name="Original",
        last_name="Name",
        display_name="Original Name",
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

    # Verify data in database is indeed updated
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "New"
        assert refreshed.last_name == "Name"
        assert refreshed.display_name == "New Name"
        assert refreshed.avatar_url == "https://cdn.example.com/new-avatar.png"


@pytest.mark.integration
def test_get_user_profile_not_found(internal_client) -> None:
    """Test getting profile for non-existent user returns 404"""
    client, _ = internal_client

    response = client.get("/api/v1/users/non-existent-user/profile")

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_not_found(internal_client) -> None:
    """Test updating profile for non-existent user returns 404"""
    client, _ = internal_client

    payload = {"firstName": "NewName"}
    response = client.put("/api/v1/users/non-existent-user/profile", json=payload)

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_partial_update(internal_client, create_user) -> None:
    """Test partial update of user profile"""
    client, session_factory = internal_client
    user = create_user(
        id="user-345",
        first_name="Original",
        last_name="Name",
        display_name="Original Name",
        email="original@example.com",
    )

    # Only update firstName
    payload = {"firstName": "New"}
    response = client.put(f"/api/v1/users/{user.id}/profile", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["firstName"] == "New"
    assert data["lastName"] == "Name"  # Keep original value
    assert data["email"] == "original@example.com"  # Keep original value

    # Verify only specified fields are updated in database
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "New"
        assert refreshed.last_name == "Name"
        assert refreshed.display_name == "New Name"
        assert refreshed.email == "original@example.com"
