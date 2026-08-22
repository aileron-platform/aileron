from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ORACLE_PATH = ROOT / "workspace-manager/scripts/acceptance_oracle.py"
OPERATOR_TEMPLATE = ROOT / "helm/aileron/templates/workspace-operator-deployment.yaml"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Runner:
    def __init__(self, results: dict[tuple[str, ...], tuple[int, str, str]]):
        self.results = results
        self.commands: list[list[str]] = []

    def run(self, command: list[str]):
        self.commands.append(command)
        return self.results[tuple(command)]


def _arguments(section: str) -> argparse.Namespace:
    return argparse.Namespace(
        section=section,
        context="rke2-homelab",
        workspace_id="workspace-1",
        platform_url="https://apps.example.tw",
        issuer_url="https://identity.example.tw/realms/aileron",
        client_id="aileron-client",
        commit="a" * 40,
        run_id="run-20260808",
    )


def _workspace_operator_component() -> str:
    source = OPERATOR_TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r'componentLabels.*"component" "([^"]+)"', source)
    assert match is not None
    return match.group(1)


def test_cli_has_only_typed_targets_and_no_observation_or_command() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_cli")
    parser = oracle.create_parser()
    actions = {action.dest: action for action in parser._actions}

    assert "command" not in actions
    assert "observation" not in actions
    assert "raw_result" not in actions
    assert "kubeconfig" not in actions
    assert actions["section"].choices == oracle.SECTIONS
    with pytest.raises(SystemExit):
        parser.parse_args(["--section", "http", "--command", "true"])


class KubernetesClient:
    def __init__(self, documents: dict[str, dict]):
        self.documents = documents
        self.paths: list[str] = []

    def get(self, path: str) -> dict:
        self.paths.append(path)
        return self.documents[path]


class LifecycleKubernetesClient:
    def __init__(self, pod_snapshots: list[dict]):
        self.pod_snapshots = list(pod_snapshots)
        self.patches: list[tuple[str, dict]] = []
        self.deletes: list[str] = []

    def get(self, path: str) -> dict:
        assert path.startswith("/api/v1/namespaces/workspace-system/pods?")
        return self.pod_snapshots.pop(0)

    def patch(self, path: str, document: dict) -> dict:
        self.patches.append((path, document))
        return {"metadata": {"generation": 2}}

    def delete(self, path: str) -> dict:
        self.deletes.append(path)
        return {"status": "Success"}


def test_image_release_uses_fixed_in_cluster_api_path() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_image_release")
    args = _arguments("imageRelease")
    inventory = "\n".join(
        (
            f"{component}\tlinux/amd64\t{args.commit}\t"
            f"registry.example/{component}@sha256:{index:064x}\t"
            f"registry.example/{component}@sha256:{index + 100:064x}"
        )
        for index, component in enumerate(sorted(oracle.IMAGE_COMPONENTS), start=1)
    )
    path = (
        "/api/v1/namespaces/workspace-system/configmaps/aileron-image-release-inventory"
    )
    kubernetes = KubernetesClient({path: {"data": {"images.tsv": inventory}}})

    observation = oracle.run_section(
        args, Runner({}), kubernetes, source_commit_reader=lambda: args.commit
    )

    assert len(observation["images"]) == 11
    assert set(observation["images"][0]) == {
        "component",
        "platform",
        "revision",
        "immutableImage",
        "runtimeImmutableImage",
    }
    assert kubernetes.paths == [path]


def test_image_release_accepts_inventory_without_optional_platform_redis() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_image_release_external_redis")
    args = _arguments("imageRelease")
    components = sorted(oracle.IMAGE_COMPONENTS - {"platform-redis"})
    inventory = "\n".join(
        (
            f"{component}\tlinux/amd64\t{args.commit}\t"
            f"registry.example/{component}@sha256:{index:064x}\t"
            f"registry.example/{component}@sha256:{index + 100:064x}"
        )
        for index, component in enumerate(components, start=1)
    )
    path = (
        "/api/v1/namespaces/workspace-system/configmaps/"
        "aileron-image-release-inventory"
    )

    observation = oracle.run_section(
        args,
        Runner({}),
        KubernetesClient({path: {"data": {"images.tsv": inventory}}}),
        source_commit_reader=lambda: args.commit,
    )

    assert {image["component"] for image in observation["images"]} == set(components)


