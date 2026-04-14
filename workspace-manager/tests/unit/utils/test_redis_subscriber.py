"""Tests for Redis Event Subscriber"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.utils.redis_subscriber import RedisEventSubscriber, wait_for_execution_completed_sync


@pytest.fixture
def mock_redis():
    """Create a mock async Redis client"""
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.close = AsyncMock()
    return mock_client


@pytest.fixture
def mock_pubsub():
    """Create a mock pubsub object"""
    mock_ps = AsyncMock()
    mock_ps.subscribe = AsyncMock()
    mock_ps.unsubscribe = AsyncMock()
    mock_ps.close = AsyncMock()
    mock_ps.get_message = AsyncMock(return_value=None)
    return mock_ps


class TestRedisEventSubscriber:
    """Test cases for RedisEventSubscriber class"""

    @pytest.mark.asyncio
    async def test_get_redis_success(self):
        """Test successful Redis connection"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock) as mock_from_url:
            mock_from_url.return_value = mock_redis

            subscriber = RedisEventSubscriber()
            redis = await subscriber.get_redis()

            assert redis is not None
            mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_redis_reuses_connection(self):
        """Test that get_redis reuses existing connection"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock) as mock_from_url:
            mock_from_url.return_value = mock_redis

            subscriber = RedisEventSubscriber()
            redis1 = await subscriber.get_redis()
            redis2 = await subscriber.get_redis()

            assert redis1 is redis2
            # ping should only be called once
            assert mock_redis.ping.call_count == 1

    @pytest.mark.asyncio
    async def test_get_redis_connection_failed(self):
        """Test Redis connection failure"""
        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock) as mock_from_url:
            mock_from_url.side_effect = Exception("Connection failed")

            subscriber = RedisEventSubscriber()

            with pytest.raises(Exception) as exc_info:
                await subscriber.get_redis()

            assert "Connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_from_key(self, mock_redis):
        """Test waiting for execution completed with existing result in Redis"""
        result_data = {"status": "completed", "result": "success"}
        mock_redis.get = AsyncMock(return_value=json.dumps(result_data))

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

            assert result == result_data
            mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_from_pubsub(self, mock_redis, mock_pubsub):
        """Test waiting for execution completed via pubsub"""
        result_data = {"status": "completed", "result": "success"}
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pubsub = Mock(return_value=mock_pubsub)

        # Simulate receiving a message
        mock_message = {
            "type": "message",
            "data": json.dumps(result_data)
        }
        mock_pubsub.get_message = AsyncMock(return_value=mock_message)

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

            assert result == result_data
            mock_pubsub.subscribe.assert_called_once()
            mock_pubsub.unsubscribe.assert_called_once()
            mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_timeout(self, mock_redis, mock_pubsub):
        """Test timeout when waiting for execution completed"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pubsub = Mock(return_value=mock_pubsub)
        mock_pubsub.get_message = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            with patch('asyncio.get_event_loop') as mock_loop:
                mock_loop.return_value.time.side_effect = [0, 0.5, 11]  # Simulate timeout

                subscriber = RedisEventSubscriber()
                result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

                assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_invalid_json(self, mock_redis, mock_pubsub):
        """Test handling of invalid JSON in pubsub message"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pubsub = Mock(return_value=mock_pubsub)

        # Simulate receiving a message with invalid JSON
        mock_message = {
            "type": "message",
            "data": "invalid json"
        }
        mock_pubsub.get_message = AsyncMock(return_value=mock_message)

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

            assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_existing_result_invalid_json(self, mock_redis):
        """Test handling of invalid JSON in existing result"""
        mock_redis.get = AsyncMock(return_value="invalid json")
        mock_redis.pubsub = Mock(return_value=AsyncMock())

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            # Should continue to pubsub if existing result is invalid
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=1)

            # Will timeout because pubsub returns nothing
            assert result is None

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_exception(self, mock_redis, mock_pubsub):
        """Test exception handling during wait"""
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pubsub = Mock(return_value=mock_pubsub)
        mock_pubsub.subscribe = AsyncMock(side_effect=Exception("Subscription failed"))

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

            assert result is None
            # Should still attempt to clean up
            mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_execution_completed_cleanup_on_error(self, mock_redis, mock_pubsub):
        """Test that result is still returned even if cleanup fails"""
        result_data = {"status": "completed"}
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.pubsub = Mock(return_value=mock_pubsub)

        mock_message = {
            "type": "message",
            "data": json.dumps(result_data)
        }
        mock_pubsub.get_message = AsyncMock(return_value=mock_message)
        mock_pubsub.unsubscribe = AsyncMock(side_effect=Exception("Unsubscribe failed"))

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            result = await subscriber.wait_for_execution_completed("exec_123", timeout=10)

            # Should still return the result even if cleanup fails
            assert result == result_data
            # Note: close() won't be called if unsubscribe() raises an exception
            mock_pubsub.unsubscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing Redis connection"""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_redis.close = AsyncMock()

        with patch('app.utils.redis_subscriber.aioredis.from_url', new_callable=AsyncMock, return_value=mock_redis):
            subscriber = RedisEventSubscriber()
            await subscriber.get_redis()
            await subscriber.close()

            mock_redis.close.assert_called_once()
            assert subscriber._redis is None

    @pytest.mark.asyncio
    async def test_close_without_connection(self):
        """Test closing when no connection exists"""
        subscriber = RedisEventSubscriber()
        await subscriber.close()

        # Should not raise an error
        assert subscriber._redis is None


class TestWaitForExecutionCompletedSync:
    """Test cases for wait_for_execution_completed_sync function"""

    @patch('app.utils.redis_subscriber.RedisEventSubscriber')
    @patch('asyncio.set_event_loop')
    @patch('asyncio.new_event_loop')
    def test_sync_wait_success(self, mock_new_loop, mock_set_loop, mock_subscriber_class):
        """Test synchronous wait with successful result"""
        result_data = {"status": "completed"}

        # Create mock subscriber instance
        mock_subscriber = Mock()
        mock_subscriber.wait_for_execution_completed = Mock(return_value=result_data)
        mock_subscriber.close = Mock(return_value=None)
        mock_subscriber_class.return_value = mock_subscriber

        # Create mock event loop
        mock_loop = Mock()
        mock_loop.run_until_complete = Mock(side_effect=[result_data, None])
        mock_loop.close = Mock()
        mock_new_loop.return_value = mock_loop

        result = wait_for_execution_completed_sync("exec_123", timeout=10)

        assert result == result_data
        mock_set_loop.assert_called_once_with(mock_loop)
        mock_loop.close.assert_called_once()

    @patch('app.utils.redis_subscriber.RedisEventSubscriber')
    @patch('asyncio.set_event_loop')
    @patch('asyncio.new_event_loop')
    def test_sync_wait_timeout(self, mock_new_loop, mock_set_loop, mock_subscriber_class):
        """Test synchronous wait with timeout"""
        # Create mock subscriber instance
        mock_subscriber = Mock()
        mock_subscriber.wait_for_execution_completed = Mock(return_value=None)
        mock_subscriber.close = Mock(return_value=None)
        mock_subscriber_class.return_value = mock_subscriber

        # Create mock event loop
        mock_loop = Mock()
        mock_loop.run_until_complete = Mock(side_effect=[None, None])
        mock_loop.close = Mock()
        mock_new_loop.return_value = mock_loop

        result = wait_for_execution_completed_sync("exec_123", timeout=5)

        assert result is None
        mock_set_loop.assert_called_once_with(mock_loop)
        mock_loop.close.assert_called_once()
