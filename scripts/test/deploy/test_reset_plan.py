from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import stat
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "deploy" / "rke2" / "reset_plan.py"
SPEC = importlib.util.spec_from_file_location("reset_plan", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

CONTEXT = "rke2-homelab"
KUBECONFIG = Path("/private/rke2-homelab.yaml")
RESET_RUN_ID = "run-20260808"
SNAPSHOT_SHA256 = "a" * 64
COMMIT = "b" * 40
REAL_LOAD_SIGNED_BACKEND_INPUTS = MODULE._load_signed_backend_inputs
REAL_VERIFY_RESET_CAUSAL_ROOTS = MODULE._verify_reset_causal_roots
ROOT_VALIDATED_AT = "2026-08-08T07:00:00Z"
ROOT_RECEIPT = {
    "validatedAt": ROOT_VALIDATED_AT,
    "suites": {"sha256": "3" * 64, "finishedAt": "2026-08-08T07:00:00Z"},
    "offlineOidcConformance": {
        "sha256": "4" * 64,
        "finishedAt": "2026-08-08T07:00:00Z",
    },
}


@pytest.fixture(autouse=True)
def _backend_cleanup_contract(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    calls: dict[str, list] = {"loads": [], "executions": [], "writes": []}
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        lambda **_kwargs: deepcopy(ROOT_RECEIPT),
    )

    def load_inputs(
        *,
        plan: dict,
        kubeconfig: Path,
        expected_commit: str,
        reset_snapshot_sha256: str,
    ) -> SimpleNamespace:
        targets = tuple(
            SimpleNamespace(
                persistent_volume_name=item["name"],
                persistent_volume_uid=item["uid"],
                locator_sha256=MODULE.BACKEND_ATTESTOR.locator_sha256(
                    item["backendLocator"]
                ),
            )
            for item in plan["persistentVolumes"]
        )
        inputs = SimpleNamespace(
            cleanup_targets=targets,
            commit=expected_commit,
            run_id=plan["resetRunId"],
            snapshot_sha256=reset_snapshot_sha256,
            context=plan["context"],
            kubeconfig=kubeconfig,
            private_root=Path("/private"),
            profile=SimpleNamespace(
                raw_sha256="c" * 64,
                canonical_sha256="d" * 64,
            ),
            image=SimpleNamespace(inventory_sha256="e" * 64),
        )
        calls["loads"].append(inputs)
        return inputs

    def target_result(
        inputs: SimpleNamespace,
        *,
        persistent_volume_name: str,
        persistent_volume_uid: str,
    ) -> dict:
        target = next(
            target
            for target in inputs.cleanup_targets
            if target.persistent_volume_name == persistent_volume_name
            and target.persistent_volume_uid == persistent_volume_uid
        )
        result = {
            "persistentVolume": {
                "name": persistent_volume_name,
                "uid": persistent_volume_uid,
            },
            "locatorSha256": target.locator_sha256,
            "cleanupResultSha256": "1" * 64,
            "verificationResultSha256": "2" * 64,
            "attestation": {"absent": True},
        }
        calls["executions"].append((persistent_volume_name, persistent_volume_uid))
        return result

    def validate_target(
        result: dict,
        *,
        inputs: SimpleNamespace,
        persistent_volume_name: str,
        persistent_volume_uid: str,
    ) -> dict:
        target = next(
            target
            for target in inputs.cleanup_targets
            if target.persistent_volume_name == persistent_volume_name
            and target.persistent_volume_uid == persistent_volume_uid
        )
        if (
            not isinstance(result, dict)
            or result.get("persistentVolume")
            != {"name": persistent_volume_name, "uid": persistent_volume_uid}
            or result.get("locatorSha256") != target.locator_sha256
            or result.get("attestation", {}).get("absent") is not True
        ):
            raise ValueError("fake backend cleanup target validation failed")
        return deepcopy(result)

    def validate_aggregate(document: dict, *, inputs: SimpleNamespace) -> dict:
        if not isinstance(document, dict) or not isinstance(
            document.get("results"), list
        ):
            raise ValueError("fake backend cleanup aggregate validation failed")
        expected = [
            (target.persistent_volume_name, target.persistent_volume_uid)
            for target in inputs.cleanup_targets
        ]
        observed = [
            (
                result["persistentVolume"]["name"],
                result["persistentVolume"]["uid"],
            )
            for result in document["results"]
        ]
        if observed != expected or document.get("allAbsent") is not True:
            raise ValueError("fake backend cleanup aggregate validation failed")
        return deepcopy(document)

    def write_aggregate(
        *,
        inputs: SimpleNamespace,
        execution_state_path: Path,
        aggregate: dict,
    ) -> tuple[dict, str]:
        del inputs
        path = execution_state_path.with_name("backend-cleanup-results.json")
        content = MODULE._canonical_bytes(aggregate) + b"\n"
        if path.exists():
            if path.read_bytes() != content:
                raise ValueError("fake backend cleanup aggregate changed")
        else:
            path.write_bytes(content)
            path.chmod(0o600)
        calls["writes"].append(path)
        return deepcopy(aggregate), hashlib.sha256(content).hexdigest()

    def load_aggregate(inputs: SimpleNamespace) -> dict:
        if not calls["writes"]:
            raise ValueError("fake backend cleanup aggregate is missing")
        path = calls["writes"][-1]
        if not path.exists():
            raise ValueError("fake backend cleanup aggregate is missing")
        raw = path.read_bytes()
        try:
            document = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("fake backend cleanup aggregate is invalid") from exc
        if raw != MODULE._canonical_bytes(document) + b"\n":
            raise ValueError("fake backend cleanup aggregate is not canonical")
        return validate_aggregate(document, inputs=inputs)

    monkeypatch.setattr(MODULE, "_load_signed_backend_inputs", load_inputs)
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "execute_signed_backend_cleanup_target",
        target_result,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "validate_backend_cleanup_target_result",
        validate_target,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "validate_backend_cleanup_results",
        validate_aggregate,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "load_backend_cleanup_results",
        load_aggregate,
    )
    monkeypatch.setattr(MODULE, "_write_backend_cleanup_aggregate", write_aggregate)
    return calls


def test_cli_derives_all_reset_artifact_paths_from_signed_identity() -> None:
    parser = MODULE.build_parser()
    options = {option for action in parser._actions for option in action.option_strings}

    assert "--expected-commit" in options
    assert "--kubeconfig" in options
    assert "--expected-reset-run-id" in options
    assert "--expected-reset-snapshot-digest" in options
    assert "--acceptance-directory" not in options
    assert "--inventory-output" not in options
    assert "--execution-state-output" not in options
    assert "--execution-lock-file" not in options
    assert "--inventory" not in options
    assert not any(action.nargs == argparse.REMAINDER for action in parser._actions)


def test_invalid_cli_identity_creates_no_reset_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset_plan.py",
            "--expected-commit",
            COMMIT,
            "--expected-reset-run-id",
            "../escape",
            "--expected-reset-snapshot-digest",
            SNAPSHOT_SHA256,
            "--context",
            CONTEXT,
            "--kubeconfig",
            str(private_root / "kubeconfig"),
        ],
    )

    with pytest.raises(ValueError, match="run ID is invalid"):
        MODULE.main()

    assert list(private_root.iterdir()) == []


def test_reset_transaction_paths_are_derived_and_evidence_is_write_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    acceptance_directory = private_root / "evidence" / COMMIT / RESET_RUN_ID
    transaction_directory = private_root / "reset" / COMMIT / RESET_RUN_ID
    evidence_path = transaction_directory / "reset-execution-evidence.json"
    paths = MODULE._derive_reset_transaction_paths(
        expected_commit=COMMIT,
        expected_run_id=RESET_RUN_ID,
        expected_snapshot_digest=SNAPSHOT_SHA256,
        context=CONTEXT,
    )

    assert paths == MODULE.ResetTransactionPaths(
        acceptance_directory=acceptance_directory,
        transaction_directory=transaction_directory,
        inventory_output=evidence_path,
        execution_state=transaction_directory / "reset-execution-state.json",
        execution_lock=transaction_directory / "reset-execution-state.json.lock",
    )
    assert list(private_root.iterdir()) == []

    MODULE._prepare_reset_transaction_directory(transaction_directory)
    MODULE._write_approval_evidence(evidence_path, {"approved": True})
    MODULE._write_approval_evidence(evidence_path, {"approved": True})

    with pytest.raises(ValueError, match="content changed"):
        MODULE._write_approval_evidence(evidence_path, {"approved": False})

    assert json.loads(evidence_path.read_text()) == {"approved": True}


def test_main_uses_only_flattened_kubeconfig_snapshot_after_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    acceptance_directory = private_root / "evidence" / COMMIT / RESET_RUN_ID
    transaction_directory = private_root / "reset" / COMMIT / RESET_RUN_ID
    source_kubeconfig = private_root / "source-kubeconfig"
    flattened_kubeconfig = transaction_directory / (
        f"reset-kubeconfig-{RESET_RUN_ID}.flattened.json"
    )
    observed: dict[str, Path] = {}

    def snapshot_kubeconfig(**arguments) -> Path:
        observed["snapshotSource"] = arguments["source"]
        return flattened_kubeconfig

    def load_trust(*, context: str, kubeconfig: Path):
        observed["trustKubeconfig"] = kubeconfig
        return type(
            "Trust",
            (),
            {
                "key": b"k" * 32,
                "cluster_uid": "cluster-uid",
                "installation_identity_sha256": "c" * 64,
            },
        )()

    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        snapshot_kubeconfig,
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        load_trust,
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_arguments: {
            "runId": RESET_RUN_ID,
            "inventory": {
                "context": CONTEXT,
                "namespaces": [],
                "releases": [],
                "resources": [],
                "persistentVolumes": [],
            },
        },
    )
    monkeypatch.setattr(MODULE, "_write_approval_evidence", lambda *_args, **_kwargs: None)

    def execute(plan, *, kubeconfig: Path, **_arguments) -> None:
        observed["executeKubeconfig"] = kubeconfig

    monkeypatch.setattr(MODULE, "execute_reset_plan", execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset_plan.py",
            "--expected-commit",
            COMMIT,
            "--expected-reset-run-id",
            RESET_RUN_ID,
            "--expected-reset-snapshot-digest",
            SNAPSHOT_SHA256,
            "--context",
            CONTEXT,
            "--kubeconfig",
            str(source_kubeconfig),
            "--execute",
            "--confirm-delete-all-aileron-data",
        ],
    )

    assert MODULE.main() == 0
    assert observed == {
        "snapshotSource": source_kubeconfig,
        "trustKubeconfig": flattened_kubeconfig,
        "executeKubeconfig": flattened_kubeconfig,
    }


