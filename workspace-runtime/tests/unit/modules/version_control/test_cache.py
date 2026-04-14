"""Git Cache 單元測試"""

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
    """GitCache 測試"""

    def test_init_with_redis_client(self):
        """測試使用 Redis 客戶端初始化"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=600, enabled=True)

        assert cache.redis == mock_redis
        assert cache.ttl == 600
        assert cache.enabled is True
        assert cache.prefix == "git:cache:"

    def test_init_without_redis_client(self):
        """測試沒有 Redis 客戶端時禁用快取"""
        cache = GitCache(redis_client=None, enabled=True)

        assert cache.redis is None
        assert cache.enabled is False

    def test_init_disabled(self):
        """測試明確禁用快取"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, enabled=False)

        assert cache.enabled is False

    def test_make_key_basic(self):
        """測試生成基本快取鍵"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key = cache._make_key("workspace-1", "changes")

        assert key.startswith("git:cache:workspace-1:changes:")
        assert len(key.split(":")) == 5  # prefix:workspace:operation:hash

    def test_make_key_with_params(self):
        """測試生成帶參數的快取鍵"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key1 = cache._make_key("workspace-1", "commits", branch="main", limit=10)
        key2 = cache._make_key("workspace-1", "commits", branch="main", limit=10)
        key3 = cache._make_key("workspace-1", "commits", branch="dev", limit=10)

        # 相同參數應該生成相同的鍵
        assert key1 == key2
        # 不同參數應該生成不同的鍵
        assert key1 != key3

    def test_make_key_params_order_independent(self):
        """測試參數順序不影響鍵生成"""
        cache = GitCache(redis_client=Mock(), enabled=True)
        key1 = cache._make_key("ws-1", "op", a=1, b=2, c=3)
        key2 = cache._make_key("ws-1", "op", c=3, a=1, b=2)

        assert key1 == key2

    def test_get_disabled(self):
        """測試快取禁用時 get 返回 None"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_cache_hit(self):
        """測試快取命中"""
        mock_redis = Mock()
        test_data = {"status": "ok", "files": ["file1.py"]}
        mock_redis.get.return_value = json.dumps(test_data)

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result == test_data
        mock_redis.get.assert_called_once()

    def test_get_cache_miss(self):
        """測試快取未命中"""
        mock_redis = Mock()
        mock_redis.get.return_value = None

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_redis_error(self):
        """測試 Redis 錯誤時返回 None"""
        mock_redis = Mock()
        mock_redis.get.side_effect = RedisError("Connection failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_get_json_decode_error(self):
        """測試 JSON 解析錯誤時返回 None"""
        mock_redis = Mock()
        mock_redis.get.return_value = "invalid json"

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.get("workspace-1", "changes")

        assert result is None

    def test_set_disabled(self):
        """測試快取禁用時 set 返回 False"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.set("workspace-1", "changes", {"data": "test"})

        assert result is False

    def test_set_success(self):
        """測試成功設定快取"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=300, enabled=True)

        test_data = {"status": "ok", "count": 5}
        result = cache.set("workspace-1", "changes", test_data)

        assert result is True
        mock_redis.setex.assert_called_once()
        # 檢查調用參數
        call_args = mock_redis.setex.call_args
        assert "workspace-1" in call_args[0][0]  # key contains workspace id
        assert json.loads(call_args[0][2]) == test_data  # data is correct

    def test_set_with_custom_ttl(self):
        """測試使用自定義 TTL"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, ttl=300, enabled=True)

        result = cache.set("ws-1", "data", {"test": 1}, ttl=600)

        assert result is True
        # 檢查 TTL 參數
        call_args = mock_redis.setex.call_args
        assert call_args[0][1].total_seconds() == 600

    def test_set_redis_error(self):
        """測試 Redis 錯誤時返回 False"""
        mock_redis = Mock()
        mock_redis.setex.side_effect = RedisError("Write failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.set("ws-1", "data", {"test": 1})

        assert result is False

    def test_set_serialization_error(self):
        """測試序列化錯誤時返回 False"""
        mock_redis = Mock()
        cache = GitCache(redis_client=mock_redis, enabled=True)

        # 嘗試序列化無法序列化的對象
        class UnserializableObject:
            pass

        # 使用自定義的 JSON dumps 來避免默認的 str() 轉換
        with patch("app.modules.version_control.cache.json.dumps") as mock_dumps:
            mock_dumps.side_effect = TypeError("Object not serializable")
            result = cache.set("ws-1", "data", {"obj": UnserializableObject()})

        assert result is False

    def test_invalidate_disabled(self):
        """測試快取禁用時 invalidate 返回 0"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.invalidate("workspace-1", "changes")

        assert result == 0

    def test_invalidate_with_pattern(self):
        """測試使用模式使快取失效"""
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
        """測試自動添加通配符"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        cache.invalidate("ws-1", "changes")

        # 檢查 scan_iter 是否使用了正確的模式
        call_args = mock_redis.scan_iter.call_args
        assert call_args[1]["match"] == "git:cache:ws-1:changes:*"

    def test_invalidate_no_keys(self):
        """測試沒有匹配的鍵時返回 0"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate("ws-1", "changes")

        assert result == 0

    def test_invalidate_redis_error(self):
        """測試 Redis 錯誤時返回 0"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Scan failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.invalidate("ws-1", "changes")

        assert result == 0

    def test_invalidate_all(self):
        """測試使所有快取失效"""
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
        """測試快取禁用時的統計資訊"""
        cache = GitCache(redis_client=None, enabled=False)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is False
        assert stats["total_keys"] == 0
        assert stats["memory_usage"] == 0

    def test_get_stats_success(self):
        """測試成功取得統計資訊"""
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
        """測試記憶體使用查詢失敗時繼續執行"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = ["git:cache:ws-1:key1"]
        mock_redis.memory_usage.side_effect = RedisError("Memory command failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is True
        assert stats["total_keys"] == 1
        assert stats["memory_usage"] == 0

    def test_get_stats_redis_error(self):
        """測試 Redis 錯誤時返回錯誤統計"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Scan failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        stats = cache.get_stats("ws-1")

        assert stats["enabled"] is True
        assert "error" in stats

    def test_clear_all_disabled(self):
        """測試快取禁用時 clear_all 返回 0"""
        cache = GitCache(redis_client=None, enabled=False)
        result = cache.clear_all()

        assert result == 0

    def test_clear_all_success(self):
        """測試成功清除所有快取"""
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
        """測試沒有鍵時清除返回 0"""
        mock_redis = Mock()
        mock_redis.scan_iter.return_value = []

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.clear_all()

        assert result == 0

    def test_clear_all_redis_error(self):
        """測試 Redis 錯誤時返回 0"""
        mock_redis = Mock()
        mock_redis.scan_iter.side_effect = RedisError("Clear failed")

        cache = GitCache(redis_client=mock_redis, enabled=True)
        result = cache.clear_all()

        assert result == 0


class TestCacheKeys:
    """CacheKeys 常數測試"""

    def test_cache_keys_values(self):
        """測試快取鍵常數值"""
        assert CacheKeys.CHANGES == "changes"
        assert CacheKeys.STATUS == "status"
        assert CacheKeys.BRANCHES == "branches"
        assert CacheKeys.COMMITS == "commits"
        assert CacheKeys.COMMIT_DETAIL == "commit_detail"
        assert CacheKeys.COMMIT_FILES == "commit_files"
        assert CacheKeys.DIFF == "diff"
        assert CacheKeys.BLOB == "blob"


class TestCacheTTL:
    """CacheTTL 常數測試"""

    def test_cache_ttl_values(self):
        """測試快取 TTL 常數值"""
        assert CacheTTL.VERY_SHORT == 10
        assert CacheTTL.SHORT == 30
        assert CacheTTL.MEDIUM == 300
        assert CacheTTL.LONG == 1800
        assert CacheTTL.VERY_LONG == 3600


class TestCreateGitCache:
    """create_git_cache 工廠函數測試"""

    def test_create_disabled_by_config(self):
        """測試通過配置禁用快取"""
        cache = create_git_cache(redis_url="redis://localhost", enabled=False)

        assert cache.enabled is False

    def test_create_without_redis_url(self):
        """測試沒有 Redis URL 時禁用快取"""
        cache = create_git_cache(redis_url=None, enabled=True)

        assert cache.enabled is False

    @patch("app.modules.version_control.cache.Redis")
    def test_create_success(self, mock_redis_class):
        """測試成功創建快取"""
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
        """測試 Redis 連接失敗時禁用快取"""
        mock_redis_class.from_url.side_effect = RedisError("Connection failed")

        cache = create_git_cache(redis_url="redis://localhost:6379/0", enabled=True)

        assert cache.enabled is False

    @patch("app.modules.version_control.cache.Redis")
    def test_create_ping_failure(self, mock_redis_class):
        """測試 Redis ping 失敗時禁用快取"""
        mock_redis_instance = Mock()
        mock_redis_instance.ping.side_effect = RedisError("Ping failed")
        mock_redis_class.from_url.return_value = mock_redis_instance

        cache = create_git_cache(redis_url="redis://localhost:6379/0", enabled=True)

        assert cache.enabled is False
