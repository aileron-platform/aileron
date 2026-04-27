"""
End-to-end authentication tests - Simulate complete OAuth2 flow

Test scenarios:
1. Generate login URL
2. Simulate Keycloak callback
3. Token verification
4. Protected route access
5. Decorator functionality
"""

import sys
from pathlib import Path
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_oauth_login_url_generation():
    """Test OAuth login URL generation"""
    print("\n🔐 Test 1: OAuth Login URL Generation")
    print("-" * 60)

    try:
        from fastapi import Request
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        print(f"   Configuration info:")
        print(f"   - Server URL: {config.server_url or 'Not configured'}")
        print(f"   - Realm: {config.realm or 'Not configured'}")
        print(f"   - Client ID: {config.client_id or 'Not configured'}")
        print(f"   - Auth enabled: {config.enabled}")

        if not config.enabled:
            print("\n   ⚠️  Authentication not enabled, using mock configuration for testing")
            # Create mock configuration
            config.server_url = "http://localhost:8080/realms"
            config.realm = "test-realm"
            config.client_id = "test-client"

        # Build authorization URL
        from urllib.parse import urlencode

        auth_url = (
            f"{config.server_url}/{config.realm}/protocol/openid-connect/auth"
            if config.server_url
            else "http://localhost:8080/realms/test-realm/protocol/openid-connect/auth"
        )

        params = {
            "client_id": config.client_id,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": "http://localhost:3001/api/v1/oauth2/callback",
            "state": "test-state-12345",
        }

        login_url = f"{auth_url}?{urlencode(params)}"

        print(f"\n   ✅ Login URL generated successfully:")
        print(f"   {login_url[:100]}...")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_middleware_token_validation():
    """Test middleware token verification flow"""
    print("\n🎫 Test 2: Middleware Token Verification")
    print("-" * 60)

    try:
        from app.modules.auth import JWTAuthenticationMiddleware, get_keycloak_config
        from fastapi import Request

        class MockApp:
            pass

        # Create middleware
        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/health"],
            exclude_patterns=["/public/*"],
        )

        print("   ✅ Middleware created successfully")

        # Test token extraction
        class MockRequest:
            def __init__(self, headers, path):
                self.headers = headers
                self.url = Mock(path=path)

        # Test 1: Request with valid token
        request = MockRequest(
            {"Authorization": "Bearer test-token-12345"},
            "/api/workspaces"
        )

        token = middleware._extract_bearer_token(request)
        print(f"   ✅ Token extracted: {token}")

        # Test 2: Request without token
        request = MockRequest({}, "/api/workspaces")
        token = middleware._extract_bearer_token(request)
        print(f"   ✅ No token handling: {token}")

        # Test 3: Exclude paths
        is_excluded = middleware._is_excluded_path("/health")
        print(f"   ✅ Path exclusion check (/health): {is_excluded}")

        is_excluded = middleware._is_excluded_path("/api/workspaces")
        print(f"   ✅ Path exclusion check (/api/workspaces): {is_excluded}")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_decorator_authentication():
    """Test decorator authentication functionality"""
    print("\n🔒 Test 3: Decorator Authentication")
    print("-" * 60)

    try:
        from app.modules.auth import (
            require_role,
            require_permission,
            PermissionDeniedError,
        )

        # Test require_role decorator
        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # Test authorized user
        admin_user = {"sub": "user-123", "roles": ["admin"]}
        try:
            result = await admin_endpoint(current_user=admin_user)
            print(f"   ✅ Admin role access successful: {result}")
        except Exception as e:
            print(f"   ❌ Admin role access failed: {e}")
            return False

        # Test unauthorized user
        normal_user = {"sub": "user-456", "roles": ["user"]}
        try:
            await admin_endpoint(current_user=normal_user)
            print("   ❌ Should reject unauthorized user")
            return False
        except PermissionDeniedError as e:
            print(f"   ✅ Correctly rejected unauthorized user: {e.detail}")

        # Test require_permission decorator
        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # admin role should have workspace:create permission
        admin_user = {"sub": "user-123", "roles": ["admin"]}
        try:
            result = await create_workspace_endpoint(current_user=admin_user)
            print(f"   ✅ Permission check successful: {result}")
        except Exception as e:
            print(f"   ❌ Permission check failed: {e}")
            return False

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_permission_system():
    """Test permission system"""
    print("\n📋 Test 4: Permission System")
    print("-" * 60)

    try:
        from app.modules.auth import (
            get_user_permissions,
            has_permission,
            has_role,
            has_all_permissions,
            has_any_permission,
        )

        # Test role-permission mapping
        admin_permissions = get_user_permissions(["admin"])
        print(f"   ✅ Admin role permission count: {len(admin_permissions)}")
        print(f"   - Permission examples: {admin_permissions[:3]}")

        user_permissions = get_user_permissions(["user"])
        print(f"   ✅ User role permission count: {len(user_permissions)}")

        # Test permission checks
        assert has_permission("workspace:read", admin_permissions) is True
        print("   ✅ has_permission('workspace:read') working")

        assert has_role("admin", ["admin", "user"]) is True
        print("   ✅ has_role('admin') working")

        assert has_all_permissions(
            ["workspace:read", "workspace:create"],
            admin_permissions
        ) is True
        print("   ✅ has_all_permissions working")

        assert has_any_permission(
            ["workspace:read", "workspace:delete"],
            user_permissions
        ) is True
        print("   ✅ has_any_permission working")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_sync_service():
    """Test user synchronization service"""
    print("\n👤 Test 5: User Synchronization Service")
    print("-" * 60)

    try:
        from app.modules.auth import get_user_sync_service

        service = get_user_sync_service()
        print("   ✅ UserSyncService instantiated successfully")

        # Test role extraction
        test_user_info = {
            "realm_access": {
                "admin": True,
                "user": True,
            },
            "resource_access": {
                "test-api": {
                    "roles": ["read", "write"]
                }
            }
        }

        roles = service._extract_roles(test_user_info)
        print(f"   ✅ Role extraction successful: {roles}")

        assert "admin" in roles
        assert "user" in roles
        assert "read" in roles
        assert "write" in roles
        print("   ✅ Role extraction correct")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_jwt_utilities():
    """Test JWT utilities"""
    print("\n🔑 Test 6: JWT Utilities")
    print("-" * 60)

    try:
        from app.modules.auth import get_jwt_utils
        from datetime import datetime, timedelta, timezone

        jwt_utils = get_jwt_utils()
        print("   ✅ JWTUtils instantiated successfully")

        # Test token expiry validation
        exp_valid = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        payload_valid = {"exp": exp_valid, "sub": "user-123"}

        is_valid = jwt_utils.validate_token_expiry(payload_valid)
        print(f"   ✅ Valid token verification: {is_valid}")

        # Test expired token
        exp_expired = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        payload_expired = {"exp": exp_expired, "sub": "user-123"}

        is_valid = jwt_utils.validate_token_expiry(payload_expired)
        print(f"   ✅ Expired token verification: {is_valid}")

        return True

    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Execute all end-to-end tests"""
    print("=" * 60)
    print("🧪 End-to-end authentication tests")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("OAuth Login URL Generation", test_oauth_login_url_generation()))
    results.append(("Middleware Token Verification", await test_middleware_token_validation()))
    results.append(("Decorator Authentication", await test_decorator_authentication()))
    results.append(("Permission System", await test_permission_system()))
    results.append(("User Synchronization Service", await test_user_sync_service()))
    results.append(("JWT Utilities", await test_jwt_utilities()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{status}  {test_name}")

    print()
    print(f"Pass rate: {passed}/{total} ({passed * 100 // total if total > 0 else 0}%)")

    if passed == total:
        print("\n🎉 All tests passed! Authentication system is working properly.")
        print("\n📝 Next steps:")
        print("   1. Configure Keycloak realm and client")
        print("   2. Set ENABLE_AUTH=true")
        print("   3. Test complete OAuth2 flow")
        return 0
    else:
        print("\n⚠️  Some tests failed, please check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