def test_main_resumes_after_approval_evidence_was_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    acceptance_directory = private_root / "evidence" / COMMIT / RESET_RUN_ID
    transaction_directory = private_root / "reset" / COMMIT / RESET_RUN_ID
    flattened_kubeconfig = transaction_directory / (
        f"reset-kubeconfig-{RESET_RUN_ID}.flattened.json"
    )
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT,
        "snapshot_self_contained_kubeconfig",
        lambda **_arguments: flattened_kubeconfig,
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        lambda **_arguments: SimpleNamespace(
            key=b"k" * 32,
            cluster_uid="cluster-uid",
            installation_identity_sha256="c" * 64,
        ),
    )
    clean_inventory = {
        "context": CONTEXT,
        "namespaces": [],
        "releases": [],
        "resources": [],
        "persistentVolumes": [],
    }
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_arguments: {
            "runId": RESET_RUN_ID,
            "inventory": deepcopy(clean_inventory),
        },
    )
    execute_calls: list[dict] = []

    def execute(_plan_document: dict, **arguments) -> None:
        execute_calls.append(arguments)
        if len(execute_calls) == 1:
            raise KeyboardInterrupt("crash after approval evidence")

    monkeypatch.setattr(MODULE, "execute_reset_plan", execute)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset_plan.py",
            "--expected-commit",
            COMMIT,
            "--expected-reset-run-id",
            RESET_RUN_ID,
            "--expected-reset-snapshot-digest",
            SNAPSHOT_SHA256,
            "--context",
            CONTEXT,
            "--kubeconfig",
            str(private_root / "source-kubeconfig"),
            "--execute",
            "--confirm-delete-all-aileron-data",
        ],
    )

    with pytest.raises(KeyboardInterrupt, match="after approval evidence"):
        MODULE.main()
    evidence_path = transaction_directory / "reset-execution-evidence.json"
    first_evidence = evidence_path.read_bytes()

    assert MODULE.main() == 0
    assert evidence_path.read_bytes() == first_evidence
    assert len(execute_calls) == 2
    assert all(call["expected_commit"] == COMMIT for call in execute_calls)


def test_execute_resumes_after_namespace_delete_completed_before_journal_commit(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    approved["namespaces"] = [approved["namespaces"][0]]
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    live = deepcopy(approved)
    state_path = tmp_path / "reset-execution-state.json"
    commands: list[list[str]] = []
    boundary = _inventory_runner(live, commands)

    def interrupted_runner(command: list[str]) -> str:
        result = boundary(command)
        if "patch" in command and "namespace" in command:
            live["namespaces"][0]["labels"] = {
                **live["namespaces"][0]["labels"],
                MODULE.NAMESPACE_RESET_UID_LABEL: "namespace-uid-workspace",
                MODULE.NAMESPACE_RESET_RUN_LABEL: RESET_RUN_ID,
            }
            live["namespaces"][0]["resourceVersion"] = "601"
        return result

    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    with pytest.raises(
        KeyboardInterrupt, match="crash after deleteNamespace/workspace-system"
    ):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=interrupted_runner,
            delete_client=_FakeDeleteClient(
                live,
                crash_action="deleteNamespace/workspace-system",
            ),
        )

    state_after_crash = json.loads(state_path.read_text())
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    assert state_after_crash["actions"]["deleteNamespace/workspace-system"] == {
        "status": "started"
    }

    resume_commands: list[list[str]] = []
    MODULE.execute_reset_plan(
        plan,
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(live, resume_commands),
        delete_client=_FakeDeleteClient(live),
    )

    completed = json.loads(state_path.read_text())
    assert completed["actions"]["deleteNamespace/workspace-system"] == {
        "status": "completed"
    }
    assert not any("delete" in command for command in resume_commands)


def test_execute_verifies_causal_roots_before_backend_or_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    root_checks: list[str] = []

    def reject_roots(**_kwargs):
        root_checks.append("checked")
        raise ValueError("reset causal root report is missing")

    def reject_backend(**_kwargs):
        raise AssertionError("backend verification started before causal roots")

    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        reject_roots,
        raising=False,
    )
    monkeypatch.setattr(MODULE, "_load_signed_backend_inputs", reject_backend)

    with pytest.raises(ValueError, match="causal root report"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=tmp_path / "reset-execution-state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
        )

    assert root_checks == ["checked"]


def test_reset_resume_is_bound_to_causal_root_report_digests(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = []
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"

    MODULE.execute_reset_plan(
        plan,
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(deepcopy(approved), []),
    )
    state = json.loads(state_path.read_text())
    assert state["causalRootReports"] == ROOT_RECEIPT

    drifted = deepcopy(ROOT_RECEIPT)
    drifted["suites"]["sha256"] = "5" * 64
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        lambda **_kwargs: drifted,
    )

    with pytest.raises(ValueError, match="causal root receipt"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
        )


def test_reset_partial_resume_after_report_age_uses_first_validation_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = [approved["namespaces"][0]]
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    live = deepcopy(approved)
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    first_validation = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    resumed_at = first_validation + timedelta(days=2)
    observed_checkpoints: list[datetime] = []

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        lambda **_kwargs: SimpleNamespace(
            key=b"k" * 32,
            cluster_uid="cluster-uid",
            installation_identity_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EPOCH,
        "load_deployment_epoch",
        lambda **_kwargs: {
            "deploymentRunId": RESET_RUN_ID,
            "authenticationMode": "bundledKeycloak",
            "resetSnapshotSha256": SNAPSHOT_SHA256,
            "createdAt": "2026-08-08T06:00:00Z",
        },
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "load_canonical_contract",
        lambda: {"maximumReportAgeSeconds": 86400},
    )

    def validate_report_file(*, section: str, now: datetime, **_kwargs):
        observed_checkpoints.append(now)
        if now > first_validation:
            raise MODULE.ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError(
                "causal root report expired"
            )
        return {
            "sha256": "3" * 64 if section == "suites" else "4" * 64,
            "finishedAt": ROOT_VALIDATED_AT,
        }

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_file",
        validate_report_file,
    )
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        REAL_VERIFY_RESET_CAUSAL_ROOTS,
    )

    with pytest.raises(
        KeyboardInterrupt,
        match="crash after guardNamespace/workspace-system",
    ):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardNamespace/workspace-system",
            ),
            clock=lambda: first_validation,
        )
    assert json.loads(state_path.read_text())["actions"][
        "guardNamespace/workspace-system"
    ] == {
        "status": "started",
    }
    with pytest.raises(KeyboardInterrupt, match="stop after root revalidation"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=lambda _command: (_ for _ in ()).throw(
                KeyboardInterrupt("stop after root revalidation")
            ),
            clock=lambda: resumed_at,
        )

    assert observed_checkpoints == [first_validation] * 4
    assert json.loads(state_path.read_text())["causalRootReports"] == ROOT_RECEIPT


def test_reset_all_pending_resume_after_report_age_revalidates_at_current_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _backend_cleanup_contract: dict[str, list],
) -> None:
    approved = _inventory()
    approved["namespaces"] = [approved["namespaces"][0]]
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    first_validation = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    resumed_at = first_validation + timedelta(days=2)
    observed_checkpoints: list[datetime] = []

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        lambda **_kwargs: SimpleNamespace(
            key=b"k" * 32,
            cluster_uid="cluster-uid",
            installation_identity_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EPOCH,
        "load_deployment_epoch",
        lambda **_kwargs: {
            "deploymentRunId": RESET_RUN_ID,
            "authenticationMode": "bundledKeycloak",
            "resetSnapshotSha256": SNAPSHOT_SHA256,
            "createdAt": "2026-08-08T06:00:00Z",
        },
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "load_canonical_contract",
        lambda: {"maximumReportAgeSeconds": 86400},
    )

    def validate_report_file(*, now: datetime, **_kwargs):
        observed_checkpoints.append(now)
        if now > first_validation:
            raise MODULE.ACCEPTANCE_EVIDENCE.AcceptanceEvidenceError(
                "causal root report expired"
            )
        return {"sha256": "3" * 64, "finishedAt": ROOT_VALIDATED_AT}

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_file",
        validate_report_file,
    )
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        REAL_VERIFY_RESET_CAUSAL_ROOTS,
    )
    write_evidence = MODULE._write_evidence

    def write_then_interrupt(path: Path, document: dict) -> None:
        write_evidence(path, document)
        raise KeyboardInterrupt("crash with all journals pending")

    monkeypatch.setattr(
        MODULE,
        "_write_evidence",
        write_then_interrupt,
    )

    with pytest.raises(KeyboardInterrupt, match="all journals pending"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
            clock=lambda: first_validation,
        )
    state_before_resume = state_path.read_bytes()
    state = json.loads(state_before_resume)
    assert state["actions"] == {
        "guardNamespace/workspace-system": {"status": "pending"},
        "deleteNamespace/workspace-system": {"status": "pending"},
    }
    assert state["backendCleanup"] == {
        "targets": [],
        "aggregate": {"status": "pending", "sha256": None},
    }
    monkeypatch.setattr(
        MODULE,
        "_write_evidence",
        write_evidence,
    )
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="causal root reports are invalid"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), commands),
            clock=lambda: resumed_at,
        )

    assert observed_checkpoints == [
        first_validation,
        first_validation,
        resumed_at,
    ]
    assert state_path.read_bytes() == state_before_resume
    assert commands == []
    assert _backend_cleanup_contract["executions"] == []
    assert _backend_cleanup_contract["writes"] == []


