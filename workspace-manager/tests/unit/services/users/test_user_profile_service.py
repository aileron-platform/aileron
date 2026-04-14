"""UserProfileService 單元測試"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.db.models import User as DBUser
from app.models import UserProfile, UserProfileUpdate
from app.services.user_profile_service import UserProfileService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock 資料庫 Session"""
    session = MagicMock(spec=Session)
    session.query = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def keycloak_sync():
    """Mock KeycloakProfileSync"""
    return MagicMock()


@pytest.fixture
def user_profile_service(db_session, keycloak_sync):
    """UserProfileService 實例"""
    return UserProfileService(db=db_session, keycloak_sync=keycloak_sync)


@pytest.fixture
def sample_db_user():
    """範例資料庫用戶"""
    user = DBUser(
        id="user-123",
        username="testuser",
        email="test@example.com",
        first_name="Test",
        last_name="User",
        display_name="Test User",
        avatar_url="https://example.com/avatar.jpg",
    )
    return user


# ============================================================================
# 個人檔案查詢測試
# ============================================================================

@pytest.mark.unit
class TestGetProfile:
    """個人檔案查詢測試"""

    def test_get_profile_exists(self, user_profile_service, db_session, sample_db_user):
        """測試：查詢存在的個人檔案"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        result = user_profile_service.get_profile("user-123")

        assert result is not None
        assert isinstance(result, UserProfile)
        assert result.user_id == "user-123"
        assert result.username == "testuser"
        assert result.first_name == "Test"
        assert result.last_name == "User"
        assert result.email == "test@example.com"
        assert result.avatar_url == "https://example.com/avatar.jpg"

    def test_get_profile_not_found(self, user_profile_service, db_session):
        """測試：查詢不存在的個人檔案返回 None"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        result = user_profile_service.get_profile("nonexistent-user")

        assert result is None

    def test_get_profile_with_none_names(self, user_profile_service, db_session):
        """測試：名字為 None 時返回空字串"""
        user = DBUser(
            id="user-123",
            username="testuser",
            email="test@example.com",
            first_name=None,
            last_name=None,
            display_name=None,
            avatar_url=None,
        )
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = user
        db_session.query.return_value = mock_query

        result = user_profile_service.get_profile("user-123")

        assert result is not None
        assert result.first_name == ""
        assert result.last_name == ""
        assert result.avatar_url is None


# ============================================================================
# 個人檔案更新測試
# ============================================================================

@pytest.mark.unit
class TestUpdateProfile:
    """個人檔案更新測試"""

    @pytest.mark.asyncio
    async def test_update_first_and_last_name(self, user_profile_service, db_session, sample_db_user):
        """測試：更新名字和姓氏"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(
            first_name="NewFirst",
            last_name="NewLast",
        )

        result = await user_profile_service.update_profile("user-123", update_data)

        assert result is not None
        assert sample_db_user.first_name == "NewFirst"
        assert sample_db_user.last_name == "NewLast"
        assert sample_db_user.display_name == "NewFirst NewLast"
        db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_avatar_only(self, user_profile_service, db_session, sample_db_user):
        """測試：只更新頭像 URL"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(avatar_url="https://example.com/new-avatar.jpg")

        result = await user_profile_service.update_profile("user-123", update_data)

        assert result is not None
        assert sample_db_user.avatar_url == "https://example.com/new-avatar.jpg"

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(self, user_profile_service, db_session):
        """測試：更新不存在的用戶返回 None"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(first_name="Updated")

        result = await user_profile_service.update_profile("nonexistent-user", update_data)

        assert result is None
        db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_first_name_only(self, user_profile_service, db_session, sample_db_user):
        """測試：只更新名字，display_name 自動計算"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(first_name="NewFirst")

        result = await user_profile_service.update_profile("user-123", update_data)

        assert result is not None
        assert sample_db_user.first_name == "NewFirst"
        assert sample_db_user.display_name == "NewFirst User"
