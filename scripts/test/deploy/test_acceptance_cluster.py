from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy/rke2/acceptance_cluster.py"
SPEC = importlib.util.spec_from_file_location("acceptance_cluster", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
INSTALLATION_ID = "44444444-4444-4444-8444-444444444444"
SECRET_UID = "22222222-2222-4222-8222-222222222222"
ACCEPTANCE_NAMESPACE_UID = "33333333-3333-4333-8333-333333333333"
KEY = bytes(range(32))
IDENTITY = (
    json.dumps(
        MODULE.INSTALLATION_STATE.installation_identity_document(
            installation_id=INSTALLATION_ID,
            identity_mode="bundledKeycloak",
            issuer_url=MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
            client_id=MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            cluster_uid=CLUSTER_UID,
        ),
        indent=2,
        sort_keys=True,
    )
    + "\n"
).encode()
IDENTITY_DIGEST = hashlib.sha256(IDENTITY).hexdigest()


class Runner:
    def __init__(
        self,
        *,
        secret_override: dict | None = None,
        namespace_override: dict | None = None,
        replace_namespace_after_secret: bool = False,
    ) -> None:
        self.calls: list[list[str]] = []
        self.secret_override = secret_override or {}
        self.namespace_override = namespace_override or {}
        self.replace_namespace_after_secret = replace_namespace_after_secret
        self.namespace_reads = 0

    def __call__(self, command: list[str]) -> bytes:
        self.calls.append(command)
        if "namespace" in command and "kube-system" in command:
            return CLUSTER_UID.encode()
        if "namespace" in command and "aileron-acceptance-system" in command:
            self.namespace_reads += 1
            namespace = {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {
                    "name": "aileron-acceptance-system",
                    "uid": ACCEPTANCE_NAMESPACE_UID,
                    "resourceVersion": "17",
                    "labels": {
                        "platform.aileron.dev/namespace-owner": "aileron-installer",
                        "pod-security.kubernetes.io/enforce": "restricted",
                        "pod-security.kubernetes.io/audit": "restricted",
                        "pod-security.kubernetes.io/warn": "restricted",
                    },
                },
                "status": {"phase": "Active"},
            }
            for key, value in self.namespace_override.items():
                if key == "labels":
                    namespace["metadata"]["labels"] = value
                elif key == "status":
                    namespace["status"] = value
                else:
                    namespace["metadata"][key] = value
            if self.replace_namespace_after_secret and self.namespace_reads > 1:
                namespace["metadata"]["uid"] = (
                    "44444444-4444-4444-8444-444444444444"
                )
                namespace["metadata"]["resourceVersion"] = "18"
            return json.dumps(namespace).encode()
        secret = {
            "apiVersion": "v1",
            "kind": "Secret",
            "immutable": True,
            "metadata": {
                "name": "aileron-acceptance-signing",
                "namespace": "aileron-acceptance-system",
                "uid": SECRET_UID,
                "resourceVersion": "19",
                "labels": {
                    "platform.aileron.dev/secret-owner": "aileron-installer",
                    "platform.aileron.dev/cluster-uid": CLUSTER_UID,
                },
                "annotations": {
                    "platform.aileron.dev/installation-identity-sha256": IDENTITY_DIGEST,
                },
            },
            "data": {"hmac-key": base64.b64encode(KEY).decode()},
            "type": "Opaque",
        }
        for key, value in self.secret_override.items():
            if key == "data":
                secret["data"] = value
            elif key == "immutable":
                secret["immutable"] = value
            else:
                secret["metadata"][key] = value
        return json.dumps(secret).encode()


def _kubeconfig(tmp_path: Path) -> Path:
    path = tmp_path / "kubeconfig"
    path.write_text(
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": "rke2-homelab",
                "clusters": [
                    {
                        "name": "rke2-homelab",
                        "cluster": {
                            "server": "https://192.0.2.10:6443",
                            "certificate-authority-data": "Y2E=",
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": "rke2-homelab",
                        "context": {
                            "cluster": "rke2-homelab",
                            "user": "rke2-homelab",
                        },
                    }
                ],
                "users": [
                    {
                        "name": "rke2-homelab",
                        "user": {
                            "client-certificate-data": "Y2VydA==",
                            "client-key-data": "a2V5",
                        },
                    }
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def _secret_store(tmp_path: Path, **overrides: str) -> Path:
    install_secrets = tmp_path / "install-secrets"
    install_secrets.mkdir(mode=0o700, exist_ok=True)
    install_secrets.chmod(0o700)
    store = install_secrets / "homelab"
    store.mkdir(mode=0o700, exist_ok=True)
    store.chmod(0o700)
    anchor = {
        "contractVersion": "aileron-acceptance-trust-anchor/v2",
        "clusterUid": CLUSTER_UID,
        "installationIdentitySha256": IDENTITY_DIGEST,
        "keySha256": hashlib.sha256(KEY).hexdigest(),
        "secretName": "aileron-acceptance-signing",
        "secretNamespace": "aileron-acceptance-system",
        "secretUid": SECRET_UID,
        **overrides,
    }
    path = store / "acceptance-trust-anchor.json"
    path.write_text(
        json.dumps(anchor, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    identity_path = store / "installation-identity.json"
    identity_path.write_bytes(IDENTITY)
    identity_path.chmod(0o600)
    return store


@pytest.fixture(autouse=True)
def _fixed_installation_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(MODULE.INSTALLATION_STATE, "PRIVATE_ROOT", tmp_path)
    monkeypatch.setattr(
        MODULE.INSTALLATION_STATE, "SECRET_STORE", _secret_store(tmp_path)
    )


def test_loads_key_only_from_fixed_homelab_private_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = Runner()
    monkeypatch.setenv(
        "AILERON_INSTALLATION_SECRET_STORE", str(tmp_path / "attacker-store")
    )
    trust = MODULE.load_cluster_acceptance_key(
        context="rke2-homelab",
        kubeconfig=_kubeconfig(tmp_path),
        runner=runner,
    )

    assert trust.key == KEY
    assert trust.cluster_uid == CLUSTER_UID
    assert trust.installation_identity_sha256 == IDENTITY_DIGEST
    assert trust.secret_uid == SECRET_UID
    assert trust.secret_resource_version == "19"
    assert trust.acceptance_namespace_uid == ACCEPTANCE_NAMESPACE_UID
    assert trust.acceptance_namespace_resource_version == "17"
    assert any("aileron-acceptance-system" in command for command in runner.calls)
    assert all(
        command[1:3] == ["--kubeconfig", str(tmp_path / "kubeconfig")]
        for command in runner.calls
    )


def test_release_trust_requires_matching_local_installation_identity(
    tmp_path: Path,
) -> None:
    trust = MODULE.load_cluster_release_trust(
        context="rke2-homelab",
        kubeconfig=_kubeconfig(tmp_path),
        runner=Runner(),
    )

    assert trust.installation_identity_sha256 == IDENTITY_DIGEST
    assert trust.secret_uid == SECRET_UID

    identity_path = MODULE.INSTALLATION_STATE.SECRET_STORE / (
        "installation-identity.json"
    )
    identity_path.write_text("{}\n", encoding="utf-8")
    identity_path.chmod(0o600)
    with pytest.raises(MODULE.AcceptanceClusterError, match="identity"):
        MODULE.load_cluster_release_trust(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(),
        )


def test_release_loader_rejects_retired_v2_identity_even_with_matching_digest(
    tmp_path: Path,
) -> None:
    retired_identity = (
        json.dumps(
            {
                "contractVersion": "aileron-installation-identity/v2",
                "clusterUid": CLUSTER_UID,
                "context": "rke2-homelab",
                "namespaces": [
                    "aileron-acceptance-system",
                    "aileron-backend-attestor-system",
                    "aileron-identity-system",
                    "aileron-turn-system",
                    "workspace-system",
                ],
                "realm": "aileron",
                "issuerUrl": MODULE.INSTALLATION_STATE.BUNDLED_ISSUER_URL,
                "clientId": MODULE.INSTALLATION_STATE.BUNDLED_CLIENT_ID,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode()
    retired_digest = hashlib.sha256(retired_identity).hexdigest()
    identity_path = MODULE.INSTALLATION_STATE.SECRET_STORE / "installation-identity.json"
    identity_path.write_bytes(retired_identity)
    identity_path.chmod(0o600)
    anchor_path = MODULE.INSTALLATION_STATE.SECRET_STORE / (
        "acceptance-trust-anchor.json"
    )
    anchor = json.loads(anchor_path.read_bytes())
    anchor["installationIdentitySha256"] = retired_digest
    anchor_path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n")
    anchor_path.chmod(0o600)
    runner = Runner(
        secret_override={
            "annotations": {
                "platform.aileron.dev/installation-identity-sha256": retired_digest
            }
        }
    )

    with pytest.raises(MODULE.AcceptanceClusterError, match="identity"):
        MODULE.load_cluster_release_trust(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=runner,
        )


@pytest.mark.parametrize(
    "namespace_override",
    [
        {"status": {"phase": "Terminating"}},
        {"deletionTimestamp": "2026-08-10T00:00:00Z"},
        {
            "labels": {
                "platform.aileron.dev/namespace-owner": "aileron-installer",
                "pod-security.kubernetes.io/enforce": "restricted",
                "pod-security.kubernetes.io/audit": "restricted",
                "pod-security.kubernetes.io/warn": "restricted",
                "pod-security.kubernetes.io/enforce-version": "latest",
            }
        },
    ],
)
def test_rejects_invalid_acceptance_namespace_before_secret_query(
    tmp_path: Path,
    namespace_override: dict,
) -> None:
    runner = Runner(namespace_override=namespace_override)

    with pytest.raises(MODULE.AcceptanceClusterError, match="Namespace record"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=runner,
        )

    assert not any("secret" in command for command in runner.calls)


def test_rejects_acceptance_namespace_replacement_after_secret_query(
    tmp_path: Path,
) -> None:
    runner = Runner(replace_namespace_after_secret=True)

    with pytest.raises(MODULE.AcceptanceClusterError, match="changed"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=runner,
        )

    assert runner.namespace_reads == 2
    assert sum("secret" in command for command in runner.calls) == 1


@pytest.mark.parametrize(
    "secret_override,anchor_override,error",
    [
        ({"labels": {"platform.aileron.dev/secret-owner": "other"}}, {}, "metadata"),
        (
            {
                "labels": {
                    "platform.aileron.dev/secret-owner": "aileron-installer",
                    "platform.aileron.dev/cluster-uid": CLUSTER_UID,
                    "unexpected": "label",
                }
            },
            {},
            "metadata",
        ),
        (
            {
                "annotations": {
                    "platform.aileron.dev/context": "other",
                    "platform.aileron.dev/installation-identity-sha256": IDENTITY_DIGEST,
                }
            },
            {},
            "metadata",
        ),
        ({"immutable": False}, {}, "immutable"),
        ({"uid": "33333333-3333-4333-8333-333333333333"}, {}, "anchor"),
        (
            {"data": {"hmac-key": base64.b64encode(b"z" * 32).decode()}},
            {},
            "anchor",
        ),
        ({}, {"installationIdentitySha256": "b" * 64}, "anchor"),
    ],
)
def test_rejects_cluster_secret_or_external_anchor_drift(
    tmp_path: Path,
    secret_override: dict,
    anchor_override: dict,
    error: str,
) -> None:
    _secret_store(tmp_path, **anchor_override)
    with pytest.raises(MODULE.AcceptanceClusterError, match=error):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(secret_override=secret_override),
        )


def test_rejects_missing_or_insecure_stable_store_anchor(tmp_path: Path) -> None:
    store = _secret_store(tmp_path)
    (store / "acceptance-trust-anchor.json").chmod(0o644)
    with pytest.raises(MODULE.AcceptanceClusterError, match="anchor is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(),
        )


def test_rejects_hardlinked_anchor_and_insecure_secret_store_parent(
    tmp_path: Path,
) -> None:
    store = _secret_store(tmp_path)
    anchor = store / "acceptance-trust-anchor.json"
    (store / "anchor-hardlink.json").hardlink_to(anchor)
    with pytest.raises(MODULE.AcceptanceClusterError, match="anchor is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(),
        )

    anchor.unlink()
    _secret_store(tmp_path)
    (tmp_path / "install-secrets").chmod(0o755)
    with pytest.raises(MODULE.AcceptanceClusterError, match="secret store is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(),
        )


def test_rejects_kubeconfig_outside_private_root_or_with_multiple_links(
    tmp_path: Path,
) -> None:
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_root.mkdir(mode=0o700)
    external = _kubeconfig(external_root)
    with pytest.raises(MODULE.AcceptanceClusterError, match="snapshot is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=external,
            runner=Runner(),
        )

    kubeconfig = _kubeconfig(tmp_path)
    (tmp_path / "kubeconfig-hardlink").hardlink_to(kubeconfig)
    with pytest.raises(MODULE.AcceptanceClusterError, match="snapshot is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=kubeconfig,
            runner=Runner(),
        )


def test_rejects_non_minified_or_context_drifted_kubeconfig(tmp_path: Path) -> None:
    kubeconfig = _kubeconfig(tmp_path)
    document = json.loads(kubeconfig.read_bytes())
    document["contexts"].append(
        {
            "name": "other",
            "context": {"cluster": "rke2-homelab", "user": "rke2-homelab"},
        }
    )
    kubeconfig.write_text(json.dumps(document), encoding="utf-8")
    kubeconfig.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceClusterError, match="snapshot is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=kubeconfig,
            runner=Runner(),
        )


@pytest.mark.parametrize("tamper", ["duplicate", "reordered", "invalid-utf8"])
def test_rejects_ambiguous_or_noncanonical_trust_anchor(
    tmp_path: Path,
    tamper: str,
) -> None:
    store = _secret_store(tmp_path)
    anchor = store / "acceptance-trust-anchor.json"
    document = json.loads(anchor.read_bytes())
    if tamper == "duplicate":
        raw = anchor.read_bytes().replace(
            f'  "clusterUid": "{CLUSTER_UID}",'.encode(),
            (
                f'  "clusterUid": "{CLUSTER_UID}",\n'
                f'  "clusterUid": "{CLUSTER_UID}",'
            ).encode(),
            1,
        )
    elif tamper == "reordered":
        raw = (
            json.dumps(dict(reversed(list(document.items()))), indent=2) + "\n"
        ).encode()
    else:
        raw = b'{"context":\xff}\n'
    anchor.write_bytes(raw)
    anchor.chmod(0o600)

    with pytest.raises(MODULE.AcceptanceClusterError, match="anchor is invalid"):
        MODULE.load_cluster_acceptance_key(
            context="rke2-homelab",
            kubeconfig=_kubeconfig(tmp_path),
            runner=Runner(),
        )


def test_loader_has_no_key_or_store_path_parameter() -> None:
    assert "signing_key" not in MODULE.load_cluster_acceptance_key.__annotations__
    assert "secret_store" not in MODULE.load_cluster_acceptance_key.__annotations__
    assert not hasattr(MODULE, "TRUST_ANCHOR_ENV")