def test_reset_all_pending_resume_refreshes_receipt_before_live_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = [approved["namespaces"][0]]
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    first_validation = datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc)
    resumed_at = first_validation + timedelta(hours=1)
    observed_checkpoints: list[datetime] = []

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        lambda **_kwargs: SimpleNamespace(
            key=b"k" * 32,
            cluster_uid="cluster-uid",
            installation_identity_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EPOCH,
        "load_deployment_epoch",
        lambda **_kwargs: {
            "deploymentRunId": RESET_RUN_ID,
            "authenticationMode": "bundledKeycloak",
            "resetSnapshotSha256": SNAPSHOT_SHA256,
            "createdAt": "2026-08-08T06:00:00Z",
        },
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "load_canonical_contract",
        lambda: {"maximumReportAgeSeconds": 86400},
    )

    def validate_report_file(*, section: str, now: datetime, **_kwargs):
        observed_checkpoints.append(now)
        return {
            "sha256": "3" * 64 if section == "suites" else "4" * 64,
            "finishedAt": ROOT_VALIDATED_AT,
        }

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EVIDENCE,
        "validate_report_file",
        validate_report_file,
    )
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        REAL_VERIFY_RESET_CAUSAL_ROOTS,
    )
    write_evidence = MODULE._write_evidence

    def write_then_interrupt(path: Path, document: dict) -> None:
        write_evidence(path, document)
        raise KeyboardInterrupt("crash with all journals pending")

    monkeypatch.setattr(
        MODULE,
        "_write_evidence",
        write_then_interrupt,
    )

    with pytest.raises(KeyboardInterrupt, match="all journals pending"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
            clock=lambda: first_validation,
        )
    state_before_resume = state_path.read_bytes()
    monkeypatch.setattr(
        MODULE,
        "_write_evidence",
        write_evidence,
    )

    with pytest.raises(KeyboardInterrupt, match="stop before live inventory"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=lambda _command: (_ for _ in ()).throw(
                KeyboardInterrupt("stop before live inventory")
            ),
            clock=lambda: resumed_at,
        )

    refreshed = json.loads(state_path.read_text())
    assert state_path.read_bytes() != state_before_resume
    assert refreshed["causalRootReports"] == {
        **ROOT_RECEIPT,
        "validatedAt": "2026-08-08T08:00:00Z",
    }
    assert refreshed["actions"] == {
        "guardNamespace/workspace-system": {"status": "pending"},
        "deleteNamespace/workspace-system": {"status": "pending"},
    }
    assert refreshed["backendCleanup"] == {
        "targets": [],
        "aggregate": {"status": "pending", "sha256": None},
    }
    assert observed_checkpoints == [
        first_validation,
        first_validation,
        resumed_at,
        resumed_at,
    ]


@pytest.mark.parametrize(
    "invalid_receipt",
    (
        "noncanonical-validated-at",
        "noncanonical-finished-at",
        "finished-after-validated-at",
        "extra-key",
    ),
)
def test_reset_resume_rejects_invalid_causal_root_receipt_before_revalidation(
    invalid_receipt: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = []
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    MODULE.execute_reset_plan(
        plan,
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(deepcopy(approved), []),
    )
    state = json.loads(state_path.read_text())
    receipt = state["causalRootReports"]
    if invalid_receipt == "noncanonical-validated-at":
        receipt["validatedAt"] = "2026-08-08T07:00:00.000Z"
    elif invalid_receipt == "noncanonical-finished-at":
        receipt["suites"]["finishedAt"] = "2026-08-08T07:00:00.000Z"
    elif invalid_receipt == "finished-after-validated-at":
        receipt["suites"]["finishedAt"] = "2026-08-08T07:00:01Z"
    else:
        receipt["unexpected"] = "value"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    root_checks: list[str] = []

    def reject_untrusted_checkpoint(**_kwargs):
        root_checks.append("checked")
        raise AssertionError("causal root revalidation used an invalid checkpoint")

    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        reject_untrusted_checkpoint,
    )

    with pytest.raises(ValueError, match="reset causal root receipt"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
        )

    assert root_checks == []


def test_reset_resume_rejects_validation_checkpoint_before_deployment_epoch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = []
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    MODULE.execute_reset_plan(
        plan,
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(deepcopy(approved), []),
    )
    state = json.loads(state_path.read_text())
    receipt = state["causalRootReports"]
    receipt["validatedAt"] = "2026-08-08T05:00:00Z"
    for section in ("suites", "offlineOidcConformance"):
        receipt[section]["finishedAt"] = "2026-08-08T05:00:00Z"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    monkeypatch.setattr(
        MODULE.ACCEPTANCE_CLUSTER,
        "load_cluster_acceptance_key",
        lambda **_kwargs: SimpleNamespace(
            key=b"k" * 32,
            cluster_uid="cluster-uid",
            installation_identity_sha256="1" * 64,
        ),
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_EPOCH,
        "load_deployment_epoch",
        lambda **_kwargs: {
            "resetSnapshotSha256": SNAPSHOT_SHA256,
            "createdAt": "2026-08-08T06:00:00Z",
        },
    )
    monkeypatch.setattr(
        MODULE.ACCEPTANCE_SNAPSHOT,
        "load_reset_snapshot",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("snapshot validation started after invalid checkpoint")
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        REAL_VERIFY_RESET_CAUSAL_ROOTS,
    )

    with pytest.raises(ValueError, match="predates deployment epoch"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), []),
        )


def test_reset_resume_rejects_future_validation_checkpoint_before_causal_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = _inventory()
    approved["namespaces"] = []
    approved["releases"] = []
    approved["resources"] = []
    approved["persistentVolumes"] = []
    plan = MODULE.build_reset_plan(
        approved,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )
    state_path = tmp_path / "reset-execution-state.json"
    MODULE.execute_reset_plan(
        plan,
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(deepcopy(approved), []),
        clock=lambda: datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc),
    )
    state = json.loads(state_path.read_text())
    state["causalRootReports"]["validatedAt"] = "2026-08-08T08:00:00Z"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    root_checks: list[str] = []
    backend_checks: list[str] = []
    commands: list[list[str]] = []

    def reject_future_checkpoint(**_kwargs):
        root_checks.append("checked")
        raise AssertionError("causal root validation accepted a future checkpoint")

    def reject_backend_source(**_kwargs):
        backend_checks.append("checked")
        raise AssertionError("backend source loaded after a future checkpoint")

    monkeypatch.setattr(
        MODULE,
        "_verify_reset_causal_roots",
        reject_future_checkpoint,
    )
    monkeypatch.setattr(
        MODULE,
        "_load_signed_backend_inputs",
        reject_backend_source,
    )

    with pytest.raises(ValueError, match="future"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(deepcopy(approved), commands),
            clock=lambda: datetime(2026, 8, 8, 7, 0, tzinfo=timezone.utc),
        )

    assert root_checks == []
    assert backend_checks == []
    assert commands == []


def test_execute_rejects_symlink_execution_state_before_mutation(
    tmp_path: Path,
) -> None:
    inventory = _inventory()
    inventory["namespaces"] = []
    inventory["releases"] = []
    inventory["resources"] = []
    inventory["persistentVolumes"] = []
    target_directory = tmp_path / "operator-owned"
    target_directory.mkdir()
    target = target_directory / "reset-state.json"
    link_directory = tmp_path / "linked-state"
    link_directory.symlink_to(target_directory, target_is_directory=True)
    state_path = link_directory / "reset-state.json"
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="symbolic link"):
        MODULE.execute_reset_plan(
            _plan(inventory),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(inventory, commands),
        )

    assert not target.exists()
    assert commands == []


def test_second_executor_fails_before_any_cluster_command(tmp_path: Path) -> None:
    inventory = _inventory()
    state_path = tmp_path / "reset-state.json"
    lock_path = tmp_path / "reset-state.json.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    commands: list[list[str]] = []
    try:
        with pytest.raises(ValueError, match="another reset executor"):
            MODULE.execute_reset_plan(
                _plan(inventory),
                kubeconfig=KUBECONFIG,
                execution_state_path=state_path,
                execution_lock_path=lock_path,
                expected_commit=COMMIT,
                reset_snapshot_sha256=SNAPSHOT_SHA256,
                runner=_inventory_runner(inventory, commands),
            )
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)

    assert commands == []
    assert not state_path.exists()


