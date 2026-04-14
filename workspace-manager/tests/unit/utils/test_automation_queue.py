"""Tests for Automation Queue Manager"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from app.utils.automation_queue import AutomationQueueManager, get_queue_manager


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    mock_client = Mock()
    mock_client.zadd = Mock(return_value=1)
    mock_client.zrank = Mock(return_value=0)
    mock_client.zpopmin = Mock(return_value=[("execution_123", 1234567890.0)])
    mock_client.zrem = Mock(return_value=1)
    mock_client.zcard = Mock(return_value=5)
    mock_client.zrange = Mock(return_value=["execution_1", "execution_2"])
    mock_client.zremrangebyscore = Mock(return_value=2)
    mock_client.expire = Mock(return_value=True)
    return mock_client


@pytest.fixture
def queue_manager(mock_redis):
    """Create an AutomationQueueManager with mock Redis"""
    return AutomationQueueManager(mock_redis)


class TestAutomationQueueManager:
    """Test cases for AutomationQueueManager"""

    def test_init(self, mock_redis):
        """Test initialization"""
        manager = AutomationQueueManager(mock_redis)
        assert manager.redis == mock_redis

    def test_get_queue_key(self, queue_manager):
        """Test queue key generation"""
        key = queue_manager._get_queue_key("workspace_123")
        assert key == "automation:queue:workspace:workspace_123"

    @patch('app.utils.automation_queue.utcnow')
    def test_enqueue(self, mock_utcnow, queue_manager, mock_redis):
        """Test enqueuing a task"""
        mock_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_utcnow.return_value = mock_now
        mock_redis.zrank.return_value = 2  # Position in queue

        position = queue_manager.enqueue("workspace_123", "execution_123")

        assert position == 3  # zrank returns 0-based, position is 1-based
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_dequeue_success(self, queue_manager, mock_redis):
        """Test dequeuing a task successfully"""
        execution_id = queue_manager.dequeue("workspace_123")

        assert execution_id == "execution_123"
        mock_redis.zpopmin.assert_called_once()

    def test_dequeue_empty_queue(self, queue_manager, mock_redis):
        """Test dequeuing from empty queue"""
        mock_redis.zpopmin.return_value = []

        execution_id = queue_manager.dequeue("workspace_123")

        assert execution_id is None

    def test_cancel_success(self, queue_manager, mock_redis):
        """Test canceling a task successfully"""
        mock_redis.zrem.return_value = 1

        result = queue_manager.cancel("workspace_123", "execution_123")

        assert result is True
        mock_redis.zrem.assert_called_once()

    def test_cancel_not_in_queue(self, queue_manager, mock_redis):
        """Test canceling a task not in queue"""
        mock_redis.zrem.return_value = 0

        result = queue_manager.cancel("workspace_123", "execution_123")

        assert result is False

    def test_get_queue_position_exists(self, queue_manager, mock_redis):
        """Test getting queue position for existing task"""
        mock_redis.zrank.return_value = 3

        position = queue_manager.get_queue_position("workspace_123", "execution_123")

        assert position == 4  # zrank is 0-based, position is 1-based

    def test_get_queue_position_not_exists(self, queue_manager, mock_redis):
        """Test getting queue position for non-existing task"""
        mock_redis.zrank.return_value = None

        position = queue_manager.get_queue_position("workspace_123", "execution_123")

        assert position == 0

    def test_get_queue_length(self, queue_manager, mock_redis):
        """Test getting queue length"""
        mock_redis.zcard.return_value = 10

        length = queue_manager.get_queue_length("workspace_123")

        assert length == 10
        mock_redis.zcard.assert_called_once()

    def test_list_queued_executions(self, queue_manager, mock_redis):
        """Test listing queued executions"""
        mock_redis.zrange.return_value = ["exec_1", "exec_2", "exec_3"]

        executions = queue_manager.list_queued_executions("workspace_123", limit=10)

        assert executions == ["exec_1", "exec_2", "exec_3"]
        mock_redis.zrange.assert_called_once_with(
            "automation:queue:workspace:workspace_123", 0, 9
        )

    def test_list_queued_executions_default_limit(self, queue_manager, mock_redis):
        """Test listing queued executions with default limit"""
        executions = queue_manager.list_queued_executions("workspace_123")

        mock_redis.zrange.assert_called_once_with(
            "automation:queue:workspace:workspace_123", 0, 49
        )

    @patch('app.utils.automation_queue.utcnow')
    def test_cleanup_expired(self, mock_utcnow, queue_manager, mock_redis):
        """Test cleaning up expired tasks"""
        mock_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_utcnow.return_value = mock_now
        mock_redis.zremrangebyscore.return_value = 3

        removed = queue_manager.cleanup_expired("workspace_123", timeout_seconds=3600)

        assert removed == 3
        mock_redis.zremrangebyscore.assert_called_once()

    @patch('app.utils.automation_queue.utcnow')
    def test_cleanup_expired_none_removed(self, mock_utcnow, queue_manager, mock_redis):
        """Test cleanup when no expired tasks"""
        mock_now = datetime(2024, 1, 1, 12, 0, 0)
        mock_utcnow.return_value = mock_now
        mock_redis.zremrangebyscore.return_value = 0

        removed = queue_manager.cleanup_expired("workspace_123", timeout_seconds=3600)

        assert removed == 0

    def test_get_queue_info_empty_queue(self, queue_manager, mock_redis):
        """Test getting queue info for empty queue"""
        mock_redis.zcard.return_value = 0

        info = queue_manager.get_queue_info("workspace_123")

        assert info["workspace_id"] == "workspace_123"
        assert info["queue_length"] == 0
        assert info["oldest_queued_at"] is None
        assert info["newest_queued_at"] is None

    def test_get_queue_info_with_tasks(self, queue_manager, mock_redis):
        """Test getting queue info with tasks in queue"""
        mock_redis.zcard.return_value = 5
        mock_redis.zrange.side_effect = [
            [("execution_1", 1704110400.0)],  # oldest
            [("execution_5", 1704114000.0)]   # newest
        ]

        info = queue_manager.get_queue_info("workspace_123")

        assert info["workspace_id"] == "workspace_123"
        assert info["queue_length"] == 5
        assert isinstance(info["oldest_queued_at"], datetime)
        assert isinstance(info["newest_queued_at"], datetime)

    def test_get_queue_info_with_tasks_no_scores(self, queue_manager, mock_redis):
        """Test getting queue info when zrange returns empty"""
        mock_redis.zcard.return_value = 5
        mock_redis.zrange.side_effect = [[], []]  # Empty results

        info = queue_manager.get_queue_info("workspace_123")

        assert info["workspace_id"] == "workspace_123"
        assert info["queue_length"] == 5
        assert info["oldest_queued_at"] is None
        assert info["newest_queued_at"] is None


class TestGetQueueManager:
    """Test cases for get_queue_manager function"""

    @patch('app.utils.automation_queue.redis.from_url')
    @patch('app.config.settings.get_settings')
    def test_get_queue_manager(self, mock_get_settings, mock_from_url):
        """Test getting queue manager instance"""
        mock_settings = Mock()
        mock_settings.REDIS_URL = "redis://localhost:6379/0"
        mock_get_settings.return_value = mock_settings

        mock_redis = Mock()
        mock_from_url.return_value = mock_redis

        manager = get_queue_manager()

        assert isinstance(manager, AutomationQueueManager)
        assert manager.redis == mock_redis
        mock_from_url.assert_called_once_with(
            "redis://localhost:6379/0",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
