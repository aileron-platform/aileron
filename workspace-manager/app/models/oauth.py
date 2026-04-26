"""OAuth related data models"""

from __future__ import annotations

from pydantic import Field

from app.utils.pydantic import CamelModel


class OAuthExchangeRequest(CamelModel):
    """OAuth Code Exchange Request"""
    auth_code: str = Field(..., alias="authCode", description="Authorization code (format: code#state)")
    verifier: str = Field(..., description="PKCE code verifier")


class OAuthExchangeResponse(CamelModel):
    """OAuth Code Exchange Response"""
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    expires_at: int = Field(..., alias="expiresAt", description="Expiration time (millisecond timestamp)")


class OAuthRefreshRequest(CamelModel):
    """OAuth Token Refresh Request"""
    refresh_token: str = Field(..., alias="refreshToken")


class OAuthRefreshResponse(CamelModel):
    """OAuth Token Refresh Response"""
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    expires_at: int = Field(..., alias="expiresAt", description="Expiration time (millisecond timestamp)")


__all__ = [
    "OAuthExchangeRequest",
    "OAuthExchangeResponse",
    "OAuthRefreshRequest",
    "OAuthRefreshResponse",
]

