from __future__ import annotations

import hashlib
import time
from typing import Any, Mapping
from uuid import uuid4

from _common import ArgoCDClient, GitLabClient, PublishingConfig, SkillError, result_envelope


def chart_version(publication_id: str) -> str:
    if not publication_id.startswith("pub-"):
        raise SkillError("PUBLICATION_ID_INVALID", "publicationId must start with pub-.")
    suffix = publication_id[4:]
    if len(suffix) != 32 or any(character not in "0123456789abcdef" for character in suffix):
        raise SkillError("PUBLICATION_ID_INVALID", "publicationId must use the managed format.")
    return f"0.1.0-{suffix}"


def desired_application(
    config: PublishingConfig,
    *,
    site_id: str,
    hostname: str,
    publication_id: str,
    source_commit: str,
) -> dict[str, Any]:
    return {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": config.application_name(site_id),
            "namespace": "argocd",
            "finalizers": ["resources-finalizer.argocd.argoproj.io"],
            "labels": {
                "app.kubernetes.io/managed-by": "aileron-canvas-publish",
                "aileron.io/workspace-id": config.workspace_id,
                "aileron.io/site-id-hash": hashlib.sha256(site_id.encode()).hexdigest()[:12],
            },
        },
        "spec": {
            "project": config.argocd_project,
            "source": {
                "repoURL": f"oci://{config.chart_repository(site_id)}",
                "path": ".",
                "targetRevision": chart_version(publication_id),
                "helm": {"releaseName": config.application_name(site_id)},
            },
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": config.destination_namespace,
            },
            "syncPolicy": {
                "automated": {"allowEmpty": False, "prune": True, "selfHeal": True},
                "syncOptions": ["CreateNamespace=false"],
            },
        },
        "info": [
            {"name": "aileron.siteId", "value": site_id},
            {"name": "aileron.publicationId", "value": publication_id},
            {"name": "aileron.sourceCommit", "value": source_commit},
            {"name": "aileron.hostname", "value": hostname},
        ],
    }


def _same_application(existing: Mapping[str, Any], desired: Mapping[str, Any]) -> bool:
    existing_metadata = existing.get("metadata", {})
    desired_metadata = desired.get("metadata", {})
    return (
        existing.get("spec") == desired.get("spec")
        and existing_metadata.get("finalizers") == desired_metadata.get("finalizers")
        and all(
            existing_metadata.get("labels", {}).get(key) == value
            for key, value in desired_metadata.get("labels", {}).items()
        )
    )


def application_scope_matches(
    config: PublishingConfig,
    application: Mapping[str, Any],
    *,
    site_id: str,
) -> bool:
    metadata = application.get("metadata", {})
    spec = application.get("spec", {})
    source = spec.get("source", {})
    destination = spec.get("destination", {})
    labels = metadata.get("labels", {})
    return (
        metadata.get("name") == config.application_name(site_id)
        and metadata.get("namespace") == "argocd"
        and labels.get("app.kubernetes.io/managed-by") == "aileron-canvas-publish"
        and labels.get("aileron.io/workspace-id") == config.workspace_id
        and labels.get("aileron.io/site-id-hash") == hashlib.sha256(site_id.encode()).hexdigest()[:12]
        and spec.get("project") == config.argocd_project
        and source.get("repoURL") == f"oci://{config.chart_repository(site_id)}"
        and source.get("path") == "."
        and destination == {
            "server": "https://kubernetes.default.svc",
            "namespace": config.destination_namespace,
        }
    )


def ensure_site_application(
    config: PublishingConfig,
    *,
    site_id: str,
    hostname: str,
    publication_id: str,
    source_commit: str,
) -> dict[str, Any]:
    desired = desired_application(config, site_id=site_id, hostname=hostname, publication_id=publication_id, source_commit=source_commit)
    client = ArgoCDClient(config)
    existing = client.get_application(config.application_name(site_id))
    action = "unchanged"
    if existing is None:
        client.create_application(desired)
        action = "created"
    elif not application_scope_matches(config, existing, site_id=site_id):
        raise SkillError(
            "ARGOCD_APPLICATION_CONTRACT_MISMATCH",
            "refusing to update an Argo CD Application outside the managed site scope.",
            next_operation="status",
        )
    elif not _same_application(existing, desired):
        payload = dict(desired)
        metadata = dict(payload["metadata"])
        resource_version = existing.get("metadata", {}).get("resourceVersion")
        if resource_version:
            metadata["resourceVersion"] = resource_version
        payload["metadata"] = metadata
        client.update_application(config.application_name(site_id), payload)
        action = "updated"
    return {
        "application": config.application_name(site_id),
        "action": action,
        "targetRevision": desired["spec"]["source"]["targetRevision"],
        "automatedSync": True,
        "prune": True,
        "selfHeal": True,
    }


def wait_for_pipeline(config: PublishingConfig, *, project_id: int, pipeline_id: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    client = GitLabClient(config)
    while True:
        pipeline = client.get_pipeline(project_id, pipeline_id)
        status = pipeline.get("status")
        if status in {"success", "failed", "canceled", "skipped"}:
            return pipeline
        if time.monotonic() >= deadline:
            raise SkillError("PUBLISHING_PIPELINE_TIMEOUT", "Publication Pipeline did not reach a terminal state.", retryable=True, next_operation="status")
        time.sleep(min(5, max(0.1, deadline - time.monotonic())))


def deploy_after_pipeline(
    config: PublishingConfig,
    *,
    project_id: int,
    pipeline_id: int,
    site_id: str,
    hostname: str,
    publication_id: str,
    source_commit: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    pipeline = wait_for_pipeline(config, project_id=project_id, pipeline_id=pipeline_id, timeout_seconds=timeout_seconds)
    if pipeline.get("status") != "success":
        return result_envelope(
            operation="publish",
            status="FAILED",
            phase="FAILED",
            site_id=site_id,
            publication_id=publication_id,
            evidence={"pipeline": {"id": pipeline_id, "status": pipeline.get("status"), "url": pipeline.get("web_url")}},
            error_code="PIPELINE_FAILED",
            next_operation="publish",
        )
    application = ensure_site_application(config, site_id=site_id, hostname=hostname, publication_id=publication_id, source_commit=source_commit)
    return result_envelope(
        operation="publish",
        status="DEPLOYING",
        phase="DEPLOYING",
        site_id=site_id,
        publication_id=publication_id,
        deployment_action_id=str(uuid4()),
        evidence={"pipeline": {"id": pipeline_id, "status": pipeline.get("status"), "url": pipeline.get("web_url")}, "argocd": application},
        next_operation="status",
    )
