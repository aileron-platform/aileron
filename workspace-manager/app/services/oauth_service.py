"""OAuth AuthenticationService - Handle Claude OAuth Process"""

from __future__ import annotations

import hashlib
import secrets
import base64
import time
from typing import Optional
import httpx

from pydantic import BaseModel, Field, ConfigDict


class PKCEParams(BaseModel):
    """PKCE Parameter"""
    verifier: str
    challenge: str


class OAuthTokenResponse(BaseModel):
    """OAuth Token Response"""
    access_token: str = Field(..., alias="access_token")
    refresh_token: str = Field(..., alias="refresh_token")
    expires_in: int = Field(..., alias="expires_in")
    token_type: str = Field(default="Bearer", alias="token_type")

    model_config = ConfigDict(populate_by_name=True)


class OAuthExchangeResult(BaseModel):
    """OAuth Exchange Result"""
    access_token: str
    refresh_token: str
    expires_at: int  # Millisecond timestamp


class OAuthAccountInfo(BaseModel):
    """OAuth account information"""
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
    """Handle Claude OAuth AuthenticationProcess"""

    CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
    AUTHORIZATION_URL = "https://claude.ai/oauth/authorize"
    TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
    REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
    SCOPE = "org:create_api_key user:profile user:inference"

    @staticmethod
    def generate_pkce() -> PKCEParams:
        """Generate PKCE code verifier and challenge"""
        # Generate code verifier (43-128 characters)
        verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        
        # Generate code challenge (SHA256 hash of verifier)
        challenge_bytes = hashlib.sha256(verifier.encode('utf-8')).digest()
        challenge = base64.urlsafe_b64encode(challenge_bytes).decode('utf-8').rstrip('=')
        
        return PKCEParams(verifier=verifier, challenge=challenge)

    @staticmethod
    def build_authorization_url(pkce: PKCEParams) -> str:
        """
        Build OAuth authorization URL
        Note: According to reference implementation, state parameter should use verifier's value
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
            "state": pkce.verifier,  # Use verifier as state
        }

        return f"{OAuthService.AUTHORIZATION_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str, verifier: str) -> OAuthExchangeResult:
        """
        Exchange authorization code for access token

        Args:
            code: Authentication code in format "code#state"
            verifier: PKCE code verifier (should be same as state)

        Returns:
            OAuthExchangeResult containing access_token, refresh_token, expires_at

        Raises:
            httpx.HTTPStatusError: When API request fails
            ValueError: When response format is incorrect

        Note: According to reference implementation, state parameter should equal verifier
        """
        # Split code and state
        splits = code.split("#")
        if len(splits) != 2:
            raise ValueError("Invalid authentication code format. Expected format: code#state")

        auth_code = splits[0]
        state = splits[1]

        # Validate if state equals verifier (according to reference implementation)
        if state != verifier:
            raise ValueError(
                f"State mismatch: state={state[:10]}..., verifier={verifier[:10]}... "
                "State should equal verifier in this OAuth flow"
            )

        # Prepare request data (reference AuthAnthropic.exchange)
        payload = {
            "code": auth_code,
            "state": state,
            "grant_type": "authorization_code",
            "client_id": OAuthService.CLIENT_ID,
            "redirect_uri": OAuthService.REDIRECT_URI,
            "code_verifier": verifier,
        }
        
        # SendRequest
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OAuthService.TOKEN_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            
            # CheckResponseStatus
            if not response.is_success:
                error_detail = response.text
                raise httpx.HTTPStatusError(
                    f"OAuth token exchange failed: {error_detail}",
                    request=response.request,
                    response=response,
                )
            
            # ParseResponse
            data = response.json()

            # Avoid exposing sensitive credentials in logs, only record required summary information
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

            # Calculate expiration time (millisecond timestamp)
            # Use current time (milliseconds) + expires_in (seconds) * 1000
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
        Use refresh token to update access token

        Args:
            refresh_token: Refresh token

        Returns:
            OAuthExchangeResult containing new access_token, refresh_token, expires_at

        Raises:
            httpx.HTTPStatusError: When API request fails
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

            # Calculate expiration time (millisecond timestamp)
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
        Get valid access token, automatically update if expired

        Args:
            access_token: Current access token
            refresh_token: Refresh token
            expires_at: Access token expiration time (millisecond timestamp)

        Returns:
            Valid access token, or None if unable to obtain
        """
        # If access token exists and not expired, return directly
        if access_token and expires_at:
            current_time_ms = int(time.time() * 1000)
            if expires_at > current_time_ms:
                return access_token

        # If no refresh token, cannot update
        if not refresh_token:
            return None

        # Use refresh token Update
        try:
            result = await OAuthService.refresh_access_token(refresh_token)
            return result.access_token
        except Exception:
            return None

    @staticmethod
    async def get_account_info(access_token: str) -> OAuthAccountInfo:
        """
        Get account information using access token

        Args:
            access_token: OAuth access token

        Returns:
            OAuthAccountInfo containing complete account and organization information

        Raises:
            httpx.HTTPStatusError: When API request fails
        """
        async with httpx.AsyncClient() as client:
            # 1. Get profile Information
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

            # 2. Get roles Information
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

            # 3. Combine information
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
