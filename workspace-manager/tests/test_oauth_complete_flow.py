#!/usr/bin/env python3
"""
從容器內部測試完整的 OAuth2 流程
使用 Docker 網絡通信（HTTP），避免 HTTPS 要求
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import requests
import json
import os

def main():
    print("=" * 70)
    print("🔑 Keycloak OAuth2 完整流程測試")
    print("=" * 70)

    # 配置
    KEYCLOAK_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://aileron-keycloak-dev:8080")
    REALM = os.getenv("KEYCLOAK_REALM", "aileron")
    CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "workspace-manager")
    CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "workspace-manager-secret-12345")

    print(f"\n配置信息：")
    print(f"  Keycloak URL: {KEYCLOAK_URL}")
    print(f"  Realm: {REALM}")
    print(f"  Client ID: {CLIENT_ID}")

    # 步驟 1: 獲取 Admin Token
    print("\n" + "=" * 70)
    print("步驟 1: 獲取 Admin Token")
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
        print("\n正在請求 token...")
        response = requests.post(token_url, data=token_data, timeout=10)
        print(f"狀態碼: {response.status_code}")

        if response.status_code == 200:
            token_response = response.json()
            access_token = token_response.get("access_token")

            print(f"\n✅ Token 獲取成功！")
            print(f"Token 類型: {token_response.get('token_type')}")
            print(f"Token 長度: {len(access_token)} 字符")
            print(f"過期時間: {token_response.get('expires_in')} 秒")

            # 解碼 JWT 查看內容
            import base64
            parts = access_token.split('.')
            if len(parts) == 3:
                payload = parts[1]
                payload += '=' * (4 - len(payload) % 4)
                decoded = base64.b64decode(payload)
                claims = json.loads(decoded)
                print(f"\n📋 Token Payload:")
                print(f"  用戶名: {claims.get('preferred_username')}")
                print(f"  Email: {claims.get('email')}")
                print(f"  角色: {claims.get('realm_access', {}).get('roles', [])}")

        else:
            print(f"\n❌ Token 獲取失敗")
            print(f"響應: {response.text}")
            return False

    except Exception as e:
        print(f"\n❌ 請求失敗: {e}")
        print(f"\n💡 提示: 確保 Keycloak 容器正在運行")
        print(f"   檢查命令: docker ps | grep keycloak")
        return False

    # 步驟 2: 測試受保護的 API 端點
    print("\n" + "=" * 70)
    print("步驟 2: 測試受保護的 API 端點")
    print("=" * 70)

    # 測試 2.1: 獲取當前用戶信息
    print("\n測試 2.1: GET /api/v1/oauth2/me")
    print("-" * 70)

    me_url = "http://localhost:3001/api/v1/oauth2/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        response = requests.get(me_url, headers=headers, timeout=5)
        print(f"狀態碼: {response.status_code}")

        if response.status_code == 200:
            user_info = response.json()
            print(f"✅ 成功獲取用戶信息！\n")
            print("用戶信息:")
            print(json.dumps(user_info, indent=2, ensure_ascii=False))
        else:
            print(f"❌ 請求失敗")
            print(f"響應: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 請求失敗: {e}")
        print(f"\n💡 提示: 確保 workspace-manager 服務正在運行")
        return False

    # 測試 2.2: 測試沒有 token 的請求
    print("\n測試 2.2: 測試沒有 token 的請求（應該返回 401）")
    print("-" * 70)

    try:
        response = requests.get(me_url, timeout=5)
        print(f"狀態碼: {response.status_code}")

        if response.status_code == 401:
            error_info = response.json()
            print(f"✅ 正確拒絕未認證請求！\n")
            print("錯誤信息:")
            print(json.dumps(error_info, indent=2, ensure_ascii=False))
        else:
            print(f"⚠️  意外的狀態碼: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ 請求失敗: {e}")
        return False

    # 總結
    print("\n" + "=" * 70)
    print("✅ 測試完成！認證系統正常工作！")
    print("=" * 70)

    print("\n📝 測試結果：")
    print("   ✅ Keycloak Token 獲取成功")
    print("   ✅ JWT Token 驗證成功")
    print("   ✅ 受保護 API 端點正常工作")
    print("   ✅ 中間件正確攔截未認證請求")
    print("   ✅ 用戶信息正確提取")

    print("\n🔗 測試帳號：")
    print("   - Admin: admin / admin123 (角色: admin)")
    print("   - User: testuser / test123 (角色: user)")

    print("\n🚀 認證系統已就緒，可以開始使用！")
    print("\n💡 下一步：")
    print("   1. 在瀏覽器中測試 OAuth2 登入流程")
    print("   2. 實施前端集成")
    print("   3. 實施 Workspace Runtime 的 token 驗證")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
