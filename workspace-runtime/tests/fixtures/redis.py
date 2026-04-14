"""Redis fixtures for testing

Provides fakeredis (for unit tests) and real Redis (for integration tests) fixtures.
"""

import pytest
from typing import AsyncGenerator


@pytest.fixture(scope="function")
async def fake_redis() -> AsyncGenerator:
    """Provide fake Redis for unit tests

    Features:
    - No external dependencies
    - Fast
    - Isolated per test
    - Most Redis commands supported

    Usage:
        @pytest.mark.asyncio
        async def test_redis_set_get(fake_redis):
            await fake_redis.set("key", "value")
            result = await fake_redis.get("key")
            assert result == "value"
    """
    try:
        import fakeredis.aioredis
    except ImportError:
        pytest.skip("fakeredis not installed. Install with: uv add fakeredis --group dev")

    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    yield redis

    # Cleanup
    await redis.flushall()
    await redis.aclose()


@pytest.fixture(scope="function")
async def real_redis():
    """Provide real Redis for integration tests

    Requires:
    - Redis running on localhost:6380

    Run with Docker:
        docker-compose -f docker-compose.test.yml up -d redis-test
    """
    try:
        import redis.asyncio as aioredis
    except ImportError:
        pytest.skip("redis not installed. Install with: uv add redis")

    try:
        redis = await aioredis.from_url(
            "redis://localhost:6380",
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )

        # Test connection
        await redis.ping()

        yield redis

        # Cleanup
        await redis.flushall()
        await redis.aclose()
    except (ConnectionRefusedError, Exception) as e:
        pytest.skip(f"Redis not available: {e}")


@pytest.fixture(scope="function")
async def redis_client(fake_redis):
    """Alias for fake_redis for convenience"""
    return fake_redis


@pytest.fixture
def redis_publisher(fake_redis):
    """Create RedisEventPublisher with fake Redis

    Usage:
        @pytest.mark.asyncio
        async def test_publish(redis_publisher):
            await redis_publisher.publish_execution_completed(
                execution_id="exec_123",
                session_id="sess_123",
                workspace_id="ws_test",
                status="completed",
                total_messages=10,
                has_error=False
            )
    """
    from app.core.redis_publisher import RedisEventPublisher
    from unittest.mock import patch, AsyncMock

    publisher = RedisEventPublisher()

    # Patch redis_manager to use fake_redis
    with patch("app.core.redis_publisher.redis_manager") as mock_manager:
        mock_manager.get_redis = AsyncMock(return_value=fake_redis)
        mock_manager.close = AsyncMock()
        yield publisher


@pytest.fixture
async def redis_subscriber(fake_redis):
    """Create Redis subscriber for testing pub/sub

    Usage:
        @pytest.mark.asyncio
        async def test_pubsub(redis_subscriber, redis_publisher):
            # Subscribe to channel
            channel = "workspace:ws_123"
            await redis_subscriber.subscribe(channel)

            # Publish message
            await redis_publisher.publish(channel, "test message")

            # Receive message
            message = await redis_subscriber.get_message(timeout=1.0)
            assert message is not None
    """
    pubsub = fake_redis.pubsub()
    yield pubsub
    await pubsub.unsubscribe()
    await pubsub.aclose()


# Cache testing helpers

@pytest.fixture
async def redis_cache(fake_redis):
    """Redis cache helper for testing

    Usage:
        @pytest.mark.asyncio
        async def test_cache(redis_cache):
            await redis_cache.set("user:1", {"name": "test"}, ttl=60)
            user = await redis_cache.get("user:1")
            assert user["name"] == "test"
    """
    class RedisCache:
        def __init__(self, redis_client):
            self.redis = redis_client

        async def get(self, key: str):
            import json
            value = await self.redis.get(key)
            return json.loads(value) if value else None

        async def set(self, key: str, value: dict, ttl: int = None):
            import json
            serialized = json.dumps(value)
            if ttl:
                await self.redis.setex(key, ttl, serialized)
            else:
                await self.redis.set(key, serialized)

        async def delete(self, key: str):
            await self.redis.delete(key)

        async def exists(self, key: str) -> bool:
            return await self.redis.exists(key) > 0

    return RedisCache(fake_redis)
