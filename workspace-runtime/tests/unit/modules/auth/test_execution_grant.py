"""Behavior tests for local Runtime Execution Grant verification."""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
    ExecutionGrantVerifier,
)


def _verifier(tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    jwks = tmp_path / "jwks.json"
    jwks.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "use": "sig",
                        "alg": "EdDSA",
                        "kid": "manager-v1",
                        "x": base64.urlsafe_b64encode(public).rstrip(b"=").decode(),
                    }
                ]
            }
        )
    )
    now = datetime.now(timezone.utc)

    def token(**overrides):
        claims = {
            "iss": "workspace-manager",
            "sub": "local-user-1",
            "aud": "workspace-runtime",
            "kind": "workspace-execution-access-grant",
            "workspaceId": "workspace-1",
            "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
            "runtimeAccessRevision": 7,
            "actions": ["agent", "runtime_read"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
            "jti": "reusable-grant",
        }
        claims.update(overrides)
        return jwt.encode(
            claims,
            private_key,
            algorithm="EdDSA",
            headers={"kid": "manager-v1", "typ": "JWT"},
        )

    return (
        ExecutionGrantVerifier(
            public_key_set_file=jwks,
            issuer="workspace-manager",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            runtime_access_revision=7,
            clock=lambda: now,
        ),
        token,
    )


def _write_jwks(path, *, kid: str, private_key: Ed25519PrivateKey) -> None:
    public = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    path.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "use": "sig",
                        "alg": "EdDSA",
                        "kid": kid,
                        "x": base64.urlsafe_b64encode(public).rstrip(b"=").decode(),
                    }
                ]
            }
        )
    )


def _rotation_verifier(path, now: datetime) -> ExecutionGrantVerifier:
    return ExecutionGrantVerifier(
        public_key_set_file=path,
        issuer="workspace-manager",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        runtime_access_revision=7,
        clock=lambda: now,
    )


def _rotation_token(private_key: Ed25519PrivateKey, *, kid: str, now: datetime) -> str:
    return jwt.encode(
        {
            "iss": "workspace-manager",
            "sub": "local-user-1",
            "aud": "workspace-runtime",
            "kind": "workspace-execution-access-grant",
            "workspaceId": "workspace-1",
            "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
            "runtimeAccessRevision": 7,
            "actions": ["runtime_read"],
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=60)).timestamp()),
            "jti": f"grant-{kid}",
        },
        private_key,
        algorithm="EdDSA",
        headers={"kid": kid, "typ": "JWT"},
    )


def test_grant_is_reusable_within_ttl_and_requires_route_action(tmp_path) -> None:
    verifier, token = _verifier(tmp_path)
    grant = token()

    first = verifier.verify(grant, action="agent")
    second = verifier.verify(grant, action="agent")

    assert first.subject == second.subject == "local-user-1"
    with pytest.raises(ExecutionGrantInvalid):
        verifier.verify(grant, action="runtime_write")


@pytest.mark.parametrize(
    ("override", "error"),
    [
        ({"aud": "workspace-terminal"}, ExecutionGrantInvalid),
        ({"workspaceId": "workspace-2"}, ExecutionGrantConflict),
        (
            {"runtimeInstanceId": "22222222-2222-4222-8222-222222222222"},
            ExecutionGrantConflict,
        ),
        ({"runtimeAccessRevision": 8}, ExecutionGrantConflict),
        ({"kind": "runtime-command"}, ExecutionGrantInvalid),
    ],
)
def test_grant_fails_closed_for_wrong_boundary(tmp_path, override, error) -> None:
    verifier, token = _verifier(tmp_path)
    with pytest.raises(error):
        verifier.verify(token(**override), action="agent")


def test_unknown_kid_reloads_atomically_projected_jwks_once(tmp_path) -> None:
    now = datetime.now(timezone.utc)
    old_key = Ed25519PrivateKey.generate()
    new_key = Ed25519PrivateKey.generate()
    jwks = tmp_path / "jwks.json"
    _write_jwks(jwks, kid="manager-v1", private_key=old_key)
    verifier = _rotation_verifier(jwks, now)

    projected = tmp_path / "jwks.next"
    _write_jwks(projected, kid="manager-v2", private_key=new_key)
    os.replace(projected, jwks)

    claims = verifier.verify(
        _rotation_token(new_key, kid="manager-v2", now=now),
        action="runtime_read",
    )

    assert claims.jti == "grant-manager-v2"


def test_malformed_unknown_kid_reload_fails_closed_and_keeps_trusted_keys(
    tmp_path,
) -> None:
    now = datetime.now(timezone.utc)
    old_key = Ed25519PrivateKey.generate()
    unknown_key = Ed25519PrivateKey.generate()
    jwks = tmp_path / "jwks.json"
    _write_jwks(jwks, kid="manager-v1", private_key=old_key)
    verifier = _rotation_verifier(jwks, now)

    projected = tmp_path / "jwks.next"
    projected.write_text("{malformed")
    os.replace(projected, jwks)

    with pytest.raises(ExecutionGrantInvalid):
        verifier.verify(
            _rotation_token(unknown_key, kid="manager-v2", now=now),
            action="runtime_read",
        )
    assert (
        verifier.verify(
            _rotation_token(old_key, kid="manager-v1", now=now),
            action="runtime_read",
        ).jti
        == "grant-manager-v1"
    )
