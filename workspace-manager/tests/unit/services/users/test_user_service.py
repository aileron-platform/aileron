"""UserService 單元Testing"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from app.models import User, UserCreate, UserUpdate, UserProfile, UserProfileUpdate
from app.services.user_service import UserService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Data庫 Session"""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.all.return_value = []
    session.query.return_value.order_by.return_value = session.query.return_value
    session.query.return_value.limit.return_value = session.query.return_value
    session.add = MagicMock()
    session.commit = MagicMock()
    session.delete = MagicMock()
    session.refresh = MagicMock()
    return session


@pytest.fixture
def sample_db_user(user_factory):
    """範例Data庫用Household"""
    return user_factory()


@pytest.fixture
def user_service(mock_db_session):
    """UserService Instance"""
    return UserService(mock_db_session)


# ============================================================================
# User List Tests
# ============================================================================

@pytest.mark.unit
class TestUserList:
    """用HouseholdListing表Testing"""

    def test_list_users_success(
        self, user_service, mock_db_session, user_factory
    ):
        """Testing：SuccessfullyListingOutAll用Household"""
        # Arrange
        users = [user_factory(username=f"user{i}") for i in range(3)]
        mock_db_session.query.return_value.order_by.return_value.all.return_value = users

        # Act
        result = user_service.list()

        # Assert
        assert result.total == 3
        assert len(result.items) == 3

    def test_list_users_empty(
        self, user_service, mock_db_session
    ):
        """Testing：空用HouseholdListing表"""
        # Arrange
        mock_db_session.query.return_value.order_by.return_value.all.return_value = []

        # Act
        result = user_service.list()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0


# ============================================================================
# User Get Tests
# ============================================================================

@pytest.mark.unit
class TestUserGet:
    """用Household查詢Testing"""

    def test_get_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Successfully獲Getting用Household"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        result = user_service.get("user-123")

        # Assert
        assert result is not None
        assert isinstance(result, User)
        assert result.username == sample_db_user.username

    def test_get_user_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：用Household不存At返Back None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = user_service.get("nonexistent-user")

        # Assert
        assert result is None

    def test_get_by_email_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Pass email Successfully獲Getting用Household"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        result = user_service.get_by_email("test@example.com")

        # Assert
        assert result is not None
        assert result.email == sample_db_user.email

    def test_get_by_email_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：email 不存At返Back None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = user_service.get_by_email("nonexistent@example.com")

        # Assert
        assert result is None


# ============================================================================
# User Create Tests
# ============================================================================

@pytest.mark.unit
class TestUserCreate:
    """用Household創建Testing"""

    def test_create_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Successfully創建用Household"""
        # Arrange
        # First call for email check returns None, second call for refresh returns user
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        def mock_refresh(obj):
            obj.id = sample_db_user.id
            obj.username = sample_db_user.username
            obj.email = sample_db_user.email
            obj.display_name = sample_db_user.display_name
            obj.avatar_url = sample_db_user.avatar_url
            obj.is_active = True
            obj.created_at = datetime.now()
            obj.updated_at = datetime.now()

        mock_db_session.refresh.side_effect = mock_refresh

        user_create = UserCreate(
            username="newuser",
            email="newuser@example.com",
            display_name="New User",
            password="password123"
        )

        # Act
        result = user_service.create(user_create)

        # Assert
        assert isinstance(result, User)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_create_user_duplicate_email(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Repeat email 創建Unsuccessfully"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        user_create = UserCreate(
            username="newuser",
            email="test@example.com",
            display_name="New User",
            password="password123"
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Email already registered"):
            user_service.create(user_create)


# ============================================================================
# User Update Tests
# ============================================================================

@pytest.mark.unit
class TestUserUpdate:
    """用HouseholdMoreNewTesting"""

    def test_update_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：SuccessfullyMoreNew用Household"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        user_update = UserUpdate(
            display_name="Updated Name",
            bio="Updated bio"
        )

        # Act
        result = user_service.update("user-123", user_update)

        # Assert
        assert result is not None
        mock_db_session.commit.assert_called_once()

    def test_update_user_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：MoreNew不存At的用Household返Back None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        user_update = UserUpdate(display_name="Updated Name")

        # Act
        result = user_service.update("nonexistent-user", user_update)

        # Assert
        assert result is None


# ============================================================================
# User Delete Tests
# ============================================================================

@pytest.mark.unit
class TestUserDelete:
    """用HouseholdDeleteTesting"""

    def test_delete_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：SuccessfullyDelete用Household"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        user_service.delete("user-123")

        # Assert
        mock_db_session.delete.assert_called_once_with(sample_db_user)
        mock_db_session.commit.assert_called_once()

    def test_delete_user_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：Delete不存At的用Household優雅Handle"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        user_service.delete("nonexistent-user")

        # Assert
        mock_db_session.delete.assert_not_called()


# ============================================================================
# User Login Tests
# ============================================================================

@pytest.mark.unit
class TestUserLogin:
    """用Household登錄Testing"""

    def test_mark_login_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：SuccessfullyMark用Household登錄"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        user_service.mark_login("user-123")

        # Assert
        mock_db_session.commit.assert_called_once()

    def test_mark_login_user_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：用Household不存At時優雅Handle"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        user_service.mark_login("nonexistent-user")

        # Assert
        mock_db_session.commit.assert_not_called()


# ============================================================================
# User Profile Tests
# ============================================================================

@pytest.mark.unit
class TestUserProfile:
    """用Household個PersonFileTesting"""

    def test_get_profile_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Successfully獲Getting用HouseholdFile"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        result = user_service.get_profile("user-123")

        # Assert
        assert result is not None
        assert isinstance(result, UserProfile)
        assert result.user_id == sample_db_user.id

    def test_get_profile_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：用HouseholdFile不存At返Back None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = user_service.get_profile("nonexistent-user")

        # Assert
        assert result is None

    def test_update_profile_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：SuccessfullyMoreNew用HouseholdFile"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        profile_update = UserProfileUpdate(
            first_name="Updated",
            last_name="Name",
        )

        # Act
        result = user_service.update_profile("user-123", profile_update)

        # Assert
        assert result is not None
        assert isinstance(result, UserProfile)
        mock_db_session.commit.assert_called_once()

    def test_update_profile_not_found(
        self, user_service, mock_db_session
    ):
        """Testing：MoreNew不存At的用HouseholdFile返Back None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        profile_update = UserProfileUpdate(first_name="Updated")

        # Act
        result = user_service.update_profile("nonexistent-user", profile_update)

        # Assert
        assert result is None

    def test_update_profile_partial_fields(
        self, user_service, mock_db_session, sample_db_user
    ):
        """Testing：Part欄位MoreNew"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        profile_update = UserProfileUpdate(avatar_url="https://example.com/new.jpg")

        # Act
        result = user_service.update_profile("user-123", profile_update)

        # Assert
        assert result is not None
        assert sample_db_user.avatar_url == "https://example.com/new.jpg"