def test_image_release_rejects_inventory_without_required_component() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_image_release_missing_required")
    args = _arguments("imageRelease")
    components = sorted(oracle.IMAGE_COMPONENTS - {"platform-coturn"})
    inventory = "\n".join(
        (
            f"{component}\tlinux/amd64\t{args.commit}\t"
            f"registry.example/{component}@sha256:{index:064x}\t"
            f"registry.example/{component}@sha256:{index + 100:064x}"
        )
        for index, component in enumerate(components, start=1)
    )
    path = (
        "/api/v1/namespaces/workspace-system/configmaps/"
        "aileron-image-release-inventory"
    )

    with pytest.raises(oracle.OracleError, match="component set is incomplete"):
        oracle.run_section(
            args,
            Runner({}),
            KubernetesClient({path: {"data": {"images.tsv": inventory}}}),
            source_commit_reader=lambda: args.commit,
        )


@pytest.mark.parametrize("attack", ["legacy-single-digest", "foreign-runtime-repo"])
def test_image_release_rejects_incomplete_runtime_image_binding(attack: str) -> None:
    oracle = _load(ORACLE_PATH, f"acceptance_oracle_image_release_{attack}")
    args = _arguments("imageRelease")
    rows = []
    for index, component in enumerate(sorted(oracle.IMAGE_COMPONENTS), start=1):
        immutable_image = f"registry.example/{component}@sha256:{index:064x}"
        if attack == "legacy-single-digest":
            rows.append(f"{component}\tlinux/amd64\t{args.commit}\tsha256:{index:064x}")
            continue
        runtime_image = (
            f"registry.example/foreign@sha256:{index + 100:064x}"
            if index == 1
            else f"registry.example/{component}@sha256:{index + 100:064x}"
        )
        rows.append(
            f"{component}\tlinux/amd64\t{args.commit}\t"
            f"{immutable_image}\t{runtime_image}"
        )
    path = (
        "/api/v1/namespaces/workspace-system/configmaps/aileron-image-release-inventory"
    )

    with pytest.raises(oracle.OracleError, match="image release raw"):
        oracle.run_section(
            args,
            Runner({}),
            KubernetesClient({path: {"data": {"images.tsv": "\n".join(rows)}}}),
            source_commit_reader=lambda: args.commit,
        )


def test_identity_uses_keycloak_deployment_and_ready_rollout_status() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_identity_deployment")
    args = _arguments("identity")
    smoke_report = {
        "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
        "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
        "restoreJobUid": "restore-job-uid",
        "restoreMarker": "identity-smoke-marker",
        "jobClosureVerified": True,
    }
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
    kubernetes = KubernetesClient(
        {
            paths[0]: {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "aileron-identity-keycloak",
                    "namespace": "aileron-identity-system",
                    "generation": 2,
                },
                "status": {
                    "observedGeneration": 2,
                    "replicas": 1,
                    "updatedReplicas": 1,
                    "readyReplicas": 1,
                    "availableReplicas": 1,
                },
            },
            paths[1]: {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "aileron-identity-restore-marker",
                    "namespace": "aileron-identity-system",
                    "labels": {
                        "platform.aileron.dev/acceptance-owner": "aileron-installer",
                        "platform.aileron.dev/acceptance-run-id": args.run_id,
                        "platform.aileron.dev/source-commit": args.commit,
                    },
                },
                "data": {
                    "marker": "identity-smoke-marker",
                    "commit": args.commit,
                    "runId": args.run_id,
                    "smokeReport": json.dumps(
                        smoke_report, separators=(",", ":"), sort_keys=True
                    ),
                },
            },
        }
    )

    assert oracle.run_section(
        args,
        Runner({}),
        kubernetes,
        source_commit_reader=lambda: args.commit,
    ) == {
        "installRevision": 2,
        "restartObserved": True,
        "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
        "restoreJobUid": "restore-job-uid",
        "restoreMarker": "identity-smoke-marker",
        "jobClosureVerified": True,
    }
    assert kubernetes.paths == paths


