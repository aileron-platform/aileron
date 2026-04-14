"""
Keycloak Auth 模組完整測試套件

運行所有單元測試和集成測試，包括異步測試。
"""

import sys
import asyncio
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# 同步測試
# ============================================================================

def test_config_module():
    """測試配置模組"""
    from app.modules.auth.config import KeycloakConfig, get_keycloak_config

    print("📋 測試配置模組...")
    config = get_keycloak_config()
    assert config is not None
    assert isinstance(config, KeycloakConfig)
    print(f"   ✅ 配置載入成功 (enabled={config.enabled})")
    return True


def test_jwt_utils_singleton():
    """測試 JWT utils 單例模式"""
    from app.modules.auth.jwt_utils import get_jwt_utils, clear_jwt_utils_cache

    print("🔐 測試 JWT Utils 單例模式...")
    utils1 = get_jwt_utils()
    utils2 = get_jwt_utils()
    assert utils1 is utils2
    print("   ✅ JWT Utils 單例模式正常")

    clear_jwt_utils_cache()
    print("   ✅ 清除快取成功")
    return True


def test_jwks_cache_singleton():
    """測試 JWKS cache 單例模式"""
    from app.modules.auth.jwks_cache import get_jwks_cache, clear_jwks_cache

    print("🔑 測試 JWKS Cache 單例模式...")
    cache1 = get_jwks_cache()
    cache2 = get_jwks_cache()
    assert cache1 is cache2
    print("   ✅ JWKS Cache 單例模式正常")

    clear_jwks_cache()
    print("   ✅ 清除快取成功")
    return True


def test_user_sync_service_singleton():
    """測試用戶同步服務單例模式"""
    from app.modules.auth.user_sync import get_user_sync_service

    print("👤 測試 UserSyncService 單例模式...")
    service1 = get_user_sync_service()
    service2 = get_user_sync_service()
    assert service1 is service2
    print("   ✅ UserSyncService 單例模式正常")
    return True


def test_role_mapping():
    """測試角色映射"""
    from app.modules.auth.auth_decorators import get_user_permissions, load_role_mapping

    print("🔑 測試角色映射...")
    role_mapping = load_role_mapping()
    assert isinstance(role_mapping, dict)
    print(f"   ✅ 角色映射載入成功 ({len(role_mapping)} 個鍵)")

    # 測試 admin 角色權限
    admin_permissions = get_user_permissions(['admin'])
    assert isinstance(admin_permissions, list)
    assert len(admin_permissions) > 0
    print(f"   ✅ Admin 角色擁有 {len(admin_permissions)} 個權限")
    return True


def test_permission_checkers():
    """測試權限檢查函數"""
    from app.modules.auth.auth_decorators import (
        has_permission,
        has_role,
        has_any_role,
        has_all_permissions,
        has_any_permission,
    )

    print("✅ 測試權限檢查函數...")

    # has_permission
    assert has_permission("workspace:read", ["workspace:read", "workspace:create"]) is True
    assert has_permission("workspace:delete", ["workspace:read"]) is False
    print("   ✅ has_permission 正常")

    # has_role
    assert has_role("admin", ["admin", "user"]) is True
    assert has_role("admin", ["user"]) is False
    print("   ✅ has_role 正常")

    # has_any_role
    assert has_any_role(["admin", "developer"], ["user", "admin"]) is True
    assert has_any_role(["admin", "developer"], ["viewer"]) is False
    print("   ✅ has_any_role 正常")

    # has_all_permissions
    assert has_all_permissions(
        ["workspace:read", "workspace:create"],
        ["workspace:read", "workspace:create", "workspace:delete"]
    ) is True
    assert has_all_permissions(
        ["workspace:read", "workspace:create"],
        ["workspace:read"]
    ) is False
    print("   ✅ has_all_permissions 正常")

    # has_any_permission
    assert has_any_permission(
        ["workspace:create", "workspace:delete"],
        ["workspace:read", "workspace:create"]
    ) is True
    assert has_any_permission(
        ["workspace:create", "workspace:delete"],
        ["workspace:read"]
    ) is False
    print("   ✅ has_any_permission 正常")

    return True


def test_auth_router_endpoints():
    """測試認證路由端點"""
    from app.modules.auth import auth_router

    print("🛣️  測試認證路由端點...")
    routes = auth_router.routes

    expected_endpoints = [
        '/oauth2/login',
        '/oauth2/login/redirect',
        '/oauth2/callback',
        '/oauth2/refresh',
        '/oauth2/logout',
        '/oauth2/me',
        '/oauth2/config',
    ]

    route_paths = [route.path for route in routes if hasattr(route, 'path')]

    for endpoint in expected_endpoints:
        assert endpoint in route_paths, f"端點 {endpoint} 未找到"

    print(f"   ✅ 所有 {len(expected_endpoints)} 個端點已定義")
    return True


def test_module_exports():
    """測試模組導出"""
    from app.modules import auth

    print("📤 測試模組導出...")
    assert hasattr(auth, '__all__')
    exports = auth.__all__

    required_exports = [
        'KeycloakConfig',
        'get_keycloak_config',
        'JWTUtils',
        'JWTValidationError',
        'get_jwt_utils',
        'JKWSCache',
        'get_jwks_cache',
        'auth_router',
        'UserSyncService',
        'get_user_sync_service',
        'PermissionDeniedError',
        'get_user_permissions',
        'require_role',
        'require_permission',
        'get_current_user',
    ]

    for export in required_exports:
        assert export in exports, f"導出 {export} 未找到"

    print(f"   ✅ 所有必要符號已導出 ({len(exports)} 個)")
    return True


