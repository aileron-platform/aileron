from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from _common import (
    GitLabClient,
    PublishingConfig,
    SkillError,
    build_publication_id,
    checkout_branch,
    clone_repository,
    configure_git_identity,
    copy_content_tree,
    dump_json,
    ensure_within,
    git_has_changes,
    git_head,
    git_push,
    git_remote_head,
    git_environment,
    load_json,
    load_publishing_config,
    materialized_ca,
    result_envelope,
    run_cli,
    run_command,
    temporary_directory,
    workspace_operation_lock,
)
from config import resolve_site_config, validate_site_hostname, write_site_config
from bootstrap import check_platform
from deploy import deploy_after_pipeline
from ensure_user_resources import _repo_url


SITE_MANIFEST_PATH = Path(".aileron/publishing/site-manifest.json")
STANDALONE_PATTERN = re.compile(
    r"\boutput\s*:\s*['\"]standalone['\"]", re.MULTILINE
)


def load_canvas_manifest(workspace: Path) -> tuple[dict[str, Any], Path]:
    manifest_path = workspace / ".aileron" / "canvas.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillError(
            "CANVAS_MANIFEST_INVALID",
            "Canvas manifest is missing or invalid JSON.",
        ) from exc
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise SkillError("CANVAS_MANIFEST_INVALID", "Canvas manifest version must be 1.")
    kind = manifest.get("kind")
    if kind not in {"static", "nextjs"}:
        raise SkillError("CANVAS_BUILD_TYPE_UNSUPPORTED", "Canvas kind is not supported.")
    content_dir = manifest.get("contentDir") or manifest.get("sourceRoot")
    if not isinstance(content_dir, str) or not content_dir.strip():
        raise SkillError("CANVAS_MANIFEST_INVALID", "Canvas contentDir is required.")
    raw_content_path = manifest_path.parent / content_dir
    if raw_content_path.is_symlink():
        raise SkillError(
            "PUBLISHING_SOURCE_SYMLINK",
            "Canvas source directory cannot be a symlink.",
        )
    content_path = ensure_within(
        workspace,
        raw_content_path,
        error_code="PUBLISHING_SOURCE_OUTSIDE_WORKSPACE",
    )
    if not content_path.is_dir():
        raise SkillError("PUBLISHING_SOURCE_NOT_FOUND", "Canvas source directory does not exist.")

    build_type = "static" if kind == "static" else "nextjs-standalone"
    if build_type == "static":
        if not (content_path / "index.html").is_file():
            raise SkillError("PUBLISHING_SOURCE_INVALID", "static source must contain index.html.")
    else:
        package_json = content_path / "package.json"
        lockfile = content_path / "package-lock.json"
        if not package_json.is_file() or not lockfile.is_file():
            raise SkillError(
                "NEXTJS_LOCKFILE_REQUIRED",
                "nextjs-standalone source requires package.json and package-lock.json.",
            )
        config_candidates = (
            content_path / "next.config.js",
            content_path / "next.config.mjs",
            content_path / "next.config.ts",
        )
        next_config = next(
            (path for path in config_candidates if path.is_file()),
            None,
        )
        if next_config is None or not STANDALONE_PATTERN.search(
            next_config.read_text(encoding="utf-8")
        ):
            raise SkillError(
                "NEXTJS_STANDALONE_REQUIRED",
                "Next.js source must configure standalone output.",
            )
        package = load_json(package_json, error_code="NEXTJS_PACKAGE_INVALID")
        if not package.get("packageManager"):
            raise SkillError(
                "NEXTJS_PACKAGE_MANAGER_REQUIRED",
                "Next.js source must pin packageManager in package.json.",
            )

    routes = manifest.get("routes") or [{"path": "/"}]
    if not isinstance(routes, list) or not routes:
        raise SkillError("CANVAS_MANIFEST_INVALID", "Canvas routes must be a non-empty array.")
    default_path = manifest.get("defaultPath", "/")
    route_paths = {
        route.get("path") for route in routes if isinstance(route, dict)
    }
    if default_path not in route_paths:
        raise SkillError(
            "CANVAS_MANIFEST_INVALID",
            "Canvas defaultPath must match a declared route.",
        )
    normalized = dict(manifest)
    normalized["buildType"] = build_type
    normalized["routes"] = routes
    normalized["defaultPath"] = default_path
    return normalized, content_path


def site_publishing_manifest(
    *,
    site_id: str,
    requested_slug: str,
    title: str,
    build_type: str,
    hostname: str,
    source_root: str,
    workspace_id: str = "",
) -> dict[str, Any]:
    return {
        "version": 1,
        "siteId": site_id,
        "workspaceId": workspace_id,
        "requestedSlug": requested_slug,
        "title": title,
        "buildType": build_type,
        "hostname": hostname,
        "sourceRoot": source_root,
    }


