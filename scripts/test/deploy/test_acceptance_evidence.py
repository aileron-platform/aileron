from __future__ import annotations

import base64
import hashlib
import hmac
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts/deploy/rke2/acceptance_evidence.py"
SPEC = importlib.util.spec_from_file_location("acceptance_evidence", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
BUNDLE_PATH = ROOT / "scripts/deploy/rke2/acceptance_bundle.py"
BUNDLE_SPEC = importlib.util.spec_from_file_location("acceptance_bundle", BUNDLE_PATH)
assert BUNDLE_SPEC and BUNDLE_SPEC.loader
BUNDLE = importlib.util.module_from_spec(BUNDLE_SPEC)
BUNDLE_SPEC.loader.exec_module(BUNDLE)
CONTRACT = ROOT / "scripts/deploy/rke2/deployment-acceptance-contract.json"
IMAGE_COMPONENTS = json.loads(
    (ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
)["publishedComponents"]
COMMIT = "a" * 40
WORKSPACE = {"id": "workspace-1", "userSubject": "oidc-user-1"}
_UNSET_WORKSPACE_CONTEXT = object()
UTC = timezone.utc
NOW = datetime(2026, 8, 8, 8, 0, tzinfo=UTC)
KEY = bytes(range(32))
CLUSTER_UID = "11111111-1111-4111-8111-111111111111"
ACCEPTANCE_NAMESPACE_UID = "33333333-3333-4333-8333-333333333333"
SECRET_UID = "22222222-2222-4222-8222-222222222222"
IDENTITY_DIGEST = "b" * 64
BROWSER_IMAGE_ID = f"sha256:{'c' * 64}"
BROWSER_SCRIPT_BYTES = b"tracked browser acceptance fixture\n"
BROWSER_SCRIPT_DIGEST = hashlib.sha256(BROWSER_SCRIPT_BYTES).hexdigest()
SUITE_RUNNER_IMAGE_ID = f"sha256:{'f' * 64}"
DEPLOYMENT_RUN_ID = "run-20260808"
SUITE_SOURCE_ROOT = "/private/.suites-source-123456789abc"
OFFLINE_SOURCE_ROOT = "/private/.offlineOidcConformance-source-123456789abc"
SOURCE_ARCHIVE_BYTES = b"exact commit archive fixture\n"
SOURCE_ARCHIVE_DIGEST = hashlib.sha256(SOURCE_ARCHIVE_BYTES).hexdigest()
RESET_BACKEND_LOCATOR = {
    "type": "nfs",
    "server": "192.168.50.100",
    "path": "/volume1/okd/aileron/workspace-1",
}
RESET_BACKEND_LOCATOR_SHA256 = hashlib.sha256(
    json.dumps(RESET_BACKEND_LOCATOR, separators=(",", ":"), sort_keys=True).encode()
).hexdigest()
CLEANUP_SOURCE_FILE = "clean-reset-backend-cleanup-results.json"
CLEANUP_SOURCE_BYTES = b'{"fixture":"signed backend cleanup aggregate"}\n'
CLEANUP_SOURCE_SHA256 = hashlib.sha256(CLEANUP_SOURCE_BYTES).hexdigest()
POST_RESET_SOURCE_FILE = "clean-reset-backend-post-reset-verification.json"
POST_RESET_SOURCE_BYTES = b'{"fixture":"independent read-only backend verification"}\n'
POST_RESET_SOURCE_SHA256 = hashlib.sha256(POST_RESET_SOURCE_BYTES).hexdigest()
SUITE_RUNNER_REPOSITORIES = {
    "docker": "ailerondocker/compose-e2e-test",
    "helm": "ailerondocker/helm-contract-test",
    "frontend": "ailerondocker/workspace-ui-suite",
    "manager": "ailerondocker/workspace-manager-suite",
    "operator": "ailerondocker/workspace-operator-suite",
    "identity": "ailerondocker/deployment-contract-test",
    "platform-conformance": "ailerondocker/product-conformance-test",
    "kubernetes-hardening": "ailerondocker/kubernetes-hardening-test",
    "docs-zh-Hant": "ailerondocker/docs-site-test",
    "docs-en": "ailerondocker/docs-site-test",
}
SUITE_IMAGE_ENVIRONMENT = {
    "docker": "AILERON_COMPOSE_E2E_TEST_IMAGE",
    "helm": "AILERON_HELM_CONTRACT_TEST_IMAGE",
    "frontend": "AILERON_FRONTEND_TEST_IMAGE",
    "manager": "AILERON_MANAGER_TEST_IMAGE",
    "operator": "AILERON_OPERATOR_TEST_IMAGE",
    "identity": "AILERON_DEPLOYMENT_CONTRACT_TEST_IMAGE",
    "platform-conformance": "AILERON_PRODUCT_CONFORMANCE_TEST_IMAGE",
    "kubernetes-hardening": "AILERON_KUBERNETES_HARDENING_TEST_IMAGE",
    "docs-zh-Hant": "AILERON_DOCS_SITE_TEST_IMAGE",
    "docs-en": "AILERON_DOCS_SITE_TEST_IMAGE",
}
BACKEND_PROFILE = {
    "schemaVersion": "aileron-backend-execution-profile/v1",
    "executionNamespace": "aileron-backend-attestor-system",
    "namespaceOwner": "aileron-installer",
    "imagePullSecret": "harbor-rke-creds",
    "nfsMountRoots": [{"server": "192.168.50.100", "path": "/volume1/okd/aileron"}],
    "localPathNodes": [],
}


@pytest.fixture(autouse=True)
def _stable_store_anchor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_secrets = tmp_path / "install-secrets"
    install_secrets.mkdir(mode=0o700)
    store = install_secrets / "rke2"
    store.mkdir(mode=0o700)
    anchor = store / "acceptance-trust-anchor.json"
    anchor.write_text(
        json.dumps(
            {
                "contractVersion": "aileron-acceptance-trust-anchor/v2",
                "clusterUid": CLUSTER_UID,
                "installationIdentitySha256": IDENTITY_DIGEST,
                "keySha256": hashlib.sha256(KEY).hexdigest(),
                "secretName": "aileron-acceptance-signing",
                "secretNamespace": "aileron-acceptance-system",
                "secretUid": SECRET_UID,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    anchor.chmod(0o600)
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE, "SECRET_STORE", store
    )
    monkeypatch.setattr(
        BUNDLE.EVIDENCE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE,
        "SECRET_STORE",
        store,
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE, "PRIVATE_ROOT", tmp_path
    )
    monkeypatch.setattr(
        BUNDLE.EVIDENCE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        tmp_path,
    )


def _key(tmp_path: Path) -> Path:
    path = tmp_path / "acceptance-hmac.key"
    path.write_bytes(KEY)
    path.chmod(0o600)
    return path


def _kubeconfig(tmp_path: Path) -> Path:
    path = tmp_path / "kubeconfig"
    path.write_text("fixture", encoding="utf-8")
    path.chmod(0o600)
    return path


def _canonical_kubeconfig_bytes() -> bytes:
    return (
        json.dumps(
            {
                "apiVersion": "v1",
                "kind": "Config",
                "current-context": "rke2-homelab",
                "clusters": [
                    {
                        "name": "homelab",
                        "cluster": {
                            "server": "https://192.0.2.10:6443",
                            "certificate-authority-data": base64.b64encode(
                                b"homelab-ca"
                            ).decode(),
                        },
                    }
                ],
                "contexts": [
                    {
                        "name": "rke2-homelab",
                        "context": {"cluster": "homelab", "user": "installer"},
                    }
                ],
                "users": [{"name": "installer", "user": {"token": "installer-token"}}],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


class ClusterRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> bytes:
        self.commands.append(command)
        if command[-4:] == [
            "get",
            "namespace",
            "kube-system",
            "--output=jsonpath={.metadata.uid}",
        ]:
            return CLUSTER_UID.encode()
        if command[-4:] == [
            "get",
            "namespace",
            "aileron-acceptance-system",
            "--output=json",
        ]:
            return json.dumps(
                {
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
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        if command[-4:] == [
            "get",
            "secret",
            "aileron-acceptance-signing",
            "--output=json",
        ]:
            return json.dumps(
                {
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
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        raise AssertionError(f"unexpected cluster fixture command: {command!r}")


def _cluster_kwargs(tmp_path: Path) -> dict:
    return {
        "context": "rke2-homelab",
        "runner": ClusterRunner(),
        "now": NOW,
    }


SUITE_SERVICES = {
    "docker": (
        "scripts/test/compose-e2e/docker-compose.acceptance.yml",
        "compose-e2e-test",
    ),
    "helm": ("scripts/test/helm/docker-compose.test.yml", "helm-contract-test"),
    "frontend": ("frontend/docker-compose.test.yml", "frontend-test"),
    "manager": ("workspace-manager/docker-compose.test.yml", "workspace-manager-test"),
    "operator": (
        "workspace-operator/docker-compose.test.yml",
        "workspace-operator-test",
    ),
    "identity": (
        "scripts/test/deploy/docker-compose.test.yml",
        "deployment-contract-test",
    ),
    "platform-conformance": (
        "scripts/test/kubernetes/product-conformance/docker-compose.test.yml",
        "product-conformance-test",
    ),
    "kubernetes-hardening": (
        "scripts/test/kubernetes/product-conformance/docker-compose.test.yml",
        "kubernetes-conformance-hardening-test",
    ),
    "docs-zh-Hant": ("docs-site/docker-compose.test.yml", "docs-site-build-zh-hant"),
    "docs-en": ("docs-site/docker-compose.test.yml", "docs-site-build-en"),
}


def _suite_project(name: str) -> str:
    return f"aileron-{name.lower()}-{COMMIT[:12]}-1234abcd"


def _suite_image(name: str) -> str:
    return f"{SUITE_RUNNER_REPOSITORIES[name]}:{COMMIT}-123456789abc"


def _suite_command(name: str, source_root: str = SUITE_SOURCE_ROOT) -> list[str]:
    compose_file, service = SUITE_SERVICES[name]
    return [
        *MODULE.HERMETIC_COMPOSE_ENVIRONMENT,
        f"AILERON_SOURCE_REVISION={COMMIT}",
        f"AILERON_SUITE_SOURCE_ROOT={source_root}",
        f"{SUITE_IMAGE_ENVIRONMENT[name]}={SUITE_RUNNER_IMAGE_ID}",
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        _suite_project(name),
        "--file",
        f"{source_root}/{compose_file}",
        "run",
        "--pull",
        "never",
        "--rm",
        service,
    ]


def _suite_cleanup(name: str, source_root: str = SUITE_SOURCE_ROOT) -> list[str]:
    compose_file, _ = SUITE_SERVICES[name]
    return [
        *MODULE.HERMETIC_COMPOSE_ENVIRONMENT,
        f"AILERON_SOURCE_REVISION={COMMIT}",
        f"AILERON_SUITE_SOURCE_ROOT={source_root}",
        f"{SUITE_IMAGE_ENVIRONMENT[name]}={SUITE_RUNNER_IMAGE_ID}",
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        _suite_project(name),
        "--file",
        f"{source_root}/{compose_file}",
        "down",
        "--volumes",
        "--remove-orphans",
    ]


def _suite_runner(name: str, source_root: str = SUITE_SOURCE_ROOT) -> dict:
    image = _suite_image(name)
    context_relative, dockerfile_relative, target = MODULE.SUITE_BUILD_TARGETS[name]
    build_command = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--file",
        f"{source_root}/{dockerfile_relative}",
        "--tag",
        image,
        "--build-arg",
        f"SOURCE_REVISION={COMMIT}",
    ]
    for argument_name, argument_value in MODULE.SUITE_BUILD_ARGUMENTS.get(name, ()):
        build_command.extend(["--build-arg", f"{argument_name}={argument_value}"])
    if target is not None:
        build_command.extend(["--target", target])
    build_command.append(str((Path(source_root) / context_relative).resolve()))
    return {
        "image": image,
        "imageId": SUITE_RUNNER_IMAGE_ID,
        "architecture": "amd64",
        "sourceRevision": COMMIT,
        "buildCommand": build_command,
        "inspectCommand": [
            "docker",
            "image",
            "inspect",
            '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
            image,
        ],
    }


def _browser_probe() -> dict:
    return {
        "imageId": BROWSER_IMAGE_ID,
        "trackedScriptSha256": BROWSER_SCRIPT_DIGEST,
        "imageScriptSha256": BROWSER_SCRIPT_DIGEST,
        "exactSourceMatch": True,
    }


def _browser_source_commands(
    section: str,
    *,
    workspace_id: str | None = None,
    ca_bootstrap_wrapper: bool = False,
) -> dict[str, list[list[str]]]:
    image_tag = f"ailerondocker/workspace-ui-playwright:{COMMIT}-123456789abc"
    lifecycle_command = [
        "docker",
        "run",
        "--rm",
        BROWSER_IMAGE_ID,
        "node",
        "/app/e2e/acceptance.mjs",
        "--section",
        section,
    ]
    if ca_bootstrap_wrapper:
        lifecycle_command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            BROWSER_IMAGE_ID,
            "sh",
            "-ec",
            'exec node /app/e2e/acceptance.mjs "$@"',
            "acceptance-browser",
            "--section",
            section,
        ]
    if workspace_id is not None:
        lifecycle_command.extend(["--workspace-id", workspace_id])
    return {
        "a" * 64: [
            lifecycle_command,
            [
                "docker",
                "build",
                "--file",
                "frontend/Dockerfile.playwright",
                "--tag",
                image_tag,
                "--label",
                f"org.opencontainers.image.revision={COMMIT}",
                "--pull=false",
                "frontend",
            ],
            [
                "docker",
                "image",
                "inspect",
                '--format={{.Id}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
                image_tag,
            ],
            [
                "docker",
                "image",
                "tag",
                BROWSER_IMAGE_ID,
                f"ailerondocker/workspace-ui-playwright:{COMMIT}",
            ],
            ["docker", "image", "rm", "--force", image_tag],
        ],
        BROWSER_SCRIPT_DIGEST: [
            ["git", "show", f"{COMMIT}:frontend/e2e/acceptance.mjs"],
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "node",
                BROWSER_IMAGE_ID,
                "-e",
                (
                    'process.stdout.write(require("node:fs").readFileSync('
                    '"/app/e2e/acceptance.mjs"))'
                ),
            ],
        ],
    }


def _validate_browser_observations(
    section: str,
    observations: dict,
    source_commands: dict[str, list[list[str]]],
    *,
    workspace_context: object = _UNSET_WORKSPACE_CONTEXT,
) -> None:
    default_workspace = (
        WORKSPACE
        if section
        in {
            "oidcWorkspace",
            "terminal",
            "http",
            "browser",
            "websocket",
            "workspaceLifecycle",
        }
        else None
    )
    MODULE._validate_observations(
        section,
        observations,
        contract=json.loads(CONTRACT.read_text()),
        commit=COMMIT,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        authentication_mode="bundledKeycloak",
        workspace=(
            default_workspace
            if workspace_context is _UNSET_WORKSPACE_CONTEXT
            else workspace_context
        ),
        started=datetime(2026, 8, 8, 6, 0, tzinfo=UTC),
        finished=datetime(2026, 8, 8, 6, 1, tzinfo=UTC),
        source_digests=set(source_commands),
        canonical_kubeconfig=Path("/private/kubeconfig"),
        context="rke2-homelab",
        source_commands=source_commands,
    )


def _source_provenance(*, tree_digest_checks: int) -> dict:
    return {
        "headCommit": COMMIT,
        "targetCommit": COMMIT,
        "worktreeClean": True,
        "untrackedFilesIncluded": True,
        "archiveSha256": SOURCE_ARCHIVE_DIGEST,
        "treeSha256": "1" * 64,
        "archiveCommand": [
            "git",
            "-C",
            "/repo",
            "archive",
            "--format=tar.gz",
            COMMIT,
        ],
        "materializedTreeReadOnly": True,
        "treeDigestChecks": tree_digest_checks,
    }


def _observations(section: str, source_digest: str, reset_snapshot_sha256: str) -> dict:
    values = {
        "cleanReset": {
            "resetRunId": "run-20260808",
            "inventorySha256": source_digest,
            "fixedResetTargets": {
                "namespaces": [
                    "aileron-identity-system",
                    "aileron-turn-system",
                    "workspace-system",
                ],
                "storageClasses": [
                    "aileron-local-rwo-delete",
                    "aileron-local-rwo-retain",
                    "aileron-nfs-rwx-delete",
                    "aileron-nfs-rwx-retain",
                ],
            },
            "expected": {
                "namespaces": [
                    "aileron-identity-system",
                    "aileron-turn-system",
                    "workspace-system",
                ],
                "workspaceCRs": ["workspace-1"],
                "pvcs": ["workspace-system/data-workspace-1"],
                "pvs": ["pv-1"],
                "backendTargets": [
                    {
                        "persistentVolume": {
                            "name": "pv-1",
                            "uid": "pv-1-uid",
                        },
                        "locatorSha256": RESET_BACKEND_LOCATOR_SHA256,
                    }
                ],
            },
            "observedAbsent": {
                "namespaces": [
                    "aileron-identity-system",
                    "aileron-turn-system",
                    "workspace-system",
                ],
                "workspaceCRs": ["workspace-1"],
                "pvcs": ["workspace-system/data-workspace-1"],
                "pvs": ["pv-1"],
            },
            "backendCleanupResults": {
                "schemaVersion": "aileron-backend-cleanup-results/v1",
                "sourceFile": CLEANUP_SOURCE_FILE,
                "sourceSha256": CLEANUP_SOURCE_SHA256,
                "commit": COMMIT,
                "runId": DEPLOYMENT_RUN_ID,
                "snapshotSha256": reset_snapshot_sha256,
                "allAbsent": True,
                "targetResultDigests": [
                    {
                        "persistentVolume": {
                            "name": "pv-1",
                            "uid": "pv-1-uid",
                        },
                        "locatorSha256": RESET_BACKEND_LOCATOR_SHA256,
                        "cleanupResultSha256": "1" * 64,
                        "verificationResultSha256": "2" * 64,
                    }
                ],
            },
            "backendPostResetVerification": {
                "schemaVersion": "aileron-backend-post-reset-verification/v1",
                "sourceFile": POST_RESET_SOURCE_FILE,
                "sourceSha256": POST_RESET_SOURCE_SHA256,
                "commit": COMMIT,
                "runId": DEPLOYMENT_RUN_ID,
                "snapshotSha256": reset_snapshot_sha256,
                "backendCleanupResultsSha256": CLEANUP_SOURCE_SHA256,
                "allAbsent": True,
                "targetResultDigests": [
                    {
                        "persistentVolume": {
                            "name": "pv-1",
                            "uid": "pv-1-uid",
                        },
                        "locatorSha256": RESET_BACKEND_LOCATOR_SHA256,
                        "verificationResultSha256": "3" * 64,
                    }
                ],
            },
        },
        "imageRelease": {
            "images": [
                {
                    "component": image["component"],
                    "platform": image["platform"],
                    "revision": image["revision"],
                    "immutableImage": image["immutableImage"],
                    "runtimeImmutableImage": image["runtimeImmutableImage"],
                }
                for image in _signed_soak_images()
            ]
        },
        "identity": {
            "installRevision": 1,
            "restartObserved": True,
            "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
            "restoreJobUid": "restore-job-uid",
            "restoreMarker": "identity-smoke-marker",
            "jobClosureVerified": True,
        },
        "oidcWorkspace": {
            "flow": "authorization-code-pkce",
            "createdWorkspaceId": WORKSPACE["id"],
            "userSubject": WORKSPACE["userSubject"],
            "browserProbe": _browser_probe(),
        },
        "terminal": {
            "sessionId": "terminal-1",
            "roundTrip": "verified",
            "browserProbe": _browser_probe(),
        },
        "http": {
            "runtime": 200,
            "browser": 200,
            "canvas": 200,
            "browserProbe": _browser_probe(),
        },
        "browser": {
            "route": f"/workspaces/{WORKSPACE['id']}/browser",
            "websocket": "open",
            "webrtc": "connected",
            "videoTrack": "live",
            "dataChannel": "open",
            "videoWidth": 1440,
            "videoHeight": 900,
            "browserProbe": _browser_probe(),
        },
        "websocket": {
            "handshakeStatus": 101,
            "messagesObserved": 2,
            "browserProbe": _browser_probe(),
        },
        "turn": {"frontendPath": "relayed", "backendPath": "relayed"},
        "workspaceLifecycle": {
            "componentsRestarted": ["runtime", "browser", "canvas"],
            "stopObserved": "stopped",
            "startObserved": "ready",
            "browserProbe": _browser_probe(),
        },
        "restart": {
            "frontendUidChanged": True,
            "operatorUidChanged": True,
            "browserUidChanged": True,
            "unexpectedRestarts": 0,
        },
        "soak": {
            "identityMode": "bundledKeycloak",
            "mutationMode": "read-only",
            "baseline": {},
            "samples": [
                {
                    "observedAt": (
                        datetime(2026, 8, 8, 6, 43, tzinfo=UTC)
                        + timedelta(seconds=60 * index)
                    )
                    .isoformat(timespec="seconds")
                    .replace("+00:00", "Z"),
                }
                for index in range(31)
            ],
        },
        "adminDisableLogin": {
            "initialLogin": "accepted",
            "disabledLogin": "rejected",
            "restoration": "reEnabled",
            "restoredLogin": "accepted",
            "platformAdmin": {
                "platformRole": "admin",
                "requiredOperations": "verified",
                "adminUsersStatus": 200,
                "marketplaceCatalogStatus": 200,
            },
            "browserProbe": _browser_probe(),
        },
        "offlineOidcConformance": {
            "mode": "offline",
            "scope": "provider-neutral-oidc-contract",
            "authenticationMode": "oidc-without-ldap",
            "capabilities": [
                "authorizationCodePkce",
                "jitProvisioning",
                "providerNeutralIssuer",
            ],
            "result": "passed",
            "projectName": _suite_project("platform-conformance"),
            "cleanupCommand": _suite_cleanup(
                "platform-conformance", OFFLINE_SOURCE_ROOT
            ),
            "cleaned": True,
            "runner": _suite_runner("platform-conformance", OFFLINE_SOURCE_ROOT),
            "sourceProvenance": _source_provenance(tree_digest_checks=5),
        },
        "suites": {
            "containerSuites": [
                "docker",
                "helm",
                "frontend",
                "manager",
                "operator",
                "identity",
                "platform-conformance",
                "kubernetes-hardening",
            ],
            "runs": [
                {
                    "name": name,
                    "command": _suite_command(name),
                    "locale": "none",
                    "exitCode": 0,
                    "startedAt": "2026-08-08T07:00:00Z",
                    "finishedAt": "2026-08-08T07:01:00Z",
                    "rawLogSha256": source_digest,
                    "projectName": _suite_project(name),
                    "cleanupCommand": _suite_cleanup(name),
                    "cleaned": True,
                    "runner": _suite_runner(name),
                    **(
                        {
                            "preflightCommand": [
                                *MODULE.HERMETIC_COMPOSE_ENVIRONMENT,
                                "docker",
                                "compose",
                                "--env-file",
                                f"{SUITE_SOURCE_ROOT}/.env.example",
                                "--project-name",
                                _suite_project(name),
                                "--file",
                                f"{SUITE_SOURCE_ROOT}/docker-compose.yml",
                                "config",
                                "--quiet",
                            ]
                        }
                        if name == "docker"
                        else {}
                    ),
                }
                for name in [
                    "docker",
                    "helm",
                    "frontend",
                    "manager",
                    "operator",
                    "identity",
                    "platform-conformance",
                    "kubernetes-hardening",
                ]
            ]
            + [
                {
                    "name": f"docs-{locale}",
                    "command": _suite_command(f"docs-{locale}"),
                    "locale": locale,
                    "exitCode": 0,
                    "startedAt": "2026-08-08T07:00:00Z",
                    "finishedAt": "2026-08-08T07:01:00Z",
                    "rawLogSha256": source_digest,
                    "linksVerified": True,
                    "projectName": _suite_project(f"docs-{locale}"),
                    "cleanupCommand": _suite_cleanup(f"docs-{locale}"),
                    "cleaned": True,
                    "runner": _suite_runner(f"docs-{locale}"),
                }
                for locale in ["zh-Hant", "en"]
            ],
            "releaseInputs": {
                "signedImageInventorySha256": "e" * 64,
            },
            "sourceProvenance": _source_provenance(tree_digest_checks=32),
        },
    }
    return values[section]


def _owner_reference(*, api_version: str, kind: str, name: str, uid: str) -> dict:
    return {
        "apiVersion": api_version,
        "kind": kind,
        "name": name,
        "uid": uid,
        "controller": True,
        "blockOwnerDeletion": True,
    }


def _soak_raw_documents(identity_mode: str) -> dict[str, dict]:
    def detached(value: object) -> object:
        return json.loads(json.dumps(value))

    def raw_list(items: list[dict]) -> dict:
        return {
            "apiVersion": "v1",
            "kind": "List",
            "items": detached(items),
        }

    def safe_hash(seed: str) -> str:
        alphabet = "bcdfghjklmnpqrstvwxz2456789"
        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        return "".join(alphabet[value % len(alphabet)] for value in digest[:10])

    def generated_name(generate_name: str) -> str:
        return f"{generate_name[:58]}{safe_hash(generate_name)[:5]}"

    def component_annotations(component: str) -> dict[str, str]:
        key = component.removeprefix("workspace-")
        component_spec = workspace_component_specs[key]
        annotations = {
            "aileron.io/component-revision": str(component_spec["revision"]),
            "aileron.io/component-instance-id": component_spec["instanceId"],
        }
        if key == "runtime":
            annotations.update(
                {
                    "aileron.io/runtime-instance-id": component_spec["instanceId"],
                    "aileron.io/runtime-access-revision": str(
                        component_spec["accessRevision"]
                    ),
                    "aileron.io/knowledge-base-mount-revision": str(
                        component_spec["mountRevision"]
                    ),
                }
            )
        elif key == "browser":
            annotations.update(
                {
                    "aileron.io/browser-credential-revision": str(
                        component_spec["credentialRevision"]
                    ),
                    "aileron.io/browser-credential-key-id": component_spec[
                        "credentialKeyId"
                    ],
                    "aileron.io/browser-credential-algorithm": component_spec[
                        "credentialAlgorithm"
                    ],
                }
            )
        return annotations

    workspace_name = "workspace-workspace-1"
    workspace_uid = "workspace-uid"
    workspace_owner = WORKSPACE["userSubject"]
    workspace_image_pull_secrets = [{"name": "workspace-registry"}]
    runtime_instance = "44444444-4444-4444-8444-444444444444"
    browser_instance = "55555555-5555-4555-8555-555555555555"
    canvas_instance = "66666666-6666-4666-8666-666666666666"
    workspace_component_specs = {
        "runtime": {
            "desiredState": "Running",
            "instanceId": runtime_instance,
            "revision": 11,
            "mountRevision": 12,
            "accessRevision": 13,
            "image": "registry.example/product@sha256:" + "1" * 64,
        },
        "browser": {
            "enabled": True,
            "desiredState": "Running",
            "instanceId": browser_instance,
            "revision": 21,
            "image": "registry.example/browser@sha256:" + "2" * 64,
            "credentialRevision": 22,
            "credentialKeyId": "browser-key-1",
            "credentialAlgorithm": "hkdf-sha256-v1",
        },
        "canvas": {
            "enabled": True,
            "desiredState": "Running",
            "instanceId": canvas_instance,
            "revision": 31,
            "image": "registry.example/canvas@sha256:" + "3" * 64,
        },
    }
    definitions = [
        (
            "Deployment",
            "aileron-identity-system",
            "aileron-identity-keycloak",
            "aileron-identity-keycloak",
            None,
        ),
        (
            "Deployment",
            "aileron-identity-system",
            "aileron-identity-postgres",
            "aileron-identity-postgres",
            None,
        ),
        ("DaemonSet", "aileron-turn-system", "aileron-coturn", "coturn", None),
        ("Deployment", "workspace-system", "aileron-frontend", "frontend", None),
        (
            "Deployment",
            "workspace-system",
            "aileron-workspace-manager",
            "workspace-manager",
            None,
        ),
        (
            "Deployment",
            "workspace-system",
            "aileron-workspace-operator",
            "workspace-operator",
            None,
        ),
        ("StatefulSet", "workspace-system", "aileron-postgres", "postgres", None),
        ("StatefulSet", "workspace-system", "aileron-redis", "redis", None),
        (
            "DaemonSet",
            "workspace-system",
            "aileron-workspace-firewall-attestor",
            "workspace-firewall-attestor",
            None,
        ),
        (
            "Deployment",
            "workspace-system",
            "aileron-connectivity-evidence-gateway",
            "connectivity-evidence-gateway",
            None,
        ),
        (
            "DaemonSet",
            "workspace-system",
            "aileron-connectivity-host-agent",
            "connectivity-external-agent",
            None,
        ),
        (
            "Deployment",
            "workspace-system",
            "workspace-runtime-workspace-1",
            "workspace-runtime",
            WORKSPACE["id"],
        ),
        (
            "Deployment",
            "workspace-system",
            "workspace-browser-workspace-1",
            "workspace-browser",
            WORKSPACE["id"],
        ),
        (
            "Deployment",
            "workspace-system",
            "workspace-canvas-workspace-1",
            "workspace-canvas",
            WORKSPACE["id"],
        ),
    ]
    if identity_mode == "externalOidc":
        definitions = [
            item for item in definitions if item[1] != "aileron-identity-system"
        ]
    controllers: list[dict] = []
    replica_sets: list[dict] = []
    controller_revisions: list[dict] = []
    pods: list[dict] = []
    workspace_service_selectors: dict[str, dict] = {}
    for (
        kind,
        namespace,
        name,
        component,
        workspace_id,
    ) in definitions:
        labels: dict[str, str]
        selector_labels: dict[str, str]
        template_labels: dict[str, str]
        if namespace == "aileron-identity-system":
            labels = {
                "app.kubernetes.io/part-of": "aileron-identity",
                "app.kubernetes.io/managed-by": "Helm",
                "helm.sh/chart": "aileron-identity-1.0.0",
            }
            selector_labels = {"app.kubernetes.io/name": name}
            template_labels = {
                **selector_labels,
                "app.kubernetes.io/part-of": "aileron-identity",
            }
        else:
            labels = {
                "helm.sh/chart": "aileron-1.0.0",
                "app.kubernetes.io/name": "aileron",
                "app.kubernetes.io/instance": "aileron",
                "app.kubernetes.io/version": "1.0.0",
                "app.kubernetes.io/managed-by": "Helm",
                "app.kubernetes.io/part-of": "aileron",
            }
            if component in {
                "coturn",
                "workspace-firewall-attestor",
                "connectivity-evidence-gateway",
                "connectivity-external-agent",
            }:
                labels["app.kubernetes.io/component"] = component
            selector_labels = {
                "app.kubernetes.io/name": "aileron",
                "app.kubernetes.io/instance": "aileron",
                "app.kubernetes.io/component": component,
            }
            template_labels = detached(selector_labels)
            if component not in {
                "connectivity-evidence-gateway",
                "connectivity-external-agent",
            }:
                template_labels["app.kubernetes.io/part-of"] = "aileron"
        if workspace_id is not None:
            labels = {
                "app.kubernetes.io/part-of": "aileron",
                "aileron.io/component": component,
                "aileron.io/firewall-group": (
                    "browser" if component == "workspace-browser" else "workspace"
                ),
                "aileron.io/owner-id": workspace_owner,
                "aileron.io/workspace-id": workspace_id,
            }
            selector_labels = detached(labels)
            template_labels = detached(labels)
        uid = f"{name}-uid"
        status = {"observedGeneration": 1}
        if component == "workspace-runtime":
            template_labels["aileron.io/runtime-instance-id"] = runtime_instance
        if workspace_id is not None:
            workspace_service_selectors[component] = detached(template_labels)
        template_container_name = {
            "workspace-runtime": "runtime",
            "workspace-browser": "browser",
            "workspace-canvas": "canvas",
        }.get(component, component)
        image = (
            workspace_component_specs[component.removeprefix("workspace-")]["image"]
            if workspace_id is not None
            else "registry.example/product@sha256:" + "1" * 64
        )
        template_container = {"name": template_container_name, "image": image}
        if component == "workspace-browser":
            template_container["readinessProbe"] = {
                "exec": {
                    "command": list(MODULE.ACCEPTANCE_SOAK.BROWSER_READINESS_COMMAND)
                },
                "periodSeconds": 5,
                "timeoutSeconds": 2,
                "failureThreshold": 3,
                "successThreshold": 1,
            }
        template_spec = {"containers": [template_container]}
        if workspace_id is not None:
            template_spec["serviceAccountName"] = (
                f"workspace-workload-{workspace_id}"
            )
        if component == "workspace-runtime":
            template_spec["initContainers"] = [
                {"name": "runtime-home-initializer", "image": image}
            ]
        if kind == "StatefulSet":
            template_spec["automountServiceAccountToken"] = False
            template_container["volumeMounts"] = [
                {"name": "data", "mountPath": "/data"}
            ]
        template_metadata = {
            "creationTimestamp": None,
            "labels": detached(template_labels),
        }
        annotations = (
            component_annotations(component) if workspace_id is not None else None
        )
        if annotations is not None:
            template_metadata["annotations"] = detached(annotations)
        spec = {
            "selector": {"matchLabels": detached(selector_labels)},
            "template": {
                "metadata": template_metadata,
                "spec": template_spec,
            },
        }
        if kind == "DaemonSet":
            status.update(
                {
                    "desiredNumberScheduled": 1,
                    "currentNumberScheduled": 1,
                    "numberMisscheduled": 0,
                    "numberReady": 1,
                    "updatedNumberScheduled": 1,
                    "numberAvailable": 1,
                    "numberUnavailable": 0,
                }
            )
        else:
            spec["replicas"] = 1
            if kind == "StatefulSet":
                spec["serviceName"] = name
                spec["volumeClaimTemplates"] = [
                    {
                        "metadata": {"name": "data"},
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {"requests": {"storage": "1Gi"}},
                        },
                    }
                ]
            status.update({"replicas": 1, "readyReplicas": 1, "availableReplicas": 1})
            if kind == "Deployment":
                status.update({"updatedReplicas": 1, "unavailableReplicas": 0})
            else:
                revision_hash = safe_hash(name)
                revision_name = f"{name}-{revision_hash}"
                status.update(
                    {
                        "currentReplicas": 1,
                        "updatedReplicas": 1,
                        "currentRevision": revision_name,
                        "updateRevision": revision_name,
                    }
                )
        controller = {
            "apiVersion": "apps/v1",
            "kind": kind,
            "metadata": {
                "name": name,
                "namespace": namespace,
                "uid": uid,
                "generation": 1,
                "labels": detached(labels),
            },
            "spec": spec,
            "status": status,
        }
        if workspace_id is not None:
            controller["metadata"]["annotations"] = detached(annotations)
            controller["metadata"]["ownerReferences"] = [
                _owner_reference(
                    api_version="platform.aileron.io/v1alpha1",
                    kind="Workspace",
                    name=workspace_name,
                    uid=workspace_uid,
                )
            ]
        controllers.append(controller)
        if kind in {"StatefulSet", "DaemonSet"}:
            revision_hash = safe_hash(name)
            revision_template = detached(spec["template"])
            revision_template["$patch"] = "replace"
            hash_label = (
                "controller.kubernetes.io/hash"
                if kind == "StatefulSet"
                else "controller-revision-hash"
            )
            controller_revisions.append(
                {
                    "apiVersion": "apps/v1",
                    "kind": "ControllerRevision",
                    "metadata": {
                        "name": f"{name}-{revision_hash}",
                        "namespace": namespace,
                        "uid": f"{name}-{revision_hash}-uid",
                        "labels": {
                            **detached(template_labels),
                            hash_label: revision_hash,
                        },
                        "ownerReferences": [
                            _owner_reference(
                                api_version="apps/v1",
                                kind=kind,
                                name=name,
                                uid=uid,
                            )
                        ],
                    },
                    "data": {"spec": {"template": revision_template}},
                    "revision": 1,
                }
            )
        pod_owner = controller
        pod_labels = detached(template_labels)
        if kind == "Deployment":
            pod_template_hash = safe_hash(name)
            replica_set_labels = {
                **detached(template_labels),
                "pod-template-hash": pod_template_hash,
            }
            replica_set_selector_labels = {
                **detached(selector_labels),
                "pod-template-hash": pod_template_hash,
            }
            replica_set_template_metadata = detached(spec["template"]["metadata"])
            replica_set_template_metadata["labels"] = detached(replica_set_labels)
            replica_set_name = f"{name}-{pod_template_hash}"
            replica_set = {
                "apiVersion": "apps/v1",
                "kind": "ReplicaSet",
                "metadata": {
                    "name": replica_set_name,
                    "namespace": namespace,
                    "uid": f"{replica_set_name}-uid",
                    "generation": 1,
                    "labels": detached(replica_set_labels),
                    "ownerReferences": [
                        _owner_reference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=name,
                            uid=uid,
                        )
                    ],
                },
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": detached(replica_set_selector_labels)},
                    "template": {
                        "metadata": replica_set_template_metadata,
                        "spec": detached(spec["template"]["spec"]),
                    },
                },
                "status": {
                    "observedGeneration": 1,
                    "replicas": 1,
                    "fullyLabeledReplicas": 1,
                    "readyReplicas": 1,
                    "availableReplicas": 1,
                },
            }
            replica_sets.append(replica_set)
            pod_owner = replica_set
            pod_labels = detached(replica_set_labels)
        pod_generate_name = f"{pod_owner['metadata']['name']}-"
        pod_name = generated_name(pod_generate_name)
        if kind == "StatefulSet":
            pod_name = f"{name}-0"
            pod_labels.update(
                {
                    "controller-revision-hash": status["currentRevision"],
                    "statefulset.kubernetes.io/pod-name": pod_name,
                    "apps.kubernetes.io/pod-index": "0",
                }
            )
        elif kind == "DaemonSet":
            pod_labels.update(
                {
                    "controller-revision-hash": safe_hash(name),
                    "pod-template-generation": str(
                        controller["metadata"]["generation"]
                    ),
                }
            )
        pod_spec = detached(pod_owner["spec"]["template"]["spec"])
        if workspace_id is not None:
            pod_spec["imagePullSecrets"] = detached(workspace_image_pull_secrets)
        if kind == "StatefulSet":
            pod_spec["hostname"] = pod_name
            pod_spec["subdomain"] = controller["spec"]["serviceName"]
            pod_spec.setdefault("volumes", []).append(
                {
                    "name": "data",
                    "persistentVolumeClaim": {"claimName": f"data-{pod_name}"},
                }
            )
        node_name = f"node-{name}"
        pod_spec["nodeName"] = node_name
        pod_spec["enableServiceLinks"] = True
        pod_ip_seed = hashlib.sha256(pod_name.encode("utf-8")).digest()
        pod_ip = f"10.42.{pod_ip_seed[0]}.{1 + pod_ip_seed[1] % 254}"
        host_ip_seed = hashlib.sha256(node_name.encode("utf-8")).digest()
        host_ip = f"192.0.2.{1 + host_ip_seed[0] % 254}"
        container_name = template_container_name
        container_spec = next(
            item for item in pod_spec["containers"] if item["name"] == container_name
        )
        image = container_spec["image"]
        pod_status = {
            "phase": "Running",
            "podIP": pod_ip,
            "podIPs": [{"ip": pod_ip}],
            "hostIP": host_ip,
            "hostIPs": [{"ip": host_ip}],
            "conditions": [{"type": "Ready", "status": "True"}],
            "containerStatuses": [
                {
                    "name": container_name,
                    "image": image,
                    "imageID": "docker-pullable://" + image,
                    "containerID": "containerd://"
                    + hashlib.sha256(name.encode()).hexdigest(),
                    "restartCount": 0,
                    "ready": True,
                    "started": True,
                    "state": {"running": {"startedAt": "2026-08-08T06:42:00Z"}},
                }
            ],
        }
        if component == "workspace-runtime":
            init_image = pod_spec["initContainers"][0]["image"]
            pod_status["initContainerStatuses"] = [
                {
                    "name": "runtime-home-initializer",
                    "image": init_image,
                    "imageID": "docker-pullable://" + init_image,
                    "containerID": "containerd://" + "b" * 64,
                    "restartCount": 0,
                    "ready": True,
                    "state": {
                        "terminated": {
                            "exitCode": 0,
                            "reason": "Completed",
                            "startedAt": "2026-08-08T06:41:00Z",
                            "finishedAt": "2026-08-08T06:41:30Z",
                        }
                    },
                }
            ]
        pod_metadata = {
            "name": pod_name,
            "generateName": pod_generate_name,
            "namespace": namespace,
            "uid": f"{pod_name}-uid",
            "labels": detached(pod_labels),
            "ownerReferences": [
                _owner_reference(
                    api_version="apps/v1",
                    kind=pod_owner["kind"],
                    name=pod_owner["metadata"]["name"],
                    uid=pod_owner["metadata"]["uid"],
                )
            ],
        }
        pod_annotations = pod_owner["spec"]["template"]["metadata"].get("annotations")
        if pod_annotations is not None:
            pod_metadata["annotations"] = detached(pod_annotations)
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": pod_metadata,
            "spec": pod_spec,
            "status": pod_status,
        }
        pods.append(pod)
    workspace_pod_uids = {
        key: next(
            pod["metadata"]["uid"]
            for pod in pods
            if pod["metadata"]["labels"].get("aileron.io/component")
            == f"workspace-{key}"
        )
        for key in ("runtime", "browser", "canvas")
    }
    workspace = {
        "apiVersion": "platform.aileron.io/v1alpha1",
        "kind": "Workspace",
        "metadata": {
            "name": workspace_name,
            "namespace": "workspace-system",
            "uid": workspace_uid,
            "generation": 4,
        },
        "spec": {
            "workspaceId": WORKSPACE["id"],
            "ownerId": workspace_owner,
            **detached(workspace_component_specs),
        },
        "status": {
            "observedGeneration": 4,
            "phase": "Running",
            "components": {
                "runtime": {
                    "observedInstanceId": runtime_instance,
                    "observedRevision": 11,
                    "phase": "Running",
                    "podUid": workspace_pod_uids["runtime"],
                    "ready": True,
                    "terminalReady": True,
                    "mountObservedRevision": 12,
                    "lastKnownGoodMountRevision": 12,
                    "accessObservedRevision": 13,
                },
                "browser": {
                    "observedInstanceId": browser_instance,
                    "observedRevision": 21,
                    "phase": "Running",
                    "podUid": workspace_pod_uids["browser"],
                    "ready": True,
                    "credentialObservedRevision": 22,
                    "credentialObservedKeyId": "browser-key-1",
                    "credentialObservedAlgorithm": "hkdf-sha256-v1",
                },
                "canvas": {
                    "observedInstanceId": canvas_instance,
                    "observedRevision": 31,
                    "phase": "Running",
                    "podUid": workspace_pod_uids["canvas"],
                    "ready": True,
                },
            },
        },
    }
    workspace_service_account_name = f"workspace-workload-{WORKSPACE['id']}"
    workspace_service_accounts = [
        {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": workspace_service_account_name,
                "namespace": "workspace-system",
                "uid": f"{workspace_service_account_name}-uid",
                "labels": {
                    "app.kubernetes.io/part-of": "aileron",
                    "aileron.io/workspace-id": WORKSPACE["id"],
                    "aileron.io/owner-id": workspace_owner,
                    "aileron.io/component": "workspace-workload",
                    "aileron.io/firewall-group": "workspace",
                },
                "ownerReferences": [
                    _owner_reference(
                        api_version="platform.aileron.io/v1alpha1",
                        kind="Workspace",
                        name=workspace_name,
                        uid=workspace_uid,
                    )
                ],
            },
            "automountServiceAccountToken": False,
            "imagePullSecrets": detached(workspace_image_pull_secrets),
        }
    ]
    service_ports = {
        "runtime": [
            {"name": "http", "port": 3002, "protocol": "TCP", "targetPort": 3002},
            {
                "name": "terminal",
                "port": 3004,
                "protocol": "TCP",
                "targetPort": 3004,
            },
        ],
        "browser": [
            {
                "name": "webrtc",
                "port": 6080,
                "protocol": "TCP",
                "targetPort": 6080,
            },
            {"name": "cdp", "port": 9223, "protocol": "TCP", "targetPort": 9223},
            {
                "name": "connectivity-evidence",
                "port": 8082,
                "protocol": "TCP",
                "targetPort": 8082,
            },
        ],
        "canvas": [
            {"name": "http", "port": 3003, "protocol": "TCP", "targetPort": 3003},
            {"name": "api", "port": 3013, "protocol": "TCP", "targetPort": 3013},
        ],
    }
    services: list[dict] = []
    endpoint_slices: list[dict] = []
    for service_index, component in enumerate(
        MODULE.ACCEPTANCE_SOAK.SERVICE_COMPONENTS
    ):
        workload_component = f"workspace-{component}"
        service_labels = {
            "app.kubernetes.io/part-of": "aileron",
            "aileron.io/workspace-id": WORKSPACE["id"],
            "aileron.io/owner-id": workspace_owner,
            "aileron.io/component": workload_component,
            "aileron.io/firewall-group": (
                "browser" if component == "browser" else "workspace"
            ),
        }
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": f"workspace-{component}-workspace-1",
                "namespace": "workspace-system",
                "uid": f"{component}-service-uid",
                "labels": detached(service_labels),
                "ownerReferences": [
                    _owner_reference(
                        api_version="platform.aileron.io/v1alpha1",
                        kind="Workspace",
                        name=workspace_name,
                        uid=workspace_uid,
                    )
                ],
            },
            "spec": {
                "type": "ClusterIP",
                "clusterIP": f"10.43.1.{10 + service_index}",
                "clusterIPs": [f"10.43.1.{10 + service_index}"],
                "internalTrafficPolicy": "Cluster",
                "ipFamilies": ["IPv4"],
                "ipFamilyPolicy": "SingleStack",
                "ports": detached(service_ports[component]),
                "selector": detached(workspace_service_selectors[workload_component]),
                "sessionAffinity": "None",
            },
        }
        services.append(service)
        selected_pods = [
            pod
            for pod in pods
            if pod["metadata"]["namespace"] == service["metadata"]["namespace"]
            and all(
                pod["metadata"]["labels"].get(key) == value
                for key, value in service["spec"]["selector"].items()
            )
        ]
        assert len(selected_pods) == 1
        selected_pod = selected_pods[0]
        endpoint_slice_prefix = f"{service['metadata']['name']}-"
        endpoint_slice_name = (
            f"{endpoint_slice_prefix}{safe_hash(service['metadata']['uid'])[:5]}"
        )
        endpoint_slices.append(
            {
                "apiVersion": "discovery.k8s.io/v1",
                "kind": "EndpointSlice",
                "metadata": {
                    "name": endpoint_slice_name,
                    "generateName": endpoint_slice_prefix,
                    "namespace": service["metadata"]["namespace"],
                    "uid": f"{endpoint_slice_name}-uid",
                    "labels": {
                        **detached(service["metadata"]["labels"]),
                        "kubernetes.io/service-name": service["metadata"]["name"],
                        "endpointslice.kubernetes.io/managed-by": (
                            "endpointslice-controller.k8s.io"
                        ),
                    },
                    "ownerReferences": [
                        _owner_reference(
                            api_version="v1",
                            kind="Service",
                            name=service["metadata"]["name"],
                            uid=service["metadata"]["uid"],
                        )
                    ],
                },
                "addressType": "IPv4",
                "ports": [
                    {
                        "name": port["name"],
                        "port": port["targetPort"],
                        "protocol": port["protocol"],
                    }
                    for port in service["spec"]["ports"]
                ],
                "endpoints": [
                    {
                        "addresses": [selected_pod["status"]["podIP"]],
                        "conditions": {
                            "ready": True,
                            "serving": True,
                            "terminating": False,
                        },
                        "nodeName": selected_pod["spec"]["nodeName"],
                        "targetRef": {
                            "kind": "Pod",
                            "namespace": selected_pod["metadata"]["namespace"],
                            "name": selected_pod["metadata"]["name"],
                            "uid": selected_pod["metadata"]["uid"],
                        },
                    }
                ],
            }
        )
    pod_documents = {
        "identityPods": raw_list(
            [
                pod
                for pod in pods
                if pod["metadata"]["namespace"] == "aileron-identity-system"
            ]
        ),
        "turnPods": raw_list(
            [
                pod
                for pod in pods
                if pod["metadata"]["namespace"] == "aileron-turn-system"
            ]
        ),
        "workspacePods": raw_list(
            [pod for pod in pods if pod["metadata"]["namespace"] == "workspace-system"]
        ),
    }
    browser_pod = next(
        pod
        for pod in pods
        if pod["metadata"]["labels"].get("aileron.io/component") == "workspace-browser"
    )
    return {
        **pod_documents,
        "workspace": raw_list([workspace]),
        "workspaceServiceAccounts": raw_list(workspace_service_accounts),
        "services": raw_list(services),
        "endpointSlices": raw_list(endpoint_slices),
        "browserPods": raw_list([browser_pod]),
        "controllers": raw_list([*controllers, *replica_sets, *controller_revisions]),
    }


def _signed_soak_images() -> list[dict[str, str]]:
    required_indexes = [
        "registry.example/product@sha256:" + "1" * 64,
        "registry.example/browser@sha256:" + "2" * 64,
        "registry.example/canvas@sha256:" + "3" * 64,
    ]
    images: list[dict[str, str]] = []
    for index, component in enumerate(IMAGE_COMPONENTS):
        immutable_image = (
            required_indexes[index]
            if index < len(required_indexes)
            else f"registry.example/{component}@sha256:{index + 1:064x}"
        )
        repository = immutable_image.rsplit("@", 1)[0]
        images.append(
            {
                "component": component,
                "revision": COMMIT,
                "platform": "linux/amd64",
                "taggedImage": f"{repository}:git-{COMMIT}",
                "immutableImage": immutable_image,
                "runtimeImmutableImage": (f"{repository}@sha256:{index + 101:064x}"),
            }
        )
    return images


def _canonical(document: dict) -> bytes:
    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode()


def _raw_json_variant(
    document: dict, canonical_raw: bytes, variant: str, duplicate_key: str
) -> bytes:
    if variant == "duplicate":
        return (
            b"{"
            + json.dumps(duplicate_key).encode()
            + b":"
            + json.dumps(document[duplicate_key], separators=(",", ":")).encode()
            + b","
            + canonical_raw[1:]
        )
    if variant == "whitespace":
        return json.dumps(document, indent=2, sort_keys=True).encode() + b"\n"
    if variant == "order":
        return (
            json.dumps(
                dict(reversed(list(document.items()))),
                separators=(",", ":"),
            ).encode()
            + b"\n"
        )
    if variant == "missing-newline":
        return canonical_raw.removesuffix(b"\n")
    return b'{"bad":"\xff"}\n'


def _backend_attestor_binding() -> dict:
    canonical_profile = _canonical(BACKEND_PROFILE)
    return {
        "schemaVersion": "aileron-backend-attestor-snapshot-binding/v1",
        "executionProfile": {
            "schemaVersion": "aileron-backend-execution-profile-binding/v1",
            "rawSha256": hashlib.sha256(canonical_profile + b"\n").hexdigest(),
            "canonicalSha256": hashlib.sha256(canonical_profile).hexdigest(),
            "profile": BACKEND_PROFILE,
        },
        "executionResources": {
            "schemaVersion": "aileron-backend-execution-resources-binding/v1",
            "namespace": {
                "name": "aileron-backend-attestor-system",
                "uid": "namespace-uid",
                "owner": "aileron-installer",
                "phase": "Active",
                "podSecurityLabels": {
                    "pod-security.kubernetes.io/enforce": "privileged",
                    "pod-security.kubernetes.io/audit": "restricted",
                    "pod-security.kubernetes.io/warn": "restricted",
                },
            },
            "imagePullSecret": {
                "namespace": "aileron-backend-attestor-system",
                "name": "harbor-rke-creds",
                "uid": "secret-uid",
                "owner": "aileron-installer",
                "dataKeys": [".dockerconfigjson"],
                "dataSha256": "c" * 64,
            },
        },
        "imageInventorySha256": "d" * 64,
    }


def _evidence(
    tmp_path: Path, authentication_mode: str = "bundledKeycloak"
) -> tuple[Path, Path]:
    contract = json.loads(CONTRACT.read_text())
    key_path = _key(tmp_path)
    signed_images = _signed_soak_images()
    install_root = tmp_path / "install"
    install_root.mkdir(mode=0o700)
    install_directory = install_root / COMMIT
    install_directory.mkdir(mode=0o700)
    MODULE.ACCEPTANCE_RELEASE.write_signed_image_inventory(
        path=install_directory / "signed-image-inventory.json",
        private_root=tmp_path,
        images=signed_images,
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
    )
    image_runtime_pairs = MODULE.ACCEPTANCE_SOAK.release_image_runtime_pairs(
        signed_images
    )
    evidence_directory = MODULE.PRIVATE_IO.ensure_evidence_directory(
        private_root=tmp_path,
        commit=COMMIT,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        error_type=MODULE.AcceptanceEvidenceError,
    )
    for name in ("kubeconfig.raw", "kubeconfig"):
        kubeconfig_snapshot = evidence_directory / name
        kubeconfig_snapshot.write_bytes(_canonical_kubeconfig_bytes())
        kubeconfig_snapshot.chmod(0o600)
    snapshot_path = MODULE.ACCEPTANCE_SNAPSHOT.write_reset_snapshot(
        directory=evidence_directory,
        private_root=tmp_path,
        inventory={
            "context": "rke2-homelab",
            "namespaces": [
                {"name": "aileron-identity-system"},
                {"name": "aileron-turn-system"},
                {"name": "workspace-system"},
            ],
            "releases": [],
            "resources": [
                {
                    "apiVersion": "platform.aileron.io/v1alpha1",
                    "kind": "Workspace",
                    "namespace": "workspace-system",
                    "name": "workspace-1",
                },
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolumeClaim",
                    "namespace": "workspace-system",
                    "name": "data-workspace-1",
                },
            ],
            "persistentVolumes": [
                {
                    "apiVersion": "v1",
                    "kind": "PersistentVolume",
                    "name": "pv-1",
                    "uid": "pv-1-uid",
                    "backendLocator": RESET_BACKEND_LOCATOR,
                }
            ],
        },
        key=KEY,
        context="rke2-homelab",
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        installation_identity_sha256=IDENTITY_DIGEST,
        run_id=DEPLOYMENT_RUN_ID,
        backend_attestor=_backend_attestor_binding(),
        created_at=datetime(2026, 8, 8, 6, 0, tzinfo=UTC),
    )
    reset_snapshot_sha256 = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    epoch_path = MODULE.ACCEPTANCE_EPOCH.write_deployment_epoch(
        directory=evidence_directory,
        private_root=tmp_path,
        key=KEY,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        commit=COMMIT,
        cluster_uid=CLUSTER_UID,
        context="rke2-homelab",
        installation_identity_sha256=IDENTITY_DIGEST,
        authentication_mode=authentication_mode,
        reset_snapshot_sha256=reset_snapshot_sha256,
        created_at=datetime(2026, 8, 8, 6, 1, tzinfo=UTC),
    )
    reports = {}
    required = MODULE.required_reports_for_mode(contract, authentication_mode)
    for section in required:
        source_path = evidence_directory / f"{section}.raw.log"
        source_path.write_text(f"raw {section} probe output\n", encoding="utf-8")
        source_path.chmod(0o600)
        source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
        command = ["probe", section]
        if section in {
            "oidcWorkspace",
            "workspaceLifecycle",
            "adminDisableLogin",
            "terminal",
            "http",
            "browser",
            "websocket",
        }:
            command = [
                "docker",
                "run",
                "--rm",
                BROWSER_IMAGE_ID,
                "node",
                "/app/e2e/acceptance.mjs",
                "--section",
                section,
            ]
            if section in {"terminal", "http", "browser", "websocket"}:
                command.extend(["--workspace-id", WORKSPACE["id"]])
            if section == "workspaceLifecycle":
                command.extend(["--workspace-id", WORKSPACE["id"]])
        elif section == "offlineOidcConformance":
            command = _suite_command("platform-conformance", OFFLINE_SOURCE_ROOT)
        sources = [
            {
                "file": source_path.name,
                "sha256": source_digest,
                "command": command,
                "exitCode": 0,
            }
        ]
        if section in {
            "oidcWorkspace",
            "workspaceLifecycle",
            "adminDisableLogin",
            "terminal",
            "http",
            "browser",
            "websocket",
        }:
            image_tag = f"ailerondocker/workspace-ui-playwright:{COMMIT}-123456789abc"
            provenance_commands = [
                [
                    "docker",
                    "build",
                    "--file",
                    "frontend/Dockerfile.playwright",
                    "--tag",
                    image_tag,
                    "--label",
                    f"org.opencontainers.image.revision={COMMIT}",
                    "--pull=false",
                    "frontend",
                ],
                [
                    "docker",
                    "image",
                    "inspect",
                    '--format={{.Id}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
                    image_tag,
                ],
                [
                    "docker",
                    "image",
                    "tag",
                    BROWSER_IMAGE_ID,
                    f"ailerondocker/workspace-ui-playwright:{COMMIT}",
                ],
                [
                    "docker",
                    "image",
                    "rm",
                    "--force",
                    image_tag,
                ],
            ]
            for index, provenance_command in enumerate(provenance_commands):
                provenance_path = (
                    evidence_directory / f"{section}.provenance-{index}.log"
                )
                provenance_path.write_text(
                    f"browser provenance {section} {index}\n", encoding="utf-8"
                )
                provenance_path.chmod(0o600)
                sources.append(
                    {
                        "file": provenance_path.name,
                        "sha256": hashlib.sha256(
                            provenance_path.read_bytes()
                        ).hexdigest(),
                        "command": provenance_command,
                        "exitCode": 0,
                    }
                )
            exact_source_commands = [
                ["git", "show", f"{COMMIT}:frontend/e2e/acceptance.mjs"],
                [
                    "docker",
                    "run",
                    "--rm",
                    "--entrypoint",
                    "node",
                    BROWSER_IMAGE_ID,
                    "-e",
                    (
                        'process.stdout.write(require("node:fs").readFileSync('
                        '"/app/e2e/acceptance.mjs"))'
                    ),
                ],
            ]
            for index, exact_source_command in enumerate(exact_source_commands):
                exact_path = evidence_directory / f"{section}.exact-source-{index}.mjs"
                exact_path.write_bytes(BROWSER_SCRIPT_BYTES)
                exact_path.chmod(0o600)
                sources.append(
                    {
                        "file": exact_path.name,
                        "sha256": BROWSER_SCRIPT_DIGEST,
                        "command": exact_source_command,
                        "exitCode": 0,
                    }
                )
        if section == "soak":
            soak_attempt_id = "run-soak-fixture"
            soak_documents = _soak_raw_documents(authentication_mode)
            soak_commands = MODULE.ACCEPTANCE_SOAK.build_query_commands(
                kubeconfig=str(evidence_directory / "kubeconfig"),
                context="rke2-homelab",
                workspace_id=WORKSPACE["id"],
                identity_mode=authentication_mode,
            )
            sources = []
            soak_bindings = []
            for sample_index in range(31):
                sample_bindings = []
                for query_id, soak_command in soak_commands.items():
                    soak_source_path = evidence_directory / (
                        f"soak-{soak_attempt_id}-{sample_index:04d}-{query_id}.json"
                    )
                    soak_source_path.write_bytes(
                        json.dumps(
                            soak_documents[query_id],
                            separators=(",", ":"),
                            sort_keys=True,
                        ).encode()
                        + b"\n"
                    )
                    soak_source_path.chmod(0o600)
                    digest = hashlib.sha256(soak_source_path.read_bytes()).hexdigest()
                    source = {
                        "file": soak_source_path.name,
                        "sha256": digest,
                        "command": soak_command,
                        "exitCode": 0,
                        "attemptId": soak_attempt_id,
                        "sampleSequence": sample_index,
                        "queryId": query_id,
                    }
                    sources.append(source)
                    sample_bindings.append(
                        {"queryId": query_id, "file": source["file"], "sha256": digest}
                    )
                soak_bindings.append(sample_bindings)
        if section == "cleanReset":
            for filename, content in (
                (CLEANUP_SOURCE_FILE, CLEANUP_SOURCE_BYTES),
                (POST_RESET_SOURCE_FILE, POST_RESET_SOURCE_BYTES),
            ):
                backend_source_path = evidence_directory / filename
                backend_source_path.write_bytes(content)
                backend_source_path.chmod(0o600)
                sources.append(
                    {
                        "file": filename,
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "command": ["probe", section, filename],
                        "exitCode": 0,
                    }
                )
        observations = _observations(section, source_digest, reset_snapshot_sha256)
        if section == "soak":
            observations = {
                "identityMode": authentication_mode,
                "mutationMode": "read-only",
                "monotonicDurationMilliseconds": 1_800_000,
                "attemptId": soak_attempt_id,
                "baseline": MODULE.ACCEPTANCE_SOAK.snapshot_sample(
                    soak_documents,
                    workspace_id=WORKSPACE["id"],
                    identity_mode=authentication_mode,
                    commit=COMMIT,
                    deployment_run_id=DEPLOYMENT_RUN_ID,
                    image_runtime_pairs=image_runtime_pairs,
                ),
                "samples": [
                    {
                        "sequence": index,
                        "observedAt": (
                            datetime(2026, 8, 8, 6, 43, tzinfo=UTC)
                            + timedelta(seconds=60 * index)
                        )
                        .isoformat(timespec="seconds")
                        .replace("+00:00", "Z"),
                        "elapsedMilliseconds": 60_000 * index,
                        "queryBindings": bindings,
                    }
                    for index, bindings in enumerate(soak_bindings)
                ],
            }
        if section == "offlineOidcConformance":
            archive_path = evidence_directory / "offline-source-archive.tar.gz"
            archive_path.write_bytes(SOURCE_ARCHIVE_BYTES)
            archive_path.chmod(0o600)
            sources.insert(
                0,
                {
                    "file": archive_path.name,
                    "sha256": SOURCE_ARCHIVE_DIGEST,
                    "command": observations["sourceProvenance"]["archiveCommand"],
                    "exitCode": 0,
                },
            )
        if section == "suites":
            archive_path = evidence_directory / "suites-source-archive.tar.gz"
            archive_path.write_bytes(SOURCE_ARCHIVE_BYTES)
            archive_path.chmod(0o600)
            sources = [
                {
                    "file": archive_path.name,
                    "sha256": SOURCE_ARCHIVE_DIGEST,
                    "command": observations["sourceProvenance"]["archiveCommand"],
                    "exitCode": 0,
                }
            ]
            for index, run in enumerate(observations["runs"]):
                log_path = evidence_directory / f"suite-{index}.raw.log"
                log_path.write_text(f"unique suite log {index}\n", encoding="utf-8")
                log_path.chmod(0o600)
                digest = hashlib.sha256(log_path.read_bytes()).hexdigest()
                run["rawLogSha256"] = digest
                sources.append(
                    {
                        "file": log_path.name,
                        "sha256": digest,
                        "command": run["command"],
                        "exitCode": 0,
                    }
                )
        intervals = {
            "suites": ("2026-08-08T06:02:00Z", "2026-08-08T06:04:00Z"),
            "offlineOidcConformance": (
                "2026-08-08T06:02:00Z",
                "2026-08-08T06:04:00Z",
            ),
            "cleanReset": ("2026-08-08T06:05:00Z", "2026-08-08T06:10:00Z"),
            "imageRelease": ("2026-08-08T06:11:00Z", "2026-08-08T06:15:00Z"),
            "identity": ("2026-08-08T06:16:00Z", "2026-08-08T06:20:00Z"),
            "oidcWorkspace": ("2026-08-08T06:21:00Z", "2026-08-08T06:30:00Z"),
            "terminal": ("2026-08-08T06:31:00Z", "2026-08-08T06:35:00Z"),
            "http": ("2026-08-08T06:31:00Z", "2026-08-08T06:35:00Z"),
            "browser": ("2026-08-08T06:31:00Z", "2026-08-08T06:35:00Z"),
            "websocket": ("2026-08-08T06:31:00Z", "2026-08-08T06:35:00Z"),
            "turn": ("2026-08-08T06:31:00Z", "2026-08-08T06:35:00Z"),
            "workspaceLifecycle": ("2026-08-08T06:36:00Z", "2026-08-08T06:40:00Z"),
            "restart": ("2026-08-08T06:41:00Z", "2026-08-08T06:42:00Z"),
            "soak": ("2026-08-08T06:43:00Z", "2026-08-08T07:13:00Z"),
            "adminDisableLogin": ("2026-08-08T07:15:00Z", "2026-08-08T07:16:00Z"),
        }
        started_at, finished_at = intervals[section]
        report = {
            "schemaVersion": "aileron-acceptance-report/v9",
            "section": section,
            "commit": COMMIT,
            "deploymentRunId": DEPLOYMENT_RUN_ID,
            "authenticationMode": authentication_mode,
            "startedAt": started_at,
            "finishedAt": finished_at,
            "producer": {
                "id": contract["requiredProducers"][section],
                "executable": "scripts/deploy/rke2/acceptance_producer.py",
                "version": "6",
            },
            "probe": {
                "id": f"homelab-{section}",
                "kind": (
                    "offline"
                    if section == "offlineOidcConformance"
                    else "container"
                    if section == "suites"
                    else "live"
                ),
            },
            "sources": sources,
            "observations": observations,
        }
        if section in contract["workspaceScopedReports"]:
            report["workspace"] = WORKSPACE
        report["signature"] = hmac.new(
            KEY, _canonical(report), hashlib.sha256
        ).hexdigest()
        raw = _canonical(report) + b"\n"
        report_path = evidence_directory / f"{section}.json"
        report_path.write_bytes(raw)
        report_path.chmod(0o600)
        reports[section] = {
            "file": report_path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    bundle = {
        "contractVersion": "aileron-homelab-acceptance/v11",
        "commit": COMMIT,
        "deploymentRunId": DEPLOYMENT_RUN_ID,
        "authenticationMode": authentication_mode,
        "workspace": WORKSPACE,
        "epoch": {
            "file": epoch_path.name,
            "sha256": hashlib.sha256(epoch_path.read_bytes()).hexdigest(),
        },
        "reports": reports,
    }
    bundle_path = evidence_directory / MODULE.DEFAULT_BUNDLE_NAME
    bundle_path.write_bytes(_canonical(bundle) + b"\n")
    bundle_path.chmod(0o600)
    return bundle_path, key_path


def _validate(tmp_path: Path) -> None:
    _bundle, _ = _evidence(tmp_path)
    MODULE.validate_evidence(
        COMMIT,
        DEPLOYMENT_RUN_ID,
        CONTRACT,
        **_cluster_kwargs(tmp_path),
    )


def _build_code_owned_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authentication_mode: str,
) -> Path:
    tmp_path.chmod(0o700)
    manual_bundle, _ = _evidence(tmp_path, authentication_mode)
    manual_bundle.unlink()
    original_validator = BUNDLE.EVIDENCE.validate_evidence

    def validate_at_fixture_time(*args, **kwargs) -> None:
        original_validator(*args, **kwargs, now=NOW)

    monkeypatch.setattr(BUNDLE.EVIDENCE, "validate_evidence", validate_at_fixture_time)
    return BUNDLE.build_bundle(
        expected_commit=COMMIT,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        contract_path=CONTRACT,
        context="rke2-homelab",
        runner=ClusterRunner(),
    )


