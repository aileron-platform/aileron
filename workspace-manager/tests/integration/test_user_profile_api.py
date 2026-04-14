"""User Profile API 整合測試"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models as db_models


@pytest.mark.integration
def test_get_user_profile_returns_profile(
    internal_client, create_user
) -> None:
    """測試獲取用戶個人檔案"""
    client, _ = internal_client
    user = create_user(
        id="user-123",
        username="developer",
        first_name="開發",
        last_name="者",
        display_name="開發者",
        email="developer@example.com",
        avatar_url="https://cdn.example.com/avatar.png",
    )

    response = client.get(f"/api/v1/users/{user.id}/profile")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["userId"] == "user-123"
    assert data["username"] == "developer"
    assert data["firstName"] == "開發"
    assert data["lastName"] == "者"
    assert data["email"] == "developer@example.com"
    assert data["avatarUrl"] == "https://cdn.example.com/avatar.png"


@pytest.mark.integration
def test_update_user_profile_updates_fields(internal_client, create_user) -> None:
    """測試更新用戶個人檔案"""
    client, session_factory = internal_client
    user = create_user(
        id="user-234",
        first_name="原始",
        last_name="名稱",
        display_name="原始名稱",
        email="old@example.com",
    )

    payload = {
        "firstName": "新",
        "lastName": "名稱",
        "avatarUrl": "https://cdn.example.com/new-avatar.png",
    }

    response = client.put(f"/api/v1/users/{user.id}/profile", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["firstName"] == "新"
    assert data["lastName"] == "名稱"

    # 驗證資料庫中的資料確實已更新
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "新"
        assert refreshed.last_name == "名稱"
        assert refreshed.display_name == "新 名稱"
        assert refreshed.avatar_url == "https://cdn.example.com/new-avatar.png"


@pytest.mark.integration
def test_get_user_profile_not_found(internal_client) -> None:
    """測試獲取不存在用戶的個人檔案時返回 404"""
    client, _ = internal_client

    response = client.get("/api/v1/users/non-existent-user/profile")

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_not_found(internal_client) -> None:
    """測試更新不存在用戶的個人檔案時返回 404"""
    client, _ = internal_client

    payload = {"firstName": "新名稱"}
    response = client.put("/api/v1/users/non-existent-user/profile", json=payload)

    assert response.status_code == 404
    assert "User not found" in response.json()["detail"]


@pytest.mark.integration
def test_update_user_profile_partial_update(internal_client, create_user) -> None:
    """測試部分更新用戶個人檔案"""
    client, session_factory = internal_client
    user = create_user(
        id="user-345",
        first_name="原始",
        last_name="名稱",
        display_name="原始名稱",
        email="original@example.com",
    )

    # 只更新 firstName
    payload = {"firstName": "新"}
    response = client.put(f"/api/v1/users/{user.id}/profile", json=payload)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["firstName"] == "新"
    assert data["lastName"] == "名稱"  # 保持原值
    assert data["email"] == "original@example.com"  # 保持原值

    # 驗證資料庫中只有指定欄位被更新
    with session_factory() as session:
        refreshed = session.get(db_models.User, user.id)
        assert refreshed is not None
        assert refreshed.first_name == "新"
        assert refreshed.last_name == "名稱"
        assert refreshed.display_name == "新 名稱"
        assert refreshed.email == "original@example.com"
