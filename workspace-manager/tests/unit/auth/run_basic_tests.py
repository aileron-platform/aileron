#!/usr/bin/env python3
"""
Auth ModuleBasicFunctionTest腳本
不依賴 pytest-asyncio，用AtFast速VerifyCoreFunction
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

# 添加ProjectRoad徑
sys.path.insert(0, '.')

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTUtils, JWTValidationError, JWKSFetchError, get_jwt_utils
from app.modules.auth.jwks_cache import JKWSCache, JWKSFetchError as JKSError, get_jwks_cache


def test_config():
    """TestConfigurationModule"""
    print("TestConfigurationModule...")

    config = get_keycloak_config()
    assert config is not None
    assert hasattr(config, 'enabled')
    assert hasattr(config, 'realm')
    assert hasattr(config, 'client_id')

    print("✓ ConfigurationModuleTestPassed")


def test_jwt_utils_singleton():
    """Test JWTUtils SingletonPattern"""
    print("Test JWTUtils SingletonPattern...")

    instance1 = get_jwt_utils()
    instance2 = get_jwt_utils()

    assert instance1 is instance2
    print("✓ JWTUtils SingletonTestPassed")


def test_jwt_utils_initialization():
    """Test JWTUtils Initialize"""
    print("Test JWTUtils Initialize...")

    jwt_utils = JWTUtils()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ JWTUtils InitializeTestPassed")


def test_jwt_utils_clear_cache():
    """TestClear JWKS Cache"""
    print("TestClear JWKS Cache...")

    jwt_utils = JWTUtils()

    # SetupCache
    jwt_utils.jwks_cache = {"keys": []}
    jwt_utils.jwks_cache_time = timezone.utc

    # ClearCache
    jwt_utils.clear_jwks_cache()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ ClearCacheTestPassed")


def test_jwt_validate_expiry():
    """Test token 過期Verify"""
    print("Test token 過期Verify...")

    jwt_utils = JWTUtils()

    # Valid的 token
    exp_valid = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
    payload_valid = {"exp": exp_valid}
    assert jwt_utils.validate_token_expiry(payload_valid) is True

    # 過期的 token
    exp_expired = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    payload_expired = {"exp": exp_expired}
    assert jwt_utils.validate_token_expiry(payload_expired) is False

    # None exp 字段
    payload_no_exp = {"sub": "test"}
    assert jwt_utils.validate_token_expiry(payload_no_exp) is False

    print("✓ Token 過期VerifyTestPassed")


def test_jwt_auth_disabled():
    """TestAuthentication未Enabled時的行為"""
    print("TestAuthentication未Enabled時的行為...")

    jwt_utils = JWTUtils()

    # 模擬Authentication未Enabled
    with patch("app.modules.auth.jwt_utils.get_keycloak_config") as mock_config:
        mock_config.return_value = Mock(enabled=False)
        jwt_utils.config = mock_config.return_value

        # ShouldReturn空Dictionary
        result = jwt_utils.decode_token("dummy-token")
        assert result == {}

    print("✓ Authentication未EnabledTestPassed")


def test_jwks_cache_singleton():
    """Test JKWSCache SingletonPattern"""
    print("Test JKWSCache SingletonPattern...")

    instance1 = get_jwks_cache()
    instance2 = get_jwks_cache()

    assert instance1 is instance2
    print("✓ JKWSCache SingletonTestPassed")


def test_jwks_cache_initialization():
    """Test JKWSCache Initialize"""
    print("Test JKWSCache Initialize...")

    cache = JKWSCache()

    assert cache._cache is None
    assert cache._cache_time is None
    assert cache._cache_hits == 0
    assert cache._cache_misses == 0
    assert cache._refresh_errors == 0

    print("✓ JKWSCache InitializeTestPassed")


def test_jwks_cache_validity():
    """TestCacheValid性Check"""
    print("TestCacheValid性Check...")

    cache = JKWSCache()

    # 空CacheShouldInvalid
    assert cache.is_cache_valid() is False
    assert cache.get_cache_age_seconds() is None

    # NewCacheShouldValid
    cache._cache = {"keys": []}
    cache._cache_time = datetime.now(timezone.utc)
    assert cache.is_cache_valid() is True

    # 過期CacheShouldInvalid
    cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)
    assert cache.is_cache_valid() is False

    print("✓ CacheValid性TestPassed")


def test_jwks_cache_stats():
    """TestCacheStatisticsInfo"""
    print("TestCacheStatisticsInfo...")

    cache = JKWSCache()

    # Setup一些Data
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

    print("✓ CacheStatisticsTestPassed")


def test_jwks_cache_clear():
    """TestClearCache"""
    print("TestClearCache...")

    cache = JKWSCache()

    # SetupCache
    cache._cache = {"keys": []}
    cache._cache_time = timezone.utc

    # ClearCache
    cache.clear()

    assert cache._cache is None
    assert cache._cache_time is None

    print("✓ ClearCacheTestPassed")


def test_jwks_cache_get_key():
    """TestAccording to kid Get公鑰"""
    print("TestAccording to kid Get公鑰...")

    cache = JKWSCache()

    # SetupCache
    mock_jwks = {
        "keys": [
            {"kid": "key-1", "kty": "RSA"},
            {"kid": "key-2", "kty": "RSA"},
        ]
    }
    cache._cache = mock_jwks

    # 找To的Circumstance
    key = cache.get_key_by_kid("key-1")
    assert key is not None
    assert key["kid"] == "key-1"

    # 找不To的Circumstance
    key = cache.get_key_by_kid("non-existent")
    assert key is None

    # NoneCache的Circumstance
    cache._cache = None
    key = cache.get_key_by_kid("key-1")
    assert key is None

    print("✓ Get公鑰TestPassed")


def test_router_endpoints():
    """Test Router Endpoint定義"""
    print("Test Router Endpoint定義...")

    from app.modules.auth.router import router

    # CheckEndpointQuantity
    assert len(router.routes) == 7

    # CheckEndpointRoad徑
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

    print("✓ Router EndpointTestPassed")


def run_all_tests():
    """RunAllTest"""
    print("=" * 60)
    print("Auth ModuleBasicFunctionTest")
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
            print(f"✗ TestFailed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ TestError: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"TestComplete: {passed} Passed, {failed} Failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