def test_cli_has_no_signing_key_or_key_path() -> None:
    parser = MODULE.build_parser()
    destinations = {action.dest for action in parser._actions}
    assert "signing_key" not in destinations
    assert "key" not in destinations
    assert "contract" not in destinations
    assert "context" in destinations
    assert "kubeconfig" not in destinations
    bundle_destinations = {action.dest for action in BUNDLE.build_parser()._actions}
    assert "context" in bundle_destinations
    assert "kubeconfig" not in bundle_destinations


def test_cluster_runner_routes_exact_namespace_and_secret_object_queries() -> None:
    runner = ClusterRunner()
    command_prefix = [
        "kubectl",
        "--kubeconfig",
        "/private/kubeconfig",
        "--context",
        "rke2-homelab",
    ]
    namespace = MODULE.ACCEPTANCE_CLUSTER.NAMESPACE_CONTRACT.validate_namespace_json(
        runner(
            [
                *command_prefix,
                "get",
                "namespace",
                "aileron-acceptance-system",
                "--output=json",
            ]
        ),
        namespace="aileron-acceptance-system",
        require_canonical_uid=True,
    )
    secret = json.loads(
        runner(
            [
                *command_prefix,
                "--namespace",
                "aileron-acceptance-system",
                "get",
                "secret",
                "aileron-acceptance-signing",
                "--output=json",
            ]
        )
    )

    assert namespace.uid == ACCEPTANCE_NAMESPACE_UID
    assert secret["kind"] == "Secret"
    with pytest.raises(AssertionError, match="unexpected cluster fixture command"):
        runner(
            [
                *command_prefix,
                "get",
                "namespace",
                "aileron-acceptance-system",
                "--output=jsonpath={.metadata.labels}",
            ]
        )


