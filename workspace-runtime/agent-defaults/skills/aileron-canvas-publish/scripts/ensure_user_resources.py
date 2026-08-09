from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from _common import (
    SCAFFOLD_VERSION,
    SKILL_ROOT,
    GitLabClient,
    PublishingConfig,
    SkillError,
    clone_repository,
    git_has_changes,
    git_remote_head,
    git_push,
    load_publishing_config,
    result_envelope,
    run_cli,
    run_command,
    temporary_directory,
)


SCAFFOLD_ROOT = SKILL_ROOT / "assets" / "user-site-repo"
MARKER_FILE = ".aileron/publishing/repository.json"
KIT_CHECKSUMS_FILE = SKILL_ROOT / "assets" / "kit" / "checksums.sha256"
KIT_MANIFEST_FILE = SKILL_ROOT / "assets" / "kit" / "manifest.json"


def _verify_kit_checksums() -> None:
    try:
        lines = KIT_CHECKSUMS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SkillError(
            "PUBLISHING_KIT_INTEGRITY_INVALID",
            "Skill kit checksum metadata is unavailable.",
        ) from exc
    mismatches: list[str] = []
    entries = 0
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        parts = value.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            mismatches.append(value[:120])
            continue
        expected, relative = parts
        target = (SKILL_ROOT / relative).resolve()
        if target == KIT_CHECKSUMS_FILE.resolve() or SKILL_ROOT.resolve() not in target.parents:
            mismatches.append(relative)
            continue
        entries += 1
        try:
            digest = hashlib.sha256()
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError:
            mismatches.append(relative)
            continue
        if digest.hexdigest() != expected:
            mismatches.append(relative)
    if entries == 0 or mismatches:
        raise SkillError(
            "PUBLISHING_KIT_INTEGRITY_INVALID",
            "Skill kit assets do not match the published checksums.",
            details={"paths": mismatches[:20]},
        )


def _verify_kit_release(config: PublishingConfig) -> None:
    _verify_kit_checksums()
    try:
        manifest = json.loads(KIT_MANIFEST_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SkillError(
            "PUBLISHING_RELEASE_SET_INVALID",
            "Skill kit release manifest is unavailable or invalid.",
        ) from exc
    providers = manifest.get("providers") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("schemaVersion") != 1
        or manifest.get("kitVersion") != config.release_version
        or manifest.get("scaffoldVersion") != SCAFFOLD_VERSION
        or manifest.get("chartSchemaVersion") != 1
        or manifest.get("checksumsFile") != "assets/kit/checksums.sha256"
        or not isinstance(providers, dict)
        or config.build_provider not in providers.get("build", [])
        or config.deploy_provider not in providers.get("deploy", [])
    ):
        raise SkillError(
            "PUBLISHING_RELEASE_SET_INVALID",
            "Workspace publishing configuration does not match the Skill release set.",
            details={"releaseVersion": config.release_version},
        )


def _repo_url(project: Mapping[str, Any]) -> str:
    value = project.get("http_url_to_repo") or project.get("httpUrlToRepo")
    if not isinstance(value, str) or not value:
        raise SkillError("GITLAB_PROJECT_INVALID", "GitLab project does not expose an HTTP repository URL.")
    return value


def _has_head(repo: Path) -> bool:
    completed = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo, check=False, capture_output=True)
    return completed.returncode == 0


def _desired_marker(config: PublishingConfig) -> dict[str, Any]:
    return {
        "version": 1,
        "releaseVersion": config.release_version,
        "scaffoldVersion": SCAFFOLD_VERSION,
        "workspaceId": config.workspace_id,
        "projectPath": config.gitlab_project_path,
    }


def _scaffold_files() -> list[Path]:
    return sorted(path for path in SCAFFOLD_ROOT.rglob("*") if path.is_file() and ".git" not in path.parts)


