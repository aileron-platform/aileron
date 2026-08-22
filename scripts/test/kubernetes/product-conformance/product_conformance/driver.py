"""Executable product conformance driver."""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib
import inspect
import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.x509.oid import NameOID
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .context import ProductConfig, ProductContext
from .contract import CAPABILITY_KEYS, ConformanceReport, Evidence
from .scenarios_jobs import SCENARIOS as JOB_SCENARIOS
from .scenarios_jobs import finalize_manager_api_lifecycle, setup_manager_api_lifecycle

ScenarioResult = list[Evidence] | Awaitable[list[Evidence]]
Scenario = Callable[[ProductContext], ScenarioResult]

_TRANSACTION_WORKSPACE_CONFIGMAP = "product-installation-transaction-workspace"


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _external_oidc_evidence(context: ProductContext) -> list[Evidence]:
    observed = context.external_oidc_observation
    actors = observed.get("actors") if isinstance(observed, dict) else None
    if (
        observed.get("fixture") != "provider-neutral-non-keycloak"
        or not observed.get("authorizationEndpoint")
        or observed.get("callbackPath") != "/api/v1/oauth2/callback"
        or not isinstance(actors, dict)
        or not actors
        or not all(
            actor.get("subject")
            and actor.get("sessionIssued") is True
            and actor.get("jitWorkspaceListAccepted") is True
            for actor in actors.values()
            if isinstance(actor, dict)
        )
        or not all(isinstance(actor, dict) for actor in actors.values())
    ):
        raise AssertionError(
            "external OIDC Authorization Code, callback, session, and JIT evidence is incomplete"
        )
    return [
        Evidence(
            kind="oidc",
            ref=context.settings.oidc_issuer_url,
            assertion=(
                "disposable non-Keycloak provider completed Authorization Code + PKCE, "
                "Manager callback, opaque session issuance, and JIT reconciliation"
            ),
            observed=observed,
        )
    ]


def _load_kubernetes_config() -> None:
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        config.load_incluster_config()
    else:
        config.load_kube_config()


def _public_jwk(private_key: Ed25519PrivateKey, key_id: str) -> dict[str, str]:
    raw_public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    encoded = base64.urlsafe_b64encode(raw_public_key).rstrip(b"=").decode("ascii")
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "use": "sig",
        "alg": "EdDSA",
        "kid": key_id,
        "x": encoded,
    }


def _upsert_secret(
    api: client.CoreV1Api,
    *,
    namespace: str,
    name: str,
    string_data: dict[str, str],
) -> None:
    body = client.V1Secret(
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        type="Opaque",
        string_data=string_data,
    )
    try:
        api.create_namespaced_secret(namespace=namespace, body=body)
    except ApiException as exc:
        if exc.status != 409:
            raise
        api.replace_namespaced_secret(name=name, namespace=namespace, body=body)


def prepare_keys() -> int:
    _load_kubernetes_config()
    namespace = _required_env("E2E_NAMESPACE")
    key_id = os.getenv("PRODUCT_ASSERTION_KEY_ID", "product-conformance-ed25519-v1")
    private_key = Ed25519PrivateKey.generate()
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    jwks = json.dumps(
        {"keys": [_public_jwk(private_key, key_id)]},
        separators=(",", ":"),
        sort_keys=True,
    )
    api = client.CoreV1Api()
    _upsert_secret(
        api,
        namespace=namespace,
        name=os.getenv("PRODUCT_ASSERTION_SIGNER_SECRET", "runtime-assertion-signer"),
        string_data={"private-key.pem": private_key_pem},
    )
    _upsert_secret(
        api,
        namespace=namespace,
        name=os.getenv(
            "PRODUCT_ASSERTION_JWKS_SECRET", "runtime-assertion-public-jwks"
        ),
        string_data={"jwks.json": jwks},
    )
    return 0


def prepare_oidc_fixture_tls() -> int:
    _load_kubernetes_config()
    namespace = _required_env("E2E_NAMESPACE")
    hostname = _required_env("OIDC_FIXTURE_HOSTNAME")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
        .sign(private_key, hashes.SHA256())
    )
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM).decode(
        "ascii"
    )
    _upsert_secret(
        client.CoreV1Api(),
        namespace=namespace,
        name="external-oidc-tls",
        string_data={
            "ca.crt": certificate_pem,
            "tls.crt": certificate_pem,
            "tls.key": private_key_pem,
        },
    )
    return 0


