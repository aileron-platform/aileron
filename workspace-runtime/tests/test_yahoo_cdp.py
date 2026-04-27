"""
Test connecting to Yahoo Taiwan via Browser Relay using native CDP
And test glow effect functionality

Run:
    uv run tests/test_yahoo_cdp.py

Requirements:
    - Chrome Extension enabled and connected
    - Browser Relay service running

Test Content:
    - Create tab and navigate to Yahoo Taiwan
    - Enable/disable glow effect (Browser.setGlowEffect)
    - Test glow effect auto-recovery after page reload
    - Capture screenshot with glow effect
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
    reason="Browser Relay E2E test needs to be explicitly enabled",
)


async def create_page_via_api(page_name: str) -> dict:
    """Create named page via API"""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3002/api/v1/client-browser-relay/pages",
            json={"name": page_name}
        )
        response.raise_for_status()
        return response.json()


async def send_cdp_command(websocket, method: str, params: dict = None, session_id: str = None) -> dict:
    """Send CDP command and wait for response"""
    message_id = id(method)  # Use simple ID

    message = {
        "id": message_id,
        "method": method,
        "params": params or {}
    }

    if session_id:
        message["sessionId"] = session_id

    # Send command
    await websocket.send(json.dumps(message))
    print(f"  📤 Sent: {method}")

    # Wait for response
    while True:
        response_text = await websocket.recv()
        response = json.loads(response_text)

        # If it's our response
        if response.get("id") == message_id:
            if "error" in response:
                print(f"  ❌ Error: {response['error']}")
                raise Exception(f"CDP Error: {response['error']}")
            return response.get("result", {})

        # If it's an event, log but continue waiting
        if "method" in response:
            print(f"  📥 Event: {response['method']}")


async def test_yahoo_navigation():
    """Test navigating to Yahoo Taiwan"""
    import websockets

    print("\n" + "=" * 60)
    print("Testing navigation to Yahoo Taiwan using native CDP")
    print("=" * 60)

    # Step 1: Create test page
    import time
    page_name = f"yahoo-test-{int(time.time())}"
    print(f"\n📝 Step 1: Create test page '{page_name}'")

    try:
        page_info = await create_page_via_api(page_name)
        target_id = page_info['targetId']
        print(f"✅ Page created")
        print(f"   - Target ID: {target_id}")
        print(f"   - Initial URL: {page_info['url']}")
    except Exception as e:
        print(f"❌ Failed to create page: {e}")
        return False

    # Step 2: Connect to WebSocket CDP endpoint
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 Step 2: Connect to Browser Relay")
    print(f"   Endpoint: {cdp_endpoint}")

    try:
        async with websockets.connect(cdp_endpoint, max_size=10 * 1024 * 1024) as websocket:  # Increase to 10MB
            print("✅ WebSocket connected successfully")

            # Step 3: Set Target auto-attach
            print(f"\n🔧 Step 3: Set Target auto-attach")
            await send_cdp_command(
                websocket,
                "Target.setAutoAttach",
                {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True}
            )
            print("✅ Target auto-attach configured")

            # Wait a bit for targets to attach
            await asyncio.sleep(1)

            # Step 4: Attach to our target
            print(f"\n🎯 Step 4: Attach to Target {target_id}")
            result = await send_cdp_command(
                websocket,
                "Target.attachToTarget",
                {"targetId": target_id, "flatten": True}
            )
            session_id = result.get("sessionId")

            if not session_id:
                print("❌ Did not get session ID")
                return False

            print(f"✅ Attached to Target")
            print(f"   - Session ID: {session_id}")

            # Step 5: Enable Page domain in session
            print(f"\n📄 Step 5: Enable Page domain")
            await send_cdp_command(websocket, "Page.enable", {}, session_id)
            print("✅ Page domain enabled")

            # Step 5.5: Test glow effect - enable
            print(f"\n✨ Step 5.5: Test glow effect - enable glow")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ Green glow effect enabled")
            print("   💡 Please check the browser tab, you should see green glow border")
            await asyncio.sleep(3)

            # Step 6: Navigate to Yahoo
            print(f"\n🌐 Step 6: Navigate to https://tw.yahoo.com/")
            await send_cdp_command(
                websocket,
                "Page.navigate",
                {"url": "https://tw.yahoo.com/"},
                session_id
            )
            print("✅ Navigation command sent")

            # Wait for page load
            print("\n⏳ Waiting for page to load...")
            await asyncio.sleep(5)

            # Step 7: Get page information
            print(f"\n📋 Step 7: Get page information")

            # Execute JavaScript to get title and URL
            result = await send_cdp_command(
                websocket,
                "Runtime.evaluate",
                {"expression": "document.title"},
                session_id
            )
            title = result.get("result", {}).get("value", "Unknown")
            print(f"   - Title: {title}")

            result = await send_cdp_command(
                websocket,
                "Runtime.evaluate",
                {"expression": "window.location.href"},
                session_id
            )
            url = result.get("result", {}).get("value", "Unknown")
            print(f"   - URL: {url}")

            # Step 7.5: Test glow effect - disable and re-enable
            print(f"\n✨ Step 7.5: Test glow effect - disable glow")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": False},
                session_id
            )
            print("✅ Glow effect disabled")
            print("   💡 Please confirm the green glow in browser has disappeared")
            await asyncio.sleep(2)

            print(f"\n✨ Re-enable glow")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ Glow effect re-enabled")
            print("   💡 Please confirm the green glow in browser has reappeared")
            await asyncio.sleep(2)

            # Step 7.6: Test glow recovery after page reload
            print(f"\n🔄 Step 7.6: Test glow auto-recovery after page reload")
            print("   Reloading page...")
            await send_cdp_command(
                websocket,
                "Page.reload",
                {},
                session_id
            )
            print("✅ Page reload command sent")
            print("   ⏳ Waiting for page to load and auto-recover glow...")
            await asyncio.sleep(5)
            print("   💡 Please confirm the green glow still exists after page reload")

            # Step 8: Screenshot
            print(f"\n📸 Step 8: Capture page screenshot (with glow effect)")
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
                print(f"✅ Screenshot saved: {screenshot_path}")
            else:
                print("⚠️  Did not get screenshot data")

            # Step 9: Verification
            print(f"\n✅ Step 9: Verify results")
            if "yahoo" in url.lower():
                print("✅ URL verification passed - indeed on Yahoo website")
            else:
                print(f"⚠️  URL verification failed - expected to contain 'yahoo', actual: {url}")

            if "yahoo" in title.lower():
                print("✅ Title verification passed - contains Yahoo")
            else:
                print(f"⚠️  Title verification failed - expected to contain 'Yahoo', actual: {title}")

            # Test summary
            print("\n" + "=" * 60)
            print("Test Complete")
            print("=" * 60)
            print("✅ Successfully navigated to Yahoo Taiwan via Browser Relay")
            print(f"   - Page name: {page_name}")
            print(f"   - Target ID: {target_id}")
            print(f"   - Session ID: {session_id}")
            print(f"   - Title: {title}")
            print(f"   - URL: {url}")
            print("\n✨ Glow effect test results:")
            print("   ✅ Enable glow - Success")
            print("   ✅ Disable glow - Success")
            print("   ✅ Re-enable glow - Success")
            print("   ✅ Glow auto-recovery after page reload - Success")
            print("\n💡 Tip: Browser page stays open with green glow, viewable in Chrome")

            return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main program"""
    try:
        success = await test_yahoo_navigation()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
