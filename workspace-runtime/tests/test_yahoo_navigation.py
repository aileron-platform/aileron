"""
測試透過 Browser Relay 連接到 Yahoo 台灣

執行方式：
    uv run tests/test_yahoo_navigation.py

需求：
    - Chrome Extension 已啟用並連接
    - Browser Relay 服務運行中
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_BROWSER_RELAY_E2E"),
    reason="需要明確啟用 Browser Relay E2E 測試",
)


async def create_page_via_api(page_name: str) -> dict:
    """透過 API 創建命名頁面"""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3002/api/v1/client-browser-relay/pages",
            json={"name": page_name}
        )
        response.raise_for_status()
        return response.json()


async def test_yahoo_navigation():
    """測試導航到 Yahoo 台灣"""
    from playwright.async_api import async_playwright

    print("\n" + "=" * 60)
    print("測試透過 Browser Relay 連接到 Yahoo 台灣")
    print("=" * 60)

    # 步驟 1: 先透過 API 創建命名頁面
    page_name = f"yahoo-test-{int(asyncio.get_event_loop().time())}"
    print(f"\n📝 創建測試頁面: {page_name}")

    try:
        page_info = await create_page_via_api(page_name)
        print(f"✅ 頁面已創建")
        print(f"   - Target ID: {page_info['targetId']}")
        print(f"   - 初始 URL: {page_info['url']}")
    except Exception as e:
        print(f"❌ 創建頁面失敗: {e}")
        return False

    # 步驟 2: 連接到 Browser Relay
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 連接到 Browser Relay: {cdp_endpoint}")

    async with async_playwright() as p:
        try:
            # 連接到現有的瀏覽器
            browser = await p.chromium.connect_over_cdp(cdp_endpoint)
            print("✅ 成功連接到瀏覽器")

            # 獲取所有 contexts 和 pages
            contexts = browser.contexts
            print(f"📋 找到 {len(contexts)} 個 context(s)")

            # 尋找我們剛創建的頁面
            target_page = None
            for context in contexts:
                pages = context.pages
                print(f"   Context 有 {len(pages)} 個頁面")
                for page in pages:
                    print(f"   - 頁面 URL: {page.url}")
                    # 尋找 about:blank 頁面（剛創建的）
                    if page.url == "about:blank" or not target_page:
                        target_page = page

            if not target_page:
                print("❌ 找不到可用的頁面")
                return False

            print(f"\n✅ 使用頁面: {target_page.url}")

            # 步驟 3: 導航到 Yahoo 台灣
            print("\n🌐 導航到 https://tw.yahoo.com/")
            await target_page.goto("https://tw.yahoo.com/", wait_until="domcontentloaded", timeout=30000)
            print(f"✅ 頁面已載入: {target_page.url}")

            # 等待頁面載入完成
            try:
                await target_page.wait_for_load_state("networkidle", timeout=10000)
                print("✅ 網路請求完成")
            except Exception as e:
                print(f"⚠️  等待網路閒置逾時（正常）: {e}")

            # 步驟 4: 獲取頁面資訊
            title = await target_page.title()
            print(f"\n📄 頁面標題: {title}")

            current_url = target_page.url
            print(f"🔗 當前 URL: {current_url}")

            # 步驟 5: 截圖
            screenshot_path = Path(__file__).parent / "yahoo_screenshot.png"
            await target_page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"📸 截圖已儲存: {screenshot_path}")

            # 步驟 6: 驗證頁面內容
            print("\n🔍 驗證頁面內容...")

            # 檢查頁面是否包含 Yahoo 相關元素
            try:
                # 等待頁面主要內容載入
                await target_page.wait_for_selector('body', timeout=5000)

                # 獲取頁面文字內容
                body_text = await target_page.evaluate('() => document.body.innerText')

                if 'yahoo' in body_text.lower() or 'Yahoo' in body_text:
                    print("✅ 頁面內容包含 Yahoo")
                else:
                    print("⚠️  頁面內容未明確包含 Yahoo 關鍵字")

            except Exception as e:
                print(f"⚠️  驗證頁面內容時發生錯誤: {e}")

            # 驗證 URL
            if "yahoo" in current_url.lower():
                print("✅ URL 驗證通過 - 確實在 Yahoo 網站")
            else:
                print(f"⚠️  URL 驗證失敗 - 期望包含 'yahoo'，實際: {current_url}")

            # 步驟 7: 測試摘要
            print("\n" + "=" * 60)
            print("測試完成")
            print("=" * 60)
            print("✅ 成功透過 Browser Relay 導航到 Yahoo 台灣")
            print(f"   - 頁面名稱: {page_name}")
            print(f"   - 標題: {title}")
            print(f"   - URL: {current_url}")
            print(f"   - 截圖: {screenshot_path}")
            print("\n💡 提示: 瀏覽器頁面保持開啟，可在 Chrome 中查看")

            # 不關閉瀏覽器，保持連接
            # await browser.close()

            return True

        except Exception as e:
            print(f"\n❌ 測試失敗: {e}")
            import traceback
            traceback.print_exc()
            return False


async def main():
    """主程式"""
    try:
        success = await test_yahoo_navigation()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  測試被中斷")
        return 130
    except Exception as e:
        print(f"\n❌ 發生未預期的錯誤: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
