from __future__ import annotations

import base64
from datetime import datetime, timezone
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from app.modules.auth.manager_assertion import (
    ManagerAssertionConflict,
    ManagerAssertionInvalid,
    ManagerAssertionVerifier,
)

NOW = datetime(2026, 7, 20, 1, 0, tzinfo=timezone.utc)
NOW_EPOCH = int(NOW.timestamp())
INSTANCE_ID = "7af68c67-128c-4ae3-b906-f19e0613b91b"


def b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def jwk(private_key: Ed25519PrivateKey, kid: str) -> dict[str, str]:
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
        "kid": kid,
        "x": b64(public),
    }


def sign(
    private_key: Ed25519PrivateKey,
    claims: dict,
    *,
    kid: str = "key-a",
) -> str:
    header = b64(
        json.dumps(
            {"alg": "EdDSA", "kid": kid, "typ": "JWT"},
            separators=(",", ":"),
        ).encode()
    )
    payload = b64(json.dumps(claims, separators=(",", ":")).encode())
    signed = f"{header}.{payload}".encode("ascii")
    return f"{header}.{payload}.{b64(private_key.sign(signed))}"


def drain_claims(**updates) -> dict:
    claims = {
        "iss": "workspace-manager",
        "aud": "workspace-runtime-drain",
        "action": "drain",
        "workspaceId": "workspace-a",
        "expectedRuntimeInstanceId": INSTANCE_ID,
        "expectedMountedRevision": 7,
        "targetRevision": 8,
        "drainAttemptId": "attempt-a",
        "deadline": NOW_EPOCH + 45,
        "jobId": "job-a",
        "iat": NOW_EPOCH,
        "exp": NOW_EPOCH + 45,
        "jti": "jti-a",
    }
    claims.update(updates)
    return claims


def browser_pairing_claims(**updates) -> dict:
    claims = {
        "iss": "workspace-manager",
        "aud": "workspace-browser-extension",
        "action": "browser_automation",
        "actorUserId": "user-a",
        "workspaceId": "workspace-a",
        "runtimeInstanceId": INSTANCE_ID,
        "browserWorkloadIdentity": "browser-uid-a",
        "pairingSessionId": "pairing-a",
        "iat": NOW_EPOCH,
        "exp": NOW_EPOCH + 45,
        "jti": "pairing-jti-a",
    }
    claims.update(updates)
    return claims


def build_verifier(tmp_path, *keys):
    key_entries = [jwk(key, kid) for key, kid in keys]
    key_file = tmp_path / "manager-jwks.json"
    key_file.write_text(json.dumps({"keys": key_entries}), encoding="utf-8")
    return ManagerAssertionVerifier(
        public_key_set_file=key_file,
        issuer="workspace-manager",
        workspace_id="workspace-a",
        runtime_instance_id=INSTANCE_ID,
        mounted_revision=7,
        clock=lambda: NOW,
    )


def test_valid_drain_assertion_checks_current_revision_not_target(tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (private_key, "key-a"))

    verified = verifier.verify_runtime_drain(
        sign(private_key, drain_claims(targetRevision=999))
    )

    assert verified.expected_mounted_revision == 7
    assert verified.target_revision == 999
    assert verified.drain_attempt_id == "attempt-a"


@pytest.mark.parametrize(
    ("update", "error_type"),
    [
        ({"aud": "workspace-terminal-drain"}, ManagerAssertionInvalid),
        ({"action": "start"}, ManagerAssertionInvalid),
        ({"exp": NOW_EPOCH}, ManagerAssertionInvalid),
        ({"exp": NOW_EPOCH + 61, "deadline": NOW_EPOCH + 61}, ManagerAssertionInvalid),
        ({"expectedRuntimeInstanceId": "old-instance"}, ManagerAssertionConflict),
        ({"expectedMountedRevision": 6}, ManagerAssertionConflict),
        ({"workspaceId": "workspace-b"}, ManagerAssertionConflict),
    ],
)
def test_rejects_wrong_audience_time_and_fences(tmp_path, update, error_type) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (private_key, "key-a"))

    with pytest.raises(error_type):
        verifier.verify_runtime_drain(sign(private_key, drain_claims(**update)))


