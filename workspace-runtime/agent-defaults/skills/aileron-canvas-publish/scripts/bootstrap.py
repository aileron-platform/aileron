from __future__ import annotations

import argparse
import os
from typing import Sequence

from _common import (
    ArgoCDClient,
    GitLabClient,
    SkillError,
    load_publishing_config,
    result_envelope,
    run_cli,
    PublishingConfig,
    SITE_CHART_NAME,
    validate_base_domain,
    validate_image_by_digest,
)
from ensure_user_resources import ensure_publishing_repository


def _validate_argocd_project_policy(config: PublishingConfig, project: object) -> None:
    if not isinstance(project, dict):
        raise SkillError("ARGOCD_PROJECT_INVALID", "Argo CD AppProject response is invalid.")
    spec = project.get("spec")
    if not isinstance(spec, dict):
        raise SkillError("ARGOCD_PROJECT_POLICY_INVALID", "Argo CD AppProject spec is missing.")
    expected_source = f"oci://{config.chart_repository_prefix}/*/{SITE_CHART_NAME}"
    source_repositories = spec.get("sourceRepos")
    destinations = spec.get("destinations")
    namespace_resources = spec.get("namespaceResourceWhitelist")
    if (
        not isinstance(source_repositories, list)
        or not all(isinstance(item, str) for item in source_repositories)
        or set(source_repositories) != {expected_source}
    ):
        raise SkillError(
            "ARGOCD_PROJECT_POLICY_INVALID",
            "Argo CD AppProject must allow only the configured OCI chart repository.",
            details={"expectedSourceRepos": [expected_source]},
        )
    expected_destination = {
        "server": "https://kubernetes.default.svc",
        "namespace": config.destination_namespace,
    }
    if not isinstance(destinations, list) or destinations != [expected_destination]:
        raise SkillError(
            "ARGOCD_PROJECT_POLICY_INVALID",
            "Argo CD AppProject must target only the configured Workspace namespace.",
        )
    if spec.get("clusterResourceWhitelist") != [] or spec.get("clusterResourceBlacklist"):
        raise SkillError(
            "ARGOCD_PROJECT_POLICY_INVALID",
            "Argo CD AppProject must not allow cluster-scoped resources.",
        )
    expected_namespace_resources = [
        {"group": "apps", "kind": "Deployment"},
        {"group": "", "kind": "Service"},
        {"group": "networking.k8s.io", "kind": "Ingress"},
    ]
    actual_namespace_resources = (
        [
            (item.get("group", ""), item.get("kind"))
            for item in namespace_resources
            if isinstance(item, dict)
        ]
        if isinstance(namespace_resources, list)
        else []
    )
    if (
        len(actual_namespace_resources) != len(namespace_resources or [])
        or set(actual_namespace_resources)
        != {(item["group"], item["kind"]) for item in expected_namespace_resources}
        or spec.get("namespaceResourceBlacklist")
    ):
        raise SkillError(
            "ARGOCD_PROJECT_POLICY_INVALID",
            "Argo CD AppProject must allow only the managed site resource kinds.",
        )


def check_platform() -> dict[str, object]:
    config = load_publishing_config()
    validate_base_domain(config.base_domain)
    validate_image_by_digest(config.runtime_base, field="runtime_base")
    validate_image_by_digest(config.nextjs_builder, field="nextjs_builder")
    project = GitLabClient(config).get_project(config.gitlab_project_path)
    if project is None:
        raise SkillError(
            "GITLAB_PROJECT_MISSING",
            "The administrator must create the empty GitLab Project before publishing.",
            details={"projectPath": config.gitlab_project_path},
            next_operation="bootstrap",
        )
    argocd_project = ArgoCDClient(config).get_project(config.argocd_project)
    if argocd_project is None:
        raise SkillError(
            "ARGOCD_PROJECT_MISSING",
            "The configured Argo CD AppProject does not exist.",
            details={"project": config.argocd_project},
        )
    _validate_argocd_project_policy(config, argocd_project)
    repository = ensure_publishing_repository(config, mutate=False)
    return result_envelope(
        operation="check",
        status="READY",
        phase="CHECKING",
        evidence={
            "git": {"projectPath": config.gitlab_project_path, "projectId": project.get("id")},
            "argocd": {"project": config.argocd_project},
            "repository": repository.get("evidence"),
            "releaseSet": {"version": config.release_version},
        },
        details={
            "buildProvider": config.build_provider,
            "deployProvider": config.deploy_provider,
            "adminOwnedPrerequisites": "namespace, DNS, TLS, IngressClass and registry retention are validated by the HomeLab E2E check",
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check or bootstrap Canvas publishing prerequisites.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--ensure", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    operation = "check" if args.check else "bootstrap"
    os.environ["AILERON_PUBLISH_OPERATION"] = operation
    return run_cli(lambda: check_platform() if args.check else ensure_publishing_repository(load_publishing_config(), mutate=True))


if __name__ == "__main__":
    raise SystemExit(main())
