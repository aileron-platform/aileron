from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from app.modules.auth import jwt_utils as jwt_module


@pytest.fixture
def utils(monkeypatch):
    monkeypatch.setattr(
        jwt_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(
            enabled=True,
            jwks_cache_ttl=60,
            jwks_url="https://example.test/certs",
            jwt_algorithm="RS256",
            client_id="client-1",
        ),
    )
    return jwt_module.JWTUtils()


async def test_fetch_jwks_uses_cache_and_fetches(utils, monkeypatch) -> None:
    utils.jwks_cache = {"keys": [{"kid": "cached"}]}
    utils.jwks_cache_time = datetime.now(UTC)
    assert await utils.fetch_jwks() == {"keys": [{"kid": "cached"}]}

    utils.jwks_cache_time = datetime.now(UTC) - timedelta(seconds=120)
    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"keys": [{"kid": "fresh"}]},
    )
    client = AsyncMock()
    client.get.return_value = response
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    monkeypatch.setattr(jwt_module.httpx, "AsyncClient", lambda timeout=10.0: client)

    assert await utils.fetch_jwks() == {"keys": [{"kid": "fresh"}]}


async def test_fetch_jwks_raises_for_disabled_or_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        jwt_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(enabled=False, jwks_cache_ttl=60, jwks_url=None, jwt_algorithm="RS256", client_id="x"),
    )
    disabled = jwt_module.JWTUtils()
    with pytest.raises(jwt_module.JWKSFetchError):
        await disabled.fetch_jwks()

    monkeypatch.setattr(
        jwt_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(enabled=True, jwks_cache_ttl=60, jwks_url="https://example.test/certs", jwt_algorithm="RS256", client_id="x"),
    )
    utils = jwt_module.JWTUtils()
    client = AsyncMock()
    client.get.side_effect = httpx.HTTPError("network")
    client.__aenter__.return_value = client
    client.__aexit__.return_value = None
    monkeypatch.setattr(jwt_module.httpx, "AsyncClient", lambda timeout=10.0: client)
    with pytest.raises(jwt_module.JWKSFetchError):
        await utils.fetch_jwks()


def test_get_public_key_validates_header_and_cache(utils, monkeypatch) -> None:
    monkeypatch.setattr(jwt_module.jwt, "get_unverified_headers", lambda token: {"kid": "k1"})
    utils.jwks_cache = {"keys": [{"kid": "k1", "kty": "RSA"}]}
    assert utils.get_public_key("aaa.bbb.ccc")["kid"] == "k1"

    monkeypatch.setattr(jwt_module.jwt, "get_unverified_headers", lambda token: {})
    with pytest.raises(jwt_module.JWTValidationError):
        utils.get_public_key("aaa.bbb.ccc")

    monkeypatch.setattr(jwt_module.jwt, "get_unverified_headers", lambda token: {"kid": "missing"})
    with pytest.raises(jwt_module.JWTValidationError):
        utils.get_public_key("aaa.bbb.ccc")


def test_decode_token_success_and_error_mapping(utils, monkeypatch) -> None:
    monkeypatch.setattr(utils, "get_public_key", lambda token: {"kid": "k1"})

    class FakeRSAKey:
        def to_pem(self):
            return b"pem"

    monkeypatch.setattr(jwt_module.jwk, "construct", lambda key: FakeRSAKey())
    monkeypatch.setattr(
        jwt_module.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "user-1", "azp": "client-1"},
    )
    payload = utils.decode_token("aaa.bbb.ccc")
    assert payload["sub"] == "user-1"

    monkeypatch.setattr(
        jwt_module.jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "user-1", "azp": "other-client"},
    )
    with pytest.raises(jwt_module.JWTValidationError) as exc:
        utils.decode_token("aaa.bbb.ccc")
    assert "Token not issued for this client" in str(exc.value)

    monkeypatch.setattr(jwt_module.jwt, "decode", lambda *args, **kwargs: (_ for _ in ()).throw(ExpiredSignatureError()))
    with pytest.raises(jwt_module.JWTValidationError):
        utils.decode_token("aaa.bbb.ccc")

    monkeypatch.setattr(jwt_module.jwt, "decode", lambda *args, **kwargs: (_ for _ in ()).throw(JWTClaimsError("claims")))
    with pytest.raises(jwt_module.JWTValidationError):
        utils.decode_token("aaa.bbb.ccc")

    monkeypatch.setattr(jwt_module.jwt, "decode", lambda *args, **kwargs: (_ for _ in ()).throw(JWTError("bad token")))
    with pytest.raises(jwt_module.JWTValidationError):
        utils.decode_token("aaa.bbb.ccc")


async def test_decode_token_async_loads_cache_and_wraps_unknown_errors(utils, monkeypatch) -> None:
    monkeypatch.setattr(utils, "fetch_jwks", AsyncMock(return_value={"keys": [{"kid": "k1"}]}))
    monkeypatch.setattr(utils, "decode_token", lambda token, verify_audience=True: {"sub": "user-1"})
    assert await utils.decode_token_async("aaa.bbb.ccc") == {"sub": "user-1"}

    monkeypatch.setattr(utils, "decode_token", lambda token, verify_audience=True: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(jwt_module.JWTValidationError) as exc:
        await utils.decode_token_async("aaa.bbb.ccc")
    assert "Token validation failed" in str(exc.value)


def test_utils_singleton_and_clear(monkeypatch) -> None:
    monkeypatch.setattr(
        jwt_module,
        "get_keycloak_config",
        lambda: SimpleNamespace(enabled=True, jwks_cache_ttl=60, jwks_url="https://example.test/certs", jwt_algorithm="RS256", client_id="client-1"),
    )
    jwt_module._jwt_utils_instance = None
    utils1 = jwt_module.get_jwt_utils()
    utils2 = jwt_module.get_jwt_utils()
    assert utils1 is utils2

    utils1.jwks_cache = {"keys": []}
    utils1.jwks_cache_time = datetime.now(UTC)
    jwt_module.clear_jwt_utils_cache()
    assert utils1.jwks_cache is None
