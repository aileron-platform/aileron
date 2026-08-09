"""Focused visual-service lifecycle assertions."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import httpx

from product_conformance.scenarios_jobs import assert_visual_services_ready


class VisualServicesLifecycleTest(unittest.TestCase):
    @staticmethod
    def _context(handler: httpx.MockTransport) -> tuple[SimpleNamespace, httpx.Client]:
        client = httpx.Client(transport=handler)
        context = SimpleNamespace(
            http=client,
            workspace_service_urls={
                "browserNeko": "http://browser:6080",
                "browser": "http://browser:9223",
                "canvas": "http://canvas:3003",
                "canvasApi": "http://canvas:3013",
            },
        )
        return context, client

    def test_requires_real_browser_and_canvas_endpoints(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            responses: dict[str, httpx.Response] = {
                "http://browser:6080/health": httpx.Response(200, text="ok"),
                "http://browser:9223/json/version": httpx.Response(
                    200,
                    json={
                        "webSocketDebuggerUrl": "ws://browser:9223/devtools/browser/id"
                    },
                ),
                "http://canvas:3013/ready": httpx.Response(
                    200,
                    json={"status": "ready", "renderer_available": True},
                ),
                "http://canvas:3003/": httpx.Response(200, text="canvas"),
            }
            return responses[str(request.url)]

        context, client = self._context(httpx.MockTransport(handler))
        try:
            observed = assert_visual_services_ready(context)
        finally:
            client.close()

        self.assertEqual(observed["browserNekoStatus"], 200)
        self.assertEqual(observed["canvasRendererStatus"], 200)

    def test_rejects_canvas_ready_before_renderer_is_available(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if str(request.url) == "http://browser:6080/health":
                return httpx.Response(200, text="ok")
            if str(request.url) == "http://browser:9223/json/version":
                return httpx.Response(
                    200,
                    json={
                        "webSocketDebuggerUrl": "ws://browser:9223/devtools/browser/id"
                    },
                )
            return httpx.Response(
                200,
                json={"status": "ready", "renderer_available": False},
            )

        context, client = self._context(httpx.MockTransport(handler))
        try:
            with self.assertRaisesRegex(AssertionError, "readiness payload"):
                assert_visual_services_ready(context)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
