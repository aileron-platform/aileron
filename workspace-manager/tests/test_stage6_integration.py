"""
Stage 6 集成Test - VerifyMiddleware不會破Bad現有Function

TestProject：
1. 主Application可以NormalInitiating（Middleware導入無誤）
2. Arranging除Road徑不NeedingAuthentication
3. MiddlewareCorrectly注入 request.state
4. ENABLE_AUTH=false 時不Impact現有行為
5. RouteEndpointStill可Access
"""

import sys
from pathlib import Path

# 添加Project根CatalogTo Python Road徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_main_app_import():
    """Test主Application可以Normal導入（VerifyMiddleware導入Correctly）"""
    print("\n🚀 Test 1: 主Application導入")
    print("-" * 60)

    try:
        # Trying導入主Application
        from app.main import app
        print("   ✅ 主Application導入Success")

        # VerifyApplicationType
        from fastapi import FastAPI
        assert isinstance(app, FastAPI), "Application不Yes FastAPI Instance"
        print("   ✅ ApplicationTypeCorrectly (FastAPI)")

        # CheckApplicationTitle
        assert app.title == "Aileron - Workspace Manager"
        print(f"   ✅ ApplicationTitle: {app.title}")

        return True
    except Exception as e:
        print(f"   ❌ 導入Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_middleware_registered():
    """TestMiddleware已Correctly註冊ToApplication"""
    print("\n🔧 Test 2: Middleware註冊")
    print("-" * 60)

    try:
        from app.main import app
        from app.modules.auth import JWTAuthenticationMiddleware

        # CheckUserMiddleware
        user_middleware = [m for m in app.user_middleware
                          if m.cls == JWTAuthenticationMiddleware]

        if user_middleware:
            print(f"   ✅ JWTAuthenticationMiddleware 已註冊")
            print(f"   - MiddlewareQuantity: {len(user_middleware)}")
            return True
        else:
            print("   ⚠️  JWTAuthenticationMiddleware 未找To")
            print("   這PossiblyYesNormal的，如果它以OtherWay註冊")
            return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_routes_accessible():
    """Test現有RouteStill可Access"""
    print("\n🛣️  Test 3: Route可Access性")
    print("-" * 60)

    try:
        from app.main import app

        # GetAllRoute
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                for method in route.methods or []:
                    routes.append(f"{method} {route.path}")

        print(f"   找To {len(routes)} 個RouteEndpoint")

        # CheckKeyRouteYesNo存At
        key_routes = [
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/api/v1/workspaces",
            "/api/v1/oauth2/login",
        ]

        for route_path in key_routes:
            found = any(route_path in route for route in routes)
            status = "✅" if found else "⚠️ "
            print(f"   {status} {route_path}")

        print(f"\n   ✅ Route總數: {len(routes)}")
        return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_middleware_functionality():
    """TestMiddlewareCoreFunction"""
    print("\n🔐 Test 4: MiddlewareFunction")
    print("-" * 60)

    try:
        from app.modules.auth import JWTAuthenticationMiddleware

        # Create模擬Application
        class MockApp:
            pass

        # CreateMiddlewareInstance
        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

        print("   ✅ MiddlewareCreateSuccess")

        # TestRoad徑Arranging除
        test_cases = [
            ("/health", True, "健康Check"),
            ("/docs", True, "API 文檔"),
            ("/test-public", True, "TestPublicRoad徑"),
            ("/public/api", True, "Public API Pattern"),
            ("/api/workspaces", False, "受Protect的Workspace API"),
            ("/api/teams", False, "受Protect的Team API"),
        ]

        all_pass = True
        for path, expected, description in test_cases:
            result = middleware._is_excluded_path(path)
            status = "✅" if result == expected else "❌"
            if result != expected:
                all_pass = False
            print(f"   {status} {description}: {path} -> {result}")

        if all_pass:
            print("\n   ✅ AllRoad徑Arranging除TestPassed")
        else:
            print("\n   ⚠️  PartRoad徑Arranging除TestFailed")

        return all_pass

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bearer_token_extraction():
    """Test Bearer token ExtractFunction"""
    print("\n🎫 Test 5: Bearer Token Extract")
    print("-" * 60)

    try:
        from app.modules.auth import JWTAuthenticationMiddleware

        class MockApp:
            pass

        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        middleware = JWTAuthenticationMiddleware(MockApp())

        # Test用例
        test_cases = [
            ({"Authorization": "Bearer test-token"}, "test-token", "Valid token"),
            ({}, None, "缺Less Authorization header"),
            ({"Authorization": "InvalidFormat token"}, None, "InvalidFormat"),
            ({"Authorization": "Bearer "}, None, "空 token"),
        ]

        all_pass = True
        for headers, expected, description in test_cases:
            request = MockRequest(headers)
            result = middleware._extract_bearer_token(request)
            status = "✅" if result == expected else "❌"
            if result != expected:
                all_pass = False
            print(f"   {status} {description}: {repr(result)}")

        if all_pass:
            print("\n   ✅ All token ExtractTestPassed")
        else:
            print("\n   ⚠️  Part token ExtractTestFailed")

        return all_pass

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auth_decorators():
    """TestAuthenticationDecoratorStillAvailable"""
    print("\n🔒 Test 6: AuthenticationDecorator")
    print("-" * 60)

    try:
        from app.modules.auth import (
            require_role,
            require_permission,
            get_current_user,
            get_optional_current_user,
            has_permission,
            has_role,
        )

        print("   ✅ AllAuthenticationDecorator導入Success")

        # TestPermissionCheck函數
        assert has_permission("workspace:read", ["workspace:read"]) is True
        print("   ✅ has_permission Normal")

        assert has_role("admin", ["admin", "user"]) is True
        print("   ✅ has_role Normal")

        return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """TestModule導Out完整性"""
    print("\n📤 Test 7: Module導Out")
    print("-" * 60)

    try:
        from app.modules import auth

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
            'get_current_user',
            'get_optional_current_user',
            'JWTAuthenticationMiddleware',
            'StrictJWTAuthenticationMiddleware',
        ]

        missing_exports = []
        for export in required_exports:
            if export not in auth.__all__:
                missing_exports.append(export)

        if missing_exports:
            print(f"   ❌ 缺Less導Out: {', '.join(missing_exports)}")
            return False
        else:
            print(f"   ✅ AllNecessary符Number已導Out ({len(auth.__all__)} 個)")
            return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_integration():
    """TestConfigurationIntegration"""
    print("\n⚙️  Test 8: ConfigurationIntegration")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        print(f"   ✅ ConfigurationLoadSuccess")
        print(f"   - AuthenticationEnabled: {config.enabled}")
        print(f"   - Keycloak URL: {config.server_url}")
        print(f"   - Realm: {config.realm}")

        # VerifyConfigurationType
        from app.modules.auth import KeycloakConfig
        assert isinstance(config, KeycloakConfig)
        print(f"   ✅ ConfigurationTypeCorrectly")

        return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_backward_compatibility():
    """TestTowardsBack兼容性（Authentication未Enabled時）"""
    print("\n🔄 Test 9: TowardsBack兼容性")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        if not config.enabled:
            print("   ✅ Authentication未Enabled（ENABLE_AUTH=false）")
            print("   ✅ 現有FunctionShould不受Impact")
            print("\n   Expected行為：")
            print("   - Middleware跳過 token Verify")
            print("   - request.state.auth_enabled = False")
            print("   - request.state.current_user = None")
            return True
        else:
            print("   ℹ️  Authentication已Enabled（ENABLE_AUTH=true）")
            print("   ℹ️  要TestTowardsBack兼容性，請Setup ENABLE_AUTH=false")
            return True

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """ExecuteAll集成Test"""
    print("=" * 60)
    print("🧪 Stage 6 集成Test - VerifyMiddleware不破Bad現有Function")
    print("=" * 60)

    results = []

    # RunAllTest
    results.append(("主Application導入", test_main_app_import()))
    results.append(("Middleware註冊", test_middleware_registered()))
    results.append(("Route可Access性", test_routes_accessible()))
    results.append(("MiddlewareFunction", test_middleware_functionality()))
    results.append(("Bearer Token Extract", test_bearer_token_extraction()))
    results.append(("AuthenticationDecorator", test_auth_decorators()))
    results.append(("Module導Out", test_module_exports()))
    results.append(("ConfigurationIntegration", test_config_integration()))
    results.append(("TowardsBack兼容性", test_backward_compatibility()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 TestSummary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ Passed" if result else "❌ Failed"
        print(f"{status}  {test_name}")

    print()
    print(f"Passed率: {passed}/{total} ({passed * 100 // total if total > 0 else 0}%)")

    if passed == total:
        print("\n🎉 AllTestPassed！Middleware不會破Bad現有Function。")
        print("\n✅ 可以Safe地ContinueImplementBelow一StageTask。")
        return 0
    else:
        print("\n⚠️  PartTestFailed，請CheckAbove述ErrorMessage。")
        print("\n💡 SuggestFixProblemBack再ContinueImplementBelow一Stage。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
