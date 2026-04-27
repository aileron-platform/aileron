"""
Keycloak Auth Module Complete Test Suite

Run all unit tests and integration tests, including async tests.
"""

import sys
import asyncio
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ============================================================================
# Synchronous Tests
# ============================================================================

def test_config_module():
    """Test configuration module"""
    from app.modules.auth.config import KeycloakConfig, get_keycloak_config

    print("📋 Testing configuration module...")
    config = get_keycloak_config()
    assert config is not None
    assert isinstance(config, KeycloakConfig)
    print(f"   ✅ Configuration loaded successfully (enabled={config.enabled})")
    return True


def test_jwt_utils_singleton():
    """Test JWT utils singleton pattern"""
    from app.modules.auth.jwt_utils import get_jwt_utils, clear_jwt_utils_cache

    print("🔐 Testing JWT Utils Singleton Pattern...")
    utils1 = get_jwt_utils()
    utils2 = get_jwt_utils()
    assert utils1 is utils2
    print("   ✅ JWT Utils singleton pattern working")

    clear_jwt_utils_cache()
    print("   ✅ Cache cleared successfully")
    return True


def test_jwks_cache_singleton():
    """Test JWKS cache singleton pattern"""
    from app.modules.auth.jwks_cache import get_jwks_cache, clear_jwks_cache

    print("🔑 Testing JWKS Cache Singleton Pattern...")
    cache1 = get_jwks_cache()
    cache2 = get_jwks_cache()
    assert cache1 is cache2
    print("   ✅ JWKS Cache singleton pattern working")

    clear_jwks_cache()
    print("   ✅ Cache cleared successfully")
    return True


def test_user_sync_service_singleton():
    """Test user synchronization service singleton pattern"""
    from app.modules.auth.user_sync import get_user_sync_service

    print("👤 Testing UserSyncService Singleton Pattern...")
    service1 = get_user_sync_service()
    service2 = get_user_sync_service()
    assert service1 is service2
    print("   ✅ UserSyncService singleton pattern working")
    return True


def test_role_mapping():
    """Test role mapping"""
    from app.modules.auth.auth_decorators import get_user_permissions, load_role_mapping

    print("🔑 Testing role mapping...")
    role_mapping = load_role_mapping()
    assert isinstance(role_mapping, dict)
    print(f"   ✅ Role mapping loaded successfully ({len(role_mapping)} keys)")

    # Test admin role permissions
    admin_permissions = get_user_permissions(['admin'])
    assert isinstance(admin_permissions, list)
    assert len(admin_permissions) > 0
    print(f"   ✅ Admin role has {len(admin_permissions)} permissions")
    return True


def test_permission_checkers():
    """Test permission checking functions"""
    from app.modules.auth.auth_decorators import (
        has_permission,
        has_role,
        has_any_role,
        has_all_permissions,
        has_any_permission,
    )

    print("✅ Testing permission checking functions...")

    # has_permission
    assert has_permission("workspace:read", ["workspace:read", "workspace:create"]) is True
    assert has_permission("workspace:delete", ["workspace:read"]) is False
    print("   ✅ has_permission working")

    # has_role
    assert has_role("admin", ["admin", "user"]) is True
    assert has_role("admin", ["user"]) is False
    print("   ✅ has_role working")

    # has_any_role
    assert has_any_role(["admin", "developer"], ["user", "admin"]) is True
    assert has_any_role(["admin", "developer"], ["viewer"]) is False
    print("   ✅ has_any_role working")

    # has_all_permissions
    assert has_all_permissions(
        ["workspace:read", "workspace:create"],
        ["workspace:read", "workspace:create", "workspace:delete"]
    ) is True
    assert has_all_permissions(
        ["workspace:read", "workspace:create"],
        ["workspace:read"]
    ) is False
    print("   ✅ has_all_permissions working")

    # has_any_permission
    assert has_any_permission(
        ["workspace:create", "workspace:delete"],
        ["workspace:read", "workspace:create"]
    ) is True
    assert has_any_permission(
        ["workspace:create", "workspace:delete"],
        ["workspace:read"]
    ) is False
    print("   ✅ has_any_permission working")

    return True


def test_auth_router_endpoints():
    """testauthrouteendpoint"""
    from app.modules.auth import auth_router

    print("🛣️  testauthrouteendpoint...")
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
        assert endpoint in route_paths, f"endpoint {endpoint} not found"

    print(f"   ✅ All {len(expected_endpoints)} endpoints defined")
    return True


def test_module_exports():
    """testmoduleexport"""
    from app.modules import auth

    print("📤 testmoduleexport...")
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
        assert export in exports, f"export {export} not found"

    print(f"   ✅ Allnecessarysymbols exported ({len(exports)} )")
    return True


# ============================================================================
# asynctest
# ============================================================================

