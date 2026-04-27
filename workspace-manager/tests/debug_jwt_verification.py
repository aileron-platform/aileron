#!/usr/bin/env python3
"""
Debug JWT token verification
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import asyncio
import json

async def main():
    print("=" * 70)
    print("🔍 JWT Token Verification Debug")
    print("=" * 70)
    print()

    # Import after path is set
    from app.modules.auth.config import get_keycloak_config, reload_keycloak_config
    from app.modules.auth.jwt_utils import JWTUtils

    # 1. Check configuration
    print("Step 1: Check Keycloak Configuration")
    print("-" * 70)
    config = get_keycloak_config()
    print(f"Auth enabled: {config.enabled}")
    print(f"Server URL: {config.server_url}")
    print(f"Realm: {config.realm}")
    print(f"Client ID: {config.client_id}")
    print()

    # 2. Test JWKS endpoint
    print("Step 2: Test JWKS Endpoint")
    print("-" * 70)

    # Construct JWKS URL
    jwks_url = f"{config.server_url}/realms/{config.realm}/protocol/openid-connect/certs"
    print(f"JWKS URL: {jwks_url}")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            print(f"Status code: {response.status_code}")

            if response.status_code == 200:
                jwks_data = response.json()
                print(f"✅ JWKS endpoint accessible")
                print(f"Keys count: {len(jwks_data.get('keys', []))}")

                # Show first key info
                if jwks_data.get('keys'):
                    first_key = jwks_data['keys'][0]
                    print(f"First Key ID: {first_key.get('kid')}")
                    print(f"Algorithm: {first_key.get('alg')}")
            else:
                print(f"❌ JWKS request failed")
                print(f"Response: {response.text}")
                return
    except Exception as e:
        print(f"❌ JWKS request exception: {e}")
        import traceback
        traceback.print_exc()
        return

    print()

    # 3. Test JWT verification with sample token
    print("Step 3: Test Token Verification")
    print("-" * 70)

    # Get a token from environment or user input
    token = sys.stdin.readline().strip() if not sys.stdin.isatty() else None

    if not token:
        print("No token provided, skipping verification test")
        print()
        return

    try:
        jwt_utils = JWTUtils()
        payload = await jwt_utils.verify_token(token)

        print(f"✅ Token verification successful!")
        print(f"User: {payload.get('preferred_username')}")
        print(f"Email: {payload.get('email')}")
        print(f"Roles: {payload.get('realm_access', {}).get('roles', [])}")

    except Exception as e:
        print(f"❌ Token verification failed: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Summary
    print("=" * 70)
    print("Debug completed")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
