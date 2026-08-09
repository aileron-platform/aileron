"""Canonical Workspace Execution Access Grant verifier conformance."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.auth.execution_grant import (
    ExecutionGrantConflict,
    ExecutionGrantInvalid,
    ExecutionGrantVerifier,
)


CONTRACT_ROOT = Path("/app/contracts/workspace-execution-access")


def _vectors() -> dict[str, object]:
    return json.loads((CONTRACT_ROOT / "conformance-vectors.json").read_text())


def _verifier(
    tmp_path: Path,
    vectors: dict[str, object],
) -> tuple[ExecutionGrantVerifier, Ed25519PrivateKey]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    jwks_file = tmp_path / "jwks.json"
    jwks_file.write_text(
        json.dumps(
            {
                "keys": [
                    {
                        "kty": "OKP",
                        "crv": "Ed25519",
                        "use": "sig",
                        "alg": "EdDSA",
                        "kid": "manager-v1",
                        "x": base64.urlsafe_b64encode(public_key)
                        .rstrip(b"=")
                        .decode(),
                    }
                ]
            }
        )
    )
    expected = vectors["expectedContext"]
    verifier = ExecutionGrantVerifier(
        public_key_set_file=jwks_file,
        issuer=expected["issuer"],
        workspace_id=expected["workspaceId"],
        runtime_instance_id=expected["runtimeInstanceId"],
        runtime_access_revision=expected["runtimeAccessRevision"],
        clock=lambda: datetime.fromtimestamp(
            vectors["validationEpoch"], tz=timezone.utc
        ),
    )
    return verifier, private_key


def test_runtime_verifier_conforms_to_canonical_vectors(tmp_path: Path) -> None:
    vectors = _vectors()
    verifier, private_key = _verifier(tmp_path, vectors)

    for case in vectors["verificationCases"]:
        if case["consumer"] != "runtime":
            continue
        token = jwt.encode(
            case["claims"],
            private_key,
            algorithm="EdDSA",
            headers={"kid": "manager-v1", "typ": "JWT"},
        )
        if case["accepted"]:
            claims = verifier.verify(token, action=case["requiredAction"])
            assert claims.subject == case["claims"]["sub"], case["name"]
            continue
        with pytest.raises((ExecutionGrantInvalid, ExecutionGrantConflict)):
            verifier.verify(token, action=case["requiredAction"])
