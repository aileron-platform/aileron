"""
Unit Tests for JWKS Cache Management Class
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
    """Unit Tests for JKWSCache Class"""

    @pytest.fixture
    def jwks_cache(self):
        """Create JKWSCache Instance"""
        cache = JKWSCache()
        cache.config.jwks_url = "https://example.com/jwks"
        return cache

    @pytest.fixture
    def mock_jwks_response(self):
        """Mock JWKS Response"""
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
        """Test get_jwks_cache Singleton Pattern"""
        instance1 = get_jwks_cache()
        instance2 = get_jwks_cache()
        assert instance1 is instance2

    def test_initialization(self, jwks_cache):
        """Test JKWSCache Initialization"""
        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None
        assert jwks_cache._cache_hits == 0
        assert jwks_cache._cache_misses == 0

    def test_is_cache_valid_empty(self, jwks_cache):
        """Test Validity of Empty Cache"""
        assert jwks_cache.is_cache_valid() is False

    def test_is_cache_valid_fresh(self, jwks_cache, mock_jwks_response):
        """Test Validity of Fresh Cache"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        assert jwks_cache.is_cache_valid() is True

    def test_is_cache_valid_expired(self, jwks_cache, mock_jwks_response):
        """Test Validity of Expired Cache"""
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        assert jwks_cache.is_cache_valid() is False

    def test_get_cache_age_no_cache(self, jwks_cache):
        """Test Age When No Cache"""
        assert jwks_cache.get_cache_age_seconds() is None

    def test_get_cache_age_with_cache(self, jwks_cache, mock_jwks_response):
        """Test Age When Has Cache"""
        cache_time = datetime.now(timezone.utc) - timedelta(seconds=100)
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = cache_time

        age = jwks_cache.get_cache_age_seconds()
        assert age is not None
        assert age >= 99  # Allowing some Time deviation
        assert age <= 101

    @pytest.mark.asyncio
    async def test_get_jwks_cache_hit(self, jwks_cache, mock_jwks_response):
        """Test Get JWKS From Cache"""
        # Setup Cache
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # Get Should Return Cache Data
        result = await jwks_cache.get_jwks()

        assert result == mock_jwks_response
        assert jwks_cache._cache_hits == 1
        assert jwks_cache._cache_misses == 0

    @pytest.mark.asyncio
    async def test_get_jwks_cache_miss_fetch(self, jwks_cache, mock_jwks_response):
        """Test Get From Server When Cache Miss"""
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
        """Test Force Refresh Cache"""
        # Setup Old Cache
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # Force Refresh
            result = await jwks_cache.get_jwks(force_refresh=True)

            assert result == mock_jwks_response
            assert jwks_cache._cache == mock_jwks_response
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_jwks_auth_disabled(self, jwks_cache):
        """Test JWKS Get When Authentication Not Enabled"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="Authentication is not enabled"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_no_url(self, jwks_cache):
        """Test No JWKS URL Configured"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=True, jwks_url=None)
            jwks_cache.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="JWKS URL not configured"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_invalid_format(self, jwks_cache):
        """Test JWKS Format Invalid"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"invalid": "format"}  # Missing 'keys'
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            with pytest.raises(JWKSFetchError, match="Invalid JWKS format"):
                await jwks_cache.get_jwks()

    @pytest.mark.asyncio
    async def test_get_jwks_http_error(self, jwks_cache):
        """Test JWKS Get Failed (HTTP Error)"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(JWKSFetchError):
                await jwks_cache.get_jwks()

            assert jwks_cache._refresh_errors > 0

    @pytest.mark.asyncio
    async def test_get_jwks_uses_stale_on_error(self, jwks_cache, mock_jwks_response):
        """Test Use Stale Cache On Error"""
        # Setup Old Cache
        old_cache = {"keys": [{"kid": "old-key"}]}
        jwks_cache._cache = old_cache
        jwks_cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            # Should Return Old Cache Instead of Throwing Exception
            result = await jwks_cache.get_jwks()

            assert result == old_cache
            assert jwks_cache._refresh_errors > 0

    def test_clear_cache(self, jwks_cache, mock_jwks_response):
        """Test Clear Cache"""
        # Setup Cache
        jwks_cache._cache = mock_jwks_response
        jwks_cache._cache_time = datetime.now(timezone.utc)

        # Clear Cache
        jwks_cache.clear()

        assert jwks_cache._cache is None
        assert jwks_cache._cache_time is None

    def test_get_stats(self, jwks_cache, mock_jwks_response):
        """Test Get Statistics Info"""
        # Setup Some Data
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
        """Test Find Public Key by kid"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("key-1")
        assert key is not None
        assert key["kid"] == "key-1"

    def test_get_key_by_kid_not_found(self, jwks_cache, mock_jwks_response):
        """Test Cannot Find Public Key by kid"""
        jwks_cache._cache = mock_jwks_response

        key = jwks_cache.get_key_by_kid("non-existent")
        assert key is None

    def test_get_key_by_kid_no_cache(self, jwks_cache):
        """Test Get Public Key by kid When No Cache"""
        key = jwks_cache.get_key_by_kid("key-1")
        assert key is None

    @pytest.mark.asyncio
    async def test_concurrent_refresh_protection(self, jwks_cache, mock_jwks_response):
        """Test Concurrent Refresh Protection"""
        import asyncio

        call_count = 0

        async def mock_fetch():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate Network Delay
            return mock_jwks_response

        with patch.object(jwks_cache, "_fetch_jwks_from_server", side_effect=mock_fetch):
            # Concurrent Get
            tasks = [jwks_cache.get_jwks() for _ in range(5)]
            results = await asyncio.gather(*tasks)

            # All Tasks Should Get Same Result
            assert all(r == mock_jwks_response for r in results)

            # Should Only Call Once (Avoid Concurrent Refresh)
            assert call_count == 1


class TestJKWSCacheEdgeCases:
    """JKWSCache Edge Cases Test"""

    @pytest.fixture
    def jwks_cache(self):
        return JKWSCache()

    @pytest.mark.asyncio
    async def test_empty_jwks_keys(self, jwks_cache):
        """Test Empty JWKS keys List"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"keys": []}
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # Should Succeed But No Public Keys
            assert result["keys"] == []

    @pytest.mark.asyncio
    async def test_multiple_keys_same_kid(self, jwks_cache):
        """Test Multiple Same kid Public Keys (Edge Case)"""
        mock_jwks = {
            "keys": [
                {"kid": "key-1", "kty": "RSA"},
                {"kid": "key-1", "kty": "RSA"},  # Duplicate kid
            ]
        }

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = await jwks_cache.get_jwks()

            # get_key_by_kid Should Return First Match
            key = jwks_cache.get_key_by_kid("key-1")
            assert key is not None
            assert key["kid"] == "key-1"

    def test_zero_cache_ttl(self, jwks_cache):
        """Test Zero TTL (Always Refresh)"""
        with patch("app.modules.auth.jwks_cache.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(
                enabled=True,
                jwks_cache_ttl=0,  # Zero TTL
                jwks_url="http://test.com/jwks"
            )
            jwks_cache.config = mock_config.return_value

            # Cache Should Always Be Invalid
            jwks_cache._cache = {"keys": []}
            jwks_cache._cache_time = datetime.now(timezone.utc)

            assert jwks_cache.is_cache_valid() is False