def test_alternate_self_consistent_contract_cannot_weaken_canonical_policy(
    tmp_path: Path,
) -> None:
    _bundle, _ = _evidence(tmp_path)
    weakened = json.loads(CONTRACT.read_text())
    weakened["commonRequiredReports"] = ["cleanReset"]
    alternate = tmp_path / "weakened-contract.json"
    alternate.write_text(json.dumps(weakened), encoding="utf-8")

    with pytest.raises(
        MODULE.AcceptanceEvidenceError, match="tracked canonical policy"
    ):
        MODULE.validate_evidence(
            COMMIT,
            DEPLOYMENT_RUN_ID,
            alternate,
            **_cluster_kwargs(tmp_path),
        )


@pytest.mark.parametrize("mutation", ["cycle", "orphan"])
def test_contract_graph_rejects_cycles_and_orphans(mutation: str) -> None:
    contract = json.loads(CONTRACT.read_text())
    if mutation == "cycle":
        contract["causalEdges"].append(["soak", "imageRelease"])
    else:
        contract["causalEdges"].remove(["suites", "cleanReset"])

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="causal graph"):
        MODULE.required_reports_for_mode(contract, "bundledKeycloak")


def test_contract_v11_pins_production_soak_policy() -> None:
    contract = json.loads(CONTRACT.read_text())

    assert hashlib.sha256(CONTRACT.read_bytes()).hexdigest() == (
        MODULE.CANONICAL_CONTRACT_SHA256
    )
    assert contract["contractVersion"] == "aileron-homelab-acceptance/v11"
    assert contract["reportSchemaVersion"] == "aileron-acceptance-report/v9"
    assert contract["producerVersion"] == "6"
    assert contract["minimumSoakSeconds"] == 1800
    assert contract["soakSampleIntervalSeconds"] == 60
    assert contract["maximumSoakSampleGapSeconds"] == 75
    assert contract["minimumSoakSamples"] == 31
    assert contract["maximumSoakClockDriftMilliseconds"] == 2000
    assert contract["causalRoots"] == ["suites", "offlineOidcConformance"]
    assert contract["causalEdges"] == [
        ["suites", "cleanReset"],
        ["offlineOidcConformance", "cleanReset"],
        ["cleanReset", "imageRelease"],
        ["imageRelease", "identity"],
        ["imageRelease", "oidcWorkspace"],
        ["identity", "oidcWorkspace"],
        ["oidcWorkspace", "terminal"],
        ["oidcWorkspace", "http"],
        ["oidcWorkspace", "browser"],
        ["oidcWorkspace", "websocket"],
        ["oidcWorkspace", "turn"],
        ["terminal", "workspaceLifecycle"],
        ["http", "workspaceLifecycle"],
        ["browser", "workspaceLifecycle"],
        ["websocket", "workspaceLifecycle"],
        ["turn", "workspaceLifecycle"],
        ["workspaceLifecycle", "restart"],
        ["restart", "soak"],
        ["soak", "adminDisableLogin"],
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("minimumSoakSeconds", 1799),
        ("soakSampleIntervalSeconds", 61),
        ("maximumSoakSampleGapSeconds", 76),
        ("minimumSoakSamples", 30),
    ],
)
def test_contract_v11_rejects_weakened_soak_policy(field: str, value: int) -> None:
    contract = json.loads(CONTRACT.read_text())
    contract[field] = value

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="unsupported"):
        MODULE.required_reports_for_mode(contract, "bundledKeycloak")


