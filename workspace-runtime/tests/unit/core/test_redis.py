from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.redis import RedisManager


@pytest.fixture
def redis_client() -> AsyncMock:
    client = AsyncMock()
    client.ping = AsyncMock()
    client.get = AsyncMock()
    client.set = AsyncMock()
    client.setex = AsyncMock()
    client.delete = AsyncMock()
    client.exists = AsyncMock(return_value=1)
    client.close = AsyncMock()
    return client


@pytest.fixture
def manager(monkeypatch, redis_client: AsyncMock) -> RedisManager:
    monkeypatch.setattr(
        "app.core.redis.get_settings",
        lambda: SimpleNamespace(REDIS_URL="redis://redis-test:6379/0"),
    )
    from_url = AsyncMock(return_value=redis_client)
    monkeypatch.setattr("app.core.redis.aioredis.from_url", from_url)
    instance = RedisManager()
    instance._from_url = from_url  # type: ignore[attr-defined]
    return instance


@pytest.mark.asyncio
async def test_get_redis_initializes_once(manager: RedisManager, redis_client: AsyncMock) -> None:
    first = await manager.get_redis()
    second = await manager.get_redis()

    assert first is redis_client
    assert second is redis_client
    manager._from_url.assert_awaited_once()  # type: ignore[attr-defined]
    redis_client.ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_parses_json_string(manager: RedisManager, redis_client: AsyncMock) -> None:
    redis_client.get.return_value = '{"ok": true}'

    result = await manager.get("config")

    assert result == {"ok": True}


@pytest.mark.asyncio
async def test_get_returns_plain_string_when_json_invalid(manager: RedisManager, redis_client: AsyncMock) -> None:
    redis_client.get.return_value = "not-json"

    result = await manager.get("plain")

    assert result == "not-json"


@pytest.mark.asyncio
async def test_set_uses_setex_when_expire_provided(manager: RedisManager, redis_client: AsyncMock) -> None:
    result = await manager.set("key", {"foo": "bar"}, expire=30)

    assert result is True
    redis_client.setex.assert_awaited_once()
    args = redis_client.setex.await_args.args
    assert args[0] == "key"
    assert args[1] == 30
    assert args[2] == '{"foo": "bar"}'


@pytest.mark.asyncio
async def test_exists_returns_false_when_redis_raises(manager: RedisManager, redis_client: AsyncMock) -> None:
    redis_client.exists.side_effect = RuntimeError("boom")

    result = await manager.exists("missing")

    assert result is False


@pytest.mark.asyncio
async def test_close_resets_cached_connection(manager: RedisManager, redis_client: AsyncMock) -> None:
    await manager.get_redis()

    await manager.close()

    redis_client.close.assert_awaited_once()
    assert manager._redis is None
