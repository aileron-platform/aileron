"""
用戶同步服務的單元測試
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
    """UserSyncService 類的單元測試"""

    @pytest.fixture
    def sync_service(self):
        """創建 UserSyncService 實例"""
        service = UserSyncService()
        service.config.enabled = True
        service.config.server_url = "https://keycloak.example.com/realms/test"
        return service

    def test_get_user_sync_service_singleton(self, sync_service):
        """測試 get_user_sync_service 單例模式"""
        instance1 = get_user_sync_service()
        instance2 = get_user_sync_service()
        assert instance1 is instance2

    def test_initialization(self, sync_service):
        """測試 UserSyncService 初始化"""
        assert sync_service.config is not None

    @pytest.mark.asyncio
    async def test_extract_roles_empty(self, sync_service):
        """測試從空用戶信息提取角色"""
        user_info = {}
        roles = sync_service._extract_roles(user_info)
        assert roles == []

    @pytest.mark.asyncio
    async def test_extract_roles_from_realm_access(self, sync_service):
        """測試從 realm_access 提取角色"""
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
        """測試從 resource_access 提取角色"""
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
        """測試角色去重"""
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

        # 檢查去重
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
    """角色映射測試"""

    def test_load_role_mapping(self):
        """測試載入角色映射配置"""
        role_mapping = get_user_permissions([])

        # 如果配置文件不存在，應該返回空列表
        assert isinstance(role_mapping, list)

    def test_get_user_permissions_with_roles(self):
        """測試根據角色獲取權限"""
        roles = ["admin", "user"]
        permissions = get_user_permissions(roles)

        # admin 角色應該有大量權限
        assert isinstance(permissions, list)
        assert len(permissions) > 0

    def test_get_user_permissions_empty(self):
        """測試沒有角色時的權限"""
        permissions = get_user_permissions([])

        # 沒有角色時，應該返回默認角色權限
        assert isinstance(permissions, list)


class TestPermissionChecks:
    """權限檢查測試"""

    def test_has_permission_true(self):
        """測試擁有權限"""
        user_permissions = ["workspace:read", "workspace:create"]
        assert has_permission("workspace:read", user_permissions) is True

    def test_has_permission_false(self):
        """測試不擁有權限"""
        user_permissions = ["workspace:read"]
        assert has_permission("workspace:create", user_permissions) is False

    def test_has_role_true(self):
        """測試擁有角色"""
        user_roles = ["admin", "user"]
        assert has_role("admin", user_roles) is True

    def test_has_role_false(self):
        """測試不擁有角色"""
        user_roles = ["user"]
        assert has_role("admin", user_roles) is False

    def test_has_any_role_true(self):
        """測試擁有任一角色（通過）"""
        user_roles = ["user"]
        assert has_any_role(["admin", "user"], user_roles) is True

    def test_has_any_role_false(self):
        """測試擁有任一角色（失敗）"""
        user_roles = ["viewer"]
        assert has_any_role(["admin", "developer"], user_roles) is False

    def test_has_all_permissions_true(self):
        """測試擁有所有權限（通過）"""
        user_permissions = ["workspace:read", "workspace:create", "workspace:delete"]
        assert has_all_permissions(["workspace:read", "workspace:create"], user_permissions) is True

    def test_has_all_permissions_false(self):
        """測試擁有所有權限（失敗）"""
        user_permissions = ["workspace:read"]
        assert has_all_permissions(["workspace:read", "workspace:create"], user_permissions) is False

    def test_has_any_permission_true(self):
        """測試擁有任一權限（通過）"""
        user_permissions = ["workspace:read"]
        assert has_any_permission(["workspace:create", "workspace:read"], user_permissions) is True

    def test_has_any_permission_false(self):
        """測試擁有任一權限（失敗）"""
        user_permissions = ["workspace:delete"]
        assert has_any_permission(["workspace:create", "workspace:read"], user_permissions) is False


class TestAuthDecorators:
    """認證裝飾器測試"""

    def test_require_role_decorator(self):
        """測試 require_role 裝飾器"""
        from app.modules.auth.auth_decorators import require_role

        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # 測試有權限的用戶
        user_with_role = {"sub": "user-123", "roles": ["admin"]}

        import asyncio

        # 模擬調用
        try:
            result = asyncio.run(
                admin_endpoint(current_user=user_with_role)
            )
            assert result["message"] == "Admin access"
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    def test_require_role_decorator_no_role(self):
        """測試 require_role 裝飾器（沒有角色）"""
        from app.modules.auth.auth_decorators import require_role

        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # 測試沒有權限的用戶
        user_without_role = {"sub": "user-123", "roles": ["user"]}

        import asyncio

        # 應該拋出 PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            asyncio.run(
                admin_endpoint(current_user=user_without_role)
            )

    def test_require_permission_decorator(self):
        """測試 require_permission 裝飾器"""
        from app.modules.auth.auth_decorators import require_permission

        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # 模擬有權限的用戶
        # admin 角色應該有 workspace:create 權限
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
        """測試 require_permission 裝飾器（沒有權限）"""
        from app.modules.auth.auth_decorators import require_permission

        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # 模擬沒有權限的用戶
        user_without_permission = {
            "sub": "user-123",
            "roles": ["viewer"]
        }

        import asyncio

        # 應該拋出 PermissionDeniedError
        with pytest.raises(PermissionDeniedError):
            asyncio.run(
                create_workspace_endpoint(current_user=user_without_permission)
            )

    def test_require_any_role_decorator(self):
        """測試 require_any_role 裝飾器"""
        from app.modules.auth.auth_decorators import require_any_role

        @require_any_role("admin", "developer")
        async def moderator_endpoint(current_user):
            return {"message": "Moderator access"}

        # 測試有其中一個角色的用戶
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
        """測試 require_any_permission 裝飾器"""
        from app.modules.auth.auth_decorators import require_any_permission

        @require_any_permission("workspace:read", "workspace:create")
        async def workspace_access_endpoint(current_user):
            return {"message": "Workspace access"}

        # 測試有其中一個權限的用戶
        user_with_one_permission = {
            "sub": "user-123",
            "roles": ["user"]  # user 角色有 workspace:read
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
        """測試 require_all_permissions 裝飾器"""
        from app.modules.auth.auth_decorators import require_all_permissions

        @require_all_permissions("workspace:read", "workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # 測試有所有權限的用戶
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
    """用戶同步集成測試"""

    @pytest.mark.asyncio
    async def test_sync_disabled_auth(self):
        """測試認證未啟用時的同步"""
        sync_service = UserSyncService()

        with patch("app.modules.auth.user_sync.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            sync_service.config = mock_config.return_value

            with pytest.raises(UserSyncError, match="Authentication is not enabled"):
                await sync_service.get_user_from_keycloak("test-token", "user-123")
