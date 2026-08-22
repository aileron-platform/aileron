"""Installation identity v3 public contract tests."""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy/rke2/installation_state.py"
SPEC = importlib.util.spec_from_file_location("installation_state", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
INSTALLATION_ID = "22222222-2222-4222-8222-222222222222"
KEY = bytes(range(32))


def _identity() -> dict:
    return MODULE.installation_identity_document(
        installation_id=INSTALLATION_ID,
        identity_mode="bundledKeycloak",
        issuer_url=MODULE.BUNDLED_ISSUER_URL,
        client_id=MODULE.BUNDLED_CLIENT_ID,
        cluster_uid=CLUSTER_UID,
    )


def test_installation_identity_v3_contains_only_stable_identity_fields() -> None:
    assert _identity() == {
        "contractVersion": "aileron-installation-identity/v3",
        "installationId": INSTALLATION_ID,
        "clusterUid": CLUSTER_UID,
        "identityMode": "bundledKeycloak",
        "issuerUrl": MODULE.BUNDLED_ISSUER_URL,
        "clientId": MODULE.BUNDLED_CLIENT_ID,
    }


def test_installation_identity_requires_a_canonical_uuid_installation_id() -> None:
    with pytest.raises(
        MODULE.InstallationStateContractError,
        match="installation ID",
    ):
        MODULE.installation_identity_document(
            installation_id="AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.BUNDLED_ISSUER_URL,
            client_id=MODULE.BUNDLED_CLIENT_ID,
            cluster_uid=CLUSTER_UID,
        )


def test_acceptance_secret_and_anchor_do_not_bind_run_context() -> None:
    identity = (json.dumps(_identity(), indent=2, sort_keys=True) + "\n").encode()

    secret = json.loads(
        MODULE.acceptance_secret_bytes(
            key=KEY,
            identity=identity,
            cluster_uid=CLUSTER_UID,
        )
    )

    assert secret["metadata"]["annotations"] == {
        MODULE.IDENTITY_DIGEST_ANNOTATION: MODULE.hashlib.sha256(identity).hexdigest()
    }
    assert secret["data"] == {
        MODULE.ACCEPTANCE_SECRET_DATA_KEY: base64.b64encode(KEY).decode("ascii")
    }
    assert MODULE.acceptance_anchor_document(
        cluster_uid=CLUSTER_UID,
        identity_digest=MODULE.hashlib.sha256(identity).hexdigest(),
        key_digest=MODULE.hashlib.sha256(KEY).hexdigest(),
        secret_uid="33333333-3333-4333-8333-333333333333",
    ) == {
        "contractVersion": "aileron-acceptance-trust-anchor/v2",
        "clusterUid": CLUSTER_UID,
        "installationIdentitySha256": MODULE.hashlib.sha256(identity).hexdigest(),
        "keySha256": MODULE.hashlib.sha256(KEY).hexdigest(),
        "secretName": MODULE.ACCEPTANCE_SECRET_NAME,
        "secretNamespace": MODULE.ACCEPTANCE_SECRET_NAMESPACE,
        "secretUid": "33333333-3333-4333-8333-333333333333",
    }

    v2_identity = dict(_identity())
    v2_identity["contractVersion"] = "aileron-installation-identity/v2"
    with pytest.raises(
        MODULE.InstallationStateContractError,
        match="installation identity",
    ):
        MODULE.acceptance_secret_bytes(
            key=KEY,
            identity=json.dumps(v2_identity).encode(),
            cluster_uid=CLUSTER_UID,
        )