def _checkout_site_branch(
    repo: Path,
    branch: str,
    *,
    config: PublishingConfig,
    expected_head: str | None,
) -> None:
    if expected_head:
        with materialized_ca(config.ca_pem) as ca_file:
            run_command(
                [
                    "git",
                    "fetch",
                    "origin",
                    f"{branch}:refs/remotes/origin/{branch}",
                ],
                cwd=repo,
                env=git_environment(config.gitlab_token, ca_file),
                error_code="GIT_OPERATION_FAILED",
                secrets=(config.gitlab_token,),
            )
        run_command(
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            cwd=repo,
            error_code="GIT_OPERATION_FAILED",
        )
        return
    checkout_branch(repo, branch, start_point="main")


def _stage_site_branch(
    repo: Path,
    *,
    config: PublishingConfig,
    site_config: Mapping[str, Any],
    canvas_manifest: Mapping[str, Any],
    content_path: Path,
    expected_head: str | None,
    branch: str,
) -> str:
    _checkout_site_branch(repo, branch, config=config, expected_head=expected_head)
    source_root = repo / "source"
    copy_content_tree(content_path, source_root)
    manifest = site_publishing_manifest(
        site_id=str(site_config["siteId"]),
        requested_slug=str(site_config["slug"]),
        title=str(site_config["title"]),
        build_type=str(site_config["buildType"]),
        hostname=str(site_config["hostname"]),
        source_root="source",
        workspace_id=config.workspace_id,
    )
    manifest.update(
        {
            "releaseVersion": config.release_version,
            "runtimeBase": config.runtime_base,
            "nextjsBuilder": config.nextjs_builder,
            "routes": canvas_manifest["routes"],
            "defaultPath": canvas_manifest["defaultPath"],
        }
    )
    (repo / SITE_MANIFEST_PATH).parent.mkdir(parents=True, exist_ok=True)
    dump_json(repo / SITE_MANIFEST_PATH, manifest)
    if not git_has_changes(repo):
        return git_head(repo)
    run_command(
        ["git", "add", "--all", "--", "source", str(SITE_MANIFEST_PATH)],
        cwd=repo,
        error_code="GIT_OPERATION_FAILED",
    )
    run_command(
        [
            "git",
            "commit",
            "-m",
            f"feat(publishing): publish {site_config['siteId']}",
        ],
        cwd=repo,
        error_code="GIT_OPERATION_FAILED",
    )
    return git_head(repo)


def _remember_publication(
    workspace: Path,
    site_config: Mapping[str, Any],
    *,
    source_commit: str,
    publication_id: str,
    deployment_action_id: str | None = None,
) -> None:
    updated = dict(site_config)
    updated["lastSourceCommit"] = source_commit
    updated["lastPublicationId"] = publication_id
    history = [
        item
        for item in (updated.get("publicationHistory") or [])
        if isinstance(item, dict) and item.get("publicationId") != publication_id
    ]
    history.append(
        {
            "publicationId": publication_id,
            "sourceCommit": source_commit,
            "verified": False,
        }
    )
    updated["publicationHistory"] = history[-20:]
    if deployment_action_id:
        updated["lastDeploymentActionId"] = deployment_action_id
    write_site_config(workspace, updated)


ACTIVE_PIPELINE_STATUSES = {
    "created",
    "waiting_for_resource",
    "preparing",
    "pending",
    "running",
    "scheduled",
    "manual",
}


def _reusable_pipeline(
    client: GitLabClient,
    *,
    project_id: int,
    branch: str,
    source_commit: str,
    expected_variables: Mapping[str, str],
) -> dict[str, Any] | None:
    pipelines = client.pipelines_for_sha(project_id, source_commit)
    candidates = sorted(
        (
            pipeline
            for pipeline in pipelines
            if isinstance(pipeline, dict) and pipeline.get("ref") == branch
        ),
        key=lambda pipeline: int(pipeline.get("id", 0)),
        reverse=True,
    )
    for pipeline in candidates:
        if (
            pipeline.get("status") in ACTIVE_PIPELINE_STATUSES | {"success"}
            and _pipeline_identity_matches(
                client,
                project_id=project_id,
                pipeline_id=int(pipeline["id"]),
                expected_variables=expected_variables,
            )
        ):
            return pipeline
    return None


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


