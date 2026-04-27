#!/usr/bin/env python3
"""
Test complete OAuth2 flow from within container
Use Docker network communication (HTTP) to avoid HTTPS requirements
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import json
import os

def main():
    print("=" * 70)
    print("🔑 Keycloak OAuth2 Complete Flow Test")
    print("=" * 70)

    # Configuration
    KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://aileron-keycloak-dev:8080")
    REALM = os.getenv("KEYCLOAK_REALM", "aileron")
    CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "workspace-manager")
    CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "workspace-manager-secret-12345")

    print(f"\nConfiguration info:")
    print(f"  Keycloak URL: {KEYCLOAK_URL}")
    print(f"  Realm: {REALM}")
    print(f"  Client ID: {CLIENT_ID}")

    # Step 1: Get Admin Token
    print("\n" + "=" * 70)
    print("Step 1: Get Admin Token")
    print("-" * 70)

    token_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    print(f"Token URL: {token_url}")

    token_data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "username": "admin",
        "password": "admin123",
        "grant_type": "password"
    }

    try:
        print("\nRequesting token...")
        response = requests.post(token_url, data=token_data, timeout=10)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            token_response = response.json()
            access_token = token_response.get("access_token")

            print(f"\n✅ Token obtained successfully!")
            print(f"Token type: {token_response.get('token_type')}")
            print(f"Token length: {len(access_token)} characters")
            print(f"Expires in: {token_response.get('expires_in')} seconds")

            # Decode JWT to view contents
            import base64
            parts = access_token.split('.')
            if len(parts) == 3:
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                claims = json.loads(decoded)
                print(f"\n📋 Token Payload:")
                print(f"  Username: {claims.get('preferred_username')}")
                print(f"  Email: {claims.get('email')}")
                print(f"  Roles: {claims.get('realm_access', {}).get('roles', [])}")

        else:
            print(f"\n❌ Token acquisition failed")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ Request failed: {e}")
        print(f"\n💡 Hint: Ensure Keycloak container is running")
        print(f"   Check command: docker ps | grep keycloak")
        return False

    # Step 2: Test protected API endpoints
    print("\n" + "=" * 70)
    print("Step 2: Test Protected API Endpoints")
    print("=" * 70)

    # Test 2.1: Get current user information
    print("\nTest 2.1: GET /api/v1/oauth2/me")
    print("-" * 70)

    me_url = "http://localhost:3001/api/v1/oauth2/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(me_url, headers=headers, timeout=5)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ Successfully obtained user information!\n")
            print("User information:")
            print(json.dumps(user_info, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Request failed")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Request failed: {e}")
        print(f"\n💡 Hint: Ensure workspace-manager service is running")
        return False

    # Test 2.2: Test request without token
    print("\nTest 2.2: Test request without token (should return 401)")
    print("-" * 70)

    try:
        response = requests.get(me_url, timeout=5)
        print(f"Status code: {response.status_code}")

        if response.status_code == 401:
            error_info = response.json()
            print(f"✅ Correctly rejected unauthenticated request!\n")
            print("Error information:")
            print(json.dumps(error_info, indent=2, ensure_ascii=False))
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

    # Summary
    print("\n" + "=" * 70)
    print("✅ Test completed! Authentication system is working properly!")
    print("=" * 70)

    print("\n📝 Test results:")
    print("   ✅ Keycloak token acquisition successful")
    print("   ✅ JWT token verification successful")
    print("   ✅ Protected API endpoints working properly")
    print("   ✅ Middleware correctly intercepts unauthenticated requests")
    print("   ✅ User information correctly extracted")

    print("\n🔗 Test accounts:")
    print("   - Admin: admin / admin123 (role: admin)")
    print("   - User: testuser / test123 (role: user)")

    print("\n🚀 Authentication system is ready to use!")
    print("\n💡 Next steps:")
    print("   1. Test OAuth2 login flow in browser")
    print("   2. Implement frontend integration")
    print("   3. Implement token verification for Workspace Runtime")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
