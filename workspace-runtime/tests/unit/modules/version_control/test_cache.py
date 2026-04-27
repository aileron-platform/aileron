"""Git Cache unit tests"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, Mock, patch

import pytest
from redis.exceptions import RedisError

from app.modules.version_control.cache import (
    CacheKeys,
    CacheTTL,
    GitCache,
    create_git_cache,
)


class TestGitCache:
    """GitCache tests"""

    def test_init_with_redis_client(self):
        """Test initialization with Redis client"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=600, enabled=True)

        assert cache.redis == mock_redis
        assert cache.ttl == 600
        assert cache.enabled is True
        assert cache.prefix == "git:cache:"

    def test_init_without_redis_client(self):
        """Test cache disabled when no Redis client"""
        cache = GitCache(redis_client=None, enabled=True)

        assert cache.redis is None
        assert cache.enabled is False

    def test_init_disabled(self):
        """Test explicitly disable cache"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, enabled=False)

        assert cache.enabled is False

    def test_make_key_basic(self):
        """Test generate basic cache key"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key = cache._make_key("workspace-1", "changes")

        assert key.startswith("git:cache:workspace-1:changes:")
        assert len(key.split(":")) == 5  # prefix:workspace:operation:hash

    def test_make_key_with_params(self):
        """Test generate cache key with parameters"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key1 = cache._make_key("workspace-1", "commits", branch="main", limit=10)
        key2 = cache._make_key("workspace-1", "commits", branch="main", limit=10)
        key3 = cache._make_key("workspace-1", "commits", branch="dev", limit=10)

        # Same parameters should generate same key
        assert key1 == key2
        # Different parameters should generate different keys
        assert key1 != key3

    def test_make_key_params_order_independent(self):
        """Test parameter order does not affect key generation"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key1 = cache._make_key("ws-1", "op", a=1, b=2, c=3)
        key2 = cache._make_key("ws-1", "op", c=3, a=1, b=2)

        assert key1 == key2

    def test_get_disabled(self):
        """Test get returns None when cache disabled"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_cache_hit(self):
        """Test cache hit"""
        mock_redis = Mock()
        test_data = {"status": "ok", "files": ["file1.py"]}
        mock_redis.get.return_value = json.dumps(test_data)

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result == test_data
        mock_redis.get.assert_called_once()

    def test_get_cache_miss(self):
        """Test cache miss"""
        mock_redis = Mock()
        mock_redis.get.return_value = None

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_redis_error(self):
        """Test return None on Redis error"""
        mock_redis = Mock()
        mock_redis.get.side_effect = RedisError("Connection failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_json_decode_error(self):
        """Test return None on JSON decode error"""
        mock_redis = Mock()
        mock_redis.get.return_value = "invalid json"

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_set_disabled(self):
        """Test set returns False when cache disabled"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.set("workspace-1", "changes", {"data": "test"})

        assert result is False

    def test_set_success(self):
        """Test successful cache set"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=300, enabled=True)

        test_data = {"status": "ok", "count": 5}
        result = cache.set("workspace-1", "changes", test_data)

        assert result is True
        mock_redis.setex.assert_called_once()
        # Check call parameters
        call_args = mock_redis.setex.call_args
        assert "workspace-1" in call_args[0][0]  # key contains workspace id
        assert json.loads(call_args[0][1]) == test_data  # data is correct

    def test_set_with_custom_ttl(self):
        """Test using custom TTL"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=300, enabled=True)

        result = cache.set("ws-1", "data", {"test": 1}, ttl=600)

        assert result is True
        # Check TTL parameter
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == 600

    def test_set_redis_error(self):
        """Test return False on Redis error"""
        mock_redis = Mock()
        mock_redis.setex.side_effect = RedisError("Write failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.set("ws-1", "data", {"test": 1})

        assert result is False

    def test_set_serialization_error(self):
        """Test return False on serialization error"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, enabled=True)

        # Try to serialize unserializable object
        class UnserializableObject:
            pass

        # Use custom JSON dumps to avoid default str() conversion
        with patch("app.modules.version_control.cache.json.dumps") as mock_dumps:
            mock_dumps.side_effect = TypeError("Object not serializable")
            result = cache.set("ws-1", "data", {"obj": UnserializableObject()})

        assert result is False

    def test_invalidate_disabled(self):
        """Test invalidate returns 0 when cache disabled"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.invalidate("workspace-1", "changes")

        assert result == 0

    def test_invalidate_with_pattern(self):
        """Test invalidate using pattern"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [
            "git:cache:ws-1:changes:abc123",
            "git:cache:ws-1:changes:def456",
        ]
        mock_redis.delete.return_value = 2

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate("ws-1", "changes")

        assert result == 2
        mock_redis.delete.assert_called_once()

    def test_invalidate_auto_add_wildcard(self):
        """Test auto add wildcard"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        cache.invalidate("ws-1", "changes")

        # Check scan_iter used correct pattern
        call_args = mock_redis.scan_iter.call_args
        assert call_args[1]["match"] == "git:cache:ws-1:changes:*"

    def test_invalidate_no_keys(self):
        """Test return 0 when no matching keys"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate("ws-1", "changes")

        assert result == 0

    def test_invalidate_redis_error(self):
        """Test return 0 on Redis error"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Scan failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate("ws-1", "changes")

        assert result == 0

    def test_invalidate_all(self):
        """Test invalidate all cache"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [
            "git:cache:ws-1:changes:abc",
            "git:cache:ws-1:status:def",
        ]
        mock_redis.delete.return_value = 2

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate_all("ws-1")

        assert result == 2

    def test_get_stats_disabled(self):
        """Test statistics info when cache disabled"""
        cache = GitCache(redis_client=None, enabled=False)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is False
        assert stats["total_keys"] == 0
        assert stats["memory_usage"] == 0

    def test_get_stats_success(self):
        """Test successfully get statistics info"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [
            "git:cache:ws-1:key1",
            "git:cache:ws-1:key2",
        ]
        mock_redis.memory_usage.return_value = 1024

        cache = GitCache(redis_client=mock_redis, enabled=True)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is True
        assert stats["total_keys"] == 2
        assert stats["memory_usage"] > 0

    def test_get_stats_memory_usage_error(self):
        """Test continue on memory usage query failure"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = ["git:cache:ws-1:key1"]
        mock_redis.memory_usage.side_effect = RedisError("Memory command failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is True
        assert stats["total_keys"] == 1
        assert stats["memory_usage"] == 0

    def test_get_stats_redis_error(self):
        """Test return error stats on Redis error"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Scan failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is True
        assert "error" in stats

    def test_clear_all_disabled(self):
        """Test clear_all returns 0 when cache disabled"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.clear_all()

        assert result == 0

    def test_clear_all_success(self):
        """Test successfully clear all cache"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = [
            "git:cache:ws-1:key1",
            "git:cache:ws-2:key2",
        ]
        mock_redis.delete.return_value = 2

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.clear_all()

        assert result == 2
        mock_redis.delete.assert_called_once()

    def test_clear_all_no_keys(self):
        """Test return 0 when no keys"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.clear_all()

        assert result == 0

    def test_clear_all_redis_error(self):
        """Test return 0 on Redis error"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Clear failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.clear_all()

        assert result == 0