def _publish(
    workspace: Path,
    *,
    config: PublishingConfig,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    canvas_manifest, content_path = load_canvas_manifest(workspace)
    check_platform()
    site_config = resolve_site_config(
        workspace,
        title=str(canvas_manifest.get("title") or "Canvas Site"),
        build_type=str(canvas_manifest["buildType"]),
        base_domain=config.base_domain,
    )
    if site_config.get("buildType") != canvas_manifest["buildType"]:
        raise SkillError(
            "SITE_BUILD_TYPE_IMMUTABLE",
            "existing Site build type cannot be changed.",
        )
    validate_site_hostname(
        str(site_config["hostname"]),
        site_id=str(site_config["siteId"]),
        base_domain=config.base_domain,
    )

    gitlab = GitLabClient(config)
    project = gitlab.get_project(config.gitlab_project_path)
    if not project or not isinstance(project.get("id"), int):
        raise SkillError("GITLAB_PROJECT_INVALID", "GitLab Project response is invalid.")
    project_id = int(project["id"])
    branch = f"sites/{site_config['siteId']}"

    with temporary_directory("aileron-publishing-source-") as temporary:
        repo = temporary / "repo"
        clone_repository(
            _repo_url(project),
            repo,
            token=config.gitlab_token,
            ca_pem=config.ca_pem,
        )
        expected_head = git_remote_head(
            repo,
            branch=branch,
            token=config.gitlab_token,
            ca_pem=config.ca_pem,
        )
        configure_git_identity(repo)
        source_commit = _stage_site_branch(
            repo,
            config=config,
            site_config=site_config,
            canvas_manifest=canvas_manifest,
            content_path=content_path,
            expected_head=expected_head,
            branch=branch,
        )
        if source_commit != expected_head:
            git_push(
                repo,
                token=config.gitlab_token,
                ca_pem=config.ca_pem,
                branch=branch,
                expected_head=expected_head,
            )

    publication_id = build_publication_id(
        config.project_identity,
        str(site_config["siteId"]),
        source_commit,
    )
    pipeline_variables = {
        "AILERON_PUBLISH_TRIGGER": "skill",
        "AILERON_PUBLISH_SITE_ID": str(site_config["siteId"]),
        "AILERON_PUBLISH_PUBLICATION_ID": publication_id,
        "AILERON_PUBLISH_SOURCE_COMMIT": source_commit,
        "AILERON_PUBLISH_BUILD_TYPE": str(site_config["buildType"]),
    }
    pipeline = _reusable_pipeline(
        gitlab,
        project_id=project_id,
        branch=branch,
        source_commit=source_commit,
        expected_variables=pipeline_variables,
    )
    if pipeline is None:
        pipeline = gitlab.trigger_pipeline(
            project_id,
            ref=branch,
            variables=pipeline_variables,
        )
    pipeline_id = pipeline.get("id")
    if not isinstance(pipeline_id, int):
        raise SkillError("GITLAB_PIPELINE_INVALID", "GitLab did not return a pipeline id.")

    _remember_publication(
        workspace,
        site_config,
        source_commit=source_commit,
        publication_id=publication_id,
    )
    base_evidence = {
        "git": {
            "projectId": project_id,
            "projectPath": config.gitlab_project_path,
            "branch": branch,
            "commit": source_commit,
        },
        "pipeline": {
            "id": pipeline_id,
            "url": pipeline.get("web_url"),
        },
    }
    try:
        result = deploy_after_pipeline(
            config,
            project_id=project_id,
            pipeline_id=pipeline_id,
            site_id=str(site_config["siteId"]),
            hostname=str(site_config["hostname"]),
            publication_id=publication_id,
            source_commit=source_commit,
            timeout_seconds=timeout_seconds,
        )
    except SkillError as exc:
        if exc.error_code != "PUBLISHING_PIPELINE_TIMEOUT":
            raise
        return result_envelope(
            operation="publish",
            status="UNKNOWN",
            phase="VERIFYING",
            site_id=str(site_config["siteId"]),
            publication_id=publication_id,
            evidence=base_evidence,
            error_code=exc.error_code,
            retryable=True,
            next_operation="status",
        )

    if result.get("deploymentActionId"):
        _remember_publication(
            workspace,
            site_config,
            source_commit=source_commit,
            publication_id=publication_id,
            deployment_action_id=str(result["deploymentActionId"]),
        )
    result.setdefault("evidence", {}).setdefault("git", base_evidence["git"])
    result.setdefault("evidence", {}).setdefault("pipeline", base_evidence["pipeline"])
    result.setdefault("details", {})
    result["details"].update(
        {
            "hostname": site_config["hostname"],
            "buildType": site_config["buildType"],
        }
    )
    return result


def publish(
    workspace: Path,
    *,
    config: PublishingConfig,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    with workspace_operation_lock(workspace):
        return _publish(
            workspace,
            config=config,
            timeout_seconds=timeout_seconds,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the active Aileron Canvas through the configured providers."
    )
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--timeout-seconds", type=int, default=600)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    os.environ["AILERON_PUBLISH_OPERATION"] = "publish"
    args = build_parser().parse_args(argv)
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    return run_cli(
        lambda: publish(
            args.workspace.resolve(),
            config=load_publishing_config(),
            timeout_seconds=args.timeout_seconds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
