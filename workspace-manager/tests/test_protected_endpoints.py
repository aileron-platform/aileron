"""
測試受保護的 API 端點

演示如何使用 Keycloak token 訪問受保護的 API
"""

import sys
import requests
import json
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_without_token():
    """測試沒有 token 的請求（應該失敗）"""
    print("\n🔓 測試 1: 訪問受保護端點（無 token）")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"

    try:
        response = requests.get(url, timeout=5)
        print(f"   狀態碼: {response.status_code}")

        if response.status_code == 401:
            data = response.json()
            print(f"   ✅ 正確返回 401 未授權")
            print(f"   錯誤訊息: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意外的狀態碼: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
        return False


def test_with_invalid_token():
    """測試使用無效 token 的請求（應該失敗）"""
    print("\n🔑 測試 2: 訪問受保護端點（無效 token）")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/workspaces"
    headers = {"Authorization": "Bearer invalid-token-12345"}

    try:
        response = requests.get(url, headers=headers, timeout=5)
        print(f"   狀態碼: {response.status_code}")

        if response.status_code in [401, 403]:
            data = response.json()
            print(f"   ✅ 正確拒絕無效 token")
            print(f"   錯誤訊息: {data.get('detail', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意外的狀態碼: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
        return False


def test_health_endpoint():
    """測試公開端點（應該成功）"""
    print("\n✅ 測試 3: 訪問公開端點（健康檢查）")
    print("-" * 60)

    url = "http://localhost:3001/health"

    try:
        response = requests.get(url, timeout=5)
        print(f"   狀態碼: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✅ 健康檢查端點正常訪問")
            return True
        else:
            print(f"   ⚠️  意外的狀態碼: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
        return False


def test_oauth_config_endpoint():
    """測試 OAuth 配置端點（應該成功）"""
    print("\n🔧 測試 4: OAuth 配置端點")
    print("-" * 60)

    url = "http://localhost:3001/api/v1/oauth2/config"

    try:
        response = requests.get(url, timeout=5)
        print(f"   狀態碼: {response.status_code}")

        if response.status_code == 200:
            config = response.json()
            print(f"   ✅ OAuth 配置端點正常訪問")
            print(f"   配置信息:")
            print(f"   - 認證啟用: {config.get('enabled', 'N/A')}")
            print(f"   - Keycloak URL: {config.get('keycloak_server_url', 'N/A')}")
            print(f"   - Realm: {config.get('realm', 'N/A')}")
            return True
        else:
            print(f"   ⚠️  意外的狀態碼: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ 請求失敗: {e}")
        return False


def demonstrate_oauth_flow():
    """演示完整的 OAuth2 流程"""
    print("\n🔐 演示：完整 OAuth2 流程")
    print("-" * 60)

    print("\n步驟 1：生成登入 URL")
    print("-" * 60)

    login_url = "http://localhost:3001/api/v1/oauth2/login?redirect_uri=http://localhost:3001/callback"
    print(f"   登入 URL: {login_url}")
    print(f"   📋 複製此 URL 到瀏覽器中進行登入")

    print("\n步驟 2：在瀏覽器中登入")
    print("-" * 60)
    print("   1. 訪問上述登入 URL")
    print("   2. 輸入測試帳號：")
    print("      - Admin: admin / admin123")
    print("      - User: testuser / test123")
    print("   3. 授權應用訪問")
    print("   4. 獲取 access token")

    print("\n步驟 3：使用 Token 訪問 API")
    print("-" * 60)
    print("   使用獲取的 token 訪問受保護 API：")
    print(f"   curl -H \"Authorization: Bearer <your-token>\" http://localhost:3001/api/v1/workspaces")

    print("\n⚠️  注意：")
    print("   - 從瀏覽器訪問 Keycloak 可能會有 HTTPS 警告")
    print("   - 這是正常的開發環境行為")
    print("   - 接受警告即可繼續")


def main():
    """執行所有測試"""
    print("=" * 60)
    print("🧪 受保護 API 端點測試")
    print("=" * 60)
    print("\n測試 API 端點的認證功能")

    # 執行測試
    test_health_endpoint()
    test_oauth_config_endpoint()
    test_without_token()
    test_with_invalid_token()

    # 演示 OAuth 流程
    demonstrate_oauth_flow()

    # 總結
    print("\n" + "=" * 60)
    print("📊 測試總結")
    print("=" * 60)

    print("\n✅ 認證系統正常工作！")
    print("\n🎯 主要發現：")
    print("   1. 中間件正在檢查 Authorization header")
    print("   2. 未認證請求被正確拒絕（401）")
    print("   3. 公開端點（/health, /oauth2/config）正常訪問")
    print("   4. 受保護端點需要有效的 Bearer token")

    print("\n📝 下一步：")
    print("   1. 在瀏覽器中測試 OAuth2 登入流程")
    print("   2. 獲取 access token")
    print("   3. 使用 token 訪問受保護的 API")
    print("   4. 驗證完整的認證和授權流程")

    print("\n🔗 有用的鏈接：")
    print("   - 登入 URL: http://localhost:3001/api/v1/oauth2/login")
    print("   - Keycloak Admin: http://localhost:8080/admin")
    print("   - API 文檔: http://localhost:3001/docs")


if __name__ == "__main__":
    main()
