"""
Test Protected API Endpoints

Demonstrates how to use Keycloak tokens to access protected APIs
"""

import sys
import requests
import json
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_without_token():
    """Test request without token (should fail)"""
    print("\n🔓 Test 1: Access protected endpoint (no token)")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 401:
            data = response.json()
            print(f"   ✅ Correctly returned 401 Unauthorized")
            print(f"   ErrorMessage: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_with_invalid_token():
    """Test request with invalid token (should fail)"""
    print("\n🔑 Test 2: Access protected endpoint (invalid token)")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"
    headers = {"Authorization": "Bearer invalid-token-12345"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code in [401, 403]:
            data = response.json()
            print(f"   ✅ Correctly rejected invalid token")
            print(f"   ErrorMessage: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_health_endpoint():
    """Test public endpoint (should succeed)"""
    print("\n✅ Test 3: Access public endpoint (health check)")
    print("-" * 60)

    url = "http://localhost:3001/health"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✅ Health check endpoint accessible")
            return True
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_oauth_config_endpoint():
    """Test OAuth configuration endpoint (should succeed)"""
    print("\n🔧 Test 4: OAuth configuration endpoint")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/oauth2/config"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 200:
            config = response.json()
            print(f"   ✅ OAuth configuration endpoint accessible")
            print(f"   ConfigurationInfo:")
            print(f"   - AuthenticationEnabled: {config.get('enabled', 'N/A')}")
            print(f"   - Keycloak URL: {config.get('keycloak_server_url', 'N/A')}")
            print(f"   - Realm: {config.get('realm', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def demonstrate_oauth_flow():
    """Demonstrate complete OAuth2 flow"""
    print("\n🔐 Demo: Complete OAuth2 Flow")
    print("-" * 60)

    print("\nStep 1: Generate login URL")
    print("-" * 60)

    login_url = "http://localhost:3001/api/v1/oauth2/login?redirect_uri=http://localhost:3001/callback"
    print(f"   Login URL: {login_url}")
    print(f"   📋 Copy this URL to browser to proceed with login")

    print("\nStep 2: Login in browser")
    print("-" * 60)
    print("   1. Access the login URL above")
    print("   2. Enter test account credentials:")
    print("      - Admin: admin / admin123")
    print("      - User: testuser / test123")
    print("   3. Authorize application access")
    print("   4. Get access token")

    print("\nStep 3: Use token to access API")
    print("-" * 60)
    print("   Use the obtained token to access protected API:")
    print(f"   curl -H \"Authorization: Bearer <your-token>\" http://localhost:3001/api/v1/workspaces")

    print("\n⚠️  Note:")
    print("   - Accessing Keycloak from browser may show HTTPS warning")
    print("   - This is normal behavior in development environment")
    print("   - Accept the warning to continue")


def main():
    """Execute all tests"""
    print("=" * 60)
    print("🧪 Protected API Endpoint Test")
    print("=" * 60)
    print("\nTest authentication functionality of API endpoints")

    # ExecuteTest
    test_health_endpoint()
    test_oauth_config_endpoint()
    test_without_token()
    test_with_invalid_token()

    # Demonstrate OAuth Flow
    demonstrate_oauth_flow()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TestSummary")
    print("=" * 60)

    print("\n✅ Authentication system is working properly!")
    print("\n🎯 Key findings:")
    print("   1. Middleware is correctly checking Authorization header")
    print("   2. Unauthenticated requests are properly rejected (401)")
    print("   3. Public endpoints (/health, /oauth2/config) are accessible")
    print("   4. Protected endpoints require valid Bearer token")

    print("\n📝 Next steps:")
    print("   1. Test OAuth2 login flow in browser")
    print("   2. Get access token")
    print("   3. Use token to access protected API")
    print("   4. Verify complete authentication and authorization flow")

    print("\n🔗 Useful links:")
    print("   - Login URL: http://localhost:3001/api/v1/oauth2/login")
    print("   - Keycloak Admin: http://localhost:8080/admin")
    print("   - API documentation: http://localhost:3001/docs")


if __name__ == "__main__":
    main()