def test_execute_creates_private_canonical_state_directory(tmp_path: Path) -> None:
    inventory = _inventory()
    inventory["namespaces"] = []
    inventory["releases"] = []
    inventory["resources"] = []
    inventory["persistentVolumes"] = []
    private_directory = tmp_path / "reset-private"

    MODULE.execute_reset_plan(
        _plan(inventory),
        kubeconfig=KUBECONFIG,
        execution_state_path=private_directory / "state.json",
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_inventory_runner(inventory, []),
    )

    assert stat.S_IMODE(private_directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((private_directory / "state.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((private_directory / "state.json.lock").stat().st_mode) == 0o600


def test_execute_rejects_non_private_state_directory_and_lock(
    tmp_path: Path,
) -> None:
    inventory = _inventory()
    unsafe_directory = tmp_path / "unsafe-state"
    unsafe_directory.mkdir(mode=0o755)
    unsafe_directory.chmod(0o755)
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="mode 0700"):
        MODULE.execute_reset_plan(
            _plan(inventory),
            kubeconfig=KUBECONFIG,
            execution_state_path=unsafe_directory / "state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(inventory, commands),
        )
    assert commands == []

    unsafe_directory.chmod(0o700)
    lock_path = unsafe_directory / "state.json.lock"
    lock_path.write_text("")
    lock_path.chmod(0o644)
    with pytest.raises(ValueError, match="mode 0600"):
        MODULE.execute_reset_plan(
            _plan(inventory),
            kubeconfig=KUBECONFIG,
            execution_state_path=unsafe_directory / "state.json",
            execution_lock_path=lock_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(inventory, commands),
        )
    assert commands == []


@pytest.mark.parametrize(
    "run_id",
    (
        "run-invalid-",
        "r" * 64,
        "run-" + "a" * 60,
        "run/invalid",
    ),
)
def test_plan_rejects_reset_run_id_that_is_not_kubernetes_label_safe(
    run_id: str,
) -> None:
    with pytest.raises(ValueError, match="reset run ID is invalid"):
        MODULE.build_reset_plan(
            _inventory(),
            kubeconfig=KUBECONFIG,
            reset_run_id=run_id,
        )


def test_plan_accepts_maximum_63_character_shared_run_id() -> None:
    run_id = "run-" + "a" * 59

    plan = MODULE.build_reset_plan(
        _inventory(),
        kubeconfig=KUBECONFIG,
        reset_run_id=run_id,
    )

    assert len(run_id) == 63
    assert plan["resetRunId"] == run_id


def test_reset_cli_contract_uses_the_shared_63_character_run_id_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_root = tmp_path / "private"
    private_root.mkdir(mode=0o700)
    monkeypatch.setattr(
        MODULE.PRIVATE_INPUT.INSTALLATION_STATE,
        "PRIVATE_ROOT",
        private_root,
    )
    maximum_run_id = "run-" + "a" * 59
    invalid_run_id = maximum_run_id + "a"

    def validate(run_id: str) -> MODULE.ResetTransactionPaths:
        return MODULE._derive_reset_transaction_paths(
            expected_commit=COMMIT,
            expected_run_id=run_id,
            expected_snapshot_digest=SNAPSHOT_SHA256,
            context=CONTEXT,
        )

    assert MODULE.RUN_ID_PATTERN.fullmatch(maximum_run_id) is not None
    assert validate(maximum_run_id).transaction_directory == (
        private_root / "reset" / COMMIT / maximum_run_id
    )
    assert MODULE.RUN_ID_PATTERN.fullmatch(invalid_run_id) is None
    with pytest.raises(ValueError, match="run ID is invalid"):
        validate(invalid_run_id)
    assert list(private_root.iterdir()) == []


def test_execute_rejects_invalid_backend_commit_before_creating_artifacts(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "private" / "reset-state.json"

    with pytest.raises(ValueError, match="cleanup commit is invalid"):
        MODULE.execute_reset_plan(
            _plan(_inventory()),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit="not-a-commit",
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=lambda _command: pytest.fail("cluster must not be queried"),
        )

    assert not state_path.parent.exists()


CRASH_BOUNDARY_ACTIONS = [
    "guardPersistentVolume/pv-orphan",
    "guardPersistentVolume/pv-workspace",
    "guardNamespace/aileron-turn-system",
    "guardNamespace/workspace-system",
    "requestDeletePersistentVolume/pv-orphan",
    "deleteWorkspace/workspace-system/workspace-example",
    "deleteNamespace/workspace-system",
    "deleteNamespace/aileron-turn-system",
    "waitPersistentVolumeAbsent/pv-orphan",
    "waitPersistentVolumeAbsent/pv-workspace",
]


@pytest.mark.parametrize("crash_action", CRASH_BOUNDARY_ACTIONS)
def test_execute_resumes_every_typed_action_crash_boundary(
    crash_action: str, tmp_path: Path
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"
    commands: list[list[str]] = []

    with pytest.raises(KeyboardInterrupt, match="crash after"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                commands,
                crash_action=crash_action,
            ),
            delete_client=_FakeDeleteClient(
                live,
                crash_action=crash_action,
            ),
        )

    interrupted_state = json.loads(state_path.read_text())
    assert interrupted_state["backendCleanup"]["aggregate"] == {
        "status": "pending",
        "sha256": None,
    }

    resume_commands: list[list[str]] = []
    MODULE.execute_reset_plan(
        _plan(approved),
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(live, resume_commands),
        delete_client=_FakeDeleteClient(live),
    )

    state = json.loads(state_path.read_text())
    assert {item["status"] for item in state["actions"].values()} == {"completed"}


def test_signed_backend_preconditions_fail_before_any_kubernetes_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    kubernetes_commands: list[list[str]] = []
    precondition_calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        MODULE,
        "_load_signed_backend_inputs",
        REAL_LOAD_SIGNED_BACKEND_INPUTS,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "load_signed_backend_attestor_inputs",
        lambda **_arguments: inputs,
    )

    def reject_preconditions(observed: SimpleNamespace) -> None:
        precondition_calls.append(observed)
        raise ValueError("signed backend preconditions failed")

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "validate_signed_backend_cleanup_preconditions",
        reject_preconditions,
    )
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(ValueError, match="backend preconditions failed"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=lambda command: kubernetes_commands.append(command) or "",
        )

    assert precondition_calls == [inputs]
    assert kubernetes_commands == []
    assert not state_path.exists()


def test_signed_backend_target_mismatch_fails_before_preconditions_and_kubernetes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    mismatched_inputs = SimpleNamespace(
        **{
            **vars(inputs),
            "cleanup_targets": tuple(reversed(inputs.cleanup_targets)),
        }
    )
    kubernetes_commands: list[list[str]] = []
    precondition_calls: list[SimpleNamespace] = []
    monkeypatch.setattr(
        MODULE,
        "_load_signed_backend_inputs",
        REAL_LOAD_SIGNED_BACKEND_INPUTS,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "load_signed_backend_attestor_inputs",
        lambda **_arguments: mismatched_inputs,
    )
    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "validate_signed_backend_cleanup_preconditions",
        lambda observed: precondition_calls.append(observed),
    )
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(ValueError, match="target set does not match"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=lambda command: kubernetes_commands.append(command) or "",
        )

    assert precondition_calls == []
    assert kubernetes_commands == []
    assert not state_path.exists()


def test_backend_cleanup_starts_only_after_authoritative_kubernetes_absence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _backend_cleanup_contract: dict[str, list],
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    observed_live_inventories: list[dict] = []
    observed_calls: list[tuple[str, str]] = []
    execute_target = MODULE.BACKEND_ATTESTOR.execute_signed_backend_cleanup_target

    def observe_backend_cleanup(
        inputs: SimpleNamespace,
        *,
        persistent_volume_name: str,
        persistent_volume_uid: str,
    ) -> dict:
        observed_live_inventories.append(deepcopy(live))
        observed_calls.append((persistent_volume_name, persistent_volume_uid))
        return execute_target(
            inputs,
            persistent_volume_name=persistent_volume_name,
            persistent_volume_uid=persistent_volume_uid,
        )

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "execute_signed_backend_cleanup_target",
        observe_backend_cleanup,
    )
    MODULE.execute_reset_plan(
        _plan(approved),
        kubeconfig=KUBECONFIG,
        execution_state_path=tmp_path / "reset-state.json",
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(live, []),
        delete_client=_FakeDeleteClient(live),
    )

    assert observed_calls == [
        ("pv-orphan", "pv-uid-0"),
        ("pv-workspace", "pv-uid-1"),
    ]
    assert all(
        all(not inventory[key] for key in MODULE.RESET_INVENTORY_KEYS)
        for inventory in observed_live_inventories
    )
    assert _backend_cleanup_contract["executions"] == observed_calls


def test_backend_cleanup_resumes_completed_target_and_retries_started_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _backend_cleanup_contract: dict[str, list],
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)
    execute_target = MODULE.BACKEND_ATTESTOR.execute_signed_backend_cleanup_target
    attempts: list[tuple[str, str]] = []

    def interrupt_second_target(
        observed_inputs: SimpleNamespace,
        *,
        persistent_volume_name: str,
        persistent_volume_uid: str,
    ) -> dict:
        identity = (persistent_volume_name, persistent_volume_uid)
        attempts.append(identity)
        if persistent_volume_name == "pv-workspace":
            raise KeyboardInterrupt("crash during second backend target")
        return execute_target(
            observed_inputs,
            persistent_volume_name=persistent_volume_name,
            persistent_volume_uid=persistent_volume_uid,
        )

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "execute_signed_backend_cleanup_target",
        interrupt_second_target,
    )
    with pytest.raises(KeyboardInterrupt, match="second backend target"):
        MODULE._execute_backend_cleanup(
            inputs=inputs,
            state=state,
            execution_state_path=state_path,
        )

    interrupted = json.loads(state_path.read_text())
    assert [target["status"] for target in interrupted["backendCleanup"]["targets"]] == [
        "completed",
        "started",
    ]
    assert interrupted["backendCleanup"]["aggregate"] == {
        "status": "pending",
        "sha256": None,
    }
    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    loaded = MODULE._validate_execution_state_document(
        loaded,
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )

    monkeypatch.setattr(
        MODULE.BACKEND_ATTESTOR,
        "execute_signed_backend_cleanup_target",
        execute_target,
    )
    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=loaded,
        execution_state_path=state_path,
    )

    completed = json.loads(state_path.read_text())
    assert [target["status"] for target in completed["backendCleanup"]["targets"]] == [
        "completed",
        "completed",
    ]
    assert completed["backendCleanup"]["aggregate"]["status"] == "completed"
    assert attempts == [
        ("pv-orphan", "pv-uid-0"),
        ("pv-workspace", "pv-uid-1"),
    ]
    assert _backend_cleanup_contract["executions"] == [
        ("pv-orphan", "pv-uid-0"),
        ("pv-workspace", "pv-uid-1"),
    ]


