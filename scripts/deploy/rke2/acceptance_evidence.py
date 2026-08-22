"""Verify hashed original HomeLab reports before declaring deployment success."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIRECTORY / "deployment-acceptance-contract.json"
DEFAULT_BUNDLE_NAME = "deployment-acceptance-bundle.json"
CANONICAL_CONTRACT_SHA256 = (
    "ce578f2cc84a4cfc74a48234db1dcc73fad4b2272cd64decfb6d7cfc652e3eaf"
)
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FILE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
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
HERMETIC_COMPOSE_ENVIRONMENT = [
    "env",
    "-i",
    "PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
    "COMPOSE_DISABLE_ENV_FILE=1",
]
SUITE_COMPOSE_TARGETS = {
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
SUITE_BUILD_TARGETS = {
    "docker": (".", "scripts/test/compose-e2e/Dockerfile.acceptance", None),
    "helm": (".", "scripts/test/helm/Dockerfile", None),
    "frontend": ("frontend", "frontend/Dockerfile.dev", None),
    "manager": (".", "workspace-manager/Dockerfile", "test"),
    "operator": ("workspace-operator", "workspace-operator/Dockerfile", "test"),
    "identity": (".", "scripts/test/deploy/Dockerfile", None),
    "platform-conformance": (
        ".",
        "scripts/test/kubernetes/product-conformance/Dockerfile",
        None,
    ),
    "kubernetes-hardening": (
        ".",
        "scripts/test/kubernetes/product-conformance/Dockerfile.hardening",
        None,
    ),
    "docs-zh-Hant": ("docs-site", "docs-site/Dockerfile.test", None),
    "docs-en": ("docs-site", "docs-site/Dockerfile.test", None),
}
SUITE_BUILD_ARGUMENTS = {
    "docker": (
        (
            "DOCKER_CLI_IMAGE",
            "docker:27-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01",
        ),
    ),
    "frontend": (
        (
            "NODE_IMAGE",
            "node:24.18.0-alpine@sha256:4ba75f835bb8802193e4c114572113d4b26f95f6f094f4b5229d2a77773e0afc",
        ),
        ("NPM_VERSION", "12.0.1"),
    ),
    "manager": (
        (
            "PYTHON_IMAGE",
            "python:3.14.6-slim@sha256:b921fe7e7522f828d45197a47656ec465a9b15689b27fa8e1fba2864fca5b967",
        ),
        (
            "NODE_IMAGE",
            "node:24.18.0-slim@sha256:d45d78e7929b46875bbd4e29bea672d5bc48186c6c3588306521c815e78352d6",
        ),
        ("NPM_VERSION", "12.0.1"),
        ("UV_VERSION", "0.11.32"),
        ("CODEX_CLI_VERSION", "0.145.0"),
    ),
    "operator": (
        ("BUILDPLATFORM", "linux/amd64"),
        ("TARGETOS", "linux"),
        ("TARGETARCH", "amd64"),
        (
            "GO_IMAGE",
            "golang:1.22-alpine@sha256:6d405dfc5fdf3a45df1529cf060b920041f52ce523487e0f36f02765af294a51",
        ),
        (
            "RUNTIME_IMAGE",
            "alpine:3.20@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e",
        ),
    ),
}
BASE_REPORT_KEYS = {
    "schemaVersion",
    "section",
    "commit",
    "deploymentRunId",
    "authenticationMode",
    "startedAt",
    "finishedAt",
    "producer",
    "probe",
    "sources",
    "observations",
    "signature",
}
WORKSPACE_REPORT_KEYS = {*BASE_REPORT_KEYS, "workspace"}
SourceCommands = dict[str, list[list[str]]]


def _load_cluster_module() -> Any:
    specification = importlib.util.spec_from_file_location(
        "aileron_acceptance_cluster", SCRIPT_DIRECTORY / "acceptance_cluster.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError("acceptance cluster trust loader is unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ACCEPTANCE_CLUSTER = _load_cluster_module()


def _load_local_module(name: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        f"aileron_{name}", SCRIPT_DIRECTORY / f"{name}.py"
    )
    if specification is None or specification.loader is None:
        raise RuntimeError(f"acceptance dependency is unavailable: {name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


ACCEPTANCE_EPOCH = _load_local_module("acceptance_epoch")
ACCEPTANCE_RELEASE = _load_local_module("acceptance_release")
ACCEPTANCE_SNAPSHOT = _load_local_module("acceptance_snapshot")
ACCEPTANCE_SOAK = _load_local_module("acceptance_soak")
BROWSER_POLICY = _load_local_module("acceptance_browser_policy")
PRIVATE_IO = _load_local_module("acceptance_private_io")
RESET_INVENTORY = _load_local_module("collect_reset_inventory")
RUN_ID = PRIVATE_IO.RUN_ID


class AcceptanceEvidenceError(RuntimeError):
    """Raised when original deployment evidence is incomplete or inconsistent."""


def _json(
    content: bytes, description: str, *, require_canonical: bool = True
) -> dict[str, Any]:
    return PRIVATE_IO.load_json_object(
        content,
        description,
        error_type=AcceptanceEvidenceError,
        require_canonical=require_canonical,
    )


def load_canonical_contract(contract_path: Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    """Load only the tracked, digest-bound acceptance policy."""

    try:
        resolved = contract_path.resolve(strict=True)
        canonical = DEFAULT_CONTRACT.resolve(strict=True)
        content = contract_path.read_bytes()
    except OSError as exc:
        raise AcceptanceEvidenceError(
            "canonical acceptance contract is unavailable"
        ) from exc
    if (
        resolved != canonical
        or hashlib.sha256(content).hexdigest() != CANONICAL_CONTRACT_SHA256
    ):
        raise AcceptanceEvidenceError(
            "acceptance contract does not match the tracked canonical policy"
        )
    return _json(content, "acceptance contract", require_canonical=False)


def _timestamp(value: Any, description: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise AcceptanceEvidenceError(f"{description} must be an RFC3339 UTC timestamp")
    try:
        observed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise AcceptanceEvidenceError(f"{description} is invalid") from exc
    if observed.tzinfo != timezone.utc:
        raise AcceptanceEvidenceError(f"{description} must use UTC")
    return observed


def _identity(value: Any, description: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise AcceptanceEvidenceError(f"{description} identity is invalid")
    if any(not isinstance(item, str) or not item for item in value.values()):
        raise AcceptanceEvidenceError(f"{description} identity is incomplete")
    return value


def _canonical(document: dict[str, Any]) -> bytes:
    return PRIVATE_IO.canonical_json(document)


def _all_source_commands(source_commands: SourceCommands | None) -> list[list[str]]:
    if source_commands is None:
        return []
    return [command for commands in source_commands.values() for command in commands]


def _source_has_command(
    source_commands: SourceCommands | None, digest: Any, command: Any
) -> bool:
    return (
        isinstance(digest, str)
        and isinstance(command, list)
        and source_commands is not None
        and command in source_commands.get(digest, [])
    )


def _validate_source_provenance(
    provenance: Any,
    *,
    commit: str,
    tree_digest_checks: int,
    source_commands: SourceCommands | None,
) -> None:
    if (
        not isinstance(provenance, dict)
        or set(provenance)
        != {
            "headCommit",
            "targetCommit",
            "worktreeClean",
            "untrackedFilesIncluded",
            "archiveSha256",
            "treeSha256",
            "archiveCommand",
            "materializedTreeReadOnly",
            "treeDigestChecks",
        }
        or provenance["headCommit"] != commit
        or provenance["targetCommit"] != commit
        or provenance["worktreeClean"] is not True
        or provenance["untrackedFilesIncluded"] is not True
        or FILE_DIGEST.fullmatch(provenance.get("archiveSha256", "")) is None
        or FILE_DIGEST.fullmatch(provenance.get("treeSha256", "")) is None
        or provenance["materializedTreeReadOnly"] is not True
        or provenance["treeDigestChecks"] != tree_digest_checks
        or not isinstance(provenance["archiveCommand"], list)
        or len(provenance["archiveCommand"]) != 6
        or provenance["archiveCommand"][:3]
        != ["git", "-C", provenance["archiveCommand"][2]]
        or not Path(provenance["archiveCommand"][2]).is_absolute()
        or provenance["archiveCommand"][3:]
        != [
            "archive",
            "--format=tar.gz",
            commit,
        ]
        or not _source_has_command(
            source_commands,
            provenance["archiveSha256"],
            provenance["archiveCommand"],
        )
    ):
        raise AcceptanceEvidenceError("acceptance source provenance is invalid")


def _validate_runner(runner: Any, *, name: str, commit: str) -> str:
    repository = SUITE_RUNNER_REPOSITORIES.get(name)
    image = runner.get("image") if isinstance(runner, dict) else None
    image_id = runner.get("imageId") if isinstance(runner, dict) else None
    build_command = runner.get("buildCommand") if isinstance(runner, dict) else None
    expected_target = SUITE_BUILD_TARGETS.get(name)
    expected_inspect = [
        "docker",
        "image",
        "inspect",
        '--format={{.Id}}\t{{.Architecture}}\t{{index .Config.Labels "org.opencontainers.image.revision"}}',
        image,
    ]
    if (
        not isinstance(runner, dict)
        or set(runner)
        != {
            "image",
            "imageId",
            "architecture",
            "sourceRevision",
            "buildCommand",
            "inspectCommand",
        }
        or not isinstance(image, str)
        or re.fullmatch(
            rf"{re.escape(repository or '')}:{re.escape(commit)}-[0-9a-f]{{12}}",
            image,
        )
        is None
        or DIGEST.fullmatch(image_id or "") is None
        or runner["architecture"] != "amd64"
        or runner["sourceRevision"] != commit
        or runner["inspectCommand"] != expected_inspect
        or not isinstance(build_command, list)
        or expected_target is None
    ):
        raise AcceptanceEvidenceError("suite runner evidence is invalid")
    context_relative, dockerfile_relative, target = expected_target
    expected_build_args = []
    for argument_name, argument_value in SUITE_BUILD_ARGUMENTS.get(name, ()):
        expected_build_args.extend(["--build-arg", f"{argument_name}={argument_value}"])
    expected_prefix = [
        "docker",
        "build",
        "--platform",
        "linux/amd64",
        "--file",
    ]
    if (
        build_command[:5] != expected_prefix
        or len(build_command) < 11
        or not Path(build_command[5]).is_absolute()
        or not build_command[5].endswith(f"/{dockerfile_relative}")
        or build_command[6:10]
        != ["--tag", image, "--build-arg", f"SOURCE_REVISION={commit}"]
        or build_command[10 : 10 + len(expected_build_args)] != expected_build_args
    ):
        raise AcceptanceEvidenceError("suite runner build evidence is invalid")
    tail_start = 10 + len(expected_build_args)
    expected_tail = ["--target", target] if target is not None else []
    if (
        build_command[tail_start:-1] != expected_tail
        or not Path(build_command[-1]).is_absolute()
    ):
        raise AcceptanceEvidenceError("suite runner build evidence is invalid")
    source_root = str(
        Path(build_command[5]).parents[len(Path(dockerfile_relative).parts) - 1]
    )
    expected_context = str((Path(source_root) / context_relative).resolve())
    if (
        build_command[-1] != expected_context
        or re.search(
            r"/\.(?:suites|offlineOidcConformance)-source-[0-9a-f]{12}$", source_root
        )
        is None
    ):
        raise AcceptanceEvidenceError("suite runner immutable build context is invalid")
    return source_root


def _validate_isolated_compose_run(
    *,
    name: str,
    commit: str,
    project_name: Any,
    command: Any,
    cleanup_command: Any,
    cleaned: Any,
    runner_image_id: str,
    source_root: str,
) -> None:
    project_pattern = re.compile(
        rf"^aileron-[a-z0-9-]+-{re.escape(commit[:12])}-[0-9a-f]{{8}}$"
    )
    compose_file, service = SUITE_COMPOSE_TARGETS.get(name, (None, None))
    image_environment = SUITE_IMAGE_ENVIRONMENT.get(name)
    command_environment = [
        *HERMETIC_COMPOSE_ENVIRONMENT,
        f"AILERON_SOURCE_REVISION={commit}",
        f"AILERON_SUITE_SOURCE_ROOT={source_root}",
        f"{image_environment}={runner_image_id}",
    ]
    compose = [
        "docker",
        "compose",
        "--env-file",
        "/dev/null",
        "--project-name",
        project_name,
        "--file",
        str(Path(source_root) / compose_file),
    ]
    expected_command = [
        *command_environment,
        *compose,
        "run",
        "--pull",
        "never",
        "--rm",
        service,
    ]
    expected_cleanup = [
        *command_environment,
        *compose,
        "down",
        "--volumes",
        "--remove-orphans",
    ]
    if (
        not isinstance(project_name, str)
        or project_pattern.fullmatch(project_name) is None
        or command != expected_command
        or cleanup_command != expected_cleanup
        or cleaned is not True
    ):
        raise AcceptanceEvidenceError(
            f"isolated Compose execution evidence is invalid for {name}"
        )


def _backend_target_identity(
    target: Any, *, result_digests: set[str]
) -> tuple[str, str, str]:
    expected_keys = {"persistentVolume", "locatorSha256", *result_digests}
    persistent_volume = (
        target.get("persistentVolume") if isinstance(target, dict) else None
    )
    if (
        not isinstance(target, dict)
        or set(target) != expected_keys
        or not isinstance(persistent_volume, dict)
        or set(persistent_volume) != {"name", "uid"}
        or any(
            not isinstance(persistent_volume.get(key), str)
            or not persistent_volume[key]
            for key in ("name", "uid")
        )
        or FILE_DIGEST.fullmatch(target.get("locatorSha256", "")) is None
        or any(
            FILE_DIGEST.fullmatch(target.get(key, "")) is None for key in result_digests
        )
    ):
        raise AcceptanceEvidenceError("clean reset backend target identity is invalid")
    return (
        persistent_volume["name"],
        persistent_volume["uid"],
        target["locatorSha256"],
    )


def _validate_backend_summary(
    *,
    summary: Any,
    schema_version: str,
    commit: str,
    run_id: str,
    snapshot_sha256: str,
    expected_targets: list[tuple[str, str, str]],
    source_digests: set[str],
    source_references: set[tuple[str, str]],
    post_reset: bool,
    cleanup_source_sha256: str | None = None,
) -> str:
    expected_keys = {
        "schemaVersion",
        "sourceFile",
        "sourceSha256",
        "commit",
        "runId",
        "snapshotSha256",
        "allAbsent",
        "targetResultDigests",
    }
    result_digests = {"verificationResultSha256"}
    if post_reset:
        expected_keys.add("backendCleanupResultsSha256")
    else:
        result_digests.add("cleanupResultSha256")
    if (
        not isinstance(summary, dict)
        or set(summary) != expected_keys
        or summary.get("schemaVersion") != schema_version
        or summary.get("commit") != commit
        or summary.get("runId") != run_id
        or summary.get("snapshotSha256") != snapshot_sha256
        or summary.get("allAbsent") is not True
        or not isinstance(summary.get("sourceFile"), str)
        or Path(summary["sourceFile"]).name != summary["sourceFile"]
        or FILE_DIGEST.fullmatch(summary.get("sourceSha256", "")) is None
        or summary["sourceSha256"] not in source_digests
        or (summary["sourceFile"], summary["sourceSha256"]) not in source_references
        or not isinstance(summary.get("targetResultDigests"), list)
        or (
            post_reset
            and summary.get("backendCleanupResultsSha256") != cleanup_source_sha256
        )
    ):
        raise AcceptanceEvidenceError("clean reset backend result binding is invalid")
    observed_targets = [
        _backend_target_identity(target, result_digests=result_digests)
        for target in summary["targetResultDigests"]
    ]
    if observed_targets != expected_targets:
        raise AcceptanceEvidenceError("clean reset backend target set is incomplete")
    return summary["sourceSha256"]


def _bound_soak_documents(
    *,
    observations: dict[str, Any],
    source_records: list[dict[str, Any]] | None,
    canonical_kubeconfig: Path,
    context: str,
    workspace_id: str,
    identity_mode: str,
) -> list[dict[str, dict[str, Any]]]:
    attempt_id = observations.get("attemptId")
    samples = observations.get("samples")
    if (
        not isinstance(attempt_id, str)
        or RUN_ID.fullmatch(attempt_id) is None
        or not isinstance(samples, list)
        or not samples
        or not isinstance(source_records, list)
    ):
        raise AcceptanceEvidenceError("soak source binding identity is invalid")
    try:
        commands = ACCEPTANCE_SOAK.build_query_commands(
            kubeconfig=str(canonical_kubeconfig),
            context=context,
            workspace_id=workspace_id,
            identity_mode=identity_mode,
        )
    except ACCEPTANCE_SOAK.SoakValidationError as exc:
        raise AcceptanceEvidenceError(str(exc)) from exc
    expected_query_ids = list(commands)
    records_by_key: dict[tuple[int, str], dict[str, Any]] = {}
    for record in source_records:
        sequence = record.get("sampleSequence")
        query_id = record.get("queryId")
        expected_name = (
            f"soak-{attempt_id}-{sequence:04d}-{query_id}.json"
            if isinstance(sequence, int)
            and not isinstance(sequence, bool)
            and isinstance(query_id, str)
            else None
        )
        key = (sequence, query_id)
        if (
            record.get("attemptId") != attempt_id
            or not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not 0 <= sequence < len(samples)
            or query_id not in commands
            or record.get("file") != expected_name
            or record.get("command") != commands[query_id]
            or key in records_by_key
        ):
            raise AcceptanceEvidenceError("soak source binding is invalid")
        records_by_key[key] = record
    expected_keys = {
        (sequence, query_id)
        for sequence in range(len(samples))
        for query_id in expected_query_ids
    }
    if set(records_by_key) != expected_keys:
        raise AcceptanceEvidenceError("soak source binding coverage is incomplete")

    documents: list[dict[str, dict[str, Any]]] = []
    referenced_files: set[str] = set()
    for sequence, sample in enumerate(samples):
        bindings = sample.get("queryBindings") if isinstance(sample, dict) else None
        if not isinstance(bindings, list) or len(bindings) != len(expected_query_ids):
            raise AcceptanceEvidenceError("soak sample query binding is incomplete")
        sample_documents: dict[str, dict[str, Any]] = {}
        for query_id, binding in zip(expected_query_ids, bindings):
            record = records_by_key[(sequence, query_id)]
            if (
                not isinstance(binding, dict)
                or set(binding) != {"queryId", "file", "sha256"}
                or binding
                != {
                    "queryId": query_id,
                    "file": record["file"],
                    "sha256": record["sha256"],
                }
                or binding["file"] in referenced_files
            ):
                raise AcceptanceEvidenceError("soak sample query binding is invalid")
            referenced_files.add(binding["file"])
            sample_documents[query_id] = _json(
                record["raw"],
                f"soak {query_id} source",
                require_canonical=False,
            )
        documents.append(sample_documents)
    if referenced_files != {record["file"] for record in source_records}:
        raise AcceptanceEvidenceError("soak source reference coverage is incomplete")
    return documents


def _validate_observations(
    section: str,
    observations: Any,
    *,
    contract: dict[str, Any],
    commit: str,
    deployment_run_id: str,
    authentication_mode: str,
    workspace: dict[str, str] | None,
    started: datetime,
    finished: datetime,
    source_digests: set[str],
    canonical_kubeconfig: Path,
    context: str,
    source_records: list[dict[str, Any]] | None = None,
    source_commands: SourceCommands | None = None,
    source_references: set[tuple[str, str]] | None = None,
    reset_snapshot_sha256: str | None = None,
    image_runtime_pairs: Mapping[str, frozenset[str]] | None = None,
    release_images: list[dict[str, str]] | None = None,
) -> None:
    if not isinstance(observations, dict):
        raise AcceptanceEvidenceError(f"{section} observations must be an object")
    if authentication_mode not in {"bundledKeycloak", "externalOidc"}:
        raise AcceptanceEvidenceError("report authentication mode is invalid")
    if (
        section in {"identity", "adminDisableLogin"}
        and authentication_mode != "bundledKeycloak"
    ):
        raise AcceptanceEvidenceError(
            f"{section} is not valid for external OIDC acceptance"
        )
    if section in BROWSER_POLICY.BROWSER_OBSERVATION_SECTIONS:
        try:
            BROWSER_POLICY.BROWSER_OBSERVATION_POLICY.validate(
                section,
                observations,
                BROWSER_POLICY.BrowserObservationContext(
                    commit=commit,
                    workspace=workspace,
                    source_commands=source_commands,
                ),
            )
        except BROWSER_POLICY.BrowserObservationError as exc:
            raise AcceptanceEvidenceError(str(exc)) from exc
        return
    if section == "cleanReset":
        expected = observations.get("expected")
        absent = observations.get("observedAbsent")
        source_references = source_references or set()
        if (
            set(observations)
            != {
                "resetRunId",
                "inventorySha256",
                "fixedResetTargets",
                "expected",
                "observedAbsent",
                "backendCleanupResults",
                "backendPostResetVerification",
            }
            or not isinstance(observations.get("resetRunId"), str)
            or RUN_ID.fullmatch(observations["resetRunId"]) is None
            or FILE_DIGEST.fullmatch(reset_snapshot_sha256 or "") is None
            or observations.get("fixedResetTargets")
            != {
                "namespaces": sorted(ACCEPTANCE_SNAPSHOT.TARGET_NAMESPACES),
                "storageClasses": sorted(RESET_INVENTORY.TARGET_STORAGE_CLASSES),
            }
            or not isinstance(observations.get("inventorySha256"), str)
            or FILE_DIGEST.fullmatch(observations["inventorySha256"]) is None
            or observations["inventorySha256"] not in source_digests
            or not isinstance(expected, dict)
            or set(expected)
            != {"namespaces", "workspaceCRs", "pvcs", "pvs", "backendTargets"}
            or not isinstance(absent, dict)
            or set(absent) != {"namespaces", "workspaceCRs", "pvcs", "pvs"}
            or any(
                not isinstance(namespace, str) or not namespace
                for namespace in expected["namespaces"]
            )
            or len(expected["namespaces"]) != len(set(expected["namespaces"]))
            or not set(expected["namespaces"]).issubset(
                set(contract["requiredNamespaces"])
            )
            or any(not isinstance(value, list) for value in expected.values())
            or any(not isinstance(value, list) for value in absent.values())
            or any(absent[key] != expected[key] for key in absent)
        ):
            raise AcceptanceEvidenceError(
                "clean reset exact reset inventory is incomplete"
            )
        if not isinstance(expected["backendTargets"], list):
            raise AcceptanceEvidenceError(
                "clean reset backend target set is incomplete"
            )
        expected_targets = [
            _backend_target_identity(target, result_digests=set())
            for target in expected["backendTargets"]
        ]
        if expected_targets != sorted(expected_targets) or len(expected_targets) != len(
            set(expected_targets)
        ):
            raise AcceptanceEvidenceError(
                "clean reset backend target set is not canonical"
            )
        cleanup_source_sha256 = _validate_backend_summary(
            summary=observations["backendCleanupResults"],
            schema_version="aileron-backend-cleanup-results/v1",
            commit=commit,
            run_id=observations["resetRunId"],
            snapshot_sha256=reset_snapshot_sha256,
            expected_targets=expected_targets,
            source_digests=source_digests,
            source_references=source_references,
            post_reset=False,
        )
        _validate_backend_summary(
            summary=observations["backendPostResetVerification"],
            schema_version="aileron-backend-post-reset-verification/v1",
            commit=commit,
            run_id=observations["resetRunId"],
            snapshot_sha256=reset_snapshot_sha256,
            expected_targets=expected_targets,
            source_digests=source_digests,
            source_references=source_references,
            post_reset=True,
            cleanup_source_sha256=cleanup_source_sha256,
        )
    elif section == "imageRelease":
        images = observations.get("images")
        expected_images = (
            [
                {
                    "component": image["component"],
                    "platform": image["platform"],
                    "revision": image["revision"],
                    "immutableImage": image["immutableImage"],
                    "runtimeImmutableImage": image["runtimeImmutableImage"],
                }
                for image in release_images
            ]
            if isinstance(release_images, list)
            else None
        )
        if images != expected_images:
            raise AcceptanceEvidenceError(
                "published image report does not match the signed image inventory"
            )
    elif section == "identity":
        backup_job_uids = observations.get("backupJobUids")
        restore_job_uid = observations.get("restoreJobUid")
        if (
            set(observations)
            != {
                "installRevision",
                "restartObserved",
                "backupJobUids",
                "restoreJobUid",
                "restoreMarker",
                "jobClosureVerified",
            }
            or not isinstance(observations.get("installRevision"), int)
            or isinstance(observations.get("installRevision"), bool)
            or observations["installRevision"] < 1
            or observations.get("restartObserved") is not True
            or not isinstance(backup_job_uids, list)
            or len(backup_job_uids) != 2
            or any(
                not isinstance(uid, str)
                or not uid
                or any(
                    not character.isprintable() or character.isspace()
                    for character in uid
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
            or observations.get("restoreMarker") != "identity-smoke-marker"
            or observations.get("jobClosureVerified") is not True
        ):
            raise AcceptanceEvidenceError(
                "Identity install, restart, backup, or restore is incomplete"
            )
    elif section == "turn":
        if observations != {"frontendPath": "relayed", "backendPath": "relayed"}:
            raise AcceptanceEvidenceError(
                "TURN frontend and backend evidence is incomplete"
            )
    elif section == "restart":
        if observations != {
            "frontendUidChanged": True,
            "operatorUidChanged": True,
            "browserUidChanged": True,
            "unexpectedRestarts": 0,
        }:
            raise AcceptanceEvidenceError("required restart evidence is incomplete")
    elif section == "soak":
        identity_mode = observations.get("identityMode")
        monotonic_duration = observations.get("monotonicDurationMilliseconds")
        baseline = observations.get("baseline")
        samples = observations.get("samples")
        try:
            policy = ACCEPTANCE_SOAK.validate_policy(contract)
        except ACCEPTANCE_SOAK.SoakValidationError as exc:
            raise AcceptanceEvidenceError(str(exc)) from exc
        if (
            set(observations)
            != {
                "identityMode",
                "mutationMode",
                "monotonicDurationMilliseconds",
                "attemptId",
                "baseline",
                "samples",
            }
            or identity_mode != authentication_mode
            or observations.get("mutationMode") != "read-only"
            or not isinstance(monotonic_duration, int)
            or isinstance(monotonic_duration, bool)
            or not isinstance(baseline, dict)
            or not isinstance(samples, list)
            or not samples
            or not isinstance(workspace, dict)
            or not isinstance(workspace.get("id"), str)
        ):
            raise AcceptanceEvidenceError(
                "30 minute soak wall clock evidence is incomplete"
            )
        documents = _bound_soak_documents(
            observations=observations,
            source_records=source_records,
            canonical_kubeconfig=canonical_kubeconfig,
            context=context,
            workspace_id=workspace["id"],
            identity_mode=identity_mode,
        )
        observed_times = []
        elapsed_times = []
        for sequence, (sample, query_documents) in enumerate(zip(samples, documents)):
            if (
                not isinstance(sample, dict)
                or set(sample)
                != {
                    "sequence",
                    "observedAt",
                    "elapsedMilliseconds",
                    "queryBindings",
                }
                or sample.get("sequence") != sequence
            ):
                raise AcceptanceEvidenceError("soak sample schema is invalid")
            observed_at = _timestamp(sample["observedAt"], "soak sample observedAt")
            observed_times.append(observed_at)
            elapsed_times.append(sample.get("elapsedMilliseconds"))
            try:
                recomputed = ACCEPTANCE_SOAK.snapshot_sample(
                    query_documents,
                    workspace_id=workspace["id"],
                    identity_mode=identity_mode,
                    commit=commit,
                    deployment_run_id=deployment_run_id,
                    image_runtime_pairs=image_runtime_pairs,
                )
            except ACCEPTANCE_SOAK.SoakValidationError as exc:
                raise AcceptanceEvidenceError(str(exc)) from exc
            if sequence == 0:
                if recomputed != baseline:
                    raise AcceptanceEvidenceError(
                        "soak signed baseline does not match raw sources"
                    )
            elif recomputed != baseline:
                raise AcceptanceEvidenceError("soak raw snapshot drift is invalid")
        try:
            ACCEPTANCE_SOAK.validate_cadence(
                started=started,
                finished=finished,
                sample_times=observed_times,
                sample_elapsed_milliseconds=elapsed_times,
                monotonic_duration_milliseconds=monotonic_duration,
                policy=policy,
            )
        except ACCEPTANCE_SOAK.SoakValidationError as exc:
            raise AcceptanceEvidenceError(str(exc)) from exc
    elif section == "offlineOidcConformance":
        if (
            set(observations)
            != {
                "mode",
                "scope",
                "authenticationMode",
                "capabilities",
                "result",
                "projectName",
                "cleanupCommand",
                "cleaned",
                "runner",
                "sourceProvenance",
            }
            or observations.get("mode") != "offline"
            or observations.get("scope") != "provider-neutral-oidc-contract"
            or observations.get("authenticationMode") != "oidc-without-ldap"
            or observations.get("capabilities")
            != [
                "authorizationCodePkce",
                "jitProvisioning",
                "providerNeutralIssuer",
            ]
            or observations.get("result") != "passed"
        ):
            raise AcceptanceEvidenceError(
                "offline provider-neutral OIDC contract evidence is incomplete"
            )
        _validate_source_provenance(
            observations["sourceProvenance"],
            commit=commit,
            tree_digest_checks=5,
            source_commands=source_commands,
        )
        runner_evidence = observations["runner"]
        source_root = _validate_runner(
            runner_evidence, name="platform-conformance", commit=commit
        )
        commands = _all_source_commands(source_commands)
        if len(commands) != 2:
            raise AcceptanceEvidenceError("external OIDC conformance source is missing")
        command = next(
            (
                candidate
                for candidate in commands
                if candidate != observations["sourceProvenance"]["archiveCommand"]
            ),
            None,
        )
        if command is None:
            raise AcceptanceEvidenceError("external OIDC conformance source is missing")
        _validate_isolated_compose_run(
            name="platform-conformance",
            commit=commit,
            project_name=observations["projectName"],
            command=command,
            cleanup_command=observations["cleanupCommand"],
            cleaned=observations["cleaned"],
            runner_image_id=runner_evidence["imageId"],
            source_root=source_root,
        )
        if command[-1] != "product-conformance-test":
            raise AcceptanceEvidenceError("external OIDC conformance source is missing")
    elif section == "suites":
        runs = observations.get("runs")
        release_inputs = observations.get("releaseInputs")
        source_provenance = observations.get("sourceProvenance")
        if (
            not isinstance(release_inputs, dict)
            or set(release_inputs) != {"signedImageInventorySha256"}
            or FILE_DIGEST.fullmatch(
                release_inputs.get("signedImageInventorySha256", "")
            )
            is None
        ):
            raise AcceptanceEvidenceError(
                "signed suite release inventory evidence is incomplete"
            )
        suite_names = contract["requiredSuites"]
        _validate_source_provenance(
            source_provenance,
            commit=commit,
            tree_digest_checks=(len(suite_names) + 2) * 3 + 2,
            source_commands=source_commands,
        )
        run_digests = (
            [run.get("rawLogSha256") for run in runs if isinstance(run, dict)]
            if isinstance(runs, list)
            else []
        )
        if (
            observations.get("containerSuites") != suite_names
            or set(observations)
            != {"containerSuites", "runs", "releaseInputs", "sourceProvenance"}
            or not isinstance(runs, list)
            or len(runs) != 10
            or {run.get("name") for run in runs if isinstance(run, dict)}
            != {*suite_names, "docs-zh-Hant", "docs-en"}
            or len(_all_source_commands(source_commands)) != 11
            or source_digests != {source_provenance["archiveSha256"], *run_digests}
        ):
            raise AcceptanceEvidenceError(
                "container or docs suite evidence is incomplete"
            )
        for run in runs:
            required_keys = {
                "name",
                "command",
                "locale",
                "exitCode",
                "startedAt",
                "finishedAt",
                "rawLogSha256",
                "projectName",
                "cleanupCommand",
                "cleaned",
                "runner",
            }
            if run.get("name") == "docker":
                required_keys.add("preflightCommand")
            if run.get("name", "").startswith("docs-"):
                required_keys.add("linksVerified")
            expected_locale = {
                "docs-zh-Hant": "zh-Hant",
                "docs-en": "en",
            }.get(run.get("name"), "none")
            runner_evidence = run.get("runner")
            if (
                not isinstance(run, dict)
                or set(run) != required_keys
                or not isinstance(run["command"], list)
                or not run["command"]
                or not all(isinstance(item, str) and item for item in run["command"])
                or run["exitCode"] != 0
                or run["rawLogSha256"] not in source_digests
                or not _source_has_command(
                    source_commands, run["rawLogSha256"], run["command"]
                )
                or run["locale"] != expected_locale
                or (
                    run["name"].startswith("docs-")
                    and (run["linksVerified"] is not True)
                )
            ):
                raise AcceptanceEvidenceError("container or docs raw run is invalid")
            source_root = _validate_runner(
                runner_evidence, name=run["name"], commit=commit
            )
            _validate_isolated_compose_run(
                name=run["name"],
                commit=commit,
                project_name=run["projectName"],
                command=run["command"],
                cleanup_command=run["cleanupCommand"],
                cleaned=run["cleaned"],
                runner_image_id=runner_evidence["imageId"],
                source_root=source_root,
            )
            if run["name"] == "docker":
                preflight = run["preflightCommand"]
                expected_preflight = [
                    *HERMETIC_COMPOSE_ENVIRONMENT,
                    "docker",
                    "compose",
                    "--env-file",
                    str(Path(source_root) / ".env.example"),
                    "--project-name",
                    run["projectName"],
                    "--file",
                    str(Path(source_root) / "docker-compose.yml"),
                    "config",
                    "--quiet",
                ]
                if preflight != expected_preflight:
                    raise AcceptanceEvidenceError(
                        "root Compose quiet validation evidence is invalid"
                    )
            run_started = _timestamp(run["startedAt"], "suite startedAt")
            run_finished = _timestamp(run["finishedAt"], "suite finishedAt")
            if run_started > run_finished:
                raise AcceptanceEvidenceError("suite timestamp is invalid")
    else:
        raise AcceptanceEvidenceError(f"unknown acceptance report section: {section}")


def required_reports_for_mode(
    contract: dict[str, Any], authentication_mode: str
) -> list[str]:
    """Return the exact report set for one supported authentication mode."""

    common = contract.get("commonRequiredReports")
    mode_reports = contract.get("modeRequiredReports")
    producers = contract.get("requiredProducers")
    causal_edges = contract.get("causalEdges")
    causal_roots = contract.get("causalRoots")
    mode_terminals = contract.get("modeTerminalReports")
    cluster_scoped = contract.get("clusterScopedReports")
    workspace_scoped = contract.get("workspaceScopedReports")
    if (
        contract.get("contractVersion") != "aileron-homelab-acceptance/v11"
        or contract.get("reportSchemaVersion") != "aileron-acceptance-report/v9"
        or contract.get("producerVersion") != "6"
        or not isinstance(common, list)
        or not all(isinstance(section, str) and section for section in common)
        or not isinstance(mode_reports, dict)
        or set(mode_reports) != {"bundledKeycloak", "externalOidc"}
        or authentication_mode not in mode_reports
        or not all(
            isinstance(items, list)
            and all(isinstance(section, str) and section for section in items)
            for items in mode_reports.values()
        )
        or not isinstance(producers, dict)
        or not isinstance(causal_edges, list)
        or not isinstance(causal_roots, list)
        or not all(isinstance(section, str) and section for section in causal_roots)
        or not isinstance(mode_terminals, dict)
        or set(mode_terminals) != {"bundledKeycloak", "externalOidc"}
        or not all(
            isinstance(items, list)
            and all(isinstance(section, str) and section for section in items)
            for items in mode_terminals.values()
        )
        or not isinstance(cluster_scoped, list)
        or not isinstance(workspace_scoped, list)
        or not all(
            isinstance(section, str) and section
            for section in [*cluster_scoped, *workspace_scoped]
        )
    ):
        raise AcceptanceEvidenceError("acceptance contract is unsupported")
    try:
        ACCEPTANCE_SOAK.validate_policy(contract)
    except ACCEPTANCE_SOAK.SoakValidationError as exc:
        raise AcceptanceEvidenceError("acceptance contract is unsupported") from exc
    all_sections = [
        *common,
        *mode_reports["bundledKeycloak"],
        *mode_reports["externalOidc"],
    ]
    if (
        len(all_sections) != len(set(all_sections))
        or set(producers) != set(all_sections)
        or len([*cluster_scoped, *workspace_scoped])
        != len({*cluster_scoped, *workspace_scoped})
        or {*cluster_scoped, *workspace_scoped} != set(all_sections)
        or len(causal_roots) != len(set(causal_roots))
        or any(root not in producers for root in causal_roots)
        or any(
            not isinstance(edge, list)
            or len(edge) != 2
            or edge[0] == edge[1]
            or any(node not in producers for node in edge)
            for edge in causal_edges
        )
        or len({tuple(edge) for edge in causal_edges}) != len(causal_edges)
    ):
        raise AcceptanceEvidenceError("acceptance contract is unsupported")
    required = [*common, *mode_reports[authentication_mode]]
    if len(required) != len(set(required)):
        raise AcceptanceEvidenceError("acceptance report set is invalid")
    active = set(required)
    edges = [tuple(edge) for edge in causal_edges if set(edge) <= active]
    outgoing = {section: set() for section in active}
    incoming = {section: set() for section in active}
    for predecessor, successor in edges:
        outgoing[predecessor].add(successor)
        incoming[successor].add(predecessor)
    roots = {section for section in active if not incoming[section]}
    sinks = {section for section in active if not outgoing[section]}
    expected_roots = set(causal_roots)
    expected_sinks = set(mode_terminals[authentication_mode])
    if (
        not expected_roots
        or roots != expected_roots
        or not expected_sinks
        or sinks != expected_sinks
        or not expected_roots <= active
        or not expected_sinks <= active
    ):
        raise AcceptanceEvidenceError("acceptance causal graph is unsupported")

    def reachable(start: set[str], adjacency: dict[str, set[str]]) -> set[str]:
        observed = set(start)
        pending = list(start)
        while pending:
            node = pending.pop()
            for candidate in adjacency[node] - observed:
                observed.add(candidate)
                pending.append(candidate)
        return observed

    if (
        reachable(expected_roots, outgoing) != active
        or reachable(expected_sinks, incoming) != active
    ):
        raise AcceptanceEvidenceError("acceptance causal graph contains an orphan")
    indegree = {section: len(incoming[section]) for section in active}
    pending = [section for section, count in indegree.items() if count == 0]
    visited = 0
    while pending:
        node = pending.pop()
        visited += 1
        for successor in outgoing[node]:
            indegree[successor] -= 1
            if indegree[successor] == 0:
                pending.append(successor)
    if visited != len(active):
        raise AcceptanceEvidenceError("acceptance causal graph contains a cycle")
    return required


def report_scope(contract: dict[str, Any], section: str) -> str:
    """Return the declared evidence scope after validating the contract graph."""

    if section in contract.get("clusterScopedReports", []):
        return "cluster"
    if section in contract.get("workspaceScopedReports", []):
        return "workspace"
    raise AcceptanceEvidenceError("acceptance report scope is unsupported")


def immediate_predecessors(
    contract: dict[str, Any], section: str, authentication_mode: str
) -> tuple[str, ...]:
    """Return direct incoming causal edges that are active for one mode."""

    active = set(required_reports_for_mode(contract, authentication_mode))
    if section not in active:
        raise AcceptanceEvidenceError(
            f"acceptance report is not active for this mode: {section}"
        )
    return tuple(
        predecessor
        for predecessor, successor in contract["causalEdges"]
        if successor == section and predecessor in active
    )


def validate_report_bytes(
    *,
    raw: bytes,
    directory: Path,
    section: str,
    contract: dict[str, Any],
    expected_commit: str,
    epoch: dict[str, Any],
    signing_key: bytes,
    private_root: Path,
    canonical_kubeconfig: Path,
    workspace: dict[str, str] | None = None,
    now: datetime | None = None,
    must_finish_by: datetime | None = None,
) -> dict[str, Any]:
    """Validate canonical in-memory report bytes and every referenced source."""

    if not isinstance(raw, bytes) or len(raw) > 4 * 1024 * 1024:
        raise AcceptanceEvidenceError("report content must be canonical bytes")

    if section == "soak":
        try:
            canonical_kubeconfig_path = canonical_kubeconfig.resolve(strict=True)
            expected_kubeconfig_path = (directory / "kubeconfig").resolve(strict=True)
        except OSError as exc:
            raise AcceptanceEvidenceError(
                "canonical kubeconfig is unavailable"
            ) from exc
        if canonical_kubeconfig_path != expected_kubeconfig_path:
            raise AcceptanceEvidenceError(
                "canonical kubeconfig path does not match the report directory"
            )

    required = required_reports_for_mode(contract, epoch.get("authenticationMode"))
    if section not in required:
        raise AcceptanceEvidenceError(f"report is not active for this mode: {section}")
    scope = report_scope(contract, section)
    path = directory / f"{section}.json"
    report = _json(raw, f"{section} report")
    expected_report_keys = (
        BASE_REPORT_KEYS if scope == "cluster" else WORKSPACE_REPORT_KEYS
    )
    if set(report) != expected_report_keys:
        raise AcceptanceEvidenceError(f"report schema is invalid: {section}")
    signature = report.get("signature")
    unsigned = dict(report)
    unsigned.pop("signature", None)
    if (
        not isinstance(signature, str)
        or FILE_DIGEST.fullmatch(signature) is None
        or not hmac.compare_digest(
            signature,
            hmac.new(signing_key, _canonical(unsigned), hashlib.sha256).hexdigest(),
        )
    ):
        raise AcceptanceEvidenceError(f"report signature does not match: {section}")
    if (
        report["schemaVersion"] != contract["reportSchemaVersion"]
        or report["section"] != section
        or report["commit"] != expected_commit
        or report["deploymentRunId"] != epoch.get("deploymentRunId")
        or report["authenticationMode"] != epoch.get("authenticationMode")
        or (scope == "workspace" and report["workspace"] != workspace)
    ):
        raise AcceptanceEvidenceError(f"report identity does not match: {section}")
    producer = _identity(
        report["producer"], "producer", {"id", "executable", "version"}
    )
    probe = _identity(report["probe"], "probe", {"id", "kind"})
    if producer["id"] != contract["requiredProducers"].get(section):
        raise AcceptanceEvidenceError(f"report producer is not trusted: {section}")
    if producer["executable"] != contract["producerExecutable"]:
        raise AcceptanceEvidenceError(
            f"report producer executable is not trusted: {section}"
        )
    if producer["version"] != contract["producerVersion"]:
        raise AcceptanceEvidenceError(
            f"report producer version is not trusted: {section}"
        )
    expected_probe_kind = (
        "offline"
        if section == "offlineOidcConformance"
        else "container"
        if section == "suites"
        else "live"
    )
    if probe["kind"] != expected_probe_kind:
        raise AcceptanceEvidenceError(f"report probe kind is invalid: {section}")
    observed_now = now or datetime.now(timezone.utc)
    epoch_created = _timestamp(epoch.get("createdAt"), "deployment epoch createdAt")
    started = _timestamp(report["startedAt"], f"{section} startedAt")
    finished = _timestamp(report["finishedAt"], f"{section} finishedAt")
    if (
        started > finished
        or started < epoch_created
        or finished > observed_now
        or (observed_now - finished).total_seconds()
        > contract["maximumReportAgeSeconds"]
        or (must_finish_by is not None and finished > must_finish_by)
    ):
        raise AcceptanceEvidenceError(f"report freshness is invalid: {section}")
    sources = report["sources"]
    if not isinstance(sources, list) or not sources:
        raise AcceptanceEvidenceError(f"report source evidence is missing: {section}")
    source_digests: set[str] = set()
    source_commands: SourceCommands = {}
    source_references: set[tuple[str, str]] = set()
    source_records: list[dict[str, Any]] = []
    source_files: set[str] = set()
    for source in sources:
        expected_source_keys = {
            "file",
            "sha256",
            "command",
            "exitCode",
            *(
                {"attemptId", "sampleSequence", "queryId"}
                if section == "soak"
                else set()
            ),
        }
        if not isinstance(source, dict) or set(source) != expected_source_keys:
            raise AcceptanceEvidenceError(f"report source is invalid: {section}")
        source_file = source["file"]
        if (
            not isinstance(source_file, str)
            or Path(source_file).name != source_file
            or FILE_DIGEST.fullmatch(source.get("sha256", "")) is None
            or not isinstance(source["command"], list)
            or not source["command"]
            or not all(isinstance(item, str) and item for item in source["command"])
            or source["exitCode"] != 0
        ):
            raise AcceptanceEvidenceError(f"report source is invalid: {section}")
        source_raw = PRIVATE_IO.read_private_bytes(
            directory / source_file,
            f"{section} source",
            private_root=private_root,
            error_type=AcceptanceEvidenceError,
            maximum_size=128 * 1024 * 1024,
        )
        source_digest = hashlib.sha256(source_raw).hexdigest()
        if source_digest != source["sha256"]:
            raise AcceptanceEvidenceError(
                f"report source SHA256 does not match: {section}"
            )
        if section == "soak" and source_file in source_files:
            raise AcceptanceEvidenceError("soak source file is duplicated")
        source_files.add(source_file)
        source_digests.add(source_digest)
        source_commands.setdefault(source_digest, []).append(source["command"])
        source_references.add((source_file, source_digest))
        source_records.append({**source, "raw": source_raw})
    image_runtime_pairs = None
    release_images = None
    if section in {"imageRelease", "soak"}:
        try:
            release_images = ACCEPTANCE_RELEASE.load_signed_image_inventory(
                path=(
                    private_root
                    / "install"
                    / expected_commit
                    / "signed-image-inventory.json"
                ),
                private_root=private_root,
                key=signing_key,
                context=epoch["context"],
                commit=expected_commit,
                cluster_uid=epoch["clusterUid"],
                installation_identity_sha256=(epoch["installationIdentitySha256"]),
            )
            if section == "soak":
                image_runtime_pairs = ACCEPTANCE_SOAK.release_image_runtime_pairs(
                    release_images
                )
        except (
            ACCEPTANCE_RELEASE.AcceptanceReleaseError,
            ACCEPTANCE_SOAK.SoakValidationError,
        ) as exc:
            raise AcceptanceEvidenceError(str(exc)) from exc
    _validate_observations(
        section,
        report["observations"],
        contract=contract,
        commit=expected_commit,
        deployment_run_id=epoch["deploymentRunId"],
        authentication_mode=epoch["authenticationMode"],
        workspace=workspace if scope == "workspace" else None,
        started=started,
        finished=finished,
        source_digests=source_digests,
        source_records=source_records,
        canonical_kubeconfig=canonical_kubeconfig,
        context=epoch["context"],
        source_commands=source_commands,
        source_references=source_references,
        reset_snapshot_sha256=epoch["resetSnapshotSha256"],
        image_runtime_pairs=image_runtime_pairs,
        release_images=release_images,
    )
    return {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "startedAt": report["startedAt"],
        "finishedAt": report["finishedAt"],
        "started": started,
        "finished": finished,
        "report": report,
    }


def validate_report_file(
    *,
    directory: Path,
    section: str,
    contract: dict[str, Any],
    expected_commit: str,
    epoch: dict[str, Any],
    signing_key: bytes,
    private_root: Path,
    canonical_kubeconfig: Path,
    workspace: dict[str, str] | None = None,
    now: datetime | None = None,
    must_finish_by: datetime | None = None,
) -> dict[str, Any]:
    """Read and validate one canonical report through the in-memory validator."""

    path = directory / f"{section}.json"
    raw = PRIVATE_IO.read_private_bytes(
        path,
        f"{section} report",
        private_root=private_root,
        error_type=AcceptanceEvidenceError,
        maximum_size=4 * 1024 * 1024,
    )
    return validate_report_bytes(
        raw=raw,
        directory=directory,
        section=section,
        contract=contract,
        expected_commit=expected_commit,
        epoch=epoch,
        signing_key=signing_key,
        private_root=private_root,
        canonical_kubeconfig=canonical_kubeconfig,
        workspace=workspace,
        now=now,
        must_finish_by=must_finish_by,
    )


def validate_evidence(
    expected_commit: str,
    deployment_run_id: str,
    contract_path: Path,
    *,
    context: str,
    canonical_kubeconfig: Path | None = None,
    runner: Any = ACCEPTANCE_CLUSTER._run_command,
    now: datetime | None = None,
) -> None:
    private_root = ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
    evidence_directory = PRIVATE_IO.evidence_directory(
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceEvidenceError,
    )
    PRIVATE_IO.validate_evidence_directory(
        evidence_directory,
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceEvidenceError,
    )
    canonical_snapshot = PRIVATE_IO.validate_canonical_kubeconfig(
        directory=evidence_directory,
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        context=context,
        error_type=AcceptanceEvidenceError,
    )
    if (
        canonical_kubeconfig is not None
        and canonical_kubeconfig != canonical_snapshot.path
    ):
        raise AcceptanceEvidenceError(
            "canonical kubeconfig path does not match the acceptance run"
        )
    kubeconfig = canonical_snapshot.path
    bundle_path = evidence_directory / DEFAULT_BUNDLE_NAME
    contract = load_canonical_contract(contract_path)
    bundle = _json(
        PRIVATE_IO.read_private_bytes(
            bundle_path,
            "acceptance bundle",
            private_root=private_root,
            error_type=AcceptanceEvidenceError,
            maximum_size=4 * 1024 * 1024,
        ),
        "acceptance bundle",
    )
    if set(bundle) != {
        "contractVersion",
        "commit",
        "deploymentRunId",
        "authenticationMode",
        "workspace",
        "epoch",
        "reports",
    }:
        raise AcceptanceEvidenceError("acceptance bundle shape is invalid")
    if (
        bundle["contractVersion"] != contract["contractVersion"]
        or bundle["commit"] != expected_commit
    ):
        raise AcceptanceEvidenceError(
            "acceptance bundle release identity does not match"
        )
    workspace = _identity(bundle["workspace"], "workspace", {"id", "userSubject"})
    try:
        trust = ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
            context=context, kubeconfig=kubeconfig, runner=runner
        )
    except ACCEPTANCE_CLUSTER.AcceptanceClusterError as exc:
        raise AcceptanceEvidenceError(
            "cluster acceptance trust root is invalid"
        ) from exc
    signing_key = trust.key
    epoch_reference = bundle["epoch"]
    if (
        not isinstance(epoch_reference, dict)
        or set(epoch_reference) != {"file", "sha256"}
        or epoch_reference.get("file") != ACCEPTANCE_EPOCH.EPOCH_NAME
        or FILE_DIGEST.fullmatch(epoch_reference.get("sha256", "")) is None
    ):
        raise AcceptanceEvidenceError("deployment epoch reference is invalid")
    epoch_raw = PRIVATE_IO.read_private_bytes(
        bundle_path.parent / ACCEPTANCE_EPOCH.EPOCH_NAME,
        "deployment epoch",
        private_root=private_root,
        error_type=AcceptanceEvidenceError,
        maximum_size=4 * 1024 * 1024,
    )
    if hashlib.sha256(epoch_raw).hexdigest() != epoch_reference["sha256"]:
        raise AcceptanceEvidenceError("deployment epoch SHA256 does not match")
    try:
        epoch = ACCEPTANCE_EPOCH.load_deployment_epoch(
            directory=bundle_path.parent,
            private_root=private_root,
            key=signing_key,
            commit=expected_commit,
            cluster_uid=trust.cluster_uid,
            context=context,
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=deployment_run_id,
        )
        ACCEPTANCE_SNAPSHOT.load_reset_snapshot(
            directory=bundle_path.parent,
            private_root=private_root,
            key=signing_key,
            context=context,
            commit=expected_commit,
            cluster_uid=trust.cluster_uid,
            installation_identity_sha256=trust.installation_identity_sha256,
            expected_run_id=epoch["deploymentRunId"],
            expected_snapshot_sha256=epoch["resetSnapshotSha256"],
        )
    except (
        ACCEPTANCE_EPOCH.AcceptanceEpochError,
        ACCEPTANCE_SNAPSHOT.AcceptanceSnapshotError,
    ) as exc:
        raise AcceptanceEvidenceError(str(exc)) from exc
    if (
        bundle["deploymentRunId"] != epoch["deploymentRunId"]
        or bundle["deploymentRunId"] != deployment_run_id
        or bundle["authenticationMode"] != epoch["authenticationMode"]
    ):
        raise AcceptanceEvidenceError("acceptance bundle epoch identity does not match")
    required = required_reports_for_mode(contract, epoch["authenticationMode"])
    reports = bundle.get("reports")
    if not isinstance(reports, dict) or set(reports) != set(required):
        raise AcceptanceEvidenceError(
            "acceptance bundle must contain the exact required reports"
        )

    observed_now = now or datetime.now(timezone.utc)
    epoch_created = _timestamp(epoch["createdAt"], "deployment epoch createdAt")
    if epoch_created > observed_now:
        raise AcceptanceEvidenceError("deployment epoch timestamp is in the future")
    report_intervals: dict[str, tuple[datetime, datetime]] = {}
    for section in required:
        reference = reports[section]
        if (
            not isinstance(reference, dict)
            or set(reference) != {"file", "sha256"}
            or reference.get("file") != f"{section}.json"
            or FILE_DIGEST.fullmatch(reference.get("sha256", "")) is None
        ):
            raise AcceptanceEvidenceError(f"report reference is invalid: {section}")
        validated = validate_report_file(
            directory=bundle_path.parent,
            section=section,
            contract=contract,
            expected_commit=expected_commit,
            epoch=epoch,
            signing_key=signing_key,
            private_root=private_root,
            canonical_kubeconfig=kubeconfig,
            workspace=workspace,
            now=observed_now,
        )
        if validated["sha256"] != reference["sha256"]:
            raise AcceptanceEvidenceError(f"report SHA256 does not match: {section}")
        report_intervals[section] = (
            validated["started"],
            validated["finished"],
        )
    for predecessor, successor in contract["causalEdges"]:
        if predecessor not in report_intervals or successor not in report_intervals:
            continue
        if report_intervals[predecessor][1] > report_intervals[successor][0]:
            raise AcceptanceEvidenceError(
                f"acceptance causal edge is violated: {predecessor} -> {successor}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--deployment-run-id", required=True)
    parser.add_argument("--context", required=True)
    return parser


def main() -> int:
    parser = build_parser()
    arguments = parser.parse_args()
    try:
        validate_evidence(
            arguments.expected_commit,
            arguments.deployment_run_id,
            DEFAULT_CONTRACT,
            context=arguments.context,
        )
    except AcceptanceEvidenceError as exc:
        parser.error(str(exc))
    print("deployment=passed")
    print(f"commit={arguments.expected_commit}")
    print(f"deploymentRunId={arguments.deployment_run_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
