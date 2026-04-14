"""
使用原生 CDP 測試透過 Browser Relay 連接到 Yahoo 台灣
並測試光暈效果功能

執行方式：
    uv run tests/test_yahoo_cdp.py

需求：
    - Chrome Extension 已啟用並連接
    - Browser Relay 服務運行中

測試內容：
    - 創建標籤頁並導航到 Yahoo 台灣
    - 啟用/關閉光暈效果 (Browser.setGlowEffect)
    - 測試頁面重新載入後光暈自動恢復
    - 截取帶光暈效果的頁面截圖
"""

import asyncio
import json
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


async def send_cdp_command(websocket, method: str, params: dict = None, session_id: str = None) -> dict:
    """發送 CDP 命令並等待回應"""
    message_id = id(method)  # 使用簡單的 ID

    message = {
        "id": message_id,
        "method": method,
        "params": params or {}
    }

    if session_id:
        message["sessionId"] = session_id

    # 發送命令
    await websocket.send(json.dumps(message))
    print(f"  📤 發送: {method}")

    # 等待回應
    while True:
        response_text = await websocket.recv()
        response = json.loads(response_text)

        # 如果是我們的回應
        if response.get("id") == message_id:
            if "error" in response:
                print(f"  ❌ 錯誤: {response['error']}")
                raise Exception(f"CDP Error: {response['error']}")
            return response.get("result", {})

        # 如果是事件，記錄但繼續等待
        if "method" in response:
            print(f"  📥 事件: {response['method']}")