async def test_jwks_cache_initialization():
    """test JWKS cacheinitialization"""
    from app.modules.auth.jwks_cache import get_jwks_cache

    print("🔑 test JWKS cacheinitialization...")
    cache = get_jwks_cache()

    # testcachestate
    stats = cache.get_stats()
    assert stats is not None
    assert 'is_cached' in stats
    print(f"   ✅ JWKS cacheinitializationsuccessfully (cachestate: {stats['is_cached']})")
    return True


async def test_user_sync_role_extraction():
    """testusersyncroleextraction"""
    from app.modules.auth.user_sync import get_user_sync_service

    print("👤 testusersyncroleextraction...")
    service = get_user_sync_service()

    # Test empty user info
    roles_empty = service._extract_roles({})
    assert roles_empty == []
    print("   ✅ Empty user info processing working")

    # test realm_access
    user_info = {
        "realm_access": {
            "admin": True,
            "user": True,
        }
    }
    roles = service._extract_roles(user_info)
    assert "admin" in roles
    assert "user" in roles
    print("   ✅ realm_access roleextractionworking")

    # test resource_access
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
    print("   ✅ resource_access roleextractionworking")

    return True


async def test_decorator_functionality():
    """testdecoratorFunctionality"""
    from app.modules.auth.auth_decorators import require_role, require_permission

    print("🔒 testdecoratorFunctionality...")

    # test require_role decorator
    @require_role("admin")
    async def admin_only_endpoint(current_user):
        return {"message": "Admin access"}

    # Authorized user
    admin_user = {"sub": "user-123", "roles": ["admin"]}
    try:
        result = await admin_only_endpoint(current_user=admin_user)
        assert result["message"] == "Admin access"
        print("   ✅ require_role decorator (authorized) working")
    except Exception as e:
        print(f"   ❌ require_role decoratorerror: {e}")
        return False

    # Unauthorized user
    from app.modules.auth.auth_decorators import PermissionDeniedError

    normal_user = {"sub": "user-456", "roles": ["user"]}
    try:
        await admin_only_endpoint(current_user=normal_user)
        print("   ❌ require_role decorator did not reject unauthorized user")
        return False
    except PermissionDeniedError:
        print("   ✅ require_role decorator (unauthorized) working")

    # test require_permission decorator
    @require_permission("workspace:create")
    async def create_workspace_endpoint(current_user):
        return {"message": "Workspace created"}

    # Admin role should have workspace:create permission
    admin_user = {"sub": "user-123", "roles": ["admin"]}
    try:
        result = await create_workspace_endpoint(current_user=admin_user)
        assert result["message"] == "Workspace created"
        print("   ✅ require_permission decoratorworking")
    except Exception as e:
        print(f"   ❌ require_permission decoratorerror: {e}")
        return False

    return True


# ============================================================================
# maintestRunner
# ============================================================================

def run_sync_tests():
    """Run all sync tests"""
    print("\n" + "=" * 60)
    print("🔍 synctest")
    print("=" * 60 + "\n")

    tests = [
        ("Configurationmodule", test_config_module),
        ("JWT Utils Singleton", test_jwt_utils_singleton),
        ("JWKS Cache Singleton", test_jwks_cache_singleton),
        ("UserSyncService Singleton", test_user_sync_service_singleton),
        ("Role Mapping", test_role_mapping),
        ("Permission Checkers", test_permission_checkers),
        ("authrouteendpoint", test_auth_router_endpoints),
        ("moduleexport", test_module_exports),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"   ❌ error: {e}")

    return results


async def run_async_tests():
    """Run all async tests"""
    print("\n" + "=" * 60)
    print("⚡ asynctest")
    print("=" * 60 + "\n")

    tests = [
        ("JWKS cacheinitialization", test_jwks_cache_initialization),
        ("usersyncroleextraction", test_user_sync_role_extraction),
        ("decoratorFunctionality", test_decorator_functionality),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"   ❌ error: {e}")

    return results


def main():
    """maintestRunner"""
    print("=" * 60)
    print("🧪 Keycloak Auth Module Complete Test Suite")
    print("=" * 60)

    all_results = []

    # Run sync tests
    sync_results = run_sync_tests()
    all_results.extend(sync_results)

    # Run async tests
    async_results = asyncio.run(run_async_tests())
    all_results.extend(async_results)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result, _ in all_results if result)
    total = len(all_results)

    for name, result, error in all_results:
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{status}  {name}")
        if error:
            print(f"      error: {error}")

    print()
    print(f"Pass rate: {passed}/{total} ({passed * 100 / total if total > 0 else 0}%)")

    if passed == total:
        print("\n🎉 All tests passed! Keycloak auth module is working properly.")
        return 0
    else:
        print("\n⚠️  Some tests failed, please check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
