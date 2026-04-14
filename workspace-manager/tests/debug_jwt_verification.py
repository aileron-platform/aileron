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
    print("🔍 JWT Token 驗證調試")
    print("=" * 70)
    print()

    # Import after path is set
    from app.modules.auth.config import get_keycloak_config, reload_keycloak_config
    from app.modules.auth.jwt_utils import JWTUtils

    # 1. Check configuration
    print("步驟 1: 檢查 Keycloak 配置")
    print("-" * 70)
    config = get_keycloak_config()
    print(f"認證啟用: {config.enabled}")
    print(f"伺服器 URL: {config.server_url}")
    print(f"Realm: {config.realm}")
    print(f"Client ID: {config.client_id}")
    print()

    # 2. Test JWKS endpoint
    print("步驟 2: 測試 JWKS 端點")
    print("-" * 70)

    # Construct JWKS URL
    jwks_url = f"{config.server_url}/realms/{config.realm}/protocol/openid-connect/certs"
    print(f"JWKS URL: {jwks_url}")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            print(f"狀態碼: {response.status_code}")

            if response.status_code == 200:
                jwks_data = response.json()
                print(f"✅ JWKS 端點可訪問")
                print(f"Keys 數量: {len(jwks_data.get('keys', []))}")

                # Show first key info
                if jwks_data.get('keys'):
                    first_key = jwks_data['keys'][0]
                    print(f"第一個 Key ID: {first_key.get('kid')}")
                    print(f"算法: {first_key.get('alg')}")
            else:
                print(f"❌ JWKS 請求失敗")
                print(f"響應: {response.text}")
                return
    except Exception as e:
        print(f"❌ JWKS 請求異常: {e}")
        import traceback
        traceback.print_exc()
        return

    print()

    # 3. Test JWT verification with sample token
    print("步驟 3: 測試 Token 驗證")
    print("-" * 70)

    # Get a token from environment or user input
    token = sys.stdin.readline().strip() if not sys.stdin.isatty() else None

    if not token:
        print("沒有提供 token，跳過驗證測試")
        print()
        return

    try:
        jwt_utils = JWTUtils()
        payload = await jwt_utils.verify_token(token)

        print(f"✅ Token 驗證成功！")
        print(f"用戶: {payload.get('preferred_username')}")
        print(f"Email: {payload.get('email')}")
        print(f"角色: {payload.get('realm_access', {}).get('roles', [])}")

    except Exception as e:
        print(f"❌ Token 驗證失敗: {e}")
        import traceback
        traceback.print_exc()

    print()

    # Summary
    print("=" * 70)
    print("調試完成")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
