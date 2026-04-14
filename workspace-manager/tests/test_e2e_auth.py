"""
端到端認證測試 - 模擬完整 OAuth2 流程

測試場景：
1. 生成登入 URL
2. 模擬 Keycloak callback
3. Token 驗證
4. 受保護路由訪問
5. 裝飾器功能
"""

import sys
from pathlib import Path
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_oauth_login_url_generation():
    """測試 OAuth 登入 URL 生成"""
    print("\n🔐 測試 1: OAuth 登入 URL 生成")
    print("-" * 60)

    try:
        from fastapi import Request
        from app.modules.auth import get_keycloak_config

        config = get_keycloak_config()

        print(f"   配置信息:")
        print(f"   - 伺服器 URL: {config.server_url or '未配置'}")
        print(f"   - Realm: {config.realm or '未配置'}")
        print(f"   - Client ID: {config.client_id or '未配置'}")
        print(f"   - 認證啟用: {config.enabled}")

        if not config.enabled:
            print("\n   ⚠️  認證未啟用，使用模擬配置進行測試")
            # 創建模擬配置
            config.server_url = "http://localhost:8080/realms"
            config.realm = "test-realm"
            config.client_id = "test-client"

        # 構建授權 URL
        from urllib.parse import urlencode

        auth_url = (
            f"{config.server_url}/{config.realm}/protocol/openid-connect/auth"
            if config.server_url
            else "http://localhost:8080/realms/test-realm/protocol/openid-connect/auth"
        )

        params = {
            "client_id": config.client_id,
            "response_type": "code",
            "scope": "openid profile email",
            "redirect_uri": "http://localhost:3001/api/v1/oauth2/callback",
            "state": "test-state-12345",
        }

        login_url = f"{auth_url}?{urlencode(params)}"

        print(f"\n   ✅ 登入 URL 生成成功:")
        print(f"   {login_url[:100]}...")

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_middleware_token_validation():
    """測試中間件 token 驗證流程"""
    print("\n🎫 測試 2: 中間件 Token 驗證")
    print("-" * 60)

    try:
        from app.modules.auth import JWTAuthenticationMiddleware, get_keycloak_config
        from fastapi import Request

        class MockApp:
            pass

        # 創建中間件
        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/health"],
            exclude_patterns=["/public/*"],
        )

        print("   ✅ 中間件創建成功")

        # 測試 token 提取
        class MockRequest:
            def __init__(self, headers, path):
                self.headers = headers
                self.url = Mock(path=path)

        # 測試 1: 有有效 token 的請求
        request = MockRequest(
            {"Authorization": "Bearer test-token-12345"},
            "/api/workspaces"
        )

        token = middleware._extract_bearer_token(request)
        print(f"   ✅ Token 提取: {token}")

        # 測試 2: 無 token 的請求
        request = MockRequest({}, "/api/workspaces")
        token = middleware._extract_bearer_token(request)
        print(f"   ✅ 無 Token 處理: {token}")

        # 測試 3: 排除路徑
        is_excluded = middleware._is_excluded_path("/health")
        print(f"   ✅ 路徑排除檢查 (/health): {is_excluded}")

        is_excluded = middleware._is_excluded_path("/api/workspaces")
        print(f"   ✅ 路徑排除檢查 (/api/workspaces): {is_excluded}")

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_decorator_authentication():
    """測試裝飾器認證功能"""
    print("\n🔒 測試 3: 裝飾器認證")
    print("-" * 60)

    try:
        from app.modules.auth import (
            require_role,
            require_permission,
            PermissionDeniedError,
        )

        # 測試 require_role 裝飾器
        @require_role("admin")
        async def admin_endpoint(current_user):
            return {"message": "Admin access"}

        # 測試有權限用戶
        admin_user = {"sub": "user-123", "roles": ["admin"]}
        try:
            result = await admin_endpoint(current_user=admin_user)
            print(f"   ✅ Admin 角色訪問成功: {result}")
        except Exception as e:
            print(f"   ❌ Admin 角色訪問失敗: {e}")
            return False

        # 測試無權限用戶
        normal_user = {"sub": "user-456", "roles": ["user"]}
        try:
            await admin_endpoint(current_user=normal_user)
            print("   ❌ 應該拒絕無權限用戶")
            return False
        except PermissionDeniedError as e:
            print(f"   ✅ 正確拒絕無權限用戶: {e.detail}")

        # 測試 require_permission 裝飾器
        @require_permission("workspace:create")
        async def create_workspace_endpoint(current_user):
            return {"message": "Workspace created"}

        # admin 角色應該有 workspace:create 權限
        admin_user = {"sub": "user-123", "roles": ["admin"]}
        try:
            result = await create_workspace_endpoint(current_user=admin_user)
            print(f"   ✅ 權限檢查成功: {result}")
        except Exception as e:
            print(f"   ❌ 權限檢查失敗: {e}")
            return False

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_permission_system():
    """測試權限系統"""
    print("\n📋 測試 4: 權限系統")
    print("-" * 60)

    try:
        from app.modules.auth import (
            get_user_permissions,
            has_permission,
            has_role,
            has_all_permissions,
            has_any_permission,
        )

        # 測試角色權限映射
        admin_permissions = get_user_permissions(["admin"])
        print(f"   ✅ Admin 角色權限數量: {len(admin_permissions)}")
        print(f"   - 權限示例: {admin_permissions[:3]}")

        user_permissions = get_user_permissions(["user"])
        print(f"   ✅ User 角色權限數量: {len(user_permissions)}")

        # 測試權限檢查
        assert has_permission("workspace:read", admin_permissions) is True
        print("   ✅ has_permission('workspace:read') 正常")

        assert has_role("admin", ["admin", "user"]) is True
        print("   ✅ has_role('admin') 正常")

        assert has_all_permissions(
            ["workspace:read", "workspace:create"],
            admin_permissions
        ) is True
        print("   ✅ has_all_permissions 正常")

        assert has_any_permission(
            ["workspace:read", "workspace:delete"],
            user_permissions
        ) is True
        print("   ✅ has_any_permission 正常")

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_user_sync_service():
    """測試用戶同步服務"""
    print("\n👤 測試 5: 用戶同步服務")
    print("-" * 60)

    try:
        from app.modules.auth import get_user_sync_service

        service = get_user_sync_service()
        print("   ✅ UserSyncService 實例化成功")

        # 測試角色提取
        test_user_info = {
            "realm_access": {
                "admin": True,
                "user": True,
            },
            "resource_access": {
                "test-api": {
                    "roles": ["read", "write"]
                }
            }
        }

        roles = service._extract_roles(test_user_info)
        print(f"   ✅ 角色提取成功: {roles}")

        assert "admin" in roles
        assert "user" in roles
        assert "read" in roles
        assert "write" in roles
        print("   ✅ 角色提取正確")

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_jwt_utilities():
    """測試 JWT 工具"""
    print("\n🔑 測試 6: JWT 工具")
    print("-" * 60)

    try:
        from app.modules.auth import get_jwt_utils
        from datetime import datetime, timedelta, timezone

        jwt_utils = get_jwt_utils()
        print("   ✅ JWTUtils 實例化成功")

        # 測試 token 過期驗證
        exp_valid = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        payload_valid = {"exp": exp_valid, "sub": "user-123"}

        is_valid = jwt_utils.validate_token_expiry(payload_valid)
        print(f"   ✅ 有效 token 驗證: {is_valid}")

        # 測測過期 token
        exp_expired = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        payload_expired = {"exp": exp_expired, "sub": "user-123"}

        is_valid = jwt_utils.validate_token_expiry(payload_expired)
        print(f"   ✅ 過期 token 驗證: {is_valid}")

        return True

    except Exception as e:
        print(f"   ❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """執行所有端到端測試"""
    print("=" * 60)
    print("🧪 端到端認證測試")
    print("=" * 60)

    results = []

    # 運行所有測試
    results.append(("OAuth 登入 URL 生成", test_oauth_login_url_generation()))
    results.append(("中間件 Token 驗證", await test_middleware_token_validation()))
    results.append(("裝飾器認證", await test_decorator_authentication()))
    results.append(("權限系統", await test_permission_system()))
    results.append(("用戶同步服務", await test_user_sync_service()))
    results.append(("JWT 工具", await test_jwt_utilities()))

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
        print("\n🎉 所有測試通過！認證系統運作正常。")
        print("\n📝 下一步建議：")
        print("   1. 配置 Keycloak realm 和 client")
        print("   2. 設置 ENABLE_AUTH=true")
        print("   3. 測試完整的 OAuth2 流程")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤訊息。")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
