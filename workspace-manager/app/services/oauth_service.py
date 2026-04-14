"""OAuth 認證服務 - 處理 Claude OAuth 流程"""

from __future__ import annotations

import hashlib
import secrets
import base64
import time
from typing import Optional
import httpx

from pydantic import BaseModel, Field, ConfigDict


class PKCEParams(BaseModel):
    """PKCE 參數"""
    verifier: str
    challenge: str


class OAuthTokenResponse(BaseModel):
    """OAuth Token 回應"""
    access_token: str = Field(..., alias="access_token")
    refresh_token: str = Field(..., alias="refresh_token")
    expires_in: int = Field(..., alias="expires_in")
    token_type: str = Field(default="Bearer", alias="token_type")

    model_config = ConfigDict(populate_by_name=True)


class OAuthExchangeResult(BaseModel):
    """OAuth Exchange 結果"""
    access_token: str
    refresh_token: str
    expires_at: int  # 毫秒時間戳


class OAuthAccountInfo(BaseModel):
    """OAuth 帳戶資訊"""
    account_uuid: str = Field(..., alias="accountUuid")
    email_address: str = Field(..., alias="emailAddress")
    organization_uuid: str = Field(..., alias="organizationUuid")
    display_name: str = Field(..., alias="displayName")
    organization_billing_type: str = Field(..., alias="organizationBillingType")
    organization_role: str = Field(..., alias="organizationRole")
    workspace_role: Optional[str] = Field(None, alias="workspaceRole")
    organization_name: str = Field(..., alias="organizationName")

    model_config = ConfigDict(populate_by_name=True)


