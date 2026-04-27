"""
JWKS CacheManagement類的UnitTest
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
    """JKWSCache 類的UnitTest"""

    @pytest.fixture
    def jwks_cache(self):
        """Create JKWSCache Instance"""
        cache = JKWSCache()
        cache.config.jwks_url = "https://example.com/jwks"
        return cache

    @pytest.fixture
    def mock_jwks_response(self):
        """模擬 JWKS Response"""
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
        """Test get_jwks_cache SingletonPattern"""
        instance1 = get_jwks_cache()
        instance2 = get_jwks_cache()
        assert instance1 is instance2

    def test_initialization(self, jwks_cache):
        """Test JKWSCache Initialize"""
        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None
        assert jwks_cache._cache_hits == 0
        assert jwks_cache._cache_misses == 0

    def test_is_cache_valid_empty(self, jwks_cache):
        """Test空Cache的Valid性"""
        assert jwks_cache.is_cache_valid() is False

    def test_is_cache_valid_fresh(self, jwks_cache, mock_jwks_response):
        """TestNewCache的Valid性"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        assert jwks_cache.is_cache_valid() is True

    def test_is_cache_valid_expired(self, jwks_cache, mock_jwks_response):
        """Test過期Cache的Valid性"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        assert jwks_cache.is_cache_valid() is False

    def test_get_cache_age_no_cache(self, jwks_cache):
        """TestNoneCache時的Year齡"""
        assert jwks_cache.get_cache_age_seconds() is None

    def test_get_cache_age_with_cache(self, jwks_cache, mock_jwks_response):
        """Test有Cache時的Year齡"""
        cache_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = cache_time

        age = jwks_cache.get_cache_age_seconds()
        assert age is not None
        assert age >= 99  # Allowing一些TimePoor異
        assert age <= 101

    @pytest.mark.asyncio
    async def test_get_jwks_cache_hit(self, jwks_cache, mock_jwks_response):
        """TestFromCacheGet JWKS"""
        # SetupCache
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # GetShouldReturnCache的Data
        result = await jwks_cache.get_jwks()

        assert result == mock_jwks_response
        assert jwks_cache._cache_hits == 1
        assert jwks_cache._cache_misses == 0

    @pytest.mark.asyncio
    async def test_get_jwks_cache_miss_fetch(self, jwks_cache, mock_jwks_response):
        """TestCache未命中時FromService器Get"""
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
        """Test強制刷NewCache"""
        # SetupOldCache
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # 強制刷New
            result = await jwks_cache.get_jwks(force_refresh=True)

            assert result == mock_jwks_response
            assert jwks_cache._cache == mock_jwks_response
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jwks_auth_disabled(self, jwks_cache):
        """TestAuthentication未Enabled時的 JWKS Get"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="Authentication is not enabled"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_no_url(self, jwks_cache):
        """TestNoneConfiguration JWKS URL"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True, jwks_url=None)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="JWKS URL not configured"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_invalid_format(self, jwks_cache):
        """Test JWKS FormatInvalid"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"invalid": "format"}  # 缺Less 'keys'
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(JWKSFetchError, match="Invalid JWKS format"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_http_error(self, jwks_cache):
        """Test JWKS GetFailed（HTTP Error）"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(JWKSFetchError):
                await jwks_cache.get_jwks()

            assert jwks_cache._refresh_errors > 0

    @pytest.mark.asyncio
    async def test_get_jwks_uses_stale_on_error(self, jwks_cache, mock_jwks_response):
        """TestError時Use過期Cache"""
        # SetupOldCache
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            # ShouldReturnOldCache而不YesThrowAbnormal
            result = await jwks_cache.get_jwks()

            assert result == old_cache
            assert jwks_cache._refresh_errors > 0

    def test_clear_cache(self, jwks_cache, mock_jwks_response):
        """TestClearCache"""
        # SetupCache
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # ClearCache
        jwks_cache.clear()

        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None

    def test_get_stats(self, jwks_cache, mock_jwks_response):
        """TestGetStatisticsInfo"""
        # Setup一些Data
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
        """TestAccording to kid 找To公鑰"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("key-1")
        assert key is not None
        assert key["kid"] == "key-1"

    def test_get_key_by_kid_not_found(self, jwks_cache, mock_jwks_response):
        """TestAccording to kid 找不To公鑰"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("non-existent")
        assert key is None

    def test_get_key_by_kid_no_cache(self, jwks_cache):
        """TestNoneCache時According to kid Get公鑰"""
        key = jwks_cache.get_key_by_kid("key-1")
        assert key is None

    @pytest.mark.asyncio
    async def test_concurrent_refresh_protection(self, jwks_cache, mock_jwks_response):
        """Test並發刷NewProtect"""
        import asyncio

        call_count = 0

        async def mock_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # 模擬NetworkDelayed
            return mock_jwks_response

        with patch.object(jwks_cache, "_fetch_jwks_from_server", side_effect=mock_fetch):
            # 並發Get
            tasks = [jwks_cache.get_jwks() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # AllTaskShouldGettingSame的Result
            assert all(r == mock_jwks_response for r in results)

            # Should只調用一次（避免並發刷New）
            assert call_count == 1


class TestJKWSCacheEdgeCases:
    """JKWSCache BoundaryCircumstanceTest"""

    @pytest.fixture
    def jwks_cache(self):
        return JKWSCache()

    @pytest.mark.asyncio
    async def test_empty_jwks_keys(self, jwks_cache):
        """Test空 JWKS keys List"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"keys": []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # ShouldSuccess但None公鑰
            assert result["keys"] == []

    @pytest.mark.asyncio
    async def test_multiple_keys_same_kid(self, jwks_cache):
        """TestMany個Same kid 的公鑰（BoundaryCircumstance）"""
        mock_jwks = {
            "keys": [
                {"kid": "key-1", "kty": "RSA"},
                {"kid": "key-1", "kty": "RSA"},  # Repeat的 kid
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # get_key_by_kid ShouldReturn第一個匹配的
            key = jwks_cache.get_key_by_kid("key-1")
            assert key is not None
            assert key["kid"] == "key-1"

    def test_zero_cache_ttl(self, jwks_cache):
        """Test零 TTL（每次都刷New）"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(
                enabled=True,
                jwks_cache_ttl=0,  # 零 TTL
                jwks_url="http://test.com/jwks"
            )
            jwks_cache.config = mock_config.return_value

            # CacheShould始終Invalid
            jwks_cache._cache = {"keys": []}
            jwks_cache._cache_time = datetime.now(timezone.utc)

            assert jwks_cache.is_cache_valid() is False