def test_active_v11_immediate_predecessors_are_mode_specific() -> None:
    contract = MODULE.load_canonical_contract(CONTRACT)
    common = {
        "suites": (),
        "offlineOidcConformance": (),
        "cleanReset": ("suites", "offlineOidcConformance"),
        "imageRelease": ("cleanReset",),
        "oidcWorkspace": ("imageRelease",),
        "terminal": ("oidcWorkspace",),
        "http": ("oidcWorkspace",),
        "browser": ("oidcWorkspace",),
        "websocket": ("oidcWorkspace",),
        "turn": ("oidcWorkspace",),
        "workspaceLifecycle": (
            "terminal",
            "http",
            "browser",
            "websocket",
            "turn",
        ),
        "restart": ("workspaceLifecycle",),
        "soak": ("restart",),
    }
    bundled = {
        **common,
        "identity": ("imageRelease",),
        "oidcWorkspace": ("imageRelease", "identity"),
        "adminDisableLogin": ("soak",),
    }

    assert {
        section: MODULE.immediate_predecessors(contract, section, "bundledKeycloak")
        for section in bundled
    } == bundled
    assert {
        section: MODULE.immediate_predecessors(contract, section, "externalOidc")
        for section in common
    } == common

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="not active"):
        MODULE.immediate_predecessors(contract, "adminDisableLogin", "externalOidc")


