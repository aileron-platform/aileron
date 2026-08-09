from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
import re


class BuildError(Exception):
    pass


SENSITIVE_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:\.env(?:\..*)?|\.npmrc|\.pypirc|\.netrc|\.docker/config\.json|"
    r"\.aws/credentials|.*\.(?:pem|key|p12|pfx|crt|cer|secret|token)|"
    r"\.git-credentials|id_(?:rsa|ed25519)(?:\..*)?|"
    r"(?:credential|credentials|secret|secrets)(?:\..*)?)$",
    re.IGNORECASE,
)


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise BuildError(f"missing required pipeline variable: {name}")
    return value


def validate_source_tree(source: Path) -> None:
    if source.is_symlink() or not source.is_dir():
        raise BuildError("managed source directory is missing")
    for path in source.rglob("*"):
        if path.is_symlink():
            raise BuildError("source contains a symlink")
        if SENSITIVE_PATH_PATTERN.search(path.as_posix()):
            raise BuildError("source contains a protected credential-like path")


def run(command: list[str]) -> None:
    completed = subprocess.run(command, check=False)
    if completed.returncode:
        raise BuildError(f"command failed: {command[0]}")


def build_nextjs(source: Path, destination: Path, builder: str) -> None:
    container = f"aileron-canvas-builder-{os.environ.get('CI_JOB_ID', 'local')}"
    run(
        [
            "docker",
            "create",
            "--name",
            container,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "10001:10001",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev",
            "--tmpfs",
            "/workspace:rw,nosuid,nodev",
            "--tmpfs",
            "/output:rw,nosuid,nodev",
            builder,
        ]
    )
    try:
        run(["docker", "cp", f"{source}/.", f"{container}:/workspace"])
        run(["docker", "start", "--attach", container])
        run(["docker", "cp", f"{container}:/output/.", f"{destination}/"])
    finally:
        subprocess.run(
            ["docker", "rm", "--force", container],
            check=False,
            capture_output=True,
        )


def main() -> int:
    output_root = Path(".canvas-build")
    output_site = output_root / "site"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_site.mkdir(parents=True)

    manifest = json.loads(
        Path(".aileron/publishing/site-manifest.json").read_text(encoding="utf-8")
    )
    source = Path(str(manifest["sourceRoot"]))
    validate_source_tree(source)
    build_type = str(manifest["buildType"])
    if build_type == "static":
        shutil.copytree(source, output_site, dirs_exist_ok=True, symlinks=False)
        endpoint_root = output_site
    elif build_type == "nextjs-standalone":
        build_nextjs(source, output_site, required("AILERON_PUBLISH_NEXTJS_BUILDER"))
        endpoint_root = output_site / "public"
        endpoint_root.mkdir(parents=True, exist_ok=True)
    else:
        raise BuildError(f"unsupported managed build type: {build_type}")

    endpoint = {
        "schemaVersion": 1,
        "siteId": required("AILERON_PUBLISH_SITE_ID"),
        "publicationId": required("AILERON_PUBLISH_PUBLICATION_ID"),
        "sourceCommit": required("AILERON_PUBLISH_SOURCE_COMMIT"),
        "releaseVersion": required("AILERON_PUBLISH_RELEASE_VERSION"),
        "hostname": str(manifest["hostname"]),
        "buildType": build_type,
    }
    endpoint_path = endpoint_root / "_aileron" / "publication.json"
    endpoint_path.parent.mkdir(parents=True, exist_ok=True)
    endpoint_path.write_text(
        json.dumps(endpoint, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "buildType": build_type}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BuildError as exc:
        raise SystemExit(str(exc)) from exc
