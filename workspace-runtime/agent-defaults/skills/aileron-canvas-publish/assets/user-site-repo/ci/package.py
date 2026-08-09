from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


class PackageError(Exception):
    pass


CHART_NAME = "aileron-site"


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise PackageError(f"missing required pipeline variable: {name}")
    return value


def run(command: list[str], *, capture: bool = False) -> str:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=capture,
        text=True,
    )
    if completed.returncode:
        raise PackageError(f"command failed: {command[0]}")
    return completed.stdout.strip() if capture else ""


def site_hash(site_id: str) -> str:
    return hashlib.sha256(site_id.encode("utf-8")).hexdigest()[:12]


def chart_version(publication_id: str) -> str:
    suffix = publication_id.removeprefix("pub-")
    if not re.fullmatch(r"[0-9a-f]{32}", suffix):
        raise PackageError("publicationId does not have the managed format")
    return f"0.1.0-{suffix}"


def image_digest(repository: str) -> str:
    output = run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{range .RepoDigests}}{{println .}}{{end}}",
            repository,
        ],
        capture=True,
    )
    for line in output.splitlines():
        if line.startswith(f"{repository}@sha256:"):
            return line.split("@", 1)[1]
    raise PackageError("registry did not return an immutable image digest")


def existing_image_digest(repository: str) -> str | None:
    completed = subprocess.run(
        ["docker", "manifest", "inspect", "--verbose", repository],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        output = f"{completed.stdout}\n{completed.stderr}".lower()
        if any(
            marker in output
            for marker in ("manifest unknown", "no such manifest", "not found", "404")
        ):
            return None
        raise PackageError("cannot inspect existing OCI image artifact")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PackageError("registry returned an invalid image manifest") from exc

    def find_digest(value: object) -> str | None:
        if isinstance(value, dict):
            digest = value.get("digest")
            if isinstance(digest, str) and digest.startswith("sha256:"):
                return digest
            for child in value.values():
                found = find_digest(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_digest(child)
                if found:
                    return found
        return None

    digest = find_digest(payload)
    if not digest:
        raise PackageError("registry image manifest has no immutable digest")
    return digest


def existing_chart_values(repository: str, version: str) -> tuple[str, str] | None:
    reference = f"oci://{repository}"
    chart = subprocess.run(
        ["helm", "show", "chart", reference, "--version", version],
        check=False,
        capture_output=True,
        text=True,
    )
    if chart.returncode:
        output = f"{chart.stdout}\n{chart.stderr}".lower()
        if "not found" in output or "404" in output:
            return None
        raise PackageError("cannot inspect existing OCI Helm chart")
    app_version = re.search(r"(?m)^appVersion:\s*['\"]?([^'\"\s]+)", chart.stdout)
    if not app_version:
        raise PackageError("existing OCI Helm chart has no managed appVersion")
    values = subprocess.run(
        ["helm", "show", "values", reference, "--version", version],
        check=False,
        capture_output=True,
        text=True,
    )
    if values.returncode:
        raise PackageError("cannot inspect existing OCI Helm chart values")
    return app_version.group(1), values.stdout


def registry_login(registry: str, username: str, password: str) -> None:
    result = subprocess.run(
        ["docker", "login", registry, "--username", username, "--password-stdin"],
        input=password + "\n",
        text=True,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise PackageError("OCI registry login failed")
    result = subprocess.run(
        ["helm", "registry", "login", registry, "--username", username, "--password-stdin"],
        input=password + "\n",
        text=True,
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise PackageError("Helm OCI registry login failed")


def main() -> int:
    site_id = required("AILERON_PUBLISH_SITE_ID")
    publication_id = required("AILERON_PUBLISH_PUBLICATION_ID")
    registry = required("AILERON_PUBLISH_OCI_REGISTRY").rstrip("/")
    site_repository = required("AILERON_PUBLISH_OCI_SITE_REPOSITORY").strip("/")
    chart_repository = required("AILERON_PUBLISH_OCI_CHART_REPOSITORY").strip("/")
    image_repository = f"{registry}/{site_repository}/{site_hash(site_id)}"
    chart_repository_root = f"{registry}/{chart_repository}/{site_hash(site_id)}"
    chart_repository_url = f"{chart_repository_root}/{CHART_NAME}"
    image_tagged = f"{image_repository}:{publication_id}"
    chart_version_value = chart_version(publication_id)
    manifest = json.loads(
        Path(".aileron/publishing/site-manifest.json").read_text(encoding="utf-8")
    )

    registry_login(
        registry,
        required("AILERON_PUBLISH_OCI_PUSH_USERNAME"),
        required("AILERON_PUBLISH_OCI_PUSH_PASSWORD"),
    )
    existing_image = existing_image_digest(image_tagged)
    existing_chart = existing_chart_values(chart_repository_url, chart_version_value)
    if existing_image is not None or existing_chart is not None:
        if existing_image is None or existing_chart is None:
            raise PackageError("PARTIAL_ARTIFACT_STATE")
        app_version, chart_values = existing_chart
        if app_version != publication_id or image_repository not in chart_values or existing_image not in chart_values:
            raise PackageError("ARTIFACT_IDENTITY_CONFLICT")
        print(
            json.dumps(
                {
                    "status": "reused",
                    "imageRepository": image_repository,
                    "imageDigest": existing_image,
                    "chartRepository": chart_repository_url,
                    "chartVersion": chart_version_value,
                },
                sort_keys=True,
            )
        )
        return 0
    run(
        [
            "docker",
            "build",
            "--provenance=false",
            "--build-arg",
            f"RUNTIME_BASE={required('AILERON_PUBLISH_RUNTIME_BASE')}",
            "--file",
            "ci/Dockerfile.site",
            "--tag",
            image_tagged,
            ".canvas-build",
        ]
    )
    run(["docker", "push", image_tagged])
    digest = image_digest(image_tagged)
    if existing_image_digest(image_tagged) != digest:
        raise PackageError("published image digest changed unexpectedly")

    chart_root = Path(".canvas-build/chart")
    if chart_root.exists():
        shutil.rmtree(chart_root)
    shutil.copytree("chart", chart_root)
    (chart_root / "Chart.yaml").write_text(
        "apiVersion: v2\n"
        "name: aileron-site\n"
        f"version: {chart_version_value}\n"
        f"appVersion: {publication_id}\n"
        "type: application\n",
        encoding="utf-8",
    )
    values = {
        "site": {
            "siteId": site_id,
            "workspaceId": required("AILERON_PUBLISH_WORKSPACE_ID"),
            "hostname": str(manifest["hostname"]),
        },
        "image": {"repository": image_repository, "digest": digest},
        "imagePullSecretName": required("AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME"),
        "tlsSecretName": required("AILERON_PUBLISH_TLS_SECRET_NAME"),
        "ingressClassName": required("AILERON_PUBLISH_INGRESS_CLASS_NAME"),
        "resources": {
            "requests": {"cpu": "10m", "memory": "32Mi"},
            "limits": {"cpu": "250m", "memory": "256Mi"},
        },
    }
    (chart_root / "values.yaml").write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    package_path = Path(".canvas-build") / f"aileron-site-{chart_version_value}.tgz"
    run(
        [
            "helm",
            "package",
            str(chart_root),
            "--destination",
            ".canvas-build",
        ]
    )
    if not package_path.is_file():
        raise PackageError("Helm did not create the expected immutable chart package")
    run(["helm", "push", str(package_path), f"oci://{chart_repository_root}"])
    published_chart = existing_chart_values(chart_repository_url, chart_version_value)
    if (
        published_chart is None
        or published_chart[0] != publication_id
        or image_repository not in published_chart[1]
        or digest not in published_chart[1]
    ):
        raise PackageError("published chart identity changed unexpectedly")
    print(
        json.dumps(
            {
                "status": "ok",
                "imageRepository": image_repository,
                "imageDigest": digest,
                "chartRepository": chart_repository_url,
                "chartVersion": chart_version_value,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PackageError as exc:
        raise SystemExit(str(exc)) from exc