def test_backend_cleanup_resumes_all_targets_completed_before_aggregate_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _backend_cleanup_contract: dict[str, list],
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)
    write_aggregate = MODULE._write_backend_cleanup_aggregate
    monkeypatch.setattr(
        MODULE,
        "_write_backend_cleanup_aggregate",
        lambda **_arguments: (_ for _ in ()).throw(
            KeyboardInterrupt("crash before aggregate write")
        ),
    )

    with pytest.raises(KeyboardInterrupt, match="before aggregate write"):
        MODULE._execute_backend_cleanup(
            inputs=inputs,
            state=state,
            execution_state_path=state_path,
        )

    interrupted = json.loads(state_path.read_text())
    assert {target["status"] for target in interrupted["backendCleanup"]["targets"]} == {
        "completed"
    }
    assert interrupted["backendCleanup"]["aggregate"] == {
        "status": "pending",
        "sha256": None,
    }
    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    loaded = MODULE._validate_execution_state_document(
        loaded,
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )
    executions_before_resume = list(_backend_cleanup_contract["executions"])

    monkeypatch.setattr(MODULE, "_write_backend_cleanup_aggregate", write_aggregate)
    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=loaded,
        execution_state_path=state_path,
    )

    assert _backend_cleanup_contract["executions"] == executions_before_resume
    assert json.loads(state_path.read_text())["backendCleanup"]["aggregate"][
        "status"
    ] == "completed"


def test_backend_cleanup_resumes_aggregate_written_before_journal_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    _backend_cleanup_contract: dict[str, list],
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)
    write_aggregate = MODULE._write_backend_cleanup_aggregate

    def write_then_interrupt(**arguments):
        result = write_aggregate(**arguments)
        raise KeyboardInterrupt("crash after aggregate write")

    monkeypatch.setattr(
        MODULE,
        "_write_backend_cleanup_aggregate",
        write_then_interrupt,
    )
    with pytest.raises(KeyboardInterrupt, match="after aggregate write"):
        MODULE._execute_backend_cleanup(
            inputs=inputs,
            state=state,
            execution_state_path=state_path,
        )

    aggregate_path = state_path.with_name("backend-cleanup-results.json")
    aggregate_before_resume = aggregate_path.read_bytes()
    interrupted = json.loads(state_path.read_text())
    assert interrupted["backendCleanup"]["aggregate"] == {
        "status": "pending",
        "sha256": None,
    }
    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    loaded = MODULE._validate_execution_state_document(
        loaded,
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )
    executions_before_resume = list(_backend_cleanup_contract["executions"])

    monkeypatch.setattr(MODULE, "_write_backend_cleanup_aggregate", write_aggregate)
    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=loaded,
        execution_state_path=state_path,
    )

    assert aggregate_path.read_bytes() == aggregate_before_resume
    assert _backend_cleanup_contract["executions"] == executions_before_resume
    assert json.loads(state_path.read_text())["backendCleanup"]["aggregate"][
        "status"
    ] == "completed"


def test_completed_backend_cleanup_rejects_changed_write_once_aggregate(
    tmp_path: Path,
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)
    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=state,
        execution_state_path=state_path,
    )
    aggregate_path = state_path.with_name("backend-cleanup-results.json")
    aggregate_path.write_bytes(b"{}\n")
    aggregate_path.chmod(0o600)
    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    loaded = MODULE._validate_execution_state_document(
        loaded,
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )

    with pytest.raises(ValueError, match="aggregate"):
        MODULE._execute_backend_cleanup(
            inputs=inputs,
            state=loaded,
            execution_state_path=state_path,
        )


def test_completed_backend_cleanup_rejects_missing_durable_aggregate(
    tmp_path: Path,
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)
    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=state,
        execution_state_path=state_path,
    )
    aggregate_path = state_path.with_name("backend-cleanup-results.json")
    aggregate_path.unlink()
    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    loaded = MODULE._validate_execution_state_document(
        loaded,
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )

    with pytest.raises(ValueError, match="aggregate is missing"):
        MODULE._execute_backend_cleanup(
            inputs=inputs,
            state=loaded,
            execution_state_path=state_path,
        )
    assert not aggregate_path.exists()


def test_backend_cleanup_empty_target_set_writes_all_absent_aggregate(
    tmp_path: Path,
) -> None:
    inventory = _inventory()
    inventory["persistentVolumes"] = []
    plan = _plan(inventory)
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)

    MODULE._execute_backend_cleanup(
        inputs=inputs,
        state=state,
        execution_state_path=state_path,
    )

    aggregate = json.loads(
        state_path.with_name("backend-cleanup-results.json").read_text()
    )
    assert aggregate["results"] == []
    assert aggregate["allAbsent"] is True
    assert json.loads(state_path.read_text())["backendCleanup"] == {
        "targets": [],
        "aggregate": {
            "status": "completed",
            "sha256": hashlib.sha256(
                MODULE._canonical_bytes(aggregate) + b"\n"
            ).hexdigest(),
        },
    }


@pytest.mark.parametrize(
    "aggregate",
    (
        {"status": "pending", "sha256": "f" * 64},
        {"status": "completed", "sha256": None},
    ),
)
def test_backend_cleanup_journal_rejects_nonexclusive_aggregate_state(
    aggregate: dict, tmp_path: Path
) -> None:
    plan = _plan(_inventory())
    inputs = _backend_inputs(plan)
    state = _backend_state(plan, inputs)
    state["backendCleanup"]["aggregate"] = aggregate
    state_path = tmp_path / "reset-state.json"
    MODULE._write_evidence(state_path, state)

    loaded = MODULE._read_execution_state(state_path)
    assert loaded is not None
    with pytest.raises(ValueError, match="aggregate journal is invalid"):
        MODULE._validate_execution_state_document(
            loaded,
            plan=plan,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            backend_inputs=inputs,
            causal_root_reports=deepcopy(ROOT_RECEIPT),
        )


def test_resume_rejects_same_name_namespace_uid_replacement(tmp_path: Path) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardNamespace/workspace-system",
            ),
        )
    workspace_namespace = next(
        item for item in live["namespaces"] if item["name"] == "workspace-system"
    )
    workspace_namespace["uid"] = "replacement-namespace-uid"

    with pytest.raises(ValueError, match="UID was replaced"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(live, []),
        )


def test_resume_keeps_unstarted_namespace_at_exact_identity(tmp_path: Path) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardNamespace/aileron-turn-system",
            ),
        )
    workspace_namespace = next(
        item for item in live["namespaces"] if item["name"] == "workspace-system"
    )
    workspace_namespace["labels"]["unexpected"] = "drift"
    workspace_namespace["resourceVersion"] = "999"

    with pytest.raises(ValueError, match="unguarded reset namespace drifted"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(live, []),
        )


def test_resume_allows_guarded_namespace_controller_churn_and_subsets(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardNamespace/workspace-system",
            ),
        )
    live["resources"] = [
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "namespace": "workspace-system",
            "name": "replacement-controller-pod",
            "uid": "replacement-controller-pod-uid",
            "resourceVersion": "901",
        }
    ]

    MODULE.execute_reset_plan(
        _plan(approved),
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(live, []),
        delete_client=_FakeDeleteClient(live),
    )

    assert live["namespaces"] == []
    assert live["resources"] == []


def test_resume_rejects_snapshot_after_new_target_persistent_volume(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardPersistentVolume/pv-orphan",
            ),
        )
    replacement = deepcopy(approved["persistentVolumes"][0])
    replacement.update(
        {
            "name": "pv-created-after-snapshot",
            "uid": "pv-created-after-snapshot-uid",
            "resourceVersion": "777",
        }
    )
    replacement["backendLocator"] = {
        **replacement["backendLocator"],
        "path": "/var/lib/aileron/pv-created-after-snapshot",
    }
    live["persistentVolumes"].append(replacement)

    with pytest.raises(ValueError, match="unapproved PersistentVolume"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(live, []),
        )


@pytest.mark.parametrize(
    ("identity_key", "replacement"),
    [
        ("resetRunId", "run-wrong-identity"),
        ("resetSnapshotSha256", "b" * 64),
        ("planSha256", "c" * 64),
    ],
)
def test_resume_rejects_wrong_journal_identity(
    identity_key: str, replacement: str, tmp_path: Path
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"
    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardPersistentVolume/pv-orphan",
            ),
        )
    state = json.loads(state_path.read_text())
    state[identity_key] = replacement
    state_path.write_text(json.dumps(state))
    state_path.chmod(0o600)

    with pytest.raises(ValueError, match="identity does not match"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(live, []),
        )


def test_resume_rejects_non_private_journal_mode(tmp_path: Path) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"
    with pytest.raises(KeyboardInterrupt):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                crash_action="guardPersistentVolume/pv-orphan",
            ),
        )
    state_path.chmod(0o644)

    with pytest.raises(ValueError, match="mode 0600"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(live, []),
        )


def test_command_failure_converges_only_after_authoritative_absence(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    MODULE.execute_reset_plan(
        _plan(approved),
        kubeconfig=KUBECONFIG,
        execution_state_path=state_path,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(
            live,
            [],
            fail_action="deleteNamespace/workspace-system",
            mutate_before_failure=True,
        ),
        delete_client=_FakeDeleteClient(
            live,
            fail_action="deleteNamespace/workspace-system",
            mutate_before_failure=True,
        ),
    )

    assert json.loads(state_path.read_text())["actions"][
        "deleteNamespace/workspace-system"
    ] == {"status": "completed"}


def test_command_failure_without_authoritative_postcondition_fails_closed(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"

    with pytest.raises(ValueError, match="authoritative postcondition"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                fail_action="guardPersistentVolume/pv-orphan",
            ),
        )

    assert json.loads(state_path.read_text())["actions"][
        "guardPersistentVolume/pv-orphan"
    ] == {"status": "started"}


def test_successful_mutation_without_authoritative_postcondition_fails_closed(
    tmp_path: Path,
) -> None:
    approved = _inventory()
    live = deepcopy(approved)
    state_path = tmp_path / "reset-state.json"
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="authoritative postcondition"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=state_path,
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(live, commands),
        )

    state = json.loads(state_path.read_text())
    assert state["actions"]["guardPersistentVolume/pv-orphan"] == {
        "status": "started"
    }
    assert all(
        progress == {"status": "pending"}
        for action_id, progress in state["actions"].items()
        if action_id != "guardPersistentVolume/pv-orphan"
    )