def test_rejects_bad_signature_and_replayed_jti(tmp_path) -> None:
    trusted = Ed25519PrivateKey.generate()
    untrusted = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (trusted, "key-a"))

    with pytest.raises(ManagerAssertionInvalid):
        verifier.verify_runtime_drain(sign(untrusted, drain_claims()))

    assertion = sign(trusted, drain_claims())
    verifier.verify_runtime_drain(assertion)
    with pytest.raises(ManagerAssertionInvalid) as exc_info:
        verifier.verify_runtime_drain(assertion)
    assert exc_info.value.error_code == "RUNTIME_ASSERTION_REPLAYED"


def test_supports_public_key_rotation_and_rejects_unknown_kid(tmp_path) -> None:
    old_key = Ed25519PrivateKey.generate()
    current_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(
        tmp_path,
        (old_key, "key-old"),
        (current_key, "key-current"),
    )

    old = verifier.verify_runtime_drain(
        sign(old_key, drain_claims(jti="old-jti"), kid="key-old")
    )
    current = verifier.verify_runtime_drain(
        sign(current_key, drain_claims(jti="current-jti"), kid="key-current")
    )
    assert old.jti == "old-jti"
    assert current.jti == "current-jti"

    with pytest.raises(ManagerAssertionInvalid) as exc_info:
        verifier.verify_runtime_drain(
            sign(current_key, drain_claims(jti="unknown-jti"), kid="key-unknown")
        )
    assert exc_info.value.error_code == "RUNTIME_ASSERTION_KID_UNKNOWN"


def test_browser_pairing_binds_actor_generation_and_signed_workload_claim(
    tmp_path,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (private_key, "key-a"))
    claims = browser_pairing_claims()

    verified = verifier.verify_browser_pairing(sign(private_key, claims))

    assert verified.actor_user_id == "user-a"
    assert verified.runtime_instance_id == INSTANCE_ID
    assert verified.browser_workload_identity == "browser-uid-a"
    assert verified.pairing_session_id == "pairing-a"


@pytest.mark.parametrize(
    ("claim_name", "claim_value", "error_type"),
    [
        ("runtimeInstanceId", "old-instance", ManagerAssertionConflict),
        ("browserWorkloadIdentity", "", ManagerAssertionInvalid),
    ],
)
def test_browser_pairing_rejects_old_generation_or_missing_signed_workload_claim(
    tmp_path,
    claim_name,
    claim_value,
    error_type,
) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (private_key, "key-a"))
    claims = browser_pairing_claims(jti=f"pairing-jti-{claim_name}")
    claims[claim_name] = claim_value

    with pytest.raises(error_type):
        verifier.verify_browser_pairing(sign(private_key, claims))


def test_browser_pairing_assertion_is_single_use(tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    verifier = build_verifier(tmp_path, (private_key, "key-a"))
    assertion = sign(private_key, browser_pairing_claims())

    verifier.verify_browser_pairing(assertion)

    with pytest.raises(ManagerAssertionInvalid) as exc_info:
        verifier.verify_browser_pairing(assertion)
    assert exc_info.value.error_code == "RUNTIME_ASSERTION_REPLAYED"


def test_jwks_must_not_contain_private_key_material(tmp_path) -> None:
    private_key = Ed25519PrivateKey.generate()
    exposed = jwk(private_key, "key-a")
    exposed["d"] = "private-material"
    key_file = tmp_path / "manager-jwks.json"
    key_file.write_text(json.dumps({"keys": [exposed]}), encoding="utf-8")

    with pytest.raises(ManagerAssertionInvalid) as exc_info:
        ManagerAssertionVerifier(
            public_key_set_file=key_file,
            issuer="workspace-manager",
            workspace_id="workspace-a",
            runtime_instance_id=INSTANCE_ID,
            mounted_revision=7,
        )
    assert exc_info.value.error_code == "RUNTIME_ASSERTION_KEYS_INVALID"