def _copy_managed_files(
    repo: Path,
    config: PublishingConfig,
    *,
    mutate: bool,
    upgrade: bool,
) -> tuple[list[str], list[str]]:
    marker = repo / MARKER_FILE
    added: list[str] = []
    drifted: list[str] = []
    if marker.exists():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SkillError("MANAGED_SCAFFOLD_INVALID", "repository marker is invalid.") from exc
        if current.get("workspaceId") != config.workspace_id or current.get("projectPath") != config.gitlab_project_path:
            raise SkillError("PUBLISHING_REPOSITORY_IDENTITY_CONFLICT", "repository belongs to another Workspace.")
        marker_drifted = current.get("scaffoldVersion") != SCAFFOLD_VERSION or current.get("releaseVersion") != config.release_version
        if marker_drifted and not (mutate and upgrade):
            raise SkillError(
                "PUBLISHING_VERSION_MISMATCH",
                "repository Release Set does not match this Skill.",
                details={"expectedScaffoldVersion": SCAFFOLD_VERSION, "actualScaffoldVersion": current.get("scaffoldVersion"), "expectedReleaseVersion": config.release_version, "actualReleaseVersion": current.get("releaseVersion")},
                next_operation="upgrade",
            )
        if marker_drifted and mutate and upgrade:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps(_desired_marker(config), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            added.append(MARKER_FILE)
    elif _has_head(repo):
        raise SkillError("PUBLISHING_PROJECT_NOT_EMPTY", "admin-provisioned GitLab Project must be empty or managed by this Skill.")
    elif mutate:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps(_desired_marker(config), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        added.append(MARKER_FILE)

    for source in _scaffold_files():
        relative = source.relative_to(SCAFFOLD_ROOT).as_posix()
        if relative == ".aileron/publishing/repository.json":
            continue
        destination = repo / relative
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                if mutate and upgrade:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
                    added.append(relative)
                else:
                    drifted.append(relative)
            continue
        if mutate:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            added.append(relative)
        else:
            added.append(relative)
    return added, drifted


def _ci_variables(config: PublishingConfig) -> dict[str, tuple[str, bool, str]]:
    return {
        "AILERON_PUBLISH_RELEASE_VERSION": (config.release_version, False, "*"),
        "AILERON_PUBLISH_WORKSPACE_ID": (config.workspace_id, False, "*"),
        "AILERON_PUBLISH_RUNTIME_BASE": (config.runtime_base, False, "*"),
        "AILERON_PUBLISH_NEXTJS_BUILDER": (config.nextjs_builder, False, "*"),
        "AILERON_PUBLISH_OCI_REGISTRY": (config.oci_registry, False, "*"),
        "AILERON_PUBLISH_OCI_SITE_REPOSITORY": (config.oci_site_repository, False, "*"),
        "AILERON_PUBLISH_OCI_CHART_REPOSITORY": (config.oci_chart_repository, False, "*"),
        "AILERON_PUBLISH_BASE_DOMAIN": (config.base_domain, False, "*"),
        "AILERON_PUBLISH_DESTINATION_NAMESPACE": (config.destination_namespace, False, "*"),
        "AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME": (config.image_pull_secret_name, False, "*"),
        "AILERON_PUBLISH_TLS_SECRET_NAME": (config.tls_secret_name, False, "*"),
        "AILERON_PUBLISH_INGRESS_CLASS_NAME": (config.ingress_class_name, False, "*"),
        "AILERON_PUBLISH_OCI_PUSH_USERNAME": (config.oci_push_username, False, "package"),
        "AILERON_PUBLISH_OCI_PUSH_PASSWORD": (config.oci_push_password, True, "package"),
    }


def _configure_ci_variables(client: GitLabClient, config: PublishingConfig, project_id: int) -> None:
    variables = _ci_variables(config)
    for key, (value, masked, environment_scope) in variables.items():
        client.set_variable(
            project_id,
            key,
            value,
            masked=masked,
            environment_scope=environment_scope,
        )


def _check_ci_variables(client: GitLabClient, config: PublishingConfig, project_id: int) -> None:
    missing: list[str] = []
    drifted: list[str] = []
    for key, (expected_value, expected_masked, expected_scope) in _ci_variables(config).items():
        variable = client.get_variable(
            project_id,
            key,
            environment_scope=expected_scope,
        )
        if variable is None:
            missing.append(key)
            continue
        if (
            variable.get("value") != expected_value
            or variable.get("environment_scope", "*") != expected_scope
            or bool(variable.get("masked")) != expected_masked
            or not bool(variable.get("protected"))
        ):
            drifted.append(key)
    if missing or drifted:
        raise SkillError(
            "PUBLISHING_CI_VARIABLES_INCOMPLETE",
            "Skill-owned GitLab CI variables are missing or out of sync.",
            details={"missing": missing, "drifted": drifted},
            next_operation="bootstrap",
        )


def ensure_publishing_repository(
    config: PublishingConfig,
    *,
    mutate: bool,
    upgrade: bool = False,
) -> dict[str, Any]:
    _verify_kit_release(config)
    gitlab = GitLabClient(config)
    project = gitlab.get_project(config.gitlab_project_path)
    if project is None:
        raise SkillError(
            "GITLAB_PROJECT_MISSING",
            "The administrator must create the empty GitLab Project before bootstrap.",
            details={"projectPath": config.gitlab_project_path},
            next_operation="bootstrap",
        )
    actual_path = project.get("path_with_namespace") or project.get("pathWithNamespace")
    if actual_path != config.gitlab_project_path:
        raise SkillError("GITLAB_PROJECT_IDENTITY_CONFLICT", "GitLab project path does not match Workspace configuration.")
    project_id = project.get("id")
    if not isinstance(project_id, int):
        raise SkillError("GITLAB_PROJECT_INVALID", "GitLab project response does not contain a numeric id.")
    repo_url = _repo_url(project)

    with temporary_directory("aileron-publishing-bootstrap-") as temporary:
        repo = temporary / "repo"
        clone_repository(repo_url, repo, token=config.gitlab_token, ca_pem=config.ca_pem, allow_empty=True)
        expected_head = git_remote_head(repo, branch="main", token=config.gitlab_token, ca_pem=config.ca_pem)
        if not _has_head(repo):
            run_command(["git", "checkout", "-B", "main"], cwd=repo, error_code="GIT_OPERATION_FAILED")
        added, drifted = _copy_managed_files(
            repo,
            config,
            mutate=mutate,
            upgrade=upgrade,
        )
        if drifted:
            raise SkillError("MANAGED_SCAFFOLD_DRIFT", "managed publishing files were modified.", details={"paths": drifted}, next_operation="upgrade")
        changed = git_has_changes(repo)
        if (changed or added) and not mutate:
            raise SkillError("PUBLISHING_BOOTSTRAP_REQUIRED", "repository requires bootstrap.", details={"paths": added}, next_operation="bootstrap")
        if changed and mutate:
            run_command(["git", "add", "--all"], cwd=repo, error_code="GIT_OPERATION_FAILED")
            run_command(["git", "commit", "-m", "chore(publishing): bootstrap managed repository [skip ci]"], cwd=repo, error_code="GIT_OPERATION_FAILED")
            git_push(repo, token=config.gitlab_token, ca_pem=config.ca_pem, branch="main", expected_head=expected_head)

    if mutate:
        _configure_ci_variables(gitlab, config, project_id)
    else:
        _check_ci_variables(gitlab, config, project_id)
    return result_envelope(
        operation="bootstrap" if mutate else "check",
        status="READY",
        phase="PREPARING" if mutate else "CHECKING",
        evidence={"git": {"projectId": project_id, "projectPath": config.gitlab_project_path, "repository": repo_url}, "scaffold": {"version": SCAFFOLD_VERSION, "releaseVersion": config.release_version}},
        details={
            "managedFiles": added,
            "ciVariablesSynchronized": mutate,
            "upgrade": upgrade,
        },
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bootstrap the admin-created Canvas publishing repository.")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ensure", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check == args.ensure:
        raise SystemExit("choose exactly one of --check or --ensure")
    os_operation = "check" if args.check else "bootstrap"
    os.environ["AILERON_PUBLISH_OPERATION"] = os_operation
    return run_cli(
        lambda: ensure_publishing_repository(
            load_publishing_config(), mutate=args.ensure
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
