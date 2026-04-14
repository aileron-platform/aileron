"""
JWKS 快取管理類的單元測試
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta, timezone

from app.modules.auth.jwks_cache import (
    JKWSCache,
    JWKSFetchError,
    get_jwks_cache,
)


class TestJKWSCache:
    """JKWSCache 類的單元測試"""

    @pytest.fixture
    def jwks_cache(self):
        """創建 JKWSCache 實例"""
        cache = JKWSCache()
        cache.config.jwks_url = "https://example.com/jwks"
        return cache

    @pytest.fixture
    def mock_jwks_response(self):
        """模擬 JWKS 響應"""
        return {
            "keys": [
                {
                    "kid": "key-1",
                    "kty": "RSA",
                    "alg": "RS256",
                },
                {
                    "kid": "key-2",
                    "kty": "RSA",
                    "alg": "RS256",
                }
            ]
        }

    def test_get_jwks_cache_singleton(self, jwks_cache):
        """測試 get_jwks_cache 單例模式"""
        instance1 = get_jwks_cache()
        instance2 = get_jwks_cache()
        assert instance1 is instance2

    def test_initialization(self, jwks_cache):
        """測試 JKWSCache 初始化"""
        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None
        assert jwks_cache._cache_hits == 0
        assert jwks_cache._cache_misses == 0

    def test_is_cache_valid_empty(self, jwks_cache):
        """測試空快取的有效性"""
        assert jwks_cache.is_cache_valid() is False

    def test_is_cache_valid_fresh(self, jwks_cache, mock_jwks_response):
        """測試新快取的有效性"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        assert jwks_cache.is_cache_valid() is True

    def test_is_cache_valid_expired(self, jwks_cache, mock_jwks_response):
        """測試過期快取的有效性"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        assert jwks_cache.is_cache_valid() is False

    def test_get_cache_age_no_cache(self, jwks_cache):
        """測試沒有快取時的年齡"""
        assert jwks_cache.get_cache_age_seconds() is None

    def test_get_cache_age_with_cache(self, jwks_cache, mock_jwks_response):
        """測試有快取時的年齡"""
        cache_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = cache_time

        age = jwks_cache.get_cache_age_seconds()
        assert age is not None
        assert age >= 99  # 允許一些時間差異
        assert age <= 101

    @pytest.mark.asyncio
    async def test_get_jwks_cache_hit(self, jwks_cache, mock_jwks_response):
        """測試從快取獲取 JWKS"""
        # 設置快取
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # 獲取應該返回快取的數據
        result = await jwks_cache.get_jwks()

        assert result == mock_jwks_response
        assert jwks_cache._cache_hits == 1
        assert jwks_cache._cache_misses == 0

    @pytest.mark.asyncio
    async def test_get_jwks_cache_miss_fetch(self, jwks_cache, mock_jwks_response):
        """測試快取未命中時從服務器獲取"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            assert result == mock_jwks_response
            assert jwks_cache._cache == mock_jwks_response
            assert jwks_cache._cache_misses == 1
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jwks_force_refresh(self, jwks_cache, mock_jwks_response):
        """測試強制刷新快取"""
        # 設置舊快取
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # 強制刷新
            result = await jwks_cache.get_jwks(force_refresh=True)

            assert result == mock_jwks_response
            assert jwks_cache._cache == mock_jwks_response
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jwks_auth_disabled(self, jwks_cache):
        """測試認證未啟用時的 JWKS 獲取"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="Authentication is not enabled"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_no_url(self, jwks_cache):
        """測試沒有配置 JWKS URL"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True, jwks_url=None)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="JWKS URL not configured"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_invalid_format(self, jwks_cache):
        """測試 JWKS 格式無效"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"invalid": "format"}  # 缺少 'keys'
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(JWKSFetchError, match="Invalid JWKS format"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_http_error(self, jwks_cache):
        """測試 JWKS 獲取失敗（HTTP 錯誤）"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(JWKSFetchError):
                await jwks_cache.get_jwks()

            assert jwks_cache._refresh_errors > 0

    @pytest.mark.asyncio
    async def test_get_jwks_uses_stale_on_error(self, jwks_cache, mock_jwks_response):
        """測試錯誤時使用過期快取"""
        # 設置舊快取
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            # 應該返回舊快取而不是拋出異常
            result = await jwks_cache.get_jwks()

            assert result == old_cache
            assert jwks_cache._refresh_errors > 0

    def test_clear_cache(self, jwks_cache, mock_jwks_response):
        """測試清除快取"""
        # 設置快取
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # 清除快取
        jwks_cache.clear()

        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None

    def test_get_stats(self, jwks_cache, mock_jwks_response):
        """測試獲取統計信息"""
        # 設置一些數據
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        jwks_cache._cache_hits = 10
        jwks_cache._cache_misses = 5

        stats = jwks_cache.get_stats()

        assert stats["cache_hits"] == 10
        assert stats["cache_misses"] == 5
        assert stats["is_cached"] is True
        assert stats["cache_age_seconds"] >= 99
        assert stats["is_valid"] is True

    def test_get_key_by_kid_found(self, jwks_cache, mock_jwks_response):
        """測試根據 kid 找到公鑰"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("key-1")
        assert key is not None
        assert key["kid"] == "key-1"

    def test_get_key_by_kid_not_found(self, jwks_cache, mock_jwks_response):
        """測試根據 kid 找不到公鑰"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("non-existent")
        assert key is None

    def test_get_key_by_kid_no_cache(self, jwks_cache):
        """測試沒有快取時根據 kid 獲取公鑰"""
        key = jwks_cache.get_key_by_kid("key-1")
        assert key is None

    @pytest.mark.asyncio
    async def test_concurrent_refresh_protection(self, jwks_cache, mock_jwks_response):
        """測試並發刷新保護"""
        import asyncio

        call_count = 0

        async def mock_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模擬網絡延遲
            return mock_jwks_response

        with patch.object(jwks_cache, "_fetch_jwks_from_server", side_effect=mock_fetch):
            # 並發獲取
            tasks = [jwks_cache.get_jwks() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # 所有任務應該獲得相同的結果
            assert all(r == mock_jwks_response for r in results)

            # 應該只調用一次（避免並發刷新）
            assert call_count == 1


class TestJKWSCacheEdgeCases:
    """JKWSCache 邊界情況測試"""

    @pytest.fixture
    def jwks_cache(self):
        return JKWSCache()

    @pytest.mark.asyncio
    async def test_empty_jwks_keys(self, jwks_cache):
        """測試空 JWKS keys 列表"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"keys": []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # 應該成功但沒有公鑰
            assert result["keys"] == []

    @pytest.mark.asyncio
    async def test_multiple_keys_same_kid(self, jwks_cache):
        """測試多個相同 kid 的公鑰（邊界情況）"""
        mock_jwks = {
            "keys": [
                {"kid": "key-1", "kty": "RSA"},
                {"kid": "key-1", "kty": "RSA"},  # 重複的 kid
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # get_key_by_kid 應該返回第一個匹配的
            key = jwks_cache.get_key_by_kid("key-1")
            assert key is not None
            assert key["kid"] == "key-1"

    def test_zero_cache_ttl(self, jwks_cache):
        """測試零 TTL（每次都刷新）"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(
                enabled=True,
                jwks_cache_ttl=0,  # 零 TTL
                jwks_url="http://test.com/jwks"
            )
            jwks_cache.config = mock_config.return_value

            # 快取應該始終無效
            jwks_cache._cache = {"keys": []}
            jwks_cache._cache_time = datetime.now(timezone.utc)

            assert jwks_cache.is_cache_valid() is False
