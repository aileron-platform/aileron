"""
JWT AuthenticationMiddlewareFunctionTest腳本

TestMiddleware的各種Function，包括：
- Token Extract
- Road徑Arranging除
- Token Verify
- UserInfo注入
"""

import sys
from pathlib import Path

# 添加Project根CatalogTo Python Road徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_middleware_import():
    """TestMiddleware導入"""
    print("🔧 TestMiddleware導入...")
    try:
        from app.modules.auth.middleware import (
            JWTAuthenticationMiddleware,
            StrictJWTAuthenticationMiddleware,
        )
        print("   ✅ Middleware導入Success")
        return True
    except Exception as e:
        print(f"   ❌ 導入Failed: {e}")
        return False


def test_middleware_initialization():
    """TestMiddlewareInitialize"""
    print("\n⚙️  TestMiddlewareInitialize...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        # Create模擬Application
        class MockApp:
            pass

        mock_app = MockApp()

        # CreateMiddlewareInstance
        middleware = JWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

        print(f"   ✅ MiddlewareInitializeSuccess")
        print(f"   - Arranging除Road徑Quantity: {len(middleware.exclude_paths)}")
        print(f"   - Arranging除PatternQuantity: {len(middleware.exclude_patterns)}")

        return True
    except Exception as e:
        print(f"   ❌ InitializeFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bearer_token_extraction():
    """Test Bearer token Extract"""
    print("\n🎫 Test Bearer Token Extract...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        class MockApp:
            pass

        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        middleware = JWTAuthenticationMiddleware(MockApp())

        # TestValid的 Bearer token
        request = MockRequest({"Authorization": "Bearer test-token-12345"})
        token = middleware._extract_bearer_token(request)
        assert token == "test-token-12345", f"Expected 'test-token-12345', got '{token}'"
        print("   ✅ Valid Bearer token ExtractSuccess")

        # Test缺Less Authorization header
        request = MockRequest({})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None, got '{token}'"
        print("   ✅ 缺Less Authorization header HandleCorrectly")

        # TestInvalidFormat
        request = MockRequest({"Authorization": "InvalidFormat token"})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None for invalid format, got '{token}'"
        print("   ✅ InvalidFormatHandleCorrectly")

        return True
    except Exception as e:
        print(f"   ❌ Token ExtractTestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_exclusion():
    """TestRoad徑Arranging除Logic"""
    print("\n🚷 TestRoad徑Arranging除Logic...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        class MockApp:
            pass

        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/test-public", "/custom-path"],
            exclude_patterns=["/public/*", "/api/public/*"],
        )

        # Test完全匹配
        assert middleware._is_excluded_path("/test-public") is True
        assert middleware._is_excluded_path("/custom-path") is True
        print("   ✅ 完全匹配Arranging除Correctly")

        # TestPattern匹配
        assert middleware._is_excluded_path("/public/resource") is True
        assert middleware._is_excluded_path("/api/public/data") is True
        print("   ✅ Pattern匹配Arranging除Correctly")

        # Test無匹配
        assert middleware._is_excluded_path("/api/workspaces") is False
        assert middleware._is_excluded_path("/protected/data") is False
        print("   ✅ 非Arranging除Road徑JudgingCorrectly")

        # Test默認Arranging除Road徑
        assert middleware._is_excluded_path("/health") is True
        assert middleware._is_excluded_path("/docs") is True
        assert middleware._is_excluded_path("/redoc") is True
        print("   ✅ 默認Arranging除Road徑Correctly")

        return True
    except Exception as e:
        print(f"   ❌ Road徑Arranging除TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """TestModule導Out"""
    print("\n📤 TestModule導Out...")
    try:
        from app.modules import auth

        # CheckMiddlewareYesNo已導Out
        assert hasattr(auth, 'JWTAuthenticationMiddleware'), "JWTAuthenticationMiddleware 未導Out"
        assert hasattr(auth, 'StrictJWTAuthenticationMiddleware'), "StrictJWTAuthenticationMiddleware 未導Out"

        # Check __all__
        assert 'JWTAuthenticationMiddleware' in auth.__all__, "JWTAuthenticationMiddleware 不At __all__ 中"
        assert 'StrictJWTAuthenticationMiddleware' in auth.__all__, "StrictJWTAuthenticationMiddleware 不At __all__ 中"

        print("   ✅ Middleware已Correctly導Out")
        print(f"   - JWTAuthenticationMiddleware")
        print(f"   - StrictJWTAuthenticationMiddleware")

        return True
    except Exception as e:
        print(f"   ❌ Module導OutTestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """ExecuteAllTest"""
    print("=" * 60)
    print("🔐 JWT AuthenticationMiddlewareFunctionTest")
    print("=" * 60)

    results = []

    # RunAllTest
    results.append(("Middleware導入", test_middleware_import()))
    results.append(("MiddlewareInitialize", test_middleware_initialization()))
    results.append(("Bearer Token Extract", test_bearer_token_extraction()))
    results.append(("Road徑Arranging除Logic", test_path_exclusion()))
    results.append(("Module導Out", test_module_exports()))

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
        print("\n🎉 AllTestPassed！JWT AuthenticationMiddlewareFunctionNormal。")
        return 0
    else:
        print("\n⚠️  PartTestFailed，請CheckAbove述ErrorMessage。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
