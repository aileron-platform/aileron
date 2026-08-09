"""OIDC discovery and confidential-client ID-token validation tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.config.settings import Settings
from app.modules.auth.token_validation import (
    JWKSFetchError,
    JWTUtils,
    JWTValidationError,
    OIDCDiscoveryDocument,
)


@pytest.fixture()
def config(tmp_path: Path) -> Settings:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")
    return Settings(
        ENV="testing",
        PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        OIDC_ISSUER_URL="https://issuer.example.com/tenant",
        OIDC_CLIENT_ID="aileron-web",
        OIDC_CLIENT_SECRET_FILE=str(secret_file),
        OIDC_ALLOWED_ALGORITHMS=["RS256"],
        OIDC_MAX_TOKEN_LIFETIME_SECONDS=1800,
        OIDC_JWKS_CACHE_TTL=3600,
    )


@pytest.fixture()
def jwt_utils(config: Settings) -> JWTUtils:
    return JWTUtils(config)


@pytest.fixture()
def discovery() -> OIDCDiscoveryDocument:
    return OIDCDiscoveryDocument(
        issuer="https://issuer.example.com/tenant",
        jwks_uri="https://issuer.example.com/tenant/keys",
        authorization_endpoint="https://issuer.example.com/tenant/authorize",
        token_endpoint="https://issuer.example.com/tenant/token",
        userinfo_endpoint="https://issuer.example.com/tenant/userinfo",
        end_session_endpoint="https://issuer.example.com/tenant/logout",
    )


def _valid_payload(**overrides: object) -> dict[str, object]:
    now = datetime.now(timezone.utc).timestamp()
    payload: dict[str, object] = {
        "iss": "https://issuer.example.com/tenant",
        "sub": "directory-user-1",
        "aud": ["aileron-web"],
        "iat": now - 60,
        "exp": now + 600,
        "nbf": now - 60,
        "azp": "different-client-is-not-used",
    }
    payload.update(overrides)
    return payload


def test_discovery_document_rejects_issuer_mismatch() -> None:
    with pytest.raises(JWKSFetchError, match="issuer does not match"):
        OIDCDiscoveryDocument.from_payload(
            {
                "issuer": "https://other.example.com",
                "jwks_uri": "https://other.example.com/keys",
                "authorization_endpoint": "https://other.example.com/auth",
                "token_endpoint": "https://other.example.com/token",
            },
            "https://issuer.example.com/tenant",
        )


def test_discovery_document_rejects_http_endpoint_for_https_issuer() -> None:
    with pytest.raises(JWKSFetchError, match="jwks_uri"):
        OIDCDiscoveryDocument.from_payload(
            {
                "issuer": "https://issuer.example.com/tenant",
                "jwks_uri": "http://issuer.example.com/tenant/keys",
                "authorization_endpoint": "https://issuer.example.com/tenant/auth",
                "token_endpoint": "https://issuer.example.com/tenant/token",
            },
            "https://issuer.example.com/tenant",
        )


@pytest.mark.asyncio
async def test_fetch_discovery_validates_and_caches_document(
    jwt_utils: JWTUtils,
    discovery: OIDCDiscoveryDocument,
) -> None:
    response = Mock()
    response.json.return_value = {
        "issuer": discovery.issuer,
        "jwks_uri": discovery.jwks_uri,
        "authorization_endpoint": discovery.authorization_endpoint,
        "token_endpoint": discovery.token_endpoint,
    }
    response.raise_for_status = Mock()
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=response)) as get:
        first = await jwt_utils.fetch_discovery()
        second = await jwt_utils.fetch_discovery()

    assert (
        first
        == second
        == discovery.__class__(
            issuer=discovery.issuer,
            jwks_uri=discovery.jwks_uri,
            authorization_endpoint=discovery.authorization_endpoint,
            token_endpoint=discovery.token_endpoint,
        )
    )
    get.assert_awaited_once()


@pytest.mark.asyncio
async def test_fetch_discovery_uses_configured_ca_certificate(
    discovery: OIDCDiscoveryDocument,
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "oidc-client-secret"
    secret_file.write_text("manager-secret\n", encoding="utf-8")
    config = Settings(
        ENV="testing",
        PLATFORM_PUBLIC_ORIGIN="https://aileron.example.com",
        OIDC_ISSUER_URL=discovery.issuer,
        OIDC_CLIENT_ID="aileron-web",
        OIDC_CLIENT_SECRET_FILE=str(secret_file),
        OIDC_CA_CERT_FILE="/etc/aileron/oidc-ca/ca.crt",
    )
    response = Mock()
    response.json.return_value = {
        "issuer": discovery.issuer,
        "jwks_uri": discovery.jwks_uri,
        "authorization_endpoint": discovery.authorization_endpoint,
        "token_endpoint": discovery.token_endpoint,
    }
    response.raise_for_status = Mock()
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    client.get.return_value = response

    with patch(
        "app.modules.auth.token_validation.httpx.AsyncClient",
        return_value=client,
    ) as async_client:
        await JWTUtils(config).fetch_discovery()

    async_client.assert_called_once_with(
        timeout=config.OIDC_DISCOVERY_TIMEOUT_SECONDS,
        verify=config.OIDC_CA_CERT_FILE,
    )


@pytest.mark.asyncio
async def test_unknown_kid_refreshes_jwks_once(
    jwt_utils: JWTUtils,
) -> None:
    public_key = {"kid": "rotated", "kty": "RSA", "alg": "RS256"}
    jwt_utils.fetch_jwks = AsyncMock(
        side_effect=[
            {"keys": [{"kid": "old", "kty": "RSA", "alg": "RS256"}]},
            {"keys": [public_key]},
        ]
    )
    with patch(
        "app.modules.auth.token_validation.jwt.get_unverified_headers",
        return_value={"kid": "rotated", "alg": "RS256"},
    ):
        result = await jwt_utils.get_public_key_async("token")

    assert result == public_key
    assert jwt_utils.fetch_jwks.await_count == 2
    assert jwt_utils.fetch_jwks.await_args_list[1].kwargs == {"force": True}


@pytest.mark.asyncio
async def test_id_token_requires_manager_client_audience_and_nonce(
    jwt_utils: JWTUtils,
) -> None:
    public_key = {"kid": "one", "kty": "RSA", "alg": "RS256"}
    jwt_utils.get_public_key_async = AsyncMock(return_value=public_key)
    with (
        patch("app.modules.auth.token_validation.jwk.construct") as construct,
        patch(
            "app.modules.auth.token_validation.jwt.decode",
            return_value=_valid_payload(aud=["other-client"], nonce="nonce-1"),
        ),
        patch(
            "app.modules.auth.token_validation.jwt.get_unverified_headers",
            return_value={"kid": "one", "alg": "RS256"},
        ),
    ):
        key = Mock()
        key.to_pem.return_value = b"pem"
        construct.return_value = key
        with pytest.raises(JWTValidationError, match="client ID"):
            await jwt_utils.decode_id_token_async("token", nonce="nonce-1")


@pytest.mark.asyncio
async def test_id_token_passes_access_token_for_at_hash_validation(
    jwt_utils: JWTUtils,
) -> None:
    public_key = {"kid": "one", "kty": "RSA", "alg": "RS256"}
    jwt_utils.get_public_key_async = AsyncMock(return_value=public_key)
    with (
        patch("app.modules.auth.token_validation.jwk.construct") as construct,
        patch(
            "app.modules.auth.token_validation.jwt.decode",
            return_value=_valid_payload(nonce="nonce-1", at_hash="provider-hash"),
        ) as decode,
        patch(
            "app.modules.auth.token_validation.jwt.get_unverified_headers",
            return_value={"kid": "one", "alg": "RS256"},
        ),
    ):
        key = Mock()
        key.to_pem.return_value = b"pem"
        construct.return_value = key

        await jwt_utils.decode_id_token_async(
            "provider-id-token",
            nonce="nonce-1",
            access_token="provider-access-token",
        )

    assert decode.call_args.kwargs["access_token"] == "provider-access-token"