@pytest.mark.parametrize(
    "read_failure",
    (
        "transport timeout",
        "forbidden by the API server",
        "connection refused",
    ),
)
def test_failed_action_get_transport_or_authorization_never_proves_absence(
    read_failure: str, tmp_path: Path
) -> None:
    approved = _inventory()
    live = deepcopy(approved)

    with pytest.raises(ValueError, match="authoritative postcondition"):
        MODULE.execute_reset_plan(
            _plan(approved),
            kubeconfig=KUBECONFIG,
            execution_state_path=tmp_path / "reset-state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_mutable_runner(
                live,
                [],
                fail_action="guardPersistentVolume/pv-orphan",
                fail_reads_after_action=read_failure,
            ),
        )


def _kubectl(*arguments: str) -> list[str]:
    return [
        "kubectl",
        "--kubeconfig",
        str(KUBECONFIG),
        "--context",
        CONTEXT,
        *arguments,
    ]


def _helm(*arguments: str) -> list[str]:
    return [
        "helm",
        "--kubeconfig",
        str(KUBECONFIG),
        "--kube-context",
        CONTEXT,
        *arguments,
    ]


def _plan(inventory: dict) -> dict:
    return MODULE.build_reset_plan(
        inventory,
        kubeconfig=KUBECONFIG,
        reset_run_id=RESET_RUN_ID,
    )


def _backend_inputs(plan: dict) -> SimpleNamespace:
    return MODULE._load_signed_backend_inputs(
        plan=plan,
        kubeconfig=KUBECONFIG,
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
    )


def _backend_state(plan: dict, inputs: SimpleNamespace) -> dict:
    return MODULE._execution_state_document(
        plan=plan,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        backend_inputs=inputs,
        causal_root_reports=deepcopy(ROOT_RECEIPT),
    )


def _inventory() -> dict:
    owner = {MODULE.NAMESPACE_OWNER_LABEL: MODULE.NAMESPACE_OWNER}
    return {
        "context": "rke2-homelab",
        "namespaces": [
            {
                "name": "workspace-system",
                "uid": "namespace-uid-workspace",
                "resourceVersion": "501",
                "labels": owner,
            },
            {
                "name": "aileron-turn-system",
                "uid": "namespace-uid-turn",
                "resourceVersion": "502",
                "labels": owner,
            },
        ],
        "releases": [
            {"name": "aileron", "namespace": "workspace-system"},
            {"name": "aileron-turn", "namespace": "aileron-turn-system"},
        ],
        "persistentVolumes": [
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-orphan",
                "uid": "pv-uid-0",
                "resourceVersion": "100",
                "labels": {},
                "phase": "Released",
                "storageClassName": "aileron-local-rwo-retain",
                "reclaimPolicy": "Delete",
                "claimRef": {
                    "namespace": "workspace-system",
                    "name": "deleted-manager-state",
                    "uid": "pvc-uid-0",
                },
                "backendLocator": {
                    "type": "localPath",
                    "node": "rke2-worker-1",
                    "path": "/var/lib/aileron/pv-orphan",
                    "volumeSource": "hostPath",
                },
            },
            {
                "apiVersion": "v1",
                "kind": "PersistentVolume",
                "name": "pv-workspace",
                "uid": "pv-uid-1",
                "resourceVersion": "101",
                "labels": {"app.kubernetes.io/part-of": "aileron"},
                "phase": "Bound",
                "storageClassName": "aileron-nfs-rwx-retain",
                "reclaimPolicy": "Retain",
                "claimRef": {
                    "namespace": "workspace-system",
                    "name": "workspace-example-data",
                    "uid": "pvc-uid-1",
                },
                "backendLocator": {
                    "type": "nfs",
                    "server": "10.0.0.12",
                    "path": "/exports/pv-workspace",
                },
            },
        ],
        "resources": [
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "namespace": "workspace-system",
                "name": "workspace-example-data",
                "uid": "pvc-resource-uid",
                "resourceVersion": "801",
            },
            {
                "apiVersion": "platform.aileron.io/v1alpha1",
                "kind": "Workspace",
                "namespace": "workspace-system",
                "name": "workspace-example",
                "uid": "workspace-resource-uid",
                "resourceVersion": "802",
            },
        ],
    }


def _live_persistent_volume(persistent_volume: dict) -> dict:
    locator = persistent_volume["backendLocator"]
    spec = {
        "storageClassName": persistent_volume["storageClassName"],
        "persistentVolumeReclaimPolicy": persistent_volume["reclaimPolicy"],
        "claimRef": persistent_volume["claimRef"],
    }
    if locator["type"] == "nfs":
        spec["nfs"] = {"server": locator["server"], "path": locator["path"]}
    elif locator["type"] == "localPath":
        spec[locator["volumeSource"]] = {"path": locator["path"]}
        spec["nodeAffinity"] = {
            "required": {
                "nodeSelectorTerms": [
                    {
                        "matchExpressions": [
                            {
                                "key": "kubernetes.io/hostname",
                                "operator": "In",
                                "values": [locator["node"]],
                            }
                        ]
                    }
                ]
            }
        }
    else:
        spec["csi"] = {
            "driver": locator["driver"],
            "volumeHandle": locator["volumeHandle"],
        }
    return {
        "apiVersion": "v1",
        "kind": "PersistentVolume",
        "metadata": {
            "name": persistent_volume["name"],
            "uid": persistent_volume["uid"],
            "resourceVersion": persistent_volume["resourceVersion"],
            "labels": persistent_volume["labels"],
        },
        "spec": spec,
        "status": {"phase": persistent_volume["phase"]},
    }


def _inventory_runner(
    inventory: dict,
    commands: list[list[str]],
    *,
    current_context: str = CONTEXT,
):
    resource_names = {
        ("v1", "PersistentVolumeClaim"): "persistentvolumeclaims",
        ("platform.aileron.io/v1alpha1", "Workspace"): (
            "workspaces.platform.aileron.io"
        ),
        ("example.io/v1", "Widget"): "widgets.example.io",
    }
    def current_rows() -> dict[str, list[str]]:
        rows_by_resource: dict[str, list[str]] = {}
        for resource in inventory["resources"]:
            resource_name = resource_names.get(
                (resource["apiVersion"], resource["kind"]),
                f"{resource['kind'].lower()}s",
            )
            rows_by_resource.setdefault(resource_name, []).append(
                " ".join(
                    resource[key]
                    for key in (
                        "apiVersion",
                        "kind",
                        "namespace",
                        "name",
                        "uid",
                        "resourceVersion",
                    )
                )
            )
        return rows_by_resource

    def runner(command: list[str]) -> str:
        commands.append(command)
        if command == _kubectl("config", "current-context"):
            return f"{current_context}\n"
        if command == _kubectl("get", "namespaces", "-o", "json"):
            return json.dumps(
                {
                    "items": [
                        {
                            "metadata": {
                                "name": namespace["name"],
                                "uid": namespace["uid"],
                                "resourceVersion": namespace["resourceVersion"],
                                "labels": namespace["labels"],
                            }
                        }
                        for namespace in inventory["namespaces"]
                    ]
                }
            )
        if command == _helm("list", "--all-namespaces", "--output", "json"):
            return json.dumps(inventory["releases"])
        if command == _kubectl("get", "persistentvolumes", "-o", "json"):
            return json.dumps(
                {
                    "items": [
                        _live_persistent_volume(persistent_volume)
                        for persistent_volume in inventory["persistentVolumes"]
                    ]
                }
            )
        if command == _kubectl(
            "api-resources", "--namespaced=true", "--verbs=list", "-o", "name"
        ):
            rows_by_resource = current_rows()
            return "\n".join(sorted(rows_by_resource))
        if command[:6] == _kubectl("get"):
            rows_by_resource = current_rows()
            return "\n".join(rows_by_resource.get(command[6], []))
        return ""

    return runner


def _action_id(command: list[str]) -> str | None:
    if command[:6] == _kubectl("patch"):
        kind = command[6]
        name = command[7]
        if kind == "persistentvolume":
            return f"guardPersistentVolume/{name}"
        if kind == "namespace":
            return f"guardNamespace/{name}"
    if command[:7] == _kubectl("delete", "persistentvolumes"):
        uid = command[7].rsplit("=", 1)[1]
        names = {
            "pv-uid-0": "pv-orphan",
            "pv-uid-1": "pv-workspace",
        }
        return f"requestDeletePersistentVolume/{names[uid]}"
    if command[:7] == _kubectl("delete", "workspaces.platform.aileron.io"):
        namespace = command[command.index("--namespace") + 1]
        return f"deleteWorkspaces/{namespace}"
    if command[:6] == _helm("uninstall"):
        namespace = command[command.index("--namespace") + 1]
        return f"uninstallRelease/{namespace}/{command[6]}"
    if command[:7] == _kubectl("delete", "namespaces"):
        selector = command[7].removeprefix("--selector=")
        uid = selector.split(",", 1)[0].split("=", 1)[1]
        names = {
            "namespace-uid-workspace": "workspace-system",
            "namespace-uid-turn": "aileron-turn-system",
        }
        return f"deleteNamespace/{names[uid]}"
    if command[:7] == _kubectl("wait", "--for=delete"):
        name = command[7].split("/", 1)[1]
        return f"waitPersistentVolumeAbsent/{name}"
    return None


