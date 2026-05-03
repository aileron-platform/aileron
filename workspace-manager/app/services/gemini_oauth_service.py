"""Gemini Google OAuth service"""

import time
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config.settings import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


@dataclass
class GeminiTokenResult:
    access_token: str
    refresh_token: Optional[str]
    id_token: Optional[str]
    expires_at: int
    scope: str
    token_type: str


@dataclass
class GeminiUserInfo:
    email: Optional[str]
    name: Optional[str]


class GeminiOAuthService:
    @staticmethod
    def _get_google_oauth_config() -> tuple[str, str, str]:
        settings = get_settings()
        client_id = settings.GEMINI_GOOGLE_CLIENT_ID.strip()
        client_secret = settings.GEMINI_GOOGLE_CLIENT_SECRET.strip()
        redirect_uri = settings.GEMINI_GOOGLE_REDIRECT_URI.strip()

        if not client_id or not client_secret:
            raise ValueError("Gemini Google OAuth credentials are not configured")
        if not redirect_uri:
            raise ValueError("Gemini Google OAuth redirect URI is not configured")

        return client_id, client_secret, redirect_uri

    @staticmethod
    async def exchange_code(code: str, verifier: str) -> GeminiTokenResult:
        client_id, client_secret, redirect_uri = GeminiOAuthService._get_google_oauth_config()
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(_GOOGLE_TOKEN_URL, data=payload)
            resp.raise_for_status()
            data = resp.json()

        expires_in = data.get("expires_in", 3600)
        expires_at = int(time.time() * 1000) + expires_in * 1000

        logger.info("Gemini OAuth code exchanged successfully")
        return GeminiTokenResult(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            id_token=data.get("id_token"),
            expires_at=expires_at,
            scope=data.get("scope", ""),
            token_type=data.get("token_type", "Bearer"),
        )

    @staticmethod
    async def get_userinfo(access_token: str) -> GeminiUserInfo:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        return GeminiUserInfo(
            email=data.get("email"),
            name=data.get("name"),
        )
