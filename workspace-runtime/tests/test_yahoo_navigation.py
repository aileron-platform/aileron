"""
Test connecting to Yahoo Taiwan via Browser Relay

Run:
    uv run tests/test_yahoo_navigation.py

Requirements:
    - Chrome Extension enabled and connected
    - Browser Relay service running
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


async def test_yahoo_navigation():
    """Test navigating to Yahoo Taiwan"""
    from playwright.async_api import async_playwright

    print("\n" + "=" * 60)
    print("Testing connection to Yahoo Taiwan via Browser Relay")
    print("=" * 60)

    # Step 1: First create named page via API
    page_name = f"yahoo-test-{int(asyncio.get_event_loop().time())}"
    print(f"\n📝 Creating test page: {page_name}")

    try:
        page_info = await create_page_via_api(page_name)
        print(f"✅ Page created")
        print(f"   - Target ID: {page_info['targetId']}")
        print(f"   - Initial URL: {page_info['url']}")
    except Exception as e:
        print(f"❌ Failed to create page: {e}")
        return False

    # Step 2: Connect to Browser Relay
    cdp_endpoint = "ws://localhost:3002/api/v1/client-browser-relay/cdp"
    print(f"\n📡 Connecting to Browser Relay: {cdp_endpoint}")

    async with async_playwright() as p:
        try:
            # Connect to existing browser
            browser = await p.chromium.connect_over_cdp(cdp_endpoint)
            print("✅ Successfully connected to browser")

            # Get all contexts and pages
            contexts = browser.contexts
            print(f"📋 Found {len(contexts)} context(s)")

            # Find the page we just created
            target_page = None
            for context in contexts:
                pages = context.pages
                print(f"   Context has {len(pages)} page(s)")
                for page in pages:
                    print(f"   - Page URL: {page.url}")
                    # Look for about:blank page (newly created)
                    if page.url == "about:blank" or not target_page:
                        target_page = page

            if not target_page:
                print("❌ Cannot find available page")
                return False

            print(f"\n✅ Using page: {target_page.url}")

            # Step 3: Navigate to Yahoo Taiwan
            print("\n🌐 Navigating to https://tw.yahoo.com/")
            await target_page.goto("https://tw.yahoo.com/", wait_until="domcontentloaded", timeout=30000)
            print(f"✅ Page loaded: {target_page.url}")

            # Wait for page load completion
            try:
                await target_page.wait_for_load_state("networkidle", timeout=10000)
                print("✅ Network requests completed")
            except Exception as e:
                print(f"⚠️  Wait for network idle timeout (normal): {e}")

            # Step 4: Get page information
            title = await target_page.title()
            print(f"\n📄 Page title: {title}")

            current_url = target_page.url
            print(f"🔗 Current URL: {current_url}")

            # Step 5: Screenshot
            screenshot_path = Path(__file__).parent / "yahoo_screenshot.png"
            await target_page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"📸 Screenshot saved: {screenshot_path}")

            # Step 6: Verify page content
            print("\n🔍 Verifying page content...")

            # Check if page contains Yahoo-related elements
            try:
                # Wait for page main content to load
                await target_page.wait_for_selector('body', timeout=5000)

                # Get page text content
                body_text = await target_page.evaluate('() => document.body.innerText')

                if 'yahoo' in body_text.lower() or 'Yahoo' in body_text:
                    print("✅ Page content contains Yahoo")
                else:
                    print("⚠️  Page content does not explicitly contain Yahoo keyword")

            except Exception as e:
                print(f"⚠️  Error occurred while verifying page content: {e}")

            # Verify URL
            if "yahoo" in current_url.lower():
                print("✅ URL verification passed - indeed on Yahoo website")
            else:
                print(f"⚠️  URL verification failed - expected to contain 'yahoo', actual: {current_url}")

            # Step 7: Test summary
            print("\n" + "=" * 60)
            print("Test Complete")
            print("=" * 60)
            print("✅ Successfully navigated to Yahoo Taiwan via Browser Relay")
            print(f"   - Page name: {page_name}")
            print(f"   - Title: {title}")
            print(f"   - URL: {current_url}")
            print(f"   - Screenshot: {screenshot_path}")
            print("\n💡 Tip: Browser page stays open, viewable in Chrome")

            # Don't close browser, keep connection
            # await browser.close()

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
