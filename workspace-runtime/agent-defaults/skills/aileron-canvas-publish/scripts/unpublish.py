from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from _common import (
    ArgoCDClient,
    load_publishing_config,
    result_envelope,
    run_cli,
    SkillError,
    workspace_operation_lock,
)
from config import load_site_config, validate_site_hostname, write_site_config
from deploy import application_scope_matches
from status import _probe_verification


def _unpublish(workspace: Path) -> dict[str, object]:
    config = load_publishing_config()
    current = load_site_config(workspace)
    site_id = str(current["siteId"])
    validate_site_hostname(
        str(current["hostname"]),
        site_id=site_id,
        base_domain=config.base_domain,
    )
    application_name = config.application_name(site_id)
    deployment_action_id = str(uuid4())
    argocd = ArgoCDClient(config)
    existing = argocd.get_application(application_name)
    expected_resource_version = (
        existing.get("metadata", {}).get("resourceVersion")
        if existing is not None
        else None
    )
    latest = argocd.get_application(application_name)
    if latest is not None:
        if not application_scope_matches(config, latest, site_id=site_id):
            raise SkillError(
                "ARGOCD_APPLICATION_CONTRACT_MISMATCH",
                "refusing to remove an Argo CD Application outside the managed site scope.",
                next_operation="status",
            )
        if existing is not None and latest.get("metadata", {}).get("resourceVersion") != expected_resource_version:
            raise SkillError(
                "UNPUBLISH_CONFLICT",
                "Argo CD Application changed while unpublish was being prepared.",
                retryable=True,
                next_operation="status",
            )
        existing = latest
        expected_resource_version = latest.get("metadata", {}).get("resourceVersion")
    else:
        existing = None
    if existing is not None:
        argocd.delete_application(
            application_name,
            project=config.argocd_project,
        )
    if argocd.get_application(application_name) is not None:
        return result_envelope(
            operation="unpublish",
            status="UNKNOWN",
            phase="VERIFYING",
            site_id=site_id,
            deployment_action_id=deployment_action_id,
            evidence={
                "argocd": {
                    "application": application_name,
                    "deleted": False,
                }
            },
            error_code="UNPUBLISH_PRUNE_PENDING",
            retryable=True,
            next_operation="status",
        )

    verification = _probe_verification(
        f"https://{current['hostname']}/_aileron/publication.json",
        ca_pem=config.ca_pem,
    )
    if verification.get("httpStatus") != 404:
        return result_envelope(
            operation="unpublish",
            status="UNKNOWN",
            phase="VERIFYING",
            site_id=site_id,
            deployment_action_id=deployment_action_id,
            evidence={
                "argocd": {"application": application_name, "deleted": True},
                "https": verification,
            },
            error_code="UNPUBLISH_PRUNE_PENDING",
            retryable=True,
            next_operation="status",
        )

    cleaned = dict(current)
    for key in (
        "lastSourceCommit",
        "lastPublicationId",
        "lastDeploymentActionId",
    ):
        cleaned.pop(key, None)
    write_site_config(workspace, cleaned)
    return result_envelope(
        operation="unpublish",
        status="UNPUBLISHED",
        phase="VERIFYING",
        site_id=site_id,
        deployment_action_id=deployment_action_id,
        evidence={
            "argocd": {"application": application_name, "deleted": True},
            "https": verification,
        },
        details={"historyRetained": True},
    )


def unpublish(workspace: Path) -> dict[str, object]:
    with workspace_operation_lock(workspace):
        return _unpublish(workspace)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove a Canvas Site Application while retaining publishing history."
    )
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.environ["AILERON_PUBLISH_OPERATION"] = "unpublish"
    args = build_parser().parse_args(argv)
    return run_cli(lambda: unpublish(args.workspace.resolve()))


if __name__ == "__main__":
    raise SystemExit(main())
