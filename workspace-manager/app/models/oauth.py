"""OAuth 相關資料模型"""

from __future__ import annotations

from pydantic import Field

from app.utils.pydantic import CamelModel


class OAuthExchangeRequest(CamelModel):
    """OAuth Code Exchange 請求"""
    auth_code: str = Field(..., alias="authCode", description="認證碼 (格式: code#state)")
    verifier: str = Field(..., description="PKCE code verifier")


class OAuthExchangeResponse(CamelModel):
    """OAuth Code Exchange 回應"""
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    expires_at: int = Field(..., alias="expiresAt", description="過期時間（毫秒時間戳）")


class OAuthRefreshRequest(CamelModel):
    """OAuth Token Refresh 請求"""
    refresh_token: str = Field(..., alias="refreshToken")


class OAuthRefreshResponse(CamelModel):
    """OAuth Token Refresh 回應"""
    access_token: str = Field(..., alias="accessToken")
    refresh_token: str = Field(..., alias="refreshToken")
    expires_at: int = Field(..., alias="expiresAt", description="過期時間（毫秒時間戳）")


__all__ = [
    "OAuthExchangeRequest",
    "OAuthExchangeResponse",
    "OAuthRefreshRequest",
    "OAuthRefreshResponse",
]

