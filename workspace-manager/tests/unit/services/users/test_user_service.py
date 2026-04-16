"""UserService 單元測試"""

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
    """Mock 資料庫 Session"""
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
    """範例資料庫用戶"""
    return user_factory()


@pytest.fixture
def user_service(mock_db_session):
    """UserService 實例"""
    return UserService(mock_db_session)


# ============================================================================
# User List Tests
# ============================================================================

@pytest.mark.unit
class TestUserList:
    """用戶列表測試"""

    def test_list_users_success(
        self, user_service, mock_db_session, user_factory
    ):
        """測試：成功列出所有用戶"""
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
        """測試：空用戶列表"""
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
    """用戶查詢測試"""

    def test_get_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功獲取用戶"""
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
        """測試：用戶不存在返回 None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = user_service.get("nonexistent-user")

        # Assert
        assert result is None

    def test_get_by_email_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：通過 email 成功獲取用戶"""
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
        """測試：email 不存在返回 None"""
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
    """用戶創建測試"""

    def test_create_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功創建用戶"""
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
        """測試：重複 email 創建失敗"""
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
    """用戶更新測試"""

    def test_update_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功更新用戶"""
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
        """測試：更新不存在的用戶返回 None"""
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
    """用戶刪除測試"""

    def test_delete_user_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功刪除用戶"""
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
        """測試：刪除不存在的用戶優雅處理"""
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
    """用戶登錄測試"""

    def test_mark_login_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功標記用戶登錄"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        # Act
        user_service.mark_login("user-123")

        # Assert
        mock_db_session.commit.assert_called_once()

    def test_mark_login_user_not_found(
        self, user_service, mock_db_session
    ):
        """測試：用戶不存在時優雅處理"""
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
    """用戶個人檔案測試"""

    def test_get_profile_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功獲取用戶檔案"""
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
        """測試：用戶檔案不存在返回 None"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = user_service.get_profile("nonexistent-user")

        # Assert
        assert result is None

    def test_update_profile_success(
        self, user_service, mock_db_session, sample_db_user
    ):
        """測試：成功更新用戶檔案"""
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
        """測試：更新不存在的用戶檔案返回 None"""
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
        """測試：部分欄位更新"""
        # Arrange
        mock_db_session.query.return_value.filter.return_value.first.return_value = sample_db_user

        profile_update = UserProfileUpdate(avatar_url="https://example.com/new.jpg")

        # Act
        result = user_service.update_profile("user-123", profile_update)

        # Assert
        assert result is not None
        assert sample_db_user.avatar_url == "https://example.com/new.jpg"

