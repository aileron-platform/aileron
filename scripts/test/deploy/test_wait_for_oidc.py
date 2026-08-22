"""OIDC discovery and JWKS readiness gate tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "wait_for_oidc.py"
)
SPEC = importlib.util.spec_from_file_location("wait_for_oidc", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_accepts_matching_discovery_and_non_empty_jwks() -> None:
    issuer = "https://identity.example.test/realms/aileron"
    documents = {
        f"{issuer}/.well-known/openid-configuration": {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/protocol/openid-connect/auth",
            "token_endpoint": f"{issuer}/protocol/openid-connect/token",
            "jwks_uri": f"{issuer}/protocol/openid-connect/certs",
        },
        f"{issuer}/protocol/openid-connect/certs": {
            "keys": [{"kid": "key-1", "kty": "RSA"}]
        },
    }

    MODULE.wait_for_oidc(
        issuer_url=issuer,
        timeout_seconds=1,
        fetch_json=lambda url: documents[url],
        monotonic=lambda: 0,
        sleep=lambda _: None,
    )


def test_accepts_trailing_slash_issuer_and_cross_authority_endpoints() -> None:
    issuer = "https://identity.example.test/application/o/aileron/"
    discovery_url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    documents = {
        discovery_url: {
            "issuer": issuer,
            "authorization_endpoint": "https://login.example.test/authorize",
            "token_endpoint": "https://tokens.example.test/token",
            "jwks_uri": "https://cdn.example.test/aileron/jwks.json",
        },
        "https://cdn.example.test/aileron/jwks.json": {
            "keys": [{"kid": "key-1", "kty": "EC"}]
        },
    }

    MODULE.wait_for_oidc(
        issuer_url=issuer,
        timeout_seconds=1,
        fetch_json=lambda url: documents[url],
        monotonic=lambda: 0,
        sleep=lambda _: None,
    )


@pytest.mark.parametrize(
    "discovery",
    [
        {
            "issuer": "https://wrong.example.test",
            "authorization_endpoint": "https://identity.example.test/auth",
            "token_endpoint": "https://identity.example.test/token",
            "jwks_uri": "https://identity.example.test/keys",
        },
        {
            "issuer": "https://identity.example.test/realms/aileron",
            "authorization_endpoint": "https://identity.example.test/auth",
            "token_endpoint": "https://identity.example.test/token",
            "jwks_uri": "http://identity.example.test/keys",
        },
        {
            "issuer": "https://identity.example.test/realms/aileron",
            "authorization_endpoint": "https://identity.example.test/auth",
            "token_endpoint": "https://user:password@identity.example.test/token",
            "jwks_uri": "https://identity.example.test/keys",
        },
    ],
)
def test_retries_then_times_out_on_discovery_drift(discovery: dict[str, str]) -> None:
    times = iter([0.0, 2.0])
    with pytest.raises(MODULE.OIDCReadinessError, match="not ready"):
        MODULE.wait_for_oidc(
            issuer_url="https://identity.example.test/realms/aileron",
            timeout_seconds=1,
            fetch_json=lambda _: discovery,
            monotonic=lambda: next(times),
            sleep=lambda _: None,
        )


def test_retries_then_times_out_on_empty_jwks() -> None:
    issuer = "https://identity.example.test/realms/aileron"
    times = iter([0.0, 0.5, 2.0])

    def fetch(url: str) -> dict:
        if url.endswith("openid-configuration"):
            return {
                "issuer": issuer,
                "authorization_endpoint": f"{issuer}/auth",
                "token_endpoint": f"{issuer}/token",
                "jwks_uri": f"{issuer}/certs",
            }
        return {"keys": []}

    with pytest.raises(MODULE.OIDCReadinessError, match="not ready"):
        MODULE.wait_for_oidc(
            issuer_url=issuer,
            timeout_seconds=1,
            fetch_json=fetch,
            monotonic=lambda: next(times),
            sleep=lambda _: None,
        )


def test_http_fetcher_rejects_non_object_or_oversized_response() -> None:
    class Response:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, limit: int) -> bytes:
            return self.content[:limit]

    with pytest.raises(ValueError, match="object"):
        MODULE.fetch_json(
            "https://identity.example.test/document",
            opener=lambda *_args, **_kwargs: Response(json.dumps([]).encode()),
        )
    with pytest.raises(ValueError, match="large"):
        MODULE.fetch_json(
            "https://identity.example.test/document",
            opener=lambda *_args, **_kwargs: Response(
                b"x" * (MODULE.MAX_RESPONSE_BYTES + 1)
            ),
        )
