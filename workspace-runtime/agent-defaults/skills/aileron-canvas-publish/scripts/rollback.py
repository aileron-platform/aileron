from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from _common import (
    ArgoCDClient,
    GitLabClient,
    load_publishing_config,
    result_envelope,
    run_cli,
    SkillError,
    workspace_operation_lock,
)
from config import load_site_config, validate_site_hostname, write_site_config
from deploy import application_scope_matches, desired_application


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


def _rollback(workspace: Path, publication_id: str) -> dict[str, Any]:
    config = load_publishing_config()
    current = load_site_config(workspace)
    site_id = str(current["siteId"])
    validate_site_hostname(
        str(current["hostname"]),
        site_id=site_id,
        base_domain=config.base_domain,
    )
    history = current.get("publicationHistory") or []
    target = next(
        (
            item
            for item in history
            if isinstance(item, dict) and item.get("publicationId") == publication_id
        ),
        None,
    )
    if not isinstance(target, dict) or not isinstance(target.get("sourceCommit"), str):
        raise SkillError(
            "PUBLICATION_HISTORY_MISSING",
            "requested Publication is not present in the local publication history.",
            next_operation="status",
        )
    if target.get("verified") is not True:
        raise SkillError(
            "PUBLICATION_NOT_VERIFIED",
            "rollback only accepts a previously verified Publication.",
            next_operation="status",
        )

    branch = f"sites/{site_id}"
    source_commit = str(target["sourceCommit"])
    gitlab = GitLabClient(config)
    project = gitlab.get_project(config.gitlab_project_path)
    if not project or not isinstance(project.get("id"), int):
        raise SkillError(
            "GITLAB_PROJECT_MISSING",
            "publishing GitLab Project cannot be found.",
            retryable=True,
            next_operation="status",
        )
    project_id = int(project["id"])
    pipelines = gitlab.pipelines_for_sha(project_id, source_commit)
    expected_variables = {
        "AILERON_PUBLISH_TRIGGER": "skill",
        "AILERON_PUBLISH_SITE_ID": site_id,
        "AILERON_PUBLISH_PUBLICATION_ID": publication_id,
        "AILERON_PUBLISH_SOURCE_COMMIT": source_commit,
        "AILERON_PUBLISH_BUILD_TYPE": str(current["buildType"]),
    }
    successful = [
        pipeline
        for pipeline in pipelines
        if (
            isinstance(pipeline, dict)
            and pipeline.get("ref") == branch
            and pipeline.get("status") == "success"
            and isinstance(pipeline.get("id"), int)
        )
    ]
    verified_pipeline = next(
        (
            pipeline
            for pipeline in successful
            if _pipeline_identity_matches(
                gitlab,
                project_id=project_id,
                pipeline_id=int(pipeline["id"]),
                expected_variables=expected_variables,
            )
        ),
        None,
    )
    if verified_pipeline is None:
        if successful:
            raise SkillError(
                "PIPELINE_IDENTITY_MISMATCH",
                "rollback source commit has no successful Skill-triggered pipeline with the requested Publication identity.",
                next_operation="status",
            )
        raise SkillError(
            "PUBLICATION_ARTIFACT_NOT_VERIFIED",
            "rollback source commit has no successful pipeline on the site branch.",
            retryable=True,
            next_operation="status",
        )

    application_name = config.application_name(site_id)
    argocd = ArgoCDClient(config)
    existing = argocd.get_application(application_name)
    if existing is None:
        raise SkillError(
            "ARGOCD_APPLICATION_MISSING",
            "cannot rollback a site without an Argo CD Application.",
            next_operation="publish",
        )
    if not application_scope_matches(config, existing, site_id=site_id):
        raise SkillError(
            "ARGOCD_APPLICATION_CONTRACT_MISMATCH",
            "refusing to update an Argo CD Application outside the managed site scope.",
            next_operation="status",
        )
    expected_resource_version = existing.get("metadata", {}).get("resourceVersion")
    latest = argocd.get_application(application_name)
    if latest is None:
        raise SkillError(
            "ARGOCD_APPLICATION_MISSING",
            "Argo CD Application disappeared while rollback was being prepared.",
            retryable=True,
            next_operation="status",
        )
    if latest.get("metadata", {}).get("resourceVersion") != expected_resource_version:
        raise SkillError(
            "ROLLBACK_CONFLICT",
            "Argo CD Application changed while rollback was being prepared.",
            retryable=True,
            next_operation="status",
        )
    if not application_scope_matches(config, latest, site_id=site_id):
        raise SkillError(
            "ARGOCD_APPLICATION_CONTRACT_MISMATCH",
            "refusing to update an Argo CD Application outside the managed site scope.",
            next_operation="status",
        )

    application = desired_application(
        config,
        site_id=site_id,
        hostname=str(current["hostname"]),
        publication_id=publication_id,
        source_commit=source_commit,
    )
    if expected_resource_version:
        application["metadata"]["resourceVersion"] = expected_resource_version
    argocd.update_application(application_name, application)
    action_id = str(uuid4())
    updated = dict(current)
    updated["lastSourceCommit"] = source_commit
    updated["lastPublicationId"] = publication_id
    updated["lastDeploymentActionId"] = action_id
    write_site_config(workspace, updated)
    return result_envelope(
        operation="rollback",
        status="DEPLOYING",
        phase="DEPLOYING",
        site_id=site_id,
        publication_id=publication_id,
        deployment_action_id=action_id,
        evidence={
            "git": {
                "projectId": project_id,
                "projectPath": config.gitlab_project_path,
                "branch": branch,
                "commit": source_commit,
                "pipelineId": verified_pipeline["id"],
                "pipelineStatus": verified_pipeline["status"],
            },
            "argocd": {"application": application_name, "action": "updated"},
        },
        next_operation="status",
    )


def rollback(workspace: Path, publication_id: str) -> dict[str, Any]:
    with workspace_operation_lock(workspace):
        return _rollback(workspace, publication_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rollback a Canvas site to an existing Publication.")
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--publication-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.environ["AILERON_PUBLISH_OPERATION"] = "rollback"
    args = build_parser().parse_args(argv)
    return run_cli(lambda: rollback(args.workspace.resolve(), args.publication_id))


if __name__ == "__main__":
    raise SystemExit(main())
