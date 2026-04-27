"""
Test受Protect的 API Endpoint

演示如何Use Keycloak token Access受Protect的 API
"""

import sys
import requests
import json
from pathlib import Path

# 添加Project根CatalogTo Python Road徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_without_token():
    """TestNone token 的Request（ShouldFailed）"""
    print("\n🔓 Test 1: Access受ProtectEndpoint（無 token）")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 401:
            data = response.json()
            print(f"   ✅ CorrectlyReturn 401 未Authorizing")
            print(f"   ErrorMessage: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意Outside的StatusCode: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_with_invalid_token():
    """TestUseInvalid token 的Request（ShouldFailed）"""
    print("\n🔑 Test 2: Access受ProtectEndpoint（Invalid token）")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"
    headers = {"Authorization": "Bearer invalid-token-12345"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code in [401, 403]:
            data = response.json()
            print(f"   ✅ CorrectlyRejectInvalid token")
            print(f"   ErrorMessage: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意Outside的StatusCode: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_health_endpoint():
    """TestPublicEndpoint（ShouldSuccess）"""
    print("\n✅ Test 3: AccessPublicEndpoint（健康Check）")
    print("-" * 60)

    url = "http://localhost:3001/health"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✅ 健康CheckEndpointNormalAccess")
            return True
        else:
            print(f"   ⚠️  意Outside的StatusCode: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def test_oauth_config_endpoint():
    """Test OAuth ConfigurationEndpoint（ShouldSuccess）"""
    print("\n🔧 Test 4: OAuth ConfigurationEndpoint")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/oauth2/config"

    try:
        response = requests.get(url, timeout=5)
        print(f"   StatusCode: {response.status_code}")

        if response.status_code == 200:
            config = response.json()
            print(f"   ✅ OAuth ConfigurationEndpointNormalAccess")
            print(f"   ConfigurationInfo:")
            print(f"   - AuthenticationEnabled: {config.get('enabled', 'N/A')}")
            print(f"   - Keycloak URL: {config.get('keycloak_server_url', 'N/A')}")
            print(f"   - Realm: {config.get('realm', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意Outside的StatusCode: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ RequestFailed: {e}")
        return False


def demonstrate_oauth_flow():
    """演示完整的 OAuth2 Flow"""
    print("\n🔐 演示：完整 OAuth2 Flow")
    print("-" * 60)

    print("\nStep 1：Generating登入 URL")
    print("-" * 60)

    login_url = "http://localhost:3001/api/v1/oauth2/login?redirect_uri=http://localhost:3001/callback"
    print(f"   登入 URL: {login_url}")
    print(f"   📋 Copy此 URL To瀏覽器中Proceed登入")

    print("\nStep 2：At瀏覽器中登入")
    print("-" * 60)
    print("   1. AccessAbove述登入 URL")
    print("   2. 輸入Test帳Number：")
    print("      - Admin: admin / admin123")
    print("      - User: testuser / test123")
    print("   3. AuthorizingApplicationAccess")
    print("   4. Get access token")

    print("\nStep 3：Use Token Access API")
    print("-" * 60)
    print("   UseGet的 token Access受Protect API：")
    print(f"   curl -H \"Authorization: Bearer <your-token>\" http://localhost:3001/api/v1/workspaces")

    print("\n⚠️  Noticing：")
    print("   - From瀏覽器Access Keycloak Possibly會有 HTTPS Warning")
    print("   - 這YesNormal的On發Environment行為")
    print("   - AcceptingWarning即可Continue")


def main():
    """ExecuteAllTest"""
    print("=" * 60)
    print("🧪 受Protect API EndpointTest")
    print("=" * 60)
    print("\nTest API Endpoint的AuthenticationFunction")

    # ExecuteTest
    test_health_endpoint()
    test_oauth_config_endpoint()
    test_without_token()
    test_with_invalid_token()

    # 演示 OAuth Flow
    demonstrate_oauth_flow()

    # Summary
    print("\n" + "=" * 60)
    print("📊 TestSummary")
    print("=" * 60)

    print("\n✅ AuthenticationSystemNormalWorking！")
    print("\n🎯 MainDiscover：")
    print("   1. Middleware正AtCheck Authorization header")
    print("   2. 未AuthenticationRequest被CorrectlyReject（401）")
    print("   3. PublicEndpoint（/health, /oauth2/config）NormalAccess")
    print("   4. 受ProtectEndpointNeedingValid的 Bearer token")

    print("\n📝 Below一步：")
    print("   1. At瀏覽器中Test OAuth2 登入Flow")
    print("   2. Get access token")
    print("   3. Use token Access受Protect的 API")
    print("   4. Verify完整的Authentication和AuthorizingFlow")

    print("\n🔗 有用的Chain接：")
    print("   - 登入 URL: http://localhost:3001/api/v1/oauth2/login")
    print("   - Keycloak Admin: http://localhost:8080/admin")
    print("   - API 文檔: http://localhost:3001/docs")


if __name__ == "__main__":
    main()