@pytest.mark.parametrize(
    "mutation",
    ("missing", "cross-run", "bad-hmac", "source", "observation"),
)
def test_single_report_validator_rejects_untrusted_causal_root(
    tmp_path: Path,
    mutation: str,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    directory = bundle_path.parent
    report_path = directory / "suites.json"
    report = json.loads(report_path.read_text())

    if mutation == "missing":
        report_path.unlink()
    elif mutation == "source":
        source_path = directory / report["sources"][1]["file"]
        source_path.write_bytes(source_path.read_bytes() + b"tampered\n")
    else:
        if mutation == "cross-run":
            report["deploymentRunId"] = "run-cross-run"
        elif mutation == "bad-hmac":
            report["signature"] = "0" * 64
        else:
            report["observations"]["runs"][0]["exitCode"] = 1
        if mutation != "bad-hmac":
            unsigned = dict(report)
            unsigned.pop("signature")
            report["signature"] = hmac.new(
                KEY, _canonical(unsigned), hashlib.sha256
            ).hexdigest()
        report_path.write_bytes(_canonical(report) + b"\n")

    epoch = json.loads((directory / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME).read_text())
    with pytest.raises(MODULE.AcceptanceEvidenceError):
        MODULE.validate_report_file(
            directory=directory,
            section="suites",
            contract=MODULE.load_canonical_contract(CONTRACT),
            expected_commit=COMMIT,
            epoch=epoch,
            signing_key=KEY,
            private_root=tmp_path,
            canonical_kubeconfig=directory / "kubeconfig",
            now=NOW,
        )


def test_single_report_validator_accepts_trusted_causal_root(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    directory = bundle_path.parent
    epoch = json.loads((directory / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME).read_text())

    validated = MODULE.validate_report_file(
        directory=directory,
        section="suites",
        contract=MODULE.load_canonical_contract(CONTRACT),
        expected_commit=COMMIT,
        epoch=epoch,
        signing_key=KEY,
        private_root=tmp_path,
        canonical_kubeconfig=directory / "kubeconfig",
        now=NOW,
    )

    assert validated["path"] == directory / "suites.json"
    assert validated["finishedAt"] == "2026-08-08T06:04:00Z"
    assert (
        validated["sha256"]
        == hashlib.sha256(validated["path"].read_bytes()).hexdigest()
    )


@pytest.mark.parametrize("attack", ["legacy-single-digest", "runtime-mismatch"])
def test_image_release_report_requires_the_exact_signed_runtime_pair(
    tmp_path: Path,
    attack: str,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    directory = bundle_path.parent
    report_path = directory / "imageRelease.json"
    report = json.loads(report_path.read_text())
    image = report["observations"]["images"][0]
    if attack == "legacy-single-digest":
        report["observations"]["images"][0] = {
            "component": image["component"],
            "platform": image["platform"],
            "revision": image["revision"],
            "digest": image["immutableImage"].rsplit("@", 1)[1],
        }
    else:
        image["runtimeImmutableImage"] = "registry.example/foreign@sha256:" + "f" * 64
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    report_path.write_bytes(_canonical(report) + b"\n")
    epoch = json.loads((directory / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME).read_text())

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="signed image inventory",
    ):
        MODULE.validate_report_file(
            directory=directory,
            section="imageRelease",
            contract=MODULE.load_canonical_contract(CONTRACT),
            expected_commit=COMMIT,
            epoch=epoch,
            signing_key=KEY,
            private_root=tmp_path,
            canonical_kubeconfig=directory / "kubeconfig",
            now=NOW,
        )


def test_in_memory_report_validator_accepts_canonical_bytes(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    directory = bundle_path.parent
    report_path = directory / "suites.json"
    raw = report_path.read_bytes()
    report_path.unlink()
    epoch = json.loads((directory / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME).read_text())

    validated = MODULE.validate_report_bytes(
        raw=raw,
        directory=directory,
        section="suites",
        contract=MODULE.load_canonical_contract(CONTRACT),
        expected_commit=COMMIT,
        epoch=epoch,
        signing_key=KEY,
        private_root=tmp_path,
        canonical_kubeconfig=directory / "kubeconfig",
        now=NOW,
    )

    assert validated["path"] == report_path
    assert not report_path.exists()
    assert validated["report"] == json.loads(raw)
    assert validated["sha256"] == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("started_at", "finished_at", "observed_now"),
    (
        (
            "2026-08-08T06:00:00Z",
            "2026-08-08T06:00:00Z",
            NOW,
        ),
        (
            "2026-08-08T06:05:00Z",
            "2026-08-08T06:10:00Z",
            datetime(2026, 8, 8, 6, 9, tzinfo=UTC),
        ),
        (
            "2026-08-08T06:05:00Z",
            "2026-08-08T06:10:00Z",
            datetime(2026, 8, 9, 6, 10, 1, tzinfo=UTC),
        ),
    ),
    ids=("before-epoch", "future", "maximum-age"),
)
def test_single_clean_reset_validator_rejects_invalid_temporal_evidence(
    tmp_path: Path,
    started_at: str,
    finished_at: str,
    observed_now: datetime,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    directory = bundle_path.parent
    report_path = directory / "cleanReset.json"
    report = json.loads(report_path.read_text())
    report["startedAt"] = started_at
    report["finishedAt"] = finished_at
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    report_path.write_bytes(_canonical(report) + b"\n")
    epoch = json.loads((directory / MODULE.ACCEPTANCE_EPOCH.EPOCH_NAME).read_text())

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="report freshness is invalid: cleanReset",
    ):
        MODULE.validate_report_file(
            directory=directory,
            section="cleanReset",
            contract=MODULE.load_canonical_contract(CONTRACT),
            expected_commit=COMMIT,
            epoch=epoch,
            signing_key=KEY,
            private_root=tmp_path,
            canonical_kubeconfig=directory / "kubeconfig",
            now=observed_now,
        )


def test_verified_signed_original_reports_pass(tmp_path: Path) -> None:
    _validate(tmp_path)


def test_final_bundle_validation_reuses_common_report_validator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = MODULE.load_canonical_contract(CONTRACT)
    expected_sections = MODULE.required_reports_for_mode(contract, "bundledKeycloak")
    validate_report_file = MODULE.validate_report_file
    observed: list[str] = []

    def capture_validation(**kwargs):
        observed.append(kwargs["section"])
        return validate_report_file(**kwargs)

    monkeypatch.setattr(MODULE, "validate_report_file", capture_validation)

    _validate(tmp_path)

    assert observed == expected_sections


@pytest.mark.parametrize(
    ("variant", "expected_error"),
    (
        ("duplicate", "invalid JSON"),
        ("whitespace", "not canonical JSON"),
        ("order", "not canonical JSON"),
        ("missing-newline", "not canonical JSON"),
        ("invalid-utf8", "invalid JSON"),
    ),
)
def test_bundle_rejects_ambiguous_or_noncanonical_raw_json(
    tmp_path: Path, variant: str, expected_error: str
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    canonical_raw = bundle_path.read_bytes()
    bundle = json.loads(canonical_raw)
    bundle_path.write_bytes(_raw_json_variant(bundle, canonical_raw, variant, "commit"))

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match=f"acceptance bundle is {expected_error}",
    ):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


@pytest.mark.parametrize(
    ("variant", "expected_error"),
    (
        ("duplicate", "invalid JSON"),
        ("whitespace", "not canonical JSON"),
        ("order", "not canonical JSON"),
        ("missing-newline", "not canonical JSON"),
        ("invalid-utf8", "invalid JSON"),
    ),
)
def test_report_rejects_ambiguous_or_noncanonical_raw_json(
    tmp_path: Path, variant: str, expected_error: str
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_bytes())
    report_path = bundle_path.parent / bundle["reports"]["terminal"]["file"]
    canonical_raw = report_path.read_bytes()
    report = json.loads(canonical_raw)
    mutated_raw = _raw_json_variant(report, canonical_raw, variant, "commit")
    report_path.write_bytes(mutated_raw)
    bundle["reports"]["terminal"]["sha256"] = hashlib.sha256(mutated_raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match=f"terminal report is {expected_error}",
    ):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_report_rejects_nested_duplicate_json_keys(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_bytes())
    report_path = bundle_path.parent / bundle["reports"]["terminal"]["file"]
    raw = report_path.read_bytes()
    needle = b'"probe":{"id":"homelab-terminal",'
    assert needle in raw
    mutated_raw = raw.replace(
        needle,
        b'"probe":{"id":"homelab-terminal","id":"homelab-terminal",',
        1,
    )
    report_path.write_bytes(mutated_raw)
    bundle["reports"]["terminal"]["sha256"] = hashlib.sha256(mutated_raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="terminal report is invalid JSON",
    ):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_validator_uses_only_the_run_bound_canonical_kubeconfig(
    tmp_path: Path,
) -> None:
    _evidence(tmp_path)
    runner = ClusterRunner()
    canonical = tmp_path / "evidence" / COMMIT / DEPLOYMENT_RUN_ID / "kubeconfig"

    MODULE.validate_evidence(
        COMMIT,
        DEPLOYMENT_RUN_ID,
        CONTRACT,
        context="rke2-homelab",
        runner=runner,
        now=NOW,
    )

    assert runner.commands
    assert all(
        command[command.index("--kubeconfig") + 1] == str(canonical)
        for command in runner.commands
    )
    rejected = ClusterRunner()
    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="canonical kubeconfig path does not match the acceptance run",
    ):
        MODULE.validate_evidence(
            COMMIT,
            DEPLOYMENT_RUN_ID,
            CONTRACT,
            context="rke2-homelab",
            canonical_kubeconfig=_kubeconfig(tmp_path),
            runner=rejected,
            now=NOW,
        )
    assert rejected.commands == []


def test_bundle_second_validation_receives_the_same_canonical_kubeconfig(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    output, _ = _evidence(tmp_path)
    output.unlink()
    canonical = output.parent / "kubeconfig"
    observed: list[Path] = []

    def capture(*_args, **kwargs) -> None:
        observed.append(kwargs["canonical_kubeconfig"])

    monkeypatch.setattr(BUNDLE.EVIDENCE, "validate_evidence", capture)
    BUNDLE.build_bundle(
        expected_commit=COMMIT,
        deployment_run_id=DEPLOYMENT_RUN_ID,
        contract_path=CONTRACT,
        context="rke2-homelab",
        runner=ClusterRunner(),
    )

    assert observed == [canonical]


@pytest.mark.parametrize("authentication_mode", ["bundledKeycloak", "externalOidc"])
def test_code_owned_bundle_builder_uses_exact_mode_report_set_and_mode_0600(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    authentication_mode: str,
) -> None:
    output = _build_code_owned_bundle(tmp_path, monkeypatch, authentication_mode)
    contract = json.loads(CONTRACT.read_text())
    bundle = json.loads(output.read_text())

    assert output.stat().st_mode & 0o777 == 0o600
    assert set(bundle["reports"]) == set(
        MODULE.required_reports_for_mode(contract, authentication_mode)
    )
    assert bundle["deploymentRunId"] == DEPLOYMENT_RUN_ID
    assert bundle["authenticationMode"] == authentication_mode
    assert not list(output.parent.glob(f".{BUNDLE.DEFAULT_BUNDLE_NAME}.*.tmp"))


def test_code_owned_bundle_rejects_cross_mode_report_stitching(
    tmp_path: Path,
) -> None:
    tmp_path.chmod(0o700)
    manual_bundle, _ = _evidence(tmp_path, "externalOidc")
    manual_bundle.unlink()
    extra = manual_bundle.parent / "identity.json"
    extra.write_text("{}\n", encoding="utf-8")
    extra.chmod(0o600)

    with pytest.raises(BUNDLE.AcceptanceBundleError, match="exact mode-specific"):
        BUNDLE.build_bundle(
            expected_commit=COMMIT,
            deployment_run_id=DEPLOYMENT_RUN_ID,
            contract_path=CONTRACT,
            context="rke2-homelab",
            runner=ClusterRunner(),
        )


def test_code_owned_bundle_removes_temporary_file_after_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.chmod(0o700)
    manual_bundle, _ = _evidence(tmp_path)
    manual_bundle.unlink()

    def reject(*_args, **_kwargs) -> None:
        raise BUNDLE.EVIDENCE.AcceptanceEvidenceError("fixture rejection")

    monkeypatch.setattr(BUNDLE.EVIDENCE, "validate_evidence", reject)
    output = manual_bundle
    with pytest.raises(BUNDLE.AcceptanceBundleError, match="fixture rejection"):
        BUNDLE.build_bundle(
            expected_commit=COMMIT,
            deployment_run_id=DEPLOYMENT_RUN_ID,
            contract_path=CONTRACT,
            context="rke2-homelab",
            runner=ClusterRunner(),
        )

    assert not output.exists()
    assert not list(output.parent.glob(f".{BUNDLE.DEFAULT_BUNDLE_NAME}.*.tmp"))


def test_code_owned_bundle_never_overwrites_or_removes_an_existing_output(
    tmp_path: Path,
) -> None:
    output, _ = _evidence(tmp_path)
    original = output.read_bytes()

    with pytest.raises(BUNDLE.AcceptanceBundleError, match="already exists"):
        BUNDLE.build_bundle(
            expected_commit=COMMIT,
            deployment_run_id=DEPLOYMENT_RUN_ID,
            contract_path=CONTRACT,
            context="rke2-homelab",
            runner=ClusterRunner(),
        )

    assert output.read_bytes() == original


def test_code_owned_bundle_publish_race_preserves_the_concurrent_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, _ = _evidence(tmp_path)
    output.unlink()
    concurrent = b"concurrent valid owner output\n"

    def collide(*_args, **_kwargs) -> None:
        output.write_bytes(concurrent)
        output.chmod(0o600)
        raise FileExistsError("simulated concurrent publisher")

    monkeypatch.setattr(BUNDLE.os, "link", collide)
    with pytest.raises(BUNDLE.AcceptanceBundleError, match="concurrent publisher"):
        BUNDLE.build_bundle(
            expected_commit=COMMIT,
            deployment_run_id=DEPLOYMENT_RUN_ID,
            contract_path=CONTRACT,
            context="rke2-homelab",
            runner=ClusterRunner(),
        )

    assert output.read_bytes() == concurrent
    assert not list(output.parent.glob(f".{BUNDLE.DEFAULT_BUNDLE_NAME}.*.tmp"))


@pytest.mark.parametrize(
    "section",
    [
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "workspaceLifecycle",
        "adminDisableLogin",
    ],
)
def test_observation_validator_accepts_browser_evidence_contract(section: str) -> None:
    workspace_id = (
        WORKSPACE["id"]
        if section in {"terminal", "http", "browser", "websocket", "workspaceLifecycle"}
        else None
    )

    _validate_browser_observations(
        section,
        _observations(section, "a" * 64, "b" * 64),
        _browser_source_commands(section, workspace_id=workspace_id),
    )


@pytest.mark.parametrize("section", ["oidcWorkspace", "adminDisableLogin"])
def test_observation_validator_accepts_ca_bootstrap_browser_source(
    section: str,
) -> None:
    _validate_browser_observations(
        section,
        _observations(section, "a" * 64, "b" * 64),
        _browser_source_commands(section, ca_bootstrap_wrapper=True),
    )


@pytest.mark.parametrize(
    ("section", "field", "invalid_value", "message"),
    [
        (
            "oidcWorkspace",
            "createdWorkspaceId",
            "workspace-cross-scope",
            "OIDC user and new Workspace evidence is invalid",
        ),
        ("terminal", "roundTrip", "failed", "Terminal evidence is incomplete"),
        (
            "http",
            "browser",
            503,
            "Runtime, Browser, and Canvas HTTP evidence is incomplete",
        ),
        (
            "browser",
            "dataChannel",
            "closed",
            (
                "Browser UI WebSocket, WebRTC, video, or data-channel evidence "
                "is incomplete"
            ),
        ),
        (
            "websocket",
            "messagesObserved",
            0,
            "WebSocket evidence is incomplete",
        ),
        (
            "workspaceLifecycle",
            "componentsRestarted",
            ["runtime", "browser"],
            "Workspace lifecycle evidence is incomplete",
        ),
        (
            "adminDisableLogin",
            "disabledLogin",
            "accepted",
            "temporary native user disable and restoration did not fail closed",
        ),
    ],
)
def test_observation_validator_preserves_browser_fail_closed_errors(
    section: str,
    field: str,
    invalid_value: object,
    message: str,
) -> None:
    observations = _observations(section, "a" * 64, "b" * 64)
    observations[field] = invalid_value
    workspace_id = (
        WORKSPACE["id"]
        if section in {"terminal", "http", "browser", "websocket", "workspaceLifecycle"}
        else None
    )

    with pytest.raises(MODULE.AcceptanceEvidenceError, match=message):
        _validate_browser_observations(
            section,
            observations,
            _browser_source_commands(section, workspace_id=workspace_id),
        )


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("missing", None),
        (
            "malformed",
            {
                "platformRole": "admin",
                "requiredOperations": "verified",
                "adminUsersStatus": 403,
                "marketplaceCatalogStatus": 200,
            },
        ),
        (
            "extra",
            {
                "platformRole": "admin",
                "requiredOperations": "verified",
                "adminUsersStatus": 200,
                "marketplaceCatalogStatus": 200,
                "unexpected": True,
            },
        ),
    ],
)
def test_observation_validator_rejects_invalid_platform_admin_evidence(
    mutation: str,
    value: object,
) -> None:
    observations = _observations("adminDisableLogin", "a" * 64, "b" * 64)
    if mutation == "missing":
        observations.pop("platformAdmin")
    else:
        observations["platformAdmin"] = value

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="temporary native user disable and restoration did not fail closed",
    ):
        _validate_browser_observations(
            "adminDisableLogin",
            observations,
            _browser_source_commands("adminDisableLogin"),
        )


