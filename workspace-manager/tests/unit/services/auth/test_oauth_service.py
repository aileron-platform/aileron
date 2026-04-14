"""OAuthService 單元測試"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.oauth_service import (
    OAuthAccountInfo,
    OAuthExchangeResult,
    OAuthService,
    OAuthTokenResponse,
    PKCEParams,
)


# ============================================================================
# PKCE Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestPKCE:
    """PKCE 生成測試"""

    def test_generate_pkce_returns_valid_params(self):
        """測試：生成有效的 PKCE 參數"""
        # Act
        pkce = OAuthService.generate_pkce()

        # Assert
        assert isinstance(pkce, PKCEParams)
        assert len(pkce.verifier) >= 43
        assert len(pkce.challenge) >= 43
        assert pkce.verifier != pkce.challenge

    def test_generate_pkce_creates_unique_params(self):
        """測試：每次生成不同的 PKCE 參數"""
        # Act
        pkce1 = OAuthService.generate_pkce()
        pkce2 = OAuthService.generate_pkce()

        # Assert
        assert pkce1.verifier != pkce2.verifier
        assert pkce1.challenge != pkce2.challenge

    def test_pkce_challenge_is_sha256_of_verifier(self):
        """測試：challenge 是 verifier 的 SHA256 hash"""
        import hashlib
        import base64

        # Act
        pkce = OAuthService.generate_pkce()

        # 手動計算 challenge
        expected_challenge_bytes = hashlib.sha256(pkce.verifier.encode('utf-8')).digest()
        expected_challenge = base64.urlsafe_b64encode(expected_challenge_bytes).decode('utf-8').rstrip('=')

        # Assert
        assert pkce.challenge == expected_challenge


# ============================================================================
# Authorization URL Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestAuthorizationURL:
    """授權 URL 建構測試"""

    def test_build_authorization_url_with_correct_params(self):
        """測試：建構正確的授權 URL"""
        from urllib.parse import unquote

        # Arrange
        pkce = PKCEParams(verifier="test-verifier", challenge="test-challenge")

        # Act
        url = OAuthService.build_authorization_url(pkce)
        decoded_url = unquote(url)

        # Assert
        assert url.startswith(OAuthService.AUTHORIZATION_URL)
        assert "code=true" in url
        assert f"client_id={OAuthService.CLIENT_ID}" in url
        assert "response_type=code" in url
        assert OAuthService.REDIRECT_URI in decoded_url
        assert "code_challenge=test-challenge" in url
        assert "code_challenge_method=S256" in url
        assert "state=test-verifier" in url

    def test_build_authorization_url_uses_verifier_as_state(self):
        """測試：使用 verifier 作為 state"""
        # Arrange
        pkce = PKCEParams(verifier="my-verifier-123", challenge="my-challenge-456")

        # Act
        url = OAuthService.build_authorization_url(pkce)

        # Assert
        assert "state=my-verifier-123" in url


# ============================================================================
# Code Exchange Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestCodeExchange:
    """授權碼交換測試"""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self):
        """測試：成功交換授權碼獲取 token"""
        # Arrange
        code = "auth-code-123#verifier-123"
        verifier = "verifier-123"

        mock_response_data = {
            "access_token": "access-token-abc",
            "refresh_token": "refresh-token-xyz",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = mock_response_data

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await OAuthService.exchange_code(code, verifier)

            # Assert
            assert isinstance(result, OAuthExchangeResult)
            assert result.access_token == "access-token-abc"
            assert result.refresh_token == "refresh-token-xyz"
            assert result.expires_at > 0

            # 驗證 API 調用
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == OAuthService.TOKEN_URL
            payload = call_args[1]["json"]
            assert payload["code"] == "auth-code-123"
            assert payload["state"] == "verifier-123"
            assert payload["code_verifier"] == verifier

    @pytest.mark.asyncio
    async def test_exchange_code_with_invalid_format(self):
        """測試：無效的 code 格式失敗"""
        # Arrange
        invalid_code = "invalid-code-without-hash"
        verifier = "verifier-123"

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid authentication code format"):
            await OAuthService.exchange_code(invalid_code, verifier)

    @pytest.mark.asyncio
    async def test_exchange_code_with_state_mismatch(self):
        """測試：state 不匹配失敗"""
        # Arrange
        code = "auth-code-123#wrong-state"
        verifier = "correct-verifier"

        # Act & Assert
        with pytest.raises(ValueError, match="State mismatch"):
            await OAuthService.exchange_code(code, verifier)

    @pytest.mark.asyncio
    async def test_exchange_code_with_api_error(self):
        """測試：API 請求失敗"""
        # Arrange
        code = "auth-code-123#verifier-123"
        verifier = "verifier-123"

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.text = "Invalid authorization code"
        mock_response.request = MagicMock()

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError, match="OAuth token exchange failed"):
                await OAuthService.exchange_code(code, verifier)

    @pytest.mark.asyncio
    async def test_exchange_code_calculates_expires_at_correctly(self):
        """測試：正確計算 expires_at 時間戳"""
        # Arrange
        code = "auth-code-123#verifier-123"
        verifier = "verifier-123"

        mock_response_data = {
            "access_token": "access-token-abc",
            "refresh_token": "refresh-token-xyz",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = mock_response_data

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            current_time_ms = int(time.time() * 1000)
            result = await OAuthService.exchange_code(code, verifier)

            # Assert
            # expires_at 應該在當前時間 + 3600 秒左右
            expected_expires_at = current_time_ms + (3600 * 1000)
            assert abs(result.expires_at - expected_expires_at) < 5000  # 允許 5 秒誤差


# ============================================================================
# Token Refresh Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestTokenRefresh:
    """Token 刷新測試"""

    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self):
        """測試：成功刷新 access token"""
        # Arrange
        refresh_token = "refresh-token-xyz"

        mock_response_data = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = mock_response_data

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await OAuthService.refresh_access_token(refresh_token)

            # Assert
            assert isinstance(result, OAuthExchangeResult)
            assert result.access_token == "new-access-token"
            assert result.refresh_token == "new-refresh-token"
            assert result.expires_at > 0

            # 驗證 API 調用
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            payload = call_args[1]["json"]
            assert payload["grant_type"] == "refresh_token"
            assert payload["refresh_token"] == refresh_token
            assert payload["client_id"] == OAuthService.CLIENT_ID

    @pytest.mark.asyncio
    async def test_refresh_access_token_with_invalid_token(self):
        """測試：無效的 refresh token 刷新失敗"""
        # Arrange
        refresh_token = "invalid-refresh-token"

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.text = "Invalid refresh token"
        mock_response.request = MagicMock()

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError, match="OAuth token refresh failed"):
                await OAuthService.refresh_access_token(refresh_token)


# ============================================================================
# Get Valid Access Token Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestGetValidAccessToken:
    """獲取有效 access token 測試"""

    @pytest.mark.asyncio
    async def test_get_valid_token_with_non_expired_token(self):
        """測試：token 未過期時直接返回"""
        # Arrange
        access_token = "valid-access-token"
        refresh_token = "refresh-token"
        expires_at = int(time.time() * 1000) + 3600000  # 1 小時後過期

        # Act
        result = await OAuthService.get_valid_access_token(
            access_token, refresh_token, expires_at
        )

        # Assert
        assert result == access_token

    @pytest.mark.asyncio
    async def test_get_valid_token_with_expired_token(self):
        """測試：token 過期時自動刷新"""
        # Arrange
        access_token = "expired-access-token"
        refresh_token = "refresh-token"
        expires_at = int(time.time() * 1000) - 1000  # 已過期

        mock_response_data = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.json.return_value = mock_response_data

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await OAuthService.get_valid_access_token(
                access_token, refresh_token, expires_at
            )

            # Assert
            assert result == "new-access-token"

    @pytest.mark.asyncio
    async def test_get_valid_token_without_refresh_token(self):
        """測試：沒有 refresh token 時返回 None"""
        # Arrange
        access_token = "expired-access-token"
        refresh_token = None
        expires_at = int(time.time() * 1000) - 1000  # 已過期

        # Act
        result = await OAuthService.get_valid_access_token(
            access_token, refresh_token, expires_at
        )

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_valid_token_with_refresh_failure(self):
        """測試：刷新失敗時返回 None"""
        # Arrange
        access_token = "expired-access-token"
        refresh_token = "invalid-refresh-token"
        expires_at = int(time.time() * 1000) - 1000  # 已過期

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.text = "Invalid refresh token"
        mock_response.request = MagicMock()

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await OAuthService.get_valid_access_token(
                access_token, refresh_token, expires_at
            )

            # Assert
            assert result is None


# ============================================================================
# Account Info Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.auth
class TestAccountInfo:
    """帳戶資訊獲取測試"""

    @pytest.mark.asyncio
    async def test_get_account_info_success(self):
        """測試：成功獲取帳戶資訊"""
        # Arrange
        access_token = "valid-access-token"

        mock_profile_data = {
            "account": {
                "uuid": "account-uuid-123",
                "email": "user@example.com",
                "display_name": "Test User"
            },
            "organization": {
                "uuid": "org-uuid-456",
                "billing_type": "paid",
                "name": "Test Organization"
            }
        }

        mock_roles_data = {
            "organization_role": "admin",
            "workspace_role": "owner"
        }

        mock_profile_response = MagicMock()
        mock_profile_response.is_success = True
        mock_profile_response.json.return_value = mock_profile_data

        mock_roles_response = MagicMock()
        mock_roles_response.is_success = True
        mock_roles_response.json.return_value = mock_roles_data

        # Act
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=[mock_profile_response, mock_roles_response])
            mock_client_class.return_value = mock_client

            result = await OAuthService.get_account_info(access_token)

            # Assert
            assert isinstance(result, OAuthAccountInfo)
            assert result.account_uuid == "account-uuid-123"
            assert result.email_address == "user@example.com"
            assert result.display_name == "Test User"
            assert result.organization_uuid == "org-uuid-456"
            assert result.organization_billing_type == "paid"
            assert result.organization_role == "admin"
            assert result.workspace_role == "owner"
            assert result.organization_name == "Test Organization"

            # 驗證 API 調用
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_get_account_info_profile_failure(self):
        """測試：獲取 profile 失敗"""
        # Arrange
        access_token = "invalid-access-token"

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.text = "Unauthorized"
        mock_response.request = MagicMock()

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError, match="Failed to get profile"):
                await OAuthService.get_account_info(access_token)

    @pytest.mark.asyncio
    async def test_get_account_info_roles_failure(self):
        """測試：獲取 roles 失敗"""
        # Arrange
        access_token = "valid-access-token"

        mock_profile_data = {
            "account": {
                "uuid": "account-uuid-123",
                "email": "user@example.com",
                "display_name": "Test User"
            },
            "organization": {
                "uuid": "org-uuid-456",
                "billing_type": "paid",
                "name": "Test Organization"
            }
        }

        mock_profile_response = MagicMock()
        mock_profile_response.is_success = True
        mock_profile_response.json.return_value = mock_profile_data

        mock_roles_response = MagicMock()
        mock_roles_response.is_success = False
        mock_roles_response.text = "Failed to get roles"
        mock_roles_response.request = MagicMock()

        # Act & Assert
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get = AsyncMock(side_effect=[mock_profile_response, mock_roles_response])
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError, match="Failed to get roles"):
                await OAuthService.get_account_info(access_token)


# ============================================================================
# Model Tests
# ============================================================================

@pytest.mark.unit
class TestOAuthModels:
    """OAuth 模型測試"""

    def test_pkce_params_model(self):
        """測試：PKCEParams 模型"""
        pkce = PKCEParams(verifier="test-verifier", challenge="test-challenge")
        assert pkce.verifier == "test-verifier"
        assert pkce.challenge == "test-challenge"

    def test_oauth_token_response_model(self):
        """測試：OAuthTokenResponse 模型"""
        token_data = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer"
        }
        token = OAuthTokenResponse(**token_data)
        assert token.access_token == "access-token"
        assert token.refresh_token == "refresh-token"
        assert token.expires_in == 3600
        assert token.token_type == "Bearer"

    def test_oauth_exchange_result_model(self):
        """測試：OAuthExchangeResult 模型"""
        result = OAuthExchangeResult(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=1234567890000
        )
        assert result.access_token == "access-token"
        assert result.refresh_token == "refresh-token"
        assert result.expires_at == 1234567890000

    def test_oauth_account_info_model(self):
        """測試：OAuthAccountInfo 模型"""
        account_data = {
            "accountUuid": "account-123",
            "emailAddress": "test@example.com",
            "organizationUuid": "org-456",
            "displayName": "Test User",
            "organizationBillingType": "paid",
            "organizationRole": "admin",
            "workspaceRole": "owner",
            "organizationName": "Test Org"
        }
        account = OAuthAccountInfo(**account_data)
        assert account.account_uuid == "account-123"
        assert account.email_address == "test@example.com"
        assert account.organization_uuid == "org-456"
        assert account.display_name == "Test User"
