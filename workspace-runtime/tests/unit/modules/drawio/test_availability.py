"""Draw.io availability helper tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.drawio import availability as drawio_availability
from app.modules.drawio.availability import clear_drawio_availability_cache, get_drawio_availability


def make_settings(**overrides):
    values = {
        "DRAWIO_ENABLED": True,
        "DRAWIO_EXTERNAL_URL": "http://localhost:8083/draw",
        "DRAWIO_INTERNAL_URL": "http://drawio:8080",
        "DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS": 1.5,
        "DRAWIO_HEALTHCHECK_TTL_SECONDS": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeResponse:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.status_code = 500 if should_fail else 200

    def raise_for_status(self):
        if self.should_fail:
            raise RuntimeError("unhealthy")


class FakeAsyncClient:
    calls = 0
    should_fail = False

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url):
        FakeAsyncClient.calls += 1
        if FakeAsyncClient.should_fail:
            raise RuntimeError("unreachable")
        return FakeResponse()


@pytest.fixture(autouse=True)
def reset_cache():
    clear_drawio_availability_cache()
    FakeAsyncClient.calls = 0
    FakeAsyncClient.should_fail = False
    yield
    clear_drawio_availability_cache()


@pytest.mark.asyncio
async def test_availability_disabled_does_not_call_healthcheck(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)

    result = await get_drawio_availability(make_settings(DRAWIO_ENABLED=False))

    assert result.available is False
    assert result.reason == "DISABLED"
    assert FakeAsyncClient.calls == 0


@pytest.mark.asyncio
async def test_availability_empty_external_url_is_disabled(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)

    result = await get_drawio_availability(make_settings(DRAWIO_EXTERNAL_URL=""))

    assert result.available is False
    assert result.reason == "DISABLED"
    assert FakeAsyncClient.calls == 0


@pytest.mark.asyncio
async def test_availability_healthy(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)

    result = await get_drawio_availability(make_settings())

    assert result.available is True
    assert result.reason is None
    assert FakeAsyncClient.calls == 1


@pytest.mark.asyncio
async def test_availability_unreachable(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)
    FakeAsyncClient.should_fail = True

    result = await get_drawio_availability(make_settings())

    assert result.available is False
    assert result.reason == "UNREACHABLE"
    assert FakeAsyncClient.calls == 1


@pytest.mark.asyncio
async def test_availability_uses_cache_within_ttl(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)
    settings = make_settings(DRAWIO_HEALTHCHECK_TTL_SECONDS=30)

    first = await get_drawio_availability(settings)
    second = await get_drawio_availability(settings)

    assert first is second
    assert FakeAsyncClient.calls == 1


@pytest.mark.asyncio
async def test_availability_force_refresh_bypasses_cache(monkeypatch):
    monkeypatch.setattr(drawio_availability.httpx, "AsyncClient", FakeAsyncClient)
    settings = make_settings(DRAWIO_HEALTHCHECK_TTL_SECONDS=30)

    await get_drawio_availability(settings)
    await get_drawio_availability(settings, force_refresh=True)

    assert FakeAsyncClient.calls == 2