@pytest.mark.parametrize("invalid_uid", [" ", "restore\njob", "restore\x00job"])
def test_identity_rejects_marker_job_uids_with_whitespace_or_control_characters(
    invalid_uid: str,
) -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_identity_invalid_uid")
    args = _arguments("identity")
    deployment_path = (
        "/apis/apps/v1/namespaces/aileron-identity-system/deployments/"
        "aileron-identity-keycloak"
    )
    marker_path = (
        "/api/v1/namespaces/aileron-identity-system/configmaps/"
        "aileron-identity-restore-marker"
    )
    smoke_report = {
        "schemaVersion": "aileron-identity-backup-restore-smoke/v1",
        "backupJobUids": ["backup-job-uid-1", "backup-job-uid-2"],
        "restoreJobUid": invalid_uid,
        "restoreMarker": "identity-smoke-marker",
        "jobClosureVerified": True,
    }
    kubernetes = KubernetesClient(
        {
            deployment_path: {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "aileron-identity-keycloak",
                    "namespace": "aileron-identity-system",
                    "generation": 1,
                },
                "status": {
                    "observedGeneration": 1,
                    "replicas": 1,
                    "updatedReplicas": 1,
                    "readyReplicas": 1,
                    "availableReplicas": 1,
                },
            },
            marker_path: {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "aileron-identity-restore-marker",
                    "namespace": "aileron-identity-system",
                    "labels": {
                        "platform.aileron.dev/acceptance-owner": "aileron-installer",
                        "platform.aileron.dev/acceptance-run-id": args.run_id,
                        "platform.aileron.dev/source-commit": args.commit,
                    },
                },
                "data": {
                    "marker": "identity-smoke-marker",
                    "commit": args.commit,
                    "runId": args.run_id,
                    "smokeReport": json.dumps(
                        smoke_report, separators=(",", ":"), sort_keys=True
                    ),
                },
            },
        }
    )

    with pytest.raises(oracle.OracleError, match="Identity raw install"):
        oracle.run_section(
            args,
            Runner({}),
            kubernetes,
            source_commit_reader=lambda: args.commit,
        )


def test_turn_oracle_requires_two_relay_candidates_from_fixed_probe() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_turn")
    args = _arguments("turn")
    commands = oracle.build_turn_commands(args)
    runner = Runner(
        {
            tuple(commands[0]): (0, "candidate:1 1 UDP 1 10.0.0.1 5000 typ relay", ""),
            tuple(commands[1]): (0, "candidate:2 1 UDP 1 10.0.0.2 5001 typ relay", ""),
        }
    )

    assert oracle.run_section(
        args, runner, source_commit_reader=lambda: args.commit
    ) == {
        "frontendPath": "relayed",
        "backendPath": "relayed",
    }


def test_restart_oracle_takes_before_snapshot_triggers_and_waits_for_new_uids() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_restart_lifecycle")
    args = _arguments("restart")

    operator_component = _workspace_operator_component()
    assert operator_component == "workspace-operator"

    def pods(suffix: str) -> dict:
        return {
            "items": [
                {
                    "metadata": {
                        "name": f"aileron-{component}-{suffix}",
                        "uid": f"{component}-{suffix}",
                        "labels": (
                            {
                                "aileron.io/component": "workspace-browser",
                                "aileron.io/workspace-id": args.workspace_id,
                            }
                            if component == "browser"
                            else {"app.kubernetes.io/component": component}
                        ),
                    },
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [{"restartCount": 0, "ready": True}],
                    },
                }
                for component in ("frontend", operator_component, "browser")
            ]
        }

    client = LifecycleKubernetesClient([pods("before"), pods("after")])
    observation = oracle.run_section(
        args,
        Runner({}),
        client,
        source_commit_reader=lambda: args.commit,
        lifecycle_sleeper=lambda _seconds: None,
    )

    assert observation == {
        "frontendUidChanged": True,
        "operatorUidChanged": True,
        "browserUidChanged": True,
        "unexpectedRestarts": 0,
    }
    assert [path for path, _document in client.patches] == [
        "/apis/apps/v1/namespaces/workspace-system/deployments/aileron-frontend",
        (
            "/apis/apps/v1/namespaces/workspace-system/deployments/"
            "aileron-workspace-operator"
        ),
    ]
    assert client.deletes == [
        "/api/v1/namespaces/workspace-system/pods/aileron-browser-before"
    ]


