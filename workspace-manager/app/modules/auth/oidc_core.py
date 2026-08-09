"""Manager-owned OIDC authorization-code flow and External Principal boundary."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.db import models as db_models
from app.modules.auth.session import IssuedManagerSession, ManagerSessionService
from app.modules.auth.token_validation import (
    JWKSFetchError,
    JWTUtils,
    JWTValidationError,
    get_jwt_utils,
)
from app.modules.identity.snapshot_sync import UserSnapshotSyncService

LOGIN_ATTEMPT_LIFETIME = timedelta(minutes=10)
LOGIN_ATTEMPT_LIMIT = 10
LOGIN_ATTEMPT_CLEANUP_BATCH_SIZE = 100


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class OIDCCallbackError(ValueError):
    """OIDC callback failed closed before a Manager session was created."""


class OIDCLoginRateLimitError(ValueError):
    """OIDC login initiation exceeded the per-client attempt window."""


@dataclass(frozen=True)
class LoginStart:
    authorization_url: str
    state: str
    attempt: db_models.OIDCLoginAttempt


@dataclass(frozen=True)
class LoginCompletion:
    user: db_models.User
    session: IssuedManagerSession
    return_path: str


class OIDCCore:
    """Terminate external OIDC and emit only local identity and session state."""

    def __init__(
        self,
        db: Session,
        *,
        config: Settings | None = None,
        jwt_utils: JWTUtils | None = None,
        http_client_factory: Callable[..., Any] = httpx.AsyncClient,
    ) -> None:
        self.db = db
        self.config = config or get_settings()
        self.jwt_utils = jwt_utils or get_jwt_utils()
        self.http_client_factory = http_client_factory

    async def begin_login(
        self,
        *,
        attempt_bucket: str,
        return_path: str = "/",
    ) -> LoginStart:
        if not return_path.startswith("/") or return_path.startswith("//"):
            raise ValueError("OIDC return path must be local")
        now = datetime.now(timezone.utc)
        self._cleanup_expired_attempts(now)
        bucket_hash = _digest(attempt_bucket)
        recent_attempts = self.db.scalar(
            select(func.count(db_models.OIDCLoginAttempt.id)).where(
                db_models.OIDCLoginAttempt.attempt_bucket_hash == bucket_hash,
                db_models.OIDCLoginAttempt.created_at >= now - LOGIN_ATTEMPT_LIFETIME,
            )
        )
        if isinstance(recent_attempts, int) and recent_attempts >= LOGIN_ATTEMPT_LIMIT:
            raise OIDCLoginRateLimitError("OIDC login attempt rate limit exceeded")
        discovery = await self.jwt_utils.fetch_discovery()
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(48)
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
            .decode("ascii")
            .rstrip("=")
        )
        attempt = db_models.OIDCLoginAttempt(
            id=str(uuid4()),
            state_hash=_digest(state),
            code_verifier=verifier,
            nonce=nonce,
            return_path=return_path,
            attempt_bucket_hash=bucket_hash,
            created_at=now,
            expires_at=now + LOGIN_ATTEMPT_LIFETIME,
        )
        self.db.add(attempt)
        self.db.commit()
        query = urlencode(
            {
                "client_id": self.config.OIDC_CLIENT_ID,
                "redirect_uri": self.config.oidc_callback_url,
                "response_type": "code",
                "scope": " ".join(self.config.OIDC_SCOPES),
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return LoginStart(
            authorization_url=f"{discovery.authorization_endpoint}?{query}",
            state=state,
            attempt=attempt,
        )

    def _cleanup_expired_attempts(self, now: datetime) -> None:
        expired_ids = (
            select(db_models.OIDCLoginAttempt.id)
            .where(db_models.OIDCLoginAttempt.expires_at <= now)
            .order_by(db_models.OIDCLoginAttempt.expires_at)
            .limit(LOGIN_ATTEMPT_CLEANUP_BATCH_SIZE)
        )
        self.db.execute(
            delete(db_models.OIDCLoginAttempt).where(
                db_models.OIDCLoginAttempt.id.in_(expired_ids)
            )
        )
        self.db.commit()

    async def provider_logout_url(self) -> str | None:
        """Return a provider logout URL when Discovery advertises one."""

        try:
            discovery = await self.jwt_utils.fetch_discovery()
        except (httpx.HTTPError, JWKSFetchError, TypeError, ValueError):
            return None
        if not discovery.end_session_endpoint:
            return None
        query = {"client_id": self.config.OIDC_CLIENT_ID}
        query["post_logout_redirect_uri"] = (
            self.config.oidc_post_logout_redirect_url
        )
        return f"{discovery.end_session_endpoint}?{urlencode(query)}"

    async def complete_callback(self, *, code: str, state: str) -> LoginCompletion:
        if not code or not state:
            raise OIDCCallbackError("OIDC callback code and state are required")
        attempt = self.db.scalar(
            select(db_models.OIDCLoginAttempt).where(
                db_models.OIDCLoginAttempt.state_hash == _digest(state)
            )
        )
        if attempt is None or datetime.now(timezone.utc) >= _utc(attempt.expires_at):
            raise OIDCCallbackError("OIDC callback state is invalid or expired")
        verifier = attempt.code_verifier
        nonce = attempt.nonce
        return_path = attempt.return_path
        self.db.delete(attempt)
        self.db.commit()

        discovery = await self.jwt_utils.fetch_discovery()
        try:
            async with self.http_client_factory(
                timeout=self.config.OIDC_DISCOVERY_TIMEOUT_SECONDS,
                verify=self.config.OIDC_CA_CERT_FILE or True,
            ) as client:
                response = await client.post(
                    discovery.token_endpoint,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "redirect_uri": self.config.oidc_callback_url,
                        "client_id": self.config.OIDC_CLIENT_ID,
                        "client_secret": self.config.oidc_client_secret,
                        "code_verifier": verifier,
                    },
                    headers={"Accept": "application/json"},
                )
                response.raise_for_status()
                token_payload = response.json()
                id_token = token_payload.get("id_token")
                access_token = token_payload.get("access_token")
                if not isinstance(id_token, str) or not id_token:
                    raise OIDCCallbackError("OIDC token response is missing id_token")
                claims = await self.jwt_utils.decode_id_token_async(
                    id_token,
                    nonce=nonce,
                    access_token=access_token
                    if isinstance(access_token, str)
                    else None,
                )
                if discovery.userinfo_endpoint and isinstance(access_token, str):
                    userinfo_response = await client.get(
                        discovery.userinfo_endpoint,
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    userinfo_response.raise_for_status()
                    userinfo = userinfo_response.json()
                    if userinfo.get("sub") != claims.get("sub"):
                        raise OIDCCallbackError("OIDC UserInfo subject does not match")
                    for key in (
                        "preferred_username",
                        "email",
                        "given_name",
                        "family_name",
                        "name",
                        "picture",
                    ):
                        if key in userinfo:
                            claims[key] = userinfo[key]
        except OIDCCallbackError:
            raise
        except (httpx.HTTPError, JWTValidationError, TypeError, ValueError) as exc:
            raise OIDCCallbackError("OIDC callback exchange failed") from exc

        user = UserSnapshotSyncService(self.db).sync_from_claims(
            claims,
            issuer=self.config.OIDC_ISSUER_URL,
        )
        session = ManagerSessionService(self.db).create(
            user_id=user.id,
            issuer=self.config.OIDC_ISSUER_URL,
            subject=user.oidc_subject or "",
            authentication_context={
                key: claims[key] for key in ("acr", "amr", "auth_time") if key in claims
            },
        )
        return LoginCompletion(user=user, session=session, return_path=return_path)


__all__ = [
    "LoginCompletion",
    "LoginStart",
    "OIDCCallbackError",
    "OIDCLoginRateLimitError",
    "OIDCCore",
]
