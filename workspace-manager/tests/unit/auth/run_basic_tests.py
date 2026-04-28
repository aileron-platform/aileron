#!/usr/bin/env python3
"""
Auth Module Basic Function Test Script
Does not depend on pytest-asyncio, use for fast verification of core functions
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

# Add project path
sys.path.insert(0, '.')

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTUtils, JWTValidationError, JWKSFetchError, get_jwt_utils
from app.modules.auth.jwks_cache import JKWSCache, JWKSFetchError as JKSError, get_jwks_cache


def test_config():
    """Test Configuration Module"""
    print("Test Configuration Module...")

    config = get_keycloak_config()
    assert config is not None
    assert hasattr(config, 'enabled')
    assert hasattr(config, 'realm')
    assert hasattr(config, 'client_id')

    print("✓ Configuration Module Test Passed")


def test_jwt_utils_singleton():
    """Test JWTUtils SingletonPattern"""
    print("Test JWTUtils Singleton Pattern...")

    instance1 = get_jwt_utils()
    instance2 = get_jwt_utils()

    assert instance1 is instance2
    print("✓ JWTUtils Singleton Test Passed")


def test_jwt_utils_initialization():
    """Test JWTUtils Initialization"""
    print("Test JWTUtils Initialization...")

    jwt_utils = JWTUtils()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ JWTUtils Initialization Test Passed")


def test_jwt_utils_clear_cache():
    """Test Clear JWKS Cache"""
    print("Test Clear JWKS Cache...")

    jwt_utils = JWTUtils()

    # Setup Cache
    jwt_utils.jwks_cache = {"keys": []}
    jwt_utils.jwks_cache_time = timezone.utc

    # Clear Cache
    jwt_utils.clear_jwks_cache()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ Clear Cache Test Passed")


def test_jwt_validate_expiry():
    """Test Token Expiration Verification"""
    print("Test Token Expiration Verification...")

    jwt_utils = JWTUtils()

    # Valid token
    exp_valid = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
    payload_valid = {"exp": exp_valid}
    assert jwt_utils.validate_token_expiry(payload_valid) is True

    # Expired token
    exp_expired = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    payload_expired = {"exp": exp_expired}
    assert jwt_utils.validate_token_expiry(payload_expired) is False

    # Missing exp field
    payload_no_exp = {"sub": "test"}
    assert jwt_utils.validate_token_expiry(payload_no_exp) is False

    print("✓ Token Expiration Verification Test Passed")


def test_jwt_auth_disabled():
    """Test Behavior When Authentication is Not Enabled"""
    print("Test Behavior When Authentication is Not Enabled...")

    jwt_utils = JWTUtils()

    # Simulate authentication not enabled
    with patch("app.modules.auth.jwt_utils.get_keycloak_config") as mock_config:
        mock_config.return_value = Mock(enabled=False)
        jwt_utils.config = mock_config.return_value

        # Should return empty dictionary
        result = jwt_utils.decode_token("dummy-token")
        assert result == {}

    print("✓ Authentication Not Enabled Test Passed")


def test_jwks_cache_singleton():
    """Test JKWSCache Singleton Pattern"""
    print("Test JKWSCache Singleton Pattern...")

    instance1 = get_jwks_cache()
    instance2 = get_jwks_cache()

    assert instance1 is instance2
    print("✓ JKWSCache Singleton Test Passed")


def test_jwks_cache_initialization():
    """Test JKWSCache Initialization"""
    print("Test JKWSCache Initialization...")

    cache = JKWSCache()

    assert cache._cache is None
    assert cache._cache_time is None
    assert cache._cache_hits == 0
    assert cache._cache_misses == 0
    assert cache._refresh_errors == 0

    print("✓ JKWSCache Initialization Test Passed")


def test_jwks_cache_validity():
    """Test Cache Validity Check"""
    print("Test Cache Validity Check...")

    cache = JKWSCache()

    # Empty cache should be invalid
    assert cache.is_cache_valid() is False
    assert cache.get_cache_age_seconds() is None

    # New cache should be valid
    cache._cache = {"keys": []}
    cache._cache_time = datetime.now(timezone.utc)
    assert cache.is_cache_valid() is True

    # Expired cache should be invalid
    cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)
    assert cache.is_cache_valid() is False

    print("✓ Cache Validity Test Passed")


def test_jwks_cache_stats():
    """Test Cache Statistics Info"""
    print("Test Cache Statistics Info...")

    cache = JKWSCache()

    # Setup some data
    cache._cache = {"keys": [{"kid": "key-1"}]}
    cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=100)
    cache._cache_hits = 10
    cache._cache_misses = 5

    stats = cache.get_stats()

    assert stats["cache_hits"] == 10
    assert stats["cache_misses"] == 5
    assert stats["is_cached"] is True
    assert stats["cache_age_seconds"] >= 99
    assert stats["is_valid"] is True

    print("✓ Cache Statistics Test Passed")


def test_jwks_cache_clear():
    """Test Clear Cache"""
    print("Test Clear Cache...")

    cache = JKWSCache()

    # Setup cache
    cache._cache = {"keys": []}
    cache._cache_time = timezone.utc

    # Clear cache
    cache.clear()

    assert cache._cache is None
    assert cache._cache_time is None

    print("✓ Clear Cache Test Passed")


def test_jwks_cache_get_key():
    """Test Get Public Key by kid"""
    print("Test Get Public Key by kid...")

    cache = JKWSCache()

    # Setup cache
    mock_jwks = {
        "keys": [
            {"kid": "key-1", "kty": "RSA"},
            {"kid": "key-2", "kty": "RSA"},
        ]
    }
    cache._cache = mock_jwks

    # Found case
    key = cache.get_key_by_kid("key-1")
    assert key is not None
    assert key["kid"] == "key-1"

    # Not found case
    key = cache.get_key_by_kid("non-existent")
    assert key is None

    # None cache case
    cache._cache = None
    key = cache.get_key_by_kid("key-1")
    assert key is None

    print("✓ Get Public Key Test Passed")


def test_router_endpoints():
    """Test Router Endpoint Definitions"""
    print("Test Router Endpoint Definitions...")

    from app.modules.auth.router import router

    # Check endpoint count
    assert len(router.routes) == 7

    # Check endpoint paths
    paths = [route.path for route in router.routes]
    expected_paths = [
        "/auth/login",
        "/auth/login/redirect",
        "/auth/callback",
        "/auth/refresh",
        "/auth/logout",
        "/auth/me",
        "/auth/config",
    ]

    for expected_path in expected_paths:
        assert expected_path in paths, f"Missing endpoint: {expected_path}"

    print("✓ Router Endpoint Test Passed")


def run_all_tests():
    """Run All Tests"""
    print("=" * 60)
    print("Auth Module Basic Function Test")
    print("=" * 60)
    print()

    tests = [
        test_config,
        test_jwt_utils_singleton,
        test_jwt_utils_initialization,
        test_jwt_utils_clear_cache,
        test_jwt_validate_expiry,
        test_jwt_auth_disabled,
        test_jwks_cache_singleton,
        test_jwks_cache_initialization,
        test_jwks_cache_validity,
        test_jwks_cache_stats,
        test_jwks_cache_clear,
        test_jwks_cache_get_key,
        test_router_endpoints,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ Test Failed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test Error: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Test Complete: {passed} Passed, {failed} Failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
