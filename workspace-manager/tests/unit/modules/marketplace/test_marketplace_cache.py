"""Marketplace Redis cache contract tests."""

from __future__ import annotations

from redis.exceptions import ConnectionError

from app.modules.marketplace import cache as marketplace_cache
from app.modules.marketplace.cache import (
    MARKETPLACE_CACHE_TTL_SECONDS,
    MarketplaceCache,
)


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.delete_batches: list[tuple[str, ...]] = []

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str, *, ex: int) -> None:
        self.values[key] = value
        self.expirations[key] = ex

    def delete(self, *keys: str) -> None:
        self.delete_batches.append(keys)
        for key in keys:
            self.values.pop(key, None)
            self.expirations.pop(key, None)

    def scan_iter(self, *, match: str, count: int):
        _ = count
        prefix, suffix = match.split("*", 1)
        return (
            key
            for key in list(self.values)
            if key.startswith(prefix) and key.endswith(suffix)
        )


class _UnavailableRedis:
    def get(self, key: str) -> None:
        _ = key
        raise ConnectionError("unavailable")

    def set(self, key: str, value: str, *, ex: int) -> None:
        _ = (key, value, ex)
        raise ConnectionError("unavailable")

    def delete(self, *keys: str) -> None:
        _ = keys
        raise ConnectionError("unavailable")

    def scan_iter(self, *, match: str, count: int):
        _ = (match, count)
        raise ConnectionError("unavailable")


def test_cache_uses_fixed_ttl_and_global_shared_keys() -> None:
    client = _FakeRedis()
    cache = MarketplaceCache("redis://unused", client=client)
    first_key = cache.registry_index_key()
    second_key = cache.registry_index_key()

    cache.set_json(first_key, {"items": []})

    assert first_key == second_key
    assert cache.get_json(first_key) == {"items": []}
    assert cache.get_json(second_key) == {"items": []}
    assert client.expirations[first_key] == MARKETPLACE_CACHE_TTL_SECONDS


def test_cache_can_invalidate_one_package_or_all_shared_packages() -> None:
    client = _FakeRedis()
    cache = MarketplaceCache("redis://unused", client=client)
    first = cache.package_overview_key("codex", "first")
    second = cache.package_overview_key("codex", "second")
    for key in (first, second):
        cache.set_json(key, {"revision": key})

    cache.delete(first)
    cache.delete_pattern(cache.package_overview_pattern())

    assert cache.get_json(first) is None
    assert cache.get_json(second) is None


def test_redis_unavailable_bypasses_cache() -> None:
    cache = MarketplaceCache("redis://unused", client=_UnavailableRedis())

    assert cache.get_json("missing") is None
    cache.set_json("key", {"value": True})
    cache.delete("key")
    cache.delete_pattern("key:*")


def test_pattern_invalidation_deletes_scan_results_in_bounded_batches() -> None:
    client = _FakeRedis()
    cache = MarketplaceCache("redis://unused", client=client)
    for index in range(205):
        cache.set_json(f"marketplace:package:codex:{index}:overview", {})

    cache.delete_pattern(cache.package_overview_pattern())

    pattern_batches = [batch for batch in client.delete_batches if len(batch) > 1]
    assert [len(batch) for batch in pattern_batches] == [100, 100, 5]


def test_cache_reuses_redis_client_for_same_url(monkeypatch) -> None:
    clients: list[_FakeRedis] = []

    def create_client(redis_url: str, *, decode_responses: bool) -> _FakeRedis:
        assert redis_url == "redis://shared"
        assert decode_responses is True
        client = _FakeRedis()
        clients.append(client)
        return client

    marketplace_cache._redis_client.cache_clear()
    monkeypatch.setattr(marketplace_cache.Redis, "from_url", create_client)

    first = MarketplaceCache("redis://shared")
    second = MarketplaceCache("redis://shared")

    assert first._client is second._client
    assert len(clients) == 1
    marketplace_cache._redis_client.cache_clear()
