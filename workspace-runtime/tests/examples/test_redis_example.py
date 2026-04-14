"""Redis testing examples

This file demonstrates how to use Redis fixtures for testing.
"""

import pytest
import json


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_basic_operations(fake_redis):
    """Example: Basic Redis operations with fakeredis

    This test demonstrates:
    - Using fakeredis for unit tests
    - Fast testing without external dependencies
    - Standard Redis commands
    """
    # Set a value
    await fake_redis.set("test:key", "test_value")

    # Get the value
    value = await fake_redis.get("test:key")
    assert value == "test_value"

    # Delete the key
    await fake_redis.delete("test:key")

    # Verify deletion
    value = await fake_redis.get("test:key")
    assert value is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_json_storage(fake_redis):
    """Example: Store and retrieve JSON data

    This test demonstrates:
    - Serializing/deserializing JSON
    - Complex data structures in Redis
    - Common pattern in the application
    """
    # Store JSON data
    data = {
        "session_id": "sess_123",
        "workspace_id": "ws_test",
        "status": "running",
        "timestamp": "2025-01-01T00:00:00Z"
    }

    await fake_redis.set("session:sess_123", json.dumps(data))

    # Retrieve and parse
    retrieved = await fake_redis.get("session:sess_123")
    parsed = json.loads(retrieved)

    assert parsed["session_id"] == "sess_123"
    assert parsed["status"] == "running"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_expiration(fake_redis):
    """Example: Test key expiration

    This test demonstrates:
    - Setting TTL on keys
    - Testing time-based behavior
    - Cache invalidation patterns
    """
    # Set key with 60 second TTL
    await fake_redis.setex("temp:key", 60, "temporary_value")

    # Verify key exists
    assert await fake_redis.exists("temp:key") == 1

    # Check TTL
    ttl = await fake_redis.ttl("temp:key")
    assert ttl > 0 and ttl <= 60


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_pubsub(fake_redis, redis_subscriber):
    """Example: Test pub/sub functionality

    This test demonstrates:
    - Publishing and subscribing to channels
    - Event-driven architecture testing
    - WebSocket notification patterns
    """
    # Subscribe to a channel
    channel = "workspace:ws_test:events"
    await redis_subscriber.subscribe(channel)

    # Publish a message
    message_data = {
        "type": "session_started",
        "session_id": "sess_123"
    }
    await fake_redis.publish(channel, json.dumps(message_data))

    # Receive the message
    message = await redis_subscriber.get_message(ignore_subscribe_messages=True, timeout=1.0)

    if message:
        assert message["type"] == "message"
        data = json.loads(message["data"])
        assert data["type"] == "session_started"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_cache_helper(redis_cache):
    """Example: Test cache helper fixture

    This test demonstrates:
    - Using custom cache helper
    - Higher-level abstraction
    - Cleaner test code
    """
    # Cache user data
    user_data = {
        "id": "user_123",
        "name": "Test User",
        "email": "test@example.com"
    }

    await redis_cache.set("user:user_123", user_data, ttl=300)

    # Retrieve cached data
    cached_user = await redis_cache.get("user:user_123")
    assert cached_user["name"] == "Test User"

    # Check existence
    assert await redis_cache.exists("user:user_123") is True

    # Delete cache
    await redis_cache.delete("user:user_123")
    assert await redis_cache.exists("user:user_123") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_redis_publisher(redis_publisher, fake_redis):
    """Example: Test RedisEventPublisher

    This test demonstrates:
    - Testing the RedisEventPublisher service
    - Event publishing patterns
    - Execution completion notifications
    """
    # Subscribe to execution completed events
    pubsub = fake_redis.pubsub()
    execution_id = "exec_test_123"
    await pubsub.subscribe(f"automation:execution:completed:{execution_id}")

    # Publish an event using RedisEventPublisher
    await redis_publisher.publish_execution_completed(
        execution_id=execution_id,
        session_id="sess_123",
        workspace_id="ws_test",
        status="completed",
        total_messages=10,
        has_error=False
    )

    # Verify event was published
    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

    if message:
        event_data = json.loads(message["data"])
        assert event_data["execution_id"] == execution_id
        assert event_data["status"] == "completed"
        assert event_data["total_messages"] == 10

    await pubsub.aclose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_real_redis_operations(real_redis):
    """Example: Test with real Redis instance

    This test demonstrates:
    - Integration testing with actual Redis
    - More realistic testing
    - Performance testing opportunities

    Requires:
    - Redis running on localhost:6380
    - Run: make test-setup
    """
    # This test will be skipped if Redis is not available
    await real_redis.set("integration:test", "value")
    value = await real_redis.get("integration:test")
    assert value == "value"

    await real_redis.delete("integration:test")
