"""UserProfileService 單元Testing"""

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
    """Mock Data庫 Session"""
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
    """UserProfileService Instance"""
    return UserProfileService(db=db_session, keycloak_sync=keycloak_sync)


@pytest.fixture
def sample_db_user():
    """範例Data庫用Household"""
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
# 個PersonFile查詢Testing
# ============================================================================

@pytest.mark.unit
class TestGetProfile:
    """個PersonFile查詢Testing"""

    def test_get_profile_exists(self, user_profile_service, db_session, sample_db_user):
        """Testing：查詢存At的個PersonFile"""
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
        """Testing：查詢不存At的個PersonFile返Back None"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        result = user_profile_service.get_profile("nonexistent-user")

        assert result is None

    def test_get_profile_with_none_names(self, user_profile_service, db_session):
        """Testing：名字為 None 時返Back空String"""
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
# 個PersonFileMoreNewTesting
# ============================================================================

@pytest.mark.unit
class TestUpdateProfile:
    """個PersonFileMoreNewTesting"""

    @pytest.mark.asyncio
    async def test_update_first_and_last_name(self, user_profile_service, db_session, sample_db_user):
        """Testing：MoreNew名字和姓氏"""
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
        """Testing：只MoreNew頭像 URL"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(avatar_url="https://example.com/new-avatar.jpg")

        result = await user_profile_service.update_profile("user-123", update_data)

        assert result is not None
        assert sample_db_user.avatar_url == "https://example.com/new-avatar.jpg"

    @pytest.mark.asyncio
    async def test_update_profile_user_not_found(self, user_profile_service, db_session):
        """Testing：MoreNew不存At的用Household返Back None"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(first_name="Updated")

        result = await user_profile_service.update_profile("nonexistent-user", update_data)

        assert result is None
        db_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_first_name_only(self, user_profile_service, db_session, sample_db_user):
        """Testing：只MoreNew名字，display_name 自動計算"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_db_user
        db_session.query.return_value = mock_query

        update_data = UserProfileUpdate(first_name="NewFirst")

        result = await user_profile_service.update_profile("user-123", update_data)

        assert result is not None
        assert sample_db_user.first_name == "NewFirst"
        assert sample_db_user.display_name == "NewFirst User"
