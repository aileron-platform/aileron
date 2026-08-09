"""Canonical Workspace Execution Access Grant contract conformance."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.modules.workspace.runtime.assertions import (
    ExecutionGrantContext,
    RuntimeAssertionContextError,
    RuntimeAssertionService,
)


CONTRACT_ROOT = Path("/repo-root/contracts/workspace-execution-access")


def _vectors() -> dict[str, object]:
    return json.loads((CONTRACT_ROOT / "conformance-vectors.json").read_text())


def test_generated_execution_grant_contract_has_no_drift() -> None:
    subprocess.run(
        [
            sys.executable,
            str(CONTRACT_ROOT / "generate_contract_bundle.py"),
            "--check",
        ],
        check=True,
    )


def _signer(tmp_path: Path, now: int) -> tuple[RuntimeAssertionService, Ed25519PrivateKey]:
    private_key = Ed25519PrivateKey.generate()
    private_key_file = tmp_path / "manager-key.pem"
    private_key_file.write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return (
        RuntimeAssertionService(
            private_key_file=private_key_file,
            key_id="manager-v1",
            issuer="workspace-manager",
            ttl_seconds=60,
            clock=lambda: datetime.fromtimestamp(now, tz=timezone.utc),
            jti_factory=lambda: "canonical-grant-jti",
        ),
        private_key,
    )


def test_manager_issuance_conforms_to_canonical_vectors(tmp_path: Path) -> None:
    vectors = _vectors()
    signer, private_key = _signer(tmp_path, vectors["validationEpoch"])

    for case in vectors["issuanceCases"]:
        context = ExecutionGrantContext(
            actor_user_id=case["request"]["userId"],
            workspace_id=case["request"]["workspaceId"],
            runtime_instance_id=case["request"]["runtimeInstanceId"],
            runtime_access_revision=case["request"]["runtimeAccessRevision"],
            audience=case["request"]["audience"],
            actions=tuple(case["request"]["actions"]),
        )
        if not case["accepted"]:
            with pytest.raises(RuntimeAssertionContextError):
                signer.sign_execution_grant(context)
            continue

        token = signer.sign_execution_grant(context)
        claims = jwt.decode(
            token,
            private_key.public_key(),
            algorithms=["EdDSA"],
            audience=case["request"]["audience"],
            issuer="workspace-manager",
            options={"verify_exp": False, "verify_iat": False},
        )
        assert claims == case["expectedClaims"], case["name"]
