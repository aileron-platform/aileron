"""Behavior tests for the Manager-owned OIDC authorization-code boundary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlparse

import pytest

from app.db import models as db_models
from app.config.settings import Settings
from app.modules.auth.oidc_core import (
    LOGIN_ATTEMPT_LIMIT,
    OIDCCallbackError,
    OIDCCore,
    OIDCLoginRateLimitError,
)
from app.modules.auth.token_validation import OIDCDiscoveryDocument


@pytest.fixture()
def bff_config(tmp_path: Path) -> Settings:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")
    return Settings(
        ENV="testing",
        PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        OIDC_ISSUER_URL="https://issuer.example.com/tenant",
        OIDC_CLIENT_ID="aileron-manager",
        OIDC_CLIENT_SECRET_FILE=str(secret_file),
    )


@pytest.mark.asyncio
async def test_login_url_uses_server_owned_state_nonce_and_pkce(
    test_app,
    bff_config: Settings,
) -> None:
    _, session_factory = test_app
    discovery = OIDCDiscoveryDocument(
        issuer=bff_config.OIDC_ISSUER_URL,
        jwks_uri=f"{bff_config.OIDC_ISSUER_URL}/jwks",
        authorization_endpoint=f"{bff_config.OIDC_ISSUER_URL}/authorize",
        token_endpoint=f"{bff_config.OIDC_ISSUER_URL}/token",
    )
    oidc = Mock()
    oidc.fetch_discovery = AsyncMock(return_value=discovery)

    with session_factory() as db:
        result = await OIDCCore(db, config=bff_config, jwt_utils=oidc).begin_login(
            attempt_bucket="browser-attempt-bucket-1", return_path="/workspaces"
        )
        params = parse_qs(urlparse(result.authorization_url).query)

        assert params["client_id"] == ["aileron-manager"]
        assert params["redirect_uri"] == [bff_config.oidc_callback_url]
        assert params["response_type"] == ["code"]
        assert params["code_challenge_method"] == ["S256"]
        assert len(params["state"][0]) >= 43
        assert len(params["nonce"][0]) >= 43
        assert result.state not in repr(db.query(type(result.attempt)).all())


@pytest.mark.asyncio
async def test_callback_creates_local_identity_and_opaque_session_without_tokens(
    test_app,
    bff_config: Settings,
) -> None:
    _, session_factory = test_app
    discovery = OIDCDiscoveryDocument(
        issuer=bff_config.OIDC_ISSUER_URL,
        jwks_uri=f"{bff_config.OIDC_ISSUER_URL}/jwks",
        authorization_endpoint=f"{bff_config.OIDC_ISSUER_URL}/authorize",
        token_endpoint=f"{bff_config.OIDC_ISSUER_URL}/token",
        userinfo_endpoint=f"{bff_config.OIDC_ISSUER_URL}/userinfo",
    )
    oidc = Mock()
    oidc.fetch_discovery = AsyncMock(return_value=discovery)
    oidc.decode_id_token_async = AsyncMock(
        return_value={
            "iss": bff_config.OIDC_ISSUER_URL,
            "sub": "directory-user-1",
            "preferred_username": "nova",
            "email": "nova@example.com",
            "acr": "urn:mfa",
        }
    )
    provider = AsyncMock()
    token_response = Mock()
    token_response.raise_for_status = Mock()
    token_response.json.return_value = {
        "access_token": "provider-access-token",
        "id_token": "provider-id-token",
        "token_type": "Bearer",
    }
    provider.post.return_value = token_response
    userinfo_response = Mock()
    userinfo_response.raise_for_status = Mock()
    userinfo_response.json.return_value = {"sub": "directory-user-1"}
    provider.get.return_value = userinfo_response
    provider.__aenter__.return_value = provider
    provider.__aexit__.return_value = None

    with session_factory() as db:
        core = OIDCCore(
            db,
            config=bff_config,
            jwt_utils=oidc,
            http_client_factory=lambda **_: provider,
        )
        login = await core.begin_login(
            attempt_bucket="browser-attempt-bucket-1",
            return_path="/workspaces",
        )
        callback = await core.complete_callback(code="code-1", state=login.state)

        assert callback.user.oidc_issuer == bff_config.OIDC_ISSUER_URL
        assert callback.user.oidc_subject == "directory-user-1"
        assert callback.session.handle != "provider-access-token"
        assert callback.return_path == "/workspaces"
        assert "token" not in callback.session.__dict__
        oidc.decode_id_token_async.assert_awaited_once_with(
            "provider-id-token",
            nonce=login.attempt.nonce,
            access_token="provider-access-token",
        )

        with pytest.raises(OIDCCallbackError, match="state"):
            await core.complete_callback(code="code-1", state=login.state)


@pytest.mark.asyncio
async def test_logout_url_uses_platform_origin_derived_redirect(
    test_app,
    bff_config: Settings,
) -> None:
    _, session_factory = test_app
    oidc = Mock()
    oidc.fetch_discovery = AsyncMock(
        return_value=OIDCDiscoveryDocument(
            issuer=bff_config.OIDC_ISSUER_URL,
            jwks_uri=f"{bff_config.OIDC_ISSUER_URL}/jwks",
            authorization_endpoint=f"{bff_config.OIDC_ISSUER_URL}/authorize",
            token_endpoint=f"{bff_config.OIDC_ISSUER_URL}/token",
            end_session_endpoint=f"{bff_config.OIDC_ISSUER_URL}/logout",
        )
    )

    with session_factory() as db:
        logout_url = await OIDCCore(
            db,
            config=bff_config,
            jwt_utils=oidc,
        ).provider_logout_url()

    assert logout_url is not None
    params = parse_qs(urlparse(logout_url).query)
    assert params["client_id"] == ["aileron-manager"]
    assert params["post_logout_redirect_uri"] == [
        "https://aileron.example.com/login"
    ]


@pytest.mark.asyncio
async def test_login_removes_expired_attempts_in_bounded_batches(
    test_app,
    bff_config: Settings,
) -> None:
    _, session_factory = test_app
    oidc = Mock()
    oidc.fetch_discovery = AsyncMock(
        return_value=OIDCDiscoveryDocument(
            issuer=bff_config.OIDC_ISSUER_URL,
            jwks_uri=f"{bff_config.OIDC_ISSUER_URL}/jwks",
            authorization_endpoint=f"{bff_config.OIDC_ISSUER_URL}/authorize",
            token_endpoint=f"{bff_config.OIDC_ISSUER_URL}/token",
        )
    )
    now = datetime.now(timezone.utc)

    with session_factory() as db:
        expired = db_models.OIDCLoginAttempt(
            id="expired-attempt",
            state_hash="expired-state",
            code_verifier="verifier",
            nonce="nonce",
            return_path="/",
            attempt_bucket_hash="expired-client",
            created_at=now - timedelta(minutes=20),
            expires_at=now - timedelta(minutes=10),
        )
        db.add(expired)
        db.commit()
        expired_attempt_id = expired.id

        await OIDCCore(db, config=bff_config, jwt_utils=oidc).begin_login(
            attempt_bucket="browser-attempt-bucket-1",
            return_path="/",
        )

        assert db.get(db_models.OIDCLoginAttempt, expired_attempt_id) is None


@pytest.mark.asyncio
async def test_login_rate_limits_each_browser_attempt_bucket(
    test_app,
    bff_config: Settings,
) -> None:
    _, session_factory = test_app
    oidc = Mock()
    oidc.fetch_discovery = AsyncMock(
        return_value=OIDCDiscoveryDocument(
            issuer=bff_config.OIDC_ISSUER_URL,
            jwks_uri=f"{bff_config.OIDC_ISSUER_URL}/jwks",
            authorization_endpoint=f"{bff_config.OIDC_ISSUER_URL}/authorize",
            token_endpoint=f"{bff_config.OIDC_ISSUER_URL}/token",
        )
    )

    with session_factory() as db:
        core = OIDCCore(db, config=bff_config, jwt_utils=oidc)
        for _ in range(LOGIN_ATTEMPT_LIMIT):
            await core.begin_login(
                attempt_bucket="browser-attempt-bucket-1",
                return_path="/",
            )

        with pytest.raises(OIDCLoginRateLimitError):
            await core.begin_login(
                attempt_bucket="browser-attempt-bucket-1",
                return_path="/",
            )

        await core.begin_login(
            attempt_bucket="browser-attempt-bucket-2",
            return_path="/",
        )
