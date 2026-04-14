from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.auth import jwks_cache as cache_module


@pytest.fixture
def cache(monkeypatch):
    monkeypatch.setattr(
        cache_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(enabled=True, jwks_cache_ttl=60, jwks_url="https://example.test/certs"),
    )
    return cache_module.JKWSCache()


async def test_get_jwks_uses_valid_cache(cache) -> None:
    cache._cache = {"keys": [{"kid": "k1"}]}
    cache._cache_time = datetime.now(UTC)

    result = await cache.get_jwks()

    assert result == {"keys": [{"kid": "k1"}]}
    assert cache._cache_hits == 1


async def test_get_jwks_refreshes_when_missing(cache, monkeypatch) -> None:
    refresh = AsyncMock(return_value={"keys": [{"kid": "fresh"}]})
    monkeypatch.setattr(cache, "_refresh_jwks", refresh)

    result = await cache.get_jwks()

    assert result == {"keys": [{"kid": "fresh"}]}
    refresh.assert_awaited_once_with(force_refresh=False)


async def test_refresh_jwks_fetches_and_updates_cache(cache, monkeypatch) -> None:
    fetch = AsyncMock(return_value={"keys": [{"kid": "k1"}]})
    monkeypatch.setattr(cache, "_fetch_jwks_from_server", fetch)

    result = await cache._refresh_jwks()

    assert result == {"keys": [{"kid": "k1"}]}
    assert cache._cache == {"keys": [{"kid": "k1"}]}
    assert cache._cache_misses == 1
    assert cache._is_refreshing is False


async def test_fetch_jwks_from_server_validates_format(cache, monkeypatch) -> None:
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {},
    )
    client = AsyncMock()
    client.get.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    monkeypatch.setattr(cache_module.httpx, "AsyncClient", lambda timeout=10.0: client)

    with pytest.raises(cache_module.JWKSFetchError) as exc:
        await cache._fetch_jwks_from_server()

    assert "missing 'keys'" in str(exc.value)


async def test_fetch_jwks_from_server_falls_back_to_stale_cache(cache, monkeypatch) -> None:
    cache._cache = {"keys": [{"kid": "stale"}]}
    client = AsyncMock()
    client.get.side_effect = httpx.HTTPError("network")
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    monkeypatch.setattr(cache_module.httpx, "AsyncClient", lambda timeout=10.0: client)

    result = await cache._fetch_jwks_from_server()

    assert result == {"keys": [{"kid": "stale"}]}
    assert cache._refresh_errors == 1


async def test_fetch_jwks_from_server_raises_without_cache(cache, monkeypatch) -> None:
    client = AsyncMock()
    client.get.side_effect = RuntimeError("boom")
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    monkeypatch.setattr(cache_module.httpx, "AsyncClient", lambda timeout=10.0: client)

    with pytest.raises(cache_module.JWKSFetchError) as exc:
        await cache._fetch_jwks_from_server()

    assert "Unexpected error" in str(exc.value)


def test_cache_helpers(cache) -> None:
    cache._cache = {"keys": [{"kid": "k1"}, {"kid": "k2"}]}
    cache._cache_time = datetime.now(UTC) - timedelta(seconds=120)

    assert cache.is_cache_valid() is False
    assert cache.get_key_by_kid("k2") == {"kid": "k2"}
    assert cache.get_key_by_kid("missing") is None

    cache.clear()
    assert cache._cache is None


def test_singletons(monkeypatch) -> None:
    monkeypatch.setattr(
        cache_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(enabled=True, jwks_cache_ttl=60, jwks_url="https://example.test/certs"),
    )
    cache_module._jwks_cache_instance = None

    cache1 = cache_module.get_jwks_cache()
    cache2 = cache_module.get_jwks_cache()
    assert cache1 is cache2

    cache_module.clear_jwks_cache()
    assert cache1._cache is None
