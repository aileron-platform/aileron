"""
測試 Workspace Runtime 的 JWT Token 驗證功能
"""

import asyncio
import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_jwt_auth():
    """測試 JWT 認證功能"""
    print("=" * 70)
    print("🧪 Workspace Runtime JWT 認證測試")
    print("=" * 70)
    print()

    # 導入必要的模組
    try:
        from app.modules.auth import get_keycloak_config, get_jwt_utils
        from app.services.auth_service import get_auth_service
    except ImportError as e:
        print(f"❌ 導入模組失敗: {e}")
        print("請確保已安裝所有依賴: pip install python-jose[cryptography]")
        return False

    # 1. 檢查配置
    print("步驟 1: 檢查 Keycloak 配置")
    print("-" * 70)

    try:
        config = get_keycloak_config()
        print(f"認證啟用: {config.enabled}")

        if not config.enabled:
            print("⚠️  Keycloak 認證未啟用")
            print("請在 workspace-manager/.env 中設置 ENABLE_AUTH=true")
            return False

        print(f"伺服器 URL: {config.server_url}")
        print(f"Realm: {config.realm}")
        print(f"Client ID: {config.client_id}")
        print()

    except Exception as e:
        print(f"❌ 配置讀取失敗: {e}")
        return False

    # 2. 測試 JWKS 端點
    print("步驟 2: 測試 JWKS 端點")
    print("-" * 70)

    try:
        jwt_utils = get_jwt_utils()
        jwks = await jwt_utils.fetch_jwks()
        print(f"✅ JWKS 端點可訪問")
        print(f"Keys 數量: {len(jwks.get('keys', []))}")
        print()

    except Exception as e:
        print(f"❌ JWKS 端點訪問失敗: {e}")
        print("請確保 Keycloak 容器正在運行")
        return False

    # 3. 測試 Token 驗證
    print("步驟 3: 測試 Token 驗證")
    print("-" * 70)
    print()

    # 獲取測試 token（從 workspace-manager 獲取）
    print("從 workspace-manager 獲取測試 token...")
    import subprocess

    try:
        # 使用腳本從 Keycloak 獲取 token
        token_cmd = [
            "docker", "exec", "aileron-workspace-manager-dev",
            "wget", "-q", "-O-", "--timeout=10",
            "--post-data=client_id=workspace-manager&client_secret=workspace-manager-secret-12345&username=admin&password=admin123&grant_type=password",
            "--header=Content-Type: application/x-www-form-urlencoded",
            "http://aileron-keycloak-dev:8080/realms/aileron/protocol/openid-connect/token"
        ]

        result = subprocess.run(token_cmd, capture_output=True, text=True, timeout=15)

        if result.returncode != 0:
            print(f"❌ Token 獲取失敗: {result.stderr}")
            return False

        # 解析 token
        import json
        token_data = json.loads(result.stdout)
        test_token = token_data.get("access_token")

        if not test_token:
            print(f"❌ Token 獲取失敗: {token_data}")
            return False

        print(f"✅ Token 獲取成功 (長度: {len(test_token)} 字符)")
        print()

    except Exception as e:
        print(f"❌ Token 獲取異常: {e}")
        return False

    # 4. 驗證 Token
    print("步驟 4: 驗證 JWT Token")
    print("-" * 70)

    try:
        payload = await jwt_utils.decode_token_async(test_token)
        print(f"✅ Token 驗證成功！")
        print(f"用戶 ID: {payload.get('sub')}")
        print(f"用戶名: {payload.get('preferred_username')}")
        print(f"Email: {payload.get('email')}")
        print(f"角色: {payload.get('realm_access', {}).get('roles', [])}")
        print()

    except Exception as e:
        print(f"❌ Token 驗證失敗: {e}")
        return False

    # 5. 測試 AuthService
    print("步驟 5: 測試 AuthService")
    print("-" * 70)

    try:
        auth_service = get_auth_service()
        user = await auth_service.validate_access_token(test_token)

        if user:
            print(f"✅ AuthService 驗證成功！")
            print(f"用戶 ID: {user.id}")
            print(f"用戶名: {user.username}")
            print(f"Email: {user.email}")
            print(f"角色: {user.roles}")
            print()

        else:
            print(f"❌ AuthService 驗證失敗: user is None")
            return False

    except Exception as e:
        print(f"❌ AuthService 驗證異常: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 總結
    print("=" * 70)
    print("✅ 所有測試通過！")
    print("=" * 70)
    print()
    print("📋 測試結果：")
    print("   ✅ Keycloak 配置正確")
    print("   ✅ JWKS 端點可訪問")
    print("   ✅ Token 獲取成功")
    print("   ✅ Token 驗證成功")
    print("   ✅ AuthService 整合成功")
    print()
    print("🚀 Workspace Runtime JWT 認證已就緒！")

    return True


if __name__ == "__main__":
    success = asyncio.run(test_jwt_auth())
    sys.exit(0 if success else 1)
