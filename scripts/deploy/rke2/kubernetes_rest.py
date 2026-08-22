#!/usr/bin/env python3
"""Issue exact Kubernetes REST deletes with server-side identity preconditions."""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.util
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple, Union


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9](?:[-_.A-Za-z0-9]{0,251}[A-Za-z0-9])?$")
RESOURCE_PATTERN = re.compile(r"^[a-z0-9](?:[-a-z0-9.]{0,251}[a-z0-9])?$")
API_VERSION_PATTERN = re.compile(
    r"^(?:v[0-9]+|[a-z0-9](?:[-a-z0-9.]*[a-z0-9])?/v[0-9]+(?:alpha|beta)?[0-9]*)$"
)
MAX_RESPONSE_BYTES = 1024 * 1024
_CLIENT_TOKEN = object()


def _load_private_input() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_kubernetes_rest_private_input",
        SCRIPT_DIRECTORY / "private_input.py",
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("private input contract is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


PRIVATE_INPUT = _load_private_input()


class KubernetesRestError(RuntimeError):
    """Raised when a Kubernetes preconditioned delete cannot be proven."""


class TransportResult(NamedTuple):
    status: int
    body: bytes


Transport = Callable[..., Union[tuple[int, bytes], TransportResult]]


def _decode_inline(value: Any, description: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise KubernetesRestError(f"{description} is missing")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise KubernetesRestError(f"{description} is invalid") from exc
    if not decoded:
        raise KubernetesRestError(f"{description} is empty")
    return decoded


def _one_named(document: dict[str, Any], key: str, nested_key: str) -> dict[str, Any]:
    values = document.get(key)
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], dict)
        or not isinstance(values[0].get(nested_key), dict)
    ):
        raise KubernetesRestError("flattened kubeconfig identity is invalid")
    return values[0]


def _https_transport(
    *,
    url: str,
    headers: dict[str, str],
    body: bytes,
    tls_context: ssl.SSLContext,
    timeout: int,
) -> TransportResult:
    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(
            request,
            context=tls_context,
            timeout=timeout,
        ) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise KubernetesRestError("Kubernetes REST response is too large")
            return TransportResult(response.status, content)
    except urllib.error.HTTPError as exc:
        content = exc.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            content = b""
        return TransportResult(exc.code, content)
    except KubernetesRestError:
        raise
    except Exception as exc:
        raise KubernetesRestError("Kubernetes REST transport or TLS failed") from exc


def _https_get_transport(
    *,
    url: str,
    headers: dict[str, str],
    tls_context: ssl.SSLContext,
    timeout: int,
) -> TransportResult:
    request = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(
            request,
            context=tls_context,
            timeout=timeout,
        ) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
            if len(content) > MAX_RESPONSE_BYTES:
                raise KubernetesRestError("Kubernetes REST response is too large")
            return TransportResult(response.status, content)
    except urllib.error.HTTPError as exc:
        content = exc.read(MAX_RESPONSE_BYTES + 1)
        if len(content) > MAX_RESPONSE_BYTES:
            content = b""
        return TransportResult(exc.code, content)
    except KubernetesRestError:
        raise
    except Exception as exc:
        raise KubernetesRestError("Kubernetes REST transport or TLS failed") from exc


def _resource_path(
    *,
    api_version: str,
    resource: str,
    namespace: str | None,
    name: str,
) -> str:
    if API_VERSION_PATTERN.fullmatch(api_version) is None:
        raise ValueError("Kubernetes API version is invalid")
    if RESOURCE_PATTERN.fullmatch(resource) is None:
        raise ValueError("Kubernetes REST resource is invalid")
    if not isinstance(name, str) or IDENTITY_PATTERN.fullmatch(name) is None:
        raise ValueError("Kubernetes resource name is invalid")
    if namespace is not None and (
        not isinstance(namespace, str)
        or IDENTITY_PATTERN.fullmatch(namespace) is None
    ):
        raise ValueError("Kubernetes resource namespace is invalid")
    if "/" in api_version:
        group, version = api_version.split("/", 1)
        path = f"/apis/{group}/{version}"
    else:
        path = f"/api/{api_version}"
    if namespace is not None:
        path += "/namespaces/" + urllib.parse.quote(namespace, safe="")
    return path + "/" + resource + "/" + urllib.parse.quote(name, safe="")


