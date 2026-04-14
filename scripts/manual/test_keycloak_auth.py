"""
Keycloak 認證全面測試腳本
使用 Playwright 測試前端應用的 Keycloak OAuth2/OIDC 認證流程
"""

from playwright.sync_api import sync_playwright, Page, Browser
import time
import json
from pathlib import Path

# 測試配置
FRONTEND_URL = "http://localhost:8082"
KEYCLOAK_URL = "http://localhost:8080"
TEST_EMAIL = "admin@aileron.com"
TEST_PASSWORD = "admin"  # 根據實際配置調整

def test_login_page_load(page: Page):
    """測試 1: 登入頁面載入"""
    print("\n🧪 測試 1: 登入頁面載入")

    page.goto(FRONTEND_URL)
    page.wait_for_load_state("networkidle")

    # 檢查是否重定向到登入頁面
    current_url = page.url
    print(f"   當前 URL: {current_url}")

    # 截圖
    screenshot_path = "/tmp/test_01_login_page.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"   ✅ 截圖已保存: {screenshot_path}")

    # 檢查頁面元素
    title = page.title()
    print(f"   頁面標題: {title}")

    # 檢查是否有 Keycloak 登入按鈕
    keycloak_button = page.locator('text=/Keycloak|登入/i').first
    if keycloak_button.is_visible():
        print("   ✅ Keycloak 登入按鈕可見")
    else:
        print("   ⚠️  Keycloak 登入按鈕不可見")

    # 檢查 DOM 結構
    content = page.content()
    if "Keycloak" in content or "登入" in content:
        print("   ✅ 頁面包含認證相關內容")

    return True

def test_no_local_login_form(page: Page):
    """測試 2: 確認本機登入表單已移除"""
    print("\n🧪 測試 2: 確認本機登入表單已移除")

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 檢查是否沒有密碼輸入框
    password_inputs = page.locator('input[type="password"]').count()
    print(f"   密碼輸入框數量: {password_inputs}")

    if password_inputs == 0:
        print("   ✅ 本機登入表單已移除（無密碼輸入框）")
    else:
        print("   ⚠️  仍然存在密碼輸入框")

    # 檢查是否沒有註冊鏈接
    register_links = page.locator('a[href*="register"]').count()
    print(f"   註冊鏈接數量: {register_links}")

    if register_links == 0:
        print("   ✅ 註冊鏈接已移除")
    else:
        print("   ⚠️  仍然存在註冊鏈接")

    screenshot_path = "/tmp/test_02_no_local_auth.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"   ✅ 截圖已保存: {screenshot_path}")

    return password_inputs == 0 and register_links == 0

def test_keycloak_button_visible(page: Page):
    """測試 3: Keycloak 登入按鈕可見且可點擊"""
    print("\n🧪 測試 3: Keycloak 登入按鈕")

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 查找 Keycloak 登入按鈕
    selectors = [
        'button:has-text("Keycloak")',
        'button:has-text("登入")',
        'text=/使用.*登入/i',
    ]

    button_found = False
    for selector in selectors:
        try:
            button = page.locator(selector).first
            if button.is_visible(timeout=5000):
                print(f"   ✅ 找到按鈕: {selector}")
                button_found = True

                # 獲取按鈕文本
                button_text = button.text_content()
                print(f"   按鈕文本: {button_text}")

                screenshot_path = "/tmp/test_03_keycloak_button.png"
                page.screenshot(path=screenshot_path)
                print(f"   ✅ 截圖已保存: {screenshot_path}")
                break
        except Exception as e:
            continue

    if not button_found:
        print("   ⚠️  未找到 Keycloak 登入按鈕")
        # 截取整個頁面用於調試
        page.screenshot(path="/tmp/test_03_debug.png", full_page=True)
        print("   📸 調試截圖已保存")

    return button_found

def test_authentication_disabled_message(page: Page):
    """測試 4: 認證未啟用時的警告訊息"""
    print("\n🧪 測試 4: 認證狀態檢查")

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 檢查頁面內容
    content = page.content()

    # 檢查是否有認證相關訊息
    has_auth_enabled = "Keycloak" in content or "使用 Keycloak" in content
    has_auth_disabled = "認證未啟用" in content or "未配置" in content

    if has_auth_enabled:
        print("   ✅ 頁面顯示 Keycloak 認證已啟用")
    elif has_auth_disabled:
        print("   ⚠️  頁面顯示認證未啟用")
    else:
        print("   ℹ️  頁面認證狀態不明")

    # 獲取所有文本內容
    body_text = page.locator('body').text_content()
    print(f"   頁面主要文本: {body_text[:200]}...")

    return has_auth_enabled