def test_observation_validator_rejects_browser_source_provenance_drift() -> None:
    source_commands = _browser_source_commands("browser", workspace_id=WORKSPACE["id"])
    source_commands[BROWSER_SCRIPT_DIGEST] = source_commands[BROWSER_SCRIPT_DIGEST][1:]

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="browser probe exact source evidence is missing",
    ):
        _validate_browser_observations(
            "browser",
            _observations("browser", "a" * 64, "b" * 64),
            source_commands,
        )


def test_observation_validator_rejects_cross_workspace_lifecycle_source() -> None:
    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="Terminal browser lifecycle source is missing",
    ):
        _validate_browser_observations(
            "terminal",
            _observations("terminal", "a" * 64, "b" * 64),
            _browser_source_commands("terminal", workspace_id="workspace-cross-scope"),
        )


@pytest.mark.parametrize(
    ("section", "workspace_context"),
    [
        (section, workspace_context)
        for section in [
            "oidcWorkspace",
            "terminal",
            "http",
            "browser",
            "websocket",
            "workspaceLifecycle",
        ]
        for workspace_context in [None, {}, {"id": ""}, {"id": 1}]
    ],
)
def test_observation_validator_rejects_invalid_browser_workspace_context(
    section: str,
    workspace_context: object,
) -> None:
    workspace_id = (
        WORKSPACE["id"]
        if section in {"terminal", "http", "browser", "websocket", "workspaceLifecycle"}
        else None
    )

    with pytest.raises(MODULE.AcceptanceEvidenceError) as exc_info:
        _validate_browser_observations(
            section,
            _observations(section, "a" * 64, "b" * 64),
            _browser_source_commands(section, workspace_id=workspace_id),
            workspace_context=workspace_context,
        )

    assert str(exc_info.value) == f"{section} workspace context is invalid"