class KubernetesDeleteClient:
    """A client derived only from one validated flattened kubeconfig snapshot."""

    __slots__ = ("_server", "_headers", "_tls_context")

    def __init__(
        self,
        *,
        server: str,
        headers: dict[str, str],
        tls_context: ssl.SSLContext,
        _token: object,
    ) -> None:
        if _token is not _CLIENT_TOKEN:
            raise TypeError("KubernetesDeleteClient must be loaded from a snapshot")
        self._server = server.rstrip("/")
        self._headers = dict(headers)
        self._tls_context = tls_context

    def delete(
        self,
        *,
        api_version: str,
        resource: str,
        namespace: str | None,
        name: str,
        uid: str,
        resource_version: str,
        transport: Transport = _https_transport,
    ) -> None:
        path = _resource_path(
            api_version=api_version,
            resource=resource,
            namespace=namespace,
            name=name,
        )
        for value, description in (
            (uid, "resource UID"),
            (resource_version, "resourceVersion"),
        ):
            if not isinstance(value, str) or IDENTITY_PATTERN.fullmatch(value) is None:
                raise ValueError(f"Kubernetes {description} is invalid")
        body = json.dumps(
            {
                "apiVersion": "v1",
                "kind": "DeleteOptions",
                "preconditions": {
                    "resourceVersion": resource_version,
                    "uid": uid,
                },
                "propagationPolicy": "Foreground",
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        try:
            result = transport(
                url=self._server + path,
                headers=self._headers,
                body=body,
                tls_context=self._tls_context,
                timeout=30,
            )
        except KubernetesRestError:
            raise
        except Exception as exc:
            raise KubernetesRestError("Kubernetes REST transport or TLS failed") from exc
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], int)
            or not isinstance(result[1], bytes)
        ):
            raise KubernetesRestError("Kubernetes REST transport result is invalid")
        status, response_body = result
        if status not in {200, 202}:
            raise KubernetesRestError(
                f"Kubernetes REST preconditioned delete failed with status {status}"
            )
        try:
            response = json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KubernetesRestError("Kubernetes REST response is invalid") from exc
        if not isinstance(response, dict):
            raise KubernetesRestError("Kubernetes REST response is invalid")

    def get(
        self,
        *,
        api_version: str,
        resource: str,
        namespace: str | None,
        name: str,
        transport: Transport = _https_get_transport,
    ) -> dict[str, Any] | None:
        """Read one exact resource, mapping a validated NotFound to ``None``."""

        path = _resource_path(
            api_version=api_version,
            resource=resource,
            namespace=namespace,
            name=name,
        )
        try:
            result = transport(
                url=self._server + path,
                headers=self._headers,
                tls_context=self._tls_context,
                timeout=30,
            )
        except KubernetesRestError:
            raise
        except Exception as exc:
            raise KubernetesRestError("Kubernetes REST transport or TLS failed") from exc
        if (
            not isinstance(result, tuple)
            or len(result) != 2
            or not isinstance(result[0], int)
            or not isinstance(result[1], bytes)
        ):
            raise KubernetesRestError("Kubernetes REST transport result is invalid")
        status, response_body = result
        try:
            response = json.loads(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KubernetesRestError("Kubernetes REST response is invalid") from exc
        if not isinstance(response, dict):
            raise KubernetesRestError("Kubernetes REST response is invalid")
        if status == 404:
            if response.get("kind") != "Status" or response.get("reason") != "NotFound":
                raise KubernetesRestError("Kubernetes REST NotFound response is invalid")
            return None
        if status != 200:
            raise KubernetesRestError(
                f"Kubernetes REST read failed with status {status}"
            )
        return response


def load_kubernetes_delete_client(
    *,
    kubeconfig: Path,
    context: str,
    credential_directory: Path,
    private_root: Path | None = None,
) -> KubernetesDeleteClient:
    content = PRIVATE_INPUT.read_private_bytes(
        kubeconfig,
        "flattened kubeconfig",
        private_root=private_root,
    )
    PRIVATE_INPUT.validate_self_contained_kubeconfig(
        content,
        expected_context=context,
        description="flattened kubeconfig",
        require_minified=True,
    )
    try:
        document = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise KubernetesRestError("flattened kubeconfig is not canonical JSON") from exc
    if not isinstance(document, dict):
        raise KubernetesRestError("flattened kubeconfig is invalid")
    cluster_entry = _one_named(document, "clusters", "cluster")
    context_entry = _one_named(document, "contexts", "context")
    user_entry = _one_named(document, "users", "user")
    cluster = cluster_entry["cluster"]
    selected_context = context_entry["context"]
    user = user_entry["user"]
    if (
        cluster_entry.get("name") != selected_context.get("cluster")
        or user_entry.get("name") != selected_context.get("user")
        or set(cluster) != {"server", "certificate-authority-data"}
        or set(selected_context) - {"cluster", "user", "namespace"}
    ):
        raise KubernetesRestError("flattened kubeconfig identity is invalid")
    server = cluster["server"]
    ca_data = _decode_inline(
        cluster["certificate-authority-data"], "certificate authority data"
    )
    try:
        tls_context = ssl.create_default_context(cadata=ca_data.decode("utf-8"))
    except (UnicodeDecodeError, ssl.SSLError, OSError) as exc:
        raise KubernetesRestError("flattened kubeconfig TLS identity is invalid") from exc
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if set(user) == {"token"} and isinstance(user.get("token"), str):
        headers["Authorization"] = "Bearer " + user["token"]
    elif set(user) == {"client-certificate-data", "client-key-data"}:
        certificate = _decode_inline(
            user["client-certificate-data"], "client certificate data"
        )
        private_key = _decode_inline(user["client-key-data"], "client key data")
        digest = hashlib.sha256(certificate + b"\0" + private_key).hexdigest()
        certificate_path = PRIVATE_INPUT.write_private_snapshot(
            destination=credential_directory / f"kubernetes-rest-{digest}.crt",
            content=certificate,
            description="Kubernetes REST client certificate",
            private_root=private_root,
            allow_existing_exact=True,
        )
        private_key_path = PRIVATE_INPUT.write_private_snapshot(
            destination=credential_directory / f"kubernetes-rest-{digest}.key",
            content=private_key,
            description="Kubernetes REST client key",
            private_root=private_root,
            allow_existing_exact=True,
        )
        load_error: Exception | None = None
        try:
            tls_context.load_cert_chain(certificate_path, private_key_path)
        except (ssl.SSLError, OSError) as exc:
            load_error = exc
        cleanup_error: OSError | None = None
        for credential_path in (certificate_path, private_key_path):
            try:
                credential_path.unlink()
            except OSError as exc:
                cleanup_error = cleanup_error or exc
        if cleanup_error is not None:
            raise KubernetesRestError(
                "temporary Kubernetes REST credential cleanup failed"
            ) from cleanup_error
        if load_error is not None:
            raise KubernetesRestError(
                "flattened kubeconfig client certificate is invalid"
            ) from load_error
    else:
        raise KubernetesRestError("flattened kubeconfig authentication is invalid")
    return KubernetesDeleteClient(
        server=server,
        headers=headers,
        tls_context=tls_context,
        _token=_CLIENT_TOKEN,
    )
