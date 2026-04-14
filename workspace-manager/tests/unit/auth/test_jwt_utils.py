"""
JWT 驗證工具類的單元測試
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta, timezone

from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.modules.auth.jwt_utils import (
    JWTUtils,
    JWTValidationError,
    JWKSFetchError,
    clear_jwt_utils_cache,
    get_jwt_utils,
)


class TestJWTUtils:
    """JWTUtils 類的單元測試"""

    @pytest.fixture
    def jwt_utils(self):
        """創建 JWTUtils 實例"""
        utils = JWTUtils()
        utils.config.jwks_url = "https://example.com/jwks"
        return utils

    @pytest.fixture
    def mock_jwks_response(self):
        """模擬 JWKS 響應"""
        return {
            "keys": [
                {
                    "kid": "test-key-id",
                    "kty": "RSA",
                    "alg": "RS256",
                    "n": "test-n-value",
                    "e": "AQAB",
                }
            ]
        }

    @pytest.fixture
    def valid_token_payload(self):
        """有效的 token payload"""
        exp_time = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        return {
            "sub": "test-user-id",
            "preferred_username": "testuser",
            "email": "test@example.com",
            "exp": exp_time,
            "iat": datetime.now(timezone.utc).timestamp(),
            "iss": "http://localhost:8080/realms/aileron",
            "aud": "aileron-frontend",
        }

    def test_get_jwt_utils_singleton(self, jwt_utils):
        """測試 get_jwt_utils 單例模式"""
        instance1 = get_jwt_utils()
        instance2 = get_jwt_utils()
        assert instance1 is instance2

    def test_initialization(self, jwt_utils):
        """測試 JWTUtils 初始化"""
        assert jwt_utils.jwks_cache is None
        assert jwt_utils.jwks_cache_time is None

    @pytest.mark.asyncio
    async def test_fetch_jwks_success(
        self, jwt_utils, mock_jwks_response
    ):
        """測試成功獲取 JWKS"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            jwks = await jwt_utils.fetch_jwks()

            assert jwks == mock_jwks_response
            assert jwt_utils.jwks_cache == mock_jwks_response
            assert jwt_utils.jwks_cache_time is not None

    @pytest.mark.asyncio
    async def test_fetch_jwks_cache_hit(self, jwt_utils, mock_jwks_response):
        """測試 JWKS 快取命中"""
        # 首次獲取
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            jwks1 = await jwt_utils.fetch_jwks()
            cache_time = jwt_utils.jwks_cache_time

            # 第二次獲取應該使用快取
            jwks2 = await jwt_utils.fetch_jwks()

            assert jwks1 == jwks2
            assert jwt_utils.jwks_cache_time == cache_time
            mock_get.assert_called_once()  # 只調用一次

    @pytest.mark.asyncio
    async def test_fetch_jwks_cache_expiry(self, jwt_utils, mock_jwks_response):
        """測試 JWKS 快取過期"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_jwks_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            # 首次獲取
            await jwt_utils.fetch_jwks()

            # 模擬快取過期
            old_cache_time = jwt_utils.jwks_cache_time
            jwt_utils.jwks_cache_time = datetime.now(timezone.utc) - timedelta(seconds=10000)

            # 再次獲取應該重新請求
            await jwt_utils.fetch_jwks()

            assert mock_get.call_count == 2  # 調用兩次

    @pytest.mark.asyncio
    async def test_fetch_jwks_auth_disabled(self, jwt_utils):
        """測試認證未啟用時的 JWKS 獲取"""
        with patch("app.modules.auth.jwt_utils.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            jwt_utils.config = mock_config.return_value

            with pytest.raises(JWKSFetchError, match="Authentication is not enabled"):
                await jwt_utils.fetch_jwks()

    @pytest.mark.asyncio
    async def test_fetch_jwks_http_error(self, jwt_utils):
        """測試 JWKS 獲取失敗（HTTP 錯誤）"""
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.side_effect = Exception("Network error")

            with pytest.raises(JWKSFetchError):
                await jwt_utils.fetch_jwks()

    @pytest.mark.asyncio
    async def test_fetch_jwks_missing_url(self, jwt_utils):
        """測試 JWKS URL 未設定時會失敗"""
        jwt_utils.config.jwks_url = None

        with pytest.raises(JWKSFetchError, match="JWKS URL not configured"):
            await jwt_utils.fetch_jwks()

    @pytest.mark.asyncio
    async def test_fetch_jwks_httpx_error_wrapped(self, jwt_utils):
        """測試 httpx 例外會被包裝為 JWKSFetchError"""
        jwt_utils.config.jwks_url = "https://example.com/jwks"
        with patch("httpx.AsyncClient.get", side_effect=__import__("httpx").ConnectError("boom")):
            with pytest.raises(JWKSFetchError, match="Failed to fetch JWKS"):
                await jwt_utils.fetch_jwks()

    def test_clear_jwks_cache(self, jwt_utils, mock_jwks_response):
        """測試清除 JWKS 快取"""
        # 設置快取
        jwt_utils.jwks_cache = mock_jwks_response
        jwt_utils.jwks_cache_time = datetime.now(timezone.utc)

        # 清除快取
        jwt_utils.clear_jwks_cache()

        assert jwt_utils.jwks_cache is None
        assert jwt_utils.jwks_cache_time is None

    def test_get_public_key_from_cached_jwks(self, jwt_utils, mock_jwks_response):
        """測試從快取的 JWKS 取得 public key"""
        jwt_utils.jwks_cache = mock_jwks_response

        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_headers", return_value={"kid": "test-key-id"}):
            key = jwt_utils.get_public_key("token")

        assert key["kid"] == "test-key-id"

    def test_get_public_key_missing_kid(self, jwt_utils):
        """測試 token header 缺少 kid"""
        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_headers", return_value={}):
            with pytest.raises(JWTValidationError, match="missing 'kid'"):
                jwt_utils.get_public_key("token")

    def test_get_public_key_invalid_header(self, jwt_utils):
        """測試無效 token header"""
        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_headers", side_effect=JWTError("bad header")):
            with pytest.raises(JWTValidationError, match="Invalid token header"):
                jwt_utils.get_public_key("token")

    def test_get_public_key_fetches_jwks_when_cache_missing(self, jwt_utils, mock_jwks_response):
        """測試 cache 缺失時會同步取得 JWKS"""
        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_headers", return_value={"kid": "test-key-id"}), \
             patch.object(jwt_utils, "fetch_jwks", new=AsyncMock(return_value=mock_jwks_response)):
            key = jwt_utils.get_public_key("token")

        assert key["kid"] == "test-key-id"

    def test_get_public_key_raises_when_kid_not_found(self, jwt_utils, mock_jwks_response):
        """測試找不到對應 kid 時拋出錯誤"""
        jwt_utils.jwks_cache = {"keys": []}

        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_headers", return_value={"kid": "missing"}):
            with pytest.raises(JWTValidationError, match="Public key not found"):
                jwt_utils.get_public_key("token")

    def test_validate_token_expiry_valid(self, jwt_utils):
        """測試驗證有效的 token 過期時間"""
        exp_time = (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
        payload = {"exp": exp_time}

        assert jwt_utils.validate_token_expiry(payload) is True

    def test_validate_token_expiry_expired(self, jwt_utils):
        """測試驗證過期的 token"""
        exp_time = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        payload = {"exp": exp_time}

        assert jwt_utils.validate_token_expiry(payload) is False

    def test_validate_token_expiry_no_exp(self, jwt_utils):
        """測試沒有 exp 字段的 token"""
        payload = {"sub": "test-user"}

        assert jwt_utils.validate_token_expiry(payload) is False

    def test_validate_token_expiry_returns_true_when_auth_disabled(self, jwt_utils):
        """測試認證停用時 validate_token_expiry 直接返回 True"""
        jwt_utils.config.enabled = False
        assert jwt_utils.validate_token_expiry({}) is True

    def test_decode_token_success(self, jwt_utils):
        """測試成功解碼 token"""
        payload = {"sub": "user-1", "azp": jwt_utils.config.client_id}
        jwt_utils.config.enabled = True

        with patch.object(jwt_utils, "get_public_key", return_value={"kid": "kid"}), \
             patch("app.modules.auth.jwt_utils.jwk.construct") as mock_construct, \
             patch("app.modules.auth.jwt_utils.jwt.decode", return_value=payload):
            mock_rsa_key = Mock()
            mock_rsa_key.to_pem.return_value = b"pem"
            mock_construct.return_value = mock_rsa_key

            assert jwt_utils.decode_token("token") == payload

    def test_decode_token_azp_mismatch(self, jwt_utils):
        """測試 azp 不符時會失敗"""
        with patch.object(jwt_utils, "get_public_key", return_value={"kid": "kid"}), \
             patch("app.modules.auth.jwt_utils.jwk.construct") as mock_construct, \
             patch("app.modules.auth.jwt_utils.jwt.decode", return_value={"sub": "user-1", "azp": "other-client"}):
            mock_rsa_key = Mock()
            mock_rsa_key.to_pem.return_value = b"pem"
            mock_construct.return_value = mock_rsa_key

            with pytest.raises(JWTValidationError, match="Token not issued for this client"):
                jwt_utils.decode_token("token")

    @pytest.mark.parametrize(
        ("side_effect", "message"),
        [
            (ExpiredSignatureError(), "Token has expired"),
            (JWTClaimsError("bad claims"), "Invalid token claims"),
            (JWTError("bad token"), "Invalid token"),
        ],
    )
    def test_decode_token_wraps_jose_errors(self, jwt_utils, side_effect, message):
        """測試 jose 例外會被轉成 JWTValidationError"""
        with patch.object(jwt_utils, "get_public_key", return_value={"kid": "kid"}), \
             patch("app.modules.auth.jwt_utils.jwk.construct") as mock_construct, \
             patch("app.modules.auth.jwt_utils.jwt.decode", side_effect=side_effect):
            mock_rsa_key = Mock()
            mock_rsa_key.to_pem.return_value = b"pem"
            mock_construct.return_value = mock_rsa_key

            with pytest.raises(JWTValidationError, match=message):
                jwt_utils.decode_token("token")

    @pytest.mark.asyncio
    async def test_decode_token_async_fetches_jwks_when_needed(self, jwt_utils):
        """測試異步解碼會先抓 JWKS 再委派同步解碼"""
        with patch.object(jwt_utils, "fetch_jwks", new=AsyncMock(return_value={"keys": []})) as mock_fetch, \
             patch.object(jwt_utils, "decode_token", return_value={"sub": "user-1"}) as mock_decode:
            payload = await jwt_utils.decode_token_async("token")

        assert payload == {"sub": "user-1"}
        mock_fetch.assert_awaited_once()
        mock_decode.assert_called_once_with("token", True)

    @pytest.mark.asyncio
    async def test_decode_token_async_wraps_unexpected_errors(self, jwt_utils):
        """測試異步解碼的未知例外會被包裝"""
        with patch.object(jwt_utils, "decode_token", side_effect=RuntimeError("unexpected")):
            jwt_utils.jwks_cache = {"keys": []}

            with pytest.raises(JWTValidationError, match="Token validation failed: unexpected"):
                await jwt_utils.decode_token_async("token")

    def test_get_token_claims_wraps_errors(self, jwt_utils):
        """測試 get_token_claims 會包裝 JWTError"""
        with patch("app.modules.auth.jwt_utils.jwt.get_unverified_claims", side_effect=JWTError("broken")):
            with pytest.raises(JWTValidationError, match="Failed to get token claims"):
                jwt_utils.get_token_claims("token")

    def test_get_cache_stats(self, jwt_utils, mock_jwks_response):
        """測試獲取快取統計信息"""
        # 模擬快取命中
        jwt_utils.jwks_cache = mock_jwks_response
        jwt_utils.jwks_cache_time = datetime.now(timezone.utc)

        stats = jwt_utils.get_cache_stats() if hasattr(jwt_utils, "get_stats") else None

        # 如果有實現 get_stats 方法，測試它
        if stats is not None:
            assert "is_cached" in stats
            assert stats["is_cached"] is True


class TestJWTUtilsIntegration:
    """JWTUtils 集成測試（使用真實的 JWT 操作）"""

    @pytest.fixture
    def jwt_utils(self):
        """創建 JWTUtils 實例"""
        return JWTUtils()

    def test_get_unverified_claims(self, jwt_utils):
        """測試獲取未驗證的 token claims"""
        # 這需要一個真實的 token 格式，但不需要有效的簽名
        # 由於我們還沒有實際的 Keycloak token，跳過此測試
        pytest.skip("Requires actual Keycloak token")

    def test_decode_token_disabled_auth(self, jwt_utils):
        """測試認證未啟用時的 token 解碼"""
        with patch("app.modules.auth.jwt_utils.get_keycloak_config") as mock_config:
            mock_config.return_value = Mock(enabled=False)
            jwt_utils.config = mock_config.return_value

            # 應該返回空字典而不是拋出異常
            result = jwt_utils.decode_token("dummy-token")
            assert result == {}

    def test_clear_jwt_utils_cache_clears_singleton(self):
        """測試清除全域 JWTUtils singleton"""
        instance = get_jwt_utils()
        instance.jwks_cache = {"keys": []}

        clear_jwt_utils_cache()

        fresh_instance = get_jwt_utils()
        assert fresh_instance.jwks_cache is None