@pytest.mark.parametrize(
    "workspace_context",
    [
        {"id": WORKSPACE["id"]},
        {"id": WORKSPACE["id"], "userSubject": ""},
        {"id": WORKSPACE["id"], "userSubject": 1},
    ],
)
def test_observation_validator_rejects_invalid_oidc_workspace_subject(
    workspace_context: object,
) -> None:
    with pytest.raises(MODULE.AcceptanceEvidenceError) as exc_info:
        _validate_browser_observations(
            "oidcWorkspace",
            _observations("oidcWorkspace", "a" * 64, "b" * 64),
            _browser_source_commands("oidcWorkspace"),
            workspace_context=workspace_context,
        )

    assert str(exc_info.value) == "oidcWorkspace workspace context is invalid"


@pytest.mark.parametrize(
    ("flag", "message"),
    [
        ("--tag", "browser probe full-SHA image build is missing"),
        ("--label", "browser probe full-SHA image build is missing"),
        ("--section", "Terminal browser lifecycle source is missing"),
    ],
)
def test_observation_validator_rejects_malformed_browser_source_option(
    flag: str,
    message: str,
) -> None:
    source_commands = _browser_source_commands("terminal", workspace_id=WORKSPACE["id"])
    command = next(command for command in source_commands["a" * 64] if flag in command)
    del command[command.index(flag) + 1 :]

    with pytest.raises(MODULE.AcceptanceEvidenceError) as exc_info:
        _validate_browser_observations(
            "terminal",
            _observations("terminal", "a" * 64, "b" * 64),
            source_commands,
        )

    assert str(exc_info.value) == message