def _transaction_context() -> ProductContext:
    settings = ProductConfig.from_environment()
    return ProductContext(
        settings,
        core=client.CoreV1Api(),
        apps=client.AppsV1Api(),
        custom=client.CustomObjectsApi(),
        discovery=client.DiscoveryV1Api(),
    )


def _login_transaction_owner(context: ProductContext) -> None:
    suffix = re.sub(
        r"[^a-z0-9]+", "-", context.settings.run_id.lower()
    ).strip("-")
    username = f"e2e-owner-{(suffix[-24:] or 'run')}"
    context.sessions["owner"] = context.oidc_adapter.login(
        manager_url=context.settings.manager_url,
        username=username,
    )
    response = context.request_owner("GET", "/workspaces")
    if response.status_code != 200:
        raise AssertionError(
            f"Installation transaction owner login returned {response.status_code}"
        )


def _wait_transaction_control_plane(context: ProductContext) -> None:
    deadline = time.monotonic() + 300
    consecutive = 0
    while time.monotonic() < deadline:
        operator = context.cluster.apps.read_namespaced_deployment(
            "workspace-operator",
            context.settings.namespace,
        )
        status = operator.status
        ready = (
            status.observed_generation == operator.metadata.generation
            and status.ready_replicas == 1
            and status.available_replicas == 1
        )
        if ready:
            context.cluster.wait_supervisor_processes(
                {
                    "fastapi": "RUNNING",
                    "celery-worker": "RUNNING",
                    "celery-beat": "RUNNING",
                }
            )
            consecutive += 1
            if consecutive == 3:
                return
        else:
            consecutive = 0
        time.sleep(1)
    raise AssertionError("Installation transaction control plane did not stabilize")


def _wait_failed_transaction_workspace_absent(
    context: ProductContext,
    workspace_id: str,
) -> None:
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        resource = context.cluster._read_workspace_custom_resource(workspace_id)
        workspace_pvc = context.cluster._read_namespaced_pvc(
            f"workspace-pvc-{workspace_id}"
        )
        runtime_home_pvc = context.cluster._read_namespaced_pvc(
            f"workspace-runtime-home-pvc-{workspace_id}"
        )
        if (
            resource is None
            and workspace_pvc is None
            and runtime_home_pvc is None
            and not context.cluster.workspace_pods(workspace_id)
        ):
            return
        time.sleep(1)
    raise AssertionError(
        f"Failed installation transaction Workspace left cluster residue: {workspace_id}"
    )


def _delete_failed_transaction_workspace(
    context: ProductContext,
    *,
    workspace_id: str,
    workspace_name: str,
) -> None:
    response = context.request_owner(
        "DELETE",
        f"/workspaces/{workspace_id}",
        json={"confirmationName": workspace_name},
    )
    if response.status_code != 202:
        raise AssertionError(
            "Delete failed installation transaction Workspace returned "
            f"{response.status_code}: {response.text[:500]!r}"
        )
    context.db.wait_workspace(
        workspace_id,
        lambda row: row is None,
        description="failed installation transaction Workspace deleted",
        timeout_seconds=600,
    )
    _wait_failed_transaction_workspace_absent(context, workspace_id)
    context.cluster.delete_workspace_storage(workspace_id)


