#!/usr/bin/env python3
"""
Auth 模組基本功能測試腳本
不依賴 pytest-asyncio，用於快速驗證核心功能
"""

import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

# 添加項目路徑
sys.path.insert(0, '.')

from app.modules.auth.config import get_keycloak_config
from app.modules.auth.jwt_utils import JWTUtils, JWTValidationError, JWKSFetchError, get_jwt_utils
from app.modules.auth.jwks_cache import JKWSCache, JWKSFetchError as JKSError, get_jwks_cache


def test_config():
    """測試配置模組"""
    print("測試配置模組...")

    config = get_keycloak_config()
    assert config is not None
    assert hasattr(config, 'enabled')
    assert hasattr(config, 'realm')
    assert hasattr(config, 'client_id')

    print("✓ 配置模組測試通過")


def test_jwt_utils_singleton():
    """測試 JWTUtils 單例模式"""
    print("測試 JWTUtils 單例模式...")

    instance1 = get_jwt_utils()
    instance2 = get_jwt_utils()

    assert instance1 is instance2
    print("✓ JWTUtils 單例測試通過")


def test_jwt_utils_initialization():
    """測試 JWTUtils 初始化"""
    print("測試 JWTUtils 初始化...")

    jwt_utils = JWTUtils()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ JWTUtils 初始化測試通過")


def test_jwt_utils_clear_cache():
    """測試清除 JWKS 快取"""
    print("測試清除 JWKS 快取...")

    jwt_utils = JWTUtils()

    # 設置快取
    jwt_utils.jwks_cache = {"keys": []}
    jwt_utils.jwks_cache_time = timezone.utc

    # 清除快取
    jwt_utils.clear_jwks_cache()

    assert jwt_utils.jwks_cache is None
    assert jwt_utils.jwks_cache_time is None

    print("✓ 清除快取測試通過")


def test_jwt_validate_expiry():
    """測試 token 過期驗證"""
    print("測試 token 過期驗證...")

    jwt_utils = JWTUtils()

    # 有效的 token
    exp_valid = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
    payload_valid = {"exp": exp_valid}
    assert jwt_utils.validate_token_expiry(payload_valid) is True

    # 過期的 token
    exp_expired = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    payload_expired = {"exp": exp_expired}
    assert jwt_utils.validate_token_expiry(payload_expired) is False

    # 沒有 exp 字段
    payload_no_exp = {"sub": "test"}
    assert jwt_utils.validate_token_expiry(payload_no_exp) is False

    print("✓ Token 過期驗證測試通過")


def test_jwt_auth_disabled():
    """測試認證未啟用時的行為"""
    print("測試認證未啟用時的行為...")

    jwt_utils = JWTUtils()

    # 模擬認證未啟用
    with patch("app.modules.auth.jwt_utils.get_keycloak_config") as mock_config:
        mock_config.return_value = Mock(enabled=False)
        jwt_utils.config = mock_config.return_value

        # 應該返回空字典
        result = jwt_utils.decode_token("dummy-token")
        assert result == {}

    print("✓ 認證未啟用測試通過")


def test_jwks_cache_singleton():
    """測試 JKWSCache 單例模式"""
    print("測試 JKWSCache 單例模式...")

    instance1 = get_jwks_cache()
    instance2 = get_jwks_cache()

    assert instance1 is instance2
    print("✓ JKWSCache 單例測試通過")


def test_jwks_cache_initialization():
    """測試 JKWSCache 初始化"""
    print("測試 JKWSCache 初始化...")

    cache = JKWSCache()

    assert cache._cache is None
    assert cache._cache_time is None
    assert cache._cache_hits == 0
    assert cache._cache_misses == 0
    assert cache._refresh_errors == 0

    print("✓ JKWSCache 初始化測試通過")


def test_jwks_cache_validity():
    """測試快取有效性檢查"""
    print("測試快取有效性檢查...")

    cache = JKWSCache()

    # 空快取應該無效
    assert cache.is_cache_valid() is False
    assert cache.get_cache_age_seconds() is None

    # 新快取應該有效
    cache._cache = {"keys": []}
    cache._cache_time = datetime.now(timezone.utc)
    assert cache.is_cache_valid() is True

    # 過期快取應該無效
    cache._cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)
    assert cache.is_cache_valid() is False

    print("✓ 快取有效性測試通過")


def test_jwks_cache_stats():
    """測試快取統計信息"""
    print("測試快取統計信息...")

    cache = JKWSCache()

    # 設置一些數據
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

    print("✓ 快取統計測試通過")


def test_jwks_cache_clear():
    """測試清除快取"""
    print("測試清除快取...")

    cache = JKWSCache()

    # 設置快取
    cache._cache = {"keys": []}
    cache._cache_time = timezone.utc

    # 清除快取
    cache.clear()

    assert cache._cache is None
    assert cache._cache_time is None

    print("✓ 清除快取測試通過")


def test_jwks_cache_get_key():
    """測試根據 kid 獲取公鑰"""
    print("測試根據 kid 獲取公鑰...")

    cache = JKWSCache()

    # 設置快取
    mock_jwks = {
        "keys": [
            {"kid": "key-1", "kty": "RSA"},
            {"kid": "key-2", "kty": "RSA"},
        ]
    }
    cache._cache = mock_jwks

    # 找到的情況
    key = cache.get_key_by_kid("key-1")
    assert key is not None
    assert key["kid"] == "key-1"

    # 找不到的情況
    key = cache.get_key_by_kid("non-existent")
    assert key is None

    # 沒有快取的情況
    cache._cache = None
    key = cache.get_key_by_kid("key-1")
    assert key is None

    print("✓ 獲取公鑰測試通過")


def test_router_endpoints():
    """測試 Router 端點定義"""
    print("測試 Router 端點定義...")

    from app.modules.auth.router import router

    # 檢查端點數量
    assert len(router.routes) == 7

    # 檢查端點路徑
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

    print("✓ Router 端點測試通過")


def run_all_tests():
    """運行所有測試"""
    print("=" * 60)
    print("Auth 模組基本功能測試")
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
            print(f"✗ 測試失敗: {test.__name__}")
            print(f"  錯誤: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ 測試錯誤: {test.__name__}")
            print(f"  錯誤: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"測試完成: {passed} 通過, {failed} 失敗")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