def test_forged_report_with_recomputed_hash_fails_signature(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["terminal"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["roundTrip"] = "verified"
    report["probe"]["id"] = "forged-live-probe"
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["terminal"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="signature"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_clean_reset_requires_exact_absence_sets(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["cleanReset"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["observedAbsent"]["pvs"] = []
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["cleanReset"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="exact reset"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_requires_the_full_cadence_window(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    report["finishedAt"] = "2026-08-08T07:01:00Z"
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="cadence"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_report_omits_fixed_success_and_duplicate_duration_fields(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    observations = json.loads(
        (bundle_path.parent / bundle["reports"]["soak"]["file"]).read_text()
    )["observations"]

    assert "durationSeconds" not in observations
    assert all(
        set(sample)
        == {"sequence", "observedAt", "elapsedMilliseconds", "queryBindings"}
        for sample in observations["samples"]
    )


def test_soak_raw_fixture_is_json_round_trip_safe_and_object_detached() -> None:
    documents = _soak_raw_documents("bundledKeycloak")

    assert documents == json.loads(json.dumps(documents))
    browser_query_pod = documents["browserPods"]["items"][0]
    workspace_query_pod = next(
        pod
        for pod in documents["workspacePods"]["items"]
        if pod["metadata"]["uid"] == browser_query_pod["metadata"]["uid"]
    )
    browser_query_pod["metadata"]["labels"]["fixture-isolation"] = "browser"
    assert "fixture-isolation" not in workspace_query_pod["metadata"]["labels"]

    deployment = next(
        item
        for item in documents["controllers"]["items"]
        if item["kind"] == "Deployment"
    )
    replica_set = next(
        item
        for item in documents["controllers"]["items"]
        if item["kind"] == "ReplicaSet"
        and item["metadata"]["ownerReferences"][0]["uid"]
        == deployment["metadata"]["uid"]
    )
    deployment["metadata"]["labels"]["fixture-isolation"] = "deployment"
    assert "fixture-isolation" not in replica_set["metadata"]["labels"]
    assert "fixture-isolation" not in deployment["spec"]["selector"]["matchLabels"]

    service = documents["services"]["items"][0]
    service["metadata"]["labels"]["fixture-isolation"] = "service"
    assert "fixture-isolation" not in service["spec"]["selector"]


def test_external_soak_does_not_query_or_require_identity_pods(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path, "externalOidc")
    bundle = json.loads(bundle_path.read_text())
    assert "identity" not in bundle["reports"]
    assert "adminDisableLogin" not in bundle["reports"]
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    assert report["authenticationMode"] == "externalOidc"
    assert len(report["observations"]["samples"]) == 31
    assert len(report["sources"]) == 31 * 9 == 279
    assert all(
        len(sample["queryBindings"]) == 9
        for sample in report["observations"]["samples"]
    )
    assert all(
        item["namespace"] != "aileron-identity-system"
        for item in report["observations"]["baseline"]["pods"]
    )

    MODULE.validate_evidence(
        COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
    )


def test_soak_rejects_any_mutating_source_command(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    report["sources"][0]["command"][5:] = [
        "delete",
        "pod",
        "aileron-identity-1",
        "--namespace",
        "aileron-identity-system",
    ]
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="source binding"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_rejects_wall_clock_gap_without_matching_monotonic_gap(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["samples"][15]["observedAt"] = "2026-08-08T06:58:16Z"
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="clock drift"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_rejects_cumulative_wall_clock_drift(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    started = datetime(2026, 8, 8, 6, 43, tzinfo=UTC)
    for sample in report["observations"]["samples"]:
        index = sample["sequence"]
        sample["observedAt"] = (
            (started + timedelta(milliseconds=60_000 * index + 100 * index))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
    report["finishedAt"] = "2026-08-08T07:13:03Z"
    _resign_soak_report(bundle_path, report)

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="clock drift"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_rejects_a_32nd_sample_and_its_nine_sources(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    previous_sources = [
        item for item in report["sources"] if item["sampleSequence"] == 30
    ]
    bindings = []
    for previous in previous_sources:
        source = dict(previous)
        source["sampleSequence"] = 31
        source["file"] = source["file"].replace("-0030-", "-0031-")
        source_path = bundle_path.parent / source["file"]
        source_path.write_bytes((bundle_path.parent / previous["file"]).read_bytes())
        source_path.chmod(0o600)
        report["sources"].append(source)
        bindings.append(
            {
                "queryId": source["queryId"],
                "file": source["file"],
                "sha256": source["sha256"],
            }
        )
    report["observations"]["samples"].append(
        {
            "sequence": 31,
            "observedAt": "2026-08-08T07:14:00Z",
            "elapsedMilliseconds": 1_860_000,
            "queryBindings": bindings,
        }
    )
    report["observations"]["monotonicDurationMilliseconds"] = 1_860_000
    report["finishedAt"] = "2026-08-08T07:14:00Z"
    _resign_soak_report(bundle_path, report)

    assert len(report["observations"]["samples"]) == 32
    assert len(report["sources"]) == 32 * 9
    with pytest.raises(MODULE.AcceptanceEvidenceError, match="sample count"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_requires_every_read_only_query_for_every_sample(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    report["sources"].pop()
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="binding coverage"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def _resign_soak_report(bundle_path: Path, report: dict) -> None:
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    unsigned = dict(report)
    unsigned.pop("signature", None)
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")


def test_external_soak_rejects_identity_residue_from_bound_raw_sources(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path, "externalOidc")
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    source = next(
        item
        for item in report["sources"]
        if item["sampleSequence"] == 0 and item["queryId"] == "identityPods"
    )
    source_path = bundle_path.parent / source["file"]
    document = json.loads(source_path.read_text())
    document["items"].append(
        _soak_raw_documents("bundledKeycloak")["identityPods"]["items"][0]
    )
    source_path.write_bytes(
        json.dumps(document, separators=(",", ":"), sort_keys=True).encode() + b"\n"
    )
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source["sha256"] = digest
    binding = next(
        item
        for item in report["observations"]["samples"][0]["queryBindings"]
        if item["queryId"] == "identityPods"
    )
    binding["sha256"] = digest
    _resign_soak_report(bundle_path, report)

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="identity|external OIDC"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


@pytest.mark.parametrize(
    "attack",
    [
        "duplicate-reference",
        "cross-sequence-swap",
        "missing-source",
        "extra-source",
        "tampered-attempt",
        "tampered-sequence",
        "tampered-query",
        "untrusted-kubeconfig",
    ],
)
def test_soak_rejects_source_binding_attacks(tmp_path: Path, attack: str) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    query_count = len(report["observations"]["samples"][0]["queryBindings"])
    first = report["sources"][0]
    second_sequence = report["sources"][query_count]
    if attack == "duplicate-reference":
        second_sequence["file"] = first["file"]
        second_sequence["sha256"] = first["sha256"]
        report["observations"]["samples"][1]["queryBindings"][0].update(
            {"file": first["file"], "sha256": first["sha256"]}
        )
    elif attack == "cross-sequence-swap":
        first["file"], second_sequence["file"] = (
            second_sequence["file"],
            first["file"],
        )
        first["sha256"], second_sequence["sha256"] = (
            second_sequence["sha256"],
            first["sha256"],
        )
        report["observations"]["samples"][0]["queryBindings"][0].update(
            {"file": first["file"], "sha256": first["sha256"]}
        )
        report["observations"]["samples"][1]["queryBindings"][0].update(
            {"file": second_sequence["file"], "sha256": second_sequence["sha256"]}
        )
    elif attack == "missing-source":
        report["sources"].pop()
    elif attack == "extra-source":
        report["sources"].append(dict(report["sources"][-1]))
    elif attack == "tampered-attempt":
        first["attemptId"] = "run-other-attempt"
    elif attack == "tampered-sequence":
        first["sampleSequence"] = 1
    elif attack == "tampered-query":
        first["queryId"] = "services"
    else:
        for source in report["sources"]:
            source["command"][2] = "/private/untrusted-kubeconfig"
    _resign_soak_report(bundle_path, report)

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="source|binding"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_rejects_invalid_bound_raw_json(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    source = report["sources"][0]
    source_path = bundle_path.parent / source["file"]
    source_path.write_bytes(b"{\n")
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    source["sha256"] = digest
    report["observations"]["samples"][0]["queryBindings"][0]["sha256"] = digest
    _resign_soak_report(bundle_path, report)

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="invalid JSON"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_allows_distinct_sources_with_identical_raw_sha(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report = json.loads(
        (bundle_path.parent / bundle["reports"]["soak"]["file"]).read_text()
    )

    assert len({source["file"] for source in report["sources"]}) == len(
        report["sources"]
    )
    assert len({source["sha256"] for source in report["sources"]}) < len(
        report["sources"]
    )
    MODULE.validate_evidence(
        COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
    )


def test_soak_rejects_a_tampered_baseline_with_a_recomputed_digest(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["soak"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["baseline"]["services"][1]["dnsName"] = (
        "unexpected.workspace-system.svc.cluster.local"
    )
    baseline = report["observations"]["baseline"]
    payload = {key: value for key, value in baseline.items() if key != "sha256"}
    report["observations"]["baseline"] = {
        **payload,
        "sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
    }
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["soak"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="baseline.*raw sources"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_soak_must_start_after_planned_restart_finishes(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["restart"]["file"]
    report = json.loads(report_path.read_text())
    report["finishedAt"] = "2026-08-08T07:01:00Z"
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["restart"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="restart -> soak"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_workspace_lifecycle_must_finish_before_restart_starts(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["workspaceLifecycle"]["file"]
    report = json.loads(report_path.read_text())
    report["finishedAt"] = "2026-08-08T06:59:00Z"
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["workspaceLifecycle"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(
        MODULE.AcceptanceEvidenceError, match="workspaceLifecycle -> restart"
    ):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_suite_contract_requires_docker_and_raw_logs() -> None:
    contract = json.loads(CONTRACT.read_text())
    assert contract["requiredSuites"] == [
        "docker",
        "helm",
        "frontend",
        "manager",
        "operator",
        "identity",
        "platform-conformance",
        "kubernetes-hardening",
    ]


def test_suite_report_rejects_unverified_source_provenance(tmp_path: Path) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["suites"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["sourceProvenance"]["worktreeClean"] = False
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["suites"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="source provenance"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


def test_suite_report_rejects_runner_without_the_verified_source_commit(
    tmp_path: Path,
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["suites"]["file"]
    report = json.loads(report_path.read_text())
    report["observations"]["runs"][1]["runner"]["sourceRevision"] = "b" * 40
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["suites"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(MODULE.AcceptanceEvidenceError, match="runner evidence"):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )


@pytest.mark.parametrize("attack", ["extra-environment", "duplicate-env-file"])
def test_suite_report_rejects_noncanonical_hermetic_commands(
    tmp_path: Path, attack: str
) -> None:
    bundle_path, _ = _evidence(tmp_path)
    bundle = json.loads(bundle_path.read_text())
    report_path = bundle_path.parent / bundle["reports"]["suites"]["file"]
    report = json.loads(report_path.read_text())
    run = report["observations"]["runs"][0]
    if attack == "extra-environment":
        original = list(run["command"])
        run["command"].insert(4, "HOST_PROJECT_ROOT=/untrusted")
        source = next(item for item in report["sources"] if item["command"] == original)
        source["command"] = list(run["command"])
    else:
        preflight = run["preflightCommand"]
        position = preflight.index("--project-name")
        preflight[position:position] = ["--env-file", "/untrusted.env"]
    unsigned = dict(report)
    unsigned.pop("signature")
    report["signature"] = hmac.new(
        KEY, _canonical(unsigned), hashlib.sha256
    ).hexdigest()
    raw = _canonical(report) + b"\n"
    report_path.write_bytes(raw)
    bundle["reports"]["suites"]["sha256"] = hashlib.sha256(raw).hexdigest()
    bundle_path.write_bytes(_canonical(bundle) + b"\n")

    with pytest.raises(
        MODULE.AcceptanceEvidenceError,
        match="isolated Compose execution|root Compose quiet validation",
    ):
        MODULE.validate_evidence(
            COMMIT, DEPLOYMENT_RUN_ID, CONTRACT, **_cluster_kwargs(tmp_path)
        )
