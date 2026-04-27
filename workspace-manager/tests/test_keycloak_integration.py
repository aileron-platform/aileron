"""
Keycloak 集成Test - Verify完整的 OAuth2 Flow

TestFrontLifting：
1. Keycloak 正AtRun
2. Realm 已Configuration：aileron
3. Client 已Configuration：workspace-manager
4. TestUser已Create
5. ENABLE_AUTH=true
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_keycloak_config():
    """Test Keycloak Configuration"""
    print("\n🔧 Test 1: Keycloak Configuration")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        print(f"   ConfigurationInfo:")
        print(f"   - AuthenticationEnabled: {config.enabled}")
        print(f"   - Server URL: {config.server_url}")
        print(f"   - Realm: {config.realm}")
        print(f"   - Client ID: {config.client_id}")

        if not config.enabled:
            print("\n   ❌ Authentication not enabled! Please set ENABLE_AUTH=true")
            return False

        if not config.server_url:
            print("\n   ❌ Keycloak server URL not configured!")
            return False

        if not config.realm:
            print("\n   ❌ Realm not configured!")
            return False

        print("\n   ✅ Keycloak configuration correct")
        return True

    except Exception as e:
        print(f"   ❌ ConfigurationCheckFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_oauth_endpoints():
    """Test OAuth2 Endpoint"""
    print("\n🔐 Test 2: OAuth2 Endpoint")
    print("-" * 60)

    try:
        from app.main import app

        # Get routes
        oauth_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and '/oauth2' in route.path:
                oauth_routes.append(route.path)

        print(f"   Found {len(oauth_routes)} OAuth2 endpoints")

        expected_endpoints = [
            "/api/v1/oauth2/login",
            "/api/v1/oauth2/callback",
            "/api/v1/oauth2/refresh",
            "/api/v1/oauth2/logout",
            "/api/v1/oauth2/me",
            "/api/v1/oauth2/config",
        ]

        all_found = True
        for endpoint in expected_endpoints:
            found = endpoint in oauth_routes
            status = "✅" if found else "❌"
            print(f"   {status} {endpoint}")
            if not found:
                all_found = False

        if all_found:
            print("\n   ✅ All OAuth2 endpoints registered")
        else:
            print("\n   ⚠️  Some OAuth2 endpoints missing")

        return all_found

    except Exception as e:
        print(f"   ❌ EndpointCheckFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwks_endpoint():
    """Test JWKS Endpoint (Keycloak Public Key Endpoint)"""
    print("\n🔑 Test 3: JWKS Endpoint")
    print("-" * 60)

    try:
        import requests

        # Build JWKS URL
        jwks_url = "http://localhost:8080/realms/aileron/protocol/openid-connect/certs"

        print(f"   Test URL: {jwks_url}")

        try:
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()

            jwks = response.json()
            keys = jwks.get('keys', [])

            print(f"   ✅ JWKS endpoint accessible")
            print(f"   - Found {len(keys)} public keys")

            if keys:
                for i, key in enumerate(keys):
                    kid = key.get('kid', 'N/A')
                    kty = key.get('kty', 'N/A')
                    print(f"   - Key {i+1}: kid={kid}, type={kty}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"   ❌ JWKS endpoint not accessible: {e}")
            return False

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_openid_configuration():
    """Test OpenID Connect ConfigurationEndpoint"""
    print("\n📋 Test 4: OpenID Connect Configuration")
    print("-" * 60)

    try:
        import requests

        # Build configuration URL
        config_url = "http://localhost:8080/realms/aileron/.well-known/openid-configuration"

        print(f"   Test URL: {config_url}")

        try:
            response = requests.get(config_url, timeout=5)
            response.raise_for_status()

            config = response.json()

            print(f"   ✅ OpenID configuration accessible")
            print(f"   - Issuer: {config.get('issuer', 'N/A')}")
            print(f"   - Authorization endpoint: {config.get('authorization_endpoint', 'N/A')}")
            print(f"   - Token endpoint: {config.get('token_endpoint', 'N/A')}")
            print(f"   - JWKS URI: {config.get('jwks_uri', 'N/A')}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"   ❌ Configuration endpoint not accessible: {e}")
            return False

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_keycloak_users():
    """Test Keycloak UserConfiguration"""
    print("\n👤 Test 5: Keycloak User")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config
        import requests

        config = get_keycloak_config()

        # 構建UserList URL
        users_url = f"{config.server_url}/{config.realm}/protocol/openid-connect/userinfo"

        print(f"   TestUserEndpoint")

        # Noticing：這NeedingValid的 access token
        # We只能TestEndpointYesNo存At，不能ActualGetUserList

        try:
            # TestManagementEndpoint（Needing admin Authentication）
            token_url = f"http://localhost:8080/realms/master/protocol/openid-connect/token"
            data = {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "admin",
                "password": "admin"
            }

            response = requests.post(token_url, data=data, timeout=5)

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')

                # Use token GetUserList
                users_url = f"http://localhost:8080/admin/realms/{config.realm}/users"
                headers = {"Authorization": f"Bearer {access_token}"}

                response = requests.get(users_url, headers=headers, timeout=5)
                response.raise_for_status()

                users = response.json()
                print(f"   ✅ 找To {len(users)} 個User")

                for user in users[:5]:  # 只DisplayFront 5 個
                    username = user.get('username', 'N/A')
                    email = user.get('email', 'N/A')
                    enabled = user.get('enabled', False)
                    print(f"   - {username} ({email}) - {'Enabled' if enabled else '禁用'}")

                return True
            else:
                print(f"   ⚠️  無法Get admin token")
                print(f"   - StatusCode: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"   ❌ UserEndpointTestFailed: {e}")
            return False

    except Exception as e:
        print(f"   ❌ TestFailed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """ExecuteAll Keycloak 集成Test"""
    print("=" * 60)
    print("🧪 Keycloak 集成Test")
    print("=" * 60)

    results = []

    # RunAllTest
    results.append(("Keycloak Configuration", test_keycloak_config()))
    results.append(("OAuth2 Endpoint", test_oauth_endpoints()))
    results.append(("JWKS Endpoint", test_jwks_endpoint()))
    results.append(("OpenID Configuration", test_openid_configuration()))
    results.append(("Keycloak User", test_keycloak_users()))

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
        print("\n🎉 AllTestPassed！Keycloak ConfigurationSuccess。")
        print("\n📝 Test帳Number：")
        print("   - Admin: admin / admin123")
        print("   - User: testuser / test123")
        print("\n🔗 Keycloak Admin Console:")
        print("   - URL: http://localhost:8080/admin")
        print("   - Realm: aileron")
        print("\n✅ 可以On始Test完整的 OAuth2 Flow！")
        return 0
    else:
        print("\n⚠️  PartTestFailed，請CheckAbove述ErrorMessage。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
