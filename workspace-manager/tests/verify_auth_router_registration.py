"""
驗證 Keycloak Auth Router 註冊測試腳本

檢查：
1. Keycloak auth router 導入是否成功
2. Router 是否正確註冊到主應用
3. 路由端點是否可用
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_keycloak_auth_module_import():
    """測試 Keycloak auth 模組導入"""
    print("📦 測試 1: Keycloak Auth 模組導入")
    print("-" * 60)

    try:
        from app.modules.auth import auth_router as keycloak_auth_router
        print("✅ Keycloak auth router 導入成功")
        print(f"   Router 類型: {type(keycloak_auth_router)}")
        print(f"   Router 前綴: {keycloak_auth_router.prefix}")
        print(f"   Router 標籤: {keycloak_auth_router.tags}")
        return keycloak_auth_router
    except Exception as e:
        print(f"❌ 導入失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_keycloak_auth_routes(router):
    """測試 Keycloak auth 路由端點"""
    print("\n🛣️  測試 2: Keycloak Auth 路由端點")
    print("-" * 60)

    if not router:
        print("❌ Router 為 None，跳過測試")
        return False

    try:
        routes = router.routes
        print(f"✅ 找到 {len(routes)} 個路由端點：\n")

        for route in routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                methods = list(route.methods) if route.methods else []
                print(f"   • {', '.join(methods):<8} {route.path}")
            elif hasattr(route, 'path'):
                print(f"   • {route.path}")

        # 驗證關鍵端點
        route_paths = [route.path for route in routes if hasattr(route, 'path')]
        key_endpoints = [
            '/oauth2/login',
            '/oauth2/callback',
            '/oauth2/refresh',
            '/oauth2/logout',
            '/oauth2/me',
            '/oauth2/config',
        ]

        print("\n🔍 驗證關鍵端點：")
        all_present = True
        for endpoint in key_endpoints:
            present = endpoint in route_paths
            status = "✅" if present else "❌"
            print(f"   {status} {endpoint}")
            if not present:
                all_present = False

        return all_present

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_app_import():
    """測試主應用導入（驗證沒有循環導入）"""
    print("\n🚀 測試 3: 主應用導入")
    print("-" * 60)

    try:
        # 延遲導入以避免初始化整個應用
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app.main",
            project_root / "app" / "main.py"
        )

        # 檢查是否可以訪問模組規範
        if spec and spec.loader:
            print("✅ 主應用模組規格載入成功")

            # 檢查 main.py 是否包含 keycloak_auth_router
            main_content = (project_root / "app" / "main.py").read_text()

            if "keycloak_auth_router" in main_content:
                print("✅ 主應用包含 keycloak_auth_router 導入")

                # 統計出現次數
                import_count = main_content.count("keycloak_auth_router")
                print(f"   - 導入語句: {import_count} 處")

                if "app.include_router(keycloak_auth_router" in main_content:
                    print("✅ Keycloak auth router 已註冊到主應用")
                    return True
                else:
                    print("⚠️  Keycloak auth router 未註冊到主應用")
                    return False
            else:
                print("⚠️  主應用不包含 keycloak_auth_router")
                return False
        else:
            print("❌ 無法載入主應用模組規格")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_module_exports():
    """測試模組導出的符號"""
    print("\n📤 測試 4: 模組導出符號")
    print("-" * 60)

    try:
        from app.modules import auth

        # 檢查 __all__ 定義
        if hasattr(auth, '__all__'):
            exports = auth.__all__
            print(f"✅ 模組導出 {len(exports)} 個符號：")

            # 分類導出
            categories = {
                '配置類': [],
                'JWT 工具': [],
                'JWKS 快取': [],
                '路由': [],
                '用戶同步': [],
                '裝飾器': [],
                '其他': [],
            }

            for symbol in exports:
                symbol_lower = symbol.lower()
                if 'config' in symbol_lower:
                    categories['配置類'].append(symbol)
                elif 'jwt' in symbol_lower:
                    categories['JWT 工具'].append(symbol)
                elif 'jwks' in symbol_lower or 'cache' in symbol_lower:
                    categories['JWKS 快取'].append(symbol)
                elif 'router' in symbol_lower:
                    categories['路由'].append(symbol)
                elif 'sync' in symbol_lower or 'user' in symbol_lower:
                    categories['用戶同步'].append(symbol)
                elif 'require' in symbol_lower or 'permission' in symbol_lower:
                    categories['裝飾器'].append(symbol)
                else:
                    categories['其他'].append(symbol)

            for category, symbols in categories.items():
                if symbols:
                    print(f"\n   {category}:")
                    for symbol in symbols:
                        print(f"      • {symbol}")

            return True
        else:
            print("⚠️  模組未定義 __all__")
            return False

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """執行所有測試"""
    print("=" * 60)
    print("🔐 Keycloak Auth Router 註冊驗證")
    print("=" * 60)
    print()

    results = []

    # 測試 1: 模組導入
    router = test_keycloak_auth_module_import()
    results.append(("模組導入", router is not None))

    # 測試 2: 路由端點
    if router:
        routes_ok = test_keycloak_auth_routes(router)
        results.append(("路由端點", routes_ok))

    # 測試 3: 主應用導入
    main_ok = test_main_app_import()
    results.append(("主應用註冊", main_ok))

    # 測試 4: 模組導出
    exports_ok = test_module_exports()
    results.append(("模組導出", exports_ok))

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
        print("\n🎉 所有測試通過！Keycloak auth router 已成功註冊。")
        return 0
    else:
        print("\n⚠️  部分測試失敗，請檢查上述錯誤訊息。")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