def prepare_transaction_workspace() -> int:
    """Create a disposable running Workspace for installation rotation evidence."""

    _load_kubernetes_config()
    context = _transaction_context()
    try:
        _login_transaction_owner(context)
        _wait_transaction_control_plane(context)
        suffix = re.sub(
            r"[^a-z0-9]+", "-", context.settings.run_id.lower()
        ).strip("-")
        workspace_name = f"Installation Transaction {(suffix[-24:] or 'run')}"
        workspace_id = ""
        for attempt in range(2):
            response = context.request_owner(
                "POST",
                "/workspaces",
                json={
                    "name": workspace_name,
                    "description": "Disposable installation transaction workspace",
                    "runtime": "universal",
                    "agenticTools": ["claude-code"],
                },
            )
            if response.status_code != 201:
                raise AssertionError(
                    "Create installation transaction Workspace returned "
                    f"{response.status_code}: {response.text[:500]!r}"
                )
            workspace = response.json()
            workspace_id = workspace.get("id")
            if not isinstance(workspace_id, str) or not workspace_id:
                raise AssertionError("Installation transaction Workspace has no id")
            context.workspace_id = workspace_id
            context.workspace_name = workspace_name
            context.cluster.ensure_workspace_storage(workspace_id)
            runtime_job = workspace.get("runtimeJob") or {}
            start_job_id = runtime_job.get("id")
            if not isinstance(start_job_id, str) or not start_job_id:
                latest = context.db.get_latest_job(workspace_id, "workspace_start")
                start_job_id = latest.get("id") if latest else None
            if not isinstance(start_job_id, str) or not start_job_id:
                raise AssertionError(
                    "Installation transaction Workspace has no durable start job"
                )
            try:
                context.db.wait_job(start_job_id, "succeeded")
                break
            except AssertionError:
                _delete_failed_transaction_workspace(
                    context,
                    workspace_id=workspace_id,
                    workspace_name=workspace_name,
                )
                if attempt == 1:
                    raise
                _wait_transaction_control_plane(context)
        context.db.wait_workspace(
            workspace_id,
            lambda row: bool(
                row
                and row["runtime_status"] == "running"
                and row["runtime_instance_id"]
            ),
            description="installation transaction Workspace running",
            timeout_seconds=600,
        )
        generation = context.refresh_generation()
        lifetime_uids = {
            key: generation[key]
            for key in ("workspaceCrUid", "workspacePvcUid", "runtimeHomePvcUid")
        }
        body = client.V1ConfigMap(
            metadata=client.V1ObjectMeta(
                name=_TRANSACTION_WORKSPACE_CONFIGMAP,
                namespace=context.settings.namespace,
            ),
            data={
                "workspaceId": workspace_id,
                "workspaceName": workspace_name,
                "lifetimeUids": json.dumps(lifetime_uids, sort_keys=True),
            },
        )
        try:
            context.cluster.core.create_namespaced_config_map(
                namespace=context.settings.namespace,
                body=body,
            )
        except ApiException as exc:
            if exc.status != 409:
                raise
            context.cluster.core.replace_namespaced_config_map(
                name=_TRANSACTION_WORKSPACE_CONFIGMAP,
                namespace=context.settings.namespace,
                body=body,
            )
        print(f"TRANSACTION_WORKSPACE_ID={workspace_id}")
        return 0
    finally:
        context.close()


def cleanup_transaction_workspace() -> int:
    """Delete the disposable transaction Workspace through the Manager API."""

    _load_kubernetes_config()
    context = _transaction_context()
    try:
        record = context.cluster.core.read_namespaced_config_map(
            name=_TRANSACTION_WORKSPACE_CONFIGMAP,
            namespace=context.settings.namespace,
        )
        data = record.data or {}
        workspace_id = data.get("workspaceId", "")
        workspace_name = data.get("workspaceName", "")
        lifetime_uids = json.loads(data.get("lifetimeUids", "{}"))
        if not workspace_id or not workspace_name or not isinstance(lifetime_uids, dict):
            raise AssertionError("Installation transaction Workspace record is incomplete")
        _login_transaction_owner(context)
        response = context.request_owner(
            "DELETE",
            f"/workspaces/{workspace_id}",
            json={"confirmationName": workspace_name},
        )
        if response.status_code != 202:
            raise AssertionError(
                "Delete installation transaction Workspace returned "
                f"{response.status_code}: {response.text[:500]!r}"
            )
        context.db.wait_workspace(
            workspace_id,
            lambda row: row is None,
            description="installation transaction Workspace deleted",
            timeout_seconds=600,
        )
        context.cluster.wait_workspace_absent(
            workspace_id,
            expected_uids=lifetime_uids,
        )
        context.cluster.delete_workspace_storage(workspace_id)
        context.cluster.core.delete_namespaced_config_map(
            name=_TRANSACTION_WORKSPACE_CONFIGMAP,
            namespace=context.settings.namespace,
        )
        print(f"TRANSACTION_WORKSPACE_DELETED={workspace_id}")
        return 0
    finally:
        context.close()


SCENARIOS: dict[str, Scenario] = dict(JOB_SCENARIOS)


def _load_optional_scenarios() -> None:
    """Register independently implemented scenario groups when present."""

    for module_name in ("scenarios_workspace", "scenarios_realtime"):
        try:
            module = importlib.import_module(f"{__package__}.{module_name}")
        except ModuleNotFoundError as exc:
            if exc.name != f"{__package__}.{module_name}":
                raise
            continue
        scenarios = getattr(module, "SCENARIOS", {})
        if not isinstance(scenarios, dict):
            raise TypeError(f"{module_name}.SCENARIOS must be a mapping")
        overlap = set(SCENARIOS).intersection(scenarios)
        if overlap:
            raise ValueError(f"Duplicate product scenarios: {sorted(overlap)}")
        SCENARIOS.update(scenarios)


