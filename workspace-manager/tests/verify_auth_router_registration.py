"""
Keycloak Auth Router Registration Verification Test Script

Checks:
1. Whether Keycloak auth router import is successful
2. Whether router is correctly registered to main application
3. Whether route endpoints are available
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_keycloak_auth_module_import():
    """Test Keycloak auth module import"""
    print("📦 Test 1: Keycloak Auth Module Import")
    print("-" * 60)

    try:
        from app.modules.auth import auth_router as keycloak_auth_router
        print("✅ Keycloak auth router imported successfully")
        print(f"   Router type: {type(keycloak_auth_router)}")
        print(f"   Router prefix: {keycloak_auth_router.prefix}")
        print(f"   Router tags: {keycloak_auth_router.tags}")
        return keycloak_auth_router
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_keycloak_auth_routes(router):
    """Test Keycloak auth route endpoints"""
    print("\n🛣️  Test 2: Keycloak Auth Route Endpoints")
    print("-" * 60)

    if not router:
        print("❌ Router is None, skipping test")
        return False

    try:
        routes = router.routes
        print(f"✅ Found {len(routes)} route endpoints:\n")

        for route in routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = list(route.methods) if route.methods else []
                print(f"   • {', '.join(methods):<8} {route.path}")
            elif hasattr(route, 'path'):
                print(f"   • {route.path}")

        # Verify key endpoints
        route_paths = [route.path for route in routes if hasattr(route, 'path')]
        key_endpoints = [
            '/oauth2/login',
            '/oauth2/callback',
            '/oauth2/refresh',
            '/oauth2/logout',
            '/oauth2/me',
            '/oauth2/config',
        ]

        print("\n🔍 Verify key endpoints:")
        all_present = True
        for endpoint in key_endpoints:
            present = endpoint in route_paths
            status = "✅" if present else "❌"
            print(f"   {status} {endpoint}")
            if not present:
                all_present = False

        return all_present

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_app_import():
    """Test main application import (verify no circular imports)"""
    print("\n🚀 Test 3: Main Application Import")
    print("-" * 60)

    try:
        # Lazy import to avoid initializing the entire application
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app.main",
            project_root / "app" / "main.py"
        )

        # Check if module spec is accessible
        if spec and spec.loader:
            print("✅ Main application module spec loaded successfully")

            # Check if main.py contains keycloak_auth_router
            main_content = (project_root / "app" / "main.py").read_text()

            if "keycloak_auth_router" in main_content:
                print("✅ Main application contains keycloak_auth_router import")

                # Count occurrences
                import_count = main_content.count("keycloak_auth_router")
                print(f"   - Import statements: {import_count} locations")

                if "app.include_router(keycloak_auth_router" in main_content:
                    print("✅ Keycloak auth router registered to main application")
                    return True
                else:
                    print("⚠️  Keycloak auth router not registered to main application")
                    return False
            else:
                print("⚠️  Main application does not contain keycloak_auth_router")
                return False
        else:
            print("❌ Unable to load main application module spec")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """Test module exported symbols"""
    print("\n📤 Test 4: Module Exported Symbols")
    print("-" * 60)

    try:
        from app.modules import auth

        # Check __all__ definition
        if hasattr(auth, '__all__'):
            exports = auth.__all__
            print(f"✅ Module exports {len(exports)} symbols:")

            # Categorize exports
            categories = {
                'Configuration': [],
                'JWT Utilities': [],
                'JWKS Cache': [],
                'Router': [],
                'User Sync': [],
                'Decorators': [],
                'Other': [],
            }

            for symbol in exports:
                symbol_lower = symbol.lower()
                if 'config' in symbol_lower:
                    categories['Configuration'].append(symbol)
                elif 'jwt' in symbol_lower:
                    categories['JWT Utilities'].append(symbol)
                elif 'jwks' in symbol_lower or 'cache' in symbol_lower:
                    categories['JWKS Cache'].append(symbol)
                elif 'router' in symbol_lower:
                    categories['Router'].append(symbol)
                elif 'sync' in symbol_lower or 'user' in symbol_lower:
                    categories['User Sync'].append(symbol)
                elif 'require' in symbol_lower or 'permission' in symbol_lower:
                    categories['Decorators'].append(symbol)
                else:
                    categories['Other'].append(symbol)

            for category, symbols in categories.items():
                if symbols:
                    print(f"\n   {category}:")
                    for symbol in symbols:
                        print(f"      • {symbol}")

            return True
        else:
            print("⚠️  Module does not define __all__")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Execute all tests"""
    print("=" * 60)
    print("🔐 Keycloak Auth Router Registration Verification")
    print("=" * 60)
    print()

    results = []

    # Test 1: Module import
    router = test_keycloak_auth_module_import()
    results.append(("Module Import", router is not None))

    # Test 2: Route endpoints
    if router:
        routes_ok = test_keycloak_auth_routes(router)
        results.append(("Route Endpoints", routes_ok))

    # Test 3: Main application import
    main_ok = test_main_app_import()
    results.append(("Main App Registration", main_ok))

    # Test 4: Module exports
    exports_ok = test_module_exports()
    results.append(("Module Exports", exports_ok))

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
        print("\n🎉 All tests passed! Keycloak auth router successfully registered.")
        return 0
    else:
        print("\n⚠️  Some tests failed, please check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
