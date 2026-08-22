#!/usr/bin/env python3
"""Build the only supported HomeLab deployment acceptance bundle."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import secrets
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
DEFAULT_CONTRACT = SCRIPT_DIRECTORY / "deployment-acceptance-contract.json"
DEFAULT_BUNDLE_NAME = "deployment-acceptance-bundle.json"


class AcceptanceBundleError(RuntimeError):
    """Raised when a code-owned bundle cannot be assembled exactly."""


def _load_local_module(name: str) -> Any:
    specification = importlib.util.spec_from_file_location(
        f"aileron_{name}", SCRIPT_DIRECTORY / f"{name}.py"
    )
    if specification is None or specification.loader is None:
        raise AcceptanceBundleError(f"acceptance dependency is unavailable: {name}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


EPOCH = _load_local_module("acceptance_epoch")
EVIDENCE = _load_local_module("acceptance_evidence")
PRIVATE_IO = _load_local_module("acceptance_private_io")


def _canonical(document: dict[str, Any]) -> bytes:
    return PRIVATE_IO.canonical_json(document)


def _json(raw: bytes, description: str) -> dict[str, Any]:
    return PRIVATE_IO.load_json_object(
        raw,
        description,
        error_type=AcceptanceBundleError,
        require_canonical=True,
    )


def build_bundle(
    *,
    expected_commit: str,
    deployment_run_id: str,
    contract_path: Path,
    context: str,
    runner: Any = EVIDENCE.ACCEPTANCE_CLUSTER._run_command,
) -> Path:
    """Assemble, fully validate, and atomically publish one acceptance bundle."""

    private_root = EVIDENCE.ACCEPTANCE_CLUSTER.INSTALLATION_STATE.PRIVATE_ROOT
    evidence_directory = PRIVATE_IO.evidence_directory(
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceBundleError,
    )
    PRIVATE_IO.validate_evidence_directory(
        evidence_directory,
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        error_type=AcceptanceBundleError,
    )
    canonical_kubeconfig = PRIVATE_IO.validate_canonical_kubeconfig(
        directory=evidence_directory,
        private_root=private_root,
        commit=expected_commit,
        deployment_run_id=deployment_run_id,
        context=context,
        error_type=AcceptanceBundleError,
    )
    output = evidence_directory / DEFAULT_BUNDLE_NAME
    if output.exists() or output.is_symlink():
        raise AcceptanceBundleError("acceptance bundle already exists")
    try:
        contract = EVIDENCE.load_canonical_contract(contract_path)
    except EVIDENCE.AcceptanceEvidenceError as exc:
        raise AcceptanceBundleError(str(exc)) from exc
    try:
        trust = EVIDENCE.ACCEPTANCE_CLUSTER.load_cluster_acceptance_key(
            context=context, kubeconfig=canonical_kubeconfig.path, runner=runner
        )
        epoch = EPOCH.load_deployment_epoch(
            directory=evidence_directory,
            private_root=private_root,
            key=trust.key,
            commit=expected_commit,
            cluster_uid=trust.cluster_uid,
            context=context,
            installation_identity_sha256=trust.installation_identity_sha256,
            deployment_run_id=deployment_run_id,
        )
        if epoch["deploymentRunId"] != deployment_run_id:
            raise AcceptanceBundleError(
                "deployment epoch run identity does not match"
            )
        required = EVIDENCE.required_reports_for_mode(
            contract, epoch["authenticationMode"]
        )
    except (
        EVIDENCE.ACCEPTANCE_CLUSTER.AcceptanceClusterError,
        EPOCH.AcceptanceEpochError,
        EVIDENCE.AcceptanceEvidenceError,
    ) as exc:
        raise AcceptanceBundleError(str(exc)) from exc

    known_report_files = {
        f"{section}.json" for section in contract["requiredProducers"]
    }
    observed_report_files = {
        path.name
        for path in evidence_directory.iterdir()
        if path.name in known_report_files
    }
    expected_report_files = {f"{section}.json" for section in required}
    if observed_report_files != expected_report_files:
        raise AcceptanceBundleError(
            "evidence directory does not contain the exact mode-specific report set"
        )

    reports: dict[str, dict[str, str]] = {}
    workspace: dict[str, str] | None = None
    for section in required:
        path = evidence_directory / f"{section}.json"
        raw = PRIVATE_IO.read_private_bytes(
            path,
            f"{section} report",
            private_root=private_root,
            error_type=AcceptanceBundleError,
            maximum_size=4 * 1024 * 1024,
        )
        report = _json(raw, f"{section} report")
        if (
            report.get("section") != section
            or report.get("commit") != expected_commit
            or report.get("deploymentRunId") != epoch["deploymentRunId"]
            or report.get("authenticationMode") != epoch["authenticationMode"]
        ):
            raise AcceptanceBundleError(f"{section} report epoch identity does not match")
        scope = EVIDENCE.report_scope(contract, section)
        if scope == "cluster":
            if "workspace" in report:
                raise AcceptanceBundleError(
                    f"{section} cluster-scoped report contains workspace identity"
                )
        else:
            candidate = report.get("workspace")
            if (
                not isinstance(candidate, dict)
                or set(candidate) != {"id", "userSubject"}
                or not all(isinstance(value, str) and value for value in candidate.values())
            ):
                raise AcceptanceBundleError(f"{section} report workspace is invalid")
            if section == "oidcWorkspace":
                workspace = candidate
            elif workspace is None or candidate != workspace:
                raise AcceptanceBundleError("report workspace identities do not match")
        reports[section] = {
            "file": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    if workspace is None:
        raise AcceptanceBundleError("acceptance workspace identity is missing")
    epoch_raw = PRIVATE_IO.read_private_bytes(
        evidence_directory / EPOCH.EPOCH_NAME,
        "deployment epoch",
        private_root=private_root,
        error_type=AcceptanceBundleError,
        maximum_size=4 * 1024 * 1024,
    )
    bundle = {
        "contractVersion": contract["contractVersion"],
        "commit": expected_commit,
        "deploymentRunId": epoch["deploymentRunId"],
        "authenticationMode": epoch["authenticationMode"],
        "workspace": workspace,
        "epoch": {
            "file": EPOCH.EPOCH_NAME,
            "sha256": hashlib.sha256(epoch_raw).hexdigest(),
        },
        "reports": reports,
    }
    temporary = evidence_directory / f".{DEFAULT_BUNDLE_NAME}.{secrets.token_hex(8)}.tmp"
    published = False
    try:
        PRIVATE_IO.write_private_snapshot(
            destination=temporary,
            content=_canonical(bundle) + b"\n",
            description="temporary acceptance bundle",
            private_root=private_root,
            error_type=AcceptanceBundleError,
        )
        directory_descriptor = os.open(
            evidence_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        try:
            os.link(
                temporary.name,
                output.name,
                src_dir_fd=directory_descriptor,
                dst_dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
            published = True
            os.unlink(temporary.name, dir_fd=directory_descriptor)
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
        EVIDENCE.validate_evidence(
            expected_commit,
            deployment_run_id,
            contract_path,
            context=context,
            canonical_kubeconfig=canonical_kubeconfig.path,
            runner=runner,
        )
    except (AcceptanceBundleError, EVIDENCE.AcceptanceEvidenceError, OSError) as exc:
        try:
            temporary.unlink(missing_ok=True)
            if published:
                output.unlink(missing_ok=True)
            directory_descriptor = os.open(
                evidence_directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            pass
        raise AcceptanceBundleError(str(exc)) from exc
    return output


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
        path = build_bundle(
            expected_commit=arguments.expected_commit,
            deployment_run_id=arguments.deployment_run_id,
            contract_path=DEFAULT_CONTRACT,
            context=arguments.context,
        )
    except AcceptanceBundleError as exc:
        parser.error(str(exc))
    print(f"bundle={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
