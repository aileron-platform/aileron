"""
Test Workspace Runtime JWT Token validation functionality
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_jwt_auth():
    """Test JWT authentication functionality"""
    print("=" * 70)
    print("🧪 Workspace Runtime JWT Authentication Test")
    print("=" * 70)
    print()

    # Import necessary modules
    try:
        from app.modules.auth import get_keycloak_config, get_jwt_utils
        from app.services.auth_service import get_auth_service
    except ImportError as e:
        print(f"❌ Module import failed: {e}")
        print("Please ensure all dependencies are installed: pip install python-jose[cryptography]")
        return False

    # 1. Check configuration
    print("Step 1: Check Keycloak configuration")
    print("-" * 70)

    try:
        config = get_keycloak_config()
        print(f"Authentication enabled: {config.enabled}")

        if not config.enabled:
            print("⚠️  Keycloak authentication not enabled")
            print("Please set ENABLE_AUTH=true in workspace-manager/.env")
            return False

        print(f"Server URL: {config.server_url}")
        print(f"Realm: {config.realm}")
        print(f"Client ID: {config.client_id}")
        print()

    except Exception as e:
        print(f"❌ Configuration read failed: {e}")
        return False

    # 2. Test JWKS endpoint
    print("Step 2: Test JWKS endpoint")
    print("-" * 70)

    try:
        jwt_utils = get_jwt_utils()
        jwks = await jwt_utils.fetch_jwks()
        print(f"✅ JWKS endpoint accessible")
        print(f"Keys count: {len(jwks.get('keys', []))}")
        print()

    except Exception as e:
        print(f"❌ JWKS endpoint access failed: {e}")
        print("Please ensure Keycloak container is running")
        return False

    # 3. Test Token validation
    print("Step 3: Test Token validation")
    print("-" * 70)
    print()

    # Get test token (from workspace-manager)
    print("Getting test token from workspace-manager...")
    import subprocess

    try:
        # Use script to get token from Keycloak
        token_cmd = [
            "docker", "exec", "aileron-workspace-manager-dev",
            "wget", "-q", "-O-", "--timeout=10",
            "--post-data=client_id=workspace-manager&client_secret=workspace-manager-secret-12345&username=admin&password=admin123&grant_type=password",
            "--header=Content-Type: application/x-www-form-urlencoded",
            "http://aileron-keycloak-dev:8080/realms/aileron/protocol/openid-connect/token"
        ]

        result = subprocess.run(token_cmd, capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            print(f"❌ Token retrieval failed: {result.stderr}")
            return False

        # Parse token
        import json
        token_data = json.loads(result.stdout)
        test_token = token_data.get("access_token")

        if not test_token:
            print(f"❌ Token retrieval failed: {token_data}")
            return False

        print(f"✅ Token retrieved successfully (length: {len(test_token)} characters)")
        print()

    except Exception as e:
        print(f"❌ Token retrieval exception: {e}")
        return False

    # 4. Validate Token
    print("Step 4: Validate JWT Token")
    print("-" * 70)

    try:
        payload = await jwt_utils.decode_token_async(test_token)
        print(f"✅ Token validation successful!")
        print(f"User ID: {payload.get('sub')}")
        print(f"Username: {payload.get('preferred_username')}")
        print(f"Email: {payload.get('email')}")
        print(f"Roles: {payload.get('realm_access', {}).get('roles', [])}")
        print()

    except Exception as e:
        print(f"❌ Token validation failed: {e}")
        return False

    # 5. Test AuthService
    print("Step 5: Test AuthService")
    print("-" * 70)

    try:
        auth_service = get_auth_service()
        user = await auth_service.validate_access_token(test_token)

        if user:
            print(f"✅ AuthService validation successful!")
            print(f"User ID: {user.id}")
            print(f"Username: {user.username}")
            print(f"Email: {user.email}")
            print(f"Roles: {user.roles}")
            print()

        else:
            print(f"❌ AuthService validation failed: user is None")
            return False

    except Exception as e:
        print(f"❌ AuthService validation exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Summary
    print("=" * 70)
    print("✅ All tests passed!")
    print("=" * 70)
    print()
    print("📋 Test Results:")
    print("   ✅ Keycloak configuration correct")
    print("   ✅ JWKS endpoint accessible")
    print("   ✅ Token retrieval successful")
    print("   ✅ Token validation successful")
    print("   ✅ AuthService integration successful")
    print()
    print("🚀 Workspace Runtime JWT authentication ready!")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_jwt_auth())
    sys.exit(0 if success else 1)
