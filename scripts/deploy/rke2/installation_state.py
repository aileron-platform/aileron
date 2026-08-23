"""Canonical HomeLab installation identity and acceptance trust contract."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID


PRIVATE_ROOT = Path("/root/aileron-private")
SECRET_STORE = PRIVATE_ROOT / "install-secrets/rke2"
BUNDLED_ISSUER_URL = "https://keycloak.apps.rke.soez.tw/realms/aileron"
BUNDLED_CLIENT_ID = "aileron-frontend"
ACCEPTANCE_SECRET_NAMESPACE = "aileron-acceptance-system"
BACKEND_ATTESTOR_PROFILE = (
    PRIVATE_ROOT / "backend-attestor/execution-profile.json"
)
ACCEPTANCE_SECRET_NAME = "aileron-acceptance-signing"
ACCEPTANCE_SECRET_DATA_KEY = "hmac-key"
ACCEPTANCE_ANCHOR_FILE = "acceptance-trust-anchor.json"
INSTALLER_OWNER = "aileron-installer"
SECRET_OWNER_LABEL = "platform.aileron.dev/secret-owner"
CLUSTER_UID_LABEL = "platform.aileron.dev/cluster-uid"
IDENTITY_DIGEST_ANNOTATION = "platform.aileron.dev/installation-identity-sha256"


class InstallationStateContractError(ValueError):
    """Raised when installation identity or acceptance trust data is invalid."""


def validate_identity_selection(
    *, identity_mode: str, issuer_url: str, client_id: str
) -> None:
    if not all(
        isinstance(value, str) for value in (identity_mode, issuer_url, client_id)
    ):
        raise InstallationStateContractError(
            "identity mode, issuer URL, and client ID must be strings"
        )
    parsed = urlparse(issuer_url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise InstallationStateContractError("issuer URL port is invalid") from exc
    if (
        issuer_url != issuer_url.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in issuer_url)
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.hostname is None
        or port is not None
        and not 1 <= port <= 65535
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise InstallationStateContractError(
            "issuer URL must be an exact HTTPS URL with an issuer path"
        )
    if not client_id or client_id != client_id.strip():
        raise InstallationStateContractError("client ID must be exact and non-empty")
    if identity_mode == "bundledKeycloak":
        if issuer_url != BUNDLED_ISSUER_URL or client_id != BUNDLED_CLIENT_ID:
            raise InstallationStateContractError(
                "bundled Keycloak identity must match the HomeLab installation contract"
            )
    elif identity_mode != "externalOidc":
        raise InstallationStateContractError("identity mode is unsupported")


def installation_identity_document(
    *,
    installation_id: str,
    identity_mode: str,
    issuer_url: str,
    client_id: str,
    cluster_uid: str,
) -> dict[str, Any]:
    validate_identity_selection(
        identity_mode=identity_mode, issuer_url=issuer_url, client_id=client_id
    )
    try:
        parsed_installation_id = UUID(installation_id)
        parsed_cluster_uid = UUID(cluster_uid)
    except (AttributeError, TypeError, ValueError) as exc:
        raise InstallationStateContractError(
            "installation ID and cluster UID must be canonical UUIDs"
        ) from exc
    if (
        str(parsed_installation_id) != installation_id
    ):
        raise InstallationStateContractError(
            "installation ID must be a canonical UUID"
        )
    if str(parsed_cluster_uid) != cluster_uid:
        raise InstallationStateContractError("cluster UID must be a canonical UUID")
    return {
        "contractVersion": "aileron-installation-identity/v3",
        "installationId": installation_id,
        "clusterUid": cluster_uid,
        "identityMode": identity_mode,
        "issuerUrl": issuer_url,
        "clientId": client_id,
    }


def validate_installation_identity_document(
    document: Any,
    *,
    cluster_uid: str | None = None,
) -> dict[str, Any]:
    """Validate and return the exact clean-cut installation identity v3."""

    if not isinstance(document, dict) or set(document) != {
        "contractVersion",
        "installationId",
        "clusterUid",
        "identityMode",
        "issuerUrl",
        "clientId",
    }:
        raise InstallationStateContractError("installation identity is invalid")
    if document.get("contractVersion") != "aileron-installation-identity/v3":
        raise InstallationStateContractError("installation identity is invalid")
    expected = installation_identity_document(
        installation_id=document.get("installationId"),
        identity_mode=document.get("identityMode"),
        issuer_url=document.get("issuerUrl"),
        client_id=document.get("clientId"),
        cluster_uid=document.get("clusterUid"),
    )
    if document != expected or (
        cluster_uid is not None and document["clusterUid"] != cluster_uid
    ):
        raise InstallationStateContractError(
            "installation identity does not match the cluster"
        )
    return expected


def acceptance_secret_bytes(
    *, key: bytes, identity: bytes, cluster_uid: str
) -> bytes:
    try:
        document = json.loads(identity)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InstallationStateContractError("installation identity is invalid") from exc
    validate_installation_identity_document(document, cluster_uid=cluster_uid)
    secret = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": ACCEPTANCE_SECRET_NAME,
            "namespace": ACCEPTANCE_SECRET_NAMESPACE,
            "labels": {
                SECRET_OWNER_LABEL: INSTALLER_OWNER,
                CLUSTER_UID_LABEL: cluster_uid,
            },
            "annotations": {
                IDENTITY_DIGEST_ANNOTATION: hashlib.sha256(identity).hexdigest(),
            },
        },
        "type": "Opaque",
        "immutable": True,
        "data": {ACCEPTANCE_SECRET_DATA_KEY: base64.b64encode(key).decode("ascii")},
    }
    return json.dumps(secret, separators=(",", ":"), sort_keys=True).encode()


def acceptance_anchor_document(
    *,
    cluster_uid: str,
    identity_digest: str,
    key_digest: str,
    secret_uid: str | None,
) -> dict[str, Any]:
    return {
        "contractVersion": "aileron-acceptance-trust-anchor/v2",
        "clusterUid": cluster_uid,
        "installationIdentitySha256": identity_digest,
        "keySha256": key_digest,
        "secretName": ACCEPTANCE_SECRET_NAME,
        "secretNamespace": ACCEPTANCE_SECRET_NAMESPACE,
        "secretUid": secret_uid,
    }


def acceptance_secret_uid(secret: dict[str, Any], expected: dict[str, Any]) -> str:
    metadata = secret.get("metadata") if isinstance(secret, dict) else None
    actual = {
        "apiVersion": secret.get("apiVersion") if isinstance(secret, dict) else None,
        "kind": secret.get("kind") if isinstance(secret, dict) else None,
        "immutable": secret.get("immutable") if isinstance(secret, dict) else None,
        "metadata": {
            "name": metadata.get("name") if isinstance(metadata, dict) else None,
            "namespace": metadata.get("namespace")
            if isinstance(metadata, dict)
            else None,
            "labels": metadata.get("labels") if isinstance(metadata, dict) else None,
            "annotations": metadata.get("annotations")
            if isinstance(metadata, dict)
            else None,
        },
        "type": secret.get("type") if isinstance(secret, dict) else None,
        "data": secret.get("data") if isinstance(secret, dict) else None,
    }
    if actual != expected:
        raise InstallationStateContractError(
            "acceptance signing Secret does not match installation state"
        )
    uid = metadata.get("uid") if isinstance(metadata, dict) else None
    try:
        parsed_uid = UUID(uid)
    except (TypeError, ValueError) as exc:
        raise InstallationStateContractError(
            "acceptance signing Secret UID is invalid"
        ) from exc
    if str(parsed_uid) != uid:
        raise InstallationStateContractError("acceptance signing Secret UID is invalid")
    return uid
