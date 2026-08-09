"""Executable product conformance driver."""

from __future__ import annotations

import argparse
import asyncio
import base64
import importlib
import inspect
import json
import os
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


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


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
        for key in CAPABILITY_KEYS[1:]:
            report.fail_capability(key, "manager API lifecycle setup failed")
        return

    for key in CAPABILITY_KEYS[1:]:
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
        context.assert_prerequisites()
        asyncio.run(_execute_conformance(context, report))
        context.verify_logout()
    except Exception as exc:
        for key in CAPABILITY_KEYS:
            report.fail_capability(
                key, f"prerequisite failed: {type(exc).__name__}: {exc}"
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
            "run",
            "serve-oidc-fixture",
        ),
    )
    args = parser.parse_args()
    if args.command == "prepare-keys":
        return prepare_keys()
    if args.command == "prepare-oidc-fixture-tls":
        return prepare_oidc_fixture_tls()
    if args.command == "serve-oidc-fixture":
        from .oidc_fixture import serve

        return serve()
    return run_conformance()


if __name__ == "__main__":
    raise SystemExit(main())
