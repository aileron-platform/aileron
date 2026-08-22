from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "deploy/rke2/kubernetes_rest.py"
SPEC = importlib.util.spec_from_file_location("kubernetes_rest", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _kubeconfig(tmp_path: Path) -> Path:
    document = {
        "apiVersion": "v1",
        "kind": "Config",
        "current-context": "rke2-homelab",
        "clusters": [
            {
                "name": "cluster",
                "cluster": {
                    "server": "https://192.0.2.10:6443",
                    "certificate-authority-data": base64.b64encode(b"test-ca").decode(),
                },
            }
        ],
        "contexts": [
            {
                "name": "rke2-homelab",
                "context": {"cluster": "cluster", "user": "operator"},
            }
        ],
        "users": [{"name": "operator", "user": {"token": "secret-token"}}],
    }
    path = tmp_path / "flattened-kubeconfig.json"
    path.write_text(json.dumps(document, separators=(",", ":"), sort_keys=True))
    path.chmod(0o600)
    return path


class _TLSContext:
    def __init__(self) -> None:
        self.loaded_paths: tuple[Path, Path] | None = None

    def load_cert_chain(self, certificate: Path, private_key: Path) -> None:
        assert certificate.read_bytes() == b"client-certificate"
        assert private_key.read_bytes() == b"client-private-key"
        self.loaded_paths = (certificate, private_key)


def test_delete_uses_exact_core_and_group_paths_with_uid_and_resource_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        MODULE.ssl,
        "create_default_context",
        lambda *, cadata: _TLSContext(),
    )
    client = MODULE.load_kubernetes_delete_client(
        kubeconfig=_kubeconfig(tmp_path),
        context="rke2-homelab",
        private_root=tmp_path,
        credential_directory=tmp_path,
    )
    requests: list[tuple[str, dict[str, str], dict]] = []

    def transport(*, url, headers, body, tls_context, timeout):
        assert isinstance(tls_context, _TLSContext)
        assert timeout == 30
        requests.append((url, headers, json.loads(body)))
        return 200, b'{"apiVersion":"v1","kind":"Status","status":"Success"}'

    client.delete(
        api_version="v1",
        resource="persistentvolumes",
        namespace=None,
        name="pv-one",
        uid="pv-uid",
        resource_version="101",
        transport=transport,
    )
    client.delete(
        api_version="platform.aileron.io/v1alpha1",
        resource="workspaces",
        namespace="workspace-system",
        name="workspace-one",
        uid="workspace-uid",
        resource_version="202",
        transport=transport,
    )
    client.delete(
        api_version="v1",
        resource="namespaces",
        namespace=None,
        name="workspace-system",
        uid="namespace-uid",
        resource_version="303",
        transport=transport,
    )

    assert [item[0] for item in requests] == [
        "https://192.0.2.10:6443/api/v1/persistentvolumes/pv-one",
        (
            "https://192.0.2.10:6443/apis/platform.aileron.io/v1alpha1/"
            "namespaces/workspace-system/workspaces/workspace-one"
        ),
        "https://192.0.2.10:6443/api/v1/namespaces/workspace-system",
    ]
    assert all(item[1]["Authorization"] == "Bearer secret-token" for item in requests)
    assert [item[2] for item in requests] == [
        {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"resourceVersion": "101", "uid": "pv-uid"},
            "propagationPolicy": "Foreground",
        },
        {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"resourceVersion": "202", "uid": "workspace-uid"},
            "propagationPolicy": "Foreground",
        },
        {
            "apiVersion": "v1",
            "kind": "DeleteOptions",
            "preconditions": {"resourceVersion": "303", "uid": "namespace-uid"},
            "propagationPolicy": "Foreground",
        },
    ]


def test_get_returns_one_resource_and_maps_not_found_to_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        MODULE.ssl,
        "create_default_context",
        lambda *, cadata: _TLSContext(),
    )
    client = MODULE.load_kubernetes_delete_client(
        kubeconfig=_kubeconfig(tmp_path),
        context="rke2-homelab",
        private_root=tmp_path,
        credential_directory=tmp_path,
    )
    requests: list[str] = []
    responses = iter(
        [
            (
                200,
                b'{"apiVersion":"v1","kind":"Secret","metadata":'
                b'{"name":"aileron-acceptance-signing"}}',
            ),
            (404, b'{"apiVersion":"v1","kind":"Status","reason":"NotFound"}'),
        ]
    )

    def transport(*, url, headers, tls_context, timeout):
        assert headers["Authorization"] == "Bearer secret-token"
        assert isinstance(tls_context, _TLSContext)
        assert timeout == 30
        requests.append(url)
        return next(responses)

    query = {
        "api_version": "v1",
        "resource": "secrets",
        "namespace": "aileron-acceptance-system",
        "name": "aileron-acceptance-signing",
        "transport": transport,
    }
    assert client.get(**query)["metadata"]["name"] == "aileron-acceptance-signing"
    assert client.get(**query) is None
    assert requests == [
        (
            "https://192.0.2.10:6443/api/v1/namespaces/"
            "aileron-acceptance-system/secrets/aileron-acceptance-signing"
        )
    ] * 2


@pytest.mark.parametrize("failure", ("conflict", "transport"))
def test_delete_fails_closed_without_disclosing_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    tmp_path.chmod(0o700)
    monkeypatch.setattr(
        MODULE.ssl,
        "create_default_context",
        lambda *, cadata: _TLSContext(),
    )
    client = MODULE.load_kubernetes_delete_client(
        kubeconfig=_kubeconfig(tmp_path),
        context="rke2-homelab",
        private_root=tmp_path,
        credential_directory=tmp_path,
    )

    def transport(**_kwargs):
        if failure == "transport":
            raise OSError("secret-token must not escape")
        return 409, b'{"kind":"Status","reason":"Conflict"}'

    with pytest.raises(MODULE.KubernetesRestError) as raised:
        client.delete(
            api_version="v1",
            resource="namespaces",
            namespace=None,
            name="workspace-system",
            uid="namespace-uid",
            resource_version="303",
            transport=transport,
        )

    assert "secret-token" not in str(raised.value)


def test_client_certificate_material_is_removed_after_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path.chmod(0o700)
    document = json.loads(_kubeconfig(tmp_path).read_text())
    document["users"][0]["user"] = {
        "client-certificate-data": base64.b64encode(b"client-certificate").decode(),
        "client-key-data": base64.b64encode(b"client-private-key").decode(),
    }
    kubeconfig = tmp_path / "flattened-client-certificate-kubeconfig.json"
    kubeconfig.write_text(json.dumps(document, separators=(",", ":"), sort_keys=True))
    kubeconfig.chmod(0o600)
    credential_directory = tmp_path / "credentials"
    credential_directory.mkdir(mode=0o700)
    tls_context = _TLSContext()
    monkeypatch.setattr(
        MODULE.ssl,
        "create_default_context",
        lambda *, cadata: tls_context,
    )

    MODULE.load_kubernetes_delete_client(
        kubeconfig=kubeconfig,
        context="rke2-homelab",
        private_root=tmp_path,
        credential_directory=credential_directory,
    )

    assert tls_context.loaded_paths is not None
    assert all(not path.exists() for path in tls_context.loaded_paths)
