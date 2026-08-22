from __future__ import annotations

import json
import os
import subprocess
import textwrap
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPOSITORY_ROOT / "scripts/deploy/rke2/build-push-images.sh"
CONTRACT = json.loads(
    (REPOSITORY_ROOT / "scripts/deploy/rke2/image-release-contract.json").read_text()
)
COMMIT = "0123456789abcdef0123456789abcdef01234567"
INDEX_DIGEST = f"sha256:{'a' * 64}"
RUNTIME_DIGEST = f"sha256:{'b' * 64}"
ATTESTATION_DIGEST = f"sha256:{'c' * 64}"


def _write_executable(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(0o700)


def _fake_tool_path(tmp_path: Path, *, runtime_digest: str, include_name: bool) -> Path:
    directory = tmp_path / "bin"
    directory.mkdir(mode=0o700)
    _write_executable(
        directory / "git",
        f"""
        #!/usr/bin/env python3
        import sys

        commit = {COMMIT!r}
        arguments = sys.argv[1:]
        if arguments == ["status", "--porcelain"]:
            raise SystemExit(0)
        if arguments == ["rev-parse", "--verify", "HEAD"]:
            print(commit)
            raise SystemExit(0)
        if arguments == ["rev-parse", "--short=12", "HEAD"]:
            print(commit[:12])
            raise SystemExit(0)
        raise SystemExit(f"unexpected git command: {{arguments!r}}")
        """,
    )
    image_document = {
        "image": {
            "os": "linux",
            "architecture": "amd64",
            "config": {
                "Labels": {"org.opencontainers.image.revision": COMMIT},
            },
        },
        "manifest": {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "digest": INDEX_DIGEST,
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": runtime_digest,
                    "platform": {"os": "linux", "architecture": "amd64"},
                },
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": ATTESTATION_DIGEST,
                    "platform": {"os": "unknown", "architecture": "unknown"},
                    "annotations": {
                        "vnd.docker.reference.type": "attestation-manifest",
                        "vnd.docker.reference.digest": runtime_digest,
                    },
                },
            ],
        },
    }
    _write_executable(
        directory / "docker",
        f"""
        #!/usr/bin/env python3
        import json
        import sys

        if sys.argv[1:4] != ["buildx", "imagetools", "inspect"]:
            raise SystemExit(f"unexpected docker command: {{sys.argv[1:]!r}}")
        document = {image_document!r}
        if {include_name!r}:
            document["name"] = sys.argv[4]
        print(json.dumps(document, separators=(",", ":")))
        """,
    )
    _write_executable(
        directory / "uname",
        """
        #!/bin/sh
        printf '%s\\n' x86_64
        """,
    )
    return directory


def _run_script(
    tmp_path: Path,
    *,
    runtime_digest: str = RUNTIME_DIGEST,
    include_name: bool = True,
    omit_components: str = "",
) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = tmp_path / "images.tsv"
    environment = os.environ.copy()
    tool_path = _fake_tool_path(
        tmp_path,
        runtime_digest=runtime_digest,
        include_name=include_name,
    )
    environment["PATH"] = f"{tool_path}:{environment['PATH']}"
    environment.update(
        {
            "EXPECTED_COMMIT": COMMIT,
            "HARBOR_PROJECT": "library",
            "HARBOR_REGISTRY": "harbor.example.test",
            "OUTPUT_FILE": str(output),
            "OMIT_IMAGE_COMPONENTS": omit_components,
        }
    )
    result = subprocess.run(
        [str(SCRIPT)],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    return result, output


def test_build_push_images_records_verified_index_and_runtime_digest_pair(
    tmp_path: Path,
) -> None:
    result, output = _run_script(tmp_path)

    assert result.returncode == 0, result.stderr
    rows = [line.split("\t") for line in output.read_text().splitlines()]
    assert len(rows) == len(CONTRACT["publishedComponents"])
    assert {row[0] for row in rows} == set(CONTRACT["publishedComponents"])
    assert all(len(row) == 6 for row in rows)
    for component, revision, platform, tagged, index_image, runtime_image in rows:
        repository = f"harbor.example.test/library/{component}"
        assert revision == COMMIT
        assert platform == "linux/amd64"
        assert tagged == f"{repository}:git-{COMMIT}"
        assert index_image == f"{repository}@{INDEX_DIGEST}"
        assert runtime_image == f"{repository}@{RUNTIME_DIGEST}"


def test_build_push_images_rejects_equal_index_and_runtime_digest(
    tmp_path: Path,
) -> None:
    result, output = _run_script(tmp_path, runtime_digest=INDEX_DIGEST)

    assert result.returncode != 0
    assert (
        "OCI index and linux/amd64 manifest digests must be distinct" in result.stderr
    )
    assert not output.exists()


def test_build_push_images_omits_external_redis_workload_image(
    tmp_path: Path,
) -> None:
    result, output = _run_script(tmp_path, omit_components="platform-redis")

    assert result.returncode == 0, result.stderr
    components = {line.split("\t", 1)[0] for line in output.read_text().splitlines()}
    assert components == set(CONTRACT["publishedComponents"]) - {"platform-redis"}


def test_build_push_images_rejects_remote_document_without_exact_name(
    tmp_path: Path,
) -> None:
    result, output = _run_script(tmp_path, include_name=False)

    assert result.returncode != 0
    assert "does not match the expected linux/amd64 provenance" in result.stderr
    assert not output.exists()
