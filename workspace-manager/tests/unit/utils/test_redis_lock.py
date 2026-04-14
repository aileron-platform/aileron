"""Tests for Redis Lock utility"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from app.utils.redis_lock import RedisLock, workspace_lock, get_workspace_lock_info


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    mock_client = Mock()
    mock_client.set = Mock(return_value=True)
    mock_client.get = Mock(return_value="test_value")
    mock_client.eval = Mock(return_value=1)
    mock_client.ttl = Mock(return_value=3600)
    mock_client.close = Mock()
    return mock_client


class TestRedisLock:
    """Test cases for RedisLock class"""

    def test_init(self, mock_redis):
        """Test RedisLock initialization"""
        lock = RedisLock(mock_redis, "test_key", timeout=3600)
        assert lock.redis == mock_redis
        assert lock.key == "test_key"
        assert lock.timeout == 3600
        assert lock.lock_value is None

    def test_acquire_non_blocking_success(self, mock_redis):
        """Test non-blocking acquire success"""
        mock_redis.set.return_value = True
        lock = RedisLock(mock_redis, "test_key")

        result = lock.acquire(blocking=False)

        assert result is True
        assert lock.lock_value is not None
        mock_redis.set.assert_called_once()

    def test_acquire_non_blocking_fail(self, mock_redis):
        """Test non-blocking acquire failure"""
        mock_redis.set.return_value = False
        lock = RedisLock(mock_redis, "test_key")

        result = lock.acquire(blocking=False)

        assert result is False
        mock_redis.set.assert_called_once()

    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_blocking_success(self, mock_sleep, mock_time, mock_redis):
        """Test blocking acquire success"""
        mock_time.side_effect = [0, 0.1, 0.2]  # Simulate time passing
        mock_redis.set.return_value = True
        lock = RedisLock(mock_redis, "test_key", timeout=10)

        result = lock.acquire(blocking=True, block_timeout=5)

        assert result is True
        assert lock.lock_value is not None

    @patch('time.time')
    @patch('time.sleep')
    def test_acquire_blocking_timeout(self, mock_sleep, mock_time, mock_redis):
        """Test blocking acquire timeout"""
        # Simulate timeout by making time advance past the limit
        mock_time.side_effect = [0, 6]  # Exceeds 5 second timeout
        mock_redis.set.return_value = False
        lock = RedisLock(mock_redis, "test_key", timeout=10)

        result = lock.acquire(blocking=True, block_timeout=5)

        assert result is False

    def test_release_success(self, mock_redis):
        """Test successful lock release"""
        mock_redis.eval.return_value = 1
        lock = RedisLock(mock_redis, "test_key")
        lock.lock_value = "test_value"

        result = lock.release()

        assert result is True
        mock_redis.eval.assert_called_once()

    def test_release_without_lock_value(self, mock_redis):
        """Test release without acquiring lock first"""
        lock = RedisLock(mock_redis, "test_key")

        result = lock.release()

        assert result is False
        mock_redis.eval.assert_not_called()

    def test_release_failed(self, mock_redis):
        """Test failed lock release (lock owned by another process)"""
        mock_redis.eval.return_value = 0
        lock = RedisLock(mock_redis, "test_key")
        lock.lock_value = "test_value"

        result = lock.release()

        assert result is False

    def test_extend_success(self, mock_redis):
        """Test successful lock extension"""
        mock_redis.eval.return_value = 1
        lock = RedisLock(mock_redis, "test_key")
        lock.lock_value = "test_value"

        result = lock.extend(60)

        assert result is True
        mock_redis.eval.assert_called_once()

    def test_extend_without_lock_value(self, mock_redis):
        """Test extend without acquiring lock first"""
        lock = RedisLock(mock_redis, "test_key")

        result = lock.extend(60)

        assert result is False
        mock_redis.eval.assert_not_called()

    def test_extend_failed(self, mock_redis):
        """Test failed lock extension"""
        mock_redis.eval.return_value = 0
        lock = RedisLock(mock_redis, "test_key")
        lock.lock_value = "test_value"

        result = lock.extend(60)

        assert result is False


class TestWorkspaceLock:
    """Test cases for workspace_lock context manager"""

    @patch('app.utils.redis_lock._get_redis_client')
    def test_workspace_lock_acquired(self, mock_get_redis):
        """Test workspace lock successfully acquired"""
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        with workspace_lock("workspace_123") as acquired:
            assert acquired is True

        mock_redis.close.assert_called_once()

    @patch('app.utils.redis_lock._get_redis_client')
    def test_workspace_lock_not_acquired(self, mock_get_redis):
        """Test workspace lock not acquired"""
        mock_redis = Mock()
        mock_redis.set.return_value = False
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        with workspace_lock("workspace_123") as acquired:
            assert acquired is False

        # Release should not be called if lock was not acquired
        mock_redis.close.assert_called_once()

    @patch('app.utils.redis_lock._get_redis_client')
    def test_workspace_lock_exception_handling(self, mock_get_redis):
        """Test workspace lock releases on exception"""
        mock_redis = Mock()
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        try:
            with workspace_lock("workspace_123") as acquired:
                assert acquired is True
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should be released even if exception occurs
        mock_redis.eval.assert_called_once()
        mock_redis.close.assert_called_once()


class TestGetWorkspaceLockInfo:
    """Test cases for get_workspace_lock_info function"""

    @patch('app.utils.redis_lock._get_redis_client')
    def test_get_lock_info_exists(self, mock_get_redis):
        """Test get lock info when lock exists"""
        mock_redis = Mock()
        mock_redis.get.return_value = "lock_value_123"
        mock_redis.ttl.return_value = 3500
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        result = get_workspace_lock_info("workspace_123")

        assert result is not None
        assert result["locked"] is True
        assert result["lock_value"] == "lock_value_123"
        assert result["ttl"] == 3500
        assert result["workspace_id"] == "workspace_123"
        mock_redis.close.assert_called_once()

    @patch('app.utils.redis_lock._get_redis_client')
    def test_get_lock_info_not_exists(self, mock_get_redis):
        """Test get lock info when lock does not exist"""
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        result = get_workspace_lock_info("workspace_123")

        assert result is None
        mock_redis.close.assert_called_once()

    @patch('app.utils.redis_lock._get_redis_client')
    def test_get_lock_info_closes_client_on_error(self, mock_get_redis):
        """Test get lock info closes client even on error"""
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_redis.close = Mock()
        mock_get_redis.return_value = mock_redis

        with pytest.raises(Exception):
            get_workspace_lock_info("workspace_123")

        mock_redis.close.assert_called_once()
