"""
測試光暈狀態查詢

執行方式：
    uv run tests/test_glow_state.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import websockets
    import httpx
except ImportError as e:
    print(f"❌ 錯誤: 缺少依賴套件 - {e}")
    sys.exit(1)


async def create_page_via_api(page_name: str) -> dict:
    """透過 API 創建命名頁面"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3002/api/v1/client-browser-relay/pages",
            json={"name": page_name}
        )
        response.raise_for_status()
        return response.json()


async def send_cdp_command(websocket, method: str, params: dict = None, session_id: str = None) -> dict:
    """發送 CDP 命令並等待回應"""
    message_id = id(method)

    message = {
        "id": message_id,
        "method": method,
        "params": params or {}
    }

    if session_id:
        message["sessionId"] = session_id

    await websocket.send(json.dumps(message))
    print(f"  📤 發送: {method} {params or ''}")

    while True:
        response_text = await websocket.recv()
        response = json.loads(response_text)

        if response.get("id") == message_id:
            if "error" in response:
                print(f"  ❌ 錯誤: {response['error']}")
                raise Exception(f"CDP Error: {response['error']}")
            return response.get("result", {})

        if "method" in response:
            print(f"  📥 事件: {response['method']}")


async def test_glow_state():
    """測試光暈狀態"""
    print("\n" + "=" * 60)
    print("測試光暈狀態查詢")
    print("=" * 60)

    # 創建測試頁面
    import time
    page_name = f"glow-test-{int(time.time())}"
    print(f"\n📝 步驟 1: 創建測試頁面 '{page_name}'")

    try:
        page_info = await create_page_via_api(page_name)
        target_id = page_info['targetId']
        print(f"✅ 頁面已創建")
        print(f"   - Target ID: {target_id}")
    except Exception as e:
        print(f"❌ 創建頁面失敗: {e}")
        return False

    # 連接到 WebSocket
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 步驟 2: 連接到 Browser Relay")

    try:
        async with websockets.connect(cdp_endpoint, max_size=10 * 1024 * 1024) as websocket:
            print("✅ WebSocket 連接成功")

            # 設置 Target 自動附加
            print(f"\n🔧 步驟 3: 設置 Target 自動附加")
            await send_cdp_command(
                websocket,
                "Target.setAutoAttach",
                {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True}
            )
            await asyncio.sleep(1)

            # 附加到 target
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

            # 查詢初始光暈狀態
            print(f"\n🔍 步驟 5: 查詢初始光暈狀態")
            state = await send_cdp_command(
                websocket,
                "Browser.getGlowState",
                {},
                session_id
            )
            print(f"✅ 光暈狀態:")
            print(f"   - enabled: {state.get('enabled', 'N/A')}")
            print(f"   - userEnabled: {state.get('userEnabled', 'N/A')}")

            # 嘗試啟用光暈
            print(f"\n✨ 步驟 6: 嘗試啟用光暈")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ 光暈啟用命令已發送")
            await asyncio.sleep(2)

            # 再次查詢光暈狀態
            print(f"\n🔍 步驟 7: 再次查詢光暈狀態")
            state = await send_cdp_command(
                websocket,
                "Browser.getGlowState",
                {},
                session_id
            )
            print(f"✅ 光暈狀態:")
            print(f"   - enabled: {state.get('enabled', 'N/A')}")
            print(f"   - userEnabled: {state.get('userEnabled', 'N/A')}")

            # 分析結果
            print("\n" + "=" * 60)
            print("測試結果分析")
            print("=" * 60)

            if not state.get('userEnabled'):
                print("❌ 使用者光暈開關已停用")
                print("   請在 Chrome Extension Popup 中開啟「顯示光暈效果」")
            elif state.get('enabled'):
                print("✅ 光暈已成功顯示")
                print("   請在瀏覽器中查看綠色光暈邊框")
            else:
                print("⚠️  光暈未顯示，但使用者開關已啟用")
                print("   可能的原因：頁面限制、CSS 注入失敗")

            return True

    except Exception as e:
        print(f"\n❌ 測試失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主程式"""
    try:
        await test_glow_state()
        return 0
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
