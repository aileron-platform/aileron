#!/usr/bin/env python3
"""Derive one acceptance observation from fixed live-system raw probes."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

SECTIONS = (
    "identity",
    "imageRelease",
    "restart",
    "turn",
)
SHA = re.compile(r"[0-9a-f]{40}")
IMMUTABLE_IMAGE = re.compile(r"[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}")
IMAGE_COMPONENTS = {
    "platform-coturn",
    "platform-keycloak",
    "platform-postgres",
    "platform-redis",
    "workspace-canvas",
    "workspace-chrome",
    "workspace-manager",
    "workspace-operator",
    "workspace-runtime",
    "workspace-runtime-base-lite",
    "workspace-ui",
}
OPTIONAL_IMAGE_COMPONENTS = {"platform-redis"}
RESTART_COMPONENTS = {
    "frontend": "frontend",
    "workspace-operator": "operator",
}
WORKSPACE_BROWSER_COMPONENT = "workspace-browser"
RESTART_REQUIRED_COMPONENTS = frozenset((*RESTART_COMPONENTS.values(), "browser"))
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
TRANSPORT_PROBE = SCRIPT_DIRECTORY / "acceptance_transport_probe.py"
SOURCE_COMMIT_FILE = Path("/workspace-manager/acceptance/source-commit")
SERVICE_ACCOUNT_DIRECTORY = Path("/var/run/secrets/kubernetes.io/serviceaccount")
KUBERNETES_API = "https://kubernetes.default.svc"
TURN_PROBE_USERNAME_FILE = Path("/run/secrets/turn-probe/probe-username")
TURN_REST_SHARED_SECRET_FILE = Path("/run/secrets/turn-probe/turn-rest-shared-secret")
IDENTITY_SMOKE_REPORT_SCHEMA = "aileron-identity-backup-restore-smoke/v1"
IDENTITY_SMOKE_REPORT_KEYS = {
    "schemaVersion",
    "backupJobUids",
    "restoreJobUid",
    "restoreMarker",
    "jobClosureVerified",
}


class OracleError(RuntimeError):
    pass


class Runner(Protocol):
    def run(self, command: list[str]) -> tuple[int, str, str]: ...


class KubernetesClient(Protocol):
    def get(self, path: str) -> dict: ...

    def patch(self, path: str, document: dict) -> dict: ...

    def delete(self, path: str) -> dict: ...


class SubprocessRunner:
    def run(self, command: list[str]) -> tuple[int, str, str]:
        result = subprocess.run(
            command, capture_output=True, check=False, text=True, timeout=300
        )
        return result.returncode, result.stdout, result.stderr


class InClusterKubernetesClient:
    def __init__(self) -> None:
        token_path = SERVICE_ACCOUNT_DIRECTORY / "token"
        ca_path = SERVICE_ACCOUNT_DIRECTORY / "ca.crt"
        try:
            self._token = token_path.read_text().strip()
            self._context = ssl.create_default_context(cafile=str(ca_path))
        except (OSError, ssl.SSLError) as exc:
            raise OracleError(
                "in-cluster ServiceAccount identity is unavailable"
            ) from exc
        if not self._token:
            raise OracleError("in-cluster ServiceAccount token is empty")

    def _request(self, method: str, path: str, document: dict | None = None) -> dict:
        if not path.startswith("/") or ".." in path:
            raise OracleError("Kubernetes API path is invalid")
        data = (
            json.dumps(document, separators=(",", ":"), sort_keys=True).encode()
            if document is not None
            else None
        )
        request = Request(
            KUBERNETES_API + path,
            data=data,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/merge-patch+json",
            },
            method=method,
        )
        try:
            with urlopen(request, context=self._context, timeout=30) as response:
                body = response.read().decode("utf-8")
        except (HTTPError, URLError, OSError) as exc:
            raise OracleError("fixed in-cluster Kubernetes API probe failed") from exc
        return _json(body, "Kubernetes API probe")

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def patch(self, path: str, document: dict) -> dict:
        return self._request("PATCH", path, document)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=SECTIONS, required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--workspace-id")
    parser.add_argument("--platform-url", required=True)
    parser.add_argument("--issuer-url", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    return parser


def _json(stdout: str, description: str) -> dict:
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise OracleError(f"{description} did not return JSON") from exc
    if not isinstance(value, dict):
        raise OracleError(f"{description} must return a JSON object")
    return value


def _execute(runner: Runner, command: list[str], description: str) -> str:
    exit_code, stdout, _stderr = runner.run(command)
    if exit_code != 0:
        raise OracleError(f"{description} failed")
    return stdout


def build_turn_commands(arguments: argparse.Namespace) -> list[list[str]]:
    authority = urlparse(arguments.platform_url).hostname
    if not authority:
        raise OracleError("platform URL has no host")
    base = [
        "python3",
        str(TRANSPORT_PROBE),
        "turn",
        "--host",
        authority,
        "--username-file",
        str(TURN_PROBE_USERNAME_FILE),
        "--shared-secret-file",
        str(TURN_REST_SHARED_SECRET_FILE),
    ]
    return [[*base, "--path", "frontend"], [*base, "--path", "backend"]]


def _run_turn(arguments: argparse.Namespace, runner: Runner) -> dict:
    results = {}
    for name, command in zip(
        ("frontendPath", "backendPath"), build_turn_commands(arguments)
    ):
        raw = _execute(runner, command, f"{name} TURN probe")
        if not any("relay" in line.lower() for line in raw.splitlines()):
            raise OracleError(f"{name} TURN probe did not negotiate a relay candidate")
        results[name] = "relayed"
    return results


def _run_image_release(
    arguments: argparse.Namespace, kubernetes: KubernetesClient
) -> dict:
    document = kubernetes.get(
        "/api/v1/namespaces/workspace-system/configmaps/aileron-image-release-inventory"
    )
    lines = document.get("data", {}).get("images.tsv", "").splitlines()
    images = []
    for line in lines:
        columns = line.split("\t")
        if len(columns) != 5:
            raise OracleError("image release raw inventory row is invalid")
        component, platform, revision, immutable_image, runtime_immutable_image = (
            columns
        )
        if (
            platform != "linux/amd64"
            or revision != arguments.commit
            or IMMUTABLE_IMAGE.fullmatch(immutable_image) is None
            or IMMUTABLE_IMAGE.fullmatch(runtime_immutable_image) is None
            or immutable_image == runtime_immutable_image
            or immutable_image.rsplit("@", 1)[0]
            != runtime_immutable_image.rsplit("@", 1)[0]
        ):
            raise OracleError("image release raw identity is invalid")
        images.append(
            {
                "component": component,
                "platform": platform,
                "revision": revision,
                "immutableImage": immutable_image,
                "runtimeImmutableImage": runtime_immutable_image,
            }
        )
    observed_components = {image["component"] for image in images}
    if len(images) != len(observed_components) or observed_components not in (
        IMAGE_COMPONENTS,
        IMAGE_COMPONENTS - OPTIONAL_IMAGE_COMPONENTS,
    ):
        raise OracleError("image release raw component set is incomplete")
    return {"images": images}


def _run_identity(arguments: argparse.Namespace, kubernetes: KubernetesClient) -> dict:
    paths = [
        (
            "/apis/apps/v1/namespaces/aileron-identity-system/deployments/"
            "aileron-identity-keycloak"
        ),
        (
            "/api/v1/namespaces/aileron-identity-system/configmaps/"
            "aileron-identity-restore-marker"
        ),
    ]
    deployment, marker = [kubernetes.get(path) for path in paths]
    deployment_metadata = (
        deployment.get("metadata") if isinstance(deployment, dict) else None
    )
    revision = (
        deployment_metadata.get("generation")
        if isinstance(deployment_metadata, dict)
        else None
    )
    status = deployment.get("status") if isinstance(deployment, dict) else None
    restarted = (
        isinstance(revision, int)
        and revision >= 1
        and isinstance(status, dict)
        and status.get("observedGeneration") == revision
        and status.get("replicas")
        == status.get("updatedReplicas")
        == status.get("readyReplicas")
        == status.get("availableReplicas")
        and status.get("replicas", 0) > 0
    )
    marker_metadata = marker.get("metadata") if isinstance(marker, dict) else None
    marker_labels = (
        marker_metadata.get("labels") if isinstance(marker_metadata, dict) else None
    )
    marker_data = marker.get("data") if isinstance(marker, dict) else None
    expected_labels = {
        "platform.aileron.dev/acceptance-owner": "aileron-installer",
        "platform.aileron.dev/acceptance-run-id": arguments.run_id,
        "platform.aileron.dev/source-commit": arguments.commit,
    }
    smoke_report_raw = (
        marker_data.get("smokeReport") if isinstance(marker_data, dict) else None
    )
    try:
        smoke_report = (
            json.loads(smoke_report_raw) if isinstance(smoke_report_raw, str) else None
        )
    except json.JSONDecodeError as exc:
        raise OracleError("Identity restore marker smoke report is invalid") from exc
    backup_job_uids = (
        smoke_report.get("backupJobUids") if isinstance(smoke_report, dict) else None
    )
    restore_job_uid = (
        smoke_report.get("restoreJobUid") if isinstance(smoke_report, dict) else None
    )
    if (
        not isinstance(deployment, dict)
        or deployment.get("apiVersion") != "apps/v1"
        or deployment.get("kind") != "Deployment"
        or not isinstance(deployment_metadata, dict)
        or deployment_metadata.get("name") != "aileron-identity-keycloak"
        or deployment_metadata.get("namespace") != "aileron-identity-system"
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
        or not restarted
        or not isinstance(marker, dict)
        or marker.get("apiVersion") != "v1"
        or marker.get("kind") != "ConfigMap"
        or not isinstance(marker_metadata, dict)
        or marker_metadata.get("name") != "aileron-identity-restore-marker"
        or marker_metadata.get("namespace") != "aileron-identity-system"
        or marker_labels != expected_labels
        or not isinstance(marker_data, dict)
        or set(marker_data) != {"marker", "commit", "runId", "smokeReport"}
        or marker_data.get("marker") != "identity-smoke-marker"
        or marker_data.get("commit") != arguments.commit
        or marker_data.get("runId") != arguments.run_id
        or not isinstance(smoke_report, dict)
        or set(smoke_report) != IDENTITY_SMOKE_REPORT_KEYS
        or smoke_report.get("schemaVersion") != IDENTITY_SMOKE_REPORT_SCHEMA
        or not isinstance(smoke_report_raw, str)
        or smoke_report_raw
        != json.dumps(smoke_report, separators=(",", ":"), sort_keys=True)
        or not isinstance(backup_job_uids, list)
        or len(backup_job_uids) != 2
        or any(
            not isinstance(uid, str)
            or not uid
            or any(
                not character.isprintable() or character.isspace() for character in uid
            )
            for uid in backup_job_uids
        )
        or len(set(backup_job_uids)) != 2
        or not isinstance(restore_job_uid, str)
        or not restore_job_uid
        or any(
            not character.isprintable() or character.isspace()
            for character in restore_job_uid
        )
        or restore_job_uid in backup_job_uids
        or smoke_report.get("restoreMarker") != "identity-smoke-marker"
        or smoke_report.get("jobClosureVerified") is not True
    ):
        raise OracleError(
            "Identity raw install, restart, backup, or restore evidence is incomplete"
        )
    return {
        "installRevision": revision,
        "restartObserved": True,
        "backupJobUids": backup_job_uids,
        "restoreJobUid": restore_job_uid,
        "restoreMarker": smoke_report["restoreMarker"],
        "jobClosureVerified": True,
    }


def _restart_snapshot(
    kubernetes: KubernetesClient, workspace_id: str
) -> dict[str, dict]:
    raw = kubernetes.get(
        "/api/v1/namespaces/workspace-system/pods?"
        "labelSelector=app.kubernetes.io%2Fpart-of%3Daileron"
    )
    items = raw.get("items")
    if not isinstance(items, list):
        raise OracleError("restart pod raw list is invalid")
    observed: dict[str, dict] = {}
    for pod in items:
        labels = pod.get("metadata", {}).get("labels", {})
        component_label = labels.get("app.kubernetes.io/component")
        component = RESTART_COMPONENTS.get(component_label)
        if labels.get("aileron.io/component") == WORKSPACE_BROWSER_COMPONENT:
            if labels.get("aileron.io/workspace-id") != workspace_id:
                continue
            component = "browser"
        if component is None:
            continue
        if component in observed:
            raise OracleError("restart pod component identity is not unique")
        metadata = pod.get("metadata", {})
        status = pod.get("status", {})
        statuses = status.get("containerStatuses")
        ready = any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in status.get("conditions", [])
        )
        if (
            not metadata.get("uid")
            or not metadata.get("name")
            or status.get("phase") != "Running"
            or not ready
            or not isinstance(statuses, list)
            or not statuses
            or any(
                item.get("restartCount") != 0 or item.get("ready") is not True
                for item in statuses
            )
        ):
            raise OracleError("restart pod is not ready without failures")
        observed[component] = pod
    if set(observed) != RESTART_REQUIRED_COMPONENTS:
        raise OracleError("restart pod component set is incomplete")
    return observed


def _run_restart(
    arguments: argparse.Namespace,
    kubernetes: KubernetesClient,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    before = _restart_snapshot(kubernetes, arguments.workspace_id)
    annotation = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "platform.aileron.dev/acceptance-restart-run-id": arguments.run_id
                    }
                }
            }
        }
    }
    for deployment in ("aileron-frontend", "aileron-workspace-operator"):
        kubernetes.patch(
            "/apis/apps/v1/namespaces/workspace-system/deployments/" + deployment,
            annotation,
        )
    kubernetes.delete(
        "/api/v1/namespaces/workspace-system/pods/"
        + before["browser"]["metadata"]["name"]
    )
    after = None
    for _attempt in range(30):
        try:
            candidate = _restart_snapshot(kubernetes, arguments.workspace_id)
        except OracleError:
            sleeper(5)
            continue
        if all(
            candidate[component]["metadata"]["uid"]
            != before[component]["metadata"]["uid"]
            for component in before
        ):
            after = candidate
            break
        sleeper(5)
    if after is None:
        raise OracleError("restart did not replace every required Pod")
    return {
        "frontendUidChanged": True,
        "operatorUidChanged": True,
        "browserUidChanged": True,
        "unexpectedRestarts": 0,
    }


HANDLERS = {
    "turn": _run_turn,
}
KUBERNETES_HANDLERS = {
    "imageRelease": _run_image_release,
    "identity": _run_identity,
    "restart": _run_restart,
}


def run_section(
    arguments: argparse.Namespace,
    runner: Runner,
    kubernetes: KubernetesClient | None = None,
    source_commit_reader: Callable[[], str | None] | None = None,
    lifecycle_sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    if SHA.fullmatch(arguments.commit) is None:
        raise OracleError("source commit must be a full lowercase Git SHA")
    if arguments.section in {"turn", "restart"} and not arguments.workspace_id:
        raise OracleError("workspace identity is required for this oracle section")
    if source_commit_reader is None:

        def source_commit_reader() -> str | None:
            try:
                return SOURCE_COMMIT_FILE.read_text().strip()
            except OSError:
                return None

    source_commit = source_commit_reader()
    if source_commit is None:
        raise OracleError("published oracle source commit marker is unavailable")
    if source_commit != arguments.commit:
        raise OracleError("published oracle image does not match the requested commit")
    if arguments.section in KUBERNETES_HANDLERS:
        client = kubernetes or InClusterKubernetesClient()
        if arguments.section == "restart":
            return _run_restart(arguments, client, lifecycle_sleeper)
        return KUBERNETES_HANDLERS[arguments.section](arguments, client)
    return HANDLERS[arguments.section](arguments, runner)


def main() -> int:
    arguments = create_parser().parse_args()
    observation = run_section(arguments, SubprocessRunner())
    print(json.dumps(observation, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