class OAuthService:
    """處理 Claude OAuth 認證流程"""

    CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    AUTHORIZATION_URL = "https://claude.ai/oauth/authorize"
    TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
    REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
    SCOPE = "org:create_api_key user:profile user:inference"

    @staticmethod
    def generate_pkce() -> PKCEParams:
        """生成 PKCE code verifier 和 challenge"""
        # 生成 code verifier (43-128 個字元)
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # 生成 code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return PKCEParams(verifier=verifier, challenge=challenge)

    @staticmethod
    def build_authorization_url(pkce: PKCEParams) -> str:
        """
        建構 OAuth 授權 URL
        注意：根據參考程式，state 參數應該使用 verifier 的值
        """
        from urllib.parse import urlencode

        params = {
            "code": "true",
            "client_id": OAuthService.CLIENT_ID,
            "response_type": "code",
            "redirect_uri": OAuthService.REDIRECT_URI,
            "scope": OAuthService.SCOPE,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
            "state": pkce.verifier,  # 使用 verifier 作為 state
        }

        return f"{OAuthService.AUTHORIZATION_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str, verifier: str) -> OAuthExchangeResult:
        """
        使用 authorization code 交換 access token

        Args:
            code: 格式為 "code#state" 的認證碼
            verifier: PKCE code verifier（應該與 state 相同）

        Returns:
            OAuthExchangeResult 包含 access_token, refresh_token, expires_at

        Raises:
            httpx.HTTPStatusError: 當 API 請求失敗時
            ValueError: 當回應格式不正確時

        注意：根據參考程式，state 參數應該等於 verifier
        """
        # 分割 code 和 state
        splits = code.split("#")
        if len(splits) != 2:
            raise ValueError("Invalid authentication code format. Expected format: code#state")

        auth_code = splits[0]
        state = splits[1]

        # 驗證 state 是否等於 verifier（根據參考程式的實現）
        if state != verifier:
            raise ValueError(
                f"State mismatch: state={state[:10]}..., verifier={verifier[:10]}... "
                "State should equal verifier in this OAuth flow"
            )

        # 準備請求資料（參考 AuthAnthropic.exchange）
        payload = {
            "code": auth_code,
            "state": state,
            "grant_type": "authorization_code",
            "client_id": OAuthService.CLIENT_ID,
            "redirect_uri": OAuthService.REDIRECT_URI,
            "code_verifier": verifier,
        }
        
        # 發送請求
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAuthService.TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            
            # 檢查回應狀態
            if not response.is_success:
                error_detail = response.text
                raise httpx.HTTPStatusError(
                    f"OAuth token exchange failed: {error_detail}",
                    request=response.request,
                    response=response,
                )
            
            # 解析回應
            data = response.json()

            # 避免在日誌中暴露敏感憑證，只記錄必要的摘要資訊
            from app.core.logging import get_logger

            logger = get_logger(__name__)
            has_oauth_account = bool(data.get("oauthAccount"))
            logger.info(
                "OAuth token exchange succeeded (token_type=%s, expires_in=%s, oauthAccount=%s)",
                data.get("token_type"),
                data.get("expires_in"),
                "present" if has_oauth_account else "absent",
            )

            token_response = OAuthTokenResponse(**data)

            # 計算過期時間（毫秒時間戳）
            # 使用當前時間（毫秒）+ expires_in（秒）* 1000
            current_time_ms = int(time.time() * 1000)
            expires_at_ms = current_time_ms + (token_response.expires_in * 1000)

            return OAuthExchangeResult(
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_at=expires_at_ms,
            )

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> OAuthExchangeResult:
        """
        使用 refresh token 更新 access token
        
        Args:
            refresh_token: Refresh token
            
        Returns:
            OAuthExchangeResult 包含新的 access_token, refresh_token, expires_at
            
        Raises:
            httpx.HTTPStatusError: 當 API 請求失敗時
        """
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": OAuthService.CLIENT_ID,
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAuthService.TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            
            if not response.is_success:
                error_detail = response.text
                raise httpx.HTTPStatusError(
                    f"OAuth token refresh failed: {error_detail}",
                    request=response.request,
                    response=response,
                )
            
            data = response.json()
            token_response = OAuthTokenResponse(**data)

            # 計算過期時間（毫秒時間戳）
            current_time_ms = int(time.time() * 1000)
            expires_at_ms = current_time_ms + (token_response.expires_in * 1000)

            return OAuthExchangeResult(
                access_token=token_response.access_token,
                refresh_token=token_response.refresh_token,
                expires_at=expires_at_ms,
            )

    @staticmethod
    async def get_valid_access_token(
        access_token: Optional[str],
        refresh_token: Optional[str],
        expires_at: Optional[int],
    ) -> Optional[str]:
        """
        取得有效的 access token，如果過期則自動更新

        Args:
            access_token: 當前的 access token
            refresh_token: Refresh token
            expires_at: Access token 過期時間（毫秒時間戳）

        Returns:
            有效的 access token，如果無法取得則返回 None
        """
        # 如果有 access token 且未過期，直接返回
        if access_token and expires_at:
            current_time_ms = int(time.time() * 1000)
            if expires_at > current_time_ms:
                return access_token

        # 如果沒有 refresh token，無法更新
        if not refresh_token:
            return None

        # 使用 refresh token 更新
        try:
            result = await OAuthService.refresh_access_token(refresh_token)
            return result.access_token
        except Exception:
            return None

    @staticmethod
    async def get_account_info(access_token: str) -> OAuthAccountInfo:
        """
        使用 access token 取得帳戶資訊

        Args:
            access_token: OAuth access token

        Returns:
            OAuthAccountInfo 包含完整的帳戶和組織資訊

        Raises:
            httpx.HTTPStatusError: 當 API 請求失敗時
        """
        async with httpx.AsyncClient() as client:
            # 1. 取得 profile 資訊
            profile_response = await client.get(
                "https://api.anthropic.com/api/oauth/profile",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if not profile_response.is_success:
                raise httpx.HTTPStatusError(
                    f"Failed to get profile: {profile_response.text}",
                    request=profile_response.request,
                    response=profile_response,
                )

            profile_data = profile_response.json()

            # 2. 取得 roles 資訊
            roles_response = await client.get(
                "https://api.anthropic.com/api/oauth/claude_cli/roles",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )

            if not roles_response.is_success:
                raise httpx.HTTPStatusError(
                    f"Failed to get roles: {roles_response.text}",
                    request=roles_response.request,
                    response=roles_response,
                )

            roles_data = roles_response.json()

            # 3. 組合資訊
            return OAuthAccountInfo(
                account_uuid=profile_data["account"]["uuid"],
                email_address=profile_data["account"]["email"],
                organization_uuid=profile_data["organization"]["uuid"],
                display_name=profile_data["account"]["display_name"],
                organization_billing_type=profile_data["organization"]["billing_type"],
                organization_role=roles_data["organization_role"],
                workspace_role=roles_data.get("workspace_role"),
                organization_name=profile_data["organization"]["name"],
            )


__all__ = ["OAuthService", "PKCEParams", "OAuthExchangeResult", "OAuthAccountInfo"]