def test_console_logs(page: Page):
    """測試 5: 檢查控制台日誌"""
    print("\n🧪 測試 5: 控制台日誌檢查")

    # 收集控制台日誌
    console_messages = []

    def on_console(msg):
        console_messages.append({
            'type': msg.type,
            'text': msg.text,
        })

    page.on('console', on_console)

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 等待一下以收集更多日誌
    time.sleep(2)

    if console_messages:
        print(f"   收集到 {len(console_messages)} 條控制台訊息")

        # 分類統計
        errors = [m for m in console_messages if m['type'] == 'error']
        warnings = [m for m in console_messages if m['type'] == 'warning']

        print(f"   錯誤: {len(errors)}")
        print(f"   警告: {len(warnings)}")

        if errors:
            print("\n   ❌ 錯誤訊息:")
            for err in errors[:5]:  # 只顯示前 5 個
                print(f"      - {err['text'][:100]}")

        if warnings:
            print("\n   ⚠️  警告訊息:")
            for warn in warnings[:5]:  # 只顯示前 5 個
                print(f"      - {warn['text'][:100]}")
    else:
        print("   ✅ 無控制台訊息")

    return len(console_messages) == 0 or len([m for m in console_messages if m['type'] == 'error']) == 0

def test_responsive_design(page: Page):
    """測試 6: 響應式設計"""
    print("\n🧪 測試 6: 響應式設計")

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 測試不同視口大小
    viewports = [
        {'width': 1920, 'height': 1080, 'name': 'Desktop'},
        {'width': 768, 'height': 1024, 'name': 'Tablet'},
        {'width': 375, 'height': 667, 'name': 'Mobile'},
    ]

    for vp in viewports:
        page.set_viewport_size({'width': vp['width'], 'height': vp['height']})
        page.wait_for_timeout(500)

        screenshot_path = f"/tmp/test_06_{vp['name'].lower()}.png"
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"   ✅ {vp['name']} ({vp['width']}x{vp['height']}): {screenshot_path}")

    return True

def test_network_requests(page: Page):
    """測試 7: 網絡請求檢查"""
    print("\n🧪 測試 7: 網絡請求檢查")

    # 收集網絡請求
    requests = []

    def on_request(request):
        requests.append({
            'url': request.url,
            'method': request.method,
            'resource_type': request.resource_type,
        })

    page.on('request', on_request)

    page.goto(f"{FRONTEND_URL}/login")
    page.wait_for_load_state("networkidle")

    # 過濾 API 請求
    api_requests = [r for r in requests if '/api/' in r['url']]

    print(f"   總請求數: {len(requests)}")
    print(f"   API 請求數: {len(api_requests)}")

    if api_requests:
        print("\n   API 請求:")
        for req in api_requests[:10]:
            print(f"      - {req['method']} {req['url'][:80]}")

    # 檢查是否有本機認證的 API 請求
    local_auth_requests = [r for r in api_requests if '/auth/login' in r['url'] or '/auth/register' in r['url']]

    if local_auth_requests:
        print(f"\n   ⚠️  發現本機認證請求: {len(local_auth_requests)}")
        for req in local_auth_requests:
            print(f"      - {req['url']}")
    else:
        print("\n   ✅ 無本機認證 API 請求（符合預期）")

    return len(local_auth_requests) == 0

def run_all_tests():
    """執行所有測試"""
    print("=" * 80)
    print("🚀 開始 Keycloak 認證全面測試")
    print("=" * 80)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # 使用 headless=False 以便觀察

        try:
            page = browser.new_page()

            # 執行測試
            tests = [
                ("登入頁面載入", test_login_page_load),
                ("本機登入表單已移除", test_no_local_login_form),
                ("Keycloak 按鈕可見", test_keycloak_button_visible),
                ("認證狀態檢查", test_authentication_disabled_message),
                ("控制台日誌檢查", test_console_logs),
                ("響應式設計", test_responsive_design),
                ("網絡請求檢查", test_network_requests),
            ]

            for test_name, test_func in tests:
                try:
                    result = test_func(page)
                    results.append((test_name, result, None))
                    print(f"\n{'='*60}")
                except Exception as e:
                    results.append((test_name, False, str(e)))
                    print(f"\n❌ 測試失敗: {e}")
                    print(f"{'='*60}")

                # 重新載入頁面以進行下一個測試
                page.goto("about:blank")
                time.sleep(0.5)

            browser.close()

        except Exception as e:
            print(f"\n❌ 測試過程發生錯誤: {e}")
            browser.close()

    # 生成測試報告
    print("\n" + "=" * 80)
    print("📊 測試報告")
    print("=" * 80)

    passed = sum(1 for _, result, _ in results if result)
    failed = len(results) - passed

    for test_name, result, error in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if error:
            print(f"   錯誤: {error[:100]}")

    print("\n" + "-" * 80)
    print(f"總計: {len(results)} 個測試")
    print(f"通過: {passed}")
    print(f"失敗: {failed}")
    print(f"通過率: {passed/len(results)*100:.1f}%")
    print("=" * 80)

    # 保存測試報告到文件
    report_path = "/tmp/test_report.txt"
    with open(report_path, 'w') as f:
        f.write("Keycloak 認證測試報告\n")
        f.write("=" * 80 + "\n\n")
        for test_name, result, error in results:
            status = "PASS" if result else "FAIL"
            f.write(f"{status} - {test_name}\n")
            if error:
                f.write(f"  錯誤: {error}\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write(f"總計: {len(results)} | 通過: {passed} | 失敗: {failed}\n")

    print(f"\n📄 測試報告已保存: {report_path}")

    return passed == len(results)

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
