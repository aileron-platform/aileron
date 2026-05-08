"""
Unit Tests for UserSyncService
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.user_sync import (
    UserSyncService,
    UserSyncError,
    UserNotFoundError,
    get_user_sync_service,
)
from app.modules.auth.auth_decorators import (
    PermissionDeniedError,
    get_user_permissions,
    has_permission,
    has_role,
    has_any_role,
    has_all_permissions,
    has_any_permission,
)


class TestUserSyncService:
    """Unit Tests for UserSyncService Class"""

    @pytest.fixture
    def sync_service(self):
        """Create UserSyncService Instance"""
        service = UserSyncService()
        service.config.enabled = True
        service.config.server_url = "https://keycloak.example.com/realms/test"
        return service

    def test_get_user_sync_service_singleton(self, sync_service):
        """Test get_user_sync_service Singleton Pattern"""
        instance1 = get_user_sync_service()
        instance2 = get_user_sync_service()
        assert instance1 is instance2

    def test_initialization(self, sync_service):
        """Test UserSyncService Initialization"""
        assert sync_service.config is not None

    @pytest.mark.asyncio
    async def test_extract_roles_empty(self, sync_service):
        """Test Extract Role from Empty UserInfo"""
        user_info = {}
        roles = sync_service._extract_roles(user_info)
        assert roles == []

    @pytest.mark.asyncio
    async def test_extract_roles_from_realm_access(self, sync_service):
        """Test Extract Role from realm_access"""
        user_info = {
            "realm_access": {
                "admin": True,
                "developer": False,
                "user": True,
            }
        }

        roles = sync_service._extract_roles(user_info)

        assert "admin" in roles
        assert "user" in roles
        assert "developer" not in roles

    @pytest.mark.asyncio
    async def test_extract_roles_from_resource_access(self, sync_service):
        """Test Extract Role from resource_access"""
        user_info = {
            "realm_access": {},
            "resource_access": {
                "workspace-api": {
                    "roles": ["workspace-read", "workspace-write"]
                }
            }
        }

        roles = sync_service._extract_roles(user_info)

        assert "workspace-read" in roles
        assert "workspace-write" in roles

    @pytest.mark.asyncio
    async def test_extract_roles_deduplication(self, sync_service):
        """Test Role Deduplication"""
        user_info = {
            "realm_access": {
                "admin": True,
                "user": True,
            },
            "resource_access": {
                "test-api": {
                    "roles": ["admin", "user"]
                }
            }
        }

        roles = sync_service._extract_roles(user_info)

        # Check deduplication
        assert roles.count("admin") == 1
        assert roles.count("user") == 1

    @pytest.mark.asyncio
    async def test_get_user_from_keycloak_requires_auth_enabled(self, sync_service):
        sync_service.config.enabled = False

        with pytest.raises(UserSyncError, match="Authentication is not enabled"):
            await sync_service.get_user_from_keycloak("token", "user-1")

    @pytest.mark.asyncio
    async def test_get_user_from_keycloak_success(self, sync_service, httpx_response_factory):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(
                return_value=httpx_response_factory(
                    json_data={"sub": "user-1", "preferred_username": "tester"}
                )
            )
            mock_client_class.return_value = mock_client

            user_info = await sync_service.get_user_from_keycloak("access-token", "user-1")

        assert user_info["sub"] == "user-1"
        _, kwargs = mock_client.get.await_args
        assert kwargs["headers"]["Authorization"] == "Bearer access-token"

    @pytest.mark.asyncio
    async def test_get_user_from_keycloak_wraps_http_error(self, sync_service):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.get = AsyncMock(side_effect=__import__("httpx").HTTPError("boom"))
            mock_client_class.return_value = mock_client

            with pytest.raises(UserSyncError, match="Failed to fetch user from Keycloak"):
                await sync_service.get_user_from_keycloak("access-token", "user-1")

    @pytest.mark.asyncio
    async def test_get_user_by_keycloak_id_returns_mapped_user(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=Mock(
            id="local-1",
            keycloak_id="kc-1",
            username="tester",
            email="tester@example.com",
            display_name="Test User",
            avatar_url="https://example.com/avatar.png",
            roles=["admin"],
        )))

        fake_select = Mock()
        fake_select.where.return_value = "query"
        fake_user_model = Mock(keycloak_id=Mock())

        with patch("sqlalchemy.select", return_value=fake_select), \
             patch("app.models.user.User", fake_user_model):
            user = await sync_service.get_user_by_keycloak_id(db, "kc-1")

        assert user["id"] == "local-1"
        db.execute.assert_awaited_once_with("query")

    @pytest.mark.asyncio
    async def test_get_user_by_keycloak_id_wraps_database_error(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        db.execute.side_effect = RuntimeError("db failure")
        fake_select = Mock()
        fake_select.where.return_value = "query"
        fake_user_model = Mock(keycloak_id=Mock())

        with patch("sqlalchemy.select", return_value=fake_select), \
             patch("app.models.user.User", fake_user_model):
            with pytest.raises(UserSyncError, match="Database error"):
                await sync_service.get_user_by_keycloak_id(db, "kc-1")

    @pytest.mark.asyncio
    async def test_create_user_in_db_uses_name_fallbacks(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        created_users = []

        class FakeUser:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                self.id = "local-created"

        def capture_add(user):
            created_users.append(user)

        db.add = Mock(side_effect=capture_add)

        with patch("app.models.user.User", FakeUser):
            result = await sync_service.create_user_in_db(
                db,
                {
                    "sub": "kc-1",
                    "preferred_username": "tester",
                    "email": "tester@example.com",
                    "given_name": "Test",
                    "family_name": "User",
                    "realm_access": {"admin": True},
                },
            )

        assert result["id"] == "local-created"
        assert created_users[0].display_name == "Test User"
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(created_users[0])

    @pytest.mark.asyncio
    async def test_create_user_in_db_rolls_back_on_error(self, sync_service):
        db = AsyncMock(spec=AsyncSession)

        class FakeUser:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        db.add.side_effect = RuntimeError("insert failed")

        with patch("app.models.user.User", FakeUser):
            with pytest.raises(UserSyncError, match="Failed to create user in database"):
                await sync_service.create_user_in_db(db, {"sub": "kc-1"})

        db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_user_in_db_updates_fields(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        user = Mock(
            id="local-1",
            keycloak_id="kc-1",
            username="old-user",
            email="old@example.com",
            first_name="Old",
            last_name="User",
            display_name="Old User",
            avatar_url=None,
            roles=["user"],
        )
        db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=user))

        fake_select = Mock()
        fake_select.where.return_value = "query"
        fake_user_model = Mock(keycloak_id=Mock())

        with patch("sqlalchemy.select", return_value=fake_select), \
             patch("app.models.user.User", fake_user_model):
            result = await sync_service.update_user_in_db(
                db,
                {
                    "sub": "kc-1",
                    "preferred_username": "new-user",
                    "email": "new@example.com",
                    "given_name": "New",
                    "family_name": "Name",
                    "picture": "https://example.com/avatar.png",
                    "realm_access": {"admin": True},
                },
            )

        assert result["username"] == "new-user"
        assert user.display_name == "New Name"
        assert user.avatar_url == "https://example.com/avatar.png"
        assert user.roles == ["admin"]
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once_with(user)

    @pytest.mark.asyncio
    async def test_update_user_in_db_raises_not_found(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=None))
        fake_select = Mock()
        fake_select.where.return_value = "query"
        fake_user_model = Mock(keycloak_id=Mock())

        with patch("sqlalchemy.select", return_value=fake_select), \
             patch("app.models.user.User", fake_user_model):
            with pytest.raises(UserNotFoundError, match="User not found"):
                await sync_service.update_user_in_db(db, {"sub": "kc-1"})

    @pytest.mark.asyncio
    async def test_update_user_in_db_rolls_back_on_database_error(self, sync_service):
        db = AsyncMock(spec=AsyncSession)
        db.execute.side_effect = RuntimeError("update failed")
        fake_select = Mock()
        fake_select.where.return_value = "query"
        fake_user_model = Mock(keycloak_id=Mock())

        with patch("sqlalchemy.select", return_value=fake_select), \
             patch("app.models.user.User", fake_user_model):
            with pytest.raises(UserSyncError, match="Failed to update user in database"):
                await sync_service.update_user_in_db(db, {"sub": "kc-1"})

        db.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_or_create_user_updates_existing_user(self, sync_service):
        db = AsyncMock(spec=AsyncSession)

        with patch.object(sync_service, "get_user_from_keycloak", new=AsyncMock(return_value={"sub": "kc-1"})), \
             patch.object(sync_service, "get_user_by_keycloak_id", new=AsyncMock(return_value={"id": "local-1"})), \
             patch.object(sync_service, "update_user_in_db", new=AsyncMock(return_value={"id": "local-1", "roles": ["admin"]})) as mock_update:
            result = await sync_service.sync_or_create_user(db, "token", "kc-1")

        assert result["id"] == "local-1"
        mock_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_or_create_user_creates_missing_user(self, sync_service):
        db = AsyncMock(spec=AsyncSession)

        with patch.object(sync_service, "get_user_from_keycloak", new=AsyncMock(return_value={"sub": "kc-1"})), \
             patch.object(sync_service, "get_user_by_keycloak_id", new=AsyncMock(return_value=None)), \
             patch.object(sync_service, "create_user_in_db", new=AsyncMock(return_value={"id": "local-created"})) as mock_create:
            result = await sync_service.sync_or_create_user(db, "token", "kc-1")

        assert result["id"] == "local-created"
        mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_user_roles_and_sync_user_roles(self, sync_service):
        db = AsyncMock(spec=AsyncSession)

        with patch.object(sync_service, "get_user_by_keycloak_id", new=AsyncMock(return_value={"roles": ["admin"]})):
            assert await sync_service.get_user_roles(db, "kc-1") == ["admin"]

        with patch.object(sync_service, "get_user_by_keycloak_id", new=AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundError):
                await sync_service.get_user_roles(db, "kc-1")

        with patch.object(sync_service, "get_user_from_keycloak", new=AsyncMock(return_value={"sub": "kc-1"})), \
             patch.object(sync_service, "update_user_in_db", new=AsyncMock(return_value={"roles": ["editor"]})) as mock_update:
            roles = await sync_service.sync_user_roles(db, "kc-1", "token")

        assert roles == ["editor"]
        mock_update.assert_awaited_once()


class TestRoleMapping:
    """Role Mapping Tests"""

    def test_load_role_mapping(self):
        """Test Load Role Mapping Configuration"""
        role_mapping = get_user_permissions([])

        # If configuration file doesn't exist, should return empty list
        assert isinstance(role_mapping, list)

    def test_get_user_permissions_with_roles(self):
        """Test Get Permission by Role"""
        roles = ["admin", "user"]
        permissions = get_user_permissions(roles)

        # admin role should have many permissions
        assert isinstance(permissions, list)
        assert len(permissions) > 0

    def test_get_user_permissions_empty(self):
        """Test Permissions When No Role"""
        permissions = get_user_permissions([])

        # When no role, should return default role permissions
        assert isinstance(permissions, list)


class TestPermissionChecks:
    """Permission Check Tests"""

    def test_has_permission_true(self):
        """Test Has Permission"""
        user_permissions = ["workspace:read", "workspace:create"]
        assert has_permission("workspace:read", user_permissions) is True

    def test_has_permission_resource_wildcard(self):
        """Test Resource Wildcard Permission"""
        user_permissions = ["workspace:all"]
        assert has_permission("workspace:create", user_permissions) is True

    def test_has_permission_global_wildcard(self):
        """Test Global Wildcard Permission"""
        user_permissions = ["*:all"]
        assert has_permission("marketplace:manage_registry", user_permissions) is True

    def test_has_permission_false(self):
        """Test Does Not Have Permission"""
        user_permissions = ["workspace:read"]
        assert has_permission("workspace:create", user_permissions) is False

    def test_has_role_true(self):
        """Test Has Role"""
        user_roles = ["admin", "user"]
        assert has_role("admin", user_roles) is True

    def test_has_role_false(self):
        """Test Does Not Have Role"""
        user_roles = ["user"]
        assert has_role("admin", user_roles) is False

    def test_has_any_role_true(self):
        """Test Has Any Role (Passed)"""
        user_roles = ["user"]
        assert has_any_role(["admin", "user"], user_roles) is True

    def test_has_any_role_false(self):
        """Test Has Any Role (Failed)"""
        user_roles = ["viewer"]
        assert has_any_role(["admin", "developer"], user_roles) is False

    def test_has_all_permissions_true(self):
        """Test Has All Permissions (Passed)"""
        user_permissions = ["workspace:read", "workspace:create", "workspace:delete"]
        assert has_all_permissions(["workspace:read", "workspace:create"], user_permissions) is True

    def test_has_all_permissions_false(self):
        """Test Has All Permissions (Failed)"""
        user_permissions = ["workspace:read"]
        assert has_all_permissions(["workspace:read", "workspace:create"], user_permissions) is False

    def test_has_any_permission_true(self):
        """Test Has Any Permission (Passed)"""
        user_permissions = ["workspace:read"]
        assert has_any_permission(["workspace:create", "workspace:read"], user_permissions) is True

    def test_has_any_permission_false(self):
        """Test Has Any Permission (Failed)"""
        user_permissions = ["workspace:delete"]
        assert has_any_permission(["workspace:create", "workspace:read"], user_permissions) is False


class TestAuthDecorators:
    """Authentication Decorator Tests"""

    def test_require_role_decorator(self):
        """Test require_role Decorator"""
        from app.modules.auth.auth_decorators import require_role

        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # Test user with permission
        user_with_role = {"sub": "user-123", "roles": ["admin"]}

        import asyncio

        # Simulate call
        try:
            result = asyncio.run(
                admin_endpoint(current_user=user_with_role)
            )
            assert result["message"] == "Admin access"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_require_role_decorator_no_role(self):
        """Test require_role Decorator (No Role)"""
        from app.modules.auth.auth_decorators import require_role

        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # Test user without permission
        user_without_role = {"sub": "user-123", "roles": ["user"]}

        import asyncio

        # Should throw PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            asyncio.run(
                admin_endpoint(current_user=user_without_role)
            )

    def test_require_permission_decorator(self):
        """Test require_permission Decorator"""
        from app.modules.auth.auth_decorators import require_permission

        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # Simulate user with permission
        # admin role should have workspace:create permission
        user_with_permission = {
            "sub": "user-123",
            "roles": ["admin"]
        }

        import asyncio

        try:
            result = asyncio.run(
                create_workspace_endpoint(current_user=user_with_permission)
            )
            assert result["message"] == "Workspace created"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_require_permission_decorator_no_permission(self):
        """Test require_permission Decorator (No Permission)"""
        from app.modules.auth.auth_decorators import require_permission

        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # Simulate user without permission
        user_without_permission = {
            "sub": "user-123",
            "roles": ["viewer"]
        }

        import asyncio

        # Should throw PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            asyncio.run(
                create_workspace_endpoint(current_user=user_without_permission)
            )

    def test_require_any_role_decorator(self):
        """Test require_any_role Decorator"""
        from app.modules.auth.auth_decorators import require_any_role

        @require_any_role("admin", "developer")
        async def moderator_endpoint(current_user):
            return {"message": "Moderator access"}

        # Test user with one of the roles
        user_with_one_role = {"sub": "user-123", "roles": ["developer"]}

        import asyncio

        try:
            result = asyncio.run(
                moderator_endpoint(current_user=user_with_one_role)
            )
            assert result["message"] == "Moderator access"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_require_any_permission_decorator(self):
        """Test require_any_permission Decorator"""
        from app.modules.auth.auth_decorators import require_any_permission

        @require_any_permission("workspace:read", "workspace:create")
        async def workspace_access_endpoint(current_user):
            return {"message": "Workspace access"}

        # Test user with one of the permissions
        user_with_one_permission = {
            "sub": "user-123",
            "roles": ["user"]  # user role has workspace:read
        }

        import asyncio

        try:
            result = asyncio.run(
                workspace_access_endpoint(current_user=user_with_one_permission)
            )
            assert result["message"] == "Workspace access"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_require_all_permissions_decorator(self):
        """Test require_all_permissions Decorator"""
        from app.modules.auth.auth_decorators import require_all_permissions

        @require_all_permissions("workspace:read", "workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # Test user with all permissions
        user_with_all_permissions = {
            "sub": "user-123",
            "roles": ["admin"]
        }

        import asyncio

        try:
            result = asyncio.run(
                create_workspace_endpoint(current_user=user_with_all_permissions)
            )
            assert result["message"] == "Workspace created"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")


class TestUserSyncIntegration:
    """UserSync Integration Tests"""

    @pytest.mark.asyncio
    async def test_sync_disabled_auth(self):
        """Test Sync When Authentication Not Enabled"""
        sync_service = UserSyncService()

        with patch("app.modules.auth.user_sync.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            sync_service.config = mock_config.return_value

            with pytest.raises(UserSyncError, match="Authentication is not enabled"):
                await sync_service.get_user_from_keycloak("test-token", "user-123")
