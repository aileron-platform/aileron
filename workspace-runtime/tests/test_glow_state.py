"""
Test glow state query

Run:
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
    print(f"❌ Error: Missing dependency package - {e}")
    sys.exit(1)


async def create_page_via_api(page_name: str) -> dict:
    """Create named page via API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:3002/api/v1/client-browser-relay/pages",
            json={"name": page_name}
        )
        response.raise_for_status()
        return response.json()


async def send_cdp_command(websocket, method: str, params: dict = None, session_id: str = None) -> dict:
    """Send CDP command and wait for response"""
    message_id = id(method)

    message = {
        "id": message_id,
        "method": method,
        "params": params or {}
    }

    if session_id:
        message["sessionId"] = session_id

    await websocket.send(json.dumps(message))
    print(f"  📤 Sent: {method} {params or ''}")

    while True:
        response_text = await websocket.recv()
        response = json.loads(response_text)

        if response.get("id") == message_id:
            if "error" in response:
                print(f"  ❌ Error: {response['error']}")
                raise Exception(f"CDP Error: {response['error']}")
            return response.get("result", {})

        if "method" in response:
            print(f"  📥 Event: {response['method']}")


async def test_glow_state():
    """Test glow state"""
    print("\n" + "=" * 60)
    print("Test glow state query")
    print("=" * 60)

    # Create test page
    import time
    page_name = f"glow-test-{int(time.time())}"
    print(f"\n📝 Step 1: Create test page '{page_name}'")

    try:
        page_info = await create_page_via_api(page_name)
        target_id = page_info['targetId']
        print(f"✅ Page created")
        print(f"   - Target ID: {target_id}")
    except Exception as e:
        print(f"❌ Failed to create page: {e}")
        return False

    # Connect to WebSocket
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 Step 2: Connect to Browser Relay")

    try:
        async with websockets.connect(cdp_endpoint, max_size=10 * 1024 * 1024) as websocket:
            print("✅ WebSocket connected successfully")

            # Set Target auto-attach
            print(f"\n🔧 Step 3: Set Target auto-attach")
            await send_cdp_command(
                websocket,
                "Target.setAutoAttach",
                {"autoAttach": True, "waitForDebuggerOnStart": False, "flatten": True}
            )
            await asyncio.sleep(1)

            # Attach to target
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

            # Query initial glow state
            print(f"\n🔍 Step 5: Query initial glow state")
            state = await send_cdp_command(
                websocket,
                "Browser.getGlowState",
                {},
                session_id
            )
            print(f"✅ Glow state:")
            print(f"   - enabled: {state.get('enabled', 'N/A')}")
            print(f"   - userEnabled: {state.get('userEnabled', 'N/A')}")

            # Try to enable glow
            print(f"\n✨ Step 6: Try to enable glow")
            await send_cdp_command(
                websocket,
                "Browser.setGlowEffect",
                {"enabled": True},
                session_id
            )
            print("✅ Glow enable command sent")
            await asyncio.sleep(2)

            # Query glow state again
            print(f"\n🔍 Step 7: Query glow state again")
            state = await send_cdp_command(
                websocket,
                "Browser.getGlowState",
                {},
                session_id
            )
            print(f"✅ Glow state:")
            print(f"   - enabled: {state.get('enabled', 'N/A')}")
            print(f"   - userEnabled: {state.get('userEnabled', 'N/A')}")

            # Analyze results
            print("\n" + "=" * 60)
            print("Test Result Analysis")
            print("=" * 60)

            if not state.get('userEnabled'):
                print("❌ User glow switch is disabled")
                print("   Please enable 'Show glow effect' in Chrome Extension Popup")
            elif state.get('enabled'):
                print("✅ Glow is successfully displayed")
                print("   Please check the green glow border in browser")
            else:
                print("⚠️  Glow not displayed but user switch is enabled")
                print("   Possible reasons: Page restrictions, CSS injection failed")

            return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main program"""
    try:
        await test_glow_state()
        return 0
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
