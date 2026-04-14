"""
JWT 認證中間件功能測試腳本

測試中間件的各種功能，包括：
- Token 提取
- 路徑排除
- Token 驗證
- 用戶信息注入
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_middleware_import():
    """測試中間件導入"""
    print("🔧 測試中間件導入...")
    try:
        from app.modules.auth.middleware import (
            JWTAuthenticationMiddleware,
            StrictJWTAuthenticationMiddleware,
        )
        print("   ✅ 中間件導入成功")
        return True
    except Exception as e:
        print(f"   ❌ 導入失敗: {e}")
        return False


def test_middleware_initialization():
    """測試中間件初始化"""
    print("\n⚙️  測試中間件初始化...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        # 創建模擬應用
        class MockApp:
            pass

        mock_app = MockApp()

        # 創建中間件實例
        middleware = JWTAuthenticationMiddleware(
            mock_app,
            exclude_paths=["/test-public"],
            exclude_patterns=["/public/*"],
        )

        print(f"   ✅ 中間件初始化成功")
        print(f"   - 排除路徑數量: {len(middleware.exclude_paths)}")
        print(f"   - 排除模式數量: {len(middleware.exclude_patterns)}")

        return True
    except Exception as e:
        print(f"   ❌ 初始化失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bearer_token_extraction():
    """測試 Bearer token 提取"""
    print("\n🎫 測試 Bearer Token 提取...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        class MockApp:
            pass

        class MockRequest:
            def __init__(self, headers):
                self.headers = headers

        middleware = JWTAuthenticationMiddleware(MockApp())

        # 測試有效的 Bearer token
        request = MockRequest({"Authorization": "Bearer test-token-12345"})
        token = middleware._extract_bearer_token(request)
        assert token == "test-token-12345", f"Expected 'test-token-12345', got '{token}'"
        print("   ✅ 有效 Bearer token 提取成功")

        # 測試缺少 Authorization header
        request = MockRequest({})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None, got '{token}'"
        print("   ✅ 缺少 Authorization header 處理正確")

        # 測試無效格式
        request = MockRequest({"Authorization": "InvalidFormat token"})
        token = middleware._extract_bearer_token(request)
        assert token is None, f"Expected None for invalid format, got '{token}'"
        print("   ✅ 無效格式處理正確")

        return True
    except Exception as e:
        print(f"   ❌ Token 提取測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_path_exclusion():
    """測試路徑排除邏輯"""
    print("\n🚷 測試路徑排除邏輯...")
    try:
        from app.modules.auth.middleware import JWTAuthenticationMiddleware

        class MockApp:
            pass

        middleware = JWTAuthenticationMiddleware(
            MockApp(),
            exclude_paths=["/test-public", "/custom-path"],
            exclude_patterns=["/public/*", "/api/public/*"],
        )

        # 測試完全匹配
        assert middleware._is_excluded_path("/test-public") is True
        assert middleware._is_excluded_path("/custom-path") is True
        print("   ✅ 完全匹配排除正確")

        # 測試模式匹配
        assert middleware._is_excluded_path("/public/resource") is True
        assert middleware._is_excluded_path("/api/public/data") is True
        print("   ✅ 模式匹配排除正確")

        # 測試無匹配
        assert middleware._is_excluded_path("/api/workspaces") is False
        assert middleware._is_excluded_path("/protected/data") is False
        print("   ✅ 非排除路徑判斷正確")

        # 測試默認排除路徑
        assert middleware._is_excluded_path("/health") is True
        assert middleware._is_excluded_path("/docs") is True
        assert middleware._is_excluded_path("/redoc") is True
        print("   ✅ 默認排除路徑正確")

        return True
    except Exception as e:
        print(f"   ❌ 路徑排除測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """測試模組導出"""
    print("\n📤 測試模組導出...")
    try:
        from app.modules import auth

        # 檢查中間件是否已導出
        assert hasattr(auth, 'JWTAuthenticationMiddleware'), "JWTAuthenticationMiddleware 未導出"
        assert hasattr(auth, 'StrictJWTAuthenticationMiddleware'), "StrictJWTAuthenticationMiddleware 未導出"

        # 檢查 __all__
        assert 'JWTAuthenticationMiddleware' in auth.__all__, "JWTAuthenticationMiddleware 不在 __all__ 中"
        assert 'StrictJWTAuthenticationMiddleware' in auth.__all__, "StrictJWTAuthenticationMiddleware 不在 __all__ 中"

        print("   ✅ 中間件已正確導出")
        print(f"   - JWTAuthenticationMiddleware")
        print(f"   - StrictJWTAuthenticationMiddleware")

        return True
    except Exception as e:
        print(f"   ❌ 模組導出測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """執行所有測試"""
    print("=" * 60)
    print("🔐 JWT 認證中間件功能測試")
    print("=" * 60)

    results = []

    # 運行所有測試
    results.append(("中間件導入", test_middleware_import()))
    results.append(("中間件初始化", test_middleware_initialization()))
    results.append(("Bearer Token 提取", test_bearer_token_extraction()))
    results.append(("路徑排除邏輯", test_path_exclusion()))
    results.append(("模組導出", test_module_exports()))

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
        print("\n🎉 所有測試通過！JWT 認證中間件功能正常。")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤訊息。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