async def _resolve_scenario_result(result: ScenarioResult) -> list[Evidence]:
    if inspect.isawaitable(result):
        return await result
    return result


async def _execute_conformance(
    context: ProductContext,
    report: ConformanceReport,
) -> None:
    lifecycle_setup: list[Evidence] | None = None
    lifecycle_setup_failure = ""
    try:
        lifecycle_setup = await setup_manager_api_lifecycle(context)
    except Exception as exc:
        lifecycle_setup_failure = f"{type(exc).__name__}: {exc}"
        report.fail_capability(
            "managerApiLifecycle",
            lifecycle_setup_failure,
        )

    if lifecycle_setup is None:
        if context.workspace_id:
            try:
                await finalize_manager_api_lifecycle(context, [])
            except Exception as cleanup_exc:
                lifecycle_setup_failure += (
                    "; cleanup failed: " f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )
                report.fail_capability(
                    "managerApiLifecycle",
                    lifecycle_setup_failure,
                )
        for key in CAPABILITY_KEYS:
            if key in {"externalOidcAuthorizationCodeJit", "managerApiLifecycle"}:
                continue
            report.fail_capability(key, "manager API lifecycle setup failed")
        return

    for key in CAPABILITY_KEYS:
        if key in {"externalOidcAuthorizationCodeJit", "managerApiLifecycle"}:
            continue
        scenario = SCENARIOS.get(key)
        if scenario is None:
            report.fail_capability(key, "scenario implementation is pending")
            continue
        try:
            evidence = await _resolve_scenario_result(scenario(context))
            report.pass_capability(key, evidence)
        except Exception as exc:
            report.fail_capability(key, f"{type(exc).__name__}: {exc}")

    try:
        lifecycle_evidence = await finalize_manager_api_lifecycle(
            context,
            lifecycle_setup,
        )
        report.pass_capability("managerApiLifecycle", lifecycle_evidence)
    except Exception as exc:
        report.fail_capability(
            "managerApiLifecycle",
            f"{type(exc).__name__}: {exc}",
            evidence=lifecycle_setup,
        )


def run_conformance() -> int:
    _load_kubernetes_config()
    _load_optional_scenarios()
    settings = ProductConfig.from_environment()
    report = ConformanceReport(run_id=settings.run_id, namespace=settings.namespace)
    context = ProductContext(
        settings,
        core=client.CoreV1Api(),
        apps=client.AppsV1Api(),
        custom=client.CustomObjectsApi(),
        discovery=client.DiscoveryV1Api(),
    )
    try:
        try:
            context.assert_prerequisites()
        except Exception as exc:
            for key in CAPABILITY_KEYS:
                report.fail_capability(
                    key, f"prerequisite failed: {type(exc).__name__}: {exc}"
                )
        else:
            oidc_evidence = _external_oidc_evidence(context)
            report.pass_capability(
                "externalOidcAuthorizationCodeJit",
                oidc_evidence,
            )
            asyncio.run(_execute_conformance(context, report))
            try:
                context.verify_logout()
            except Exception as exc:
                report.fail_capability(
                    "externalOidcAuthorizationCodeJit",
                    f"logout verification failed: {type(exc).__name__}: {exc}",
                    evidence=oidc_evidence,
                )
    finally:
        context.close()

    result = report.to_dict()
    settings.report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.report_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("PRODUCT_CONFORMANCE_RESULT=" + json.dumps(result, separators=(",", ":")))
    return 0 if report.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=(
            "prepare-keys",
            "prepare-oidc-fixture-tls",
            "prepare-transaction-workspace",
            "cleanup-transaction-workspace",
            "run",
            "serve-oidc-fixture",
        ),
    )
    args = parser.parse_args()
    if args.command == "prepare-keys":
        return prepare_keys()
    if args.command == "prepare-oidc-fixture-tls":
        return prepare_oidc_fixture_tls()
    if args.command == "prepare-transaction-workspace":
        return prepare_transaction_workspace()
    if args.command == "cleanup-transaction-workspace":
        return cleanup_transaction_workspace()
    if args.command == "serve-oidc-fixture":
        from .oidc_fixture import serve

        return serve()
    return run_conformance()


if __name__ == "__main__":
    raise SystemExit(main())