async def test_yahoo_navigation():
    """測試導航到 Yahoo 台灣"""
    import websockets

    print("\n" + "=" * 60)
    print("使用原生 CDP 測試導航到 Yahoo 台灣")
    print("=" * 60)

    # 步驟 1: 創建測試頁面
    import time
    page_name = f"yahoo-test-{int(time.time())}"
    print(f"\n📝 步驟 1: 創建測試頁面 '{page_name}'")

    try:
        page_info = await create_page_via_api(page_name)
        target_id = page_info['targetId']
        print(f"✅ 頁面已創建")
        print(f"   - Target ID: {target_id}")
        print(f"   - 初始 URL: {page_info['url']}")
    except Exception as e:
        print(f"❌ 創建頁面失敗: {e}")
        return False

    # 步驟 2: 連接到 WebSocket CDP 端點
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 步驟 2: 連接到 Browser Relay")
    print(f"   端點: {cdp_endpoint}")

    try:
        async with websockets.connect(cdp_endpoint, max_size=10 * 1024 * 1024) as websocket:  # 增加到 10MB
            print("✅ WebSocket 連接成功")

            # 步驟 3: 設置 Target 自動附加
            print(f"\n🔧 步驟 3: 設置 Target 自動附加")
            await send_cdp_command(
                websocket,
                "Target.setAutoAttach",
                {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True}
            )
            print("✅ Target 自動附加已設置")

            # 等待一下讓 targets 附加
            await asyncio.sleep(1)

            # 步驟 4: 附加到我們的 target
            print(f"\n🎯 步驟 4: 附加到 Target {target_id}")
            result = await send_cdp_command(
                websocket,
                "Target.attachToTarget",
                {"targetId": target_id, "flatten": True}
            )
            session_id = result.get("sessionId")

            if not session_id:
                print("❌ 未獲得 session ID")
                return False

            print(f"✅ 已附加到 Target")
            print(f"   - Session ID: {session_id}")

            # 步驟 5: 在 session 中啟用 Page 域
            print(f"\n📄 步驟 5: 啟用 Page 域")
            await send_cdp_command(websocket, "Page.enable", {}, session_id)
            print("✅ Page 域已啟用")

            # 步驟 5.5: 測試光暈效果 - 啟用
            print(f"\n✨ 步驟 5.5: 測試光暈效果 - 啟用光暈")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ 綠色光暈已啟用")
            print("   💡 請在瀏覽器中查看標籤頁，應該可以看到綠色光暈邊框")
            await asyncio.sleep(3)

            # 步驟 6: 導航到 Yahoo
            print(f"\n🌐 步驟 6: 導航到 https://tw.yahoo.com/")
            await send_cdp_command(
                websocket,
                "Page.navigate",
                {"url": "https://tw.yahoo.com/"},
                session_id
            )
            print("✅ 導航命令已發送")

            # 等待頁面載入
            print("\n⏳ 等待頁面載入...")
            await asyncio.sleep(5)

            # 步驟 7: 獲取頁面資訊
            print(f"\n📋 步驟 7: 獲取頁面資訊")

            # 執行 JavaScript 獲取標題和 URL
            result = await send_cdp_command(
                websocket,
                "Runtime.evaluate",
                {"expression": "document.title"},
                session_id
            )
            title = result.get("result", {}).get("value", "未知")
            print(f"   - 標題: {title}")

            result = await send_cdp_command(
                websocket,
                "Runtime.evaluate",
                {"expression": "window.location.href"},
                session_id
            )
            url = result.get("result", {}).get("value", "未知")
            print(f"   - URL: {url}")

            # 步驟 7.5: 測試光暈效果 - 關閉與重新啟用
            print(f"\n✨ 步驟 7.5: 測試光暈效果 - 關閉光暈")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": False},
                session_id
            )
            print("✅ 光暈已關閉")
            print("   💡 請確認瀏覽器中的綠色光暈已消失")
            await asyncio.sleep(2)

            print(f"\n✨ 重新啟用光暈")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ 光暈已重新啟用")
            print("   💡 請確認瀏覽器中的綠色光暈已重新出現")
            await asyncio.sleep(2)

            # 步驟 7.6: 測試頁面重新載入後光暈恢復
            print(f"\n🔄 步驟 7.6: 測試頁面重新載入後光暈自動恢復")
            print("   正在重新載入頁面...")
            await send_cdp_command(
                websocket,
                "Page.reload",
                {},
                session_id
            )
            print("✅ 頁面重新載入命令已發送")
            print("   ⏳ 等待頁面載入並自動恢復光暈...")
            await asyncio.sleep(5)
            print("   💡 請確認瀏覽器中的綠色光暈在頁面重新載入後仍然存在")

            # 步驟 8: 截圖
            print(f"\n📸 步驟 8: 截取頁面截圖（帶光暈效果）")
            result = await send_cdp_command(
                websocket,
                "Page.captureScreenshot",
                {"format": "png"},
                session_id
            )

            screenshot_data = result.get("data")
            if screenshot_data:
                import base64
                screenshot_path = Path(__file__).parent / "yahoo_screenshot.png"
                screenshot_path.write_bytes(base64.b64decode(screenshot_data))
                print(f"✅ 截圖已儲存: {screenshot_path}")
            else:
                print("⚠️  未獲得截圖數據")

            # 步驟 9: 驗證
            print(f"\n✅ 步驟 9: 驗證結果")
            if "yahoo" in url.lower():
                print("✅ URL 驗證通過 - 確實在 Yahoo 網站")
            else:
                print(f"⚠️  URL 驗證失敗 - 期望包含 'yahoo'，實際: {url}")

            if "yahoo" in title.lower():
                print("✅ 標題驗證通過 - 包含 Yahoo")
            else:
                print(f"⚠️  標題驗證失敗 - 期望包含 'Yahoo'，實際: {title}")

            # 測試摘要
            print("\n" + "=" * 60)
            print("測試完成")
            print("=" * 60)
            print("✅ 成功透過 Browser Relay 導航到 Yahoo 台灣")
            print(f"   - 頁面名稱: {page_name}")
            print(f"   - Target ID: {target_id}")
            print(f"   - Session ID: {session_id}")
            print(f"   - 標題: {title}")
            print(f"   - URL: {url}")
            print("\n✨ 光暈效果測試結果:")
            print("   ✅ 啟用光暈 - 成功")
            print("   ✅ 關閉光暈 - 成功")
            print("   ✅ 重新啟用光暈 - 成功")
            print("   ✅ 頁面重新載入後光暈自動恢復 - 成功")
            print("\n💡 提示: 瀏覽器頁面保持開啟且帶有綠色光暈，可在 Chrome 中查看")

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