def test_restart_oracle_ignores_other_workspace_browser_pods() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_restart_workspace_scope")
    args = _arguments("restart")
    operator_component = _workspace_operator_component()

    def pod(component: str, suffix: str, workspace_id: str | None = None) -> dict:
        labels = (
            {"aileron.io/component": "workspace-browser"}
            if component == "browser"
            else {"app.kubernetes.io/component": component}
        )
        if workspace_id is not None:
            labels["aileron.io/workspace-id"] = workspace_id
        return {
            "metadata": {
                "name": f"aileron-{component}-{suffix}",
                "uid": f"{component}-{suffix}",
                "labels": labels,
            },
            "status": {
                "phase": "Running",
                "conditions": [{"type": "Ready", "status": "True"}],
                "containerStatuses": [{"restartCount": 0, "ready": True}],
            },
        }

    def pods(suffix: str) -> dict:
        return {
            "items": [
                pod("frontend", suffix),
                pod(operator_component, suffix),
                pod("browser", suffix, args.workspace_id),
                pod("browser", suffix, "workspace-2"),
            ]
        }

    client = LifecycleKubernetesClient([pods("before"), pods("after")])
    assert oracle.run_section(
        args,
        Runner({}),
        client,
        source_commit_reader=lambda: args.commit,
        lifecycle_sleeper=lambda _seconds: None,
    )["browserUidChanged"]


def test_workspace_manager_kubernetes_image_contains_oracle_and_commit_marker() -> None:
    dockerfile = (ROOT / "workspace-manager/Dockerfile").read_text()
    stages: dict[str, str] = {}
    current_stage: str | None = None
    for line in dockerfile.splitlines():
        if line.startswith("FROM ") and " AS " in line:
            current_stage = line.rsplit(" AS ", 1)[1]
            stages[current_stage] = ""
        if current_stage is not None:
            stages[current_stage] += line + "\n"

    full_scripts_copy = "COPY workspace-manager/scripts/ ./scripts/"
    assert {stage for stage, body in stages.items() if full_scripts_copy in body} == {
        "development",
        "production",
        "kubernetes",
    }
    script_stages = {"development", "production", "kubernetes"}
    assert all(
        body.count(full_scripts_copy) == (1 if stage in script_stages else 0)
        for stage, body in stages.items()
    )
    assert (
        "COPY workspace-manager/scripts/acceptance_oracle.py"
        not in stages["kubernetes"]
    )
    assert (
        "COPY workspace-manager/scripts/backend_storage_probe.py"
        not in stages["kubernetes"]
    )
    assert "/workspace-manager/acceptance/source-commit" in stages["kubernetes"]
    assert "kubernetes-client" not in stages["kubernetes"]


def test_interactive_identity_sections_are_owned_by_tracked_browser_probe() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_no_interactive_self_report")
    source = (ROOT / "frontend/e2e/homelab-acceptance.mjs").read_text()

    assert {
        "oidcWorkspace",
        "workspaceLifecycle",
        "adminDisableLogin",
        "offlineOidcConformance",
    }.isdisjoint(oracle.SECTIONS)
    assert "/api/v1/workspaces" in source
    assert "/.well-known/openid-configuration" in source
    assert "metadata.authorization_endpoint" in source
    assert "/protocol/openid-connect/auth" not in source
    assert "code_challenge" in source
    assert "code_challenge_method" in source
    assert "S256" in source
    assert "client_id" in source
    assert "/api/v1/oauth2/callback" in source
    assert "--admin-console-url" in source
    assert "options.adminConsoleUrl" in source
    assert "buildAdminConsoleUrl(options.issuerUrl, options.adminConsoleUrl)" in source
    assert "disabledUser" not in source
    assert "kc_locale" in source
    assert "locale: 'en-US'" in source
    assert "document.documentElement.lang" in source
    assert "/admin/realms/" not in source
    assert "enabled: false" not in source
    assert "browser.newContext()" in source
    assert "/api/v1/oauth2/session" in source
    assert "X-CSRF-Token" in source
    assert "workspaceLifecycle" in source
    assert "/components/${component}/restart" in source
    assert "/stop" in source
    assert "/start" in source
    assert "availability.availability === 'stopped'" in source
    assert "availability.availability === 'ready'" in source


def test_oracle_fails_closed_when_image_commit_marker_is_missing() -> None:
    oracle = _load(ORACLE_PATH, "acceptance_oracle_missing_commit")
    args = _arguments("turn")

    with pytest.raises(oracle.OracleError, match="source commit marker is unavailable"):
        oracle.run_section(
            args,
            Runner({}),
            source_commit_reader=lambda: None,
        )