# ============================================================================
# 異步測試
# ============================================================================

async def test_jwks_cache_initialization():
    """測試 JWKS 快取初始化"""
    from app.modules.auth.jwks_cache import get_jwks_cache

    print("🔑 測試 JWKS 快取初始化...")
    cache = get_jwks_cache()

    # 測試快取狀態
    stats = cache.get_stats()
    assert stats is not None
    assert 'is_cached' in stats
    print(f"   ✅ JWKS 快取初始化成功 (快取狀態: {stats['is_cached']})")
    return True


async def test_user_sync_role_extraction():
    """測試用戶同步角色提取"""
    from app.modules.auth.user_sync import get_user_sync_service

    print("👤 測試用戶同步角色提取...")
    service = get_user_sync_service()

    # 測試空用戶信息
    roles_empty = service._extract_roles({})
    assert roles_empty == []
    print("   ✅ 空用戶信息處理正常")

    # 測試 realm_access
    user_info = {
        "realm_access": {
            "admin": True,
            "user": True,
        }
    }
    roles = service._extract_roles(user_info)
    assert "admin" in roles
    assert "user" in roles
    print("   ✅ realm_access 角色提取正常")

    # 測試 resource_access
    user_info = {
        "realm_access": {},
        "resource_access": {
            "test-api": {
                "roles": ["read", "write"]
            }
        }
    }
    roles = service._extract_roles(user_info)
    assert "read" in roles
    assert "write" in roles
    print("   ✅ resource_access 角色提取正常")

    return True


async def test_decorator_functionality():
    """測試裝飾器功能"""
    from app.modules.auth.auth_decorators import require_role, require_permission

    print("🔒 測試裝飾器功能...")

    # 測試 require_role 裝飾器
    @require_role("admin")
    async def admin_only_endpoint(current_user):
        return {"message": "Admin access"}

    # 有權限的用戶
    admin_user = {"sub": "user-123", "roles": ["admin"]}
    try:
        result = await admin_only_endpoint(current_user=admin_user)
        assert result["message"] == "Admin access"
        print("   ✅ require_role 裝飾器（有權限）正常")
    except Exception as e:
        print(f"   ❌ require_role 裝飾器錯誤: {e}")
        return False

    # 無權限的用戶
    from app.modules.auth.auth_decorators import PermissionDeniedError

    normal_user = {"sub": "user-456", "roles": ["user"]}
    try:
        await admin_only_endpoint(current_user=normal_user)
        print("   ❌ require_role 裝飾器未拒絕無權限用戶")
        return False
    except PermissionDeniedError:
        print("   ✅ require_role 裝飾器（無權限）正常")

    # 測試 require_permission 裝飾器
    @require_permission("workspace:create")
    async def create_workspace_endpoint(current_user):
        return {"message": "Workspace created"}

    # admin 角色應該有 workspace:create 權限
    admin_user = {"sub": "user-123", "roles": ["admin"]}
    try:
        result = await create_workspace_endpoint(current_user=admin_user)
        assert result["message"] == "Workspace created"
        print("   ✅ require_permission 裝飾器正常")
    except Exception as e:
        print(f"   ❌ require_permission 裝飾器錯誤: {e}")
        return False

    return True


# ============================================================================
# 主測試運行器
# ============================================================================

def run_sync_tests():
    """運行所有同步測試"""
    print("\n" + "=" * 60)
    print("🔍 同步測試")
    print("=" * 60 + "\n")

    tests = [
        ("配置模組", test_config_module),
        ("JWT Utils 單例", test_jwt_utils_singleton),
        ("JWKS Cache 單例", test_jwks_cache_singleton),
        ("UserSyncService 單例", test_user_sync_service_singleton),
        ("角色映射", test_role_mapping),
        ("權限檢查函數", test_permission_checkers),
        ("認證路由端點", test_auth_router_endpoints),
        ("模組導出", test_module_exports),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"   ❌ 錯誤: {e}")

    return results


async def run_async_tests():
    """運行所有異步測試"""
    print("\n" + "=" * 60)
    print("⚡ 異步測試")
    print("=" * 60 + "\n")

    tests = [
        ("JWKS 快取初始化", test_jwks_cache_initialization),
        ("用戶同步角色提取", test_user_sync_role_extraction),
        ("裝飾器功能", test_decorator_functionality),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"   ❌ 錯誤: {e}")

    return results


def main():
    """主測試運行器"""
    print("=" * 60)
    print("🧪 Keycloak Auth 模組完整測試套件")
    print("=" * 60)

    all_results = []

    # 運行同步測試
    sync_results = run_sync_tests()
    all_results.extend(sync_results)

    # 運行異步測試
    async_results = asyncio.run(run_async_tests())
    all_results.extend(async_results)

    # 總結
    print("\n" + "=" * 60)
    print("📊 測試總結")
    print("=" * 60)

    passed = sum(1 for _, result, _ in all_results if result)
    total = len(all_results)

    for name, result, error in all_results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}  {name}")
        if error:
            print(f"      錯誤: {error}")

    print()
    print(f"通過率: {passed}/{total} ({passed * 100 // total if total > 0 else 0}%)")

    if passed == total:
        print("\n🎉 所有測試通過！Keycloak auth 模組運作正常。")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤訊息。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