class TestCacheKeys:
    """CacheKeys constant tests"""

    def test_cache_keys_values(self):
        """Test cache key constant values"""
        assert CacheKeys.CHANGES == "changes"
        assert CacheKeys.STATUS == "status"
        assert CacheKeys.BRANCHES == "branches"
        assert CacheKeys.COMMITS == "commits"
        assert CacheKeys.COMMIT_DETAIL == "commit_detail"
        assert CacheKeys.COMMIT_FILES == "commit_files"
        assert CacheKeys.DIFF == "diff"
        assert CacheKeys.BLOB == "blob"


class TestCacheTTL:
    """CacheTTL constant tests"""

    def test_cache_ttl_values(self):
        """Test cache TTL constant values"""
        assert CacheTTL.VERY_SHORT == 10
        assert CacheTTL.SHORT == 30
        assert CacheTTL.MEDIUM == 300
        assert CacheTTL.LONG == 1800
        assert CacheTTL.VERY_LONG == 3600


class TestCreateGitCache:
    """create_git_cache utility function tests"""

    def test_create_disabled_by_config(self):
        """Test disable cache through config"""
        cache = create_git_cache(redis_url="redis://localhost", enabled=False)

        assert cache.enabled is False

    def test_create_without_redis_url(self):
        """Test disable cache when no Redis URL"""
        cache = create_git_cache(redis_url=None, enabled=True)

        assert cache.enabled is False

    @patch("app.modules.version_control.cache.Redis")
    def test_create_success(self, mock_redis_class):
        """Test successfully create cache"""
        mock_redis_instance = Mock()
        mock_redis_instance.ping.return_value = True
        mock_redis_class.from_url.return_value = mock_redis_instance

        cache = create_git_cache(redis_url="redis://localhost:6379/0", enabled=True)

        assert cache.enabled is True
        assert cache.redis == mock_redis_instance
        mock_redis_class.from_url.assert_called_once()
        mock_redis_instance.ping.assert_called_once()

    @patch("app.modules.version_control.cache.Redis")
    def test_create_connection_failure(self, mock_redis_class):
        """Test disable cache on Redis connection failure"""
        mock_redis_class.from_url.side_effect = RedisError("Connection failed")

        cache = create_git_cache(redis_url="redis://localhost:6379/0", enabled=True)

        assert cache.enabled is False

    @patch("app.modules.version_control.cache.Redis")
    def test_create_ping_failure(self, mock_redis_class):
        """Test disable cache on Redis ping failure"""
        mock_redis_instance = Mock()
        mock_redis_instance.ping.side_effect = RedisError("Ping failed")
        mock_redis_class.from_url.return_value = mock_redis_instance

        cache = create_git_cache(redis_url="redis://localhost:6379/0", enabled=True)

        assert cache.enabled is False
