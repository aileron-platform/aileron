from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from _common import (
    ArgoCDClient,
    GitLabClient,
    PublishingConfig,
    SkillError,
    load_publishing_config,
    materialized_ca,
    redact_text,
    result_envelope,
    run_cli,
    workspace_operation_lock,
)
from config import load_site_config, validate_site_hostname, write_site_config
from deploy import application_scope_matches, desired_application


ACTIVE_PIPELINE_STATUSES = {"created", "waiting_for_resource", "preparing", "pending", "running", "scheduled", "manual"}
FAILED_PIPELINE_STATUSES = {"failed", "canceled", "skipped"}


def _probe_verification(url: str, *, ca_pem: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET", headers={"Cache-Control": "no-cache"})
    with materialized_ca(ca_pem) as ca_file:
        try:
            with urllib.request.urlopen(request, context=ssl.create_default_context(cafile=ca_file) if ca_file else ssl.create_default_context(), timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if not isinstance(payload, dict):
                    return {
                        "url": url,
                        "httpStatus": response.status,
                        "error": "verification endpoint returned a non-object payload",
                    }
                allowed_keys = {
                    "schemaVersion",
                    "siteId",
                    "publicationId",
                    "sourceCommit",
                    "buildType",
                    "hostname",
                }
                return {
                    "url": url,
                    "httpStatus": response.status,
                    "payload": {
                        key: payload[key]
                        for key in allowed_keys
                        if key in payload
                    },
                }
        except urllib.error.HTTPError as exc:
            return {"url": url, "httpStatus": exc.code, "error": "verification endpoint returned an HTTP error"}
        except (urllib.error.URLError, TimeoutError, ssl.SSLError, json.JSONDecodeError):
            return {"url": url, "httpStatus": None, "error": "verification endpoint is unavailable"}


def _recovery_target(
    site_config: Mapping[str, Any],
    *,
    current_publication_id: str,
) -> dict[str, Any] | None:
    history = site_config.get("publicationHistory") or []
    entries = [item for item in history if isinstance(item, dict)]
    candidates = [
        item
        for item in reversed(entries)
        if item.get("verified") is True
        and item.get("publicationId") != current_publication_id
    ]
    for item in candidates:
        if isinstance(item.get("publicationId"), str) and isinstance(item.get("sourceCommit"), str):
            return item
    return None


def _current_verified_target(
    site_config: Mapping[str, Any],
    *,
    current_publication_id: str,
) -> dict[str, Any] | None:
    for item in site_config.get("publicationHistory") or []:
        if (
            isinstance(item, dict)
            and item.get("publicationId") == current_publication_id
            and item.get("verified") is True
            and isinstance(item.get("sourceCommit"), str)
        ):
            return item
    return None


def _application_matches_publication(
    config: PublishingConfig,
    application: Mapping[str, Any],
    *,
    site_id: str,
    hostname: str,
    publication_id: str,
    source_commit: str,
) -> bool:
    desired = desired_application(
        config,
        site_id=site_id,
        hostname=hostname,
        publication_id=publication_id,
        source_commit=source_commit,
    )
    metadata = application.get("metadata", {})
    desired_metadata = desired.get("metadata", {})
    return (
        application_scope_matches(config, application, site_id=site_id)
        and application.get("spec") == desired.get("spec")
        and metadata.get("finalizers") == desired_metadata.get("finalizers")
    )


def _recover_application(
    config: PublishingConfig,
    *,
    workspace: Path,
    site_config: Mapping[str, Any],
    application: Mapping[str, Any],
    site_id: str,
    current_publication_id: str,
    evidence: Mapping[str, Any],
) -> dict[str, Any] | None:
    target = _recovery_target(
        site_config,
        current_publication_id=current_publication_id,
    )
    action = "created" if application is None else "updated"
    if target is None:
        target = _current_verified_target(
            site_config,
            current_publication_id=current_publication_id,
        )
    if target is None:
        return None
    if application is not None and not application_scope_matches(
        config,
        application,
        site_id=site_id,
    ):
        return None
    target_publication_id = str(target["publicationId"])
    target_source_commit = str(target["sourceCommit"])
    desired = desired_application(
        config,
        site_id=site_id,
        hostname=str(site_config["hostname"]),
        publication_id=target_publication_id,
        source_commit=target_source_commit,
    )
    resource_version = (
        application.get("metadata", {}).get("resourceVersion")
        if application is not None
        else None
    )
    if resource_version:
        desired["metadata"]["resourceVersion"] = resource_version
    application_name = config.application_name(site_id)
    argocd = ArgoCDClient(config)
    if application is None:
        argocd.create_application(desired)
    else:
        argocd.update_application(application_name, desired)
    action_id = str(uuid4())
    updated = dict(site_config)
    updated["lastSourceCommit"] = target_source_commit
    updated["lastPublicationId"] = target_publication_id
    updated["lastDeploymentActionId"] = action_id
    write_site_config(workspace, updated)
    recovery_evidence = dict(evidence)
    recovery_evidence["recovery"] = {
        "application": application_name,
        "fromPublicationId": current_publication_id,
        "toPublicationId": target_publication_id,
        "action": action,
    }
    return result_envelope(
        operation="status",
        status="RECOVERING",
        phase="RECOVERING",
        site_id=site_id,
        publication_id=target_publication_id,
        deployment_action_id=action_id,
        evidence=recovery_evidence,
        retryable=True,
        next_operation="status",
    )


def _argo_evidence(
    application: Mapping[str, Any] | None,
    *,
    secrets: Sequence[str] = (),
) -> dict[str, Any]:
    if not application:
        return {"found": False, "sync": None, "health": None, "revision": None, "targetRevision": None}
    status = application.get("status") if isinstance(application.get("status"), dict) else {}
    sync = status.get("sync") if isinstance(status.get("sync"), dict) else {}
    health = status.get("health") if isinstance(status.get("health"), dict) else {}
    spec = application.get("spec") if isinstance(application.get("spec"), dict) else {}
    source = spec.get("source") if isinstance(spec.get("source"), dict) else {}
    return {
        "found": True,
        "sync": sync.get("status"),
        "health": health.get("status"),
        "revision": sync.get("revision"),
        "targetRevision": source.get("targetRevision"),
        "message": redact_text(str(health.get("message")), *secrets)
        if health.get("message") is not None
        else None,
    }


def _pipeline_identity_matches(
    client: GitLabClient,
    *,
    project_id: int,
    pipeline_id: int,
    expected_variables: Mapping[str, str],
) -> bool:
    variables = client.pipeline_variables(project_id, pipeline_id)
    actual = {
        item.get("key"): item.get("value")
        for item in variables
        if isinstance(item, dict)
    }
    return all(actual.get(key) == value for key, value in expected_variables.items())


def _status_once(config: PublishingConfig, *, workspace: Path, commit: str | None = None, publication_id: str | None = None) -> dict[str, Any]:
    site_config = load_site_config(workspace)
    site_id = str(site_config["siteId"])
    validate_site_hostname(
        str(site_config["hostname"]),
        site_id=site_id,
        base_domain=config.base_domain,
    )
    source_commit = commit or site_config.get("lastSourceCommit")
    current_publication_id = publication_id or site_config.get("lastPublicationId")
    if not source_commit or not current_publication_id:
        return result_envelope(operation="status", status="UNPUBLISHED", phase="VERIFYING", site_id=site_id, details={"reason": "no publication pointer exists"})
    gitlab = GitLabClient(config)
    project = gitlab.get_project(config.gitlab_project_path)
    if not project or not isinstance(project.get("id"), int):
        raise SkillError("GITLAB_PROJECT_MISSING", "publishing GitLab Project cannot be found.", retryable=True, next_operation="status")
    project_id = int(project["id"])
    pipeline_list = gitlab.pipelines_for_sha(project_id, str(source_commit))
    branch = f"sites/{site_id}"
    expected_pipeline_variables = {
        "AILERON_PUBLISH_TRIGGER": "skill",
        "AILERON_PUBLISH_SITE_ID": site_id,
        "AILERON_PUBLISH_PUBLICATION_ID": str(current_publication_id),
        "AILERON_PUBLISH_SOURCE_COMMIT": str(source_commit),
        "AILERON_PUBLISH_BUILD_TYPE": str(site_config["buildType"]),
    }
    candidates = sorted(
        (
            pipeline
            for pipeline in pipeline_list
            if isinstance(pipeline, dict) and pipeline.get("ref") == branch
        ),
        key=lambda item: int(item.get("id", 0)),
        reverse=True,
    )
    pipeline = next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate.get("id"), int)
            and _pipeline_identity_matches(
                gitlab,
                project_id=project_id,
                pipeline_id=int(candidate["id"]),
                expected_variables=expected_pipeline_variables,
            )
        ),
        None,
    )
    if pipeline is None and candidates:
        latest = candidates[0]
        pipeline_evidence = {
            "projectId": project_id,
            "id": latest.get("id"),
            "status": latest.get("status"),
            "url": latest.get("web_url"),
            "sourceCommit": source_commit,
            "identity": "mismatched",
        }
        return result_envelope(
            operation="status",
            status="FAILED",
            phase="FAILED",
            site_id=site_id,
            publication_id=str(current_publication_id),
            evidence={"git": {"projectId": project_id, "projectPath": config.gitlab_project_path, "commit": source_commit}, "pipeline": pipeline_evidence},
            error_code="PIPELINE_IDENTITY_MISMATCH",
            next_operation="publish",
        )
    pipeline_status = pipeline.get("status") if pipeline else None
    pipeline_evidence = {"projectId": project_id, "id": pipeline.get("id") if pipeline else None, "status": pipeline_status, "url": pipeline.get("web_url") if pipeline else None, "sourceCommit": source_commit}
    evidence = {"git": {"projectId": project_id, "projectPath": config.gitlab_project_path, "commit": source_commit}, "pipeline": pipeline_evidence}
    if pipeline is None or pipeline_status in ACTIVE_PIPELINE_STATUSES:
        return result_envelope(operation="status", status="BUILDING", phase="BUILDING", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, retryable=True, next_operation="status")
    if pipeline_status in FAILED_PIPELINE_STATUSES:
        return result_envelope(operation="status", status="FAILED", phase="FAILED", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, error_code="PIPELINE_FAILED", retryable=False, next_operation="publish")
    if pipeline_status != "success":
        return result_envelope(operation="status", status="UNKNOWN", phase="VERIFYING", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, error_code="GITLAB_PIPELINE_STATUS_UNKNOWN", retryable=True, next_operation="status")

    application_name = config.application_name(site_id)
    application = ArgoCDClient(config).get_application(application_name)
    argo = _argo_evidence(
        application,
        secrets=(config.gitlab_token, config.argocd_token, config.oci_push_password),
    )
    evidence["argocd"] = {"application": application_name, **argo}
    verification_url = f"https://{site_config['hostname']}/_aileron/publication.json"
    verification = _probe_verification(verification_url, ca_pem=config.ca_pem)
    evidence["https"] = verification
    payload = verification.get("payload") if isinstance(verification.get("payload"), dict) else {}
    matches = (
        payload.get("schemaVersion") == 1
        and payload.get("publicationId") == current_publication_id
        and payload.get("siteId") == site_id
        and payload.get("sourceCommit") == source_commit
        and payload.get("buildType") == site_config.get("buildType")
        and payload.get("hostname") == site_config.get("hostname")
    )
    if not argo["found"]:
        recovered = _recover_application(
            config,
            workspace=workspace,
            site_config=site_config,
            application=application,
            site_id=site_id,
            current_publication_id=str(current_publication_id),
            evidence=evidence,
        )
        if recovered:
            return recovered
        return result_envelope(operation="status", status="ARTIFACT_READY", phase="ARTIFACT_READY", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, next_operation="publish")
    contract_matches = _application_matches_publication(
        config,
        application,
        site_id=site_id,
        hostname=str(site_config["hostname"]),
        publication_id=str(current_publication_id),
        source_commit=str(source_commit),
    )
    evidence["argocd"]["contract"] = "matched" if contract_matches else "mismatched"
    if not contract_matches:
        recovered = _recover_application(
            config,
            workspace=workspace,
            site_config=site_config,
            application=application,
            site_id=site_id,
            current_publication_id=str(current_publication_id),
            evidence=evidence,
        )
        if recovered:
            return recovered
        return result_envelope(
            operation="status",
            status="FAILED",
            phase="FAILED",
            site_id=site_id,
            publication_id=str(current_publication_id),
            evidence=evidence,
            error_code="ARGOCD_APPLICATION_CONTRACT_MISMATCH",
            next_operation="publish",
        )
    if argo["health"] in {"Degraded", "Missing", "Unknown"} or argo["sync"] in {"Unknown", "Failed"}:
        recovered = _recover_application(
            config,
            workspace=workspace,
            site_config=site_config,
            application=application,
            site_id=site_id,
            current_publication_id=str(current_publication_id),
            evidence=evidence,
        )
        if recovered:
            return recovered
        return result_envelope(operation="status", status="FAILED", phase="FAILED", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, error_code="ARGOCD_APPLICATION_UNHEALTHY", next_operation="status")
    if argo["sync"] != "Synced" or argo["health"] != "Healthy":
        return result_envelope(operation="status", status="DEPLOYING", phase="DEPLOYING", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, retryable=True, next_operation="status")
    if not matches:
        if verification.get("httpStatus") == 200 and isinstance(payload, dict):
            recovered = _recover_application(
                config,
                workspace=workspace,
                site_config=site_config,
                application=application,
                site_id=site_id,
                current_publication_id=str(current_publication_id),
                evidence=evidence,
            )
            if recovered:
                return recovered
            return result_envelope(operation="status", status="FAILED", phase="FAILED", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, error_code="PUBLICATION_VERIFICATION_MISMATCH", next_operation="publish")
        return result_envelope(operation="status", status="VERIFYING", phase="VERIFYING", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, retryable=True, next_operation="status")
    updated = dict(site_config)
    history = []
    for item in updated.get("publicationHistory") or []:
        if isinstance(item, dict):
            entry = dict(item)
            if entry.get("publicationId") == current_publication_id:
                entry["verified"] = True
            history.append(entry)
    if history:
        updated["publicationHistory"] = history[-20:]
        write_site_config(workspace, updated)
    return result_envelope(operation="status", status="READY", phase="VERIFYING", site_id=site_id, publication_id=str(current_publication_id), evidence=evidence, details={"url": f"https://{site_config['hostname']}"})


def status_once(
    config: PublishingConfig,
    *,
    workspace: Path,
    commit: str | None = None,
    publication_id: str | None = None,
) -> dict[str, Any]:
    with workspace_operation_lock(workspace):
        return _status_once(
            config,
            workspace=workspace,
            commit=commit,
            publication_id=publication_id,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild Canvas Publication status from provider evidence.")
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--commit")
    parser.add_argument("--publication-id")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    import os

    os.environ["AILERON_PUBLISH_OPERATION"] = "status"
    args = build_parser().parse_args(argv)
    return run_cli(lambda: status_once(load_publishing_config(), workspace=args.workspace.resolve(), commit=args.commit, publication_id=args.publication_id))


if __name__ == "__main__":
    raise SystemExit(main())
