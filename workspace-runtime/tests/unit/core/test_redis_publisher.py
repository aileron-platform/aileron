"""Redis Publisher Unit Tests"""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, patch

from app.core.redis_publisher import RedisEventPublisher, get_redis_publisher


@pytest.fixture
def redis_publisher():
    """Redis publisher fixture."""
    return RedisEventPublisher()


@pytest.fixture
def mock_redis():
    """Mock Redis client fixture."""
    mock = AsyncMock()
    mock.ping = AsyncMock()
    mock.publish = AsyncMock()
    mock.setex = AsyncMock()
    mock.close = AsyncMock()
    return mock


class TestPublishExecutionCompleted:
    """Test publishing execution completed events"""

    @pytest.mark.asyncio
    async def test_publish_execution_completed_success(self, redis_publisher, mock_redis):
        """Test successful publish of execution completed event"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)
            execution_id = "exec-123"
            session_id = "session-456"
            workspace_id = "workspace-789"
            status = "completed"
            total_messages = 10
            has_error = False

            # Act
            await redis_publisher.publish_execution_completed(
                execution_id=execution_id,
                session_id=session_id,
                workspace_id=workspace_id,
                status=status,
                total_messages=total_messages,
                has_error=has_error,
            )

            # Assert
            mock_redis.publish.assert_called_once()
            channel, message = mock_redis.publish.call_args[0]
            assert channel == f"automation:execution:completed:{execution_id}"

            message_data = json.loads(message)
            assert message_data["execution_id"] == execution_id
            assert message_data["session_id"] == session_id
            assert message_data["workspace_id"] == workspace_id
            assert message_data["status"] == status
            assert message_data["total_messages"] == total_messages
            assert message_data["has_error"] == has_error
            assert message_data["error_message"] is None

            # Verify result key is set
            mock_redis.setex.assert_called_once()
            result_key, ttl, result_message = mock_redis.setex.call_args[0]
            assert result_key == f"automation:execution:result:{execution_id}"
            assert ttl == 3600
            assert result_message == message

    @pytest.mark.asyncio
    async def test_publish_execution_completed_with_error(self, redis_publisher, mock_redis):
        """Test publishing execution completed event with error"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)
            execution_id = "exec-123"
            session_id = "session-456"
            workspace_id = "workspace-789"
            status = "failed"
            total_messages = 5
            has_error = True
            error_message = "Test error occurred"

            # Act
            await redis_publisher.publish_execution_completed(
                execution_id=execution_id,
                session_id=session_id,
                workspace_id=workspace_id,
                status=status,
                total_messages=total_messages,
                has_error=has_error,
                error_message=error_message,
            )

            # Assert
            mock_redis.publish.assert_called_once()
            channel, message = mock_redis.publish.call_args[0]
            message_data = json.loads(message)
            assert message_data["has_error"] is True
            assert message_data["error_message"] == error_message
            assert message_data["status"] == status

    @pytest.mark.asyncio
    async def test_publish_execution_completed_redis_failure(self, redis_publisher, mock_redis):
        """Test Redis publish failure does not raise exception"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_redis.publish.side_effect = Exception("Redis publish failed")
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)

            # Act - Should not raise exception
            await redis_publisher.publish_execution_completed(
                execution_id="exec-123",
                session_id="session-456",
                workspace_id="workspace-789",
                status="completed",
                total_messages=10,
                has_error=False,
            )

            # Assert
            mock_redis.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_execution_completed_setex_failure(self, redis_publisher, mock_redis):
        """Test setex failure does not raise exception"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_redis.setex.side_effect = Exception("Redis setex failed")
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)

            # Act - Should not raise exception
            await redis_publisher.publish_execution_completed(
                execution_id="exec-123",
                session_id="session-456",
                workspace_id="workspace-789",
                status="completed",
                total_messages=10,
                has_error=False,
            )

            # Assert
            mock_redis.publish.assert_called_once()