def _apply_action(command: list[str], inventory: dict) -> None:
    action_id = _action_id(command)
    if action_id is None:
        return
    kind, _, target = action_id.partition("/")
    if kind == "guardPersistentVolume":
        persistent_volume = next(
            item for item in inventory["persistentVolumes"] if item["name"] == target
        )
        persistent_volume["labels"] = {
            **persistent_volume["labels"],
            MODULE.PV_RESET_UID_LABEL: persistent_volume["uid"],
        }
        persistent_volume["reclaimPolicy"] = "Delete"
        persistent_volume["resourceVersion"] = (
            f"{int(persistent_volume['resourceVersion']) + 100}"
        )
        return
    if kind == "guardNamespace":
        namespace = next(
            item for item in inventory["namespaces"] if item["name"] == target
        )
        namespace["labels"] = {
            **namespace["labels"],
            MODULE.NAMESPACE_RESET_UID_LABEL: namespace["uid"],
            MODULE.NAMESPACE_RESET_RUN_LABEL: RESET_RUN_ID,
        }
        namespace["resourceVersion"] = f"{int(namespace['resourceVersion']) + 100}"
        return
    if kind == "requestDeletePersistentVolume":
        inventory["persistentVolumes"] = [
            item for item in inventory["persistentVolumes"] if item["name"] != target
        ]
        return
    if kind == "deleteWorkspaces":
        inventory["resources"] = [
            item
            for item in inventory["resources"]
            if not (item["namespace"] == target and item["kind"] == "Workspace")
        ]
        return
    if kind == "uninstallRelease":
        namespace, release = target.split("/", 1)
        inventory["releases"] = [
            item
            for item in inventory["releases"]
            if item != {"namespace": namespace, "name": release}
        ]
        return
    if kind == "deleteNamespace":
        inventory["namespaces"] = [
            item for item in inventory["namespaces"] if item["name"] != target
        ]
        inventory["resources"] = [
            item for item in inventory["resources"] if item["namespace"] != target
        ]
        inventory["releases"] = [
            item for item in inventory["releases"] if item["namespace"] != target
        ]
        inventory["persistentVolumes"] = [
            item
            for item in inventory["persistentVolumes"]
            if not (
                isinstance(item["claimRef"], dict)
                and item["claimRef"]["namespace"] == target
            )
        ]


def _mutable_runner(
    inventory: dict,
    commands: list[list[str]],
    *,
    crash_action: str | None = None,
    fail_action: str | None = None,
    mutate_before_failure: bool = False,
    fail_reads_after_action: str | None = None,
):
    boundary = _inventory_runner(inventory, commands)
    action_failed = False

    def runner(command: list[str]) -> str:
        nonlocal action_failed
        action_id = _action_id(command)
        if action_id is None:
            if action_failed and fail_reads_after_action is not None:
                raise RuntimeError(fail_reads_after_action)
            return boundary(command)
        boundary(command)
        if action_id == fail_action and not mutate_before_failure:
            action_failed = True
            raise RuntimeError("simulated mutation command failure")
        _apply_action(command, inventory)
        if action_id == crash_action:
            raise KeyboardInterrupt(f"crash after {action_id}")
        if action_id == fail_action:
            action_failed = True
            raise RuntimeError("simulated mutation command failure")
        return ""

    return runner


class _FakeDeleteClient:
    def __init__(
        self,
        inventory: dict,
        *,
        crash_action: str | None = None,
        fail_action: str | None = None,
        mutate_before_failure: bool = False,
    ) -> None:
        self.inventory = inventory
        self.crash_action = crash_action
        self.fail_action = fail_action
        self.mutate_before_failure = mutate_before_failure
        self.calls: list[dict[str, str | None]] = []

    def delete(self, **request: str | None) -> None:
        self.calls.append(request)
        api_version = request["api_version"]
        resource = request["resource"]
        namespace = request["namespace"]
        name = request["name"]
        if resource == "persistentvolumes":
            action_id = f"requestDeletePersistentVolume/{name}"
            collection = self.inventory["persistentVolumes"]
        elif resource == "workspaces":
            action_id = f"deleteWorkspace/{namespace}/{name}"
            collection = self.inventory["resources"]
        elif resource == "namespaces":
            action_id = f"deleteNamespace/{name}"
            collection = self.inventory["namespaces"]
        else:
            raise AssertionError(f"unexpected REST resource: {resource}")
        if action_id == self.fail_action and not self.mutate_before_failure:
            raise RuntimeError("simulated preconditioned delete failure")
        if resource == "workspaces":
            live = next(
                item
                for item in collection
                if item["apiVersion"] == api_version
                and item["kind"] == "Workspace"
                and item["namespace"] == namespace
                and item["name"] == name
            )
        else:
            live = next(item for item in collection if item["name"] == name)
        if (
            live["uid"] != request["uid"]
            or live["resourceVersion"] != request["resource_version"]
        ):
            raise RuntimeError("simulated Kubernetes precondition conflict")
        if resource == "persistentvolumes":
            self.inventory["persistentVolumes"] = [
                item
                for item in self.inventory["persistentVolumes"]
                if item["name"] != name
            ]
        elif resource == "workspaces":
            self.inventory["resources"] = [
                item
                for item in self.inventory["resources"]
                if not (
                    item["apiVersion"] == api_version
                    and item["kind"] == "Workspace"
                    and item["namespace"] == namespace
                    and item["name"] == name
                    and item["uid"] == request["uid"]
                )
            ]
        else:
            self.inventory["namespaces"] = [
                item
                for item in self.inventory["namespaces"]
                if item["name"] != name
            ]
            self.inventory["resources"] = [
                item
                for item in self.inventory["resources"]
                if item["namespace"] != name
            ]
            self.inventory["releases"] = [
                item
                for item in self.inventory["releases"]
                if item["namespace"] != name
            ]
            self.inventory["persistentVolumes"] = [
                item
                for item in self.inventory["persistentVolumes"]
                if not (
                    isinstance(item["claimRef"], dict)
                    and item["claimRef"]["namespace"] == name
                )
            ]
        if action_id == self.crash_action:
            raise KeyboardInterrupt(f"crash after {action_id}")
        if action_id == self.fail_action:
            raise RuntimeError("simulated preconditioned delete failure")


def test_plan_only_deletes_signed_workspaces_and_owned_namespaces() -> None:
    result = _plan(_inventory())

    assert result["context"] == "rke2-homelab"
    assert result["namespaces"] == [
        _inventory()["namespaces"][1],
        _inventory()["namespaces"][0],
    ]
    assert result["resources"] == _inventory()["resources"]
    assert result["actions"] == [
        {
            "id": "guardPersistentVolume/pv-orphan",
            "kind": "guardPersistentVolume",
            "name": "pv-orphan",
        },
        {
            "id": "guardPersistentVolume/pv-workspace",
            "kind": "guardPersistentVolume",
            "name": "pv-workspace",
        },
        {
            "id": "guardNamespace/aileron-turn-system",
            "kind": "guardNamespace",
            "name": "aileron-turn-system",
        },
        {
            "id": "guardNamespace/workspace-system",
            "kind": "guardNamespace",
            "name": "workspace-system",
        },
        {
            "id": "requestDeletePersistentVolume/pv-orphan",
            "kind": "requestDeletePersistentVolume",
            "name": "pv-orphan",
        },
        {
            "id": "deleteWorkspace/workspace-system/workspace-example",
            "kind": "deleteWorkspace",
            "name": "workspace-example",
            "namespace": "workspace-system",
        },
        {
            "id": "deleteNamespace/workspace-system",
            "kind": "deleteNamespace",
            "name": "workspace-system",
        },
        {
            "id": "deleteNamespace/aileron-turn-system",
            "kind": "deleteNamespace",
            "name": "aileron-turn-system",
        },
        {
            "id": "waitPersistentVolumeAbsent/pv-orphan",
            "kind": "waitPersistentVolumeAbsent",
            "name": "pv-orphan",
        },
        {
            "id": "waitPersistentVolumeAbsent/pv-workspace",
            "kind": "waitPersistentVolumeAbsent",
            "name": "pv-workspace",
        },
    ]
    assert result["resetRunId"] == RESET_RUN_ID
    assert result["backendVerificationRequired"] == [
        {
            "persistentVolume": "pv-orphan",
            "uid": "pv-uid-0",
            "storageClassName": "aileron-local-rwo-retain",
            "backendLocator": {
                "type": "localPath",
                "node": "rke2-worker-1",
                "path": "/var/lib/aileron/pv-orphan",
                "volumeSource": "hostPath",
            },
        },
        {
            "persistentVolume": "pv-workspace",
            "uid": "pv-uid-1",
            "storageClassName": "aileron-nfs-rwx-retain",
            "backendLocator": {
                "type": "nfs",
                "server": "10.0.0.12",
                "path": "/exports/pv-workspace",
            },
        },
    ]


def test_plan_accepts_an_already_clean_empty_target_inventory() -> None:
    inventory = _inventory()
    inventory["namespaces"] = []
    inventory["releases"] = []
    inventory["persistentVolumes"] = []
    inventory["resources"] = []

    result = _plan(inventory)

    assert result["namespaces"] == []
    assert result["releases"] == []
    assert result["persistentVolumes"] == []
    assert result["resources"] == []
    assert result["actions"] == []
    assert result["backendVerificationRequired"] == []


def test_plan_fails_closed_when_namespace_is_not_installer_owned() -> None:
    inventory = _inventory()
    inventory["namespaces"][0]["labels"] = {}

    with pytest.raises(ValueError, match="namespace ownership mismatch"):
        _plan(inventory)


