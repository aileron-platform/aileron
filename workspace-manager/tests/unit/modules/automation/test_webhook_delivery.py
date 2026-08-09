"""Tests for webhook delivery."""

from __future__ import annotations

import httpx
import pytest

from app.modules.automation.webhook_delivery import deliver_webhook, is_safe_webhook_url


def _resolver_to(ip: str):
    return lambda host, port: [(2, 1, 6, "", (ip, port or 0))]


@pytest.mark.parametrize(
    ("url", "ip", "safe"),
    [
        ("https://hooks.example.com/x", "93.184.216.34", True),
        ("http://hooks.example.com/x", "93.184.216.34", True),
        ("https://x", "127.0.0.1", False),
        ("https://x", "10.0.0.5", False),
        ("https://x", "192.168.1.2", False),
        ("https://x", "169.254.1.1", False),
        ("ftp://x", "93.184.216.34", False),
    ],
)
def test_is_safe_webhook_url(url, ip, safe):
    assert is_safe_webhook_url(url, resolver=_resolver_to(ip)) is safe


def test_deliver_rejects_unsafe_url_without_posting():
    posted = {"called": False}

    def handler(request):
        posted["called"] = True
        return httpx.Response(200)

    result = deliver_webhook(
        "https://x",
        {"a": 1},
        "key1",
        transport=httpx.MockTransport(handler),
        resolver=_resolver_to("127.0.0.1"),
    )

    assert result.delivered is False
    assert result.error == "unsafe_url"
    assert posted["called"] is False


def test_deliver_success_sends_idempotency_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("X-Idempotency-Key")
        return httpx.Response(200)

    result = deliver_webhook(
        "https://hooks.example.com/x",
        {"a": 1},
        "exec-1",
        transport=httpx.MockTransport(handler),
        resolver=_resolver_to("93.184.216.34"),
    )

    assert result.delivered is True
    assert seen["key"] == "exec-1"


def test_deliver_retries_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503)
        return httpx.Response(200)

    result = deliver_webhook(
        "https://hooks.example.com/x",
        {"a": 1},
        "k",
        transport=httpx.MockTransport(handler),
        resolver=_resolver_to("93.184.216.34"),
        max_attempts=3,
        backoff_seconds=0,
    )

    assert result.delivered is True
    assert calls["n"] == 2


def test_deliver_exhausts_and_reports_failure():
    def handler(request):
        return httpx.Response(500)

    result = deliver_webhook(
        "https://hooks.example.com/x",
        {"a": 1},
        "k",
        transport=httpx.MockTransport(handler),
        resolver=_resolver_to("93.184.216.34"),
        max_attempts=2,
        backoff_seconds=0,
    )

    assert result.delivered is False
    assert result.attempts == 2