class TestClose:
    """Test closing Redis connection"""

    @pytest.mark.asyncio
    async def test_close_calls_redis_manager(self, redis_publisher):
        """Test close calls redis_manager.close"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.close = AsyncMock()

            # Act
            await redis_publisher.close()

            # Assert
            mock_manager.close.assert_called_once()


class TestGetRedisPublisher:
    """Test getting Redis Publisher singleton"""

    def test_get_redis_publisher_singleton(self):
        """Test singleton pattern"""
        # Reset global singleton for test
        import app.core.redis_publisher as publisher_module
        publisher_module._publisher = None

        # Act
        publisher1 = get_redis_publisher()
        publisher2 = get_redis_publisher()

        # Assert
        assert publisher1 is publisher2
        assert isinstance(publisher1, RedisEventPublisher)

    def test_get_redis_publisher_returns_instance(self):
        """Test returning correct instance"""
        # Reset global singleton for test
        import app.core.redis_publisher as publisher_module
        publisher_module._publisher = None

        # Act
        publisher = get_redis_publisher()

        # Assert
        assert isinstance(publisher, RedisEventPublisher)


class TestRedisEventData:
    """Test event data structure"""

    @pytest.mark.asyncio
    async def test_event_data_structure_complete(self, redis_publisher, mock_redis):
        """Test complete event data structure"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)

            # Act
            await redis_publisher.publish_execution_completed(
                execution_id="exec-001",
                session_id="session-002",
                workspace_id="workspace-003",
                status="completed",
                total_messages=15,
                has_error=False,
                error_message=None,
            )

            # Assert
            channel, message = mock_redis.publish.call_args[0]
            event_data = json.loads(message)

            # Verify all required fields exist
            assert "execution_id" in event_data
            assert "session_id" in event_data
            assert "workspace_id" in event_data
            assert "status" in event_data
            assert "total_messages" in event_data
            assert "has_error" in event_data
            assert "error_message" in event_data

            # Verify data types
            assert isinstance(event_data["execution_id"], str)
            assert isinstance(event_data["session_id"], str)
            assert isinstance(event_data["workspace_id"], str)
            assert isinstance(event_data["status"], str)
            assert isinstance(event_data["total_messages"], int)
            assert isinstance(event_data["has_error"], bool)


class TestChannelNaming:
    """Test channel naming"""

    @pytest.mark.asyncio
    async def test_channel_naming_convention(self, redis_publisher, mock_redis):
        """Test channel naming convention"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)
            execution_id = "test-exec-123"

            # Act
            await redis_publisher.publish_execution_completed(
                execution_id=execution_id,
                session_id="session",
                workspace_id="workspace",
                status="completed",
                total_messages=1,
                has_error=False,
            )

            # Assert
            channel, _ = mock_redis.publish.call_args[0]
            assert channel == f"automation:execution:completed:{execution_id}"
            assert channel.startswith("automation:execution:completed:")

    @pytest.mark.asyncio
    async def test_result_key_naming_convention(self, redis_publisher, mock_redis):
        """Test result key naming convention"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(return_value=mock_redis)
            execution_id = "test-exec-456"

            # Act
            await redis_publisher.publish_execution_completed(
                execution_id=execution_id,
                session_id="session",
                workspace_id="workspace",
                status="completed",
                total_messages=1,
                has_error=False,
            )

            # Assert
            result_key, _, _ = mock_redis.setex.call_args[0]
            assert result_key == f"automation:execution:result:{execution_id}"
            assert result_key.startswith("automation:execution:result:")


class TestErrorHandling:
    """Test error handling"""

    @pytest.mark.asyncio
    async def test_handles_get_redis_exception_gracefully(self, redis_publisher):
        """Test get_redis exception is handled gracefully"""
        # Arrange
        with patch("app.core.redis_publisher.redis_manager") as mock_manager:
            mock_manager.get_redis = AsyncMock(side_effect=Exception("Connection error"))

            # Act - Should not raise exception to caller
            await redis_publisher.publish_execution_completed(
                execution_id="exec",
                session_id="session",
                workspace_id="workspace",
                status="completed",
                total_messages=1,
                has_error=False,
            )

            # Assert - Method should complete without raising exception
            mock_manager.get_redis.assert_called_once()
