"""
Keycloak 集成測試 - 驗證完整的 OAuth2 流程

測試前提：
1. Keycloak 正在運行
2. Realm 已配置：aileron
3. Client 已配置：workspace-manager
4. 測試用戶已創建
5. ENABLE_AUTH=true
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_keycloak_config():
    """測試 Keycloak 配置"""
    print("\n🔧 測試 1: Keycloak 配置")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        print(f"   配置信息:")
        print(f"   - 認證啟用: {config.enabled}")
        print(f"   - 伺服器 URL: {config.server_url}")
        print(f"   - Realm: {config.realm}")
        print(f"   - Client ID: {config.client_id}")

        if not config.enabled:
            print("\n   ❌ 認證未啟用！請設置 ENABLE_AUTH=true")
            return False

        if not config.server_url:
            print("\n   ❌ Keycloak 伺服器 URL 未配置！")
            return False

        if not config.realm:
            print("\n   ❌ Realm 未配置！")
            return False

        print("\n   ✅ Keycloak 配置正確")
        return True

    except Exception as e:
        print(f"   ❌ 配置檢查失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_oauth_endpoints():
    """測試 OAuth2 端點"""
    print("\n🔐 測試 2: OAuth2 端點")
    print("-" * 60)

    try:
        from app.main import app

        # 獲取路由
        oauth_routes = []
        for route in app.routes:
            if hasattr(route, 'path') and '/oauth2' in route.path:
                oauth_routes.append(route.path)

        print(f"   找到 {len(oauth_routes)} 個 OAuth2 端點")

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
            print("\n   ✅ 所有 OAuth2 端點已註冊")
        else:
            print("\n   ⚠️  部分 OAuth2 端點缺失")

        return all_found

    except Exception as e:
        print(f"   ❌ 端點檢查失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_jwks_endpoint():
    """測試 JWKS 端點（Keycloak 公鑰端點）"""
    print("\n🔑 測試 3: JWKS 端點")
    print("-" * 60)

    try:
        import requests

        # 構建 JWKS URL
        jwks_url = "http://localhost:8080/realms/aileron/protocol/openid-connect/certs"

        print(f"   測試 URL: {jwks_url}")

        try:
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()

            jwks = response.json()
            keys = jwks.get('keys', [])

            print(f"   ✅ JWKS 端點可訪問")
            print(f"   - 找到 {len(keys)} 個公鑰")

            if keys:
                for i, key in enumerate(keys):
                    kid = key.get('kid', 'N/A')
                    kty = key.get('kty', 'N/A')
                    print(f"   - Key {i+1}: kid={kid}, type={kty}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"   ❌ JWKS 端點不可訪問: {e}")
            return False

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_openid_configuration():
    """測試 OpenID Connect 配置端點"""
    print("\n📋 測試 4: OpenID Connect 配置")
    print("-" * 60)

    try:
        import requests

        # 構建配置 URL
        config_url = "http://localhost:8080/realms/aileron/.well-known/openid-configuration"

        print(f"   測試 URL: {config_url}")

        try:
            response = requests.get(config_url, timeout=5)
            response.raise_for_status()

            config = response.json()

            print(f"   ✅ OpenID 配置可訪問")
            print(f"   - Issuer: {config.get('issuer', 'N/A')}")
            print(f"   - Authorization endpoint: {config.get('authorization_endpoint', 'N/A')}")
            print(f"   - Token endpoint: {config.get('token_endpoint', 'N/A')}")
            print(f"   - JWKS URI: {config.get('jwks_uri', 'N/A')}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"   ❌ 配置端點不可訪問: {e}")
            return False

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_keycloak_users():
    """測試 Keycloak 用戶配置"""
    print("\n👤 測試 5: Keycloak 用戶")
    print("-" * 60)

    try:
        from app.modules.auth import get_keycloak_config
        import requests

        config = get_keycloak_config()

        # 構建用戶列表 URL
        users_url = f"{config.server_url}/{config.realm}/protocol/openid-connect/userinfo"

        print(f"   測試用戶端點")

        # 注意：這需要有效的 access token
        # 我們只能測試端點是否存在，不能實際獲取用戶列表

        try:
            # 測試管理端點（需要 admin 認證）
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

                # 使用 token 獲取用戶列表
                users_url = f"http://localhost:8080/admin/realms/{config.realm}/users"
                headers = {"Authorization": f"Bearer {access_token}"}

                response = requests.get(users_url, headers=headers, timeout=5)
                response.raise_for_status()

                users = response.json()
                print(f"   ✅ 找到 {len(users)} 個用戶")

                for user in users[:5]:  # 只顯示前 5 個
                    username = user.get('username', 'N/A')
                    email = user.get('email', 'N/A')
                    enabled = user.get('enabled', False)
                    print(f"   - {username} ({email}) - {'啟用' if enabled else '禁用'}")

                return True
            else:
                print(f"   ⚠️  無法獲取 admin token")
                print(f"   - 狀態碼: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"   ❌ 用戶端點測試失敗: {e}")
            return False

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """執行所有 Keycloak 集成測試"""
    print("=" * 60)
    print("🧪 Keycloak 集成測試")
    print("=" * 60)

    results = []

    # 運行所有測試
    results.append(("Keycloak 配置", test_keycloak_config()))
    results.append(("OAuth2 端點", test_oauth_endpoints()))
    results.append(("JWKS 端點", test_jwks_endpoint()))
    results.append(("OpenID 配置", test_openid_configuration()))
    results.append(("Keycloak 用戶", test_keycloak_users()))

    # 總結
    print("\n" + "=" * 60)
    print("📊 測試總結")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}  {test_name}")

    print()
    print(f"通過率: {passed}/{total} ({passed * 100 // total if total > 0 else 0}%)")

    if passed == total:
        print("\n🎉 所有測試通過！Keycloak 配置成功。")
        print("\n📝 測試帳號：")
        print("   - Admin: admin / admin123")
        print("   - User: testuser / test123")
        print("\n🔗 Keycloak Admin Console:")
        print("   - URL: http://localhost:8080/admin")
        print("   - Realm: aileron")
        print("\n✅ 可以開始測試完整的 OAuth2 流程！")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤訊息。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
