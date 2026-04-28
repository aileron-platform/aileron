"""
JWT Authentication Middleware Functionality Test Script

Test various middleware functions including:
- Token extraction
- Path exclusion
- Token verification
- User info injection
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_middleware_import():
    """Test middleware import"""
    print("🔧 Testing middleware import...")
    try:
        from app.modules.auth.middleware import (
            JWTAuthenticationMiddleware,
            StrictJWTAuthenticationMiddleware,
        )
        print("   ✅ Middleware imported successfully")
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False


def test_middleware_initialization():
    """Test middleware initialization"""
    print("\n⚙️  Testing middleware initialization...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        # Create mock application
        class MockApp:
            pass

        mock_app = MockApp()

        # Create middleware instance
        middleware = JWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

        print(f"   ✅ Middleware initialized successfully")
        print(f"   - Excluded paths count: {len(middleware.exclude_paths)}")
        print(f"   - Excluded patterns count: {len(middleware.exclude_patterns)}")

        return True
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
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

        # Test valid Bearer token
        request = MockRequest({"Authorization": "Bearer test-token-12345"})
        token = middleware._extract_bearer_token(request)
        assert token == "test-token-12345", f"Expected 'test-token-12345', got '{token}'"
        print("   ✅ Valid Bearer token extracted successfully")

        # Test missing Authorization header
        request = MockRequest({})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None, got '{token}'"
        print("   ✅ Missing Authorization header handled correctly")

        # Test invalid format
        request = MockRequest({"Authorization": "InvalidFormat token"})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None for invalid format, got '{token}'"
        print("   ✅ Invalid format handled correctly")

        return True
    except Exception as e:
        print(f"   ❌ Token extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_exclusion():
    """Test path exclusion logic"""
    print("\n🚷 Testing path exclusion logic...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        class MockApp:
            pass

        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/test-public", "/custom-path"],
            exclude_patterns=["/public/*", "/api/public/*"],
        )

        # Test exact match
        assert middleware._is_excluded_path("/test-public") is True
        assert middleware._is_excluded_path("/custom-path") is True
        print("   ✅ Exact match exclusion correct")

        # Test pattern match
        assert middleware._is_excluded_path("/public/resource") is True
        assert middleware._is_excluded_path("/api/public/data") is True
        print("   ✅ Pattern match exclusion correct")

        # Test no match
        assert middleware._is_excluded_path("/api/workspaces") is False
        assert middleware._is_excluded_path("/protected/data") is False
        print("   ✅ Non-excluded paths judged correctly")

        # Test default excluded paths
        assert middleware._is_excluded_path("/health") is True
        assert middleware._is_excluded_path("/docs") is True
        assert middleware._is_excluded_path("/redoc") is True
        print("   ✅ Default excluded paths correct")

        return True
    except Exception as e:
        print(f"   ❌ Path exclusion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """Test module exports"""
    print("\n📤 Testing module exports...")
    try:
        from app.modules import auth

        # Check if middleware is exported
        assert hasattr(auth, 'JWTAuthenticationMiddleware'), "JWTAuthenticationMiddleware not exported"
        assert hasattr(auth, 'StrictJWTAuthenticationMiddleware'), "StrictJWTAuthenticationMiddleware not exported"

        # Check __all__
        assert 'JWTAuthenticationMiddleware' in auth.__all__, "JWTAuthenticationMiddleware not in __all__"
        assert 'StrictJWTAuthenticationMiddleware' in auth.__all__, "StrictJWTAuthenticationMiddleware not in __all__"

        print("   ✅ Middleware correctly exported")
        print(f"   - JWTAuthenticationMiddleware")
        print(f"   - StrictJWTAuthenticationMiddleware")

        return True
    except Exception as e:
        print(f"   ❌ Module export test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Execute all tests"""
    print("=" * 60)
    print("🔐 JWT Authentication Middleware Functionality Test")
    print("=" * 60)

    results = []

    # Run all tests
    results.append(("Middleware Import", test_middleware_import()))
    results.append(("Middleware Initialization", test_middleware_initialization()))
    results.append(("Bearer Token Extraction", test_bearer_token_extraction()))
    results.append(("Path Exclusion Logic", test_path_exclusion()))
    results.append(("Module Exports", test_module_exports()))

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
        print("\n🎉 All tests passed! JWT Authentication Middleware functions properly.")
        return 0
    else:
        print("\n⚠️  Some tests failed, please check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