def test_plan_rejects_unknown_release_in_owned_namespace() -> None:
    inventory = _inventory()
    inventory["releases"].append(
        {"name": "cert-manager", "namespace": "workspace-system"}
    )

    with pytest.raises(ValueError, match="release is not allowlisted"):
        _plan(inventory)


def test_plan_rejects_cluster_scoped_resource_misattributed_to_aileron() -> None:
    inventory = _inventory()
    inventory["resources"].append(
        {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "StorageClass",
            "namespace": "workspace-system",
            "name": "must-not-delete",
            "uid": "must-not-delete-uid",
            "resourceVersion": "901",
        }
    )

    with pytest.raises(ValueError, match="resource kind is not allowlisted"):
        _plan(inventory)


def test_plan_rejects_unknown_namespaced_custom_resource() -> None:
    inventory = _inventory()
    inventory["resources"].append(
        {
            "apiVersion": "example.io/v1",
            "kind": "Widget",
            "namespace": "workspace-system",
            "name": "unexpected-widget",
            "uid": "unexpected-widget-uid",
            "resourceVersion": "902",
        }
    )

    with pytest.raises(ValueError, match="resource kind is not allowlisted"):
        _plan(inventory)


def _rancher_app(
    *,
    name: str = "aileron",
    namespace: str = "workspace-system",
    owner_name: str = "sh.helm.release.v1.aileron.v6",
) -> dict:
    return {
        "apiVersion": "catalog.cattle.io/v1",
        "kind": "App",
        "namespace": namespace,
        "name": name,
        "uid": f"rancher-app-{name}-uid",
        "resourceVersion": "903",
        "ownerReferences": [
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "namespace": namespace,
                "name": owner_name,
            }
        ],
    }


def test_plan_accepts_rancher_app_owned_by_allowlisted_helm_release() -> None:
    inventory = _inventory()
    inventory["resources"].append(_rancher_app())

    plan = _plan(inventory)

    assert _rancher_app() in plan["resources"]


@pytest.mark.parametrize(
    "resource",
    [
        _rancher_app(name="other", owner_name="sh.helm.release.v1.other.v1"),
        {**_rancher_app(), "ownerReferences": []},
        _rancher_app(owner_name="sh.helm.release.v1.aileron-turn.v2"),
        _rancher_app(owner_name="sh.helm.release.v1.aileron.v0"),
        _rancher_app(owner_name="sh.helm.release.v1.aileron.vlatest"),
    ],
)
def test_plan_rejects_unbound_rancher_app(resource: dict) -> None:
    inventory = _inventory()
    inventory["resources"].append(resource)

    with pytest.raises(ValueError, match="Rancher App"):
        _plan(inventory)


def test_plan_rejects_rancher_app_outside_target_namespace() -> None:
    inventory = _inventory()
    inventory["resources"].append(
        _rancher_app(namespace="shared-system")
    )

    with pytest.raises(ValueError, match="existing Aileron reset target"):
        _plan(inventory)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (
            lambda pv: pv["claimRef"].update({"namespace": "shared-service"}),
            "target namespace",
        ),
        (
            lambda pv: pv.update({"storageClassName": "shared-storage"}),
            "StorageClass",
        ),
        (
            lambda pv: pv.update({"reclaimPolicy": "Recycle"}),
            "reclaimPolicy",
        ),
    ],
)
def test_plan_rejects_persistent_volume_outside_exact_reset_ownership(
    change, message: str
) -> None:
    inventory = _inventory()
    change(inventory["persistentVolumes"][0])

    with pytest.raises((ValueError, TypeError), match=message):
        _plan(inventory)


def test_plan_rejects_unknown_aileron_prefixed_storage_class() -> None:
    inventory = _inventory()
    inventory["persistentVolumes"][0]["storageClassName"] = "aileron-future-delete"

    with pytest.raises(ValueError, match="StorageClass is not allowlisted"):
        _plan(inventory)


def test_execute_recollects_complete_inventory_before_first_mutation(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []
    inventory = _inventory()
    live = deepcopy(inventory)
    delete_client = _FakeDeleteClient(live)
    MODULE.execute_reset_plan(
        _plan(inventory),
        kubeconfig=KUBECONFIG,
        execution_state_path=tmp_path / "reset-state.json",
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(live, commands),
        delete_client=delete_client,
    )

    first_mutation = next(
        index
        for index, command in enumerate(commands)
        if command[:6] in [_kubectl("patch"), _kubectl("delete")]
    )
    pre_mutation = commands[:first_mutation]
    assert _kubectl("get", "namespaces", "-o", "json") in pre_mutation
    assert _helm("list", "--all-namespaces", "--output", "json") in pre_mutation
    assert _kubectl("get", "persistentvolumes", "-o", "json") in pre_mutation
    assert (
        _kubectl("api-resources", "--namespaced=true", "--verbs=list", "-o", "name")
        in pre_mutation
    )
    assert not any("delete" in command for command in commands)
    assert delete_client.calls[0] == {
        "api_version": "v1",
        "resource": "persistentvolumes",
        "namespace": None,
        "name": "pv-orphan",
        "uid": "pv-uid-0",
        "resource_version": "200",
    }
    assert all(
        command[1:5] == ["--kubeconfig", str(KUBECONFIG), "--context", CONTEXT]
        for command in commands
        if command[0] == "kubectl"
    )
    assert all(
        command[1:5] == ["--kubeconfig", str(KUBECONFIG), "--kube-context", CONTEXT]
        for command in commands
        if command[0] == "helm"
    )
    assert not any("storageclass" in command for command in commands)


@pytest.mark.parametrize(
    ("inventory_key", "change"),
    [
        (
            "namespaces",
            lambda inventory: inventory["namespaces"][0].update(
                {"uid": "replacement-namespace-uid"}
            ),
        ),
        ("namespaces", lambda inventory: inventory["namespaces"].pop()),
        (
            "resources",
            lambda inventory: inventory["resources"].append(
                    {
                        "apiVersion": "platform.aileron.io/v1alpha1",
                        "kind": "Workspace",
                        "namespace": "workspace-system",
                        "name": "new-workspace",
                        "uid": "new-workspace-uid",
                        "resourceVersion": "904",
                    }
            ),
        ),
        ("resources", lambda inventory: inventory["resources"].pop()),
        (
            "releases",
            lambda inventory: inventory["releases"].pop(),
        ),
        (
            "persistentVolumes",
            lambda inventory: inventory["persistentVolumes"][0].update(
                {"labels": {"tampered": "true"}}
            ),
        ),
    ],
)
def test_execute_rejects_any_canonical_inventory_drift_before_mutation(
    inventory_key: str, change, tmp_path: Path
) -> None:
    planned_inventory = _inventory()
    live_inventory = deepcopy(planned_inventory)
    change(live_inventory)
    commands: list[list[str]] = []

    with pytest.raises(
        ValueError, match=f"live reset target set drift before mutation: {inventory_key}"
    ):
        MODULE.execute_reset_plan(
            _plan(planned_inventory),
            kubeconfig=KUBECONFIG,
            execution_state_path=tmp_path / "reset-state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(live_inventory, commands),
        )

    mutation_verbs = {"patch", "delete", "wait"}
    assert not any(
        command[0] == "helm"
        and "uninstall" in command
        or command[0] == "kubectl"
        and mutation_verbs.intersection(command)
        for command in commands
    )


def test_execute_allows_transient_inventory_resource_churn_before_mutation(
    tmp_path: Path,
) -> None:
    planned_inventory = _inventory()
    live_inventory = deepcopy(planned_inventory)
    live_inventory["resources"][0]["resourceVersion"] = "999"
    live_inventory["resources"].append(
        {
            "apiVersion": "v1",
            "kind": "Event",
            "namespace": "workspace-system",
            "name": "controller-churn",
            "uid": "controller-churn-uid",
            "resourceVersion": "1000",
        }
    )
    commands: list[list[str]] = []

    MODULE.execute_reset_plan(
        _plan(planned_inventory),
        kubeconfig=KUBECONFIG,
        execution_state_path=tmp_path / "reset-state.json",
        expected_commit=COMMIT,
        reset_snapshot_sha256=SNAPSHOT_SHA256,
        runner=_mutable_runner(live_inventory, commands),
        delete_client=_FakeDeleteClient(live_inventory),
    )

    assert live_inventory["namespaces"] == []
    assert live_inventory["resources"] == []


def test_inventory_rejects_secret_material_before_writing_evidence() -> None:
    inventory = _inventory()
    inventory["resources"].append(
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "namespace": "workspace-system",
            "name": "platform-secrets",
            "data": {"database-url": "must-not-be-recorded"},
        }
    )

    with pytest.raises(ValueError, match="non-secret metadata only"):
        _plan(inventory)


def test_execute_requires_matching_live_context_before_first_delete(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="current context does not match"):
        MODULE.execute_reset_plan(
            _plan(_inventory()),
            kubeconfig=KUBECONFIG,
            execution_state_path=tmp_path / "reset-state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(
                _inventory(), commands, current_context="unexpected-cluster"
            ),
        )

    assert commands == [_kubectl("config", "current-context")]


def test_execute_rejects_noncanonical_action_before_mutation(tmp_path: Path) -> None:
    plan = _plan({**_inventory(), "persistentVolumes": []})
    plan["actions"] = [
        {
            "id": "deleteNamespace/kube-system",
            "kind": "deleteNamespace",
            "name": "kube-system",
        }
    ]
    commands: list[list[str]] = []

    with pytest.raises(ValueError, match="canonical signed inventory"):
        MODULE.execute_reset_plan(
            plan,
            kubeconfig=KUBECONFIG,
            execution_state_path=tmp_path / "reset-state.json",
            expected_commit=COMMIT,
            reset_snapshot_sha256=SNAPSHOT_SHA256,
            runner=_inventory_runner(
                {**_inventory(), "persistentVolumes": []}, commands
            ),
        )

    assert commands == []
